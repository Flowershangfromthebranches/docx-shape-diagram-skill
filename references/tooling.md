# Tooling Notes

## Deterministic Script Path

`scripts/docx_shape_diagram.py` reads and writes `.docx` packages directly. It inserts editable VML drawing groups with virtual coordinates, Word shape metadata, `from/to` line segments, and Word text boxes. This mirrors the hand-patched diagram approach that renders cleanly in Word/LibreOffice while avoiding raster screenshots.

Use this path first when the goal is a reliable editable diagram in a Word document.

When available, Graphviz `dot` is used for general directed layout. The script falls back to deterministic internal layout when `dot` is absent.

## LibreOffice UNO Enhancement

On this machine, LibreOffice is expected at:

```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice
```

Use LibreOffice when you need visual inspection, layout adjustment, or conversion checks:

```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to pdf --outdir /tmp <output.docx>
```

For important outputs, convert to PDF and rasterize a page PNG for visual QA. Do not trust XML validation alone; it cannot catch clipping, excessive spacing, or awkward line routing.

For deeper automation, launch a UNO listener:

```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice --headless --accept='socket,host=localhost,port=2002;urp;StarOffice.ComponentContext'
```

Then connect from LibreOffice's Python runtime if available. Prefer UNO for post-processing shape position and grouping, not for first-pass semantic reconstruction.

## Microsoft Word Fallback

Use Microsoft Word for final fidelity checks when the user specifically cares about Word UI behavior. Word can verify that objects are selectable/editable through Insert > Shapes style editing rather than images.

Recommended checks:

- Open the output `.docx`.
- Click the diagram and confirm individual shapes/connectors can be selected.
- Confirm text inside boxes is editable.
- Confirm no new PNG/JPG/SVG object replaced the target diagram.

## OOXML Validation

DOCX files are ZIP archives. Useful checks:

- `word/document.xml` contains VML or drawing shape elements.
- `word/media/*` count did not increase after a conversion.
- The converted image relationship no longer appears in the replaced paragraph when using `image_index` placement.

The validation command reports these counts:

```bash
python3 scripts/docx_shape_diagram.py validate <output.docx>
```
