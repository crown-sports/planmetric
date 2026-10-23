# PlanMetric

Use drawing dimensions to calibrate pixel geometry, then measure wall lengths and room areas.

[中文](README.zh-CN.md) · [v0.2.1](https://github.com/crown-sports/planmetric/releases/tag/v0.2.1)

![Room pixel counts beside the same regions labeled with calibrated square-meter areas](examples/workflow.png)

Generated example: **143,221 living-room pixels → 14.32 m²** at 10 mm/px, with walls excluded and full precision retained in JSON. [Run this example](https://github.com/crown-sports/planportals/blob/main/docs/workflow.md).

## Try calibration first

Python 3.10+. No GPU or pretrained model required.

```bash
python -m pip install "git+https://github.com/crown-sports/planmetric.git@v0.2.1"
planmetric demo --output runs/demo
```

Keep original inputs in a separate folder. Reusing an output folder replaces its generated result files.

Open `runs/demo/evidence.svg` and `calibration.json`. This separate calibration demo includes two deliberately inconsistent dimensions:

![Supplied dimensions, eight accepted pairs, two rejected pairs and a calibrated room](examples/demo.png)

The solver accepts **8 pairs**, rejects **2**, and fits **10 mm/px** on each axis; the supplied 320×250 px rectangle becomes 8 m².

## Measure your geometry

Provide dimension text boxes and spans in the original image coordinates. [Observation format](docs/api.md).

```bash
planmetric measure --observations /private/dimensions.json \
  --geometry runs/regions/regions.json --output runs/measurements.json
```

The command accepts [PlanRegions](https://github.com/crown-sports/planregions) room exports and [WallGraph](https://github.com/crown-sports/wallgraph) wall exports. Both inputs must declare the same image size. The report includes calibration decisions, input hashes and the converted geometry.

Room area uses instance pixel counts, with holes excluded. Wall length follows the exported centerline. Each axis is fitted separately, so x/y stretching is accounted for. If a required axis has no accepted calibration, measurement exits **2**.

For calibration alone:

```bash
planmetric calibrate --observations /private/dimensions.json --output runs/result
```

## Starting from an image

Install Tesseract separately, then use the image adapter:

```bash
planmetric detect --image /private/plan.png --ocr tesseract \
  --default-unit mm --output runs/inspection
```

Review its text and span proposals before using them. The adapter can miss or misread dimensions; the figures above supply their observations directly.

Consistently wrong dimensions can still produce an accepted wrong scale. These outputs measure supplied geometry, not a verified site survey, and centerline length is not wall-face quantity. [Generated tests and known failures](docs/validation.md).

## More

[Implementation notes](docs/product.md) · [API](docs/api.md) · [Methods](docs/methods.md) · [Architecture](docs/architecture.md)

[Contributing](CONTRIBUTING.md) · [Release checks](docs/releasing.md) · [Security](SECURITY.md)

MIT for code and original generated figures. No real drawings, annotations or model weights are included. [Provenance](NOTICE.md).
