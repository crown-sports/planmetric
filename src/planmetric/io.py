"""Versioned JSON observations and standalone SVG evidence overlays."""

from __future__ import annotations

import json
from html import escape
from math import isfinite
from pathlib import Path

from .config import MetricConfig
from .domain import CalibrationResult, DimensionSpan, DimensionText, Point


def read_observations(
    path: Path,
) -> tuple[
    tuple[DimensionText, ...], tuple[DimensionSpan, ...], MetricConfig, tuple[int, int] | None
]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Observations JSON must be an object")
    if payload.get("schema_version") != "1.0":
        raise ValueError("Observations must declare schema_version 1.0")
    texts = tuple(
        DimensionText(
            id=item["id"],
            text=item["text"],
            box=tuple(item["box"]),
            confidence=item.get("confidence", 1.0),
            role=item.get("role", "unknown"),
            source_id=item.get("source_id"),
        )
        for item in payload["texts"]
    )
    spans = tuple(
        DimensionSpan(
            id=item["id"],
            p1=Point(**item["p1"]),
            p2=Point(**item["p2"]),
            source_id=item.get("source_id"),
        )
        for item in payload["spans"]
    )
    settings = MetricConfig(**payload.get("config", {}))
    size = payload.get("image_size")
    if size is not None:
        if len(size) != 2 or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in size
        ):
            raise ValueError("image_size must contain positive integer width and height")
        size = tuple(size)
    return texts, spans, settings, size


def observations_to_dict(
    texts: tuple[DimensionText, ...],
    spans: tuple[DimensionSpan, ...],
    *,
    image_size: tuple[int, int] | None = None,
) -> dict:
    from dataclasses import asdict

    result = {
        "schema_version": "1.0",
        "texts": [asdict(text) for text in texts],
        "spans": [asdict(span) for span in spans],
    }
    if image_size is not None:
        result["image_size"] = image_size
    return result


def write_json(payload: dict, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )


def write_result(
    result: CalibrationResult, directory: Path, *, image_size: tuple[int, int] | None = None
) -> tuple[Path, Path]:
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    json_path, svg_path = output / "calibration.json", output / "evidence.svg"
    write_json(result.to_dict(), json_path)
    svg_path.write_text(render_svg(result, image_size=image_size), encoding="utf-8")
    return json_path, svg_path


def render_svg(result: CalibrationResult, *, image_size: tuple[int, int] | None = None) -> str:
    if image_size:
        width, height = image_size
        if not all(isfinite(value) and value > 0 for value in image_size):
            raise ValueError("SVG image size must be positive and finite")
        viewbox = f"0 0 {width} {height}"
    else:
        points = [point for match in result.matches for point in (match.p1, match.p2)]
        minimum_x = min((point.x for point in points), default=0) - 30
        minimum_y = min((point.y for point in points), default=0) - 30
        width = max((point.x for point in points), default=610) - minimum_x + 30
        height = max((point.y for point in points), default=450) - minimum_y + 30
        if not isfinite(width) or not isfinite(height):
            raise ValueError("SVG coordinates exceed finite numeric range")
        viewbox = f"{minimum_x:g} {minimum_y:g} {width:g} {height:g}"
    evidence = {
        (item.text_id, item.span_id): (axis.status, item)
        for axis in result.axes
        for item in axis.evidence
    }
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
        f'viewBox="{viewbox}">',
        "<title>Dimension evidence in original pixel coordinates</title>",
    ]
    for match in result.matches:
        status, item = evidence[match.text_id, match.span_id]
        color = "#15805f" if status == "accepted" and item.inlier else "#cb4438"
        if status == "insufficient":
            color = "#7b8795"
        caption = escape(
            f"{match.span_id}: {match.millimeters:g} mm; {status}; {item.reason or 'inlier'}"
        )
        lines.append(
            f'<g><title>{caption}</title><line x1="{match.p1.x:g}" y1="{match.p1.y:g}" '
            f'x2="{match.p2.x:g}" y2="{match.p2.y:g}" stroke="{color}" '
            'stroke-width="4"/>'
        )
        for point in (match.p1, match.p2):
            lines.append(f'<circle cx="{point.x:g}" cy="{point.y:g}" r="4" fill="{color}"/>')
        lines.append("</g>")
    lines.append("</svg>\n")
    return "\n".join(lines)
