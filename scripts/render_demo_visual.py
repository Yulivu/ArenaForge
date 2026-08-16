"""Render public product-site visuals from the checked-in exploration artifacts."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "examples" / "quantum_optics_open_exploration" / "artifacts"
OUTPUT = ROOT / "web" / "public" / "assets"
WIDTH, HEIGHT = 1440, 900


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size=size)


def rounded_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: str, outline: str) -> None:
    draw.rounded_rectangle(xy, radius=20, fill=fill, outline=outline, width=2)


def render_campaign(snapshot: dict) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#f5f5f7")
    draw = ImageDraw.Draw(image)
    ink, muted, line, forge = "#171717", "#6e6e73", "#d2d2d7", "#007a5a"

    draw.text((80, 72), "ARENAFORGE STUDY", font=font(24, True), fill=forge)
    draw.text((80, 118), "Research input becomes an executable campaign.", font=font(44, True), fill=ink)
    draw.text((80, 182), "One real exploration replay, rendered from checked-in artifacts.", font=font(22), fill=muted)

    boxes = [(80, 310, 410, 690), (555, 250, 900, 750), (1045, 310, 1360, 690)]
    rounded_box(draw, boxes[0], "#ffffff", line)
    rounded_box(draw, boxes[1], "#171717", "#171717")
    rounded_box(draw, boxes[2], "#ffffff", line)

    draw.text((118, 350), "RESEARCH INPUT", font=font(19, True), fill=forge)
    draw.text((118, 405), "Question", font=font(26, True), fill=ink)
    draw.text((118, 448), "Constraints", font=font(26, True), fill=ink)
    draw.text((118, 491), "Evaluation rule", font=font(26, True), fill=ink)
    draw.line((118, 548, 370, 548), fill=line, width=2)
    draw.text((118, 577), "Project or simulator", font=font(18), fill=muted)

    draw.text((595, 292), "EXPLORATION", font=font(19, True), fill="#6fd1b4")
    draw.text((595, 338), f"{snapshot['candidate_count']} candidates compared", font=font(30, True), fill="#ffffff")
    draw.text((595, 385), f"{snapshot['screened_edge_count']} marginal tests", font=font(22), fill="#c9c9cd")
    draw.text((595, 420), f"{snapshot['accepted_action_count']} accepted actions", font=font(22), fill="#c9c9cd")

    center = (728, 603)
    dot_count = snapshot["candidate_count"]
    for index in range(dot_count):
        angle = (math.tau * index / dot_count) - math.pi / 2
        x = center[0] + int(math.cos(angle) * 118)
        y = center[1] + int(math.sin(angle) * 90)
        draw.line((center[0], center[1], x, y), fill="#4d8f7b", width=2)
        draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill="#6fd1b4")
    draw.ellipse((center[0] - 29, center[1] - 29, center[0] + 29, center[1] + 29), fill="#ffffff")
    draw.text((center[0] - 15, center[1] - 14), "49", font=font(22, True), fill=ink)

    draw.text((1082, 350), "RESULT PACKAGE", font=font(19, True), fill=forge)
    draw.text((1082, 407), "49 edges", font=font(42, True), fill=ink)
    draw.text((1082, 465), "recommended result", font=font(20), fill=muted)
    draw.line((1082, 525, 1318, 525), fill=line, width=2)
    draw.text((1082, 555), "logs", font=font(18), fill=ink)
    draw.text((1082, 589), "evidence", font=font(18), fill=ink)
    draw.text((1082, 623), "reproduction bundle", font=font(18), fill=ink)

    draw.line((410, 500, 555, 500), fill=forge, width=5)
    draw.polygon([(555, 500), (536, 488), (536, 512)], fill=forge)
    draw.line((900, 500, 1045, 500), fill=forge, width=5)
    draw.polygon([(1045, 500), (1026, 488), (1026, 512)], fill=forge)
    image.save(OUTPUT / "study-campaign.png")


def render_quantum_graph(snapshot: dict) -> None:
    candidate = json.loads((ARTIFACTS / "sensitivity_guided_025.json").read_text(encoding="utf-8"))
    graph = candidate["graph"]
    image = Image.new("RGB", (WIDTH, HEIGHT), "#101415")
    draw = ImageDraw.Draw(image)
    positions = {
        0: (245, 345),
        1: (500, 265),
        2: (765, 335),
        3: (350, 700),
        4: (680, 760),
        5: (1040, 610),
    }
    labels = {0: "S0", 1: "S1", 2: "S2", 3: "S3", 4: "S4", 5: "S5"}
    draw.text((80, 70), "QUANTUM OPTICS VALIDATION CASE", font=font(23, True), fill="#6fd1b4")
    draw.text((80, 116), "Candidate topology after guided pruning", font=font(44, True), fill="#ffffff")
    draw.text((80, 178), "Each visible connection is derived from the recommended artifact.", font=font(21), fill="#b7c0bd")

    for encoded, weight in graph.items():
        start, end, _, _ = (int(part.strip()) for part in encoded.strip("()").split(","))
        x1, y1 = positions[start]
        x2, y2 = positions[end]
        magnitude = max(1, int(abs(weight) * 5))
        color = "#5ed2b0" if weight > 0 else "#7598cf"
        draw.line((x1, y1, x2, y2), fill=color, width=magnitude)

    for node, (x, y) in positions.items():
        draw.ellipse((x - 40, y - 40, x + 40, y + 40), fill="#f5f5f7", outline="#ffffff", width=3)
        draw.text((x - 17, y - 14), labels[node], font=font(20, True), fill="#171717")

    rounded_box(draw, (1030, 650, 1350, 800), "#f5f5f7", "#f5f5f7")
    draw.text((1065, 686), f"{snapshot['recommended_edges']} EDGES", font=font(30, True), fill="#171717")
    draw.text((1065, 732), "quality gate retained", font=font(18), fill="#6e6e73")
    image.save(OUTPUT / "quantum-optics-case.png")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / "web" / "public" / "reference-data.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    render_campaign(snapshot)
    render_quantum_graph(snapshot)
    print(f"wrote {OUTPUT.relative_to(ROOT) / 'study-campaign.png'}")
    print(f"wrote {OUTPUT.relative_to(ROOT) / 'quantum-optics-case.png'}")


if __name__ == "__main__":
    main()
