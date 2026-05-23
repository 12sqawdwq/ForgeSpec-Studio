from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


STANDARD_DIR = Path(__file__).with_name("standards")
FASTENER_DB = STANDARD_DIR / "fasteners.json"
CATALOG_DB = STANDARD_DIR / "catalog.json"

FASTENER_TERMS = (
    "bolt",
    "screw",
    "fastener",
    "socket head",
    "hex head",
    "\u87ba\u4e1d",
    "\u87ba\u9489",
    "\u87ba\u6813",
    "\u6807\u51c6\u4ef6\u87ba",
)

ASSEMBLY_CONTEXT_TERMS = (
    "assembly",
    "assembled",
    "robot",
    "robotic",
    "mechanical arm",
    "manipulator",
    "base",
    "flange",
    "joint",
    "link",
    "bracket",
    "plate",
    "\u88c5\u914d",
    "\u88c5\u914d\u4f53",
    "\u673a\u68b0\u81c2",
    "\u6982\u5ff5\u7ea7",
    "\u5e95\u5ea7",
    "\u6cd5\u5170",
    "\u65cb\u8f6c\u5173\u8282",
    "\u81c2\u6746",
    "\u5b89\u88c5\u677f",
    "\u82e5\u5e72",
    "\u7ec4\u6210",
)

ROBOT_CONTEXT_TERMS = (
    "robot",
    "robotic",
    "mechanical arm",
    "manipulator",
    "joint",
    "rotary",
    "\u673a\u68b0\u81c2",
    "\u516d\u8f74",
    "\u5173\u8282",
    "\u65cb\u8f6c",
)

COUPLING_CONTEXT_TERMS = ("coupling", "shaft coupling", "\u8054\u8f74\u5668")
MOTOR_CONTEXT_TERMS = ("motor", "stepper", "servo", "\u7535\u673a", "\u6b65\u8fdb", "\u4f3a\u670d")
SENSOR_CONTEXT_TERMS = ("sensor", "proximity", "limit switch", "\u4f20\u611f\u5668", "\u63a5\u8fd1\u5f00\u5173", "\u9650\u4f4d")


def is_larger_assembly_request(prompt: str) -> bool:
    return _has_assembly_context(prompt)


def _load_fasteners() -> dict[str, Any]:
    return json.loads(FASTENER_DB.read_text(encoding="utf-8"))


def _load_catalog() -> dict[str, Any]:
    if not CATALOG_DB.exists():
        return {"version": "0", "records": []}
    return json.loads(CATALOG_DB.read_text(encoding="utf-8"))


def catalog_records() -> list[dict[str, Any]]:
    return [copy.deepcopy(record) for record in _load_catalog().get("records", [])]


def _record_text(record: dict[str, Any]) -> str:
    fields = [
        record.get("id"),
        record.get("name"),
        record.get("taxonomy"),
        record.get("category"),
        record.get("type_code"),
        record.get("standard"),
        record.get("kind"),
        *(record.get("keywords") or []),
    ]
    return " ".join(str(field) for field in fields if field).lower()


def _matches_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def find_catalog_records(query: str, limit: int = 6, taxonomy: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    lower = query.lower()
    ranked: list[tuple[int, dict[str, Any]]] = []
    for record in catalog_records():
        if taxonomy and record.get("taxonomy") != taxonomy:
            continue
        if category and record.get("category") != category:
            continue
        haystack = _record_text(record)
        score = 0
        for token in re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", lower):
            if not token:
                continue
            if token == str(record.get("type_code", "")).lower() or token == str(record.get("category", "")).lower():
                score += 10
            elif token in haystack:
                score += 3
        if lower and lower in haystack:
            score += 8
        if score:
            ranked.append((score, record))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [record for _, record in ranked[:limit]]


def catalog_part_from_record(record: dict[str, Any], index: int = 0, position: list[float] | None = None) -> dict[str, Any]:
    part = {
        "name": record["name"],
        "kind": record.get("kind", "generic"),
        "geometry_kind": record.get("geometry_kind"),
        "family": record.get("taxonomy"),
        "taxonomy": record.get("taxonomy"),
        "category": record.get("category"),
        "type_code": record.get("type_code"),
        "standard": record.get("standard"),
        "variant": record.get("category"),
        "material": record.get("material", "catalog material"),
        "outer_diameter_mm": record.get("outer_diameter_mm"),
        "inner_diameter_mm": record.get("inner_diameter_mm"),
        "length_mm": record.get("length_mm"),
        "width_mm": record.get("width_mm"),
        "height_mm": record.get("height_mm"),
        "thickness_mm": record.get("thickness_mm"),
        "holes": [],
        "chamfers": [{"edge": "all", "size_mm": 0.3, "angle_deg": 45}],
        "fillets": [{"edge": "all", "radius_mm": 0.4}],
        "tolerance": {"plus_mm": 0.05, "minus_mm": 0.05, "note": "Catalog default tolerance; verify with supplier table before manufacturing."},
        "position_mm": position if position is not None else [index * 55.0, -95.0, 0.0],
        "notes": [
            f"Catalog part id: {record.get('id')}.",
            "Inserted by standard part catalog; geometry is simplified for assembly planning.",
        ],
        "standard_dimensions": {key: value for key, value in record.items() if key.endswith("_mm") or key in {"id", "type_code", "standard"}},
    }
    return {key: value for key, value in part.items() if value is not None}


def _catalog_record_by_id(record_id: str) -> dict[str, Any] | None:
    for record in catalog_records():
        if record.get("id") == record_id:
            return record
    return None


def _add_catalog_id(record_ids: list[str], record_id: str) -> None:
    if record_id not in record_ids:
        record_ids.append(record_id)


def catalog_parts_for_prompt(prompt: str, components: list[str] | None = None, index_base: int = 0) -> list[dict[str, Any]]:
    """Return supporting catalog parts for assemblies without replacing the main object."""
    text = " ".join([prompt, *(components or [])])
    record_ids: list[str] = []

    if _matches_any(text, ROBOT_CONTEXT_TERMS):
        for record_id in ("bearing_6001", "bearing_6002", "dowel_pin_6x24_iso8734", "circlip_shaft_12"):
            _add_catalog_id(record_ids, record_id)

    if re.search(r"\bM\s*6\b", text, re.IGNORECASE):
        for record_id in ("washer_plain_m6_iso7089", "hex_nut_m6_iso4032"):
            _add_catalog_id(record_ids, record_id)
    if re.search(r"\bM\s*8\b", text, re.IGNORECASE):
        for record_id in ("washer_plain_m8_iso7089", "hex_nut_m8_iso4032"):
            _add_catalog_id(record_ids, record_id)

    if _matches_any(text, COUPLING_CONTEXT_TERMS):
        for record_id in ("flexible_coupling_12_12", "parallel_key_6x6x28"):
            _add_catalog_id(record_ids, record_id)
    if _matches_any(text, MOTOR_CONTEXT_TERMS):
        _add_catalog_id(record_ids, "nema17_motor_placeholder")
    if _matches_any(text, SENSOR_CONTEXT_TERMS):
        _add_catalog_id(record_ids, "proximity_sensor_m12_placeholder")

    parts: list[dict[str, Any]] = []
    for offset, record_id in enumerate(record_ids):
        record = _catalog_record_by_id(record_id)
        if record:
            parts.append(catalog_part_from_record(record, index_base + offset, [offset * 55.0, -95.0, 0.0]))
    return parts


def _has_fastener_term(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in FASTENER_TERMS)


def _has_assembly_context(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in ASSEMBLY_CONTEXT_TERMS)


def _find_thread(text: str) -> str:
    match = re.search(r"\bM\s*(3|4|5|6|8|10|12|16)\b", text, re.IGNORECASE)
    if match:
        return f"M{match.group(1)}"
    return "M10"


def _find_length(text: str) -> float:
    compact = text.replace(" ", "")
    patterns = [
        r"M(?:3|4|5|6|8|10|12|16)[x\u00d7*](\d+(?:\.\d+)?)",
        r"(?:length|\u957f\u5ea6|\u957f|\u6746\u957f|\u87ba\u6746\u957f\u5ea6)(?:\u4e3a|=|:)?(\d+(?:\.\d+)?)\s*mm?",
        r"(\d+(?:\.\d+)?)\s*mm(?:\u957f|\u957f\u5ea6)?",
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
    if "\u5185\u516d\u89d2" in text or "socket" in lower or "cap screw" in lower:
        return "socket_head_cap_screw"
    return "hex_head_bolt"


def is_primary_fastener_request(prompt: str) -> bool:
    """Return True only when the requested main object is a fastener.

    A prompt may mention screws as assembly hardware, e.g. "robot arm with
    several M6/M8 bolts"; that must not hijack the entire generation.
    """
    text = prompt.strip()
    if not _has_fastener_term(text):
        return False

    lower = text.lower()
    direct_standard_patterns = (
        "\u6807\u51c6\u4ef6\u87ba\u4e1d",
        "\u6807\u51c6\u4ef6\u87ba\u9489",
        "\u6807\u51c6\u4ef6\u87ba\u6813",
        "standard screw",
        "standard bolt",
        "hex head bolt",
        "socket head cap screw",
    )
    if any(pattern in lower for pattern in direct_standard_patterns):
        return not _has_assembly_context(text) or len(text) <= 80

    starts_as_part = lower.startswith(("generate ", "create ", "draw ", "model ", "design "))
    starts_as_part = starts_as_part or text.startswith(("\u751f\u6210", "\u7ed8\u5236", "\u8bbe\u8ba1", "\u5efa\u6a21"))
    if starts_as_part and not _has_assembly_context(text):
        return True

    short_fastener_request = len(text) <= 48 and _has_fastener_term(text) and not _has_assembly_context(text)
    return short_fastener_request


def looks_like_fastener(prompt: str) -> bool:
    return _has_fastener_term(prompt)


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
        "decomposition": {
            "main_object": name,
            "scope": "standard_part",
            "requested_output": ["stl", "json", "preview"],
            "functional_components": ["head", "threaded_shank"],
            "standard_part_mentions": [f"{default['standard']} {thread}x{length:g}"],
            "assumptions": ["Defaulted to a common metric standard fastener because the prompt did not define a larger assembly."],
        },
        "parts": [
            {
                "name": name,
                "kind": "screw",
                "geometry_kind": "screw",
                "family": default["family"],
                "taxonomy": "fastener",
                "category": variant,
                "type_code": f"{variant}:{thread}",
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
    if is_primary_fastener_request(prompt):
        return fastener_spec_from_prompt(prompt), "standard_library:fastener"

    changed = False
    spec = copy.deepcopy(raw)
    for part in spec.get("parts", []):
        fingerprint = json.dumps(part, ensure_ascii=False).lower()
        part_name = str(part.get("name", "")).lower()
        part_kind = str(part.get("kind", "")).lower()
        explicit_fastener_part = part_kind == "screw" or _has_fastener_term(part_name) or part.get("family") == "fastener"
        already_expanded = part_kind == "screw" and part.get("nominal_thread") and part.get("standard_dimensions")
        if already_expanded:
            continue
        if explicit_fastener_part:
            position = part.get("position_mm", [0, 0, 0])
            replacement = fastener_spec_from_prompt(f"{part_name} {fingerprint}")
            part.clear()
            part.update(replacement["parts"][0])
            part["position_mm"] = position
            changed = True
    return spec, "standard_library:normalized_fastener_parts" if changed else None
