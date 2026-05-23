import pytest

pytest.importorskip("cadquery")

from cad_engine import build_assembly
from planner import plan_from_prompt
from schemas import AssemblySpec


def test_build_standard_screw_exports_step_stl_json():
    raw, _ = plan_from_prompt("生成一个标准件螺丝")
    spec = AssemblySpec.model_validate(raw)
    stl_path, json_path, summary = build_assembly(spec)
    assert stl_path.exists()
    assert json_path.exists()
    assert "step" in summary
    assert summary["validation"]["ok"]
    assert summary["validation"]["part_count"] == 1
