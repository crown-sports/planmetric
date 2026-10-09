# API and input contract

All boxes and endpoints use the same image coordinates: x increases rightward, y downward, and distances are in pixels. Do not mix resized OCR boxes with original-image spans.

## A complete example

```python
from pathlib import Path

from planmetric import calibrate
from planmetric.demo import create_demo_case
from planmetric.io import write_result

case = create_demo_case()
result = calibrate(case.texts, case.spans)

assert result.scale_x == result.scale_y == 10.0
assert result.axis("x").support == result.axis("y").support == 4
assert result.convert_length(320, 0) == 3200.0  # millimeters
assert result.convert_area(320 * 250) == 8_000_000.0  # square millimeters
write_result(result, Path("runs/example"), image_size=(1200, 900))
```

`calibrate(texts, spans, config=None, *, matcher=None, estimator=None)` returns a frozen `CalibrationResult`. It accepts sequences of `DimensionText` and `DimensionSpan`; it does not modify the observations.

## Observations JSON

The following is a valid format example with one horizontal dimension. It returns an **insufficient** calibration because the default requires three independent dimensions per axis.

```json
{
  "schema_version": "1.0",
  "image_size": [400, 200],
  "config": {"default_unit": "mm"},
  "texts": [
    {
      "id": "label-1",
      "text": "3200",
      "box": [130, 30, 190, 50],
      "confidence": 0.92,
      "role": "dimension",
      "source_id": "original-ocr-label-1"
    }
  ],
  "spans": [
    {
      "id": "line-1",
      "p1": {"x": 0, "y": 60},
      "p2": {"x": 320, "y": 60},
      "source_id": "original-dimension-line-1"
    }
  ]
}
```

Required fields are `schema_version`, `texts`, and `spans`. `image_size` is optional and controls the SVG canvas. A text needs `id`, `text`, and `box` in `(x0, y0, x1, y1)` order. Its defaults are `confidence=1.0`, `role="unknown"`, and `source_id=null`. A span needs an `id` and two distinct finite endpoints; its source also defaults to null. IDs must be unique within each observation type.

The supported roles are `dimension`, `unknown`, `room`, and `area`. Room and area labels are excluded. Complete length strings such as `3200 mm`, `3.2 m`, `３２００ 毫米`, and `10' 6"` can be parsed. A bare number requires both `role="dimension"` and an explicit default unit; setting the default unit alone does not turn unknown OCR numbers into dimensions. Unit parsing does not repair mistaken digits. Chinese text parsing does not imply that the default English OCR recognizes Chinese.

`source_id` identifies the original **individual observation**, not the whole drawing. Preserve it when making duplicate candidates from one OCR label or dimension line. Each source contributes at most once per axis. Identical physical spans also count once. Omitting source lineage cannot establish that apparently different observations are independent.

## Configuration and results

| `MetricConfig` field | Default | Meaning |
| --- | --- | --- |
| `default_unit` | `None` | Unit for explicitly declared bare dimensions: `mm`, `cm`, `m`, `in`, or `ft` |
| `min_support` | `3` | Required independent inliers per axis; minimum allowed is 2 |
| `min_inlier_fraction` | `0.6` | Required share of independent matches |
| `max_relative_residual` | `0.025` | Inlier limit: `abs(scale / observed_ratio - 1)` |
| `anisotropic_tolerance` | `0.02` | Flag when `abs(scale_x-scale_y)/max(scale_x,scale_y)` exceeds this |
| `max_text_distance` | `48.0` | Maximum perpendicular box-to-line distance in pixels |
| `max_midpoint_offset` | `0.35` | Maximum along-line label-center offset, divided by span length |
| `orthogonal_tolerance` | `0.02` | Maximum minor/major displacement ratio for an x or y span |
| `min_ocr_confidence` | `0.0` | Optional upstream OCR score filter; no probability is inferred |

`result.axis("x")` and `result.axis("y")` expose `status`, `mm_per_pixel`, `support`, `total`, `evidence`, and `reason`. `total` counts independent matched dimensions. `support` counts inliers to a computed hypothesis; it is zero when too few independent observations exist to run the fit.

| Axis status | Scale | Interpretation |
| --- | --- | --- |
| `accepted` | Positive finite number | Enough independent evidence supports the fit |
| `insufficient` | `None` | Fewer than `min_support` independent matched dimensions |
| `conflict` | `None` | Evidence exists, but no hypothesis meets the support and share requirements |

An inlier in a conflict report belongs to the diagnostic hypothesis; it does not make that axis accepted. Residuals can be null where no fit exists or the residual exceeds numeric range. `anisotropic` is null unless both axes are accepted. It detects unequal axis scales, not the cause of that difference.

`result.matches` preserves text/line associations, geometry, parsed millimeters, and matching costs. `result.rejected` records parse, geometry, duplicate-source, and consensus rejection reasons. `result.to_dict()` produces output schema version `1.0`, with `axes` keyed by `x` and `y`, plus `matches`, `rejected`, `anisotropic`, and unit declarations.

`convert_length(dx, dy)` returns millimeters and requires an accepted scale for each nonzero displacement axis. `convert_area(area_pixels)` returns square millimeters and requires both axes. Missing scales, negative area, nonfinite inputs, and numeric overflow/underflow raise `ValueError`. Accepted consensus is not proof that the upstream labels are correct.

## CLI and local image inspection

```bash
planmetric demo --output runs/demo --save-image
planmetric calibrate --observations runs/demo/observations.json --output runs/result
planmetric detect --image runs/demo/generated.png --ocr tesseract --output runs/inspection
```

Every command writes `calibration.json` and `evidence.svg`. The SVG contains dimension geometry and hoverable evidence captions; it does not embed the source image. `demo` also writes generated `observations.json`; `--save-image` adds `generated.png`. Standard output is a JSON summary of axis statuses, scales, support counts, anisotropy, and report paths.

An incomplete or conflicting calibration is a successful diagnostic run, with process exit code **0**. Inspect the axis statuses before measuring. Invalid input, inaccessible files, or a failed local OCR dependency produce an error on stderr and exit code **2**.

`detect` accepts `--tesseract PATH`, `--language eng`, and `--psm 3|6|11|12` (default 11). Tesseract and its language data must already be installed. There is no cloud OCR or automatic model download. The supplied detector handles thin, continuous, orthogonal dimension lines with perpendicular endpoint ticks on both sides; other line styles should use imported spans. OCR observations retain `role="unknown"`, so unmarked numbers remain excluded even with `--default-unit`.

For Python integration, `inspect_image(path, *, ocr, detector, config=None)` accepts the [adapter contracts](architecture.md). `TesseractOCR` and `OrthogonalTickDetector` are available from `planmetric.adapters`.
