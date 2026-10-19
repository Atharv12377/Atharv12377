#!/usr/bin/env python3
"""
generate_blaster.py
Fetches the GitHub contribution graph and generates an animated
Star Wars E-11 blaster SVG that fires laser bolts at the boxes.
"""

import os
import json
import random
import requests
from datetime import datetime

# ── Color mapping (dark GitHub theme) ──────────────────────────────────────
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
    data = resp.json()
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def generate_svg(calendar: dict, seed: int = 42) -> str:
    random.seed(seed)

    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    # Layout constants
    BOX   = 10   # box size px
    GAP   = 3    # gap between boxes
    STEP  = BOX + GAP

    GUN_AREA_W  = 178   # horizontal space reserved for the gun
    GRAPH_X0    = GUN_AREA_W + 10
    GRAPH_Y0    = 28    # top of graph (below month labels)
    GUN_TIP_X   = GUN_AREA_W - 2   # where bolts originate
    GUN_BARREL_Y = 62   # y-centre of gun barrel

    N_WEEKS = len(weeks)
    N_DAYS  = max(len(w["contributionDays"]) for w in weeks)

    SVG_W = GRAPH_X0 + N_WEEKS * STEP + 20
    SVG_H = GRAPH_Y0 + N_DAYS * STEP + 32

    # ── Build list of all boxes ───────────────────────────────────────────
    all_boxes = []
    for wi, week in enumerate(weeks):
        for di, day in enumerate(week["contributionDays"]):
            bx = GRAPH_X0 + wi * STEP
            by = GRAPH_Y0 + di * STEP
            color = LEVEL_COLORS.get(day["contributionLevel"], "#161b22")
            all_boxes.append({
                "x": bx, "y": by, "cx": bx + BOX // 2, "cy": by + BOX // 2,
                "color": color, "count": day["contributionCount"],
            })

    # ── Pick shooting targets: prefer boxes with contributions ────────────
    hot  = [b for b in all_boxes if b["count"] > 0]
    cold = [b for b in all_boxes if b["count"] == 0]
    pool = hot if len(hot) >= 10 else (hot + cold)
    n_targets = min(14, len(pool))
    targets = sorted(random.sample(pool, n_targets), key=lambda b: b["cx"])

    # ── Animation timing ─────────────────────────────────────────────────
    SHOT_INTERVAL = 1.8   # seconds between shots
    BOLT_DUR      = 0.45  # seconds for bolt to travel
    CYCLE         = SHOT_INTERVAL * len(targets)
    REPEATS       = 20    # enough loops for a long session

    def begin_list(offset: float, extra: float = 0.0) -> str:
        times = [f"{offset + extra + k * CYCLE:.2f}s" for k in range(REPEATS)]
        return ";".join(times)

    # ── Month labels ─────────────────────────────────────────────────────
    seen_months: dict = {}
    for wi, week in enumerate(weeks):
        if week["contributionDays"]:
            d = datetime.strptime(week["contributionDays"][0]["date"], "%Y-%m-%d")
            m = d.strftime("%b")
            if m not in seen_months:
                seen_months[m] = wi

    # ──────────────────────────────────────────────────────────────────────
    # BUILD SVG
    # ──────────────────────────────────────────────────────────────────────
    out = []

    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {SVG_W} {SVG_H}" width="{SVG_W}" height="{SVG_H}">'
    )

    # ── Defs ─────────────────────────────────────────────────────────────
    out.append("""<defs>
  <filter id="lg"><feGaussianBlur stdDeviation="2.5" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="hg"><feGaussianBlur stdDeviation="5" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="gs"><feDropShadow dx="0" dy="1" stdDeviation="3"
    flood-color="#ff2222" flood-opacity="0.35"/></filter>
  <linearGradient id="bolt" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0"   stop-color="#ff4444" stop-opacity="0"/>
    <stop offset="0.3" stop-color="#ff2222" stop-opacity="1"/>
    <stop offset="0.7" stop-color="#ffcccc" stop-opacity="1"/>
    <stop offset="1"   stop-color="#ff2222" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="gun-g" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#2e2e40"/>
    <stop offset="1" stop-color="#16161f"/>
  </linearGradient>
</defs>""")

    # ── Background ───────────────────────────────────────────────────────
    out.append(f'<rect width="{SVG_W}" height="{SVG_H}" fill="#0d1117"/>')

    # ── Month labels ─────────────────────────────────────────────────────
    for month, wi in seen_months.items():
        mx = GRAPH_X0 + wi * STEP
        out.append(
            f'<text x="{mx}" y="20" '
            f'font-family="\'Segoe UI\',Arial,sans-serif" '
            f'font-size="9" fill="#444860">{month}</text>'
        )

    # ── Contribution grid ────────────────────────────────────────────────
    for b in all_boxes:
        out.append(
            f'<rect x="{b["x"]}" y="{b["y"]}" '
            f'width="{BOX}" height="{BOX}" rx="2" fill="{b["color"]}"/>'
        )

    # ── Laser bolts + hit effects ─────────────────────────────────────────
    for i, t in enumerate(targets):
        t_begin  = i * SHOT_INTERVAL
        h_begin  = t_begin + BOLT_DUR - 0.05

        bolt_starts = begin_list(t_begin)
        hit_starts  = begin_list(h_begin)
        bright_starts = begin_list(h_begin)

        bx_start = GUN_TIP_X
        bx_end   = t["cx"] - 28
        by       = GUN_BARREL_Y - 1.5   # bolt y follows barrel, not target row
        # (looks like it's fired horizontally; target y just receives the hit)

        # Bolt
        out.append(
            f'<rect x="{bx_start}" y="{by:.1f}" width="55" height="3" rx="1.5" '
            f'fill="url(#bolt)" filter="url(#lg)" opacity="0">'
            f'<animate attributeName="x" values="{bx_start};{bx_end}" '
            f'dur="{BOLT_DUR}s" begin="{bolt_starts}" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" '
            f'keyTimes="0;0.05;0.88;1" dur="{BOLT_DUR}s" begin="{bolt_starts}" fill="freeze"/>'
            f'</rect>'
        )

        # Hit glow
        out.append(
            f'<circle cx="{t["cx"]}" cy="{t["cy"]}" r="4" '
            f'fill="#ff4444" opacity="0" filter="url(#hg)">'
            f'<animate attributeName="r"       values="3;13;3" '
            f'keyTimes="0;0.35;1" dur="0.55s" begin="{hit_starts}" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0;0.95;0" '
            f'keyTimes="0;0.3;1"  dur="0.55s" begin="{hit_starts}" fill="freeze"/>'
            f'</circle>'
        )

        # Bright inner dot
        out.append(
            f'<circle cx="{t["cx"]}" cy="{t["cy"]}" r="2.5" fill="#ffeeaa" opacity="0">'
            f'<animate attributeName="opacity" values="0;1;0" '
            f'keyTimes="0;0.2;1" dur="0.4s" begin="{bright_starts}" fill="freeze"/>'
            f'</circle>'
        )

    # ── E-11 Blaster gun ─────────────────────────────────────────────────
    # Positioned so barrel tip is at (GUN_TIP_X, GUN_BARREL_Y)
    GX = 6
    GY = GUN_BARREL_Y - 26   # align barrel centre

    # Build muzzle-flash begin list (fires on every shot)
    flash_begins = begin_list(0.0)

    out.append(f'<g transform="translate({GX},{GY})" filter="url(#gs)">')

    # Main barrel
    out.append(
        '<rect x="30" y="22" width="130" height="9" rx="3" '
        'fill="url(#gun-g)" stroke="#3a3a52" stroke-width="0.8"/>'
    )
    # Muzzle narrowing
    out.append(
        '<rect x="158" y="24" width="16" height="5" rx="2" '
        'fill="#1a1a2a" stroke="#55556a" stroke-width="0.5"/>'
    )
    # Scope
    out.append(
        '<rect x="62" y="13" width="54" height="10" rx="2" '
        'fill="#1e1e30" stroke="#3a3a52" stroke-width="0.7"/>'
    )
    out.append('<rect x="67" y="15" width="7" height="6" rx="1" fill="#12121e"/>')
    out.append('<rect x="101" y="15" width="7" height="6" rx="1" fill="#12121e"/>')

    # Handle / grip
    out.append(
        '<rect x="50" y="30" width="19" height="28" rx="3" '
        'fill="#1e1e30" stroke="#3a3a52" stroke-width="0.7"/>'
    )
    for ly in range(36, 56, 5):
        out.append(f'<line x1="53" y1="{ly}" x2="66" y2="{ly}" stroke="#2a2a3e" stroke-width="0.6"/>')

    # Stock
    out.append(
        '<rect x="24" y="20" width="30" height="15" rx="3" '
        'fill="#191928" stroke="#3a3a52" stroke-width="0.7"/>'
    )

    # Power cell indicator (pulses red)
    cell_dur = f"{SHOT_INTERVAL:.2f}s"
    out.append(
        f'<rect x="82" y="25" width="12" height="5" rx="1" fill="#ff2222" opacity="0.18">'
        f'<animate attributeName="opacity" values="0.12;0.9;0.12" dur="{cell_dur}" repeatCount="indefinite"/>'
        f'</rect>'
    )

    # Detail seam lines
    out.append('<line x1="30" y1="27" x2="155" y2="27" stroke="#2e2e42" stroke-width="0.5"/>')
    out.append('<line x1="30" y1="31" x2="155" y2="31" stroke="#2e2e42" stroke-width="0.5"/>')

    # Trigger
    out.append(
        '<path d="M 60 31 L 65 47 L 68 47 L 63 31 Z" '
        'fill="#1a1a2a" stroke="#3a3a52" stroke-width="0.5"/>'
    )

    # Muzzle flash (outer + inner)
    out.append(
        f'<ellipse cx="170" cy="26.5" rx="10" ry="6" fill="#ff7733" opacity="0">'
        f'<animate attributeName="opacity" values="0;0.95;0" dur="0.18s" begin="{flash_begins}" fill="freeze"/>'
        f'</ellipse>'
    )
    out.append(
        f'<ellipse cx="170" cy="26.5" rx="5" ry="3" fill="#ffffbb" opacity="0">'
        f'<animate attributeName="opacity" values="0;1;0" dur="0.14s" begin="{flash_begins}" fill="freeze"/>'
        f'</ellipse>'
    )

    out.append('</g>')  # end gun group

    # ── Bottom label ─────────────────────────────────────────────────────
    out.append(
        f'<text x="{GX + 8}" y="{SVG_H - 6}" '
        f'font-family="\'Courier New\',monospace" font-size="8" '
        f'fill="#2e2e42" letter-spacing="1">'
        f'IMPERIAL E-11  ·  BLASTER ENGAGED  ·  '
        f'{total} CONTRIBUTIONS</text>'
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

    svg_content = generate_svg(calendar)

    os.makedirs("dist", exist_ok=True)
    out_path = os.path.join("dist", "github-blaster.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    print(f"Saved → {out_path}")
