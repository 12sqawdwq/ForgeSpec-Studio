from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from standard_library import looks_like_fastener


Scope = Literal["single_part", "multi_part_assembly", "standard_part", "robot_description", "inspection_or_modification", "unknown"]


class DimensionMention(BaseModel):
    raw: str
    value_mm: float
    axis_or_name: str = "unspecified"


class CadBrief(BaseModel):
    prompt: str
    main_object: str
    scope_hint: Scope = "unknown"
    units: Literal["mm"] = "mm"
    requested_output: list[str] = Field(default_factory=lambda: ["stl", "json", "preview"])
    functional_components: list[str] = Field(default_factory=list)
    standard_part_mentions: list[str] = Field(default_factory=list)
    dimensions: list[DimensionMention] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


ASSEMBLY_TERMS = (
    "assembly",
    "assembled",
    "robot",
    "robotic",
    "mechanical arm",
    "manipulator",
    "composed of",
    "consisting of",
    "\u88c5\u914d",
    "\u88c5\u914d\u4f53",
    "\u673a\u68b0\u81c2",
    "\u516d\u8f74",
    "\u7ec4\u6210",
)

PART_TERMS = (
    "block",
    "plate",
    "bracket",
    "flange",
    "shaft",
    "\u5b89\u88c5\u5757",
    "\u5b89\u88c5\u677f",
    "\u652f\u67b6",
    "\u6cd5\u5170",
    "\u8f74",
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def split_components(prompt: str) -> list[str]:
    text = prompt.strip()
    markers = ["\u7531", "\u5305\u62ec", "\u5305\u542b", "with", "including", "composed of", "consisting of"]
    lower = text.lower()
    start = -1
    marker_len = 0
    for marker in markers:
        idx = lower.find(marker.lower())
        if idx >= 0 and (start < 0 or idx < start):
            start = idx
            marker_len = len(marker)
    if start < 0:
        return []
    text = text[start + marker_len :]
    text = re.split(r"\u7ec4\u6210|\u5bfc\u51fa|export|output", text, maxsplit=1, flags=re.IGNORECASE)[0]
    chunks = re.split(r"[,，、;；/]| and | with |\+", text)
    components = []
    for chunk in chunks:
        name = chunk.strip(" .:-")
        name = re.sub(r"^(several|some|multiple|\u82e5\u5e72|\u4e00\u4e2a|\u4e00\u4ef6)\s*", "", name, flags=re.IGNORECASE)
        if 1 < len(name) <= 44 and name not in components:
            components.append(name)
    return components[:10]


def extract_dimensions(prompt: str) -> list[DimensionMention]:
    dimensions: list[DimensionMention] = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)", prompt, re.IGNORECASE):
        dimensions.append(DimensionMention(raw=match.group(0), value_mm=float(match.group(1))))
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*[xX\u00d7*]\s*(\d+(?:\.\d+)?)\s*[xX\u00d7*]\s*(\d+(?:\.\d+)?)\s*(?:mm|\u6beb\u7c73)?", prompt):
        for axis, value in zip(("x", "y", "z"), match.groups(), strict=True):
            dimensions.append(DimensionMention(raw=match.group(0), value_mm=float(value), axis_or_name=axis))
    return dimensions


def infer_main_object(prompt: str) -> str:
    text = prompt.strip()
    text = re.sub(r"^(generate|create|draw|model|design)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(\u751f\u6210|\u7ed8\u5236|\u8bbe\u8ba1|\u5efa\u6a21)\s*", "", text)
    main = re.split(r"\uff0c|,|\u7531|\u5305\u62ec|\u5305\u542b| with | including | composed of ", text, maxsplit=1, flags=re.IGNORECASE)[0]
    main = main.strip(" .:-")
    return main[:80] or prompt[:80]


def infer_scope(prompt: str, main_object: str, components: list[str]) -> Scope:
    if _contains_any(prompt, ("\u68c0\u67e5", "\u4fee\u6539", "inspect", "modify", "review")):
        return "inspection_or_modification"
    if looks_like_fastener(main_object) and not _contains_any(prompt, ASSEMBLY_TERMS):
        return "standard_part"
    if _contains_any(prompt, ("\u673a\u68b0\u81c2", "robot arm", "robotic arm", "manipulator")):
        return "robot_description"
    if len(components) > 1 or _contains_any(prompt, ASSEMBLY_TERMS):
        return "multi_part_assembly"
    if _contains_any(prompt, PART_TERMS) or looks_like_fastener(prompt):
        return "single_part"
    return "unknown"


def build_brief(prompt: str) -> CadBrief:
    components = split_components(prompt)
    main_object = infer_main_object(prompt)
    standard_mentions = [item for item in components if looks_like_fastener(item)]
    if looks_like_fastener(main_object):
        standard_mentions.append(main_object)
    outputs = ["stl", "json", "preview"]
    if "step" in prompt.lower() or "STEP" in prompt:
        outputs.insert(0, "step")
    assumptions = []
    scope = infer_scope(prompt, main_object, components)
    if scope in {"unknown", "multi_part_assembly", "robot_description"}:
        assumptions.append("Missing dimensions may be filled with conservative concept-level defaults.")
    return CadBrief(
        prompt=prompt,
        main_object=main_object,
        scope_hint=scope,
        requested_output=list(dict.fromkeys(outputs)),
        functional_components=components,
        standard_part_mentions=list(dict.fromkeys(standard_mentions)),
        dimensions=extract_dimensions(prompt),
        assumptions=assumptions,
    )
