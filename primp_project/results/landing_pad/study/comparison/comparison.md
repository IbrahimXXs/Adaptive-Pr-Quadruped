# Landing-pad planner comparison

Descriptive pilot with one seed and one attempt per planner/height/sensing cell. The ±5 mm heights were excluded from demonstration fitting but were exercised during reactive-controller development; they are training-held-out heights, not untouched engineering test cases. Noisy/delayed sensing is reserved for evaluation and is excluded from demonstration fitting and development. The 0 mm height is a calibration condition. Failed and missing cells remain visible. Impact and completion summaries below use successful trials only, so compare them alongside success and coverage. These data do not establish statistical superiority.

Coverage: **18/18** declared evaluation cells attempted; **18** accepted trials.

The CSV contains every declared cell. JSON includes the split, model provenance, raw acceptance summaries, and consistency checks.

| Planner | Accepted / attempted / planned | Median impact peak (N) | Median tilt change (deg) | Median lowering-to-completion (s) | Median fallback updates | Trials using fallback |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| reactive | 6 / 6 / 6 | 1.479 | 0.496 | 13.613 | 0.0 | 0 / 6 |
| predictive | 6 / 6 / 6 | 1.458 | 0.497 | 13.742 | 0.0 | 0 / 6 |
| learned | 6 / 6 / 6 | 1.744 | 0.489 | 13.620 | 11.5 | 4 / 6 |

Metric medians include accepted trials only. The JSON records the sample count for every metric.

Fallback counts identify departures from a planner's nominal motion: learned-motion fallback extends descent after model phase 1; predictive-planner fallback handles optimization failure. Native contact-triggered recovery in the other planners is not counted as learned-motion fallback.

The learned planner used bounded fallback in **4 / 6** trials with recorded counts (**78 planning updates** total). Success therefore includes the common recovery behavior when invoked.

| Planner | Height (mm) | Sensing | Accepted | Impact peak (N) | Tilt change (deg) | Lowering-to-completion (s) | Fallback updates | Recording |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| reactive | -5 | clean | PASS | 1.449 | 0.482 | 14.526 | 0 | [pad_reactive_20260921T073116_115745Z](<../../evaluation/pad_reactive_20260921T073116_115745Z/pad_report.md>) |
| predictive | -5 | clean | PASS | 1.438 | 0.483 | 14.586 | 0 | [pad_predictive_20260921T073156_135681Z](<../../evaluation/pad_predictive_20260921T073156_135681Z/pad_report.md>) |
| learned | -5 | clean | PASS | 1.350 | 0.463 | 14.496 | 20 | [pad_learned_20260921T073235_006299Z](<../../evaluation/pad_learned_20260921T073235_006299Z/pad_report.md>) |
| reactive | +0 | clean | PASS | 1.510 | 0.497 | 13.592 | 0 | [pad_reactive_20260921T073314_050135Z](<../../evaluation/pad_reactive_20260921T073314_050135Z/pad_report.md>) |
| predictive | +0 | clean | PASS | 1.484 | 0.498 | 13.692 | 0 | [pad_predictive_20260921T073351_881991Z](<../../evaluation/pad_predictive_20260921T073351_881991Z/pad_report.md>) |
| learned | +0 | clean | PASS | 1.942 | 0.488 | 13.582 | 3 | [pad_learned_20260921T073430_105158Z](<../../evaluation/pad_learned_20260921T073430_105158Z/pad_report.md>) |
| reactive | +5 | clean | PASS | 1.452 | 0.509 | 13.024 | 0 | [pad_reactive_20260921T073508_108531Z](<../../evaluation/pad_reactive_20260921T073508_108531Z/pad_report.md>) |
| predictive | +5 | clean | PASS | 1.417 | 0.511 | 13.166 | 0 | [pad_predictive_20260921T073545_475536Z](<../../evaluation/pad_predictive_20260921T073545_475536Z/pad_report.md>) |
| learned | +5 | clean | PASS | 1.687 | 0.522 | 13.152 | 0 | [pad_learned_20260921T073622_969397Z](<../../evaluation/pad_learned_20260921T073622_969397Z/pad_report.md>) |
| reactive | -5 | noisy_delayed | PASS | 1.448 | 0.481 | 14.610 | 0 | [pad_reactive_20260921T073700_409382Z](<../../evaluation/pad_reactive_20260921T073700_409382Z/pad_report.md>) |
| predictive | -5 | noisy_delayed | PASS | 1.451 | 0.482 | 14.730 | 0 | [pad_predictive_20260921T073739_474670Z](<../../evaluation/pad_predictive_20260921T073739_474670Z/pad_report.md>) |
| learned | -5 | noisy_delayed | PASS | 1.342 | 0.466 | 14.538 | 31 | [pad_learned_20260921T073818_880290Z](<../../evaluation/pad_learned_20260921T073818_880290Z/pad_report.md>) |
| reactive | +0 | noisy_delayed | PASS | 1.605 | 0.495 | 13.634 | 0 | [pad_reactive_20260921T073858_000299Z](<../../evaluation/pad_reactive_20260921T073858_000299Z/pad_report.md>) |
| predictive | +0 | noisy_delayed | PASS | 1.541 | 0.496 | 13.792 | 0 | [pad_predictive_20260921T073936_486243Z](<../../evaluation/pad_predictive_20260921T073936_486243Z/pad_report.md>) |
| learned | +0 | noisy_delayed | PASS | 1.801 | 0.489 | 13.658 | 24 | [pad_learned_20260921T074014_952957Z](<../../evaluation/pad_learned_20260921T074014_952957Z/pad_report.md>) |
| reactive | +5 | noisy_delayed | PASS | 1.506 | 0.508 | 13.092 | 0 | [pad_reactive_20260921T074053_396590Z](<../../evaluation/pad_reactive_20260921T074053_396590Z/pad_report.md>) |
| predictive | +5 | noisy_delayed | PASS | 1.466 | 0.509 | 13.282 | 0 | [pad_predictive_20260921T074131_022165Z](<../../evaluation/pad_predictive_20260921T074131_022165Z/pad_report.md>) |
| learned | +5 | noisy_delayed | PASS | 2.027 | 0.528 | 13.014 | 0 | [pad_learned_20260921T074209_475039Z](<../../evaluation/pad_learned_20260921T074209_475039Z/pad_report.md>) |

Measured simulated pad-normal reaction during the first 100 ms after physical contact, including static load.

Roll/pitch change from lowering entry; intentional body motion contributes. CoM reference error is separately recorded.

![Pilot comparison](comparison.png)

No planner ranking is inferred from this small pilot. Broader repetitions and predeclared held-out conditions are needed before making performance claims.
