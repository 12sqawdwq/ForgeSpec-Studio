from schemas import AssemblySpec


def test_schema_accepts_open_engineering_kind_plate():
    spec = AssemblySpec.model_validate(
        {
            "project_name": "plate_test",
            "unit": "mm",
            "description": "plate test",
            "parts": [
                {
                    "name": "mounting_plate",
                    "kind": "plate",
                    "family": "structural",
                    "length_mm": 100,
                    "width_mm": 60,
                    "height_mm": 8,
                }
            ],
        }
    )
    part = spec.parts[0]
    assert part.kind == "plate"
    assert part.geometry_kind == "plate"
    assert part.taxonomy == "structural"
    assert part.type_code == "plate"


def test_schema_maps_unknown_engineering_kind_to_generic_geometry():
    spec = AssemblySpec.model_validate(
        {
            "project_name": "sensor_test",
            "unit": "mm",
            "description": "sensor test",
            "parts": [{"name": "photoelectric_sensor", "kind": "photoelectric_sensor", "family": "electrical_component"}],
        }
    )
    part = spec.parts[0]
    assert part.kind == "photoelectric_sensor"
    assert part.geometry_kind == "generic"
    assert part.taxonomy == "electrical_component"
