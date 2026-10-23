"""PlanMetric: dimension evidence to millimeters per pixel."""

from .config import MetricConfig
from .domain import (
    AxisCalibration,
    CalibrationResult,
    DimensionSpan,
    DimensionText,
    Evidence,
    Match,
    Point,
    Rejection,
)
from .pipeline import OCRProvider, SpanDetector, calibrate, inspect_image
from .units import DimensionParseError, parse_dimension

__version__ = "0.2.1"
__all__ = [
    "AxisCalibration",
    "CalibrationResult",
    "DimensionParseError",
    "DimensionSpan",
    "DimensionText",
    "Evidence",
    "Match",
    "MetricConfig",
    "OCRProvider",
    "Point",
    "Rejection",
    "SpanDetector",
    "calibrate",
    "inspect_image",
    "parse_dimension",
]
