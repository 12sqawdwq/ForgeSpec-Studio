from standard_library import (
    catalog_part_from_record,
    catalog_parts_for_prompt,
    fastener_spec_from_prompt,
    find_catalog_records,
    is_primary_fastener_request,
)


def test_primary_fastener_detection():
    assert is_primary_fastener_request("\u751f\u6210\u4e00\u4e2a\u6807\u51c6\u4ef6\u87ba\u4e1d")
    assert not is_primary_fastener_request(
        "\u751f\u6210\u4e00\u4e2a\u516d\u8f74\u673a\u68b0\u81c2\u88c5\u914d\u4f53\uff0c"
        "\u7531\u5e95\u5ea7\u6cd5\u5170\u548c\u82e5\u5e72 M6/M8 \u87ba\u6813\u7ec4\u6210"
    )


def test_fastener_spec_defaults_to_hex_m10():
    spec = fastener_spec_from_prompt("\u751f\u6210\u4e00\u4e2a\u6807\u51c6\u4ef6\u87ba\u4e1d")
    part = spec["parts"][0]
    assert spec["decomposition"]["scope"] == "standard_part"
    assert part["kind"] == "screw"
    assert part["variant"] == "hex_head_bolt"
    assert part["nominal_thread"] == "M10"


def test_catalog_can_find_bearing_and_create_part():
    records = find_catalog_records("bearing 6001", limit=1)
    assert records
    part = catalog_part_from_record(records[0])
    assert part["taxonomy"] == "bearing"
    assert part["geometry_kind"] == "spacer"
    assert part["outer_diameter_mm"] > part["inner_diameter_mm"]


def test_catalog_enriches_robot_prompt_without_replacing_main_object():
    parts = catalog_parts_for_prompt(
        "\u751f\u6210\u4e00\u4e2a\u516d\u8f74\u673a\u68b0\u81c2\u88c5\u914d\u4f53\uff0c\u82e5\u5e72 M6/M8 \u87ba\u6813\u7ec4\u6210",
        ["base flange", "rotary joint", "arm link"],
    )
    taxonomies = {part["taxonomy"] for part in parts}
    categories = {part["category"] for part in parts}
    assert "bearing" in taxonomies
    assert "locating" in taxonomies
    assert {"washer", "nut"}.issubset(categories)
