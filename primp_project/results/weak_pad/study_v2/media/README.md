# Formal weak-pad V2 replays

These videos restore recorded robot states and measured pad deformation. No controller was rerun. The overlays show actual target loading, certified capacity, installed force cap, and physical body movement relative to the first probe. Hidden pad strength is displayed only as evaluation truth.

| Condition and policy | Outcome | Evidence |
| --- | --- | --- |
| 66 N, adaptive force with fixed posture | SAFE_STOP | [Video](../trials/fr_necessary_a_capacity66_adaptive_force_fixed_posture_seed101/weak_pad_adaptive_force_fixed_posture_20260921T111442_328019Z/media/weak_replay.mp4) · [Preview](../trials/fr_necessary_a_capacity66_adaptive_force_fixed_posture_seed101/weak_pad_adaptive_force_fixed_posture_20260921T111442_328019Z/media/weak_replay.png) · [Provenance](../trials/fr_necessary_a_capacity66_adaptive_force_fixed_posture_seed101/weak_pad_adaptive_force_fixed_posture_20260921T111442_328019Z/media/weak_replay.json) |
| 66 N, adaptive probe | SUCCESS | [Video](../trials/fr_necessary_a_capacity66_adaptive_probe_seed101/weak_pad_adaptive_probe_20260921T111443_104920Z/media/weak_replay.mp4) · [Preview](../trials/fr_necessary_a_capacity66_adaptive_probe_seed101/weak_pad_adaptive_probe_20260921T111443_104920Z/media/weak_replay.png) · [Provenance](../trials/fr_necessary_a_capacity66_adaptive_probe_seed101/weak_pad_adaptive_probe_20260921T111443_104920Z/media/weak_replay.json) |
| 34 N, adaptive probe | RECOVERED_STOP | [Video](../trials/fr_necessary_a_capacity34_adaptive_probe_seed101/weak_pad_adaptive_probe_20260921T111616_248612Z/media/weak_replay.mp4) · [Preview](../trials/fr_necessary_a_capacity34_adaptive_probe_seed101/weak_pad_adaptive_probe_20260921T111616_248612Z/media/weak_replay.png) · [Provenance](../trials/fr_necessary_a_capacity34_adaptive_probe_seed101/weak_pad_adaptive_probe_20260921T111616_248612Z/media/weak_replay.json) |

The 66 N trials share the same condition and seed. The 34 N trial tests recovery on a weaker pad. SAFE_STOP and RECOVERED_STOP are distinct from completed movement. A forward body excursion during a stronger probe alone does not establish task success.

Every video frame was decoded, every preview was visually reviewed, and raw recording hashes match the study journal. [Machine-readable checks](index.json).
