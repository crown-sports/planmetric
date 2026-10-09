"""Immutable observations and calibration results, in image pixel coordinates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import hypot, isfinite
from typing import Literal

Axis = Literal["x", "y"]
Status = Literal["accepted", "insufficient", "conflict"]


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def __post_init__(self) -> None:
        if not isfinite(self.x) or not isfinite(self.y):
            raise ValueError("Point coordinates must be finite")


@dataclass(frozen=True)
class DimensionText:
    id: str
    text: str
    box: tuple[float, float, float, float]
    confidence: float = 1.0
    role: Literal["dimension", "unknown", "room", "area"] = "unknown"
    source_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip() or not isinstance(self.text, str):
            raise ValueError("Text observations need an id and a string")
        object.__setattr__(self, "box", tuple(self.box))
        x0, y0, x1, y1 = self.box
        if (
            not all(isfinite(v) for v in self.box)
            or x1 <= x0
            or y1 <= y0
            or not isfinite(x1 - x0)
            or not isfinite(y1 - y0)
        ):
            raise ValueError("Text boxes must be finite (x0, y0, x1, y1) with positive size")
        if not isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("OCR confidence must be between 0 and 1")
        if self.role not in ("dimension", "unknown", "room", "area"):
            raise ValueError("Unknown text role")
        if self.source_id is not None and (
            not isinstance(self.source_id, str) or not self.source_id.strip()
        ):
            raise ValueError("source_id must be a nonempty string or None")

    @property
    def center(self) -> Point:
        x0, y0, x1, y1 = self.box
        return Point(x0 / 2 + x1 / 2, y0 / 2 + y1 / 2)


@dataclass(frozen=True)
class DimensionSpan:
    id: str
    p1: Point
    p2: Point
    source_id: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.id, str)
            or not self.id.strip()
            or not isfinite(self.pixel_length)
            or self.pixel_length <= 0
        ):
            raise ValueError("Dimension spans need an id and distinct finite endpoints")
        if self.source_id is not None and (
            not isinstance(self.source_id, str) or not self.source_id.strip()
        ):
            raise ValueError("source_id must be a nonempty string or None")

    @property
    def pixel_length(self) -> float:
        return hypot(self.p2.x - self.p1.x, self.p2.y - self.p1.y)

    @property
    def midpoint(self) -> Point:
        return Point(self.p1.x / 2 + self.p2.x / 2, self.p1.y / 2 + self.p2.y / 2)


@dataclass(frozen=True)
class Match:
    text_id: str
    span_id: str
    axis: Axis
    pixel_length: float
    millimeters: float
    cost: float
    text_source: str
    span_source: str
    p1: Point
    p2: Point

    def __post_init__(self) -> None:
        if (
            not isfinite(self.pixel_length)
            or self.pixel_length <= 0
            or not isfinite(self.millimeters)
            or self.millimeters <= 0
            or not isfinite(self.ratio)
            or self.ratio <= 0
        ):
            raise ValueError("Matched dimensions need positive finite lengths and scale ratios")

    @property
    def ratio(self) -> float:
        return self.millimeters / self.pixel_length


@dataclass(frozen=True)
class Rejection:
    id: str
    reason: str
    kind: Literal["text", "span", "match"]


@dataclass(frozen=True)
class Evidence:
    text_id: str
    span_id: str
    observed_mm_per_pixel: float
    relative_residual: float | None
    inlier: bool
    reason: str | None = None


@dataclass(frozen=True)
class AxisCalibration:
    axis: Axis
    status: Status
    mm_per_pixel: float | None
    support: int
    total: int
    evidence: tuple[Evidence, ...]
    reason: str | None = None


@dataclass(frozen=True)
class CalibrationResult:
    axes: tuple[AxisCalibration, AxisCalibration]
    matches: tuple[Match, ...]
    rejected: tuple[Rejection, ...]
    anisotropic: bool | None
    schema_version: str = "1.0"

    def axis(self, name: Axis) -> AxisCalibration:
        if name not in ("x", "y"):
            raise ValueError("Axis must be x or y")
        return next(axis for axis in self.axes if axis.axis == name)

    @property
    def scale_x(self) -> float | None:
        return self.axis("x").mm_per_pixel

    @property
    def scale_y(self) -> float | None:
        return self.axis("y").mm_per_pixel

    def to_dict(self) -> dict:
        result = asdict(self)
        result["axes"] = {axis.axis: asdict(axis) for axis in self.axes}
        result["units"] = {"coordinates": "pixel", "scale": "millimeter/pixel"}
        return result

    def convert_length(self, dx: float, dy: float) -> float:
        """Convert a pixel displacement to millimeters; require only axes actually used."""
        if not isfinite(dx) or not isfinite(dy):
            raise ValueError("Pixel displacements must be finite")
        sx = self._required_scale("x") if dx else 0.0
        sy = self._required_scale("y") if dy else 0.0
        length = hypot(dx * sx, dy * sy)
        if not isfinite(length) or (length == 0 and (dx != 0 or dy != 0)):
            raise ValueError("Converted length exceeds finite numeric range")
        return length

    def convert_area(self, area_pixels: float) -> float:
        """Convert nonnegative pixel area to square millimeters, requiring both axes."""
        if not isfinite(area_pixels) or area_pixels < 0:
            raise ValueError("Pixel area must be finite and nonnegative")
        area = area_pixels * self._required_scale("x") * self._required_scale("y")
        if not isfinite(area) or (area == 0 and area_pixels != 0):
            raise ValueError("Converted area exceeds finite numeric range")
        return area

    def _required_scale(self, axis: Axis) -> float:
        calibration = self.axis(axis)
        if calibration.status != "accepted" or calibration.mm_per_pixel is None:
            raise ValueError(f"No accepted {axis}-axis scale; cannot convert this measurement")
        return calibration.mm_per_pixel
