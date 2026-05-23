from __future__ import annotations

from standard_library import fastener_spec_from_prompt, looks_like_fastener


def fallback_spec(prompt: str) -> dict:
    text = prompt.lower()
    if looks_like_fastener(prompt):
        return fastener_spec_from_prompt(prompt)

    if "bracket" in text or "支架" in text:
        return {
            "project_name": "precision_mounting_bracket",
            "unit": "mm",
            "description": prompt,
            "parts": [
                {
                    "name": "L_bracket_body",
                    "kind": "bracket",
                    "material": "6061-T6 aluminum, anodized clear",
                    "width_mm": 120,
                    "height_mm": 80,
                    "thickness_mm": 12,
                    "length_mm": 70,
                    "holes": [
                        {
                            "count": 4,
                            "diameter_mm": 6.6,
                            "bolt_circle_diameter_mm": 75,
                            "through": True,
                            "counterbore_diameter_mm": 11,
                            "counterbore_depth_mm": 4,
                            "tolerance": {"plus_mm": 0.03, "minus_mm": 0.03, "note": "H13 clearance for M6 socket head screws"},
                        }
                    ],
                    "chamfers": [{"edge": "all", "size_mm": 1.0, "angle_deg": 45}],
                    "fillets": [{"edge": "all", "radius_mm": 2.0}],
                    "tolerance": {"plus_mm": 0.05, "minus_mm": 0.05, "note": "ISO 2768-m unless specified"},
                    "notes": ["Deburr all edges", "Maintain perpendicularity within 0.05 mm over 100 mm"],
                }
            ],
            "manufacturing_notes": ["Inspect hole position on CMM", "Break sharp edges 0.2-0.5 mm"],
        }

    return {
        "project_name": "precision_flanged_shaft",
        "unit": "mm",
        "description": prompt,
        "parts": [
            {
                "name": "flange",
                "kind": "flange",
                "material": "42CrMo4 steel, quenched and tempered",
                "outer_diameter_mm": 120,
                "inner_diameter_mm": 35,
                "thickness_mm": 16,
                "holes": [
                    {
                        "count": 8,
                        "diameter_mm": 8.5,
                        "bolt_circle_diameter_mm": 96,
                        "through": True,
                        "counterbore_diameter_mm": 14,
                        "counterbore_depth_mm": 5,
                        "tolerance": {"plus_mm": 0.02, "minus_mm": 0.02, "note": "Bolt pattern positional tolerance 0.05 mm"},
                    }
                ],
                "chamfers": [{"edge": "both", "size_mm": 1.0, "angle_deg": 45}, {"edge": "holes", "size_mm": 0.5, "angle_deg": 45}],
                "fillets": [{"edge": "both", "radius_mm": 1.5}],
                "tolerance": {"plus_mm": 0.03, "minus_mm": 0.03, "note": "Critical bore fit H7"},
                "notes": ["Concentricity of bore to outer diameter <= 0.03 mm"],
            },
            {
                "name": "shaft_stub",
                "kind": "shaft",
                "material": "42CrMo4 steel, same billet as flange",
                "outer_diameter_mm": 34.98,
                "length_mm": 70,
                "chamfers": [{"edge": "both", "size_mm": 1.0, "angle_deg": 45}],
                "fillets": [{"edge": "back", "radius_mm": 3.0}],
                "position_mm": [0, 0, 16],
                "tolerance": {"plus_mm": 0.0, "minus_mm": 0.02, "note": "Sliding bearing journal"},
                "notes": ["Surface roughness Ra 0.8 on journal"],
            },
        ],
        "manufacturing_notes": ["Stress relieve before finish machining", "Deburr and clean before packaging"],
    }
