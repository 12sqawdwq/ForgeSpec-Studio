from __future__ import annotations

import math
import struct
from pathlib import Path


def _read_binary_stl(path: Path, max_triangles: int = 360) -> list[tuple[tuple[float, float, float], ...]]:
    data = path.read_bytes()
    if len(data) < 84:
        return []
    count = struct.unpack_from("<I", data, 80)[0]
    available = (len(data) - 84) // 50
    count = min(count, available, max_triangles)
    tris = []
    offset = 84
    step = max(1, available // max_triangles) if available else 1
    for _ in range(count):
        v = struct.unpack_from("<12fH", data, offset)
        tris.append(((v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])))
        offset += 50 * step
        if offset + 50 > len(data):
            break
    return tris


def _project(point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    rz = math.radians(-38)
    rx = math.radians(24)
    x1 = x * math.cos(rz) - y * math.sin(rz)
    y1 = x * math.sin(rz) + y * math.cos(rz)
    z1 = z
    y2 = y1 * math.cos(rx) - z1 * math.sin(rx)
    z2 = y1 * math.sin(rx) + z1 * math.cos(rx)
    return x1, y2, z2


def render_stl_svg(stl_path: Path, svg_path: Path, width: int = 1200, height: int = 760) -> Path:
    triangles = _read_binary_stl(stl_path)
    projected = [[_project(p) for p in tri] for tri in triangles]
    points = [p for tri in projected for p in tri]
    if not points:
        svg_path.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
        return svg_path

    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    scale = min((width - 120) / span_x, (height - 120) / span_y)

    def screen(p: tuple[float, float, float]) -> tuple[float, float]:
        x = 60 + (p[0] - min_x) * scale
        y = height - 60 - (p[1] - min_y) * scale
        return x, y

    ordered = sorted(projected, key=lambda tri: sum(p[2] for p in tri) / 3.0)
    polygons = []
    for tri in ordered:
        normal_hint = abs((tri[1][0] - tri[0][0]) * (tri[2][1] - tri[0][1]) - (tri[1][1] - tri[0][1]) * (tri[2][0] - tri[0][0]))
        shade = max(176, min(222, int(196 + normal_hint * 0.015)))
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (screen(p) for p in tri))
        polygons.append(f"<polygon points='{pts}' fill='rgb({shade},{shade + 6},{shade + 12})' opacity='0.96'/>")

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#f4f6f8"/>
<g>{''.join(polygons)}</g>
</svg>"""
    svg_path.write_text(svg, encoding="utf-8")
    return svg_path
