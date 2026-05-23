from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


STANDARD_DIR = Path(__file__).with_name("standards")
FASTENER_DB = STANDARD_DIR / "fasteners.json"


def _load_fasteners() -> dict[str, Any]:
    return json.loads(FASTENER_DB.read_text(encoding="utf-8"))


def _find_thread(text: str) -> str:
    match = re.search(r"\bM\s*(3|4|5|6|8|10|12|16)\b", text, re.IGNORECASE)
    if match:
        return f"M{match.group(1)}"
    return "M10"


def _find_length(text: str) -> float:
    compact = text.replace(" ", "")
    patterns = [
        r"M(?:3|4|5|6|8|10|12|16)[x×*](\d+(?:\.\d+)?)",
        r"(?:length|长度|长|杆长|螺杆长度)(?:为|=|:)?(\d+(?:\.\d+)?)\s*mm?",
        r"(\d+(?:\.\d+)?)\s*mm(?:长|长度)?"
    ]
    for pattern in patterns:
        match = re.search(pattern, compact, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if 4 <= value <= 240:
                return value
    return 50.0


def _variant_from_text(text: str) -> str:
    lower = text.lower()
    if "内六角" in text or "socket" in lower or "cap screw" in lower:
        return "socket_head_cap_screw"
    return "hex_head_bolt"


def looks_like_fastener(prompt: str) -> bool:
    lower = prompt.lower()
    keywords = [
        "螺丝",
        "螺钉",
        "螺栓",
        "标准件螺",
        "bolt",
        "screw",
        "fastener",
        "socket head",
        "hex head",
    ]
    return any(keyword in lower for keyword in keywords)


def fastener_spec_from_prompt(prompt: str) -> dict[str, Any]:
    db = _load_fasteners()
    variant = _variant_from_text(prompt)
    thread = _find_thread(prompt)
    length = _find_length(prompt)
    thread_row = db["metric_threads"][thread]
    default = copy.deepcopy(db["defaults"][variant])
    diameter = float(thread_row["diameter_mm"])
    pitch = float(thread_row["pitch_mm"])
    if variant == "socket_head_cap_screw":
        head_diameter = float(thread_row["socket_head_diameter_mm"])
        head_height = float(thread_row["socket_head_height_mm"])
        width = head_diameter
        socket_size = float(thread_row["socket_size_mm"])
    else:
        head_diameter = float(thread_row["hex_af_mm"])
        head_height = float(thread_row["hex_head_height_mm"])
        width = head_diameter
        socket_size = None

    thread_length = length if default["thread_length_mode"] == "full" else min(length, max(2.0 * diameter + 6.0, 0.6 * length))
    name = default["name_template"].format(thread=thread.lower(), length=f"{length:g}")
    notes = [
        f"Standard reference: {default['standard']}.",
        f"Nominal thread {thread} x {pitch:g}, thread length {thread_length:g} mm.",
        f"Head style: {default['head_style']}; drive style: {default['drive_style']}.",
        "Thread is represented as a manufacturable cosmetic ridge model for STL preview/export.",
    ]
    if socket_size:
        notes.append(f"Hex socket across flats {socket_size:g} mm.")

    return {
        "project_name": name,
        "unit": "mm",
        "description": f"{default['description']} generated from request: {prompt}",
        "parts": [
            {
                "name": name,
                "kind": "screw",
                "family": default["family"],
                "standard": default["standard"],
                "variant": variant,
                "nominal_thread": thread,
                "thread_pitch_mm": pitch,
                "thread_length_mm": thread_length,
                "head_style": default["head_style"],
                "drive_style": default["drive_style"],
                "grade": default["grade"],
                "material": default["material"],
                "outer_diameter_mm": diameter,
                "inner_diameter_mm": None,
                "length_mm": length,
                "width_mm": width,
                "height_mm": head_height,
                "thickness_mm": None,
                "holes": [],
                "chamfers": [{"edge": "both", "size_mm": default["chamfer_mm"], "angle_deg": 45}],
                "fillets": [{"edge": "back", "radius_mm": max(0.2, diameter * 0.08)}],
                "tolerance": {"plus_mm": 0.0, "minus_mm": 0.2, "note": f"{thread} external thread; general tolerance ISO 2768-m."},
                "position_mm": [0, 0, 0],
                "notes": notes,
                "standard_dimensions": {
                    **thread_row,
                    "head_diameter_mm": head_diameter,
                    "head_height_mm": head_height,
                    "thread_length_mm": thread_length,
                    "socket_size_mm": socket_size,
                },
            }
        ],
        "manufacturing_notes": [
            "Cold heading or CNC turning according to selected production route.",
            "Roll or cut metric thread; verify with GO/NO-GO thread gauges.",
            "Deburr thread start and head edges; apply specified surface treatment.",
            "Inspect head dimensions, thread pitch, effective length, straightness, and material grade certificate.",
        ],
    }


def expand_standard_parts(raw: dict[str, Any], prompt: str) -> tuple[dict[str, Any], str | None]:
    if looks_like_fastener(prompt):
        return fastener_spec_from_prompt(prompt), "standard_library:fastener"

    changed = False
    spec = copy.deepcopy(raw)
    for part in spec.get("parts", []):
        fingerprint = json.dumps(part, ensure_ascii=False).lower()
        if any(token in fingerprint for token in ["螺丝", "螺钉", "螺栓", "screw", "bolt", "fastener"]):
            replacement = fastener_spec_from_prompt(f"{prompt} {fingerprint}")
            part.clear()
            part.update(replacement["parts"][0])
            changed = True
    return spec, "standard_library:normalized_fastener" if changed else None
