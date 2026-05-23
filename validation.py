from __future__ import annotations

from pathlib import Path
from typing import Any

import cadquery as cq

from schemas import AssemblySpec


def validate_spec(spec: AssemblySpec) -> dict[str, Any]:
    warnings: list[str] = []
    if not spec.parts:
        warnings.append("Assembly contains no parts.")
    if spec.decomposition.scope in {"multi_part_assembly", "robot_description"} and len(spec.parts) <= 1:
        warnings.append("Assembly-like request produced one or fewer parts.")
    if spec.decomposition.scope != "standard_part" and spec.parts and all((part.geometry_kind or part.kind) == "screw" for part in spec.parts):
        warnings.append("Non-standard-part request produced only fasteners.")
    standard_refs = [part.standard for part in spec.parts if part.standard]
    taxonomy_counts: dict[str, int] = {}
    for part in spec.parts:
        taxonomy = part.taxonomy or part.family or "unclassified"
        taxonomy_counts[taxonomy] = taxonomy_counts.get(taxonomy, 0) + 1
    return {
        "part_count": len(spec.parts),
        "scope": spec.decomposition.scope,
        "main_object": spec.decomposition.main_object,
        "standard_refs": standard_refs,
        "taxonomy_counts": taxonomy_counts,
        "warnings": warnings,
        "ok": not warnings,
    }


def validate_export(
    compound: cq.Shape,
    spec: AssemblySpec,
    stl_path: Path,
    json_path: Path,
    step_path: Path | None = None,
    source_path: Path | None = None,
) -> dict[str, Any]:
    bbox = compound.BoundingBox()
    summary = validate_spec(spec)
    export_warnings = list(summary["warnings"])
    if not stl_path.exists() or stl_path.stat().st_size <= 0:
        export_warnings.append("STL export missing or empty.")
    if not json_path.exists() or json_path.stat().st_size <= 0:
        export_warnings.append("JSON export missing or empty.")
    if step_path is not None and (not step_path.exists() or step_path.stat().st_size <= 0):
        export_warnings.append("STEP export missing or empty.")
    if source_path is not None and (not source_path.exists() or source_path.stat().st_size <= 0):
        export_warnings.append("Python CAD source export missing or empty.")
    summary.update(
        {
            "bbox_mm": {
                "x": round(float(bbox.xlen), 4),
                "y": round(float(bbox.ylen), 4),
                "z": round(float(bbox.zlen), 4),
            },
            "stl_exists": stl_path.exists(),
            "json_exists": json_path.exists(),
            "step_exists": bool(step_path and step_path.exists()),
            "source_exists": bool(source_path and source_path.exists()),
            "warnings": export_warnings,
            "ok": not export_warnings,
        }
    )
    return summary
