# Controlled front-left step: passed

Validated on 2026-09-21 with Go2, nominal acados MPC, and known flat terrain.
**Six full cycles passed across two runs**, with three consecutive cycles per
run and no resets between cycles. Each sequence shifted the body, unloaded
and lifted FL, held it airborne, lowered it, confirmed touchdown, restored
four-foot loading, and recentered.

| Run | Friction | Hold per cycle | Cycles | Simulated duration | Viewer | Result |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| [Default experiment](../../results/controlled_step/step_20260921T060420_894576Z/step_report.md) | 0.8 | 6 s | 3 | 96.064 s | Off | PASS |
| [Longer hold / lower friction](../../results/controlled_step/step_20260921T060615_222958Z/step_report.md) | 0.6 | 10 s | 3 | 108.058 s | On, closed cleanly | PASS |

These runs contain 102,061 samples at 500 Hz and a total of **48 seconds of
continuous verified airborne holds**, divided across six movements.

| Measurement across both runs | Result |
| --- | ---: |
| Commanded FL lift | 30 mm |
| Minimum measured lift during a hold | 27.01 mm |
| Minimum physical CoM support margin during holds | 69.94 mm |
| Maximum absolute body roll or pitch | 0.438 degrees |
| Maximum FL tracking error during lift/hold/lower/confirm | 5.00 mm |
| Maximum support-foot displacement from each cycle's fixed anchor | 7.32 mm |
| Largest FL normal force in first 100 ms after touchdown | 0.91 N |
| Successful QP updates | 20,423 / 20,423 |
| Final four-foot standing per run | 2.004 s |
| Terminations, resets, numerical warnings, torque saturation | None |

During every hold FL had neither physical contact nor planned support, and
all other feet maintained both. The full-horizon schedule kept FL out of
support through lowering and confirmation. Every reload followed at least
100 ms of active FL contact with normal force at least 2 N. The analyzer
checks the recorded contact/force history independently of the controller's
confirmation flag. It also verifies unloading, lift-entry guards, and gradual
force-limit ramps.

Foot displacement measures geometry-center movement; it includes contact
compliance and rolling and is not a direct estimate of sliding distance.
Clearance is relative to the fixed pre-lift foot-center height. Contact forces
are simulated constraint reactions on the foot. The reported touchdown peak
is an instantaneous-force diagnostic over 100 ms, not an integrated impulse.

The retained one-iteration SQP configuration returns NLP status 2; all QP
subproblems succeeded. These results establish repeatability for the tested
flat-ground conditions, rather than nonlinear solver convergence or general
terrain adaptation.

The [default overview plot](../../results/controlled_step/step_20260921T060420_894576Z/step_overview.png)
shows all three cycles. Each linked recording directory includes raw CSV and
NumPy data, phase/contact events, configuration, source snapshots, and the
independent validation report.

See the [controlled-step guide](../controlled_step.md) for commands, phase gates, and
the experiment-local changes to body reference, foot control, and support
schedule. The original [standing baseline](standing.md) remains separate.

All **41 focused tests passed**, covering recording alignment/contact forces,
standing acceptance, trajectory derivatives, support geometry, contact debounce,
phase gates, and intentionally corrupted step logs. A fresh
[30-second standing regression](../../results/standing/standing_20260921T060814_841427Z/REPORT.md)
also passed after these integration changes (plus the usual 2 s settling).

The analyzer was subsequently strengthened to require measured loading above
5 N on every foot over the final 0.2 s of reload, at recenter entry, and throughout
final standing. It now checks the exact configured MPC cadence, including
immediate support-change solves. Both three-cycle recordings pass all **57
checks** after reanalysis; the two archived single-cycle recordings also pass.
Raw measurements, events, and metadata were hash-checked and remain unchanged.
The expanded regression suite passes **112 tests**, including synthetic cases
that previously escaped these loading and cadence checks. The earlier gaps
were limitations of automatic validation, not observed failures in these trials.

The [results catalog](../../results/README.md) also retains earlier runs and
separates them from these selected milestone recordings.
