"""Render generated observations and actual PlanMetric evidence in one figure.

The optional --check validates a reviewed public PNG, not an OCR benchmark.
Rendering runs the calibration solver again and stores only the requested figure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from planmetric import MetricConfig, calibrate
from planmetric.demo import create_demo_case

PUBLIC_FIGURE = Path(__file__).resolve().parents[1] / "examples/demo.png"
PUBLIC_FIGURE_SHA256 = "db3eccc04c3724957a7a32c37245f397043f1f87511823024dd946d23d6503de"
SIZE = (1560, 1000)
BG = "#edf2f7"
INK = "#13273c"
MUTED = "#52677c"
TEAL = "#009d8a"
RED = "#db4f45"


def font(size: int) -> ImageFont.ImageFont:
    """Use Pillow's bundled font; no downloaded or platform font assets."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError as exc:
        raise RuntimeError("Rendering needs Pillow >=10.1 for its bundled scalable font") from exc


def fit_image(
    image: Image.Image, box: tuple[int, int, int, int]
) -> tuple[Image.Image, float, int, int]:
    x0, y0, x1, y1 = box
    ratio = min((x1 - x0) / image.width, (y1 - y0) / image.height)
    resized = image.resize(
        (round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS
    )
    return resized, ratio, x0 + (x1 - x0 - resized.width) // 2, y0 + (y1 - y0 - resized.height) // 2


def check_figure(path: Path) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != PUBLIC_FIGURE_SHA256:
        raise ValueError("PNG differs from the reviewed public figure")
    with Image.open(path) as image:
        if image.format != "PNG" or image.mode != "RGB" or image.size != SIZE or image.info:
            raise ValueError("Figure must be a metadata-free 1560x1000 RGB PNG")
        image.load()


def check_solver_demo() -> None:
    """Rerun numeric evidence; font variation does not change reviewed asset bytes."""
    case = create_demo_case()
    result = calibrate(case.texts, case.spans, MetricConfig())
    evidence = [item for axis in result.axes for item in axis.evidence]
    if sum(item.inlier for item in evidence) != 8 or sum(not item.inlier for item in evidence) != 2:
        raise ValueError("generated demo evidence differs from the reviewed 8/2 split")
    if not math.isclose(result.scale_x or 0, 10.0) or not math.isclose(result.scale_y or 0, 10.0):
        raise ValueError("generated demo scale differs from the reviewed result")
    polygon = case.measurement_polygon
    area_pixels = (
        abs(
            sum(
                p.x * q.y - q.x * p.y
                for p, q in zip(polygon, polygon[1:] + polygon[:1], strict=True)
            )
        )
        / 2
    )
    if not math.isclose(result.convert_area(area_pixels), 8_000_000.0):
        raise ValueError("generated living room area differs from the reviewed 8 m2")


def render_demo() -> tuple[Image.Image, dict]:
    case = create_demo_case()
    result = calibrate(case.texts, case.spans, MetricConfig())
    source = Image.fromarray(case.image).convert("RGB")
    board = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(board)
    draw.text((40, 28), "Pixels in. Dimensions out.", font=font(44), fill=INK)
    draw.text(
        (42, 90),
        "Recover the drawing scale. Expose a wrong dimension before measuring.",
        font=font(22),
        fill=MUTED,
    )
    titles = ("1  Drawing + candidates", "2  Match and reject", "3  Measure in real units")
    x_positions = (32, 548, 1064)
    evidence = {
        (item.text_id, item.span_id): item for axis in result.axes for item in axis.evidence
    }
    inliers = [item for item in evidence.values() if item.inlier]
    outliers = [item for item in evidence.values() if not item.inlier]
    for index, x0 in enumerate(x_positions):
        draw.rounded_rectangle((x0, 145, x0 + 464, 720), radius=18, fill="white")
        draw.text((x0 + 18, 164), titles[index], font=font(23), fill=INK)
        resized, ratio, ox, oy = fit_image(source, (x0 + 12, 210, x0 + 452, 605))
        board.paste(resized, (ox, oy))
        draw = ImageDraw.Draw(board)
        if index == 1:
            texts = {item.id: item for item in case.texts}
            for match in result.matches:
                item = evidence[(match.text_id, match.span_id)]
                color = TEAL if item.inlier else RED
                endpoints = [(ox + p.x * ratio, oy + p.y * ratio) for p in (match.p1, match.p2)]
                draw.line(endpoints, fill=color, width=4)
                for px, py in endpoints:
                    draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=color)
                box = texts[match.text_id].box
                display_box = (
                    ox + box[0] * ratio - 2,
                    oy + box[1] * ratio - 2,
                    ox + box[2] * ratio + 2,
                    oy + box[3] * ratio + 2,
                )
                draw.rectangle(display_box, outline=color, width=3)
            draw.text((x0 + 18, 628), f"{len(inliers)} supporting pairs", font=font(23), fill=TEAL)
            draw.text(
                (x0 + 18, 665), f"{len(outliers)} inconsistent pair(s)", font=font(23), fill=RED
            )
        elif index == 0:
            draw.text(
                (x0 + 18, 628),
                f"{len(case.texts)} text boxes / {len(case.spans)} spans",
                font=font(22),
                fill=INK,
            )
            draw.text(
                (x0 + 18, 665), "OCR and spans are supplied inputs.", font=font(19), fill=MUTED
            )
        else:
            # This polygon belongs to the generated scene. All units use the solver.
            polygon = case.measurement_polygon
            display = [(ox + p.x * ratio, oy + p.y * ratio) for p in polygon]
            draw.line(display + display[:1], fill="#3476d5", width=5)
            width_mm = result.convert_length(polygon[1].x - polygon[0].x, 0)
            height_mm = result.convert_length(0, polygon[2].y - polygon[1].y)
            area_pixels = (
                abs(
                    sum(
                        p.x * q.y - q.x * p.y
                        for p, q in zip(polygon, polygon[1:] + polygon[:1], strict=True)
                    )
                )
                / 2
            )
            area_mm2 = result.convert_area(area_pixels)
            draw.text(
                (x0 + 18, 628),
                f"{width_mm / 1000:.2f} x {height_mm / 1000:.2f} m",
                font=font(27),
                fill="#3476d5",
            )
            draw.text(
                (x0 + 18, 671),
                f"Living room: {area_mm2 / 1_000_000:.2f} m2",
                font=font(22),
                fill=INK,
            )
    for x0, axis in zip((32, 548), ("x", "y"), strict=True):
        calibration = result.axis(axis)
        draw.rounded_rectangle((x0, 750, x0 + 464, 890), radius=18, fill="#dff3ef")
        draw.text(
            (x0 + 20, 768), f"{axis.upper()} scale / {calibration.status}", font=font(22), fill=INK
        )
        value = (
            f"{calibration.mm_per_pixel:.3f} mm/px"
            if calibration.mm_per_pixel is not None
            else "Unavailable"
        )
        draw.text((x0 + 20, 807), value, font=font(33), fill=TEAL)
        draw.text(
            (x0 + 20, 855),
            f"Support: {calibration.support}/{calibration.total} pairs",
            font=font(18),
            fill=MUTED,
        )
    draw.rounded_rectangle((1064, 750, 1528, 890), radius=18, fill="#e1eafa")
    draw.text((1084, 768), "Anisotropic scale check", font=font(22), fill=INK)
    draw.text(
        (1084, 811),
        "Stretch detected" if result.anisotropic else "X / Y agree",
        font=font(31),
        fill="#3476d5",
    )
    draw.text((1084, 855), "Axes solved separately.", font=font(18), fill=MUTED)
    draw.text(
        (40, 923),
        "Generated drawing and OCR/span candidates. Actual solver output; no manual correction.",
        font=font(20),
        fill=MUTED,
    )
    draw.text(
        (40, 958),
        "This demonstrates calibration and evidence checks, not end-to-end OCR accuracy.",
        font=font(18),
        fill=MUTED,
    )
    return board, {
        "source": "programmatically generated demo",
        "protocol": "supplied OCR/span candidates; not image OCR accuracy",
        "input_size": list(source.size),
        "figure_size": list(SIZE),
        "scale_x": result.scale_x,
        "scale_y": result.scale_y,
        "anisotropic": result.anisotropic,
        "supporting_pairs": len(inliers),
        "inconsistent_pairs": len(outliers),
        "measured_width_m": width_mm / 1000,
        "measured_height_m": height_mm / 1000,
        "measured_area_m2": area_mm2 / 1_000_000,
        "result": result.to_dict(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary", type=Path, help="optional local inference record")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_figure(args.output or PUBLIC_FIGURE)
        check_solver_demo()
        print(
            "Reviewed figure hash/format and rerun solver's 8 inliers, 2 outliers, "
            "10 mm/px, 8 m2 verified; no OCR accuracy evaluation"
        )
        return
    if args.output is None:
        parser.error("rendering requires --output")
    board, summary = render_demo()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    board.save(args.output, format="PNG")
    summary["figure_sha256"] = hashlib.sha256(args.output.read_bytes()).hexdigest()
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    print(
        f"Rendered actual calibration: x={summary['scale_x']}, y={summary['scale_y']}, "
        f"{summary['inconsistent_pairs']} inconsistent pair(s)"
    )


if __name__ == "__main__":
    main()
