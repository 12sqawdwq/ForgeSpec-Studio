import py_compile

import pytest

pytest.importorskip("cadquery")

from cad_engine import build_assembly
from pathlib import Path
from planner import plan_from_prompt
from schemas import AssemblySpec


def test_build_standard_screw_exports_step_stl_json_and_python_source():
    raw, _ = plan_from_prompt("\u751f\u6210\u4e00\u4e2a\u6807\u51c6\u4ef6\u87ba\u4e1d")
    spec = AssemblySpec.model_validate(raw)
    stl_path, json_path, summary = build_assembly(spec)
    source_path = Path("outputs") / summary["source"]
    manifest_path = Path("outputs") / summary["manifest"]
    report_path = Path("outputs") / summary["assurance_report"]
    assert stl_path.exists()
    assert json_path.exists()
    assert "step" in summary
    assert source_path.exists()
    assert manifest_path.exists()
    assert report_path.exists()
    py_compile.compile(str(source_path), doraise=True)
    source_text = source_path.read_text(encoding="utf-8")
    assert "import cadquery as cq" in source_text
    assert "def build_model()" in source_text
    assert summary["security"]["ok"]
    assert summary["validation"]["ok"]
    assert summary["validation"]["part_count"] == 1
