"""Geometric, globally one-to-one matching of dimension labels to measured spans."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite

import numpy as np
from scipy.optimize import linear_sum_assignment

from .config import MetricConfig
from .domain import Axis, DimensionSpan, DimensionText, Match, Rejection
from .units import DimensionParseError, parse_dimension


def span_axis(span: DimensionSpan, tolerance: float) -> Axis | None:
    dx, dy = abs(span.p2.x - span.p1.x), abs(span.p2.y - span.p1.y)
    if dy <= tolerance * dx:
        return "x"
    if dx <= tolerance * dy:
        return "y"
    return None


class GeometricMatcher:
    """Match all labels together, so one label cannot support several dimension lines."""

    def match(
        self,
        texts: Sequence[DimensionText],
        spans: Sequence[DimensionSpan],
        config: MetricConfig,
    ) -> tuple[tuple[Match, ...], tuple[Rejection, ...]]:
        self._validate_ids(texts, "text")
        self._validate_ids(spans, "span")
        rejected: list[Rejection] = []
        eligible_texts: list[tuple[DimensionText, float]] = []
        for text in sorted(texts, key=lambda observation: observation.id):
            if text.role in ("room", "area"):
                rejected.append(Rejection(text.id, f"excluded_{text.role}_label", "text"))
                continue
            if text.confidence < config.min_ocr_confidence:
                rejected.append(Rejection(text.id, "ocr_confidence_below_limit", "text"))
                continue
            try:
                millimeters = parse_dimension(
                    text.text,
                    default_unit=config.default_unit,
                    allow_unitless=text.role == "dimension",
                )
            except DimensionParseError as exc:
                rejected.append(Rejection(text.id, str(exc), "text"))
                continue
            eligible_texts.append((text, millimeters))
        eligible_spans: list[tuple[DimensionSpan, Axis]] = []
        for span in sorted(spans, key=lambda observation: observation.id):
            axis = span_axis(span, config.orthogonal_tolerance)
            if axis is None:
                rejected.append(Rejection(span.id, "non_orthogonal_span", "span"))
            else:
                eligible_spans.append((span, axis))

        matches: list[Match] = []
        # One dummy column per label makes rejection possible even when all spans exist.
        matrix = np.full((len(eligible_texts), len(eligible_spans) + len(eligible_texts)), 1.01)
        for row, (text, _) in enumerate(eligible_texts):
            for column, (span, axis) in enumerate(eligible_spans):
                matrix[row, column] = self._cost(text, span, axis, config)
        used_texts: set[str] = set()
        used_spans: set[str] = set()
        if eligible_texts:
            rows, columns = linear_sum_assignment(matrix)
            for row, column in zip(rows, columns, strict=True):
                if column >= len(eligible_spans) or matrix[row, column] > 1:
                    continue
                text, millimeters = eligible_texts[row]
                span, axis = eligible_spans[column]
                ratio = millimeters / span.pixel_length
                if not isfinite(ratio) or ratio <= 0:
                    rejected.append(Rejection(text.id, "scale_ratio_outside_numeric_range", "text"))
                    continue
                matches.append(
                    Match(
                        text.id,
                        span.id,
                        axis,
                        span.pixel_length,
                        millimeters,
                        float(matrix[row, column]),
                        text.source_id or text.id,
                        span.source_id or span.id,
                        span.p1,
                        span.p2,
                    )
                )
                used_texts.add(text.id)
                used_spans.add(span.id)
        rejected.extend(
            Rejection(text.id, "no_available_geometric_match", "text")
            for text, _ in eligible_texts
            if text.id not in used_texts
        )
        rejected.extend(
            Rejection(span.id, "no_matching_dimension_text", "span")
            for span, _ in eligible_spans
            if span.id not in used_spans
        )
        return tuple(matches), tuple(rejected)

    @staticmethod
    def _cost(text: DimensionText, span: DimensionSpan, axis: Axis, config: MetricConfig) -> float:
        center, midpoint = text.center, span.midpoint
        x0, y0, x1, y1 = text.box
        if axis == "x":
            perpendicular = max(y0 - midpoint.y, midpoint.y - y1, 0)
            along = abs(center.x - midpoint.x) / span.pixel_length
        else:
            perpendicular = max(x0 - midpoint.x, midpoint.x - x1, 0)
            along = abs(center.y - midpoint.y) / span.pixel_length
        if perpendicular > config.max_text_distance or along > config.max_midpoint_offset:
            return 1e6
        return (
            0.45 * perpendicular / config.max_text_distance
            + 0.45 * along / config.max_midpoint_offset
            + 0.1 * (1 - text.confidence)
        )

    @staticmethod
    def _validate_ids(observations: Sequence, kind: str) -> None:
        ids = [observation.id for observation in observations]
        if len(set(ids)) != len(ids):
            raise ValueError(f"Duplicate {kind} observation id")
