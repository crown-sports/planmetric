"""An original generated drawing and declared dimension observations; no dataset assets."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .domain import DimensionSpan, DimensionText, Point


@dataclass(frozen=True)
class DemoCase:
    image: np.ndarray
    texts: tuple[DimensionText, ...]
    spans: tuple[DimensionSpan, ...]
    scale_x: float
    scale_y: float
    measurement_polygon: tuple[Point, ...]


def create_demo_case() -> DemoCase:
    """Four true dimensions and one deliberately incorrect OCR value on each axis.

    The explicit observations isolate matching/consensus evaluation from OCR accuracy.
    The rendered labels equal the supplied observation strings, including planted errors.
    """
    image = Image.new("RGB", (1200, 900), "#fafbfc")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=19)
    small = ImageFont.load_default(size=15)
    title = ImageFont.load_default(size=25)
    draw.text((160, 25), "GENERATED PLAN / DIMENSION EVIDENCE", font=title, fill="#24334a")
    rooms = [
        (160, 220, 480, 470, "LIVING", "#e9eef2"),
        (480, 220, 760, 470, "KITCHEN", "#f3efe8"),
        (760, 220, 1040, 470, "BEDROOM 01", "#e8eef7"),
        (160, 470, 480, 720, "BEDROOM 02", "#e8eef7"),
        (480, 470, 760, 720, "HALL", "#eeeeeb"),
        (760, 470, 1040, 720, "BATH", "#e5f1ef"),
    ]
    for x0, y0, x1, y1, name, color in rooms:
        draw.rectangle((x0, y0, x1, y1), fill=color)
        draw.text((x0 + 22, y0 + 20), name, fill="#778491", font=small)
    draw.rectangle((160, 220, 1040, 720), outline="#253342", width=12)
    for x in (480, 760):
        draw.line((x, 220, x, 720), fill="#253342", width=10)
    draw.line((160, 470, 1040, 470), fill="#253342", width=10)
    # Windows and door gaps are drawing detail, not additional calibration evidence.
    for y in (305, 365, 545, 605):
        draw.rectangle((154, y, 165, y + 45), fill="#fafbfc", outline="#82939b", width=2)
    for x in (335, 610, 880):
        draw.rectangle((x, 464, x + 48, 476), fill="#fafbfc")
        draw.line((x, 470, x, 423), fill="#6e7d88", width=2)
        draw.arc((x - 47, 423, x + 47, 517), 270, 360, fill="#8b979e", width=2)
    # Furniture adds ordinary linework that the marked-line detector must reject.
    draw.rounded_rectangle(
        (190, 325, 270, 425), radius=8, fill="#c1cad2", outline="#758592", width=2
    )
    draw.rectangle((305, 350, 402, 397), fill="#f7fafb", outline="#83929a", width=2)
    draw.ellipse((414, 380, 450, 416), fill="#8ea890", outline="#69816b", width=2)
    for x0, y0 in ((810, 290), (210, 550)):
        draw.rectangle((x0, y0, x0 + 150, y0 + 110), fill="#fafbfd", outline="#8496a7", width=2)
        draw.rectangle((x0 + 10, y0 + 10, x0 + 65, y0 + 36), outline="#a2b1bf", width=2)
        draw.rectangle((x0 + 85, y0 + 10, x0 + 140, y0 + 36), outline="#a2b1bf", width=2)
        draw.line((x0, y0 + 45, x0 + 150, y0 + 45), fill="#a2b1bf", width=2)
    draw.rectangle((510, 275, 725, 320), fill="#ddd5c8", outline="#938a7b", width=2)
    for x in (530, 610, 685):
        draw.ellipse((x, 285, x + 25, 310), outline="#968777", width=2)
    draw.rounded_rectangle(
        (802, 550, 960, 630), radius=18, fill="#f7fcfc", outline="#8ea3a1", width=2
    )
    draw.ellipse((976, 658, 1015, 695), fill="#f7fcfc", outline="#8ea3a1", width=2)
    draw.text((515, 620), "Room 101", font=font, fill="#627387")
    draw.text((790, 680), "8.0 m2", font=small, fill="#627387")

    definitions = [
        ("x1", "x", (160, 85), (480, 85), "3200 mm"),
        ("x2", "x", (480, 125), (760, 125), "2800 mm"),
        ("x3", "x", (760, 165), (1040, 165), "2800 mm"),
        ("x4", "x", (160, 780), (1040, 780), "8800 mm"),
        ("x5", "x", (380, 835), (780, 835), "12000 mm"),
        ("y1", "y", (1100, 220), (1100, 470), "2500 mm"),
        ("y2", "y", (1160, 470), (1160, 720), "2500 mm"),
        ("y3", "y", (1070, 220), (1070, 720), "5000 mm"),
        ("y4", "y", (125, 500), (125, 700), "2000 mm"),
        ("y5", "y", (125, 220), (125, 440), "6600 mm"),
    ]
    texts: list[DimensionText] = []
    spans: list[DimensionSpan] = []
    for name, axis, first, second, label in definitions:
        p1, p2 = Point(*first), Point(*second)
        spans.append(DimensionSpan(name, p1, p2))
        draw.line((*first, *second), fill="#434e5a", width=2)
        for px, py in (first, second):
            if axis == "x":
                draw.line((px, py - 9, px, py + 9), fill="#434e5a", width=2)
            else:
                draw.line((px - 9, py, px + 9, py), fill="#434e5a", width=2)
        label_box = draw.textbbox((0, 0), label, font=font)
        width, height = label_box[2] - label_box[0], label_box[3] - label_box[1]
        midpoint = ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
        tx = midpoint[0] - width / 2 if axis == "x" else midpoint[0] - width - 12
        if name in ("y1", "y3"):
            tx = midpoint[0] + 12
        ty = midpoint[1] - height - 9 if axis == "x" else midpoint[1] - height / 2
        draw.text((tx, ty - label_box[1]), label, fill="#283b51", font=font)
        texts.append(
            DimensionText(
                name + "-label", label, (tx, ty, tx + width, ty + height), role="dimension"
            )
        )
    texts.extend(
        (
            DimensionText("room-label", "Room 101", (515, 620, 605, 642), role="room"),
            DimensionText("area-label", "8.0 m2", (790, 680, 850, 700), role="area"),
        )
    )
    polygon = (Point(160, 220), Point(480, 220), Point(480, 470), Point(160, 470))
    return DemoCase(np.asarray(image), tuple(texts), tuple(spans), 10.0, 10.0, polygon)
