# Diagram Detection And Placement

Use these heuristics before converting or inserting diagrams.

## Convert Existing Raster Diagrams

Convert an image when most of these are true:

- It contains many straight horizontal/vertical/diagonal edges.
- It contains repeated rectangles, diamonds, circles, lifelines, table-like boxes, or arrowheads.
- It has low photographic texture and high white/background area.
- Nearby text names a diagram type: flowchart, sequence diagram, E-R diagram, ERD, architecture, process, workflow, decision, swimlane, data model, class diagram, 时序图, 流程图, 实体关系图, 架构图, 决策图.
- The image appears near a caption such as "Figure", "图", "流程", or "架构".

Do not convert ordinary photos, UI screenshots, charts, logos, decorative icons, scanned handwritten notes, or heatmaps unless the user explicitly says they are diagrams to redraw.

## Create Diagrams From Prompt Or Context

When a user provides a prompt and location, create the requested diagram at that location.

When the prompt only says the document "needs a diagram", scan for:

- Ordered procedures with conditional branches: create a flowchart.
- Sender/receiver interactions over time: create a sequence diagram.
- Tables/entities with fields and relationships: create an E-R diagram.
- Services, queues, databases, APIs, or deployment components: create an architecture diagram.
- Business roles or departments performing steps: create a swimlane flowchart.

Insert after the most specific paragraph that introduces the process/model/interaction. If no strong location exists, insert after the section heading that contains the relevant description.

## Reconstruction Policy

- Prioritize semantic correctness and editability over pixel-level similarity.
- Preserve source captions and surrounding paragraphs.
- Replace only the target raster diagram paragraph when `placement.mode` is `image_index`.
- Keep the original file unchanged; always write to a new output path.
- Report unclear labels, missing arrow directions, ambiguous entity cardinalities, and any shapes that required approximation.
