# Shape Spec Reference

Use this JSON format when creating editable DOCX diagrams with `scripts/docx_shape_diagram.py`.

## Minimal Spec

```json
{
  "placement": { "mode": "placeholder", "text": "{{DIAGRAM}}" },
  "canvas": { "width": 432, "height": 240 },
  "nodes": [
    { "id": "start", "type": "rounded_rect", "text": "Start", "x": 24, "y": 32, "width": 100, "height": 44 },
    { "id": "check", "type": "diamond", "text": "Valid?", "x": 172, "y": 28, "width": 88, "height": 64 }
  ],
  "connectors": [
    { "from": "start", "to": "check", "label": "submit", "arrow": true }
  ],
  "labels": [
    { "text": "Editable Word-shape flow", "x": 24, "y": 8, "width": 260, "height": 18 }
  ]
}
```

Coordinates are points relative to the top-left of the diagram canvas. Use 72 points per inch.

By default, `apply` ignores rough node coordinates and normalizes the diagram. Add `"layout": { "mode": "manual" }` or pass `--layout manual` only when coordinates are already carefully measured.

## Layout

Recommended generated specs should include semantic relationships first and leave layout to the script:

```json
{
  "layout": { "mode": "auto" },
  "canvas": { "width": 520 },
  "nodes": [
    { "id": "system", "type": "rect", "text": "智能停车管理系统" },
    { "id": "parking", "type": "rect", "text": "车位管理" }
  ],
  "connectors": [
    { "from": "system", "to": "parking", "arrow": true }
  ]
}
```

Auto layout engines:

- `compact-tree` (default): best for system function/module charts. It places the root at the top, first-level modules in columns, and each module's children vertically beneath it.
- `graphviz`: best for general directed graphs that fit the page. It uses local `dot` to compute a cleaner directed layout, then writes editable Word shapes.
- `grid`: deterministic fallback when Graphviz is unavailable or a very compact page width is required.
- All engines keep the canvas page-friendly by default. Set `layout.max_canvas_width` only when a wider landscape-style diagram is intentional.
- Uses consistent node widths and heights based on label length.
- Deduplicates repeated connectors.
- Routes arrows as simple vertical or orthogonal lines.

To force an engine:

```json
{ "layout": { "mode": "auto", "engine": "graphviz" } }
```

Or pass:

```bash
python3 scripts/docx_shape_diagram.py apply input.docx --spec diagram.json --out output.docx --engine compact-tree
```

Manual layout:

```json
{ "layout": { "mode": "manual" } }
```

Use manual mode only when the user provides exact coordinates or when post-processing a known good diagram.

## Placement

- `mode: "image_index"`: replace the raster image paragraph reported by `analyze`; include `image_index`.
- `mode: "placeholder"`: insert at the paragraph containing exact `text`; set `replace_text: true` to remove the marker text.
- `mode: "paragraph_index"`: insert before or after the zero-based paragraph index; set `position` to `before`, `after`, or `replace`.
- `mode: "append"`: append to the end of the document.

## Node Types

- `rect`: ordinary process, system, component, table/entity box.
- `rounded_rect`: start/end or soft process state.
- `diamond`: decision.
- `ellipse`: event, actor, or terminator when rounded rectangle is not suitable.
- `entity`: E-R entity/table; put attributes in the `fields` array.
- `lifeline`: sequence participant; script draws the header and a vertical line.

Recommended fields:

```json
{
  "id": "order",
  "type": "entity",
  "text": "Order",
  "fields": ["order_id PK", "user_id FK", "status"],
  "x": 40,
  "y": 50,
  "width": 130,
  "height": 90,
  "fill": "#FFFFFF",
  "stroke": "#1F2937"
}
```

## Connectors

Connectors can use node references or explicit points.

```json
{ "from": "a", "to": "b", "label": "yes", "arrow": true }
{ "points": [[40, 80], [120, 80], [120, 140]], "arrow": true, "dash": true }
```

For E-R diagrams, put cardinalities in `label`, `start_label`, or `end_label`. For sequence diagrams, use horizontal connectors between `lifeline` nodes and a `label` for the message.

## Quality Rules

- Use stable IDs; connectors must refer to existing node IDs.
- Prefer auto layout for newly generated diagrams.
- For system function structures, use `compact-tree`.
- For E-R diagrams with manually understood semantics, place entities and relationship diamonds deliberately or use `--layout manual`.
- Keep all nodes within the canvas when using manual layout.
- Keep labels short enough to fit their boxes.
- Prefer orthogonal or simple straight connectors. Avoid dense crossing lines and duplicate arrows.
- Do not create boxes shorter than their labels; CJK labels usually need wider boxes.
- If raster recognition is uncertain, create a clean approximate spec and report uncertainties.
