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


def chinese_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "msyhbd.ttc" if bold else "msyh.ttc"
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


def render_candidate_landscape(snapshot: dict) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#f5f5f7")
    draw = ImageDraw.Draw(image)
    ink, muted, line, forge, red = "#171717", "#6e6e73", "#d2d2d7", "#007a5a", "#b42318"
    left, top, right, bottom = 155, 245, 1310, 730
    min_edges, max_edges = 47, 75
    max_drop = 0.032

    def x(value: float) -> int:
        return int(left + (value - min_edges) / (max_edges - min_edges) * (right - left))

    def y(value: float) -> int:
        return int(bottom - min(value, max_drop) / max_drop * (bottom - top))

    draw.text((80, 70), "候选空间", font=chinese_font(23, True), fill=forge)
    draw.text((80, 116), "预算和质量门槛共同决定候选是否保留。", font=chinese_font(43, True), fill=ink)
    draw.text((80, 178), "每个点对应一次记录在案的候选评估。", font=chinese_font(20), fill=muted)
    legend_x, legend_y = 945, 195
    for index, (color, label) in enumerate(
        [(forge, "推荐"), ("#2d6385", "通过质量门槛"), (red, "未采用")]
    ):
        offset = index * 128
        draw.ellipse(
            (legend_x + offset, legend_y, legend_x + offset + 12, legend_y + 12),
            fill=color,
        )
        draw.text((legend_x + offset + 20, legend_y - 5), label, font=chinese_font(14), fill=muted)

    draw.rectangle((left, top, right, bottom), fill="#ffffff", outline=line, width=2)
    budget_x, gate_y = x(55), y(0.02)
    draw.rectangle((left, gate_y, budget_x, bottom), fill="#e8f4ef")
    draw.line((budget_x, top, budget_x, bottom), fill=forge, width=3)
    draw.line((left, gate_y, right, gate_y), fill=forge, width=3)
    draw.text((left + 18, gate_y + 16), "可行区域", font=chinese_font(17, True), fill=forge)
    draw.text((budget_x - 54, bottom + 20), "55 条连接上限", font=chinese_font(16), fill=forge)
    draw.text((right - 172, gate_y - 31), "2% 质量门槛", font=chinese_font(16), fill=forge)

    for percent in [0.0, 0.01, 0.02, 0.03]:
        yy = y(percent)
        draw.line((left, yy, right, yy), fill="#e8e8ed", width=1)
        draw.text((70, yy - 10), f"{percent * 100:.0f}%", font=font(16), fill=muted)
    for edge_count in [48, 55, 60, 65, 70, 74]:
        xx = x(edge_count)
        draw.line((xx, top, xx, bottom), fill="#efeff1", width=1)
        draw.text((xx - 11, bottom + 45), str(edge_count), font=font(16), fill=muted)
    draw.text((left, bottom + 78), "连接数", font=chinese_font(17), fill=muted)
    draw.text((54, top - 36), "最大质量下降", font=chinese_font(17), fill=muted)

    labels = {
        "sensitivity_guided_025": "推荐方案",
        "sparse_threshold_200": "边界失败",
        "pytheus_canonical": "基线",
    }
    visible_candidates = [
        candidate
        for candidate in snapshot["candidates"]
        if candidate["id"] not in {"random_sign_reference", "sensitivity_guided_025"}
    ]
    recommended = next(
        candidate
        for candidate in snapshot["candidates"]
        if candidate["id"] == "sensitivity_guided_025"
    )
    for candidate in [*visible_candidates, recommended]:
        xx, yy = x(candidate["edges"]), y(candidate["quality_drop"])
        if candidate["id"] == "sensitivity_guided_025":
            color, radius = forge, 13
        elif candidate["quality_acceptable"] and candidate["budget_feasible"]:
            color, radius = "#2d6385", 10
        else:
            color, radius = red, 9
        draw.ellipse((xx - radius, yy - radius, xx + radius, yy + radius), fill=color, outline="#ffffff", width=3)
        label = labels.get(candidate["id"])
        if label:
            draw.text((xx + 16, yy - 18), label, font=chinese_font(15, True), fill=ink)

    draw.text((902, 790), "随机扰动：99.98% 质量下降", font=chinese_font(17), fill=red)
    image.save(OUTPUT / "candidate-landscape.png")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / "web" / "public" / "reference-data.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    render_campaign(snapshot)
    render_quantum_graph(snapshot)
    render_candidate_landscape(snapshot)
    print(f"wrote {OUTPUT.relative_to(ROOT) / 'study-campaign.png'}")
    print(f"wrote {OUTPUT.relative_to(ROOT) / 'quantum-optics-case.png'}")
    print(f"wrote {OUTPUT.relative_to(ROOT) / 'candidate-landscape.png'}")


if __name__ == "__main__":
    main()
