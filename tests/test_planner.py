from planner import plan_from_prompt


def test_planner_keeps_bolts_as_subparts():
    prompt = (
        "\u751f\u6210\u4e00\u4e2a\u516d\u8f74\u673a\u68b0\u81c2\u88c5\u914d\u4f53\uff0c"
        "\u7531\u5e95\u5ea7\u6cd5\u5170\u3001\u65cb\u8f6c\u5173\u8282\u3001\u4e24\u6bb5\u81c2\u6746\u3001"
        "\u82e5\u5e72 M6/M8 \u87ba\u6813\u7ec4\u6210"
    )
    spec, source = plan_from_prompt(prompt)
    kinds = [part["kind"] for part in spec["parts"]]
    taxonomies = {part.get("taxonomy") for part in spec["parts"]}
    categories = {part.get("category") for part in spec["parts"]}
    assert source.startswith("planner:")
    assert spec["decomposition"]["scope"] in {"robot_description", "multi_part_assembly"}
    assert len(spec["parts"]) > 6
    assert not all(kind == "screw" for kind in kinds)
    assert "screw" in kinds
    assert "bearing" in taxonomies
    assert "locating" in taxonomies
    assert {"washer", "nut"}.issubset(categories)


def test_planner_flange_has_eight_holes_when_requested():
    spec, _ = plan_from_prompt(
        "\u751f\u6210\u4e00\u4e2a\u6cd5\u5170\u76d8\uff0c\u5916\u5f84 120mm\uff0c"
        "\u4e2d\u5fc3\u5b54 35mm\uff0c8 \u4e2a\u87ba\u6813\u5b54"
    )
    part = spec["parts"][0]
    assert part["kind"] == "flange"
    assert part["holes"][0]["count"] == 8


def test_planner_mounting_block_has_four_holes():
    spec, _ = plan_from_prompt("\u751f\u6210\u4e00\u4e2a 100x60x20mm \u5b89\u88c5\u5757\uff0c\u56db\u89d2 M6 \u6c89\u5b54")
    part = spec["parts"][0]
    assert part["kind"] == "block"
    assert part["geometry_kind"] == "block"
    assert part["holes"][0]["count"] == 4


def test_planner_adds_transmission_catalog_parts_for_assembly():
    spec, _ = plan_from_prompt(
        "\u751f\u6210\u4e00\u4e2a\u88c5\u914d\u4f53\uff0c\u5305\u542b\u8f74\u3001"
        "\u8f74\u627f\u5ea7\u3001\u8054\u8f74\u5668\u3001\u5b89\u88c5\u5e95\u677f"
    )
    categories = {part.get("category") for part in spec["parts"]}
    assert len(spec["parts"]) > 1
    assert "coupling" in categories
    assert "parallel_key" in categories
