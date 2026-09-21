# First standing baseline: passed

Recorded on 2026-09-21 with the Go2 robot and the existing nominal acados
controller, full stance, flat terrain, and human input mode with velocity
commands locked to zero. The viewer ran and closed cleanly.

The recording contains **2 seconds of settling plus 30 seconds of standing**:
16,000 samples at 500 Hz, including 15,000 standing samples. All startup data
is retained. All four feet had measured contact throughout the standing phase,
and the controller planned four-foot support throughout the whole run.

| Standing measurement | Result |
| --- | ---: |
| Maximum horizontal body drift | 3.47 mm |
| Maximum absolute roll or pitch | 1.57 degrees |
| Body height range | 7.46 mm |
| Maximum foot displacement | 0.77 mm |
| RMS linear body speed | 0.000645 m/s |
| RMS angular body speed | 0.000486 rad/s |
| Four-foot measured contact | 100% of standing samples |
| Commanded linear/angular velocity | Zero throughout |
| Successful QP solves | 3,200 / 3,200 over the full run |
| Terminations, resets, numerical warnings, torque clipping | None |

Body and foot drift use fixed anchors at the first standing sample (2.002 s).
All NLP updates returned the configured one-SQP-iteration limit status 2;
their QP subproblems succeeded. This result establishes stable standing, not
full nonlinear optimization convergence or a learned stepping policy.

Canonical recording:
[`runs/standing_20260921T053045_497150Z/`](runs/standing_20260921T053045_497150Z/)

- [Full report and acceptance checks](runs/standing_20260921T053045_497150Z/REPORT.md)
- [Overview plot](runs/standing_20260921T053045_497150Z/overview.png)
- [Raw CSV](runs/standing_20260921T053045_497150Z/samples.csv)
- [Compressed NumPy arrays](runs/standing_20260921T053045_497150Z/signals.npz)
- [Configuration and signal conventions](runs/standing_20260921T053045_497150Z/metadata.json)

The logs include body pose, actual and desired feet, touchdown references,
measured contacts and forces, planned supports and forces, timestamps, phase,
commands, torques, and solver diagnostics.
