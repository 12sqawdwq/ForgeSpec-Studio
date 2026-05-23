from planner import plan_from_prompt


def test_planner_keeps_bolts_as_subparts():
    prompt = "生成一个六轴机械臂装配体，由底座法兰、旋转关节、两段臂杆、若干 M6/M8 螺栓组成"
    spec, source = plan_from_prompt(prompt)
    kinds = [part["kind"] for part in spec["parts"]]
    assert source.startswith("planner:")
    assert spec["decomposition"]["scope"] in {"robot_description", "multi_part_assembly"}
    assert len(spec["parts"]) > 1
    assert not all(kind == "screw" for kind in kinds)
    assert "screw" in kinds


def test_planner_flange_has_eight_holes_when_requested():
    spec, _ = plan_from_prompt("生成一个法兰盘，外径 120mm，中心孔 35mm，8 个螺栓孔")
    part = spec["parts"][0]
    assert part["kind"] == "flange"
    assert part["holes"][0]["count"] == 8


def test_planner_mounting_block_has_four_holes():
    spec, _ = plan_from_prompt("生成一个 100x60x20mm 安装块，四角 M6 沉孔")
    part = spec["parts"][0]
    assert part["kind"] == "block"
    assert part["geometry_kind"] == "block"
    assert part["holes"][0]["count"] == 4
