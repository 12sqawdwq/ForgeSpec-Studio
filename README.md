# ForgeSpec Studio

ForgeSpec Studio turns natural-language engineering requirements into
source-first parametric CAD packages, renders an instant browser preview, and
exports STEP/STL/Python/metadata files from a Python CAD backend.

It is designed for industrial standard parts such as flanges, shafts,
mounting blocks, T-slot nuts, dowel pins, and simple precision assemblies.

## Features

- FastAPI backend with a browser-based interactive UI.
- Conda-managed Python environment.
- CadQuery STEP/STL export with runnable Python source snapshots.
- Brief -> intent -> planner -> deterministic AssemblySpec pipeline.
- Standards-backed part expansion for common fasteners.
- Zhipu/BigModel and Gemini API support, with deterministic fallback templates.
- Day/night UI themes, Chinese/English interface, sample prompts, JSON
  highlighting, progress logs, and one-click STEP/STL/Python/JSON downloads.
- Job-scoped outputs with manifest and assurance report artifacts.
- AST-based Python CAD source security checks for source-build workflows.

## Standards Library

ForgeSpec Studio uses a small local standards database in `standards/` to keep
common catalog parts deterministic. For example, a vague request such as
`生成一个标准件螺丝` is expanded without relying on the LLM into an
ISO 4017 / GB/T 5783 M10x50 class 8.8 hex head bolt with head dimensions,
thread pitch, thread length, material, tolerances, and inspection notes.

The first included database is `standards/fasteners.json`. It can be extended
with more metric thread rows, screw variants, washers, nuts, pins, bearings,
keys, and other standard mechanical components.

## Quick Start

```bash
git clone git@github.com:12sqawdwq/ForgeSpec-Studio.git
cd ForgeSpec-Studio

conda env create -f environment.yml
conda activate gencad_gemini

cp .env.example .env
# Edit .env and fill at least one provider key:
# ZHIPU_API_KEY=...
# GEMINI_API_KEY=...

./run.sh
```

The service listens on `0.0.0.0:${PORT:-8000}`. Open:

```text
http://127.0.0.1:8000/
```

## Configuration

Copy `.env.example` to `.env` and set the providers you want to use.

```dotenv
LLM_PROVIDER_ORDER=zhipu,gemini
ZHIPU_API_KEY=PASTE_YOUR_ZHIPU_API_KEY_HERE
ZHIPU_MODEL=glm-4.5-flash

GEMINI_API_KEY=PASTE_YOUR_GEMINI_API_KEY_HERE
GEMINI_MODEL=gemini-2.5-flash
```

If your server needs an HTTP proxy for outbound model calls, add:

```dotenv
GENCAD_HTTP_PROXY=http://127.0.0.1:7890
GENCAD_HTTPS_PROXY=http://127.0.0.1:7890
```

Do not commit `.env`. It is ignored by git.

## Conda Mirror

If the default conda channels are unreachable, create the environment with:

```bash
conda create -y -n gencad_gemini --override-channels \
  -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge \
  python=3.11 cadquery fastapi uvicorn pydantic httpx python-dotenv numpy
```

## Systemd Deployment

Edit `gencad-gemini-studio.service` and replace `/opt/forgespec-studio` with
your actual install path, then install it as a user service:

```bash
mkdir -p ~/.config/systemd/user
cp gencad-gemini-studio.service ~/.config/systemd/user/forgespec-studio.service
systemctl --user daemon-reload
systemctl --user enable --now forgespec-studio.service
systemctl --user status forgespec-studio.service
```

For public access, place a normal reverse proxy or port-forwarding layer in
front of the service and forward traffic to the configured `PORT`.

## API

- `GET /api/health`
- `POST /api/generate-config`
- `POST /api/build`
- `GET /api/files`

`/api/build` returns STL, STEP, Python source, JSON, preview SVG, manifest,
assurance report, and validation/security summaries.

Additional source-first endpoints:

- `POST /api/validate-source`
- `POST /api/build-source`
- `GET /api/jobs/{job_id}/assurance-report`

ForgeSpec Studio is a design-assist tool. Generated artifacts require
engineering review before manufacturing or operational use.

## License

MIT
