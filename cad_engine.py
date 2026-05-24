from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import uuid
from pathlib import Path

import cadquery as cq

from assurance import write_assurance_files
from schemas import AssemblySpec, PartSpec
from cad_source import render_cadquery_source
from preview import render_stl_svg
from source_security import validate_cad_source
from validation import validate_export


OUTPUT_DIR = Path("outputs")
SOURCE_BUILD_TIMEOUT_SECONDS = 90


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
    geometry_kind = part.geometry_kind or part.kind
    if geometry_kind == "screw":
        obj = _build_screw(part)
    elif geometry_kind == "shaft":
        diameter = part.outer_diameter_mm or 30
        length = part.length_mm or 60
        obj = cq.Workplane("XY").circle(diameter / 2).extrude(length)
    elif geometry_kind == "spacer":
        outer = part.outer_diameter_mm or 60
        inner = part.inner_diameter_mm or 30
        length = part.length_mm or part.thickness_mm or 20
        obj = cq.Workplane("XY").circle(outer / 2).circle(inner / 2).extrude(length)
    elif geometry_kind in {"bracket", "plate", "block", "generic"}:
        width = part.width_mm or 100
        height = part.height_mm or 70
        thickness = part.thickness_mm or 10
        leg = part.length_mm or 60
        if geometry_kind in {"plate", "block"}:
            obj = cq.Workplane("XY").box(width, leg, height or thickness, centered=(True, True, False))
        else:
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


def _job_dir(job_id: str) -> Path:
    path = OUTPUT_DIR / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _url(path: Path) -> str:
    return f"/outputs/{path.relative_to(OUTPUT_DIR).as_posix()}"


def build_assembly(spec: AssemblySpec) -> tuple[Path, Path, dict]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    run_id = uuid.uuid4().hex[:10]
    job_id = f"{slugify(spec.project_name)}_{run_id}"
    job_dir = _job_dir(job_id)
    base = slugify(spec.project_name)
    stl_path = job_dir / f"{base}.stl"
    step_path = job_dir / f"{base}.step"
    json_path = job_dir / f"{base}.json"
    source_path = job_dir / f"{base}.py"
    preview_path = job_dir / f"{base}.svg"

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
                "geometry_kind": part.geometry_kind,
                "taxonomy": part.taxonomy,
                "category": part.category,
                "type_code": part.type_code,
                "material": part.material,
                "tolerance": part.tolerance.model_dump(),
                "notes": part.notes,
            }
        )

    if compound is None:
        raise ValueError("Assembly must contain at least one part.")

    cq.exporters.export(compound, str(step_path))
    cq.exporters.export(compound, str(stl_path), tolerance=0.05, angularTolerance=0.1)
    render_stl_svg(stl_path, preview_path)
    source_text = render_cadquery_source(spec)
    security = validate_cad_source(source_text).model_dump()
    if not security["ok"]:
        raise ValueError(f"generated source failed security gate: {security['errors']}")
    source_path.write_text(source_text, encoding="utf-8")
    json_path.write_text(json.dumps(spec.model_dump(), indent=2), encoding="utf-8")
    validation = validate_export(compound, spec, stl_path, json_path, step_path, source_path)
    manifest_path, report_path = write_assurance_files(
        job_dir,
        job_id=job_id,
        source_path=source_path,
        prompt=spec.description,
        validation=validation,
        security=security,
        artifacts={"stl": stl_path, "step": step_path, "config": json_path, "source": source_path, "preview": preview_path},
        source_label="assembly_spec",
    )
    return stl_path, json_path, {
        "job_id": job_id,
        "parts": part_summaries,
        "stl": stl_path.relative_to(OUTPUT_DIR).as_posix(),
        "step": step_path.relative_to(OUTPUT_DIR).as_posix(),
        "source": source_path.relative_to(OUTPUT_DIR).as_posix(),
        "config": json_path.relative_to(OUTPUT_DIR).as_posix(),
        "preview": preview_path.relative_to(OUTPUT_DIR).as_posix(),
        "manifest": manifest_path.relative_to(OUTPUT_DIR).as_posix(),
        "assurance_report": report_path.relative_to(OUTPUT_DIR).as_posix(),
        "security": security,
        "validation": validation,
    }


def build_source_package(source: str, prompt: str | None = None) -> dict:
    OUTPUT_DIR.mkdir(exist_ok=True)
    security = validate_cad_source(source).model_dump()
    if not security["ok"]:
        raise ValueError(f"source failed security gate: {security['errors']}")

    job_id = f"source_{uuid.uuid4().hex[:10]}"
    job_dir = _job_dir(job_id)
    source_path = job_dir / "source.py"
    source_path.write_text(source, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(source_path.name), "--out", "."],
        cwd=job_dir,
        capture_output=True,
        text=True,
        timeout=SOURCE_BUILD_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"source build failed: {result.stderr[-1000:] or result.stdout[-1000:]}")

    step_files = sorted(job_dir.glob("*.step"))
    stl_files = sorted(job_dir.glob("*.stl"))
    metadata_files = sorted(job_dir.glob("*.metadata.json"))
    if not step_files or not stl_files:
        raise ValueError("source build did not produce STEP and STL outputs")

    preview_path = job_dir / "preview.svg"
    render_stl_svg(stl_files[0], preview_path)
    validation = {
        "ok": True,
        "warnings": [],
        "source_exists": True,
        "step_exists": True,
        "stl_exists": True,
        "json_exists": bool(metadata_files),
    }
    manifest_path, report_path = write_assurance_files(
        job_dir,
        job_id=job_id,
        source_path=source_path,
        prompt=prompt,
        validation=validation,
        security=security,
        artifacts={
            "source": source_path,
            "step": step_files[0],
            "stl": stl_files[0],
            "metadata": metadata_files[0] if metadata_files else source_path,
            "preview": preview_path,
        },
        source_label="source_package",
    )
    return {
        "ok": True,
        "job_id": job_id,
        "source_url": _url(source_path),
        "step_url": _url(step_files[0]),
        "stl_url": _url(stl_files[0]),
        "config_url": _url(metadata_files[0]) if metadata_files else None,
        "preview_url": _url(preview_path),
        "manifest_url": _url(manifest_path),
        "assurance_report_url": _url(report_path),
        "summary": {"job_id": job_id, "security": security, "validation": validation},
    }
