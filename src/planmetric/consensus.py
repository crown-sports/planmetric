"""Deterministic one-parameter RANSAC, with explicit independent evidence accounting."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite

import numpy as np

from .config import MetricConfig
from .domain import Axis, AxisCalibration, Evidence, Match


class ConsensusEstimator:
    """Estimate each axis separately and return a diagnostic instead of an invented scale."""

    def estimate(
        self, axis: Axis, matches: Sequence[Match], config: MetricConfig
    ) -> AxisCalibration:
        relevant = [match for match in matches if match.axis == axis]
        independent, duplicate = self._independent(relevant)
        total = len(independent)
        if total < config.min_support:
            return self._result(
                axis,
                "insufficient",
                None,
                0,
                independent,
                duplicate,
                None,
                set(),
                "not_enough_independent_dimensions",
            )
        pixels = np.asarray([match.pixel_length for match in independent], dtype=np.float64)
        millimeters = np.asarray([match.millimeters for match in independent], dtype=np.float64)
        ratios = millimeters / pixels
        candidates: list[tuple[int, float, float, np.ndarray]] = []
        for proposed in sorted(set(ratios)):
            scale = float(proposed)
            inliers = self._residuals(scale, ratios) <= config.max_relative_residual
            for _ in range(2):
                weights = (pixels[inliers] / pixels[inliers].max()) ** 2
                largest_ratio = ratios[inliers].max()
                normalized = float(np.dot(weights, ratios[inliers] / largest_ratio) / weights.sum())
                scale = float(largest_ratio * min(normalized, 1.0))
                refined = self._residuals(scale, ratios) <= config.max_relative_residual
                if np.array_equal(refined, inliers):
                    break
                inliers = refined
                if not np.any(inliers):
                    break
            residuals = self._residuals(scale, ratios)
            candidates.append((int(inliers.sum()), float(residuals[inliers].sum()), scale, inliers))
        candidates.sort(key=lambda candidate: (-candidate[0], candidate[1], candidate[2]))
        support, _, scale, inliers = candidates[0]
        accepted = support >= config.min_support and support / total >= config.min_inlier_fraction
        if not accepted:
            return self._result(
                axis,
                "conflict",
                None,
                support,
                independent,
                duplicate,
                scale,
                set(np.flatnonzero(inliers)),
                "no_dominant_consensus",
            )
        return self._result(
            axis,
            "accepted",
            scale,
            support,
            independent,
            duplicate,
            scale,
            set(np.flatnonzero(inliers)),
            None,
        )

    @staticmethod
    def _residuals(scale: float, ratios: np.ndarray) -> np.ndarray:
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            return np.abs(scale / ratios - 1)

    @staticmethod
    def _independent(matches: Sequence[Match]) -> tuple[list[Match], list[Match]]:
        used_text: set[str] = set()
        used_span: set[str] = set()
        used_geometry: set[tuple] = set()
        independent: list[Match] = []
        duplicate: list[Match] = []
        for match in sorted(matches, key=lambda match: (match.cost, match.text_id, match.span_id)):
            endpoints = sorted(
                [
                    (round(match.p1.x, 3), round(match.p1.y, 3)),
                    (round(match.p2.x, 3), round(match.p2.y, 3)),
                ]
            )
            geometry = tuple(endpoints)
            if (
                match.text_source in used_text
                or match.span_source in used_span
                or geometry in used_geometry
            ):
                duplicate.append(match)
                continue
            independent.append(match)
            used_text.add(match.text_source)
            used_span.add(match.span_source)
            used_geometry.add(geometry)
        return independent, duplicate

    @staticmethod
    def _result(
        axis: Axis,
        status: str,
        scale: float | None,
        support: int,
        independent: list[Match],
        duplicates: list[Match],
        diagnostic_scale: float | None,
        inliers: set[int],
        reason: str | None,
    ) -> AxisCalibration:
        evidence = [
            Evidence(
                match.text_id,
                match.span_id,
                match.ratio,
                ConsensusEstimator._reported_residual(diagnostic_scale, match.ratio),
                index in inliers,
                None if index in inliers else reason or "scale_outlier",
            )
            for index, match in enumerate(independent)
        ]
        evidence.extend(
            Evidence(
                match.text_id,
                match.span_id,
                match.ratio,
                None,
                False,
                "duplicate_evidence_source_or_span",
            )
            for match in duplicates
        )
        return AxisCalibration(
            axis, status, scale, support, len(independent), tuple(evidence), reason
        )

    @staticmethod
    def _reported_residual(scale: float | None, ratio: float) -> float | None:
        if scale is None:
            return None
        residual = abs(scale / ratio - 1)
        return residual if isfinite(residual) else None
