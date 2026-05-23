from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from brief import CadBrief


IntentScope = Literal["standard_part", "single_part", "multi_part_assembly", "robot_description", "inspection_or_modification", "unknown"]


class TypedIntent(BaseModel):
    scope: IntentScope
    main_object: str
    generator_family: str
    requested_output: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    standard_part_mentions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


def _family_from_text(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ["flange", "\u6cd5\u5170"]):
        return "flange"
    if any(token in lower for token in ["plate", "block", "\u677f", "\u5757"]):
        return "plate_block"
    if any(token in lower for token in ["bracket", "\u652f\u67b6"]):
        return "bracket"
    if any(token in lower for token in ["shaft", "\u8f74"]):
        return "shaft"
    if any(token in lower for token in ["screw", "bolt", "fastener", "\u87ba\u4e1d", "\u87ba\u9489", "\u87ba\u6813"]):
        return "fastener"
    if any(token in lower for token in ["robot", "arm", "\u673a\u68b0\u81c2", "\u516d\u8f74"]):
        return "robot_arm_concept"
    return "generic_assembly"


def classify_intent(brief: CadBrief) -> TypedIntent:
    scope = brief.scope_hint
    if scope == "robot_description":
        family = "robot_arm_concept"
    elif scope == "multi_part_assembly":
        family = "generic_assembly"
    elif scope == "standard_part":
        family = "fastener"
    else:
        family = _family_from_text(f"{brief.main_object} {' '.join(brief.functional_components)}")
        if scope == "unknown":
            scope = "single_part" if family != "generic_assembly" else "multi_part_assembly"
    return TypedIntent(
        scope=scope,
        main_object=brief.main_object,
        generator_family=family,
        requested_output=brief.requested_output,
        components=brief.functional_components,
        standard_part_mentions=brief.standard_part_mentions,
        assumptions=brief.assumptions,
    )
