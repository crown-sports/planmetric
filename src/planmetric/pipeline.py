"""Small orchestrator with replaceable matching, estimation, OCR and line detection."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from .config import MetricConfig
from .consensus import ConsensusEstimator
from .domain import CalibrationResult, DimensionSpan, DimensionText, Rejection
from .matching import GeometricMatcher


class OCRProvider(Protocol):
    def recognize(self, image_path: Path) -> tuple[DimensionText, ...]: ...


class SpanDetector(Protocol):
    def detect(self, image_path: Path) -> tuple[DimensionSpan, ...]: ...


def calibrate(
    texts: Sequence[DimensionText],
    spans: Sequence[DimensionSpan],
    config: MetricConfig | None = None,
    *,
    matcher: GeometricMatcher | None = None,
    estimator: ConsensusEstimator | None = None,
) -> CalibrationResult:
    settings = config or MetricConfig()
    matches, rejected = (matcher or GeometricMatcher()).match(texts, spans, settings)
    estimator = estimator or ConsensusEstimator()
    axes = (estimator.estimate("x", matches, settings), estimator.estimate("y", matches, settings))
    for axis in axes:
        rejected += tuple(
            Rejection(f"{item.text_id}:{item.span_id}", item.reason or "scale_outlier", "match")
            for item in axis.evidence
            if not item.inlier
        )
    sx, sy = axes[0].mm_per_pixel, axes[1].mm_per_pixel
    anisotropic = (
        None
        if sx is None or sy is None
        else abs(sx - sy) / max(sx, sy) > (settings.anisotropic_tolerance)
    )
    return CalibrationResult(axes, matches, rejected, anisotropic)


def inspect_image(
    image_path: Path,
    *,
    ocr: OCRProvider,
    detector: SpanDetector,
    config: MetricConfig | None = None,
) -> CalibrationResult:
    """Run local adapters. Detector candidates are evidence candidates, not ground truth."""
    image_path = Path(image_path)
    if not image_path.is_file():
        raise ValueError(f"Image does not exist: {image_path}")
    return calibrate(ocr.recognize(image_path), detector.detect(image_path), config)
