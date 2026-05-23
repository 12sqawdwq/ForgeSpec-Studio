from __future__ import annotations

import json
import os
import re

import httpx
from dotenv import load_dotenv

from alignment import validate_prompt_alignment
from standard_library import expand_standard_parts, is_primary_fastener_request
from templates import fallback_spec

load_dotenv()


SYSTEM_PROMPT = """You generate industrial CAD configuration JSON.
Return only JSON matching this schema:
{
  "project_name": "snake_case_name",
  "unit": "mm",
  "description": "string",
  "decomposition": {
    "main_object": "the object requested as the design target",
    "scope": "single_part|multi_part_assembly|standard_part|unknown",
    "requested_output": ["stl", "json", "preview", "..."],
    "functional_components": ["components that form the main object"],
    "standard_part_mentions": ["standard/catalog parts mentioned as hardware or subcomponents"],
    "assumptions": ["explicit assumptions made to fill missing dimensions"]
  },
  "parts": [
    {
      "name": "string",
      "kind": "flange|shaft|spacer|bracket|screw",
      "family": "fastener|rotary|structural|spacer|null",
      "standard": "ISO/GB/DIN/JIS reference or null",
      "variant": "specific part variant or null",
      "nominal_thread": "M3|M4|M5|M6|M8|M10|M12|M16 or null",
      "thread_pitch_mm": number|null,
      "thread_length_mm": number|null,
      "head_style": "hex|cylindrical_socket|countersunk|button|null",
      "drive_style": "external_hex|hex_socket|phillips|slot|null",
      "grade": "material/property grade or null",
      "material": "string",
      "outer_diameter_mm": number|null,
      "inner_diameter_mm": number|null,
      "length_mm": number|null,
      "width_mm": number|null,
      "height_mm": number|null,
      "thickness_mm": number|null,
      "holes": [{"count": integer, "diameter_mm": number, "bolt_circle_diameter_mm": number, "through": true, "counterbore_diameter_mm": number|null, "counterbore_depth_mm": number|null, "tolerance": {"plus_mm": number, "minus_mm": number, "note": "string"}}],
      "chamfers": [{"edge": "front|back|both|holes|all", "size_mm": number, "angle_deg": 45}],
      "fillets": [{"edge": "front|back|both|all", "radius_mm": number}],
      "tolerance": {"plus_mm": number, "minus_mm": number, "note": "string"},
      "position_mm": [number, number, number],
      "notes": ["string"],
      "standard_dimensions": {}
    }
  ],
  "manufacturing_notes": ["string"]
}
Use manufacturable metric dimensions. Include tolerances, chamfers, fillets, hole details, material, and inspection notes.
General reasoning policy:
1. First identify the user's main design target. Treat words after "with / composed of / using / include / 由 / 包含 / 若干" as components or hardware unless they are clearly the main object.
2. If the main target is an assembly, set decomposition.scope="multi_part_assembly" and create several functional parts. Do not replace the entire assembly with one mentioned screw, bolt, bearing, washer, or other catalog item.
3. If the main target itself is a standard/catalog part, set decomposition.scope="standard_part" and use the closest ISO/GB/DIN/JIS family.
4. For standard screws/bolts as the main target, choose ISO 4017 / GB/T 5783 hex head bolt M10x50 class 8.8 unless a different type or size is specified.
5. For socket head cap screws, use ISO 4762 / GB/T 70.1.
6. Use kind "screw" only for actual screw/bolt parts, not for assemblies that merely mention fasteners.
7. When the request is broad, make conservative concept-level geometry with explicit assumptions instead of pretending it is production-ready."""


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body = exc.response.text.replace("\n", " ")
        body = re.sub(r"([?&]key=)[^&\s]+", r"\1<hidden>", body)
        body = re.sub(r"\s+", " ", body).strip()
        if status == 429:
            return f"429 Too Many Requests / quota or rate limit"
        return f"{status} {exc.response.reason_phrase}: {body[:220]}"
    text = str(exc).replace("\n", " ")
    text = re.sub(r"([?&]key=)[^&\s]+", r"\1<hidden>", text)
    text = re.sub(r"(GEMINI_API_KEY=)[^\s]+", r"\1<hidden>", text)
    text = re.sub(r"(ZHIPU_API_KEY=)[^\s]+", r"\1<hidden>", text)
    return text[:180]


async def _generate_with_zhipu(prompt: str) -> tuple[dict, str]:
    key = os.getenv("ZHIPU_API_KEY", "").strip()
    if not key or key.startswith("PASTE_"):
        raise RuntimeError("zhipu:no_api_key")

    model = os.getenv("ZHIPU_MODEL", "glm-4.5-flash").strip()
    url = os.getenv("ZHIPU_API_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions").strip()
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT + "\nReturn JSON only. Do not include markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.15,
        "max_tokens": 4096,
        "thinking": {"type": "disabled"},
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    text = data["choices"][0]["message"]["content"]
    return _extract_json(text), f"zhipu:{model}"


async def _generate_with_gemini(prompt: str) -> tuple[dict, str]:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or key.startswith("PASTE_"):
        raise RuntimeError("gemini:no_api_key")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    base = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    models = []
    for candidate in [model, "gemini-2.5-flash", "gemini-flash-latest"]:
        if candidate and candidate not in models:
            models.append(candidate)

    base_payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{SYSTEM_PROMPT}\n\nUser request:\n{prompt}"}],
            }
        ],
    }
    errors = []
    async with httpx.AsyncClient(timeout=90) as client:
        for candidate in models:
            url = f"{base}/models/{candidate}:generateContent"
            for generation_config in (
                {"temperature": 0.15, "responseMimeType": "application/json"},
                {"temperature": 0.15},
            ):
                payload = dict(base_payload)
                payload["generationConfig"] = generation_config
                try:
                    response = await client.post(url, params={"key": key}, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return _extract_json(text), f"gemini:{candidate}"
                except Exception as exc:
                    errors.append(f"{candidate}:{_safe_error(exc)}")

    reason = " | ".join(errors)[-360:] if errors else "unknown error"
    raise RuntimeError(f"gemini:{reason}")


async def generate_spec(prompt: str, use_gemini: bool = True) -> tuple[dict, str]:
    load_dotenv(".env", override=True)
    if is_primary_fastener_request(prompt):
        raw, standard_source = expand_standard_parts({}, prompt)
        return raw, standard_source or "standard_library:fastener"

    if not use_gemini:
        raw, standard_source = expand_standard_parts(fallback_spec(prompt), prompt)
        return raw, standard_source or "fallback:llm_disabled"

    providers = [
        item.strip().lower()
        for item in os.getenv("LLM_PROVIDER_ORDER", "zhipu,gemini").split(",")
        if item.strip()
    ]
    errors = []
    for provider in providers:
        try:
            if provider == "zhipu":
                raw, source = await _generate_with_zhipu(prompt)
                raw, standard_source = expand_standard_parts(raw, prompt)
                validate_prompt_alignment(raw, prompt)
                return raw, f"{source}+{standard_source}" if standard_source else source
            if provider == "gemini":
                raw, source = await _generate_with_gemini(prompt)
                raw, standard_source = expand_standard_parts(raw, prompt)
                validate_prompt_alignment(raw, prompt)
                return raw, f"{source}+{standard_source}" if standard_source else source
        except Exception as exc:
            errors.append(f"{provider}:{_safe_error(exc)}")

    if not errors:
        raw, standard_source = expand_standard_parts(fallback_spec(prompt), prompt)
        validate_prompt_alignment(raw, prompt)
        return raw, standard_source or "fallback:no_provider_configured"
    reason = " | ".join(errors)[-420:]
    raw, standard_source = expand_standard_parts(fallback_spec(prompt), prompt)
    validate_prompt_alignment(raw, prompt)
    return raw, standard_source or f"fallback:llm_error:{reason}"
