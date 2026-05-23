from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Tolerance(BaseModel):
    plus_mm: float = 0.05
    minus_mm: float = 0.05
    note: str = "General machining tolerance unless otherwise specified."


class Chamfer(BaseModel):
    edge: Literal["front", "back", "both", "holes", "all"] = "both"
    size_mm: float = 1.0
    angle_deg: float = 45.0

    @field_validator("edge", mode="before")
    @classmethod
    def normalize_edge(cls, value: object) -> str:
        text = str(value or "both").strip().lower().replace("-", "_").replace(" ", "_")
        if text in {"front", "back", "both", "holes", "all"}:
            return text
        if "hole" in text or "bore" in text or "slot" in text or "groove" in text:
            return "holes"
        if "front" in text or "top" in text:
            return "front"
        if "back" in text or "bottom" in text:
            return "back"
        return "all"


class Fillet(BaseModel):
    edge: Literal["front", "back", "both", "all"] = "both"
    radius_mm: float = 1.5

    @field_validator("edge", mode="before")
    @classmethod
    def normalize_edge(cls, value: object) -> str:
        text = str(value or "both").strip().lower().replace("-", "_").replace(" ", "_")
        if text in {"front", "back", "both", "all"}:
            return text
        if "front" in text or "top" in text:
            return "front"
        if "back" in text or "bottom" in text:
            return "back"
        return "all"


class HolePattern(BaseModel):
    count: int = Field(default=6, ge=1, le=64)
    diameter_mm: float = Field(default=8.0, gt=0)
    bolt_circle_diameter_mm: float = Field(default=80.0, ge=0)
    through: bool = True
    counterbore_diameter_mm: float | None = None
    counterbore_depth_mm: float | None = None
    tolerance: Tolerance = Field(default_factory=Tolerance)


class PartSpec(BaseModel):
    name: str
    kind: Literal["flange", "shaft", "spacer", "bracket", "screw"] = "flange"
    family: str | None = None
    standard: str | None = None
    variant: str | None = None
    nominal_thread: str | None = None
    thread_pitch_mm: float | None = None
    thread_length_mm: float | None = None
    head_style: str | None = None
    drive_style: str | None = None
    grade: str | None = None
    material: str = "6061-T6 aluminum"
    outer_diameter_mm: float | None = None
    inner_diameter_mm: float | None = None
    length_mm: float | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    thickness_mm: float | None = None
    holes: list[HolePattern] = Field(default_factory=list)
    chamfers: list[Chamfer] = Field(default_factory=list)
    fillets: list[Fillet] = Field(default_factory=list)
    tolerance: Tolerance = Field(default_factory=Tolerance)
    position_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    notes: list[str] = Field(default_factory=list)
    standard_dimensions: dict[str, Any] = Field(default_factory=dict)


class AssemblySpec(BaseModel):
    project_name: str = "industrial_parametric_part"
    unit: Literal["mm"] = "mm"
    description: str
    parts: list[PartSpec]
    manufacturing_notes: list[str] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    prompt: str
    use_gemini: bool = True


class BuildRequest(BaseModel):
    spec: AssemblySpec
