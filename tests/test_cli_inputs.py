import json

import pytest
from PIL import Image

from planmetric.cli import main
from planmetric.demo import create_demo_case
from planmetric.io import observations_to_dict


@pytest.mark.parametrize("name", ["calibration.json", "evidence.svg"])
@pytest.mark.parametrize("alias", ["path", "hardlink", "symlink"])
def test_calibrate_keeps_source_observations_before_any_output(tmp_path, capsys, name, alias):
    output = tmp_path / "result"
    output.mkdir()
    source = output / name if alias == "path" else tmp_path / "observations.json"
    case = create_demo_case()
    source.write_text(json.dumps(observations_to_dict(case.texts, case.spans)))
    target = output / name
    if alias == "hardlink":
        target.hardlink_to(source)
    elif alias == "symlink":
        target.symlink_to(source)
    original = source.read_bytes()
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert main(["calibrate", "--observations", str(source), "--output", str(output)]) == 2
    assert source.read_bytes() == original
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
    assert "choose a different --output directory" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["calibration.json", "evidence.svg"])
def test_detect_rejects_source_collision_before_starting_ocr(tmp_path, capsys, name):
    source = tmp_path / name
    Image.new("RGB", (32, 32), "white").save(source, format="PNG")
    original = source.read_bytes()
    assert (
        main(
            [
                "detect",
                "--image",
                str(source),
                "--output",
                str(tmp_path),
                "--tesseract",
                "unavailable-ocr-engine",
            ]
        )
        == 2
    )
    assert source.read_bytes() == original
    assert {p.name for p in tmp_path.iterdir()} == {name}
    assert "choose a different --output directory" in capsys.readouterr().err
