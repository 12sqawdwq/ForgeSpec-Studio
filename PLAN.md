# ForgeSpec Studio Industrial Iteration Plan

ForgeSpec Studio is evolving from a natural-language-to-CAD-JSON prototype into
a continuously tested CAD generation platform.

Core route:

```text
natural language -> CAD brief -> typed intent -> part plan -> deterministic generator
-> STEP/STL/JSON/URDF export -> validation -> repair loop -> regression corpus
```

## Principles

- Do not patch individual prompts with one-off templates.
- Do not let LLM output become final manufacturing geometry without validation.
- Do not treat visual preview as validation.
- Keep standard parts, assemblies, robot mechanisms, and ordinary parts on
  separate auditable paths.
- Every capability improvement must add or update tests and regression prompts.

## Stages

### Stage 0: Stabilize Current MVP

Entry: current FastAPI/CadQuery service runs and exports STL/JSON.

Completion:
- API health, config generation, build, and file listing pass smoke tests.
- `.env`, outputs, caches, and local reference repos stay out of git.
- README and deployment docs avoid keys, public IPs, and personal paths.

### Stage 1: Brief + Intent Layer

Completion:
- `brief.py` extracts main object, components, outputs, dimensions, standard
  mentions, and assumptions.
- `intent.py` classifies requests into standard part, single part, multi-part
  assembly, robot description, or inspection/modification.
- LLM output is treated as a candidate, not as final truth.
- Target drift checks reject broad assemblies that collapse into one hardware
  item.

### Stage 2: Part Plan Layer

Completion:
- `planner.py` converts brief + intent into a deterministic part plan.
- Standard part expansion happens inside planning and cannot override the main
  object.
- Plans include main object, components, interfaces, assumptions, source, and
  warnings.

### Stage 3: STEP-first Export

Completion:
- STEP export exists alongside STL.
- STL remains a secondary preview/download artifact.
- `/api/build` returns export paths and validation summary.
- Build outputs include source plan snapshots for reproducibility.

### Stage 4: Geometry Validation

Completion:
- `validation.py` reports bbox, solid count, part count, standard references,
  alignment status, warnings, and export status.
- Build errors return actionable repair reasons.
- Failed prompts/specs are saved into regression records.

### Stage 5: Standard Part Database

Completion:
- `standards/` covers fasteners, nuts, washers, dowel pins, bearings, keys, and
  circlips.
- Each family has parameter tables, default selection rules, deterministic
  generators, and regression tests.

### Stage 6: Assembly + Robot Capability

Completion:
- Assembly plans support links, joints, mates, frames, and optional URDF export.
- Robot prompts produce concept CAD plus structured link/joint data.
- The system does not claim production readiness without loads, motors,
  reducers, bearings, fits, and material constraints.

### Stage 7: Self-Improving Regression Loop

Completion:
- Every user-reported failure is classified, stored, tested, fixed, and rerun.
- Opposite examples are tested as well, such as:
  - A standard screw prompt should generate a screw.
  - An assembly mentioning screws should not become only screws.

## Failure Classes

- intent drift
- schema too narrow
- standard part hijack
- generator limitation
- CAD build failure
- frontend preview mismatch
- export failure
- network/provider failure

## Iteration Checklist

Before each commit:

```bash
python -m py_compile app.py cad_engine.py llm.py preview.py schemas.py standard_library.py templates.py alignment.py brief.py intent.py planner.py validation.py
pytest
```

Before deployment:

```bash
curl http://127.0.0.1:$PORT/api/health
```

Public verification:

- `/api/health`
- `/api/generate-config`
- `/api/build`
- frontend serves the new JS
- `.env` is still ignored

