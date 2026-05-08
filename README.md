# DOCX Shape Diagram Skill

`docx-shape-diagram` is a Codex skill for converting raster diagrams in Word documents into editable Word shapes, and for creating new shape-based diagrams directly inside `.docx` files.

It is designed for flowcharts, sequence diagrams, E-R diagrams, decision diagrams, architecture diagrams, swimlanes, and other box/line/arrow diagrams where the final result should be editable through Word-style shapes rather than inserted as PNG/JPG/SVG images.

## What It Does

- Analyzes `.docx` files for embedded raster images and nearby text.
- Scores likely line/shape diagrams so photos and decorative images can be preserved.
- Uses a JSON shape spec for nodes, connectors, labels, and placement.
- Normalizes generated diagrams onto a clean layered grid by default.
- Writes editable Word drawing shapes into `.docx` output files.
- Supports prompt-driven insertion at placeholders, paragraph indexes, raster image positions, or the end of a document.
- Provides validation to confirm the output contains editable shapes.

## Install

```bash
git clone https://github.com/Flowershangfromthebranches/docx-shape-diagram-skill.git
mkdir -p ~/.codex/skills
cp -R docx-shape-diagram-skill ~/.codex/skills/docx-shape-diagram
```

Validate the installed skill:

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.codex/skills/docx-shape-diagram
```

## Usage

Analyze a document:

```bash
python3 scripts/docx_shape_diagram.py analyze input.docx
```

Apply an editable shape diagram from a JSON spec:

```bash
python3 scripts/docx_shape_diagram.py apply input.docx --spec diagram.json --out output.docx
```

`apply` uses auto layout by default so rough specs still produce aligned boxes, wrapped layers, and clean orthogonal connectors. Use `--layout manual` only when the JSON coordinates are already carefully designed.

Validate the output:

```bash
python3 scripts/docx_shape_diagram.py validate output.docx
```

Minimal `diagram.json`:

```json
{
  "placement": { "mode": "placeholder", "text": "{{DIAGRAM}}", "replace_text": true },
  "layout": { "mode": "auto" },
  "canvas": { "width": 432, "height": 240 },
  "nodes": [
    { "id": "start", "type": "rounded_rect", "text": "Start", "x": 24, "y": 48, "width": 100, "height": 44 },
    { "id": "decision", "type": "diamond", "text": "Valid?", "x": 172, "y": 38, "width": 88, "height": 70 },
    { "id": "end", "type": "rounded_rect", "text": "Finish", "x": 308, "y": 48, "width": 100, "height": 44 }
  ],
  "connectors": [
    { "from": "start", "to": "decision", "label": "submit", "arrow": true },
    { "from": "decision", "to": "end", "label": "yes", "arrow": true }
  ]
}
```

## Notes

The bundled script uses direct DOCX markup so it can work headlessly. LibreOffice and Microsoft Word remain useful for visual review and final fidelity checks.

---

# DOCX 可编辑形状图 Skill

`docx-shape-diagram` 是一个 Codex skill，用于把 Word 文档里的栅格图示转换成可编辑的 Word 形状，也可以根据提示词或文档上下文直接在 `.docx` 中绘制新的形状图。

它适用于流程图、时序图、E-R 图、决策图、架构图、泳道图，以及其他由方框、菱形、线条、箭头组成的图。目标结果应当能在 Word 中像“插入 > 形状”绘制的对象一样编辑，而不是插入一张 PNG/JPG/SVG 图片。

## 主要能力

- 分析 `.docx` 中的嵌入图片和上下文文字。
- 识别更像线框图/流程图的栅格图片，避免误处理照片、装饰图和普通截图。
- 使用 JSON 规格描述节点、连接线、标签和插入位置。
- 默认把生成的图自动规整到分层网格，避免节点歪斜、连线混乱和文字溢出。
- 将图写回为可编辑的 Word 绘图形状。
- 支持按占位符、段落索引、图片索引或文档末尾插入。
- 提供验证命令，确认输出文档中包含可编辑绘图形状。

## 安装

```bash
git clone https://github.com/Flowershangfromthebranches/docx-shape-diagram-skill.git
mkdir -p ~/.codex/skills
cp -R docx-shape-diagram-skill ~/.codex/skills/docx-shape-diagram
```

验证安装：

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.codex/skills/docx-shape-diagram
```

## 使用

分析文档：

```bash
python3 scripts/docx_shape_diagram.py analyze input.docx
```

根据 JSON 规格写入可编辑形状图：

```bash
python3 scripts/docx_shape_diagram.py apply input.docx --spec diagram.json --out output.docx
```

`apply` 默认启用自动布局，即使 JSON 里坐标比较粗糙，也会尽量输出对齐的方框、自动换行的层级和规整的折线箭头。只有坐标已经精心设计时才使用 `--layout manual`。

验证输出：

```bash
python3 scripts/docx_shape_diagram.py validate output.docx
```

更多规格说明见 `references/shape-spec.md`。图像识别和自动插入策略见 `references/diagram-detection.md`。LibreOffice、Word 和 OOXML 检查说明见 `references/tooling.md`。
