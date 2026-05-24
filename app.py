from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cad_engine import OUTPUT_DIR, build_assembly, build_source_package
from llm import generate_spec
from schemas import AssemblySpec, BuildRequest, GenerateRequest, SourceBuildRequest
from source_security import validate_cad_source


app = FastAPI(title="ForgeSpec Studio", version="0.2.0")
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
            "stl_url": f"/outputs/{summary['stl']}",
            "step_url": f"/outputs/{summary['step']}",
            "source_url": f"/outputs/{summary['source']}",
            "config_url": f"/outputs/{summary['config']}",
            "preview_url": f"/outputs/{summary['preview']}",
            "manifest_url": f"/outputs/{summary['manifest']}",
            "assurance_report_url": f"/outputs/{summary['assurance_report']}",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CAD build failed: {exc}") from exc


@app.post("/api/validate-source")
def validate_source(req: SourceBuildRequest) -> dict:
    return validate_cad_source(req.source).model_dump()


@app.post("/api/build-source")
def build_source(req: SourceBuildRequest) -> dict:
    try:
        return build_source_package(req.source, req.prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"source build failed: {exc}") from exc


@app.get("/api/jobs/{job_id}/assurance-report")
def assurance_report(job_id: str) -> FileResponse:
    if "/" in job_id or "\\" in job_id or ".." in job_id:
        raise HTTPException(status_code=400, detail="invalid job id")
    path = OUTPUT_DIR / job_id / "assurance_report.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="assurance report not found")
    return FileResponse(path)


@app.get("/api/files")
def files() -> dict:
    OUTPUT_DIR.mkdir(exist_ok=True)
    items = sorted((p for p in Path("outputs").rglob("*") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "files": [
            {"name": p.relative_to("outputs").as_posix(), "url": f"/outputs/{p.relative_to('outputs').as_posix()}", "size": p.stat().st_size}
            for p in items[:50]
        ]
    }
