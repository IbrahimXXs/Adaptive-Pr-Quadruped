# Recorded experiments

This index is generated from each recording's metadata and saved analysis summary. PASS means that run passed its recorded acceptance checks; the duration and conditions below define what was tested. UNANALYZED means a completed passing analysis is unavailable.

**Start with the canonical standing and controlled-step baselines.** `CANONICAL.txt` selects a group's reference recording; `LATEST.txt` identifies its most recent recording and does not imply that it passed. New runs are saved in their experiment group and added to this index automatically.

The archive retains completed smoke and development runs for provenance. Historical metadata, raw signals, events, patches, and source snapshots are preserved as recorded; old paths within them describe the layout at recording time. No archived run is counted toward a later milestone merely because its own checks passed.

Machine-readable inventory: [catalog.json](catalog.json). Refresh or list recordings with `python -m primp_project results` from the repository root.

Human-readable purposes and historical notes live in `annotations.json`, keyed by recording ID. Edit that file to label a recording without changing its original metadata; an annotation takes precedence over a purpose saved in metadata.

## Standing

| Recording / purpose | Result | Duration | Samples | Conditions | Files |
| --- | --- | ---: | ---: | --- | --- |
| [standing_20260921T053045_497150Z](standing/standing_20260921T053045_497150Z/)<br>30-second standing baseline · **canonical** | **PASS** | 32 s | 16,000 | viewer on; 30 s standing + 2 s settling | [report](standing/standing_20260921T053045_497150Z/REPORT.md) · [plot](standing/standing_20260921T053045_497150Z/overview.png) · [NPZ](standing/standing_20260921T053045_497150Z/signals.npz) · [CSV](standing/standing_20260921T053045_497150Z/samples.csv) · [config](standing/standing_20260921T053045_497150Z/metadata.json) |
| [standing_20260921T054601_396655Z](standing/standing_20260921T054601_396655Z/)<br>Standing repeat with viewer | **PASS** | 32 s | 16,000 | viewer on; 30 s standing + 2 s settling | [report](standing/standing_20260921T054601_396655Z/REPORT.md) · [plot](standing/standing_20260921T054601_396655Z/overview.png) · [NPZ](standing/standing_20260921T054601_396655Z/signals.npz) · [CSV](standing/standing_20260921T054601_396655Z/samples.csv) · [config](standing/standing_20260921T054601_396655Z/metadata.json) |
| [standing_20260921T060814_841427Z](standing/standing_20260921T060814_841427Z/)<br>Standing regression after step integration · latest | **PASS** | 32 s | 16,000 | headless; 30 s standing + 2 s settling | [report](standing/standing_20260921T060814_841427Z/REPORT.md) · [plot](standing/standing_20260921T060814_841427Z/overview.png) · [NPZ](standing/standing_20260921T060814_841427Z/signals.npz) · [CSV](standing/standing_20260921T060814_841427Z/samples.csv) · [config](standing/standing_20260921T060814_841427Z/metadata.json) |

## Controlled step

| Recording / purpose | Result | Duration | Samples | Conditions | Files |
| --- | --- | ---: | ---: | --- | --- |
| [step_20260921T060420_894576Z](controlled_step/step_20260921T060420_894576Z/)<br>Default three-cycle step baseline · **canonical** | **PASS** | 96.064 s | 48,032 | headless; 3 cycles; 6 s hold; μ=0.8 | [report](controlled_step/step_20260921T060420_894576Z/step_report.md) · [plot](controlled_step/step_20260921T060420_894576Z/step_overview.png) · [NPZ](controlled_step/step_20260921T060420_894576Z/signals.npz) · [CSV](controlled_step/step_20260921T060420_894576Z/samples.csv) · [config](controlled_step/step_20260921T060420_894576Z/metadata.json) |
| [step_20260921T060615_222958Z](controlled_step/step_20260921T060615_222958Z/)<br>Longer holds, lower friction, viewer validation · latest | **PASS** | 108.058 s | 54,029 | viewer on; 3 cycles; 10 s hold; μ=0.6 | [report](controlled_step/step_20260921T060615_222958Z/step_report.md) · [plot](controlled_step/step_20260921T060615_222958Z/step_overview.png) · [NPZ](controlled_step/step_20260921T060615_222958Z/signals.npz) · [CSV](controlled_step/step_20260921T060615_222958Z/samples.csv) · [config](controlled_step/step_20260921T060615_222958Z/metadata.json) |

## Archive

| Recording / purpose | Result | Duration | Samples | Conditions | Files |
| --- | --- | ---: | ---: | --- | --- |
| [standing_20260921T053004_991417Z](archive/standing_20260921T053004_991417Z/)<br>Initial standing smoke test | **PASS** | 3 s | 1,500 | headless; 1 s standing + 2 s settling | [report](archive/standing_20260921T053004_991417Z/REPORT.md) · [plot](archive/standing_20260921T053004_991417Z/overview.png) · [NPZ](archive/standing_20260921T053004_991417Z/signals.npz) · [CSV](archive/standing_20260921T053004_991417Z/samples.csv) · [config](archive/standing_20260921T053004_991417Z/metadata.json) |
| [standing_20260921T062300_856009Z](archive/standing_20260921T062300_856009Z/)<br>Standing smoke check after folder reorganization | **PASS** | 3 s | 1,500 | headless; 1 s standing + 2 s settling | [report](archive/standing_20260921T062300_856009Z/REPORT.md) · [plot](archive/standing_20260921T062300_856009Z/overview.png) · [NPZ](archive/standing_20260921T062300_856009Z/signals.npz) · [CSV](archive/standing_20260921T062300_856009Z/samples.csv) · [config](archive/standing_20260921T062300_856009Z/metadata.json) |
| [step_20260921T060306_304122Z](archive/step_20260921T060306_304122Z/)<br>Initial single-cycle development run | **PASS** | 33.348 s | 16,674 | headless; 1 cycle; 6 s hold; μ=0.8 | [report](archive/step_20260921T060306_304122Z/step_report.md) · [plot](archive/step_20260921T060306_304122Z/step_overview.png) · [NPZ](archive/step_20260921T060306_304122Z/signals.npz) · [CSV](archive/step_20260921T060306_304122Z/samples.csv) · [config](archive/step_20260921T060306_304122Z/metadata.json) |
| [step_20260921T062417_687064Z](archive/step_20260921T062417_687064Z/)<br>Controlled-step check after folder reorganization · latest | **PASS** | 33.35 s | 16,675 | headless; 1 cycle; 6 s hold; μ=0.8 | [report](archive/step_20260921T062417_687064Z/step_report.md) · [plot](archive/step_20260921T062417_687064Z/step_overview.png) · [NPZ](archive/step_20260921T062417_687064Z/signals.npz) · [CSV](archive/step_20260921T062417_687064Z/samples.csv) · [config](archive/step_20260921T062417_687064Z/metadata.json) |

- `standing_20260921T053004_991417Z`: One-second smoke test after settling; not the 30-second standing milestone.
- `standing_20260921T062300_856009Z`: One second of standing after settling; verifies the reorganized entry point and recorder.
- `step_20260921T060306_304122Z`: Simulation completed; the analyzer was initially unavailable. Later standalone analysis passed.
- `step_20260921T062417_687064Z`: One full six-second-hold cycle verifies the reorganized CLI, controller, recorder, and analysis.

Each recording directory keeps its raw `signals.npz` and `samples.csv`, configuration in `metadata.json`, contact events, and its analysis report and plot. Controlled-step runs also include phase events and source snapshots. Test and console logs are organized separately under `primp_project/artifacts/`.
