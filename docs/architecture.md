# Architecture

PlanMetric keeps recognition, association, and measurement separate so that an application can replace its OCR without rewriting the calibration solver.

```text
caller observations ────────────────────┐
                                       v
image → OCRProvider + SpanDetector → GeometricMatcher → ConsensusEstimator
                                                            │
                                             CalibrationResult + checked conversion
                                                            │
                                                  JSON / SVG / caller application
```

## Responsibilities

| Module | Responsibility |
| --- | --- |
| `domain.py`, `config.py` | Frozen observations, evidence, results, and explicit limits |
| `units.py` | Parse complete length labels into millimeters; reject missing context |
| `matching.py` | Gate geometric candidates and solve global one-to-one assignment |
| `consensus.py` | Count independent evidence, test deterministic scalar hypotheses, and fit each axis |
| `pipeline.py` | Compose stages and compute the axis-scale difference flag |
| `adapters.py` | Local Tesseract TSV and conservative tick-marked line detection |
| `io.py`, `cli.py` | Versioned input, evidence export, and command-line orchestration |
| `demo.py` | Original generated drawing with declared observations and truth |

The domain objects are value objects: calibration reads them and returns new decisions. The pipeline injects strategies for association and estimation. OCR and dimension detection use protocol-based adapters. These boundaries keep recognition errors visible in the final evidence rather than hiding them inside a monolithic inference function.

## Replaceable components

`OCRProvider` and `SpanDetector` are exported from `planmetric`. Any object with the following methods can be passed to `inspect_image`; inheritance is unnecessary:

```python
from pathlib import Path

from planmetric import DimensionSpan, DimensionText, inspect_image
from planmetric.demo import create_demo_case


class SuppliedOCR:
    def recognize(self, image_path: Path) -> tuple[DimensionText, ...]:
        return create_demo_case().texts


class SuppliedSpans:
    def detect(self, image_path: Path) -> tuple[DimensionSpan, ...]:
        return create_demo_case().spans


# First run: planmetric demo --output runs/demo --save-image
result = inspect_image(Path("runs/demo/generated.png"), ocr=SuppliedOCR(), detector=SuppliedSpans())
assert result.scale_x == result.scale_y == 10.0
```

This example supplies known observations; it does not perform OCR. A real adapter should preserve original coordinates, return upstream confidence values without inventing them, and keep source IDs when duplicating an observation. Bare numeric OCR output remains unknown unless the adapter has evidence to declare it a dimension.

`calibrate(..., matcher=..., estimator=...)` exposes two further strategy points. Their signatures follow the concrete implementations rather than separate runtime protocols:

- `matcher.match(texts, spans, config)` returns `(tuple[Match, ...], tuple[Rejection, ...])`.
- `estimator.estimate(axis, matches, config)` returns `AxisCalibration` for the requested `"x"` or `"y"` axis.

Subclass `GeometricMatcher` from `planmetric.matching` or `ConsensusEstimator` from `planmetric.consensus` when extending them under those type contracts. Custom implementations own the same obligations: one-to-one matches, finite positive ratios, preserved evidence lineage, explicit incomplete/conflict decisions, and no fabricated missing-axis scale. Conversion trusts an accepted result from the injected estimator.

## Decisions, not hidden corrections

The default matcher uses geometric gates followed by SciPy's global assignment. Dummy assignments let labels remain unmatched. The estimator enumerates one-dimensional scale hypotheses deterministically, counts independent inliers, and refits supported evidence with normalized least squares. It is RANSAC-style consensus without random sampling. X and y are solved separately.

The pipeline does not repair OCR digits, fill in missing units, force both axes to agree, or turn insufficient evidence into a scale. Internally consistent wrong labels can still produce an accepted wrong result. The [generated evaluation](validation.md) includes that boundary; the solver's evidence checks are separate from OCR accuracy.

Rendering lives in `tools/render_demo.py`, outside the runtime pipeline. The public figure is drawn from generated observations and an actual solver result. Exporting a result does not publish caller files or send them to an external service.
