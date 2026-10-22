"""Apply calibration to original-grid WallGraph and PlanRegions exports."""

from __future__ import annotations

import math

from .domain import CalibrationResult

COORDINATES = {"origin": "top_left", "x": "right", "y": "down", "unit": "px"}


def measure_geometry(
    calibration: CalibrationResult, geometry: dict, *, image_size: tuple[int, int]
) -> dict:
    """Measure supplied paths or exact instance pixel areas, retaining calibration evidence."""
    if (
        len(image_size) != 2
        or any(type(value) is not int or value <= 0 for value in image_size)
        or not isinstance(geometry, dict)
        or geometry.get("image") != {"width": image_size[0], "height": image_size[1]}
        or geometry.get("coordinates") != COORDINATES
    ):
        raise ValueError(
            "geometry must match the declared original image size and pixel coordinates"
        )
    schema = geometry.get("schema_version")
    if schema not in {"wallgraph/1", "planregions/1"}:
        raise ValueError("geometry must be wallgraph/1 or planregions/1")
    key = "segments" if schema == "wallgraph/1" else "regions"
    items = geometry.get(key)
    if not isinstance(items, list):
        raise ValueError(f"geometry requires a {key} array")
    measured, seen = [], set()
    for item in items:
        if not isinstance(item, dict) or type(item.get("id")) is not int or item["id"] in seen:
            raise ValueError("geometry needs distinct integer IDs")
        seen.add(item["id"])
        if key == "segments":
            points = item.get("points")
            if not isinstance(points, list) or len(points) < 2:
                raise ValueError("wall paths need at least two points")
            parsed = []
            for point in points:
                if not isinstance(point, dict):
                    raise ValueError("path points must be x/y objects")
                values = (point.get("x"), point.get("y"))
                if any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or not 0 <= value < image_size[index]
                    for index, value in enumerate(values)
                ):
                    raise ValueError("path points must be finite and inside the original image")
                parsed.append(values)
            length = math.fsum(
                calibration.convert_length(second[0] - first[0], second[1] - first[1])
                for first, second in zip(parsed, parsed[1:], strict=False)
            )
            if not math.isfinite(length):
                raise ValueError("measured path length exceeds finite numeric range")
            measured.append({"id": item["id"], "length_mm": length})
        else:
            area = item.get("area_px")
            if type(area) is not int or not 0 < area <= image_size[0] * image_size[1]:
                raise ValueError("region area_px must be a positive integer within the image area")
            measured.append(
                {"id": item["id"], "area_px": area, "area_mm2": calibration.convert_area(area)}
            )
    if key == "regions" and sum(item["area_px"] for item in measured) > math.prod(image_size):
        raise ValueError("disjoint region areas exceed the image area")
    return {
        "schema_version": "planmetric-measurements/1",
        "source_schema": schema,
        "image": geometry["image"],
        "calibration": calibration.to_dict(),
        "measurements": measured,
        "basis": "polyline_segment_lengths"
        if key == "segments"
        else "declared_instance_pixel_areas",
        "meaning": "calibrated supplied geometry; not independently verified physical measurements",
    }
