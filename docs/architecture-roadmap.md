# ForgeSpec Studio Architecture Roadmap

ForgeSpec Studio should evolve from a direct prompt-to-final-JSON demo into a
source-controlled CAD generation pipeline.

## Reference Takeaways

The following open-source projects are architecture references only:

- `MrXujiang/HiCAD` demonstrates a two-stage modeling pipeline: intent analysis
  first, then deterministic code generation for specialized model families.
  HiCAD is GPL-3.0, so ForgeSpec Studio must not copy its implementation code.
- `earthtojake/text-to-cad` emphasizes STEP-first CAD, source-before-derived
  artifacts, explicit generation targets, geometry inspection, render review,
  and robot-description outputs such as URDF/SRDF/SDF.

## Target Pipeline

1. **Natural-language CAD brief**
   - Identify the main object, scope, units, coordinate convention, required
     outputs, dimensions, missing assumptions, functional features, interfaces,
     and validation targets.
   - Do not require user-facing JSON.

2. **Typed intent specification**
   - Convert the brief into a typed, narrow intent object.
   - Distinguish `single_part`, `multi_part_assembly`, `standard_part`,
     `robot_description`, and `inspection` tasks.
   - Keep standard-part mentions separate from the main object.

3. **Domain planner**
   - Select a generator family, such as `fastener`, `plate`, `shaft`,
     `flange`, `bracket`, `linkage`, `robot_arm_concept`, or `generic_assembly`.
   - Produce a part plan with named components, datums, interfaces, and
     standard part references.

4. **Deterministic generator**
   - Generate CAD from stable Python source, not directly from the LLM answer.
   - Prefer STEP as the primary artifact; STL is a secondary export.
   - For assemblies, keep part-local frames, explicit transforms, and mating
     datums in the source representation.

5. **Validation and repair loop**
   - Validate generated geometry with programmatic checks: solid count,
     bounding boxes, named parts, units, major dimensions, and assembly
     placement.
   - Reject target drift, such as replacing a requested assembly with one
     mentioned screw or bearing.
   - Repair the source or plan, then regenerate only explicit targets.

## Near-Term Implementation Tasks

1. Add a `brief.py` module that extracts a `CadBrief` from prompt text and LLM
   output.
2. Replace direct `AssemblySpec` generation with `CadBrief -> PartPlan ->
   AssemblySpec`.
3. Move standard library expansion into the planning stage instead of letting it
   override the whole prompt.
4. Add STEP export alongside STL, then treat STL as a preview/download format.
5. Add validation summaries to `/api/build`, including part count, bbox, export
   paths, and warnings.
6. Add source snapshots for generated CAD plans so later edits are reproducible.

## Non-Goals

- Do not copy GPL implementation code from HiCAD.
- Do not let the LLM directly author final manufacturing truth.
- Do not treat visual preview as validation.
- Do not silently turn broad assemblies into one catalog part.
