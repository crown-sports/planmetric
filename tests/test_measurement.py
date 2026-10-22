import json
from dataclasses import replace

import pytest

from planmetric.cli import main
from planmetric.demo import create_demo_case
from planmetric.io import observations_to_dict
from planmetric.measurement import COORDINATES, measure_geometry
from planmetric.pipeline import calibrate


def fixture():
    case = create_demo_case()
    result = calibrate(case.texts, case.spans)
    return case, result


def geometry(schema, **items):
    return {
        "schema_version": schema,
        "image": {"width": 1200, "height": 900},
        "coordinates": COORDINATES,
        **items,
    }


def test_anisotropic_paths_and_exact_pixel_areas():
    _, result = fixture()
    result = replace(result, axes=(result.axes[0], replace(result.axes[1], mm_per_pixel=20)))
    walls = geometry(
        "wallgraph/1",
        segments=[{"id": 1, "points": [{"x": 0, "y": 0}, {"x": 3, "y": 4}, {"x": 6, "y": 4}]}],
    )
    report = measure_geometry(result, walls, image_size=(1200, 900))
    assert report["measurements"][0]["length_mm"] == pytest.approx((30**2 + 80**2) ** 0.5 + 30)
    rooms = geometry("planregions/1", regions=[{"id": 2, "area_px": 750}])
    report = measure_geometry(result, rooms, image_size=(1200, 900))
    assert report["measurements"][0]["area_mm2"] == 150000
    assert report["calibration"]["axes"]["y"]["support"] == result.axis("y").support


def test_missing_scale_wrong_grid_and_bad_paths_fail():
    _, result = fixture()
    rooms = geometry("planregions/1", regions=[{"id": 1, "area_px": 100}])
    with pytest.raises(ValueError, match="image size"):
        measure_geometry(result, rooms, image_size=(100, 100))
    incomplete = replace(result, axes=(result.axes[0], replace(result.axes[1], status="conflict")))
    with pytest.raises(ValueError, match="accepted y-axis"):
        measure_geometry(incomplete, rooms, image_size=(1200, 900))
    rooms["regions"].append({"id": 1, "area_px": 20})
    with pytest.raises(ValueError, match="distinct"):
        measure_geometry(result, rooms, image_size=(1200, 900))
    for value in (True, float("nan"), 1200, -1):
        walls = geometry(
            "wallgraph/1", segments=[{"id": 1, "points": [{"x": 0, "y": 0}, {"x": value, "y": 2}]}]
        )
        with pytest.raises(ValueError):
            measure_geometry(result, walls, image_size=(1200, 900))


def test_cli_evidence_measurements_and_invalid_exit(tmp_path):
    case, _ = fixture()
    observations = tmp_path / "observations.json"
    observations.write_text(
        json.dumps(observations_to_dict(case.texts, case.spans, image_size=(1200, 900)))
    )
    source = tmp_path / "regions.json"
    source.write_text(json.dumps(geometry("planregions/1", regions=[{"id": 1, "area_px": 80000}])))
    output = tmp_path / "measurements.json"
    args = [
        "measure",
        "--observations",
        str(observations),
        "--geometry",
        str(source),
        "--output",
        str(output),
    ]
    assert main(args) == 0
    report = json.loads(output.read_text())
    assert report["measurements"][0]["area_mm2"] == 8000000
    assert len(report["provenance"]["geometry_sha256"]) == 64
    original = source.read_text()
    assert main(args[:-1] + [str(source)]) == 2
    assert source.read_text() == original
    source.write_text("{}")
    assert main(args) == 2


def test_native_dataclass_export_tuples_are_accepted_without_json_roundtrip():
    _, result = fixture()
    # WallResult.to_dict uses asdict for segments, preserving the tuple of points.
    walls = geometry(
        "wallgraph/1",
        segments=[
            {
                "id": 0,
                "points": ({"x": 10.0, "y": 10.0}, {"x": 13.0, "y": 14.0}, {"x": 10.0, "y": 10.0}),
            }
        ],
    )
    report = measure_geometry(result, walls, image_size=(1200, 900))
    assert report["measurements"] == [{"id": 0, "length_mm": 100.0}]
