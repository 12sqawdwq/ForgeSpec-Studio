from __future__ import annotations

import json
import os
import re

import httpx
from dotenv import load_dotenv

from templates import fallback_spec

load_dotenv()


SYSTEM_PROMPT = """You generate industrial CAD configuration JSON.
Return only JSON matching this schema:
{
  "project_name": "snake_case_name",
  "unit": "mm",
  "description": "string",
  "parts": [
    {
      "name": "string",
      "kind": "flange|shaft|spacer|bracket",
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
      "notes": ["string"]
    }
  ],
  "manufacturing_notes": ["string"]
}
Use manufacturable metric dimensions. Include tolerances, chamfers, fillets, hole details, material, and inspection notes."""


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
    if not use_gemini:
        return fallback_spec(prompt), "fallback:llm_disabled"

    providers = [
        item.strip().lower()
        for item in os.getenv("LLM_PROVIDER_ORDER", "zhipu,gemini").split(",")
        if item.strip()
    ]
    errors = []
    for provider in providers:
        try:
            if provider == "zhipu":
                return await _generate_with_zhipu(prompt)
            if provider == "gemini":
                return await _generate_with_gemini(prompt)
        except Exception as exc:
            errors.append(f"{provider}:{_safe_error(exc)}")

    if not errors:
        return fallback_spec(prompt), "fallback:no_provider_configured"
    reason = " | ".join(errors)[-420:]
    return fallback_spec(prompt), f"fallback:llm_error:{reason}"
