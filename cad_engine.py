from __future__ import annotations

import json
import math
import re
import uuid
from pathlib import Path

import cadquery as cq

from schemas import AssemblySpec, PartSpec
from preview import render_stl_svg


OUTPUT_DIR = Path("outputs")


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_")
    return value.lower() or "cad_model"


def _apply_rounding(obj: cq.Workplane, part: PartSpec) -> cq.Workplane:
    for fillet in part.fillets:
        if fillet.radius_mm > 0:
            try:
                obj = obj.edges().fillet(fillet.radius_mm)
            except Exception:
                pass
    for chamfer in part.chamfers:
        if chamfer.size_mm > 0:
            try:
                obj = obj.edges().chamfer(chamfer.size_mm)
            except Exception:
                pass
    return obj


def _add_bolt_circle(obj: cq.Workplane, part: PartSpec, thickness: float) -> cq.Workplane:
    for pattern in part.holes:
        radius = pattern.bolt_circle_diameter_mm / 2.0
        for i in range(pattern.count):
            angle = 2 * math.pi * i / pattern.count
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            obj = obj.faces(">Z").workplane().pushPoints([(x, y)]).hole(pattern.diameter_mm)
            if pattern.counterbore_diameter_mm and pattern.counterbore_depth_mm:
                obj = (
                    obj.faces(">Z")
                    .workplane()
                    .pushPoints([(x, y)])
                    .cboreHole(pattern.diameter_mm, pattern.counterbore_diameter_mm, pattern.counterbore_depth_mm, depth=thickness)
                )
    return obj


def _hex_point_diameter(across_flats: float) -> float:
    return 2.0 * across_flats / math.sqrt(3.0)


def _build_screw(part: PartSpec) -> cq.Workplane:
    diameter = part.outer_diameter_mm or 10.0
    length = part.length_mm or 50.0
    pitch = part.thread_pitch_mm or max(0.5, diameter * 0.15)
    thread_length = min(part.thread_length_mm or length, length)
    dims = part.standard_dimensions or {}
    head_style = (part.head_style or "hex").lower()

    if head_style == "cylindrical_socket":
        head_diameter = float(dims.get("socket_head_diameter_mm") or part.width_mm or diameter * 1.6)
        head_height = float(dims.get("socket_head_height_mm") or part.height_mm or diameter)
        head = cq.Workplane("XY").circle(head_diameter / 2).extrude(head_height).translate((0, 0, length))
    else:
        across_flats = float(dims.get("hex_af_mm") or part.width_mm or diameter * 1.7)
        head_height = float(dims.get("hex_head_height_mm") or part.height_mm or diameter * 0.65)
        head = cq.Workplane("XY").polygon(6, _hex_point_diameter(across_flats)).extrude(head_height).translate((0, 0, length))

    shank = cq.Workplane("XY").circle(diameter / 2).extrude(length)
    obj = shank.union(head)

    if part.drive_style == "hex_socket":
        socket_af = float(dims.get("socket_size_mm") or diameter * 0.6)
        socket_depth = min(head_height * 0.65, diameter * 0.8)
        try:
            obj = obj.faces(">Z").workplane().polygon(6, _hex_point_diameter(socket_af)).cutBlind(-socket_depth)
        except Exception:
            pass

    ridge_height = min(max(pitch * 0.18, 0.12), diameter * 0.06)
    ridge_width = min(max(pitch * 0.18, 0.10), 0.45)
    ridge_count = min(int(thread_length / pitch), 90)
    for index in range(ridge_count):
        z = index * pitch + pitch * 0.35
        ridge = cq.Workplane("XY").circle(diameter / 2 + ridge_height).extrude(ridge_width).translate((0, 0, z))
        obj = obj.union(ridge)

    return obj


def build_part(part: PartSpec) -> cq.Workplane:
    if part.kind == "screw":
        obj = _build_screw(part)
    elif part.kind == "shaft":
        diameter = part.outer_diameter_mm or 30
        length = part.length_mm or 60
        obj = cq.Workplane("XY").circle(diameter / 2).extrude(length)
    elif part.kind == "spacer":
        outer = part.outer_diameter_mm or 60
        inner = part.inner_diameter_mm or 30
        length = part.length_mm or part.thickness_mm or 20
        obj = cq.Workplane("XY").circle(outer / 2).circle(inner / 2).extrude(length)
    elif part.kind == "bracket":
        width = part.width_mm or 100
        height = part.height_mm or 70
        thickness = part.thickness_mm or 10
        leg = part.length_mm or 60
        base = cq.Workplane("XY").box(width, leg, thickness, centered=(True, True, False))
        upright = cq.Workplane("XZ").box(width, height, thickness, centered=(True, False, False)).translate((0, -leg / 2 + thickness / 2, thickness / 2))
        obj = base.union(upright)
        obj = _add_bolt_circle(obj, part, thickness)
    else:
        outer = part.outer_diameter_mm or 100
        inner = part.inner_diameter_mm or 0
        thickness = part.thickness_mm or part.length_mm or 12
        obj = cq.Workplane("XY").circle(outer / 2)
        if inner > 0:
            obj = obj.circle(inner / 2)
        obj = obj.extrude(thickness)
        obj = _add_bolt_circle(obj, part, thickness)

    obj = _apply_rounding(obj, part)
    x, y, z = part.position_mm
    return obj.translate((x, y, z))


def build_assembly(spec: AssemblySpec) -> tuple[Path, Path, dict]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    run_id = uuid.uuid4().hex[:10]
    base = f"{slugify(spec.project_name)}_{run_id}"
    stl_path = OUTPUT_DIR / f"{base}.stl"
    json_path = OUTPUT_DIR / f"{base}.json"
    preview_path = OUTPUT_DIR / f"{base}.svg"

    compound = None
    part_summaries = []
    for part in spec.parts:
        obj = build_part(part)
        solid = obj.val()
        compound = solid if compound is None else cq.Compound.makeCompound([compound, solid])
        part_summaries.append(
            {
                "name": part.name,
                "kind": part.kind,
                "material": part.material,
                "tolerance": part.tolerance.model_dump(),
                "notes": part.notes,
            }
        )

    if compound is None:
        raise ValueError("Assembly must contain at least one part.")

    cq.exporters.export(compound, str(stl_path), tolerance=0.05, angularTolerance=0.1)
    render_stl_svg(stl_path, preview_path)
    json_path.write_text(json.dumps(spec.model_dump(), indent=2), encoding="utf-8")
    return stl_path, json_path, {"parts": part_summaries, "stl": stl_path.name, "config": json_path.name, "preview": preview_path.name}
