"""Explicit limits: calibration never supplies missing units or a missing axis."""

from dataclasses import dataclass
from math import isfinite
from typing import Literal


@dataclass(frozen=True)
class MetricConfig:
    default_unit: Literal["mm", "cm", "m", "in", "ft"] | None = None
    min_support: int = 3
    min_inlier_fraction: float = 0.6
    max_relative_residual: float = 0.025
    anisotropic_tolerance: float = 0.02
    max_text_distance: float = 48.0
    max_midpoint_offset: float = 0.35
    orthogonal_tolerance: float = 0.02
    min_ocr_confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.default_unit not in (None, "mm", "cm", "m", "in", "ft"):
            raise ValueError("default_unit must be mm, cm, m, in, ft or None")
        if (
            not isinstance(self.min_support, int)
            or isinstance(self.min_support, bool)
            or self.min_support < 2
        ):
            raise ValueError("min_support must be an integer of at least two")
        limits = (
            self.min_inlier_fraction,
            self.max_relative_residual,
            self.anisotropic_tolerance,
            self.max_text_distance,
            self.max_midpoint_offset,
            self.orthogonal_tolerance,
            self.min_ocr_confidence,
        )
        if not all(isfinite(value) for value in limits):
            raise ValueError("Configuration limits must be finite")
        if not 0.5 < self.min_inlier_fraction <= 1:
            raise ValueError("min_inlier_fraction must be greater than .5 and at most 1")
        if not 0 < self.max_relative_residual < 0.5:
            raise ValueError("max_relative_residual must be between 0 and .5")
        if not 0 <= self.anisotropic_tolerance < 1:
            raise ValueError("anisotropic_tolerance must be between 0 and 1")
        if self.max_text_distance <= 0 or not 0 < self.max_midpoint_offset <= 0.5:
            raise ValueError("Text distance and midpoint gates must be positive")
        if not 0 <= self.orthogonal_tolerance < 0.25:
            raise ValueError("orthogonal_tolerance must be between 0 and .25")
        if not 0 <= self.min_ocr_confidence <= 1:
            raise ValueError("min_ocr_confidence must be between 0 and 1")
