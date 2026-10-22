"""Local command-line calibration; caller-owned observations and run directories."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

from PIL import Image

from .adapters import AdapterError, OrthogonalTickDetector, TesseractOCR
from .config import MetricConfig
from .demo import create_demo_case
from .io import observations_to_dict, read_observations, write_json, write_result
from .measurement import measure_geometry
from .pipeline import calibrate, inspect_image


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate floor-plan scales from dimension evidence"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    observations = commands.add_parser(
        "calibrate", help="Use supplied OCR labels and dimension spans"
    )
    observations.add_argument("--observations", required=True, type=Path)
    observations.add_argument("--default-unit", choices=("mm", "cm", "m", "in", "ft"))
    observations.add_argument("--output", required=True, type=Path)
    detect = commands.add_parser("detect", help="Local OCR and thin, orthogonal tick-marked lines")
    detect.add_argument("--image", required=True, type=Path)
    detect.add_argument("--ocr", choices=("tesseract",), default="tesseract")
    detect.add_argument("--tesseract", default="tesseract", help="Existing local executable")
    detect.add_argument("--language", default="eng")
    detect.add_argument("--psm", type=int, choices=(3, 6, 11, 12), default=11)
    detect.add_argument("--default-unit", choices=("mm", "cm", "m", "in", "ft"))
    detect.add_argument("--output", required=True, type=Path)
    demo = commands.add_parser("demo", help="Generate observations; reject planted OCR errors")
    demo.add_argument("--output", required=True, type=Path)
    demo.add_argument("--save-image", action="store_true", help="Also write a generated input PNG")
    measure = commands.add_parser(
        "measure", help="Calibrate and measure upstream wall/room geometry"
    )
    measure.add_argument("--observations", required=True, type=Path)
    measure.add_argument("--geometry", required=True, type=Path)
    measure.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "measure":
            for source in (arguments.observations, arguments.geometry):
                if arguments.output.resolve() == source.resolve() or (
                    arguments.output.exists()
                    and source.exists()
                    and arguments.output.samefile(source)
                ):
                    raise ValueError("measurement output must not overwrite an input")
            texts, spans, config, image_size = read_observations(arguments.observations)
            if image_size is None:
                raise ValueError("measurement observations require image_size for alignment checks")
            result = calibrate(texts, spans, config)
            geometry = json.loads(arguments.geometry.read_text(encoding="utf-8"))
            report = measure_geometry(result, geometry, image_size=image_size)
            report["provenance"] = {
                "observations_sha256": hashlib.sha256(
                    arguments.observations.read_bytes()
                ).hexdigest(),
                "geometry_sha256": hashlib.sha256(arguments.geometry.read_bytes()).hexdigest(),
            }
            write_json(report, arguments.output)
            print(
                json.dumps(
                    {
                        "measurement_count": len(report["measurements"]),
                        "output": str(arguments.output),
                    },
                    allow_nan=False,
                )
            )
            return 0
        if arguments.command == "calibrate":
            texts, spans, config, image_size = read_observations(arguments.observations)
            if arguments.default_unit:
                config = replace(config, default_unit=arguments.default_unit)
            result = calibrate(texts, spans, config)
        elif arguments.command == "detect":
            with Image.open(arguments.image) as image:
                image_size = image.size
            result = inspect_image(
                arguments.image,
                ocr=TesseractOCR(arguments.tesseract, arguments.language, arguments.psm),
                detector=OrthogonalTickDetector(),
                config=MetricConfig(default_unit=arguments.default_unit),
            )
        else:
            case = create_demo_case()
            result = calibrate(case.texts, case.spans)
            image_size = (case.image.shape[1], case.image.shape[0])
            write_json(
                observations_to_dict(case.texts, case.spans, image_size=image_size),
                arguments.output / "observations.json",
            )
            if arguments.save_image:
                Image.fromarray(case.image).save(arguments.output / "generated.png")
        artifacts = write_result(result, arguments.output, image_size=image_size)
        print(
            json.dumps(
                {
                    "axes": {
                        axis.axis: {
                            "status": axis.status,
                            "mm_per_pixel": axis.mm_per_pixel,
                            "support": axis.support,
                            "total": axis.total,
                        }
                        for axis in result.axes
                    },
                    "anisotropic": result.anisotropic,
                    "outputs": [str(path) for path in artifacts],
                },
                allow_nan=False,
            )
        )
        return 0
    except (AdapterError, ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        print(f"planmetric: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
