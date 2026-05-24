from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


EXECUTABLE_KINDS = {"flange", "shaft", "spacer", "bracket", "screw", "plate", "block", "generic"}
KIND_ALIASES = {
    "mounting_plate": "plate",
    "base_plate": "plate",
    "end_plate": "plate",
    "cover_plate": "plate",
    "mounting_block": "block",
    "bearing_block": "block",
    "bearing_housing": "flange",
    "joint_housing": "flange",
    "link": "bracket",
    "arm_link": "bracket",
    "beam": "bracket",
    "bolt": "screw",
    "fastener": "screw",
    "cap_screw": "screw",
    "dowel_pin": "shaft",
    "pin": "shaft",
    "washer": "spacer",
    "nut": "spacer",
}


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
    kind: str = "generic"
    geometry_kind: str | None = None
    family: str | None = None
    taxonomy: str | None = None
    category: str | None = None
    type_code: str | None = None
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

    @field_validator("kind", "geometry_kind", mode="before")
    @classmethod
    def normalize_kind_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        return KIND_ALIASES.get(text, text)

    @model_validator(mode="after")
    def set_geometry_kind(self) -> "PartSpec":
        raw_kind = (self.kind or "generic").strip().lower()
        executable = KIND_ALIASES.get(raw_kind, raw_kind)
        if executable not in EXECUTABLE_KINDS:
            executable = "generic"
        self.geometry_kind = self.geometry_kind or executable
        if self.geometry_kind not in EXECUTABLE_KINDS:
            self.geometry_kind = KIND_ALIASES.get(self.geometry_kind, "generic")
        self.taxonomy = self.taxonomy or self.family
        self.category = self.category or self.variant or raw_kind
        self.type_code = self.type_code or raw_kind
        return self


class TaskDecomposition(BaseModel):
    main_object: str = ""
    scope: Literal["single_part", "multi_part_assembly", "standard_part", "robot_description", "inspection_or_modification", "unknown"] = "unknown"
    requested_output: list[str] = Field(default_factory=list)
    functional_components: list[str] = Field(default_factory=list)
    standard_part_mentions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class AssemblySpec(BaseModel):
    project_name: str = "industrial_parametric_part"
    unit: Literal["mm"] = "mm"
    description: str
    decomposition: TaskDecomposition = Field(default_factory=TaskDecomposition)
    parts: list[PartSpec]
    manufacturing_notes: list[str] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    prompt: str
    use_gemini: bool = True


class BuildRequest(BaseModel):
    spec: AssemblySpec


class SourceBuildRequest(BaseModel):
    source: str
    prompt: str | None = None
