from __future__ import annotations

from typing import Any

from standard_library import is_larger_assembly_request, is_primary_fastener_request


def _parts(raw: dict[str, Any]) -> list[dict[str, Any]]:
    parts = raw.get("parts", [])
    return parts if isinstance(parts, list) else []


def _is_fastener_part(part: dict[str, Any]) -> bool:
    kind = str(part.get("kind", "")).lower()
    geometry_kind = str(part.get("geometry_kind", "")).lower()
    family = str(part.get("family", "")).lower()
    name = str(part.get("name", "")).lower()
    return kind == "screw" or geometry_kind == "screw" or family == "fastener" or "screw" in name or "bolt" in name


def validate_prompt_alignment(raw: dict[str, Any], prompt: str) -> None:
    """Reject obvious target drift before accepting an LLM answer.

    This is intentionally generic. It does not know about any specific
    requested object; it only prevents a mentioned hardware item from replacing
    a larger requested assembly.
    """
    parts = _parts(raw)
    if not parts:
        raise ValueError("generated configuration contains no parts")

    if is_larger_assembly_request(prompt) and not is_primary_fastener_request(prompt):
        all_fasteners = all(_is_fastener_part(part) for part in parts)
        if all_fasteners:
            raise ValueError("target drift: prompt asks for a larger assembly, but generated output contains only fasteners")

        decomposition = raw.get("decomposition") or {}
        if isinstance(decomposition, dict):
            scope = str(decomposition.get("scope", "")).lower()
            if scope == "standard_part" and len(parts) == 1:
                raise ValueError("target drift: assembly prompt was classified as a single standard part")
