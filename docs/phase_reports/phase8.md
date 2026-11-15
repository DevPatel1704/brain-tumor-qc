# Phase 8 report: optional modules

**Data situation: C. Compute tier: 0.**

| Module | Status | Notes |
|---|---|---|
| Tumor profile | **Implemented** | Volumes per region (mL), hemisphere relative to the brain bounding-box midline, centroid, and the most uncertain spot (`btqc.infer.postprocess`), shown in the report panel. Tumor grade and stage are **not** predicted (stated in the UI and model card) |
| Scan comparison | **Not built** | A same-patient overlay needs registration and a follow-up dataset; FeTS has no longitudinal pairs. A side-by-side comparison without registration was not started, because the core came first |
| Literature retrieval (`research_assist/`) | **Not built** | Deferred, as the brief allows ("only after the core is done"). If built, it must stay isolated from the gate, send no case data, and label results "full text" or "abstract only" |

Reason: the brief puts these after a tested core. Time went to the core, the browser tests and the report.
