from __future__ import annotations

import pprint

from schemas import AssemblySpec


def render_cadquery_source(spec: AssemblySpec) -> str:
    """Render a runnable CadQuery source snapshot for the generated model."""
    spec_data = spec.model_dump(mode="json")
    spec_literal = pprint.pformat(spec_data, width=118, sort_dicts=False)
    return f'''from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import cadquery as cq


SPEC = {spec_literal}


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_")
    return value.lower() or "cad_model"


def hex_point_diameter(across_flats: float) -> float:
    return 2.0 * across_flats / math.sqrt(3.0)


def add_bolt_circle(obj: cq.Workplane, part: dict, thickness: float) -> cq.Workplane:
    for pattern in part.get("holes", []):
        radius = float(pattern.get("bolt_circle_diameter_mm") or 0) / 2.0
        for i in range(int(pattern.get("count") or 0)):
            angle = 2 * math.pi * i / int(pattern.get("count") or 1)
            point = (radius * math.cos(angle), radius * math.sin(angle))
            obj = obj.faces(">Z").workplane().pushPoints([point]).hole(float(pattern.get("diameter_mm") or 1.0))
            if pattern.get("counterbore_diameter_mm") and pattern.get("counterbore_depth_mm"):
                obj = (
                    obj.faces(">Z")
                    .workplane()
                    .pushPoints([point])
                    .cboreHole(
                        float(pattern["diameter_mm"]),
                        float(pattern["counterbore_diameter_mm"]),
                        float(pattern["counterbore_depth_mm"]),
                        depth=thickness,
                    )
                )
    return obj


def apply_rounding(obj: cq.Workplane, part: dict) -> cq.Workplane:
    for fillet in part.get("fillets", []):
        radius = float(fillet.get("radius_mm") or 0)
        if radius > 0:
            try:
                obj = obj.edges().fillet(radius)
            except Exception:
                pass
    for chamfer in part.get("chamfers", []):
        size = float(chamfer.get("size_mm") or 0)
        if size > 0:
            try:
                obj = obj.edges().chamfer(size)
            except Exception:
                pass
    return obj


def build_screw(part: dict) -> cq.Workplane:
    diameter = float(part.get("outer_diameter_mm") or 10.0)
    length = float(part.get("length_mm") or 50.0)
    pitch = float(part.get("thread_pitch_mm") or max(0.5, diameter * 0.15))
    thread_length = min(float(part.get("thread_length_mm") or length), length)
    dims = part.get("standard_dimensions") or {{}}
    head_style = str(part.get("head_style") or "hex").lower()

    if head_style == "cylindrical_socket":
        head_diameter = float(dims.get("socket_head_diameter_mm") or part.get("width_mm") or diameter * 1.6)
        head_height = float(dims.get("socket_head_height_mm") or part.get("height_mm") or diameter)
        head = cq.Workplane("XY").circle(head_diameter / 2).extrude(head_height).translate((0, 0, length))
    else:
        across_flats = float(dims.get("hex_af_mm") or part.get("width_mm") or diameter * 1.7)
        head_height = float(dims.get("hex_head_height_mm") or part.get("height_mm") or diameter * 0.65)
        head = cq.Workplane("XY").polygon(6, hex_point_diameter(across_flats)).extrude(head_height).translate((0, 0, length))

    obj = cq.Workplane("XY").circle(diameter / 2).extrude(length).union(head)

    ridge_height = min(max(pitch * 0.18, 0.12), diameter * 0.06)
    ridge_width = min(max(pitch * 0.18, 0.10), 0.45)
    for index in range(min(int(thread_length / pitch), 90)):
        z = index * pitch + pitch * 0.35
        ridge = cq.Workplane("XY").circle(diameter / 2 + ridge_height).extrude(ridge_width).translate((0, 0, z))
        obj = obj.union(ridge)
    return obj


def build_part(part: dict) -> cq.Workplane:
    geometry_kind = part.get("geometry_kind") or part.get("kind") or "generic"
    if geometry_kind == "screw":
        obj = build_screw(part)
    elif geometry_kind == "shaft":
        diameter = float(part.get("outer_diameter_mm") or 30)
        length = float(part.get("length_mm") or 60)
        obj = cq.Workplane("XY").circle(diameter / 2).extrude(length)
    elif geometry_kind == "spacer":
        outer = float(part.get("outer_diameter_mm") or 60)
        inner = float(part.get("inner_diameter_mm") or 30)
        length = float(part.get("length_mm") or part.get("thickness_mm") or 20)
        obj = cq.Workplane("XY").circle(outer / 2).circle(inner / 2).extrude(length)
    elif geometry_kind in {{"bracket", "plate", "block", "generic"}}:
        width = float(part.get("width_mm") or 100)
        height = float(part.get("height_mm") or 70)
        thickness = float(part.get("thickness_mm") or 10)
        leg = float(part.get("length_mm") or 60)
        if geometry_kind in {{"plate", "block"}}:
            obj = cq.Workplane("XY").box(width, leg, height or thickness, centered=(True, True, False))
        else:
            base = cq.Workplane("XY").box(width, leg, thickness, centered=(True, True, False))
            upright = cq.Workplane("XZ").box(width, height, thickness, centered=(True, False, False)).translate(
                (0, -leg / 2 + thickness / 2, thickness / 2)
            )
            obj = base.union(upright)
        obj = add_bolt_circle(obj, part, thickness)
    else:
        outer = float(part.get("outer_diameter_mm") or 100)
        inner = float(part.get("inner_diameter_mm") or 0)
        thickness = float(part.get("thickness_mm") or part.get("length_mm") or 12)
        obj = cq.Workplane("XY").circle(outer / 2)
        if inner > 0:
            obj = obj.circle(inner / 2)
        obj = obj.extrude(thickness)
        obj = add_bolt_circle(obj, part, thickness)

    obj = apply_rounding(obj, part)
    x, y, z = part.get("position_mm") or (0, 0, 0)
    return obj.translate((float(x), float(y), float(z)))


def build_model() -> cq.Shape:
    compound = None
    for part in SPEC["parts"]:
        solid = build_part(part).val()
        compound = solid if compound is None else cq.Compound.makeCompound([compound, solid])
    if compound is None:
        raise ValueError("SPEC contains no parts.")
    return compound


def export_outputs(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = slugify(SPEC.get("project_name", "cad_model"))
    compound = build_model()
    step_path = out_dir / f"{{base}}.step"
    stl_path = out_dir / f"{{base}}.stl"
    meta_path = out_dir / f"{{base}}.metadata.json"
    cq.exporters.export(compound, str(step_path))
    cq.exporters.export(compound, str(stl_path), tolerance=0.05, angularTolerance=0.1)
    meta_path.write_text(json.dumps(SPEC, ensure_ascii=False, indent=2), encoding="utf-8")
    return {{"step": str(step_path), "stl": str(stl_path), "metadata": str(meta_path)}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regenerate ForgeSpec Studio CAD outputs from Python source.")
    parser.add_argument("--out", default="outputs", help="Output directory")
    args = parser.parse_args()
    print(json.dumps(export_outputs(Path(args.out)), ensure_ascii=False, indent=2))
'''
