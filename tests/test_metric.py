from __future__ import annotations

import json
from dataclasses import replace

import cv2
import pytest

from planmetric import (
    DimensionParseError,
    DimensionSpan,
    DimensionText,
    MetricConfig,
    Point,
    calibrate,
    parse_dimension,
)
from planmetric.adapters import AdapterError, OrthogonalTickDetector, TesseractOCR
from planmetric.cli import main
from planmetric.demo import create_demo_case
from planmetric.io import observations_to_dict, render_svg, write_json
from planmetric.matching import GeometricMatcher


@pytest.mark.parametrize(
    ("label", "millimeters"),
    [
        ("3200 mm", 3200),
        ("32 cm", 320),
        ("3.2 m", 3200),
        ("３２００ 毫米", 3200),
        ("25厘米", 250),
        ("3米", 3000),
        ("10' 6\"", 3200.4),
        ("10 ft - 6 in", 3200.4),
        ("6 inches", 152.4),
        ("3′ 2″", 965.2),
        ("2500 mm.", 2500),
    ],
)
def test_complete_dimension_labels(label, millimeters):
    assert parse_dimension(label) == pytest.approx(millimeters)


@pytest.mark.parametrize(
    "label", ["Room 101", "8m²", "12 m2", "0 mm", "-3 m", "10' 15\"", "3O00 mm"]
)
def test_room_area_and_invalid_lengths_are_not_dimensions(label):
    with pytest.raises(DimensionParseError):
        parse_dimension(label, default_unit="mm", allow_unitless=True)


def test_bare_numbers_require_role_and_default_unit():
    with pytest.raises(DimensionParseError, match="dimension_role"):
        parse_dimension("3200", default_unit="mm")
    with pytest.raises(DimensionParseError, match="default_unit"):
        parse_dimension("3200", allow_unitless=True)
    assert parse_dimension("320", default_unit="cm", allow_unitless=True) == 3200
    span = DimensionSpan("span", Point(0, 30), Point(320, 30))
    text = DimensionText("room-id", "3200", (140, 5, 180, 25))
    result = calibrate([text], [span], MetricConfig(default_unit="mm"))
    assert not result.matches
    assert result.rejected[0].reason == "unitless_text_requires_dimension_role"


def test_demo_rejects_planted_errors_and_converts_real_dimensions():
    case = create_demo_case()
    result = calibrate(case.texts, case.spans)
    assert result.scale_x == result.scale_y == 10
    assert result.anisotropic is False
    assert [(axis.support, axis.total) for axis in result.axes] == [(4, 5), (4, 5)]
    assert sum(item.reason == "scale_outlier" for item in result.rejected) == 2
    assert result.convert_length(320, 0) == 3200
    assert result.convert_area(320 * 250) == 8_000_000
    # Repeatability is required for reports and SVG artifacts, without modifying observations.
    assert result.to_dict() == calibrate(case.texts, case.spans).to_dict()
    assert case.texts[0].text == "3200 mm"


def test_assignment_is_global_and_never_reuses_a_dimension_line():
    texts = [
        DimensionText("a", "1000 mm", (40, 6, 60, 8)),
        DimensionText("b", "1000 mm", (40, -20, 60, -16)),
    ]
    spans = [
        DimensionSpan("a", Point(0, 0), Point(100, 0)),
        DimensionSpan("b", Point(0, 10), Point(100, 10)),
    ]
    matches, _ = GeometricMatcher().match(texts, spans, MetricConfig(max_text_distance=20))
    assert {(match.text_id, match.span_id) for match in matches} == {("a", "b"), ("b", "a")}
    single_matches, _ = GeometricMatcher().match(
        texts, spans[:1], MetricConfig(max_text_distance=20)
    )
    assert len(single_matches) == 1


def test_empty_and_one_axis_cases_do_not_guess_missing_scales():
    empty = calibrate([], [])
    assert empty.scale_x is empty.scale_y is empty.anisotropic is None
    assert all(axis.status == "insufficient" for axis in empty.axes)
    case = create_demo_case()
    horizontal = calibrate(case.texts, [span for span in case.spans if span.id.startswith("x")])
    assert horizontal.scale_x == 10
    assert horizontal.scale_y is None
    assert horizontal.convert_length(100, 0) == 1000
    with pytest.raises(ValueError, match="y-axis"):
        horizontal.convert_length(0, 100)
    with pytest.raises(ValueError, match="y-axis"):
        horizontal.convert_area(100)


def test_same_ocr_source_or_same_physical_span_does_not_inflate_support():
    case = create_demo_case()
    texts = [replace(text, source_id="one-ocr-observation") for text in case.texts]
    result = calibrate(texts, case.spans)
    assert all(axis.status == "insufficient" and axis.total == 1 for axis in result.axes)
    assert any(item.reason == "duplicate_evidence_source_or_span" for item in result.rejected)
    spans = [DimensionSpan(str(index), Point(0, 30), Point(100, 30)) for index in range(4)]
    texts = [DimensionText(str(index), "1000 mm", (40, 10, 60, 20)) for index in range(4)]
    result = calibrate(texts, spans)
    assert result.axis("x").total == 1
    assert result.scale_x is None


def test_competing_equal_consensuses_report_conflict():
    texts, spans = [], []
    for index, length in enumerate((1000, 1000, 1000, 2000, 2000, 2000)):
        y = index * 100 + 30
        texts.append(DimensionText(str(index), f"{length} mm", (40, y - 20, 60, y - 10)))
        spans.append(DimensionSpan(str(index), Point(0, y), Point(100, y)))
    result = calibrate(texts, spans)
    assert result.axis("x").status == "conflict"
    assert result.axis("x").support == 3
    assert result.scale_x is None


def test_anisotropic_image_has_separate_axis_scales():
    case = create_demo_case()
    texts = [
        replace(text, box=(text.box[0] / 2, text.box[1], text.box[2] / 2, text.box[3]))
        for text in case.texts
    ]
    spans = [
        replace(span, p1=Point(span.p1.x / 2, span.p1.y), p2=Point(span.p2.x / 2, span.p2.y))
        for span in case.spans
    ]
    result = calibrate(texts, spans)
    assert (result.scale_x, result.scale_y) == (20, 10)
    assert result.anisotropic is True
    assert result.convert_area(160 * 250) == 8_000_000


def test_diagonal_spans_and_duplicate_ids_are_rejected():
    span = DimensionSpan("diagonal", Point(0, 0), Point(100, 100))
    result = calibrate([DimensionText("text", "1000 mm", (45, 20, 65, 40))], [span])
    assert not result.matches
    assert any(item.reason == "non_orthogonal_span" for item in result.rejected)
    with pytest.raises(ValueError, match="Duplicate span"):
        calibrate([], [span, span])


def test_extreme_values_never_export_nan_or_infinite_scale():
    with pytest.raises(ValueError):
        DimensionSpan("overflow", Point(-1e308, 0), Point(1e308, 0))
    texts, spans = [], []
    # Squared pixel lengths overflow a naive normal-equation calculation.
    for index in range(3):
        y = index * 100
        texts.append(
            DimensionText(str(index), "1" + "0" * 201 + " mm", (4e199, y + 1, 6e199, y + 2))
        )
        spans.append(DimensionSpan(str(index), Point(0, y), Point(1e200, y)))
    result = calibrate(texts, spans)
    assert result.scale_x == pytest.approx(10)
    json.dumps(result.to_dict(), allow_nan=False)
    with pytest.raises(ValueError, match="numeric range"):
        result.convert_length(1e308, 0)
    normal = calibrate(create_demo_case().texts, create_demo_case().spans)
    with pytest.raises(ValueError, match="numeric range"):
        normal.convert_area(1e308)
    with pytest.raises(ValueError):
        normal.convert_area(-1)


def test_orthogonal_marked_line_detector_avoids_furniture_rectangles():
    case = create_demo_case()
    detected = OrthogonalTickDetector().detect_array(cv2.cvtColor(case.image, cv2.COLOR_RGB2GRAY))
    assert len(detected) == 10
    result = calibrate(case.texts, detected)
    assert (result.scale_x, result.scale_y) == (10, 10)
    assert [(axis.support, axis.total) for axis in result.axes] == [(4, 5), (4, 5)]


def test_tesseract_tsv_joins_units_and_retains_room_prefix():
    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    rows = [
        "5\t1\t1\t1\t1\t10\t10\t40\t20\t90\t3200",
        "5\t1\t1\t1\t1\t58\t10\t25\t20\t80\tmm",
        "5\t1\t2\t1\t1\t10\t60\t50\t20\t95\tRoom",
        "5\t1\t2\t1\t1\t66\t60\t30\t20\t93\t101",
    ]
    texts = TesseractOCR.parse_tsv(header + "\n".join(rows))
    assert [text.text for text in texts] == ["3200 mm", "Room 101"]
    assert all(text.role == "unknown" for text in texts)
    assert texts[0].confidence == 0.8


def test_unavailable_ocr_is_explicit_and_never_downloads(tmp_path):
    with pytest.raises(AdapterError, match="unavailable"):
        TesseractOCR(executable="planmetric-nonexistent-ocr-engine").recognize(
            tmp_path / "image.png"
        )


def test_cli_demo_and_observation_calibration_roundtrip(tmp_path, capsys):
    assert main(["demo", "--output", str(tmp_path / "demo"), "--save-image"]) == 0
    first = json.loads((tmp_path / "demo" / "calibration.json").read_text())
    assert (tmp_path / "demo" / "evidence.svg").is_file()
    assert (tmp_path / "demo" / "generated.png").is_file()
    assert (
        main(
            [
                "calibrate",
                "--observations",
                str(tmp_path / "demo" / "observations.json"),
                "--output",
                str(tmp_path / "roundtrip"),
            ]
        )
        == 0
    )
    assert json.loads((tmp_path / "roundtrip" / "calibration.json").read_text()) == first
    assert first["schema_version"] == "1.0"
    assert json.loads(capsys.readouterr().out.splitlines()[0])["axes"]["x"]["support"] == 4


def test_cli_reports_unavailable_ocr_and_svg_escapes_external_ids(tmp_path, capsys):
    from PIL import Image

    image_path = tmp_path / "input.png"
    Image.new("RGB", (80, 80), "white").save(image_path)
    assert (
        main(
            [
                "detect",
                "--image",
                str(image_path),
                "--tesseract",
                "nonexistent-planmetric-ocr",
                "--output",
                str(tmp_path / "result"),
            ]
        )
        == 2
    )
    assert "unavailable" in capsys.readouterr().err
    case = create_demo_case()
    spans = tuple(replace(span, id="<script>" + span.id) for span in case.spans)
    svg = render_svg(calibrate(case.texts, spans))
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


def test_cli_invalid_schema_produces_no_calibration_artifact(tmp_path):
    observations = tmp_path / "input.json"
    write_json({"schema_version": "2.0", "texts": [], "spans": []}, observations)
    assert (
        main(
            ["calibrate", "--observations", str(observations), "--output", str(tmp_path / "output")]
        )
        == 2
    )
    assert not (tmp_path / "output" / "calibration.json").exists()
    assert observations_to_dict((), ())["schema_version"] == "1.0"


def test_observation_bbox_copies_mutable_input_and_cli_rejects_nonobject(tmp_path, capsys):
    mutable_box = [0, 0, 30, 20]
    text = DimensionText("label", "1000 mm", mutable_box)
    mutable_box[2] = 200
    assert text.box == (0, 0, 30, 20)
    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")
    assert (
        main(["calibrate", "--observations", str(invalid), "--output", str(tmp_path / "output")])
        == 2
    )
    assert "must be an object" in capsys.readouterr().err
