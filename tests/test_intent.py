from brief import build_brief
from intent import classify_intent


def test_standard_screw_is_standard_part():
    intent = classify_intent(build_brief("生成一个标准件螺丝"))
    assert intent.scope == "standard_part"
    assert intent.generator_family == "fastener"


def test_assembly_with_bolts_keeps_assembly_scope():
    prompt = "生成一个六轴机械臂装配体，由底座法兰、旋转关节、两段臂杆、若干 M6/M8 螺栓组成"
    intent = classify_intent(build_brief(prompt))
    assert intent.scope in {"robot_description", "multi_part_assembly"}
    assert intent.generator_family in {"robot_arm_concept", "generic_assembly"}


def test_mounting_block_is_single_part():
    intent = classify_intent(build_brief("生成一个 100x60x20mm 安装块，四角 M6 沉孔"))
    assert intent.scope == "single_part"
    assert intent.generator_family == "plate_block"
