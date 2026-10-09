"""Guard the stated scope and failure cases of the generated comparison."""

import runpy
from pathlib import Path


def test_generated_comparison_retains_consistent_wrong_evidence():
    module = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "tools/evaluate_generated.py")
    )
    report = module["evaluate"](seed=20261009, repeats=2)
    contract = report["contract_metrics"]["planmetric_consensus"]
    challenge = report["challenge_metrics"]["planmetric_consensus"]
    baseline = report["contract_metrics"]["unchecked_axis_median"]
    assert report["cases"] == 26
    assert contract["unsupported_axes_accepted"] == 0
    assert baseline["unsupported_axes_accepted"] > contract["unsupported_axes_accepted"]
    assert challenge["supported_axes_accepted_with_error_over_2_percent"] > 0
    assert "not image OCR accuracy" in report["protocol"]


def test_reviewed_figure_and_actual_solver_evidence():
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tools/render_demo.py"))
    module["check_figure"](module["PUBLIC_FIGURE"])
    module["check_solver_demo"]()
