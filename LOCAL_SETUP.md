# Local Miniconda setup

Repository: https://github.com/iit-DLSLab/Quadruped-PyMPC

This checkout is directly in `/home/ibrahim/Documents/GO-2 PRIMP`.
The dedicated environment is named `quadruped-pympc`, at
`/home/ibrahim/miniconda3/envs/quadruped-pympc` (Python 3.12.14).
The checkout is based on commit `519c98e`.

## Run the simulator

```bash
conda activate quadruped-pympc
cd "/home/ibrahim/Documents/GO-2 PRIMP"
python simulation/simulation.py
```

If `conda activate` is unavailable in a new shell, first run:

```bash
source /home/ibrahim/miniconda3/etc/profile.d/conda.sh
```

The upstream configuration selects the Go2 robot and nominal acados MPC.
Use the arrow keys to change forward/yaw velocity and Ctrl to zero velocity.
Controller, robot, gait, and terrain settings are in `quadruped_pympc/config.py`.

## Installation details

Conda and Python packages are selected from the repository's `pixi.lock`,
environment `humble-cuda`, for Linux x86_64. Exact package lists are retained in
`.local-setup/locked-conda-explicit.txt` and `.local-setup/locked-pypi.txt`.
This uses the upstream lock rather than the older, separately maintained
Conda YAML. It includes ROS 2 Humble and JAX 0.10.2 with CUDA 12.9.
Acados' Python interface adds Cython and future-fstrings. The lock omits
`colcon-notification`, so that utility and its dependencies were installed too;
pip selected colcon-core 0.21.3 and setuptools 79.0.1 for compatibility.
The final package state is recorded in `.local-setup/environment-installed.yml`
and `.local-setup/requirements-installed.txt`.

Acados is compiled from the pinned recursive Git submodule using its bundled
BLASFEO and HPIPM libraries. Its Tera renderer is version 0.0.34.
The environment supplies the solver paths automatically. A symlink inside the
environment avoids acados build failures caused by spaces in the checkout path.
The environment also disables JAX GPU memory preallocation and keeps ROS on
localhost by default. Existing Conda environments and shell startup files were
not changed.

A local fix in `simulation/simulation.py` waits for MuJoCo's passive viewer
threads to finish before GLFW shuts down. Without it, a completed graphical
simulation could segfault at interpreter exit. The fix also registers cleanup
for exceptions and keyboard interruption.

Build and verification logs are in `.local-setup/logs/`. Local setup artifacts
are excluded using `.git/info/exclude`; upstream Git ignore rules are unchanged.

## Repeat the bounded simulation checks

From the checkout root with the environment activated:

```bash
python .local-setup/smoke_check.py --seconds 2 --report .local-setup/logs/smoke-nominal.json
python .local-setup/smoke_check.py --controller sampling --device gpu --seconds 2 --report .local-setup/logs/smoke-sampling.json
```

The checks exercise the real controller and MuJoCo simulation, checking finite
states and torques, solver results, and successful completion. Add `--render`
for a short graphical run. Sampling explicitly requires a GPU in the command
above. The default nominal configuration allows one SQP iteration per update;
its iteration-limit status is accepted only when its underlying QP succeeds.

## ROS messages

The custom message workspace has already been built. The repository's ROS
entry points source it automatically. For an interactive Python/ROS session:

```bash
conda activate quadruped-pympc
source "/home/ibrahim/Documents/GO-2 PRIMP/ros2/msgs_ws/install/setup.bash"
```

## Verified on this machine

- `pip check`: no broken requirements.
- Go2 nominal MPC: 999 physics steps, 200 MPC updates, all QP solves successful.
- Go2 sampling MPC: 999 physics steps, 200 MPC updates, 10,000 samples per
  update on the RTX 3080 (`cuda:0`).
- MuJoCo viewer: rendered simulation with clean process exit after the local
  shutdown fix.
- ROS: custom message build, imports, and serialization round trips for all
  eight message types. Hardware communication was not exercised.

Reports and detailed logs are in `.local-setup/logs/`. These are short local
simulation checks, not an exhaustive validation of every robot/controller mode.
