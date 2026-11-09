#!/usr/bin/env python3
"""Render docs/demo.svg: the README's "See it in action" session as an animated terminal.

Run: python3 docs/make-demo.py   (rewrites docs/demo.svg)
Lines appear one at a time; the animation loops. Pure CSS, so GitHub renders it.
"""
import html
import os

LINES = [
    ("you", "> Add DELETE /api/events/:id so customers can remove an event."),
    ("", ""),
    ("title", "[factory] Delete-event endpoint — building"),
    ("dim", "  Plan: route, handler, tests. Finish line: suite + typecheck pass."),
    ("dim", "  ... implements it, tests pass ..."),
    ("", ""),
    ("title", "[factory] Delete-event endpoint — in-review"),
    ("warn", "  playbook-reviewer: 3 ways daily totals go wrong"),
    ("warn", "    - a back-dated event"),
    ("warn", "    - a delete racing the nightly rollup"),
    ("warn", "    - two concurrent deletes"),
    ("dim", "  ... fixes all three, adds tests, re-runs the suite ..."),
    ("", ""),
    ("title", "[factory] Delete-event endpoint — pr-open"),
    ("ok", "  Verified: test suite and typecheck pass."),
    ("text", "  Decisions:"),
    ("text", "  - Read-only API tokens can now delete data. That's your call:"),
    ("text", "    should DELETE need a write token?"),
]
COLORS = {"you": "#e6e6e6", "title": "#d97757", "dim": "#8b8b94", "warn": "#e5c07b", "ok": "#98c379", "text": "#e6e6e6"}
STEP, HOLD = 0.6, 6.0
W, LINE_H, TOP, LEFT = 760, 22, 52, 20
H = TOP + LINE_H * len(LINES) + 20
TOTAL = STEP * len(LINES) + HOLD


def main():
    rows, keyframes = [], []
    for i, (kind, text) in enumerate(LINES):
        if not text:
            continue
        shown = (i * STEP) / TOTAL * 100
        keyframes.append(
            f"@keyframes l{i}{{0%,{shown:.2f}%{{opacity:0}}{shown + 0.5:.2f}%,97%{{opacity:1}}100%{{opacity:0}}}}"
            f".l{i}{{animation:l{i} {TOTAL:.1f}s linear infinite}}"
        )
        y = TOP + LINE_H * i
        weight = ' font-weight="600"' if kind in ("you", "title") else ""
        rows.append(f'<text class="l{i}" x="{LEFT}" y="{y}" fill="{COLORS[kind]}"{weight} xml:space="preserve">'
                    f"{html.escape(text)}</text>")
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img"
  aria-label="A factory session: the agent builds the endpoint, its reviewer finds three bugs, it fixes them and opens a PR with a decision for you.">
<style>
text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:14px;opacity:0}}
{''.join(keyframes)}
@media (prefers-reduced-motion:reduce){{text{{animation:none!important;opacity:1}}}}
</style>
<rect width="{W}" height="{H}" rx="10" fill="#18181b"/>
<circle cx="22" cy="20" r="6" fill="#ff5f57"/><circle cx="42" cy="20" r="6" fill="#febc2e"/><circle cx="62" cy="20" r="6" fill="#28c840"/>
{chr(10).join(rows)}
</svg>
"""
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(out)


if __name__ == "__main__":
    main()
