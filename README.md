# PlanMetric

**Turn dimension evidence into measurable lengths and areas. See which dimensions support the scale.**

[中文](README.zh-CN.md) · [Releases](https://github.com/crown-sports/planmetric/releases)

![Generated furnished plan, accepted and rejected dimensions, and actual calibrated measurement](examples/demo.png)

This generated example supplies text boxes and dimension spans. The actual solver uses **8 supporting pairs**, rejects **2 inconsistent pairs**, and recovers **10 mm/px on both axes**. A 320×250 px room becomes **3.20×2.50 m, 8.00 m²**. The figure demonstrates calibration; the OCR candidates are supplied inputs.

## Try it

Python 3.10+. No GPU or pretrained model required.

```bash
python -m pip install "git+https://github.com/crown-sports/planmetric.git@v0.2.0"
planmetric demo --output runs/demo
```

The CLI writes `calibration.json` and `evidence.svg`. Open the overlay to inspect the adopted evidence.

```bash
planmetric calibrate --observations /private/dimensions.json --output runs/result
```

For image inspection, install Tesseract separately and choose the language data you are allowed to use:

```bash
planmetric detect --image /private/plan.png --ocr tesseract \
  --default-unit mm --output runs/inspection
```

The image adapters propose OCR text and orthogonal dimension spans. They can miss or misread evidence; imported observations remain the controlled integration path. [Input contract and API](docs/api.md).

## What changes for your application

| Problem | Result |
| --- | --- |
| A wall or room polygon has only pixel coordinates | Length and area conversion through supported metric calibration |
| One dimension was misread | Per-dimension residuals and adoption/rejection reasons |
| An image was stretched differently in x and y | Separate axis scales and a stretch diagnostic |
| Missing units, insufficient dimensions or conflicting evidence | An explicit incomplete/conflict result, without inventing a scale |

Use the original-coordinate geometry from [WallGraph](https://github.com/crown-sports/wallgraph) or [PlanRegions](https://github.com/crown-sports/planregions). Keep the source drawing and measurement overlay available for review.

## Measure wall paths and room areas

Available in v0.2.0; install the release above to use this command.

```bash
planmetric measure --observations /private/dimensions.json \
  --geometry runs/regions/regions.json --output runs/measurements.json
```

Accepts `planregions/1` room exports or `wallgraph/1` wall exports. Observations must
declare the same `image_size`; coordinate contracts are checked before measurement.
The report retains the full calibration evidence and input digests. Room area uses
instance pixel counts, preserving excluded holes; wall length sums calibrated path
segments, including unequal x/y scales. Required axes without accepted calibration
fail with exit 2. These are conversions of supplied evidence, not verified site measurements.

## Method and measured boundary

One-to-one geometric assignment → deterministic RANSAC-style scalar hypotheses → supported fit per axis → checked conversion. Distinct source evidence is counted once. [Methods and references](docs/methods.md) · [Architecture](docs/architecture.md).

Generated comparisons test rejection, minority errors, mixed units and unequal resizing. **Internally consistent wrong dimensions still produce a wrong accepted scale**: consensus cannot establish whether every upstream observation is true. The evaluation includes those failures. It is not a real-image OCR accuracy claim. [Full protocol and results](docs/validation.md).

## Development

```bash
python -m pip install -e '.[dev]'
pytest
python tools/render_demo.py --check
python tools/release.py --check
```

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Release contents](docs/releasing.md)

MIT for code. The only image is a code-generated composite demonstration; real drawings, annotations, datasets and weights are not distributed. [Provenance](NOTICE.md).
