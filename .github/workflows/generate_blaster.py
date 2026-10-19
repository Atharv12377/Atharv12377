#!/usr/bin/env python3
"""
generate_blaster.py
Fetches the GitHub contribution graph and generates an SVG where
red laser bolts spontaneously fire across the grid and hit boxes.
No gun. Just the laser.
"""

import os
import math
import random
import requests
from datetime import datetime

LEVEL_COLORS = {
    "NONE":            "#161b22",
    "FIRST_QUARTILE":  "#0e4429",
    "SECOND_QUARTILE": "#006d32",
    "THIRD_QUARTILE":  "#26a641",
    "FOURTH_QUARTILE": "#39d353",
}


def fetch_contributions(username: str, token: str) -> dict:
    query = """
    query($username: String!) {
      user(login: $username) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                contributionLevel
                date
              }
            }
          }
        }
      }
    }
    """
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"username": username}},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def generate_svg(calendar: dict, seed: int = 42) -> str:
    random.seed(seed)

    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    # ── Layout ────────────────────────────────────────────────────────────
    BOX    = 10
    GAP    = 3
    STEP   = BOX + GAP
    PAD_X  = 16
    PAD_Y  = 24   # space for month labels

    N_WEEKS = len(weeks)

    SVG_W = PAD_X * 2 + N_WEEKS * STEP
    SVG_H = PAD_Y + 7 * STEP + 14

    # ── Build box list ────────────────────────────────────────────────────
    all_boxes = []
    for wi, week in enumerate(weeks):
        for di, day in enumerate(week["contributionDays"]):
            bx = PAD_X + wi * STEP
            by = PAD_Y + di * STEP
            cx = bx + BOX // 2
            cy = by + BOX // 2
            color = LEVEL_COLORS.get(day["contributionLevel"], "#161b22")
            all_boxes.append({
                "x": bx, "y": by, "cx": cx, "cy": cy,
                "color": color, "count": day["contributionCount"],
                "wi": wi, "di": di,
            })

    # ── Pick shot pairs: source box → target box ──────────────────────────
    # Prefer boxes with contributions as sources; any box can be a target
    hot   = [b for b in all_boxes if b["count"] > 0]
    pool  = hot if len(hot) >= 20 else all_boxes
    n_shots = min(16, len(pool))

    shots = []
    used  = set()
    candidates = random.sample(pool, min(n_shots * 3, len(pool)))
    for src in candidates:
        if len(shots) >= n_shots:
            break
        key_s = (src["wi"], src["di"])
        if key_s in used:
            continue
        # Pick a target that isn't the same box and is in a different column
        others = [b for b in all_boxes
                  if abs(b["wi"] - src["wi"]) >= 3
                  and (b["wi"], b["di"]) != key_s
                  and (b["wi"], b["di"]) not in used]
        if not others:
            continue
        tgt = random.choice(others)
        key_t = (tgt["wi"], tgt["di"])
        used.add(key_s)
        used.add(key_t)
        shots.append((src, tgt))

    # ── Timing ────────────────────────────────────────────────────────────
    SHOT_GAP   = 1.6   # seconds between each shot
    BOLT_DUR   = 0.38  # seconds for bolt to travel
    HIT_DUR    = 0.50  # seconds for hit flash
    CYCLE      = SHOT_GAP * len(shots)
    REPEATS    = 25

    def begins(offset: float) -> str:
        return ";".join(f"{offset + k * CYCLE:.2f}s" for k in range(REPEATS))

    # ── Month labels ─────────────────────────────────────────────────────
    seen_months: dict = {}
    for wi, week in enumerate(weeks):
        if week["contributionDays"]:
            d = datetime.strptime(week["contributionDays"][0]["date"], "%Y-%m-%d")
            m = d.strftime("%b")
            if m not in seen_months:
                seen_months[m] = wi

    # ──────────────────────────────────────────────────────────────────────
    # ASSEMBLE SVG
    # ──────────────────────────────────────────────────────────────────────
    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {SVG_W} {SVG_H}" width="{SVG_W}" height="{SVG_H}">'
    )

    # ── Defs ─────────────────────────────────────────────────────────────
    out.append("""<defs>
  <!-- Laser glow -->
  <filter id="lg" x="-50%" y="-200%" width="200%" height="500%">
    <feGaussianBlur stdDeviation="1.8" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <!-- Hit explosion glow -->
  <filter id="hg" x="-100%" y="-100%" width="300%" height="300%">
    <feGaussianBlur stdDeviation="4" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>""")

    # ── Background ───────────────────────────────────────────────────────
    out.append(f'<rect width="{SVG_W}" height="{SVG_H}" fill="#0d1117"/>')

    # ── Month labels ─────────────────────────────────────────────────────
    for month, wi in seen_months.items():
        mx = PAD_X + wi * STEP
        out.append(
            f'<text x="{mx}" y="17" '
            f'font-family="\'Segoe UI\',Arial,sans-serif" '
            f'font-size="9" fill="#30363d">{month}</text>'
        )

    # ── Contribution grid ────────────────────────────────────────────────
    for b in all_boxes:
        out.append(
            f'<rect x="{b["x"]}" y="{b["y"]}" '
            f'width="{BOX}" height="{BOX}" rx="2" fill="{b["color"]}"/>'
        )

    # ── Laser shots ──────────────────────────────────────────────────────
    for i, (src, tgt) in enumerate(shots):
        t0 = i * SHOT_GAP

        sx, sy = src["cx"], src["cy"]
        tx, ty = tgt["cx"], tgt["cy"]

        # Length and angle for the bolt rect
        dx   = tx - sx
        dy   = ty - sy
        dist = math.hypot(dx, dy)
        ang  = math.degrees(math.atan2(dy, dx))

        bolt_w  = min(dist * 0.55, 55)   # bolt length ≈ half the distance, capped
        bolt_h  = 2.2

        # Bolt: starts at source, travels to just before target
        # We animate the x position (pre-rotated) via transform
        # Easier: use a <line> with stroke-dasharray/dashoffset trick

        # ── Approach: animated line using dashoffset ───────────────────
        # dash = total length, offset goes from +length → 0 (reveal) → -length (erase)
        # This makes the line "draw" from source to target, then erase
        dash   = round(dist, 1)

        # Draw phase: dashoffset from +dash to 0
        # Erase phase: dashoffset from 0 to -dash
        # We'll do: draw (0→BOLT_DUR*0.6), hold briefly, erase (BOLT_DUR*0.6→BOLT_DUR)
        draw_t  = round(BOLT_DUR * 0.55, 3)
        erase_t = round(BOLT_DUR * 0.45, 3)

        bolt_starts  = begins(t0)
        hit_starts   = begins(t0 + draw_t)

        # Core laser line (bright)
        out.append(
            f'<line x1="{sx}" y1="{sy}" x2="{tx}" y2="{ty}" '
            f'stroke="#ff3333" stroke-width="1.8" '
            f'stroke-dasharray="{dash}" stroke-dashoffset="{dash}" '
            f'filter="url(#lg)" opacity="0">'
            # Reveal the line
            f'<animate attributeName="stroke-dashoffset" '
            f'values="{dash};0" dur="{draw_t}s" begin="{bolt_starts}" fill="freeze"/>'
            # Erase the line
            f'<animate attributeName="stroke-dashoffset" '
            f'values="0;{-dash}" dur="{erase_t}s" begin="{begins(t0 + draw_t)}" fill="freeze"/>'
            # Opacity
            f'<animate attributeName="opacity" '
            f'values="0;0.95;0.95;0" keyTimes="0;0.05;0.88;1" '
            f'dur="{BOLT_DUR}s" begin="{bolt_starts}" fill="freeze"/>'
            f'</line>'
        )

        # Bright white core (thinner, no filter)
        out.append(
            f'<line x1="{sx}" y1="{sy}" x2="{tx}" y2="{ty}" '
            f'stroke="#ffaaaa" stroke-width="0.7" '
            f'stroke-dasharray="{dash}" stroke-dashoffset="{dash}" '
            f'opacity="0">'
            f'<animate attributeName="stroke-dashoffset" '
            f'values="{dash};0" dur="{draw_t}s" begin="{bolt_starts}" fill="freeze"/>'
            f'<animate attributeName="stroke-dashoffset" '
            f'values="0;{-dash}" dur="{erase_t}s" begin="{begins(t0 + draw_t)}" fill="freeze"/>'
            f'<animate attributeName="opacity" '
            f'values="0;1;1;0" keyTimes="0;0.05;0.85;1" '
            f'dur="{BOLT_DUR}s" begin="{bolt_starts}" fill="freeze"/>'
            f'</line>'
        )

        # Hit glow (outer)
        out.append(
            f'<circle cx="{tx}" cy="{ty}" r="3" fill="#ff2222" opacity="0" filter="url(#hg)">'
            f'<animate attributeName="r" values="2;14;2" '
            f'keyTimes="0;0.35;1" dur="{HIT_DUR}s" begin="{hit_starts}" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0;0.9;0" '
            f'keyTimes="0;0.25;1" dur="{HIT_DUR}s" begin="{hit_starts}" fill="freeze"/>'
            f'</circle>'
        )

        # Hit inner bright dot
        out.append(
            f'<circle cx="{tx}" cy="{ty}" r="2.5" fill="#ffffff" opacity="0">'
            f'<animate attributeName="opacity" values="0;1;0" '
            f'keyTimes="0;0.2;1" dur="0.3s" begin="{hit_starts}" fill="freeze"/>'
            f'</circle>'
        )

    out.append('</svg>')
    return "\n".join(out)


if __name__ == "__main__":
    token    = os.environ.get("GITHUB_TOKEN")
    username = os.environ.get("GITHUB_USER", "Atharv12377")

    if not token:
        raise SystemExit("GITHUB_TOKEN env var is required")

    print(f"Fetching contributions for {username} …")
    calendar = fetch_contributions(username, token)
    print(f"Total contributions: {calendar['totalContributions']}")

    svg = generate_svg(calendar)

    os.makedirs("dist", exist_ok=True)
    out_path = os.path.join("dist", "github-blaster.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"Saved → {out_path}")
