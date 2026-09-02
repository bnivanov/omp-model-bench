#!/usr/bin/env python3
"""Render the X article's benchmark figures from canonical result summaries."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmark" / "results"
OUTPUT = ROOT / "benchmark" / "visuals" / "out"

WIDTH, HEIGHT = 1600, 900
BG = "#0B1016"
PANEL = "#121A24"
PANEL_2 = "#172230"
GRID = "#293748"
TEXT = "#F4F0E8"
MUTED = "#95A3B3"
SUBTLE = "#657386"
PLAN = "#FF8066"
PLAN_SOFT = "#4A2926"
PREWALK = "#33C7B5"
PREWALK_SOFT = "#163D3B"
GOLD = "#F2C766"
BLUE = "#83A7FF"
WHITE = "#FFFFFF"

SANS = "/System/Library/Fonts/Avenir Next.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"

TASK_LABELS = {
    1: "tengo",
    4: "wasmi",
    5: "kombu",
    6: "arktype",
    8: "drizzle-orm",
}
TASKS = tuple(TASK_LABELS)


def sans(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    index = {"bold": 0, "demi": 2, "medium": 5, "regular": 7}[weight]
    return ImageFont.truetype(SANS, size, index=index)


def mono(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(MONO, size, index=1 if bold else 0)


def load_routes(task: int) -> dict[str, dict]:
    payload = json.loads((RESULTS / f"task{task}-summary.json").read_text())
    return {route["condition"]: route for route in payload["routes"]}


ROUTES = {task: load_routes(task) for task in (*TASKS, 10)}


def route(task: int, condition: str) -> dict:
    return ROUTES[task][condition]


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    return image, ImageDraw.Draw(image)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, fill: str, radius: int = 24,
            outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=font)


def wrapped_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                  max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if text_width(draw, candidate, font) <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
                 font: ImageFont.FreeTypeFont, fill: str, max_width: int,
                 spacing: int = 8) -> int:
    x, y = xy
    lines = wrapped_lines(draw, text, font, max_width)
    line_height = font.size + spacing
    for i, line in enumerate(lines):
        draw.text((x, y + i * line_height), line, font=font, fill=fill)
    return y + len(lines) * line_height


def eyebrow(draw: ImageDraw.ImageDraw, label: str, *, x: int = 90, y: int = 58,
            color: str = GOLD) -> None:
    draw.text((x, y), label.upper(), font=mono(19, True), fill=color)


def title(draw: ImageDraw.ImageDraw, heading: str, subheading: str | None = None,
          *, y: int = 92, size: int = 52) -> int:
    bottom = draw_wrapped(draw, (90, y), heading, sans(size, "bold"), TEXT, 1360, 7)
    if subheading:
        bottom = draw_wrapped(draw, (90, bottom + 12), subheading, sans(24), MUTED, 1370, 6)
    return bottom


def footer(draw: ImageDraw.ImageDraw, right: str = "bnivanov/omp-model-bench") -> None:
    y = HEIGHT - 48
    draw.line((90, y - 18, WIDTH - 90, y - 18), fill=GRID, width=1)
    draw.text((90, y), "OMP × DeepSWE  •  exploratory benchmark  •  September 2026",
              font=mono(15), fill=SUBTLE, anchor="ls")
    draw.text((WIDTH - 90, y), right, font=mono(15), fill=SUBTLE, anchor="rs")


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], label: str, color: str,
         *, background: str | None = None) -> int:
    x, y = xy
    font = mono(16, True)
    w = int(text_width(draw, label, font)) + 30
    rounded(draw, (x, y, x + w, y + 34), fill=background or PANEL_2, radius=17)
    draw.text((x + 15, y + 18), label, font=font, fill=color, anchor="lm")
    return w


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str) -> None:
    draw.line((*start, *end), fill=color, width=4)
    ex, ey = end
    draw.polygon([(ex, ey), (ex - 12, ey - 8), (ex - 12, ey + 8)], fill=color)


def save(image: Image.Image, name: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT / name, format="PNG", optimize=True)


def render_cover() -> None:
    image, draw = canvas()
    eyebrow(draw, "Coding-agent routing study")
    draw_wrapped(
        draw,
        (90, 108),
        "I could not afford frontier models on every coding task, so I benchmarked the handoff",
        sans(62, "bold"),
        TEXT,
        1350,
        7,
    )
    draw.text((92, 330), "Five valid paired DeepSWE tasks  •  Kimi K3 to DeepSeek-V4-Flash",
              font=sans(25, "medium"), fill=MUTED)

    cards = [
        (90, 438, 520, 690, PLAN_SOFT, PLAN, "PLAN-YOLO", "5 / 5", "full task passes"),
        (555, 438, 985, 690, PREWALK_SOFT, PREWALK, "PREWALK", "2 / 5", "full task passes"),
        (1020, 438, 1510, 690, PANEL, GOLD, "EXACT MCNEMAR", "p = .25", "directional signal, underpowered"),
    ]
    for x1, y1, x2, y2, fill, accent, label, value, note in cards:
        rounded(draw, (x1, y1, x2, y2), fill=fill, radius=28, outline=accent, width=2)
        draw.text((x1 + 28, y1 + 34), label, font=mono(17, True), fill=accent)
        draw.text((x1 + 28, y1 + 88), value, font=sans(62, "bold"), fill=TEXT)
        draw.text((x1 + 28, y1 + 178), note, font=sans(20), fill=MUTED)

    draw.text((90, 748), "Quality: Plan-YOLO never scored lower.", font=sans(23, "demi"), fill=TEXT)
    draw.text((790, 748), "Efficiency: prewalk was cheaper and faster on 4 / 5.",
              font=sans(23, "demi"), fill=TEXT)
    footer(draw)
    save(image, "01-cover.png")


def pipeline_node(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str,
                  note: str, accent: str, *, strong: bool = False) -> None:
    rounded(draw, box, fill=PANEL_2 if strong else PANEL, radius=20, outline=accent, width=2 if strong else 1)
    x1, y1, x2, _ = box
    draw.text(((x1 + x2) // 2, y1 + 35), label, font=sans(21, "demi"), fill=TEXT, anchor="mm")
    lines = wrapped_lines(draw, note, sans(16), x2 - x1 - 30)
    for i, line in enumerate(lines[:2]):
        draw.text(((x1 + x2) // 2, y1 + 72 + 23 * i), line, font=sans(16), fill=MUTED, anchor="mm")


def render_method() -> None:
    image, draw = canvas()
    eyebrow(draw, "Figure 1  •  treatment design")
    title(draw, "The two handoffs differ at the mutation boundary",
          "Same task and worker. Different information transfer and code ownership.", y=92)

    rows = [
        (238, "PLAN-YOLO", PLAN, [
            ("K3 explores", "read-only repo inspection"),
            ("Blueprint", "Markdown architecture plan"),
            ("Fresh DS4", "plan enters a clean context"),
            ("All edits", "DS4 owns implementation"),
        ]),
        (468, "PREWALK", PREWALK, [
            ("K3 explores", "repo reads + todo list"),
            ("First edit", "K3 commits to code"),
            ("Inherited DS4", "warm trajectory + diff"),
            ("Continue", "DS4 finishes implementation"),
        ]),
    ]
    node_w, node_h, gap, start_x = 270, 124, 64, 248
    for y, label, accent, nodes in rows:
        draw.text((90, y + 58), label, font=mono(18, True), fill=accent, anchor="lm")
        for i, (node_label, note) in enumerate(nodes):
            x = start_x + i * (node_w + gap)
            pipeline_node(draw, (x, y, x + node_w, y + node_h), node_label, note, accent,
                          strong=i in (1, 2))
            if i < len(nodes) - 1:
                arrow(draw, (x + node_w + 10, y + node_h // 2),
                      (x + node_w + gap - 12, y + node_h // 2), accent)

    mutation_x = start_x + 2 * node_w + gap + gap // 2
    draw.line((mutation_x, 208, mutation_x, 640), fill=GOLD, width=2)
    draw.text((mutation_x, 662), "MUTATION BOUNDARY", font=mono(14, True), fill=GOLD, anchor="ma")

    controls = ["same task", "same snapshot", "same verifier", "90m budget", "max reasoning", "no web / subagents"]
    x = 90
    for control in controls:
        x += pill(draw, (x, 730), control, BLUE) + 12
    footer(draw)
    save(image, "02-handoff-design.png")


def render_quality() -> None:
    image, draw = canvas()
    eyebrow(draw, "Figure 2  •  quality")
    title(draw, "Plan-YOLO passed every F2P check in all five valid pairs",
          "The 85–100% axis is intentionally truncated so the misses remain visible.", y=92)

    x0, x1 = 420, 1460
    y0, row_gap = 310, 78
    axis_min, axis_max = 0.85, 1.0
    for tick in (0.85, 0.90, 0.95, 1.0):
        x = x0 + (tick - axis_min) / (axis_max - axis_min) * (x1 - x0)
        draw.line((x, y0 - 32, x, y0 + row_gap * 4 + 58), fill=GRID, width=1)
        draw.text((x, y0 - 49), f"{tick:.0%}", font=mono(14), fill=SUBTLE, anchor="ms")

    for idx, task in enumerate(TASKS):
        y = y0 + idx * row_gap
        plan = route(task, "k3-plan-yolo-ds4")
        pre = route(task, "k3-prewalk-ds4")
        plan_rate = plan["f2p"]["passed"] / plan["f2p"]["total"]
        pre_rate = pre["f2p"]["passed"] / pre["f2p"]["total"]
        draw.text((90, y + 22), TASK_LABELS[task], font=sans(21, "demi"), fill=TEXT, anchor="lm")
        draw.text((275, y + 2), "PLAN", font=mono(13, True), fill=PLAN, anchor="lm")
        draw.text((275, y + 42), "PRE", font=mono(13, True), fill=PREWALK, anchor="lm")
        for rate, yy, color, result in (
            (plan_rate, y - 7, PLAN, plan),
            (pre_rate, y + 33, PREWALK, pre),
        ):
            end = x0 + max(0, (rate - axis_min) / (axis_max - axis_min)) * (x1 - x0)
            draw.line((x0, yy + 10, end, yy + 10), fill=color, width=14)
            draw.ellipse((end - 10, yy, end + 10, yy + 20), fill=color)
            label = f"{result['f2p']['passed']}/{result['f2p']['total']}  ({rate:.1%})"
            label_x = min(end - 12, x1 - 14)
            draw.text((label_x, yy - 5), label, font=mono(14, True), fill=TEXT, anchor="rs")

    rounded(draw, (90, 704, 1510, 804), fill=PANEL, radius=20)
    draw.text((122, 739), "Task-level full pass", font=mono(15, True), fill=MUTED)
    draw.text((420, 754), "5 / 5", font=sans(34, "bold"), fill=PLAN, anchor="mm")
    draw.text((650, 754), "vs", font=sans(22), fill=SUBTLE, anchor="mm")
    draw.text((840, 754), "2 / 5", font=sans(34, "bold"), fill=PREWALK, anchor="mm")
    draw.text((1110, 754), "exact McNemar  p = .25", font=mono(18, True), fill=GOLD, anchor="lm")
    footer(draw)
    save(image, "03-paired-quality.png")


def draw_grouped_bars(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], heading: str,
                      unit: str, values: list[tuple[str, float, float]], maximum: float) -> None:
    x1, y1, x2, y2 = box
    rounded(draw, box, fill=PANEL, radius=24)
    draw.text((x1 + 28, y1 + 34), heading, font=sans(25, "demi"), fill=TEXT)
    draw.text((x2 - 28, y1 + 37), "lower is better", font=mono(14), fill=MUTED, anchor="ra")
    bar_x0, bar_x1 = x1 + 175, x2 - 42
    start_y, gap = y1 + 95, 90
    for i, (label, plan_value, pre_value) in enumerate(values):
        y = start_y + i * gap
        if label == "kombu":
            rounded(draw, (x1 + 14, y - 18, x2 - 14, y + 75), fill="#18252C", radius=14)
        draw.text((x1 + 28, y + 27), label, font=sans(18, "demi"), fill=TEXT, anchor="lm")
        for value, yy, color in ((plan_value, y, PLAN), (pre_value, y + 35, PREWALK)):
            width = max(4, (value / maximum) * (bar_x1 - bar_x0))
            draw.rounded_rectangle((bar_x0, yy, bar_x0 + width, yy + 16), radius=8, fill=color)
            value_label = f"${value:.2f}" if unit == "$" else f"{value:g}{unit}"
            draw.text((min(bar_x0 + width + 10, bar_x1 - 2), yy + 8), value_label,
                      font=mono(13, True), fill=TEXT, anchor="lm")
    draw.text((x1 + 28, y2 - 33), "PLAN-YOLO", font=mono(13, True), fill=PLAN)
    draw.text((x1 + 165, y2 - 33), "PREWALK", font=mono(13, True), fill=PREWALK)


def render_tradeoffs() -> None:
    image, draw = canvas()
    eyebrow(draw, "Figure 3  •  efficiency")
    title(draw, "The quality gain was usually expensive",
          "Prewalk cost less and finished sooner on four of five valid pairs. Kombu reversed both.", y=92)

    cost_values: list[tuple[str, float, float]] = []
    time_values: list[tuple[str, float, float]] = []
    for task in TASKS:
        plan = route(task, "k3-plan-yolo-ds4")
        pre = route(task, "k3-prewalk-ds4")
        cost_values.append((TASK_LABELS[task], round(plan["comparison_cost_usd"], 2), round(pre["comparison_cost_usd"], 2)))
        time_values.append((TASK_LABELS[task], round(plan["runtime_seconds"] / 60, 1), round(pre["runtime_seconds"] / 60, 1)))

    draw_grouped_bars(draw, (90, 230, 780, 805), "Estimated workflow cost", "$", cost_values, 3.5)
    draw_grouped_bars(draw, (820, 230, 1510, 805), "Wall time", "m", time_values, 70)
    footer(draw)
    save(image, "04-cost-time-tradeoff.png")


def metric_comparison(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str,
                      plan_value: str, pre_value: str, note: str, *, value_size: int = 39) -> None:
    x1, y1, x2, y2 = box
    rounded(draw, box, fill=PANEL, radius=22)
    draw.text((x1 + 24, y1 + 27), label.upper(), font=mono(14, True), fill=MUTED)
    draw.text((x1 + 24, y1 + 84), plan_value, font=sans(value_size, "bold"), fill=PLAN)
    draw.text((x1 + 24, y1 + 126), "PLAN-YOLO", font=mono(13, True), fill=PLAN)
    draw.text((x2 - 24, y1 + 84), pre_value, font=sans(value_size, "bold"), fill=PREWALK, anchor="ra")
    draw.text((x2 - 24, y1 + 126), "PREWALK", font=mono(13, True), fill=PREWALK, anchor="ra")
    draw.line((x1 + 24, y1 + 154, x2 - 24, y1 + 154), fill=GRID, width=1)
    draw.text(((x1 + x2) // 2, y2 - 32), note, font=sans(16, "medium"), fill=TEXT, anchor="mm")


def render_kombu() -> None:
    image, draw = canvas()
    eyebrow(draw, "Figure 4  •  the counterexample")
    title(draw, "Kombu: the read-only plan won on quality, cost, and time",
          "One long-horizon Python task where the warm trajectory became the heavier route.", y=92)

    boxes = [(90, 250, 445, 485), (470, 250, 825, 485), (850, 250, 1205, 485), (1230, 250, 1510, 485)]
    metric_comparison(draw, boxes[0], "F2P checks", "76 / 76", "68 / 76", "full recovery vs 8 misses")
    metric_comparison(draw, boxes[1], "Estimated cost", "$0.53", "$0.71", "~25% lower")
    metric_comparison(draw, boxes[2], "Wall time", "18:54", "38:29", "~51% shorter")
    metric_comparison(draw, boxes[3], "Processed input", "6.54M", "8.75M", "~25% fewer tokens", value_size=30)

    rounded(draw, (90, 548, 1510, 760), fill=PANEL_2, radius=24)
    draw.text((124, 584), "WHAT THIS CHANGES", font=mono(15, True), fill=GOLD)
    draw_wrapped(
        draw,
        (124, 626),
        "A warm context can save rereads, but a long inherited trajectory can also make every later turn heavier. This task shows that clean-boundary planning can dominate in at least one real case.",
        sans(25, "medium"),
        TEXT,
        1030,
        8,
    )
    rounded(draw, (1210, 584, 1472, 724), fill=BG, radius=18, outline=GOLD, width=1)
    draw.text((1341, 624), "SCOPE", font=mono(14, True), fill=GOLD, anchor="mm")
    draw.text((1341, 665), "1 task", font=sans(29, "bold"), fill=TEXT, anchor="mm")
    draw.text((1341, 700), "1 run per arm", font=sans(16), fill=MUTED, anchor="mm")
    footer(draw)
    save(image, "05-kombu-case-study.png")


def interval_bar(draw: ImageDraw.ImageDraw, y: int, label: str, low: float, high: float,
                 point: float, color: str) -> None:
    x0, x1 = 360, 1415
    draw.text((90, y), label, font=sans(22, "demi"), fill=TEXT, anchor="lm")
    low_x = x0 + low * (x1 - x0)
    high_x = x0 + high * (x1 - x0)
    point_x = x0 + point * (x1 - x0)
    draw.line((x0, y, x1, y), fill=GRID, width=10)
    draw.line((low_x, y, high_x, y), fill=color, width=14)
    draw.ellipse((point_x - 13, y - 13, point_x + 13, y + 13), fill=color, outline=WHITE, width=2)
    draw.text((low_x, y - 28), f"{low:.1%}", font=mono(14, True), fill=color, anchor="ms")
    draw.text((high_x, y - 28), f"{high:.1%}", font=mono(14, True), fill=color, anchor="ms")


def render_inference() -> None:
    image, draw = canvas()
    eyebrow(draw, "Figure 5  •  statistical scope")
    title(draw, "Strong descriptive pattern. Weak population inference.",
          "Five adaptively selected paired tasks are enough to motivate the next study, not a universal claim.", y=92)

    for tick in (0, .25, .5, .75, 1):
        x = 360 + tick * (1415 - 360)
        draw.text((x, 260), f"{tick:.0%}", font=mono(14), fill=SUBTLE, anchor="ms")
    interval_bar(draw, 340, "Plan-YOLO", 0.5655, 1.0, 1.0, PLAN)
    interval_bar(draw, 450, "Prewalk", 0.1176, 0.7693, 0.4, PREWALK)
    draw.text((360, 505), "Nominal Wilson 95% intervals; exchangeability assumption is not justified by adaptive selection.",
              font=sans(16), fill=MUTED)

    rounded(draw, (90, 564, 735, 790), fill=PANEL, radius=22)
    draw.text((120, 598), "CAN SAY", font=mono(15, True), fill=PLAN)
    can_say = [
        "Observed 5 / 5 vs 2 / 5 full passes",
        "Plan-YOLO never scored lower in these pairs",
        "Kombu is a real counterexample to universal warm-context efficiency",
    ]
    for i, item in enumerate(can_say):
        draw.ellipse((122, 647 + i * 43, 132, 657 + i * 43), fill=PLAN)
        draw.text((148, 653 + i * 43), item, font=sans(17), fill=TEXT, anchor="lm")

    rounded(draw, (765, 564, 1510, 790), fill=PANEL, radius=22)
    draw.text((795, 598), "CANNOT SAY", font=mono(15, True), fill=PREWALK)
    cannot_say = [
        "Universal superiority or a file-count threshold",
        "A proven anchoring or context-pollution mechanism",
        "Generalisation to other model pairs",
    ]
    for i, item in enumerate(cannot_say):
        draw.ellipse((797, 647 + i * 43, 807, 657 + i * 43), fill=PREWALK)
        draw.text((823, 653 + i * 43), item, font=sans(17), fill=TEXT, anchor="lm")

    draw.text((1510, 520), "exact McNemar  p = .25", font=mono(17, True), fill=GOLD, anchor="rs")
    footer(draw)
    save(image, "06-statistical-scope.png")


def render_routing() -> None:
    image, draw = canvas()
    eyebrow(draw, "Figure 6  •  provisional routing policy")
    title(draw, "Where I would spend frontier intelligence today",
          "A working rule for this exact K3 to DeepSeek pair, not a validated classifier.", y=92)

    cards = [
        (90, 245, 535, 720, BLUE, "01", "DEEPSEEK SOLO", "Start here", [
            "Local or bounded task",
            "Strong verification available",
            "Cheap failure or easy retry",
        ], "Lowest expected overhead"),
        (575, 245, 1020, 720, PREWALK, "02", "PREWALK", "Optimise speed / cost", [
            "Opening edit likely captures the core",
            "Small, coherent implementation surface",
            "A near-pass may be acceptable",
        ], "Cheaper + faster in 4 / 5 pairs"),
        (1060, 245, 1510, 720, PLAN, "03", "PLAN-YOLO", "Buy reliability", [
            "Several interacting invariants",
            "Compiler, runtime, or state-machine work",
            "One missed check still means failure",
        ], "Full pass in 5 / 5 pairs"),
    ]
    for x1, y1, x2, y2, accent, number, label, strap, bullets, proof in cards:
        rounded(draw, (x1, y1, x2, y2), fill=PANEL, radius=26, outline=accent, width=2)
        draw.text((x1 + 28, y1 + 33), number, font=mono(17, True), fill=accent)
        draw.text((x1 + 28, y1 + 86), label, font=sans(29, "bold"), fill=TEXT)
        draw.text((x1 + 28, y1 + 128), strap, font=sans(19, "medium"), fill=accent)
        draw.line((x1 + 28, y1 + 170, x2 - 28, y1 + 170), fill=GRID, width=1)
        for i, bullet in enumerate(bullets):
            cy = y1 + 225 + i * 72
            draw.ellipse((x1 + 30, cy - 5, x1 + 42, cy + 7), fill=accent)
            draw_wrapped(draw, (x1 + 60, cy - 17), bullet, sans(18), TEXT, x2 - x1 - 98, 5)
        rounded(draw, (x1 + 24, y2 - 78, x2 - 24, y2 - 24), fill=PANEL_2, radius=14)
        draw.text(((x1 + x2) // 2, y2 - 51), proof, font=mono(14, True), fill=accent, anchor="mm")

    draw.text((90, 775), "Routing features still need pre-registered validation on more independent tasks and model pairs.",
              font=sans(19), fill=MUTED)
    footer(draw)
    save(image, "07-routing-policy.png")


def validate_sources() -> None:
    expected = {
        1: ((23, 23), (22, 23), 1.3394638656, 0.611064388, 2209, 1131),
        4: ((22, 22), (22, 22), 1.8487027752, 0.9588850488, 2139, 1646),
        5: ((76, 76), (68, 76), 0.5344185408, 0.7124825256, 1134, 2309),
        6: ((25, 25), (24, 25), 3.4162335104, 0.3912797472, 4045, 1675),
        8: ((130, 130), (130, 130), 0.6025, 0.5466, 1265, 1173),
    }
    for task, (plan_f2p, pre_f2p, plan_cost, pre_cost, plan_time, pre_time) in expected.items():
        plan = route(task, "k3-plan-yolo-ds4")
        pre = route(task, "k3-prewalk-ds4")
        assert (plan["f2p"]["passed"], plan["f2p"]["total"]) == plan_f2p
        assert (pre["f2p"]["passed"], pre["f2p"]["total"]) == pre_f2p
        assert math.isclose(plan["comparison_cost_usd"], plan_cost)
        assert math.isclose(pre["comparison_cost_usd"], pre_cost)
        assert plan["runtime_seconds"] == plan_time
        assert pre["runtime_seconds"] == pre_time


def main() -> None:
    validate_sources()
    render_cover()
    render_method()
    render_quality()
    render_tradeoffs()
    render_kombu()
    render_inference()
    render_routing()
    print(f"Rendered 7 figures to {OUTPUT}")


if __name__ == "__main__":
    main()
