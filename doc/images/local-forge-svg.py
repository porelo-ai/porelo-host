#!/usr/bin/env python3
"""Draws the local forge's way of a piece of work, in a hand-drawn style, as one SVG."""
import math
import sys

W, H = 1180, 2140
AI, GATE, BR, MAIN, CEN = 270, 410, 560, 750, 960
TOP, BOTTOM = 118, 1850
R = 14

COL = {
    "pink": ("#ff8cc6", "#e83e8c"),
    "yellow": ("#fff27a", "#f5c400"),
    "green": ("#7be07f", "#2fa53a"),
    "cyan": ("#8ff0ff", "#19b9d8"),
    "orange": ("#ffc07a", "#f07a1a"),
    "teal": ("#a8f5e8", "#13a58c"),
}

out = []
SEGS, RECTS = [], []


def add(s):
    out.append(s)


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def arrow(x1, y1, x2, y2, dashed=False, grey=False, gap1=R + 5, gap2=R + 7, porelo=False):
    dx, dy = x2 - x1, y2 - y1
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    sx, sy = x1 + ux * gap1, y1 + uy * gap1
    ex, ey = x2 - ux * gap2, y2 - uy * gap2
    colour = "#3b6fd0" if porelo else "#b9b9b9" if grey else "#1d1d1b"
    dash = ' stroke-dasharray="9 7"' if dashed else ""
    marker = "headblue" if porelo else "headgrey" if grey else "head"
    SEGS.append(((sx, sy), (ex, ey), f"{x1},{y1}->{x2},{y2}"))
    add(f'<path d="M{sx:.1f},{sy:.1f} L{ex:.1f},{ey:.1f}" stroke="{colour}" stroke-width="{1.7 if porelo else 2.6}" '
        f'fill="none" stroke-linecap="round"{dash} marker-end="url(#{marker})"/>')


def dot(x, y, colour):
    add(f'<circle cx="{x}" cy="{y}" r="{R}" fill="url(#g-{colour})" stroke="#1d1d1b" stroke-width="2.6"/>')


def badge(x, y, ok):
    fill = "#2fa53a" if ok else "#e23b3b"
    add(f'<circle cx="{x}" cy="{y}" r="10" fill="{fill}" stroke="#1d1d1b" stroke-width="2"/>')
    if ok:
        add(f'<path d="M{x-5},{y} l3.5,4 l6.5,-8" stroke="#fff" stroke-width="2.6" fill="none" '
            'stroke-linecap="round" stroke-linejoin="round"/>')
    else:
        add(f'<path d="M{x-4.5},{y-4.5} l9,9 M{x+4.5},{y-4.5} l-9,9" stroke="#fff" stroke-width="2.6" '
            'stroke-linecap="round"/>')


def callout(x, y, w, h, lines, tip, icon=None, todo=False, style=None):
    """A grey speech bubble; lines are (text, bold) pairs; tip is where its tail points."""
    tx, ty = tip
    RECTS.append((x, y, w, h, lines[0][0] + " " + (lines[1][0] if len(lines) > 1 else "")))
    cx, cy = x + w / 2, y + h / 2
    # the tail's base sits on the side nearest the tip
    if ty < y:
        b1, b2 = (min(max(tx, x + 18), x + w - 34), y), (min(max(tx, x + 18), x + w - 34) + 16, y)
    elif ty > y + h:
        b1, b2 = (min(max(tx, x + 18), x + w - 34), y + h), (min(max(tx, x + 18), x + w - 34) + 16, y + h)
    elif tx < x:
        b1, b2 = (x, min(max(ty, y + 12), y + h - 26)), (x, min(max(ty, y + 12), y + h - 26) + 14)
    else:
        b1, b2 = (x + w, min(max(ty, y + 12), y + h - 26)), (x + w, min(max(ty, y + 12), y + h - 26) + 14)
    style = style or icon
    fill = {"robot": "url(#bubble-robot)", "porelo": "url(#bubble-porelo)"}.get(style, "url(#bubble)")
    inner = {"robot": "#e1d7fd", "porelo": "#d9e6fb"}.get(style, "#e6e6e3")
    add('<g filter="url(#shadow)">')
    add(f'<path d="M{b1[0]:.1f},{b1[1]:.1f} L{tx:.1f},{ty:.1f} L{b2[0]:.1f},{b2[1]:.1f} Z" '
        f'fill="{fill}" stroke="#1d1d1b" stroke-width="2.4" stroke-linejoin="round" filter="url(#rough)"/>')
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="#1d1d1b" '
        'stroke-width="2.4" filter="url(#rough)"/>')
    # cover the tail's base inside the bubble
    mx = (b1[0] + b2[0]) / 2
    my = (b1[1] + b2[1]) / 2
    ix, iy = mx + (cx - mx) * 0.12, my + (cy - my) * 0.12
    add(f'<path d="M{b1[0] + (cx - b1[0]) * 0.12:.1f},{b1[1] + (cy - b1[1]) * 0.12:.1f} '
        f'L{ix:.1f},{iy:.1f} L{b2[0] + (cx - b2[0]) * 0.12:.1f},{b2[1] + (cy - b2[1]) * 0.12:.1f}" '
        f'stroke="{inner}" stroke-width="5" fill="none"/>')
    add('</g>')
    left = x + 12
    if icon:
        add(f'<use href="#{icon}" x="{x + 8}" y="{cy - 22}" width="44" height="44"/>')
        left = x + 56
    tw = x + w - left
    mid = left + tw / 2
    lh = 17
    start = cy - (len(lines) - 1) * lh / 2 + 5
    for i, (text, bold) in enumerate(lines):
        weight = ' font-weight="700"' if bold else ""
        body = ""
        for j, part in enumerate(text.replace("}", "{").split("{")):
            body += f'<tspan font-weight="700">{esc(part)}</tspan>' if j % 2 else esc(part)
        add(f'<text x="{mid:.1f}" y="{start + i * lh:.1f}" text-anchor="middle"{weight}>{body}</text>')
    if todo:
        add(f'<use href="#cone" x="{x + w - 20}" y="{y - 14}" width="26" height="26"/>')


def L(*parts):
    return [(p[1:], True) if p.startswith("*") else (p, False) for p in parts]


add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
    'font-family="Avenir Next, Avenir, Segoe UI, Helvetica Neue, Arial, sans-serif" font-size="13.5" fill="#1d1d1b">')
add('<title>How a piece of work goes from an AI agent through the local forge to the central forge</title>')
add('<defs>')
add(f'<filter id="rough" filterUnits="userSpaceOnUse" x="-50" y="-150" width="{W + 100}" height="{H + 300}"><feTurbulence type="fractalNoise" '
    'baseFrequency="0.035" numOctaves="2" seed="7"/><feDisplacementMap in="SourceGraphic" scale="2.6"/></filter>')
add('<filter id="shadow" x="-10%" y="-10%" width="130%" height="140%"><feDropShadow dx="2" dy="3" '
    'stdDeviation="2.2" flood-color="#000" flood-opacity="0.28"/></filter>')
add('<linearGradient id="bubble" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f7f7f5"/>'
    '<stop offset="1" stop-color="#d4d4d0"/></linearGradient>')
add('<linearGradient id="bubble-porelo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#eef4ff"/>'
    '<stop offset="1" stop-color="#bcd2f7"/></linearGradient>')
add('<linearGradient id="bubble-robot" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f3eeff"/>'
    '<stop offset="1" stop-color="#cdbdfa"/></linearGradient>')
for name, (light, dark) in COL.items():
    add(f'<radialGradient id="g-{name}" cx="0.38" cy="0.32" r="0.75"><stop offset="0" stop-color="{light}"/>'
        f'<stop offset="1" stop-color="{dark}"/></radialGradient>')
for mid, colour in (("head", "#1d1d1b"), ("headgrey", "#b9b9b9"), ("headblue", "#3b6fd0")):
    add(f'<marker id="{mid}" viewBox="0 0 14 14" refX="11" refY="7" markerWidth="14" markerHeight="14" '
        f'markerUnits="userSpaceOnUse" orient="auto"><path d="M1,1.5 L12,7 L1,12.5" fill="none" '
        f'stroke="{colour}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></marker>')
# the AI agent: a friendly robot
add('<symbol id="robot" viewBox="0 0 44 44">'
    '<line x1="22" y1="4" x2="22" y2="11" stroke="#1d1d1b" stroke-width="2.2"/>'
    '<circle cx="22" cy="4.5" r="3.2" fill="#ff5fa2" stroke="#1d1d1b" stroke-width="1.8"/>'
    '<rect x="3" y="18" width="5" height="11" rx="2" fill="#7d5cf0" stroke="#1d1d1b" stroke-width="1.8"/>'
    '<rect x="36" y="18" width="5" height="11" rx="2" fill="#7d5cf0" stroke="#1d1d1b" stroke-width="1.8"/>'
    '<rect x="7" y="11" width="30" height="26" rx="8" fill="#a68bff" stroke="#1d1d1b" stroke-width="2.2"/>'
    '<circle cx="16" cy="22" r="4.4" fill="#fff" stroke="#1d1d1b" stroke-width="1.6"/>'
    '<circle cx="28" cy="22" r="4.4" fill="#fff" stroke="#1d1d1b" stroke-width="1.6"/>'
    '<circle cx="17" cy="22.5" r="2" fill="#1d1d1b"/><circle cx="29" cy="22.5" r="2" fill="#1d1d1b"/>'
    '<path d="M16,30 Q22,34 28,30" stroke="#1d1d1b" stroke-width="2" fill="none" stroke-linecap="round"/>'
    '</symbol>')
# the person: you
# the reviewing agent: the robot in teal, with a magnifying glass
add('<symbol id="reviewer" viewBox="0 0 44 44">'
    '<line x1="20" y1="4" x2="20" y2="11" stroke="#1d1d1b" stroke-width="2.2"/>'
    '<circle cx="20" cy="4.5" r="3.2" fill="#ffd93b" stroke="#1d1d1b" stroke-width="1.8"/>'
    '<rect x="1" y="18" width="5" height="11" rx="2" fill="#13a58c" stroke="#1d1d1b" stroke-width="1.8"/>'
    '<rect x="5" y="11" width="30" height="26" rx="8" fill="#5fdcc4" stroke="#1d1d1b" stroke-width="2.2"/>'
    '<circle cx="14" cy="22" r="4.4" fill="#fff" stroke="#1d1d1b" stroke-width="1.6"/>'
    '<circle cx="26" cy="22" r="4.4" fill="#fff" stroke="#1d1d1b" stroke-width="1.6"/>'
    '<circle cx="15" cy="22.5" r="2" fill="#1d1d1b"/><circle cx="27" cy="22.5" r="2" fill="#1d1d1b"/>'
    '<path d="M14,31 L26,31" stroke="#1d1d1b" stroke-width="2" stroke-linecap="round"/>'
    '<line x1="37" y1="36" x2="43" y2="42" stroke="#1d1d1b" stroke-width="3.4" stroke-linecap="round"/>'
    '<circle cx="33" cy="32" r="6.5" fill="#dff7ff" fill-opacity="0.85" stroke="#1d1d1b" stroke-width="2.2"/>'
    '</symbol>')
add('<symbol id="person" viewBox="0 0 44 44">'
    '<path d="M6,42 C6,30 13,25 22,25 C31,25 38,30 38,42 Z" fill="#2e86de" stroke="#1d1d1b" stroke-width="2.2" '
    'stroke-linejoin="round"/>'
    '<circle cx="22" cy="14" r="9.5" fill="#ffc98b" stroke="#1d1d1b" stroke-width="2.2"/>'
    '<path d="M12.8,12 C13.5,5 20,3.5 24,4.5 C29,5.5 31.5,9 31.2,12.5 C27,10 20,10.5 12.8,12 Z" fill="#7a4a22" '
    'stroke="#1d1d1b" stroke-width="1.6" stroke-linejoin="round"/>'
    '<circle cx="18.5" cy="15" r="1.3" fill="#1d1d1b"/><circle cx="25.5" cy="15" r="1.3" fill="#1d1d1b"/>'
    '<path d="M18.5,19 Q22,21.5 25.5,19" stroke="#1d1d1b" stroke-width="1.6" fill="none" stroke-linecap="round"/>'
    '</symbol>')
add('<pattern id="hatch" width="14" height="14" patternUnits="userSpaceOnUse" '
    'patternTransform="rotate(45)"><rect width="14" height="14" fill="#ffd27a"/>'
    '<rect width="7" height="14" fill="#3a3a38"/></pattern>')
# Porelo itself, acting on the host: a gear
add('<symbol id="porelo" viewBox="0 0 44 44"><g transform="translate(22,22)">'
    + "".join(f'<rect x="-4.5" y="-19" width="9" height="9" rx="2" fill="#4a7fd6" stroke="#1d1d1b" stroke-width="1.8" '
              f'transform="rotate({a})"/>' for a in range(0, 360, 45))
    + '<circle r="13.5" fill="#6b9cf0" stroke="#1d1d1b" stroke-width="2.2"/>'
    '<circle r="5.5" fill="#fdfdfb" stroke="#1d1d1b" stroke-width="2"/></g></symbol>')
# not built yet: a traffic cone
add('<symbol id="cone" viewBox="0 0 30 30">'
    '<path d="M11,4 L19,4 L25,24 L5,24 Z" fill="#ff8a1f" stroke="#1d1d1b" stroke-width="1.8" stroke-linejoin="round"/>'
    '<path d="M9.4,11 L20.6,11 L22,15.5 L8,15.5 Z" fill="#fff"/>'
    '<rect x="2" y="23" width="26" height="5" rx="1.5" fill="#ff8a1f" stroke="#1d1d1b" stroke-width="1.8"/>'
    '</symbol>')
add('</defs>')
add(f'<rect width="{W}" height="{H}" fill="#fdfdfb"/>')

# the three places, and the gate between the first and the others
add(f'<rect x="56" y="104" width="326" height="{BOTTOM - 90}" rx="22" fill="#fff3e3" stroke="#f0cf9f" '
    'stroke-width="2" filter="url(#rough)"/>')
add(f'<rect x="438" y="104" width="446" height="{BOTTOM - 90}" rx="22" fill="#eef4ff" stroke="#c9d8f2" '
    'stroke-width="2" filter="url(#rough)"/>')
add(f'<rect x="900" y="104" width="258" height="{BOTTOM - 90}" rx="22" fill="#eefaf0" stroke="#c6e6cc" '
    'stroke-width="2" filter="url(#rough)"/>')
add('<text x="72" y="128" font-style="italic" fill="#a8641c">inside the tasks\' containers</text>')
add('<text x="454" y="128" font-style="italic" fill="#5470a0">on the host, outside the container</text>')
add('<text x="916" y="128" font-style="italic" fill="#3f8a50">on the central forge, public</text>')
add(f'<rect x="{GATE - 18}" y="96" width="36" height="{BOTTOM - 74}" rx="8" fill="url(#hatch)" stroke="#1d1d1b" '
    'stroke-width="2.4" filter="url(#rough)"/>')

# Porelo's gear once, on top of the gate
add(f'<use href="#porelo" x="{GATE - 21}" y="80" width="42" height="42"/>')
# headings
for x, a, b in ((219, "AI agent", "in its task"), (GATE, "the gate", "Porelo"),
                (BR, "local forge", "porelo/<task>"), (MAIN, "local forge", "main"), (CEN, "central forge", "main")):
    if x not in (BR, MAIN, CEN):
        add(f'<text x="{x}" y="52" text-anchor="middle" font-size="17" font-weight="700">{esc(a)}</text>')
    if x in (BR, MAIN, CEN):
        # the branch's name in a box at the top of its line
        bw = 15 + 8.6 * len(b)
        add(f'<rect x="{x - bw / 2:.1f}" y="146" width="{bw:.1f}" height="28" rx="8" fill="#fdfdfb" stroke="#1d1d1b" '
            'stroke-width="2.2" filter="url(#rough)"/>')
        add(f'<text x="{x}" y="165.5" text-anchor="middle" font-size="15" font-weight="700" '
            f'font-family="Menlo, Consolas, monospace">{esc(b)}</text>')
    else:
        add(f'<text x="{x}" y="76" text-anchor="middle" font-size="{14 if x == GATE else 16}">{esc(b)}</text>')

# time
add('<g filter="url(#rough)">')
add(f'<path d="M30,{TOP + 30} L30,{BOTTOM + 30}" stroke="#1d1d1b" stroke-width="5" stroke-linecap="round"/>')
add(f'<path d="M16,{BOTTOM + 8} L30,{BOTTOM + 36} L44,{BOTTOM + 8}" stroke="#1d1d1b" stroke-width="5" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
add(f'<path d="M18,{TOP + 30} L42,{TOP + 30}" stroke="#1d1d1b" stroke-width="5" stroke-linecap="round"/>')
add('</g>')
add(f'<text transform="translate(22,{TOP + 120}) rotate(-90)" font-size="24" font-weight="700" '
    'font-style="italic" text-anchor="middle">Time</text>')

# everything that happens, a little below the region labels
add(f'<g transform="translate(0,50)">')
# one heading over each forge's area (inside the shifted group, so 12 is drawn at 62)
add('<text x="661" y="12" text-anchor="middle" font-size="17" font-weight="700">local forge</text>')
add('<text x="1029" y="12" text-anchor="middle" font-size="17" font-weight="700">central forge</text>')
# lanes
for x in (BR, MAIN, CEN):
    add(f'<line x1="{x}" y1="{TOP + 22}" x2="{x}" y2="{BOTTOM - 60}" stroke="#d2d2cf" stroke-width="9" '
        'stroke-linecap="round" opacity="0.7" filter="url(#rough)"/>')


# --- the tasks' lifelines: a dashed line while the agent waits, a start and an end mark
def lifeline(x, y1, y2):
    add(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#a8641c" stroke-width="3" stroke-dasharray="3 7" '
        'stroke-linecap="round" filter="url(#rough)"/>')


def start(x, y):
    add(f'<circle cx="{x}" cy="{y}" r="9" fill="#2fa53a" stroke="#1d1d1b" stroke-width="2"/>'
        f'<path d="M{x - 3},{y - 5} L{x + 5},{y} L{x - 3},{y + 5} Z" fill="#fff"/>')


def end(x, y):
    add(f'<rect x="{x - 8}" y="{y - 8}" width="16" height="16" rx="3" fill="#e23b3b" stroke="#1d1d1b" stroke-width="2"/>')


lifeline(AI, 152, 880)
lifeline(AI + 52, 468, 566)
lifeline(AI, 926, 1100)
lifeline(AI, 1476, 1690)

# --- the arrows, under the dots
add('<g filter="url(#rough)">')
arrow(MAIN, 160, MAIN, 860)
arrow(MAIN, 860, MAIN, 1080)
arrow(MAIN, 1080, MAIN, 1350)
arrow(MAIN, 1350, MAIN, 1680)
arrow(CEN, 160, CEN, 1180)
arrow(CEN, 1180, CEN, 1280)
arrow(CEN, 1280, CEN, 1770)
arrow(BR, 270, BR, 450)
arrow(BR, 450, BR, 610)
arrow(BR, 610, BR, 770)
arrow(AI, 200, BR, 270)
arrow(AI, 350, BR, 450)
arrow(BR, 450, AI + 52, 530, dashed=True)
# a forge action tells Porelo, which starts the reviewer and later wakes the first agent
arrow(467, 451, BR, 450, porelo=True, gap1=3, gap2=R + 5)
arrow(472, 296, BR, 270, porelo=True, gap1=3, gap2=R + 5)
arrow(472, 626, BR, 616, porelo=True, gap1=3, gap2=R + 8)
# merged: a forge action tells Porelo, which ends the task
arrow(472, 840, MAIN, 860, porelo=True, gap1=3, gap2=R + 4)
arrow(472, 1072, MAIN, 1080, porelo=True, gap1=3, gap2=R + 4)
arrow(472, 1636, MAIN, 1680, porelo=True, gap1=3, gap2=R + 4)
# refused: Porelo is told and starts the merge task
arrow(472, 1414, CEN - 50, 1386, porelo=True, gap1=3, gap2=14)
arrow(AI + 52, 530, BR, 610)
arrow(AI, 740, BR, 770)
arrow(BR, 770, MAIN, 860)
arrow(AI, 960, BR, 1020)
arrow(BR, 1020, MAIN, 1080)
arrow(MAIN, 1080, CEN, 1180)
arrow(MAIN, 1350, CEN - 52, 1390, grey=True, dashed=True, gap2=4)
arrow(CEN, 1280, BR, 1440, dashed=True)
arrow(BR, 1440, AI, 1530, dashed=True)
arrow(AI, 1530, BR, 1600)
arrow(BR, 1440, BR, 1600)
arrow(BR, 1600, MAIN, 1680)
arrow(MAIN, 1680, CEN, 1770)
add('</g>')

# --- dots
for x, y, c in ((MAIN, 160, "green"), (CEN, 160, "cyan"), (AI, 200, "pink"), (BR, 270, "yellow"),
                (AI, 350, "pink"), (BR, 450, "yellow"), (AI + 52, 530, "teal"), (BR, 610, "yellow"),
                (AI, 740, "pink"), (BR, 770, "yellow"), (MAIN, 860, "green"), (AI, 960, "pink"),
                (BR, 1020, "yellow"), (MAIN, 1080, "green"), (CEN, 1180, "cyan"), (CEN, 1280, "orange"),
                (MAIN, 1350, "green"), (BR, 1440, "yellow"), (AI, 1530, "pink"), (BR, 1600, "yellow"), (MAIN, 1680, "green"), (CEN, 1770, "cyan")):
    dot(x, y, c)
badge(BR + 16, 270 + 16, False)
badge(BR + 16, 450 + 16, True)
badge(BR + 16, 770 + 16, True)
badge(BR + 16, 1020 + 16, True)
badge(BR + 16, 1600 + 16, True)
# the reviewer's comments on the pull request
add(f'<g transform="translate({BR + 6},{610 + 4})"><path d="M0,0 h22 a4,4 0 0 1 4,4 v11 a4,4 0 0 1 -4,4 h-12 '
    'l-6,6 v-6 h-4 a4,4 0 0 1 -4,-4 v-11 a4,4 0 0 1 4,-4 z" fill="#13a58c" stroke="#1d1d1b" stroke-width="2"/>'
    '<path d="M5,7 h16 M5,12 h11" stroke="#fff" stroke-width="2" stroke-linecap="round"/></g>')
add(f'<g filter="url(#rough)"><path d="M{CEN - 59},1377 l18,18 M{CEN - 41},1377 l-18,18" stroke="#e23b3b" stroke-width="5" '
    'stroke-linecap="round"/></g>')

start(AI, 152)
end(AI, 880)
start(AI + 52, 468)
end(AI + 52, 566)
start(AI, 926)
end(AI, 1100)
start(AI, 1476)
end(AI, 1690)

# --- the agent beside its work

# --- callouts
callout(62, 104, 176, 56, L("You start", "the task"), (AI - 11, 150), icon="person")
callout(58, 172, 194, 71, L("Codes, builds, tests,", "then {git push}"), (AI - 15, 202), icon="robot")
callout(58, 305, 194, 71, L("Reads the log,", "fixes, pushes again"), (AI - 15, 346), icon="robot")
callout(355, 424, 110, 54, L("Starts a", "review agent"), (AI + 61, 468), style="porelo", todo=True)
callout(58, 500, 190, 56, L("Reviews and", "only comments"), (AI + 37, 532), icon="reviewer", todo=True)
callout(350, 598, 120, 56, L("Wakes up", "the agent"), (AI + 12, 728), style="porelo", todo=True)
callout(58, 714, 190, 56, L("Works the", "comments in"), (AI - 15, 742), icon="robot")
callout(350, 812, 120, 56, L("Ends the task", "with the merge"), (AI + 10, 878), style="porelo", todo=True)
callout(350, 1044, 120, 56, L("Ends the task", "with the merge"), (AI + 10, 1100), style="porelo", todo=True)
callout(62, 900, 180, 56, L("You start", "another task"), (AI - 11, 924), icon="person")
callout(58, 972, 194, 56, L("Codes, builds, tests,", "then {git push}"), (AI - 15, 962), icon="robot")
callout(596, 228, 148, 54, L("Local build: {red};", "Porelo reads it"), (BR + 26, 262))
callout(350, 268, 120, 56, L("Hands the log", "to the task"), (AI + 12, 342), style="porelo")
callout(596, 404, 148, 54, L("Built again: {green};", "Porelo reads it"), (BR + 26, 446))
callout(596, 574, 148, 71, L("Comments on the", "pull request;", "Porelo reads them"), (BR + 34, 618), todo=True)
callout(606, 720, 130, 54, L("Built again:", "*green"), (BR + 26, 766))
callout(565, 888, 170, 71, L("*Decision 1:", "you read", "and merge"),
        (656, 820), icon="person")
callout(768, 1196, 176, 71, L("*Decision 2:", "you push all", "merged work"),
        (870, 1138), icon="person")
callout(986, 140, 164, 54, L("Central main,", "as it is"), (CEN + 15, 162))
callout(986, 1132, 164, 54, L("Built and", "*published"), (CEN + 15, 1174))
callout(986, 1250, 164, 54, L("Meanwhile someone", "merges centrally"), (CEN + 15, 1276))
callout(600, 1262, 128, 54, L("More work", "merged"), (MAIN - 16, 1346))
callout(762, 1418, 154, 71, L("*Refused:", "central forge moved;", "Porelo sees it"), (910, 1396), todo=True)
callout(446, 1330, 152, 54, L("Comes back as", "*central/main"), (BR - 10, 1428))
callout(350, 1386, 120, 56, L("Starts a", "merge task"), (AI + 11, 1476), style="porelo", todo=True)
callout(58, 1528, 194, 56, L("Merges central/main,", "then {git push}"), (AI - 15, 1530), icon="robot")
callout(606, 1540, 130, 54, L("Built:", "*green"), (BR + 26, 1596))
callout(565, 1708, 170, 56, L("You read", "and merge"), (655, 1645), icon="person")
callout(350, 1608, 120, 56, L("Ends the task", "with the merge"), (AI + 10, 1690), style="porelo", todo=True)
callout(986, 1728, 164, 54, L("You push again:", "*goes through"), (CEN + 15, 1766))

add('</g>')

# --- legend
ly = 1920
add(f'<text x="56" y="{ly}" font-weight="700">The marks</text>')
items = (("pink", "the agent's work"), ("yellow", "on the local forge, built there"),
         ("green", "merged into the local main"), ("cyan", "on the central forge"),
         ("orange", "merged centrally by someone else"), ("teal", "the reviewing agent's comments"))
for i, (colour, text) in enumerate(items):
    cx = 56 + (i % 3) * 300
    cy = ly + 26 + (i // 3) * 28
    add(f'<circle cx="{cx + 10}" cy="{cy - 5}" r="9" fill="url(#g-{colour})" stroke="#1d1d1b" stroke-width="2"/>')
    add(f'<text x="{cx + 28}" y="{cy}">{esc(text)}</text>')
cy = ly + 86
add(f'<rect x="56" y="{cy - 20}" width="16" height="26" rx="4" fill="url(#hatch)" stroke="#1d1d1b" stroke-width="1.8"/>')
add(f'<text x="80" y="{cy}">the gate</text>')
add(f'<use href="#robot" x="356" y="{cy - 22}" width="30" height="30"/>')
add(f'<text x="392" y="{cy}">the AI agent</text>')
add(f'<use href="#person" x="656" y="{cy - 22}" width="30" height="30"/>')
add(f'<text x="692" y="{cy}">you</text>')
add(f'<use href="#reviewer" x="806" y="{cy - 22}" width="30" height="30"/>')
add(f'<text x="842" y="{cy}">the reviewing agent</text>')
cy += 30
start(66, cy - 5)
add(f'<text x="84" y="{cy}">a task starts</text>')
end(366, cy - 5)
add(f'<text x="384" y="{cy}">a task ends</text>')
add(f'<line x1="660" y1="{cy - 5}" x2="700" y2="{cy - 5}" stroke="#a8641c" stroke-width="3" stroke-dasharray="3 7" '
    'stroke-linecap="round"/>')
add(f'<text x="712" y="{cy}">the agent waits</text>')
cy += 32
add(f'<use href="#cone" x="54" y="{cy - 22}" width="28" height="28"/>')
add(f'<text x="88" y="{cy}">not built yet</text>')
add(f'<use href="#porelo" x="356" y="{cy - 22}" width="30" height="30"/>')
add(f'<text x="392" y="{cy}">Porelo, the gate</text>')
add(f'<path d="M656,{cy - 5} L694,{cy - 5}" stroke="#3b6fd0" stroke-width="1.7" marker-end="url(#headblue)"/>')
add(f'<text x="712" y="{cy}">Porelo reads it from the forge</text>')
cy += 30
add(f'<text x="56" y="{cy}" font-style="italic" fill="#5d5b55">Every arrow through the gate passes Porelo: pushes, fetches, logs and comments.</text>')

add('</svg>')
open(sys.argv[1], "w").write("\n".join(out) + "\n")


def hits(seg, rect):
    (ax, ay), (bx, by), _ = seg
    x, y, w, h, _ = rect
    for i in range(41):
        t = i / 40
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        if x - 3 <= px <= x + w + 3 and y - 3 <= py <= y + h + 3:
            return True
    return False


if "--check" in sys.argv:
    for r in RECTS:
        for g in SEGS:
            if hits(g, r):
                print(f"{r[4]!r:40} at ({r[0]},{r[1]},{r[2]},{r[3]})  <- arrow {g[2]}")
