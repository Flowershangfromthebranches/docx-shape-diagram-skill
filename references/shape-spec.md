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
- Keep all nodes within the canvas.
- Keep labels short enough to fit their boxes.
- Prefer orthogonal or simple straight connectors. Avoid dense crossing lines.
- If raster recognition is uncertain, create a clean approximate spec and report uncertainties.
