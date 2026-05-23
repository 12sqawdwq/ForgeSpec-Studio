from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cad_engine import OUTPUT_DIR, build_assembly
from llm import generate_spec
from schemas import AssemblySpec, BuildRequest, GenerateRequest


app = FastAPI(title="GenCAD Gemini Studio", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/generate-config")
async def generate_config(req: GenerateRequest) -> dict:
    try:
        raw, source = await generate_spec(req.prompt, req.use_gemini)
        spec = AssemblySpec.model_validate(raw)
        return {"source": source, "spec": spec.model_dump()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"configuration generation failed: {exc}") from exc


@app.post("/api/build")
def build(req: BuildRequest) -> dict:
    try:
        stl_path, json_path, summary = build_assembly(req.spec)
        return {
            "ok": True,
            "summary": summary,
            "stl_url": f"/outputs/{stl_path.name}",
            "config_url": f"/outputs/{json_path.name}",
            "preview_url": f"/outputs/{summary['preview']}",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CAD build failed: {exc}") from exc


@app.get("/api/files")
def files() -> dict:
    OUTPUT_DIR.mkdir(exist_ok=True)
    items = sorted(Path("outputs").glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {"files": [{"name": p.name, "url": f"/outputs/{p.name}", "size": p.stat().st_size} for p in items[:50]]}
