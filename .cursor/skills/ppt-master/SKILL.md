---
name: ppt-master
description: >-
  Routes AI to the ppt-master presentation pipeline: PDF/DOCX/URL/Markdown to SVG
  pages and editable PPTX (Strategist, optional Image_Generator, Executor, export).
  Use when the user asks to create a PPT, presentation, deck, slides, 生成PPT, 做PPT,
  制作演示文稿, or mentions ppt-master, SVG-to-PPTX, or this repo’s ppt-master folder.
---

# ppt-master (Cursor entry)

## Canonical source of truth

Before doing any ppt-master work in this repository, **read the full workflow** (do not improvise a shorter pipeline):

[ppt-master/skills/ppt-master/SKILL.md](ppt-master/skills/ppt-master/SKILL.md)

All step-by-step rules, blocking checkpoints, role files, and script commands are defined there.

## Path variable

In that document, `${SKILL_DIR}` means the **absolute or workspace-relative** directory:

`ppt-master/skills/ppt-master`

Use forward slashes in paths. Replace `python3` with `python` if that is what the environment provides.

## Project layout in this repo

- New presentation projects: **`ppt-master/projects/<project_name>/`** (see [ppt-master/AGENTS.md](ppt-master/AGENTS.md)).
- Standalone template authoring: [ppt-master/skills/ppt-master/workflows/create-template.md](ppt-master/skills/ppt-master/workflows/create-template.md).

## Non-negotiable reminders (see main SKILL for detail)

- Run the pipeline **serially**; respect **BLOCKING** steps (template choice, Eight Confirmations).
- **Executor Step 6**: generate SVG **page by page** in the **main agent**; no sub-agent batching of slides.
- **Post-processing**: run `total_md_split.py`, then `finalize_svg.py`, then `svg_to_pptx.py … -s final` as **three separate** successful invocations—never one bundled shell block.
- Do not export from `svg_output/`; export uses **`svg_final`** via `-s final`.

## When ppt-master is not in this workspace

If `ppt-master/skills/ppt-master/` is missing, tell the user the skill bundle is not present and stop rather than guessing script paths.
