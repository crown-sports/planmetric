# Calibration and measurement notes

[README](../README.md) · [中文](../README.zh-CN.md)

Dimensions arrive as text boxes and line spans in image coordinates. The matcher assigns them one-to-one, then the solver fits each axis and records supporting observations, residuals and rejection reasons. Source IDs prevent one observation from being counted as several independent votes. [Matching](../src/planmetric/matching.py) · [Consensus](../src/planmetric/consensus.py) · [Tests](../tests/test_metric.py).

`measure` checks the source grid, keeps the calibration in its report and converts the supplied geometry. Room area comes from labeled-pixel counts, with holes excluded. Wall length sums the centerline segments with separate x/y scales. [Measurement implementation](../src/planmetric/measurement.py) · [Tests](../tests/test_measurement.py).

The first README figure reads actual room measurements from the [shared generated example](https://github.com/crown-sports/planportals/blob/main/docs/workflow.md). The displayed areas are rounded to two decimal places; JSON retains the full conversion. The second figure uses the standalone demo, which deliberately supplies two inconsistent dimensions. Neither runs OCR.

A verified single scale may need only a multiplier. This package keeps the supporting and rejected observations when the scale itself needs review. Consistently wrong observations can still agree on a wrong scale; see the [generated failures](validation.md). A calibrated result is not a site survey or a wall-face quantity.
