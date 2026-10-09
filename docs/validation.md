# Validation and known failures

Version 0.1.0, protocol seed `20261009`. These are generated geometry and text-observation experiments, not a trained OCR benchmark. The protocol is public; the cases are generated in memory rather than distributed as a dataset.

## Reproduce

```bash
python -m pip install -e '.[dev]'
pytest
python tools/render_demo.py --check
python tools/evaluate_generated.py --output /private/metric-evaluation.json
```

The 260 cases cover 13 scenarios, 20 cases each: clean evidence, unequal axis resizing, minority OCR errors, inconsistent dimensions, insufficient support, no evidence, mixed units, geometric distractors, a missing y axis, rounding noise, systematic unit errors, wrong majorities and incorrect span geometry. Each case contributes two axis decisions.

All estimators receive the same geometric matches. The baselines are unchecked median estimation per axis and a single unchecked median across both axes. This isolates scale estimation; it does not compare OCR engines or establish performance against the original application.

## Results

In the 200 contract cases, 260 axes have enough valid evidence and 140 require abstention. A scale counts as correct when its relative error is at most 2%.

| Estimator | Correct supported scales / 260 | Wrong supported scales | Accepted scales without sufficient support / 140 |
| --- | ---: | ---: | ---: |
| Unchecked median per axis | 260 | 0 | 80 |
| Unchecked shared scale | 220 | 40 | 100 |
| PlanMetric consensus | 260 | 0 | 0 |

The 60 challenge cases deliberately violate upstream truth: all dimensions are ten times the true size, three of five agree on twice the true size, or reported spans are half the true extent. **All three estimators accept wrong scales on all 120 challenge axes.** Agreement between observations cannot verify the physical truth of those observations.

Across the complete 520-axis protocol, PlanMetric accepts 260 correct and 120 wrong scales, and abstains on all 140 unsupported axes. The useful gain is explicit evidence requirements and separate axis calibration; systematic upstream errors remain unresolved.

## Image adapter checks

On the original generated furnished plan, local Tesseract 5.5.3 (`eng`, page segmentation mode 11) and the OpenCV tick detector recover 10 mm/px for both axes: x has 4/5 supporting pairs and y has 3/4. One vertical dimension is missed by OCR and is not filled from the known demo observations. This is one smoke check, not an OCR accuracy estimate.

One private furnished drawing produced no usable matched dimensions and an `insufficient` result on both axes. It has no measurement ground truth and is not part of the generated comparison. The drawing and its outputs remain private.

## Engineering checks

Tests cover unit parsing, one-to-one matching, duplicate evidence, abstention, anisotropy, finite arithmetic, immutable observations, adapter failure handling and CLI serialization. Release checks verify the reviewed figure against its actual solver output and allow only one metadata-free generated PNG. CI runs tests, lint, formatting and package builds on Python 3.10 and 3.12.

Lengths and areas still require source review before consequential use. A missing axis prevents area conversion; no axis is inferred from the other one.
