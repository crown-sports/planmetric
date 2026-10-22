# Where PlanMetric fits

**User and decision:** a developer with dimension observations and pixel geometry needs a supported scale before presenting lengths or areas. OCR and span candidates are inputs to the calibration decision; the no-model demo isolates that decision and deliberately includes wrong dimensions.

| Current, checkable value | Evidence | Boundary |
| --- | --- | --- |
| Avoid reusing one dimension as multiple independent votes | [`matching.py`](../src/planmetric/matching.py), source/assignment cases in [`test_metric.py`](../tests/test_metric.py) | Duplicate-source metadata must be correct upstream |
| Fit each axis and report insufficient/conflicting evidence | [`consensus.py`](../src/planmetric/consensus.py), [`test_metric.py`](../tests/test_metric.py) | Internally consistent wrong dimensions can still produce an accepted wrong scale |
| Convert wall polylines and exact instance areas on a checked grid | [`measurement.py`](../src/planmetric/measurement.py), [`test_measurement.py`](../tests/test_measurement.py) | Centerline length is not wall-face quantity; supplied geometry is not a site measurement |

A manual pixel-to-unit multiplier is reasonable for one independently checked scale. PlanMetric is useful when a reviewer needs to inspect why several observations were accepted or rejected, or when x/y scaling differs. OCR and general vision models supply candidate text/geometry; they are not replaced here. General geometry libraries such as [Shapely](https://github.com/shapely/shapely) calculate shapes and distances; calibration-evidence policy is this package's additional concern, not a claim of superior geometry algorithms.

[Generated validation](validation.md) records both correct rejections and accepted wrong-scale failures. It does not measure real-image OCR accuracy. [The shared executable example](https://github.com/crown-sports/planportals/blob/main/docs/workflow.md) measures actual PlanRegions and WallGraph exports; the standalone demo remains the quickest way to see planted dimension errors rejected.

**Next priorities:** collect permissioned dimension/line associations with reviewer corrections, evaluate rejection and false acceptance on held-out drawings, then improve adapters. Those data and validated policies could become harder to reproduce over time. Today the evidence is reusable contracts and tested calibration behavior; there is no demonstrated proprietary algorithm, data advantage or production accuracy guarantee.
