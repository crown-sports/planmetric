"""Evaluate scale solving on generated OCR/span candidates, not OCR accuracy.

Only aggregate scores are written. No generated fixture or input image is shipped.
Both unchecked baselines reuse PlanMetric's geometric matches so that the measured
difference is scale estimation and abstention, rather than a different OCR system.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from planmetric import DimensionSpan, DimensionText, MetricConfig, Point, calibrate

CONTRACT_SCENARIOS = (
    "clean",
    "axis_stretch",
    "minority_ocr_errors",
    "inconsistent_dimensions",
    "insufficient_support",
    "no_evidence",
    "mixed_units",
    "geometric_distractors",
    "missing_y_axis",
    "rounding_noise",
)
CHALLENGE_SCENARIOS = (
    "systematic_unit_error",
    "wrong_majority",
    "geometric_mismatch",
)
SCENARIOS = CONTRACT_SCENARIOS + CHALLENGE_SCENARIOS


@dataclass(frozen=True)
class GeneratedCase:
    scenario: str
    texts: tuple[DimensionText, ...]
    spans: tuple[DimensionSpan, ...]
    scales: dict[str, float]
    should_accept: dict[str, bool]


def generate_case(seed: int, scenario: str) -> GeneratedCase:
    """Generate geometry and conditional OCR candidates with known scale truth."""
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario}")
    rng = random.Random(seed)
    scales = {"x": rng.uniform(7.0, 15.0), "y": 0.0}
    scales["y"] = scales["x"] * (1.3 if scenario == "axis_stretch" else 1.0)
    should_accept = {"x": True, "y": True}
    texts: list[DimensionText] = []
    spans: list[DimensionSpan] = []
    count = 2 if scenario == "insufficient_support" else 5
    if scenario in ("insufficient_support", "inconsistent_dimensions", "no_evidence"):
        should_accept = {"x": False, "y": False}
    if scenario == "missing_y_axis":
        should_accept["y"] = False
    for axis in ("x", "y"):
        axis_count = count
        if scenario == "no_evidence" or (scenario == "missing_y_axis" and axis == "y"):
            axis_count = 0
        for i in range(axis_count):
            length = rng.uniform(95, 225)
            if axis == "x":
                p1 = Point(90.0, 100.0 + i * 70)
                p2 = Point(p1.x + length, p1.y)
                cx, cy = (p1.x + p2.x) / 2, p1.y - 15
            else:
                p1 = Point(560.0 + i * 100, 130.0)
                p2 = Point(p1.x, p1.y + length)
                cx, cy = p1.x + 20, (p1.y + p2.y) / 2
            label_scale = scales[axis]
            if scenario == "minority_ocr_errors" and i in (0, 4):
                label_scale *= 2.2 if i == 0 else 0.4
            elif scenario == "inconsistent_dimensions":
                label_scale *= (0.5, 0.8, 1.1, 1.6, 2.3)[i]
            elif scenario == "systematic_unit_error":
                label_scale *= 10.0
            elif scenario == "wrong_majority" and i < 3:
                label_scale *= 2.0
            mm = length * label_scale
            if scenario == "geometric_mismatch":
                # The upstream span detector reports the inner half of a dimension
                # while OCR belongs to the full span. Its midpoint still looks right.
                midpoint = Point((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)
                p1 = Point((p1.x + midpoint.x) / 2, (p1.y + midpoint.y) / 2)
                p2 = Point((p2.x + midpoint.x) / 2, (p2.y + midpoint.y) / 2)
            if scenario == "rounding_noise":
                mm *= rng.uniform(0.992, 1.008)
            if scenario == "mixed_units":
                text = (f"{mm / 1000:.3f} m", f"{mm / 10:.2f} cm", f"{mm:.1f} mm")[i % 3]
            else:
                text = str(round(mm))
            span_id, text_id = f"{axis}-span-{i}", f"{axis}-text-{i}"
            spans.append(DimensionSpan(span_id, p1, p2))
            texts.append(
                DimensionText(
                    text_id,
                    text,
                    (cx - 27, cy - 7, cx + 27, cy + 7),
                    role="dimension",
                )
            )
        if scenario == "geometric_distractors":
            # Room labels and distant dimensions must not become scale evidence.
            texts.extend(
                (
                    DimensionText(f"{axis}-room", "Bedroom 2", (20, 600, 150, 620), role="room"),
                    DimensionText(f"{axis}-far", "9999", (1020, 670, 1070, 686), role="dimension"),
                )
            )
    return GeneratedCase(scenario, tuple(texts), tuple(spans), scales, should_accept)


def estimate_baselines(result: object) -> dict[str, dict[str, float | None]]:
    """Shared matching, then median with no consensus or minimum support checks."""
    ratios: dict[str, list[float]] = {"x": [], "y": []}
    for match in result.matches:
        ratios[match.axis].append(match.millimeters / match.pixel_length)
    pooled = ratios["x"] + ratios["y"]
    isotropic = median(pooled) if pooled else None
    return {
        "unchecked_axis_median": {
            axis: median(values) if values else None for axis, values in ratios.items()
        },
        "unchecked_isotropic_median": {"x": isotropic, "y": isotropic},
    }


def evaluate(seed: int = 20261009, repeats: int = 20) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    records: dict[str, list[dict]] = defaultdict(list)
    scenario_counts: Counter[str] = Counter()
    # Bare candidates have a declared dimension role and millimeter units here.
    config = MetricConfig(default_unit="mm")
    for scenario_index, scenario in enumerate(SCENARIOS):
        for repetition in range(repeats):
            case = generate_case(seed + scenario_index * 10000 + repetition, scenario)
            result = calibrate(case.texts, case.spans, config)
            predictions = estimate_baselines(result)
            predictions["planmetric_consensus"] = {
                axis: result.axis(axis).mm_per_pixel
                if result.axis(axis).status == "accepted"
                else None
                for axis in ("x", "y")
            }
            scenario_counts[scenario] += 1
            for method, scales in predictions.items():
                for axis, estimate in scales.items():
                    expected = case.should_accept[axis]
                    accepted = estimate is not None
                    error = abs(estimate / case.scales[axis] - 1) if accepted else None
                    records[method].append(
                        {
                            "scenario": scenario,
                            "expected_accept": expected,
                            "accepted": accepted,
                            "relative_error": error,
                        }
                    )

    def summarize(rows: list[dict]) -> dict:
        supported = [r for r in rows if r["expected_accept"]]
        unsupported = [r for r in rows if not r["expected_accept"]]
        errors = [r["relative_error"] for r in supported if r["accepted"]]
        sorted_errors = sorted(errors)
        return {
            "axis_decisions": len(rows),
            "supported_axes": len(supported),
            "supported_axes_accepted": sum(r["accepted"] for r in supported),
            "supported_axes_within_2_percent": sum(
                r["accepted"] and r["relative_error"] <= 0.02 for r in supported
            ),
            "supported_axes_accepted_with_error_over_2_percent": sum(
                r["accepted"] and r["relative_error"] > 0.02 for r in supported
            ),
            "unsupported_axes": len(unsupported),
            "unsupported_axes_accepted": sum(r["accepted"] for r in unsupported),
            "median_relative_error_on_accepted_supported_axes": median(errors) if errors else None,
            "p95_relative_error_on_accepted_supported_axes": (
                sorted_errors[math.ceil(len(sorted_errors) * 0.95) - 1] if errors else None
            ),
        }

    return {
        "protocol": "generated conditional OCR/span candidates; not image OCR accuracy",
        "seed": seed,
        "cases": sum(scenario_counts.values()),
        "scenarios": dict(scenario_counts),
        "config": {
            "default_unit": config.default_unit,
            "min_support": config.min_support,
            "min_inlier_fraction": config.min_inlier_fraction,
            "max_relative_residual": config.max_relative_residual,
        },
        "baseline_scope": "same geometric matches, different scale estimators; no OCR benchmark",
        "truth_policy": (
            "clean/minority/rounding/unit/stretch axes supported; "
            "inconsistent/<3/missing unsupported"
        ),
        "challenge_policy": (
            "include internally consistent upstream errors without requiring impossible abstention"
        ),
        "challenge_definitions": {
            "systematic_unit_error": (
                "all OCR values on both axes are ten times the real millimeter dimension"
            ),
            "wrong_majority": "three of five OCR values per axis agree on twice the true scale",
            "geometric_mismatch": (
                "reported spans cover half of the true dimension around the same midpoint"
            ),
        },
        "metrics": {method: summarize(rows) for method, rows in records.items()},
        "contract_metrics": {
            method: summarize([r for r in rows if r["scenario"] in CONTRACT_SCENARIOS])
            for method, rows in records.items()
        },
        "challenge_metrics": {
            method: summarize([r for r in rows if r["scenario"] in CHALLENGE_SCENARIOS])
            for method, rows in records.items()
        },
        "by_scenario": {
            method: {
                scenario: summarize([r for r in rows if r["scenario"] == scenario])
                for scenario in SCENARIOS
            }
            for method, rows in records.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261009)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument(
        "--output", type=Path, required=True, help="aggregate local JSON; no fixture export"
    )
    args = parser.parse_args()
    report = evaluate(args.seed, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"cases": report["cases"], "metrics": report["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
