from standard_library import fastener_spec_from_prompt, is_primary_fastener_request


def test_primary_fastener_detection():
    assert is_primary_fastener_request("生成一个标准件螺丝")
    assert not is_primary_fastener_request("生成一个六轴机械臂装配体，由底座法兰和若干 M6/M8 螺栓组成")


def test_fastener_spec_defaults_to_hex_m10():
    spec = fastener_spec_from_prompt("生成一个标准件螺丝")
    part = spec["parts"][0]
    assert spec["decomposition"]["scope"] == "standard_part"
    assert part["kind"] == "screw"
    assert part["variant"] == "hex_head_bolt"
    assert part["nominal_thread"] == "M10"
