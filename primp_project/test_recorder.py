"""Physical checks for the contact-force convention and isolated observations."""

from types import SimpleNamespace

import mujoco
import numpy as np
import pytest

from primp_project.recorder import LEGS, StandingRecorder, ground_contacts


def sphere_model(ground_type="plane", height=0.1, gap=0.0):
    ground_position = 'pos="0 0 -0.1"' if ground_type == "box" else ""
    model = mujoco.MjModel.from_xml_string(
        f"""<mujoco>
          <option timestep="0.002" gravity="0 0 -9.81"/>
          <worldbody>
            <geom name="ground" type="{ground_type}" size="3 3 0.1"
                  {ground_position} gap="{gap}"/>
            <body name="foot_body" pos="0 0 {height}">
              <freejoint/>
              <geom name="foot" type="sphere" size="0.1" mass="1"/>
            </body>
          </worldbody>
        </mujoco>"""
    )
    return model, mujoco.MjData(model)


@pytest.mark.parametrize("ground_type, foot_slot", [("plane", 1), ("box", 0)])
def test_settled_sphere_has_upward_weight_support_in_both_geom_orders(ground_type, foot_slot):
    """Collision ordering changes with shape type; the physical reaction does not."""
    model, data = sphere_model(ground_type)
    foot_id = model.geom("foot").id
    for _ in range(1000):
        mujoco.mj_step(model, data)
    mujoco.mj_forward(model, data)
    assert data.ncon == 1
    assert data.contact[0].geom[foot_slot] == foot_id

    contact, force, normal, count = ground_contacts(model, data, [foot_id, -1, -2, -3])

    weight = model.body_mass.sum() * abs(model.opt.gravity[2])
    np.testing.assert_array_equal(contact, [True, False, False, False])
    np.testing.assert_array_equal(count, [1, 0, 0, 0])
    np.testing.assert_allclose(force[0], [0, 0, weight], rtol=1e-6, atol=1e-8)
    np.testing.assert_allclose(normal, [weight, 0, 0, 0], rtol=1e-6, atol=1e-8)
    np.testing.assert_array_equal(force[1:], np.zeros((3, 3)))


def test_detected_but_inactive_gap_contact_is_not_reported_as_support():
    """A collision candidate above the floor is not a load-bearing contact."""
    model, data = sphere_model(height=0.12, gap=0.1)
    mujoco.mj_forward(model, data)
    assert data.ncon == 1
    assert data.contact[0].dist > 0
    assert data.contact[0].efc_address < 0

    contact, force, normal, count = ground_contacts(
        model, data, [model.geom("foot").id, -1, -2, -3]
    )

    assert not contact.any()
    assert not count.any()
    np.testing.assert_array_equal(force, np.zeros((4, 3)))
    np.testing.assert_array_equal(normal, np.zeros(4))


def test_recording_refreshes_only_its_copy_and_retains_independent_samples(tmp_path):
    model = mujoco.MjModel.from_xml_string(
        """<mujoco>
          <option timestep="0.002"/>
          <worldbody>
            <geom type="plane" size="3 3 0.1"/>
            <body name="base" pos="0 0 0.2">
              <freejoint/>
              <geom name="FL" type="sphere" pos="0.2 0.15 -0.1" size="0.1" mass="1"/>
              <geom name="FR" type="sphere" pos="0.2 -0.15 -0.1" size="0.1" mass="1"/>
              <geom name="RL" type="sphere" pos="-0.2 0.15 -0.1" size="0.1" mass="1"/>
              <geom name="RR" type="sphere" pos="-0.2 -0.15 -0.1" size="0.1" mass="1"/>
            </body>
          </worldbody>
        </mujoco>"""
    )
    live = mujoco.MjData(model)
    mujoco.mj_forward(model, live)
    feet_ids = {leg: model.geom(leg).id for leg in LEGS}
    env = SimpleNamespace(
        mjModel=model, mjData=live, _feet_geom_id=feet_ids,
        simulation_time=live.time, simulation_dt=model.opt.timestep,
    )
    cfg = SimpleNamespace(
        robot="test_model", mass=4.0, mpc_params={"type": "nominal"},
        simulation_params={"mpc_frequency": 100},
    )
    recorder = StandingRecorder(tmp_path, 0.01, 0.0, seed=0, rendered=False)
    recorder.start(env, cfg)
    desired = {leg: live.geom_xpos[geom].copy() for leg, geom in feet_ids.items()}
    wb = SimpleNamespace(
        last_des_foot_pos=desired, current_contact=np.ones(4),
        pgg=SimpleNamespace(phase_signal=np.zeros(4)),
        stc=SimpleNamespace(swing_time=[0.0] * 4),
    )
    solver = SimpleNamespace(get_stats=lambda key: np.array([0]) if key == "qp_stat" else 0.001)
    wrapper = SimpleNamespace(
        wb_interface=wb,
        srbd_controller_interface=SimpleNamespace(
            controller=SimpleNamespace(acados_ocp_solver=solver, previous_status=0)
        ),
        nmpc_footholds=desired,
        nmpc_GRFs={leg: np.array([0.0, 0.0, 9.81]) for leg in LEGS},
        get_obs=lambda: {"ref_feet_pos": desired},
    )

    # Integration advances qpos, leaving the live derived geometry at the old state.
    live.qvel[:3] = [0.3, -0.1, 0.2]
    mujoco.mj_step(model, live)
    state_spec = mujoco.mjtState.mjSTATE_INTEGRATION
    before = np.empty(mujoco.mj_stateSize(model, state_spec))
    mujoco.mj_getState(model, live, before, state_spec)
    fields = (
        "qacc", "qacc_warmstart", "geom_xpos", "xipos", "subtree_com",
        "qfrc_constraint", "efc_force", "sensordata",
    )
    derived_before = {name: getattr(live, name).copy() for name in fields}
    contact_before = live.contact.frame.copy()
    warning_before = live.warning.number.copy()

    expected = mujoco.MjData(model)
    mujoco.mj_copyData(expected, model, live)
    mujoco.mj_forward(model, expected)
    assert not np.array_equal(expected.geom_xpos, live.geom_xpos)

    recorder.record_step(
        env, wrapper, episode=0, control_step=0, control_time=0.0,
        action=np.zeros(model.nu), torque_saturated=np.zeros(model.nu, dtype=bool),
        cmd_lin=np.zeros(3), cmd_ang=np.zeros(3), terminated=False, truncated=False,
    )

    after = np.empty_like(before)
    mujoco.mj_getState(model, live, after, state_spec)
    np.testing.assert_array_equal(after, before)
    for name, original in derived_before.items():
        np.testing.assert_array_equal(getattr(live, name), original, err_msg=name)
    np.testing.assert_array_equal(live.contact.frame, contact_before)
    np.testing.assert_array_equal(live.warning.number, warning_before)
    np.testing.assert_allclose(recorder.rows["feet_pos_w"][0], expected.geom_xpos[list(feet_ids.values())])
    np.testing.assert_allclose(recorder.rows["base_pos_w"][0], expected.qpos[:3])
    assert float(recorder.rows["time_s"][0]) == pytest.approx(model.opt.timestep)
    assert float(recorder.rows["control_time_s"][0]) == 0.0

    logged_actual = recorder.rows["feet_pos_w"][0].copy()
    logged_desired = recorder.rows["feet_desired_w"][0].copy()
    desired["FL"][:] = 100.0
    recorder.data.geom_xpos[:] = -100.0
    np.testing.assert_array_equal(recorder.rows["feet_pos_w"][0], logged_actual)
    np.testing.assert_array_equal(recorder.rows["feet_desired_w"][0], logged_desired)
