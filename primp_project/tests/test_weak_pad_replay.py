"""Offline replay must restore platform deformation as well as robot states."""

import json

import mujoco
import numpy as np
import pytest

from primp_project.visualization.weak_pad import read_recording, restore_frame


def recording(tmp_path, *, sink=(0., 0., .01, .02), failed=(False, True, True, True)):
    (tmp_path/"metadata.json").write_text(json.dumps({"experiment": "weak_pad"}))
    (tmp_path/"scene").mkdir()
    (tmp_path/"scene/weak_pad_truth.json").write_text(json.dumps({"sink_depth_m": .06}))
    np.savez(tmp_path/"signals.npz", time_s=np.arange(4)*.1, qpos=np.zeros((4, 7)), qvel=np.zeros((4, 6)),
             phase=np.array(["stand", "probe", "probe", "abort"]), contact_measured=np.zeros((4, 4), bool),
             pad_sink_displacement_m=np.array(sink), pad_failed=np.array(failed))
    return tmp_path


def test_reader_requires_aligned_bounded_deformation(tmp_path):
    directory = recording(tmp_path)
    metadata, truth, data = read_recording(directory)
    assert metadata["experiment"] == "weak_pad"
    np.testing.assert_array_equal(data["pad_sink_displacement_m"], [0., 0., .01, .02])
    assert truth["sink_depth_m"] == .06


@pytest.mark.parametrize("sink,failed", [
    ((0., 0., .02, .01), (False, True, True, True)),
    ((0., 0., .01, .07), (False, True, True, True)),
    ((0., 0., .01, np.nan), (False, True, True, True)),
    ((0., 0., .01, .02), (False, False, False, False)),
])
def test_reader_rejects_physical_deformation_inconsistency(tmp_path, sink, failed):
    with pytest.raises(ValueError):
        read_recording(recording(tmp_path, sink=sink, failed=failed))


def test_qpos_only_replay_is_rejected(tmp_path):
    directory = recording(tmp_path)
    with np.load(directory/"signals.npz") as saved:
        states = {key: saved[key] for key in saved.files if key != "pad_sink_displacement_m"}
    np.savez(directory/"signals.npz", **states)
    with pytest.raises(ValueError, match="deformation signals"):
        read_recording(directory)


def test_restore_frame_moves_pad_and_robot_without_physics_and_can_rewind_preview(monkeypatch):
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <geom name="primp_landing_pad" type="box" pos="0 0 -.005" size=".05 .05 .005"/>
      <body pos="0 0 .1"><freejoint/><geom type="sphere" size=".02" mass="1"/></body>
      </worldbody></mujoco>''')
    data = mujoco.MjData(model)
    def no_physics(*args):
        raise AssertionError("A replay must not call mj_step")
    monkeypatch.setattr(mujoco, "mj_step", no_physics)
    qpos = data.qpos.copy(); qpos[0] = .01
    qvel = np.arange(model.nv)*.01
    restore_frame(model, data, qpos, qvel, 3., .06)
    assert data.time == 3.
    np.testing.assert_array_equal(data.qpos, qpos)
    np.testing.assert_array_equal(data.qvel, qvel)
    assert data.geom_xpos[model.geom("primp_landing_pad").id, 2] == pytest.approx(-.065)
    restore_frame(model, data, qpos, qvel, 1., 0.)
    assert data.time == 1.
    assert data.geom_xpos[model.geom("primp_landing_pad").id, 2] == pytest.approx(-.005)
