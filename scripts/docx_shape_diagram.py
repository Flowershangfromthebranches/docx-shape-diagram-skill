#!/usr/bin/env python3
"""Analyze DOCX raster diagrams and insert editable Word/VML shape diagrams."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from lxml import etree

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover - optional runtime dependency
    cv2 = None
    np = None


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
}


def qn(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


@dataclass
class ParagraphInfo:
    index: int
    element: etree._Element
    text: str
    embed_ids: list[str]


def load_xml_from_docx(docx_path: Path, member: str) -> etree._Element:
    with zipfile.ZipFile(docx_path) as zf:
        return etree.fromstring(zf.read(member))


def paragraph_text(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS)).strip()


def paragraph_embed_ids(paragraph: etree._Element) -> list[str]:
    ids = paragraph.xpath(".//a:blip/@r:embed", namespaces=NS)
    ids.extend(paragraph.xpath(".//v:imagedata/@r:id", namespaces=NS))
    return list(dict.fromkeys(ids))


def document_paragraphs(root: etree._Element) -> list[ParagraphInfo]:
    paragraphs = root.xpath(".//w:body/w:p", namespaces=NS)
    return [
        ParagraphInfo(i, p, paragraph_text(p), paragraph_embed_ids(p))
        for i, p in enumerate(paragraphs)
    ]


def relationship_targets(docx_path: Path) -> dict[str, str]:
    rels_path = "word/_rels/document.xml.rels"
    with zipfile.ZipFile(docx_path) as zf:
        if rels_path not in zf.namelist():
            return {}
        rels = etree.fromstring(zf.read(rels_path))
    return {
        rel.get("Id"): rel.get("Target")
        for rel in rels
        if rel.get("Id") and rel.get("Target")
    }


def media_bytes(docx_path: Path, target: str) -> bytes | None:
    if target.startswith("/"):
        member = target.lstrip("/")
    else:
        member = f"word/{target}"
    with zipfile.ZipFile(docx_path) as zf:
        if member not in zf.namelist():
            return None
        return zf.read(member)


def score_diagram_like(blob: bytes) -> dict[str, Any]:
    if cv2 is None or np is None:
        return {"score": None, "reason": "cv2/numpy unavailable"}
    arr = np.frombuffer(blob, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"score": 0.0, "reason": "image decode failed"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    if height == 0 or width == 0:
        return {"score": 0.0, "reason": "empty image"}

    edges = cv2.Canny(gray, 60, 180)
    edge_density = float(np.count_nonzero(edges) / edges.size)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=max(24, min(width, height) // 8),
        minLineLength=max(18, min(width, height) // 12),
        maxLineGap=8,
    )
    line_count = 0 if lines is None else len(lines)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rect_like = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 80:
            continue
        approx = cv2.approxPolyDP(contour, 0.035 * cv2.arcLength(contour, True), True)
        if 4 <= len(approx) <= 8:
            rect_like += 1
    white_ratio = float(np.count_nonzero(gray > 245) / gray.size)
    color_std = float(np.mean(np.std(img, axis=(0, 1))))

    score = 0.0
    score += min(line_count / 30.0, 0.35)
    score += min(rect_like / 12.0, 0.30)
    score += 0.20 if 0.01 <= edge_density <= 0.18 else 0.05
    score += 0.10 if white_ratio > 0.30 else 0.0
    score += 0.05 if color_std < 75 else 0.0
    score = round(min(score, 1.0), 3)

    return {
        "score": score,
        "line_count": line_count,
        "shape_like_contours": rect_like,
        "edge_density": round(edge_density, 4),
        "white_ratio": round(white_ratio, 4),
        "color_std": round(color_std, 2),
    }


def analyze_docx(args: argparse.Namespace) -> int:
    docx_path = Path(args.input_docx)
    root = load_xml_from_docx(docx_path, "word/document.xml")
    paragraphs = document_paragraphs(root)
    rels = relationship_targets(docx_path)
    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    images: list[dict[str, Any]] = []
    image_index = 0
    for para in paragraphs:
        for embed_id in para.embed_ids:
            target = rels.get(embed_id)
            if not target:
                continue
            blob = media_bytes(docx_path, target)
            if blob is None:
                continue
            suffix = Path(target).suffix or ".bin"
            extracted = None
            if out_dir:
                extracted_path = out_dir / f"image_{image_index:03d}{suffix}"
                extracted_path.write_bytes(blob)
                extracted = str(extracted_path)
            score = score_diagram_like(blob)
            prev_text = paragraphs[para.index - 1].text if para.index > 0 else ""
            next_text = (
                paragraphs[para.index + 1].text
                if para.index + 1 < len(paragraphs)
                else ""
            )
            images.append(
                {
                    "image_index": image_index,
                    "relationship_id": embed_id,
                    "target": target,
                    "paragraph_index": para.index,
                    "context": {
                        "previous": prev_text,
                        "current": para.text,
                        "next": next_text,
                    },
                    "diagram_like": score,
                    "suggested_placement": {
                        "mode": "image_index",
                        "image_index": image_index,
                    },
                    "extracted_path": extracted,
                }
            )
            image_index += 1

    report = {
        "input": str(docx_path),
        "paragraph_count": len(paragraphs),
        "image_count": len(images),
        "libreoffice": shutil.which("soffice")
        or (
            "/Applications/LibreOffice.app/Contents/MacOS/soffice"
            if Path("/Applications/LibreOffice.app/Contents/MacOS/soffice").exists()
            else None
        ),
        "images": images,
    }
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def pt(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def color(value: Any, default: str) -> str:
    if isinstance(value, str) and value.startswith("#") and len(value) in {4, 7}:
        return value
    return default


def text_units(text: str) -> int:
    """Approximate display width; CJK characters need more room than ASCII."""
    total = 0
    for char in text:
        total += 2 if ord(char) > 127 else 1
    return total


def node_lines(node: dict[str, Any]) -> list[str]:
    lines = [str(node.get("text", "")).strip()]
    lines.extend(str(field).strip() for field in node.get("fields") or [])
    return [line for line in lines if line]


def default_node_size(node: dict[str, Any], min_width: float, max_width: float) -> tuple[float, float]:
    lines = node_lines(node)
    widest = max((text_units(line) for line in lines), default=8)
    width = min(max(min_width, widest * 6.2 + 28), max_width)
    height = 46 + max(0, len(lines) - 1) * 16
    if str(node.get("type", "")).lower() == "diamond":
        width = max(width, 78)
        height = max(height, 64)
    return width, height


def assign_graph_layers(
    nodes: list[dict[str, Any]], connectors: list[dict[str, Any]]
) -> dict[str, int]:
    node_ids = [str(node.get("id")) for node in nodes if node.get("id")]
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for connector in connectors:
        src = str(connector.get("from", ""))
        dst = str(connector.get("to", ""))
        if src in outgoing and dst in incoming:
            outgoing[src].append(dst)
            incoming[dst] += 1

    queue = [node_id for node_id in node_ids if incoming[node_id] == 0] or node_ids[:1]
    layers = {node_id: 0 for node_id in node_ids}
    seen = set(queue)
    while queue:
        src = queue.pop(0)
        for dst in outgoing.get(src, []):
            layers[dst] = max(layers.get(dst, 0), layers[src] + 1)
            incoming[dst] -= 1
            if incoming[dst] <= 0 and dst not in seen:
                queue.append(dst)
                seen.add(dst)

    # Cycles and disconnected nodes get stable layers after their predecessors.
    fallback_layer = max(layers.values(), default=0)
    for node_id in node_ids:
        if node_id not in seen:
            fallback_layer += 1
            layers[node_id] = fallback_layer
    return layers


def dedupe_connectors(connectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for connector in connectors:
        if connector.get("points"):
            key = ("points", json.dumps(connector.get("points"), sort_keys=True), str(connector.get("label", "")), "")
        else:
            key = (
                str(connector.get("from", "")),
                str(connector.get("to", "")),
                str(connector.get("label", "")),
                str(connector.get("type", "")),
            )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(connector)
    return deduped


def chunk_layer(
    row_nodes: list[dict[str, Any]], available_width: float, h_gap: float
) -> list[list[dict[str, Any]]]:
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_width = 0.0
    for node in row_nodes:
        node_width = pt(node.get("width"), 118)
        added_width = node_width if not current else node_width + h_gap
        if current and current_width + added_width > available_width:
            chunks.append(current)
            current = [node]
            current_width = node_width
        else:
            current.append(node)
            current_width += added_width
    if current:
        chunks.append(current)
    return chunks


def normalize_spec(spec: dict[str, Any], layout_override: str | None = None) -> dict[str, Any]:
    normalized = deepcopy(spec)
    nodes = normalized.get("nodes") or []
    connectors = dedupe_connectors(normalized.get("connectors") or [])
    normalized["connectors"] = connectors

    layout = normalized.get("layout") or {}
    mode = layout_override or str(layout.get("mode", "auto"))
    if mode == "manual":
        return normalized

    margin_x = pt(layout.get("margin_x"), 28)
    margin_y = pt(layout.get("margin_y"), 28)
    h_gap = pt(layout.get("h_gap"), 40)
    v_gap = pt(layout.get("v_gap"), 58)
    min_width = pt(layout.get("min_node_width"), 118)
    max_width = pt(layout.get("max_node_width"), 168)
    canvas = normalized.setdefault("canvas", {})
    max_canvas_width = pt(layout.get("max_canvas_width"), 500)
    requested_width = pt(canvas.get("width"), pt(layout.get("canvas_width"), max_canvas_width))
    canvas_width = min(max(432, requested_width), max_canvas_width)
    available_width = max(canvas_width - margin_x * 2, min_width)

    for node in nodes:
        width, height = default_node_size(node, min_width, max_width)
        node["width"] = pt(node.get("width"), width)
        node["height"] = pt(node.get("height"), height)

    layers = assign_graph_layers(nodes, connectors)
    rows: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        rows.setdefault(layers.get(str(node.get("id")), 0), []).append(node)

    visual_rows: list[list[dict[str, Any]]] = []
    for layer in sorted(rows):
        row_nodes = rows[layer]
        chunks = chunk_layer(row_nodes, available_width, h_gap)
        if not chunks and row_nodes:
            chunks = [row_nodes]
        rows[layer] = row_nodes
        for chunk in chunks:
            visual_rows.append(chunk)

    y = margin_y
    for row_nodes in visual_rows:
        row_width = sum(pt(n.get("width"), min_width) for n in row_nodes)
        row_width += h_gap * max(0, len(row_nodes) - 1)
        row_height = max((pt(n.get("height"), 46) for n in row_nodes), default=46)
        x = margin_x + max(0, (canvas_width - margin_x * 2 - row_width) / 2)
        for node in row_nodes:
            node["x"] = round(x, 2)
            node["y"] = round(y + (row_height - pt(node.get("height"), 46)) / 2, 2)
            x += pt(node.get("width"), min_width) + h_gap
        y += row_height + v_gap

    canvas["width"] = round(canvas_width, 2)
    canvas["height"] = round(max(pt(canvas.get("height"), 0), y - v_gap + margin_y), 2)
    route_connectors(normalized)
    return normalized


def node_center(node: dict[str, Any]) -> tuple[float, float]:
    return (
        pt(node.get("x")) + pt(node.get("width"), 80) / 2,
        pt(node.get("y")) + pt(node.get("height"), 40) / 2,
    )


def edge_point(source: dict[str, Any], target: dict[str, Any]) -> tuple[float, float]:
    sx, sy = node_center(source)
    tx, ty = node_center(target)
    dx = tx - sx
    dy = ty - sy
    half_w = max(pt(source.get("width"), 80) / 2, 1)
    half_h = max(pt(source.get("height"), 40) / 2, 1)
    if dx == 0 and dy == 0:
        return sx, sy
    scale = min(abs(half_w / dx) if dx else math.inf, abs(half_h / dy) if dy else math.inf)
    return sx + dx * scale, sy + dy * scale


def style_position(x: float, y: float, width: float, height: float) -> str:
    return (
        f"position:absolute;left:{x:.2f}pt;top:{y:.2f}pt;"
        f"width:{width:.2f}pt;height:{height:.2f}pt"
    )


def text_box(text: str, font_size: int = 10, bold: bool = False) -> str:
    raw_lines = str(text or "").splitlines() or [""]
    lines = [escape(line) for line in raw_lines]
    run_props = f'<w:rPr><w:sz w:val="{font_size * 2}"/><w:szCs w:val="{font_size * 2}"/>'
    if bold:
        run_props += "<w:b/><w:bCs/>"
    run_props += "</w:rPr>"
    paragraphs = "".join(
        "<w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr>"
        f"<w:r>{run_props}<w:t>{line}</w:t></w:r></w:p>"
        for line in lines
    )
    return (
        '<v:textbox inset="6pt,3pt,6pt,3pt" style="mso-fit-shape-to-text:false">'
        f"<w:txbxContent>{paragraphs}</w:txbxContent></v:textbox>"
    )


def render_node(node: dict[str, Any]) -> str:
    node_id = escape(str(node.get("id", "node")))
    x = pt(node.get("x"))
    y = pt(node.get("y"))
    width = pt(node.get("width"), 100)
    height = pt(node.get("height"), 44)
    fill = color(node.get("fill"), "#FFFFFF")
    stroke = color(node.get("stroke"), "#1F2937")
    text = str(node.get("text", ""))
    fields = node.get("fields") or []
    if fields:
        text = text + "\n" + "\n".join(str(f) for f in fields)
    shape_type = str(node.get("type", "rect")).lower()
    font_size = int(pt(node.get("font_size"), 10))
    bold = bool(node.get("bold", False))
    common = (
        f'id="{node_id}" style="{style_position(x, y, width, height)}" '
        f'fillcolor="{fill}" strokecolor="{stroke}" strokeweight="1pt"'
    )
    if shape_type == "rounded_rect":
        return f"<v:roundrect {common} arcsize=\"16%\">{text_box(text, font_size, bold)}</v:roundrect>"
    if shape_type == "ellipse":
        return f"<v:oval {common}>{text_box(text, font_size, bold)}</v:oval>"
    if shape_type == "diamond":
        return (
            f'<v:shape {common} coordsize="21600,21600" '
            'path="m,10800 l10800,21600,21600,10800,10800, xe">'
            f"{text_box(text, font_size, bold)}</v:shape>"
        )
    if shape_type == "lifeline":
        cx = x + width / 2
        bottom = pt(node.get("line_bottom"), y + height + 130)
        header = f"<v:rect {common}>{text_box(text, font_size, bold)}</v:rect>"
        line = (
            f'<v:line from="{cx:.2f}pt,{(y + height):.2f}pt" '
            f'to="{cx:.2f}pt,{bottom:.2f}pt" strokecolor="{stroke}" '
            'strokeweight="1pt"><v:stroke dashstyle="dash"/></v:line>'
        )
        return header + line
    return f"<v:rect {common}>{text_box(text, font_size, bold)}</v:rect>"


def route_connectors(spec: dict[str, Any]) -> None:
    nodes = spec.get("nodes") or []
    nodes_by_id = {str(n.get("id")): n for n in nodes if n.get("id")}
    for connector in spec.get("connectors") or []:
        if connector.get("points"):
            continue
        from_node = nodes_by_id.get(str(connector.get("from")))
        to_node = nodes_by_id.get(str(connector.get("to")))
        if not from_node or not to_node:
            continue
        sx, sy = node_center(from_node)
        tx, ty = node_center(to_node)
        if abs(tx - sx) < 4:
            start = (sx, pt(from_node.get("y")) + pt(from_node.get("height"), 46))
            end = (tx, pt(to_node.get("y")))
            connector["points"] = [[round(start[0], 2), round(start[1], 2)], [round(end[0], 2), round(end[1], 2)]]
        elif ty > sy:
            start = (sx, pt(from_node.get("y")) + pt(from_node.get("height"), 46))
            end = (tx, pt(to_node.get("y")))
            mid_y = round((start[1] + end[1]) / 2, 2)
            connector["points"] = [
                [round(start[0], 2), round(start[1], 2)],
                [round(start[0], 2), mid_y],
                [round(end[0], 2), mid_y],
                [round(end[0], 2), round(end[1], 2)],
            ]
        else:
            start = edge_point(from_node, to_node)
            end = edge_point(to_node, from_node)
            connector["points"] = [[round(start[0], 2), round(start[1], 2)], [round(end[0], 2), round(end[1], 2)]]


def render_connector(connector: dict[str, Any], nodes_by_id: dict[str, dict[str, Any]]) -> str:
    points = connector.get("points")
    if points:
        parsed = [(pt(p[0]), pt(p[1])) for p in points if isinstance(p, list) and len(p) >= 2]
        if len(parsed) < 2:
            return ""
        start = parsed[0]
        end = parsed[-1]
    else:
        from_node = nodes_by_id.get(str(connector.get("from")))
        to_node = nodes_by_id.get(str(connector.get("to")))
        if not from_node or not to_node:
            return ""
        start = edge_point(from_node, to_node)
        end = edge_point(to_node, from_node)

    stroke = color(connector.get("stroke"), "#1F2937")
    dash = " dashstyle=\"dash\"" if connector.get("dash") else ""
    if points and len(parsed) > 2:
        segments = []
        for idx, (seg_start, seg_end) in enumerate(zip(parsed, parsed[1:])):
            arrow = " endarrow=\"block\"" if idx == len(parsed) - 2 and connector.get("arrow", True) else ""
            segments.append(
                f'<v:line from="{seg_start[0]:.2f}pt,{seg_start[1]:.2f}pt" '
                f'to="{seg_end[0]:.2f}pt,{seg_end[1]:.2f}pt" strokecolor="{stroke}" '
                f'strokeweight="1pt"><v:stroke{arrow}{dash}/></v:line>'
            )
        line = "".join(segments)
    else:
        arrow = " endarrow=\"block\"" if connector.get("arrow", True) else ""
        line = (
            f'<v:line from="{start[0]:.2f}pt,{start[1]:.2f}pt" '
            f'to="{end[0]:.2f}pt,{end[1]:.2f}pt" strokecolor="{stroke}" '
            f'strokeweight="1pt"><v:stroke{arrow}{dash}/></v:line>'
        )
    label = str(connector.get("label", "")).strip()
    if label:
        mx = (start[0] + end[0]) / 2 - 28
        my = (start[1] + end[1]) / 2 - 10
        line += render_label({"text": label, "x": mx, "y": my, "width": 56, "height": 18})
    return line


def render_label(label: dict[str, Any]) -> str:
    x = pt(label.get("x"))
    y = pt(label.get("y"))
    width = pt(label.get("width"), 120)
    height = pt(label.get("height"), 22)
    text = str(label.get("text", ""))
    return (
        f'<v:shape style="{style_position(x, y, width, height)}" '
        'filled="false" stroked="false">'
        f"{text_box(text, 9)}</v:shape>"
    )


def render_diagram_paragraph(spec: dict[str, Any]) -> etree._Element:
    canvas = spec.get("canvas") or {}
    width = pt(canvas.get("width"), 432)
    height = pt(canvas.get("height"), 240)
    nodes = spec.get("nodes") or []
    nodes_by_id = {str(n.get("id")): n for n in nodes if n.get("id")}
    labels = "".join(render_label(label) for label in spec.get("labels", []) or [])
    rendered_connectors = "".join(
        render_connector(connector, nodes_by_id)
        for connector in spec.get("connectors", []) or []
    )
    rendered_nodes = "".join(render_node(node) for node in nodes)
    group = (
        f'<w:p xmlns:w="{NS["w"]}" xmlns:v="{NS["v"]}" xmlns:o="{NS["o"]}">'
        "<w:r><w:pict>"
        f'<v:group id="docx_shape_diagram" '
        f'style="width:{width:.2f}pt;height:{height:.2f}pt;position:relative" '
        f'coordsize="{int(width)},{int(height)}">'
        f"{rendered_connectors}{rendered_nodes}{labels}"
        "</v:group></w:pict></w:r></w:p>"
    )
    return etree.fromstring(group.encode("utf-8"))


def clear_placeholder_text(paragraph: etree._Element, marker: str) -> None:
    for text_node in paragraph.xpath(".//w:t", namespaces=NS):
        if text_node.text and marker in text_node.text:
            text_node.text = text_node.text.replace(marker, "")


def insert_or_replace(root: etree._Element, diagram_p: etree._Element, spec: dict[str, Any]) -> None:
    paragraphs = document_paragraphs(root)
    placement = spec.get("placement") or {"mode": "append"}
    mode = str(placement.get("mode", "append"))
    body = root.find(".//w:body", namespaces=NS)
    if body is None:
        raise ValueError("word/document.xml has no body")

    target: etree._Element | None = None
    position = str(placement.get("position", "after"))

    if mode == "image_index":
        wanted = int(placement.get("image_index", 0))
        seen = 0
        for para in paragraphs:
            if para.embed_ids:
                if seen == wanted:
                    target = para.element
                    position = "replace"
                    break
                seen += len(para.embed_ids)
    elif mode == "placeholder":
        marker = str(placement.get("text", ""))
        for para in paragraphs:
            if marker and marker in para.text:
                target = para.element
                if placement.get("replace_text", False):
                    clear_placeholder_text(target, marker)
                break
    elif mode == "paragraph_index":
        idx = int(placement.get("paragraph_index", -1))
        if 0 <= idx < len(paragraphs):
            target = paragraphs[idx].element
            position = str(placement.get("position", "after"))
    elif mode == "append":
        target = None
    else:
        raise ValueError(f"unsupported placement mode: {mode}")

    if target is None:
        sect_pr = body.find("w:sectPr", namespaces=NS)
        if sect_pr is not None:
            body.insert(body.index(sect_pr), diagram_p)
        else:
            body.append(diagram_p)
        return

    parent = target.getparent()
    if parent is None:
        raise ValueError("target paragraph has no parent")
    idx = parent.index(target)
    if position == "before":
        parent.insert(idx, diagram_p)
    elif position == "replace":
        parent[idx] = diagram_p
    else:
        parent.insert(idx + 1, diagram_p)


def apply_spec(args: argparse.Namespace) -> int:
    input_path = Path(args.input_docx)
    output_path = Path(args.out)
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    spec = normalize_spec(spec, args.layout)
    if args.dump_normalized_spec:
        Path(args.dump_normalized_spec).write_text(
            json.dumps(spec, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    root = load_xml_from_docx(input_path, "word/document.xml")
    diagram_p = render_diagram_paragraph(spec)
    insert_or_replace(root, diagram_p, spec)
    xml_bytes = etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone="yes",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "work.docx"
        with zipfile.ZipFile(input_path) as zin:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = xml_bytes if item.filename == "word/document.xml" else zin.read(item.filename)
                    zout.writestr(item, data)
        shutil.copyfile(tmp_path, output_path)

    print(json.dumps({"output": str(output_path), "status": "ok"}, ensure_ascii=False))
    return 0


def validate_docx(args: argparse.Namespace) -> int:
    docx_path = Path(args.input_docx)
    with zipfile.ZipFile(docx_path) as zf:
        names = zf.namelist()
        document = etree.fromstring(zf.read("word/document.xml"))
        media = [name for name in names if name.startswith("word/media/")]
    vml_shapes = document.xpath("count(.//v:shape | .//v:rect | .//v:roundrect | .//v:oval | .//v:line | .//v:polyline | .//v:group)", namespaces=NS)
    drawing_images = document.xpath("count(.//a:blip | .//v:imagedata)", namespaces=NS)
    report = {
        "input": str(docx_path),
        "editable_shape_count": int(vml_shapes),
        "referenced_image_count": int(drawing_images),
        "media_file_count": len(media),
        "has_editable_shapes": bool(vml_shapes),
    }
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if vml_shapes else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze images and context in a DOCX")
    analyze.add_argument("input_docx")
    analyze.add_argument("--out-dir", help="Optional directory for extracted images")
    analyze.set_defaults(func=analyze_docx)

    apply = sub.add_parser("apply", help="Insert editable shape diagram from JSON spec")
    apply.add_argument("input_docx")
    apply.add_argument("--spec", required=True)
    apply.add_argument("--out", required=True)
    apply.add_argument(
        "--layout",
        choices=["auto", "manual"],
        default=None,
        help="Default auto normalizes nodes onto a clean layered grid; manual preserves coordinates",
    )
    apply.add_argument("--dump-normalized-spec", help="Write the normalized spec used for rendering")
    apply.set_defaults(func=apply_spec)

    validate = sub.add_parser("validate", help="Validate editable shape presence in a DOCX")
    validate.add_argument("input_docx")
    validate.set_defaults(func=validate_docx)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
