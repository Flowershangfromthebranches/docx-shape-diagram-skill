---
name: docx-shape-diagram
description: Convert raster diagrams in Word .docx files into editable Word shapes, or create new editable shape diagrams from prompts/document context. Use when a DOCX contains or requests flowcharts, sequence diagrams, E-R diagrams, decision trees, architecture diagrams, process diagrams, box-and-arrow diagrams, swimlanes, or other line/shape diagrams that must be drawn with Word Insert Shapes instead of inserted as PNG/JPG/SVG images.
---

# DOCX Shape Diagram

Use editable Word drawing objects for diagrams in `.docx` documents. Do not satisfy diagram requests by inserting a screenshot or generated image unless the user explicitly asks for an image fallback.

## Workflow

1. **Classify the request**
   - Existing image conversion: inspect the DOCX for raster diagrams and surrounding text.
   - Prompted insertion: use the user's diagram prompt and target location.
   - Inferred insertion: when the prompt says a diagram is needed but gives no exact content, scan the document for process, data model, system interaction, or decision descriptions.

2. **Analyze the document**
   - Run:
     ```bash
     python3 scripts/docx_shape_diagram.py analyze <input.docx>
     ```
   - Treat high-scoring raster images with boxes, diamonds, arrows, lifelines, or entity tables as conversion candidates.
   - Preserve photos, screenshots, charts, logos, and decorative images unless they clearly represent a line/shape diagram.

3. **Create or refine a diagram spec**
   - Use `references/shape-spec.md` for the JSON schema.
   - Use `references/diagram-detection.md` for choosing diagram type and placement.
   - Prefer clean reconstruction over pixel-perfect tracing: readable layout, editable shapes, and correct relationships matter more than exact raster geometry.
   - Do not hand-place messy coordinates. Leave `layout.mode` as `auto` unless the user provides exact geometry. The script will standardize box sizes, deduplicate repeated connectors, and choose a layout engine.
   - For system/module structure charts, prefer the default `compact-tree` engine. It creates a human-style column tree instead of a loose force/grid drawing.
   - Mark uncertain labels, arrow directions, or relationships in the final response.

4. **Apply editable shapes**
   - Run:
     ```bash
     python3 scripts/docx_shape_diagram.py apply <input.docx> --spec <diagram.json> --out <output.docx>
     ```
   - The script writes editable VML/Word drawing shapes into the DOCX using a virtual-coordinate VML group, the same style as manually patched Word diagrams. Auto layout is the default; use `--layout manual` only for carefully measured coordinates.
   - If precise Word-native editing is required, use LibreOffice UNO or Microsoft Word automation guidance in `references/tooling.md`.

5. **Validate**
   - Run:
     ```bash
     python3 scripts/docx_shape_diagram.py validate <output.docx>
     ```
   - Confirm the output contains editable drawing shapes and that converted diagrams were not replaced by a new raster image.
   - Render with LibreOffice and inspect the page image before delivering important diagrams.

## Placement Rules

- For replacing a raster diagram, use `placement.mode: "image_index"` from the analyze report.
- For a specified prompt location, use `placement.mode: "placeholder"` with exact marker text, or `placement.mode: "paragraph_index"`.
- For inferred diagrams, insert after the paragraph or heading that introduces the process/model/interaction.
- Keep diagram width within the page text area; use compact labels and route connectors so text does not overlap lines.
- For generated diagrams, use a top-down layered structure by default. Avoid diagonal connector tangles, duplicate arrows, oversized text, and boxes that are too short for their labels.
- Keep generated diagrams page-friendly by default. Use wider canvases only when the user asks for landscape output or a wide architecture map.

## Tooling Preference

- Primary deterministic path: `scripts/docx_shape_diagram.py` with direct DOCX VML group markup and `dot`/Graphviz-assisted layout when useful.
- Preferred GUI/automation enhancement: `/Applications/LibreOffice.app/Contents/MacOS/soffice` with UNO or PDF/PNG rendering for visual inspection and shape adjustments.
- Fallback for final fidelity checks: Microsoft Word, especially when the user needs exact Word UI compatibility.

## References

- Diagram detection and placement: `references/diagram-detection.md`
- Diagram JSON schema: `references/shape-spec.md`
- LibreOffice, Word, and OOXML notes: `references/tooling.md`
