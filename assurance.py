from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def git_commit() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True, timeout=3)
        return result.stdout.strip()
    except Exception:
        return None


def standards_hash() -> str | None:
    standards_dir = Path("standards")
    if not standards_dir.exists():
        return None
    digest = hashlib.sha256()
    for path in sorted(standards_dir.glob("*.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def write_assurance_files(
    job_dir: Path,
    *,
    job_id: str,
    source_path: Path,
    prompt: str | None,
    validation: dict[str, Any],
    security: dict[str, Any],
    artifacts: dict[str, Path],
    source_label: str,
) -> tuple[Path, Path]:
    now = datetime.now(timezone.utc).isoformat()
    artifact_hashes = {name: sha256_file(path) for name, path in artifacts.items()}
    manifest = {
        "job_id": job_id,
        "created_at": now,
        "mode": "design_assist",
        "source_label": source_label,
        "git_commit": git_commit(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "standards_hash": standards_hash(),
        "prompt_hash": sha256_text(prompt or "") if prompt is not None else None,
        "source_hash": sha256_file(source_path),
        "artifact_hashes": artifact_hashes,
        "security": security,
        "validation": validation,
    }
    engineering_gate = {
        "status": "requires_engineer_review",
        "production_release": False,
        "statement": "Design-assist output only. Engineering review, load cases, materials, tolerances, and manufacturing release are required before use.",
    }
    report = {
        "job_id": job_id,
        "created_at": now,
        "summary": {
            "security_ok": bool(security.get("ok")),
            "validation_ok": bool(validation.get("ok")),
            "engineering_gate": engineering_gate["status"],
        },
        "engineering_gate": engineering_gate,
        "warnings": list(security.get("warnings", [])) + list(validation.get("warnings", [])),
        "manifest": manifest,
    }
    manifest_path = job_dir / "manifest.json"
    report_path = job_dir / "assurance_report.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path, report_path
