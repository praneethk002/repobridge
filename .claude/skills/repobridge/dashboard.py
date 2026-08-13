#!/usr/bin/env python3
"""RepoBridge dashboard: turns the SKILL.md JSON sidecar into a static,
self-contained HTML report. Stdlib only — no server, no build step, no CDN.
Open the generated file directly in a browser.

Accepts two input shapes:
  - a dict with "idea"/"requirements"/"repos" (the SKILL.md sidecar) ->
    full dashboard: hero card for the best pick, headline stats, and a
    secondary comparison against the other candidates
  - a plain list (raw `scout.py enrich` output, no ranking/coverage data)
    -> stats-only comparison charts, no hero (nothing to crown as "best")

`repos` is expected pre-sorted best-first — this script does not re-rank;
the winner is whichever repo Claude put first in Step 5 of SKILL.md.

--print-stats prints the same headline numbers the hero card shows, as
JSON, without writing HTML — SKILL.md uses this so the numbers in the
markdown report and the dashboard can never drift apart (one formula,
read twice, not recomputed by hand in two places).
"""

import argparse
import html
import json
import sys
from pathlib import Path

GOOD, WARNING, CRITICAL, MUTED = "#0ca30c", "#fab219", "#d03b3b", "#898781"
SEQUENTIAL_BLUE = "#3987e5"

# Headline-stat heuristics. These are illustrative order-of-magnitude
# estimates, not measurements — see the methodology note rendered beside
# them. Adjust here if they're consistently off for your kind of project.
HOURS_PER_MISSING_FEATURE = 8   # ~1 focused day to build + integrate a typical feature from scratch
HOURS_PER_PARTIAL_FEATURE = 3   # finishing something already scaffolded costs less
HOURS_PER_DAY = 6               # focused dev hours/day, for the days conversion
TOKENS_PER_FEATURE = 15_000     # rough LLM tokens (incl. iteration) to generate one feature from scratch
PARTIAL_TOKEN_FRACTION = 0.5    # a partial feature needs roughly half that generation work


def load_data(path):
    raw = json.loads(Path(path).read_text())
    if isinstance(raw, list):
        return {"idea": None, "requirements": [], "repos": raw, "pick_rationale": None}
    return raw


def esc(value):
    return html.escape(str(value if value is not None else ""))


def format_compact(n):
    n = round(n)
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def coverage_bucket(pct):
    if pct >= 70:
        return "Strong fit", GOOD
    if pct >= 40:
        return "Partial fit", WARNING
    return "Weak fit", CRITICAL


def compute_headline_stats(data):
    repos = data.get("repos", [])
    requirements = data.get("requirements", [])
    if not repos or not requirements:
        return None

    best = repos[0]
    statuses = best.get("requirement_status")
    if not statuses:
        return None

    missing = sum(1 for s in statuses.values() if s.get("status") == "missing")
    partial = sum(1 for s in statuses.values() if s.get("status") == "partial")
    present = sum(1 for s in statuses.values() if s.get("status") == "present")
    total = len(requirements)

    hours = missing * HOURS_PER_MISSING_FEATURE + partial * HOURS_PER_PARTIAL_FEATURE
    tokens_full_build = total * TOKENS_PER_FEATURE
    tokens_remaining = (missing + partial * PARTIAL_TOKEN_FRACTION) * TOKENS_PER_FEATURE
    tokens_saved = max(0, tokens_full_build - tokens_remaining)

    return {
        "best_pick": best["full_name"],
        "match_pct": best.get("coverage_pct", 0.0),
        "features_present": present,
        "features_partial": partial,
        "features_missing": missing,
        "features_left": missing + partial,
        "features_total": total,
        "estimated_hours_remaining": hours,
        "estimated_days_remaining": round(hours / HOURS_PER_DAY, 1),
        "estimated_tokens_saved": round(tokens_saved),
        "estimated_tokens_saved_pct": round(tokens_saved / tokens_full_build * 100, 1) if tokens_full_build else 0.0,
        "methodology_note": (
            f"Estimate, not a measurement: {HOURS_PER_MISSING_FEATURE}h per missing feature, "
            f"{HOURS_PER_PARTIAL_FEATURE}h per partial one; token savings assume ~{TOKENS_PER_FEATURE:,} "
            "tokens to generate one feature from scratch, at half that for a partial. Actual time and "
            "token cost depend heavily on your stack and the specific features."
        ),
    }


def stat_tile(label, value, sublabel=""):
    return f"""
        <div class="stat-tile">
          <div class="stat-value">{value}</div>
          <div class="stat-label">{esc(label)}</div>
          {f'<div class="stat-sublabel">{esc(sublabel)}</div>' if sublabel else ''}
        </div>"""


def hero_section(data, stats):
    repos = data.get("repos", [])
    best = repos[0]
    rationale = data.get("pick_rationale")
    match_pct = stats["match_pct"]
    _, match_color = coverage_bucket(match_pct)

    tiles = "".join([
        stat_tile("Match", f"{match_pct:.0f}%"),
        stat_tile("Features left", str(stats["features_left"]),
                   f"of {stats['features_total']} total"),
        stat_tile("Est. time remaining", f"{stats['estimated_days_remaining']:g}d",
                   f"~{stats['estimated_hours_remaining']:g}h"),
        stat_tile("Tokens saved", format_compact(stats["estimated_tokens_saved"]),
                   f"~{stats['estimated_tokens_saved_pct']:.0f}% vs. building from scratch"),
    ])

    return f"""
    <section class="hero">
      <div class="hero-kicker">Best match</div>
      <h2 class="hero-name"><a href="{esc(best.get('url', '#'))}">{esc(best['full_name'])}</a></h2>
      {f'<p class="hero-rationale">{esc(rationale)}</p>' if rationale else ''}
      <div class="stat-grid">{tiles}</div>
      <p class="methodology">{esc(stats["methodology_note"])}</p>
    </section>"""


def winner_checklist(best, requirements):
    icon_style = {
        "present": (GOOD, "✓"),
        "partial": (WARNING, "~"),
        "missing": (MUTED, "–"),
    }
    statuses = best.get("requirement_status", {})
    rows = []
    for req in requirements:
        entry = statuses.get(req, {"status": "missing", "evidence": ""})
        color, icon = icon_style.get(entry.get("status", "missing"), icon_style["missing"])
        evidence = entry.get("evidence", "")
        rows.append(f"""
        <div class="checklist-row">
          <span class="checklist-icon" style="background:{color};">{icon}</span>
          <span class="checklist-req">{esc(req)}</span>
          <span class="checklist-evidence">{esc(evidence) if evidence else '<em>Not covered</em>'}</span>
        </div>""")
    return f"""
    <section class="panel">
      <h3>What {esc(best['full_name'])} covers</h3>
      {"".join(rows)}
    </section>"""


def metric_bar_chart(title, subtitle, repos, key, max_value, color):
    rows = []
    for r in repos:
        value = r.get(key)
        if value is None:
            continue
        frac = 0.0 if max_value == 0 else min(value / max_value, 1.0)
        rows.append(f"""
        <div class="bar-row" title="{esc(r['full_name'])}: {esc(value)}">
          <div class="bar-label">{esc(r['full_name'])}</div>
          <div class="bar-track">
            <div class="bar-fill" style="width:{frac * 100:.1f}%; background:{color};"></div>
          </div>
          <div class="bar-value">{esc(value)}</div>
        </div>""")
    return f"""
    <section class="panel">
      <h3>{esc(title)}</h3>
      <p class="panel-subtitle">{esc(subtitle)}</p>
      {"".join(rows) if rows else '<p class="empty">No data for this metric.</p>'}
    </section>"""


def coverage_chart(repos):
    rows = []
    for r in repos:
        pct = r.get("coverage_pct")
        if pct is None:
            continue
        label, color = coverage_bucket(pct)
        rows.append(f"""
        <div class="bar-row" title="{esc(r['full_name'])}: {pct:.0f}% coverage ({label})">
          <div class="bar-label">{esc(r['full_name'])}</div>
          <div class="bar-track">
            <div class="bar-fill" style="width:{pct:.1f}%; background:{color};"></div>
          </div>
          <div class="bar-value status-label" style="color:{color};">{pct:.0f}% &middot; {label}</div>
        </div>""")
    if not rows:
        return ""
    return f"""
    <section class="panel">
      <h3>Idea coverage, all candidates</h3>
      <p class="panel-subtitle">Present + half-credit Partial, as a share of stated requirements.</p>
      {"".join(rows)}
    </section>"""


def requirement_grid(repos, requirements):
    if not requirements or not any(r.get("requirement_status") for r in repos):
        return ""
    status_style = {
        "present": (GOOD, "✓ Present"),
        "partial": (WARNING, "~ Partial"),
        "missing": (MUTED, "– Missing"),
    }
    header_cells = "".join(f"<th>{esc(req)}</th>" for req in requirements)
    body_rows = []
    for r in repos:
        statuses = r.get("requirement_status", {})
        cells = []
        for req in requirements:
            entry = statuses.get(req, {"status": "missing", "evidence": ""})
            color, text = status_style.get(entry.get("status", "missing"), status_style["missing"])
            evidence = esc(entry.get("evidence", ""))
            cells.append(
                f'<td><span class="pill" style="background:{color};" title="{evidence}">{text}</span></td>'
            )
        body_rows.append(f"<tr><th>{esc(r['full_name'])}</th>{''.join(cells)}</tr>")
    return f"""
    <section class="panel">
      <h3>Full feature-map grid</h3>
      <p class="panel-subtitle">Hover a cell for the evidence quote behind it.</p>
      <div class="table-scroll">
        <table class="grid-table">
          <thead><tr><th></th>{header_cells}</tr></thead>
          <tbody>{"".join(body_rows)}</tbody>
        </table>
      </div>
    </section>"""


def data_table(repos):
    rows = []
    for r in repos:
        rows.append(f"""
        <tr>
          <td><a href="{esc(r.get('url', '#'))}">{esc(r['full_name'])}</a></td>
          <td class="num">{esc(r.get('stars', '—'))}</td>
          <td>{esc(r.get('license_spdx') or '—')}</td>
          <td>{esc((r.get('pushed_at') or '')[:10] or '—')}</td>
          <td class="num">{esc(r.get('verified_score', '—'))}</td>
          <td class="num">{esc(r.get('deployability_score', '—'))}</td>
          <td class="num">{f"{r['coverage_pct']:.0f}%" if r.get('coverage_pct') is not None else '—'}</td>
        </tr>""")
    return f"""
    <section class="panel">
      <h3>All candidates</h3>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr><th>Repo</th><th class="num">Stars</th><th>License</th><th>Last commit</th>
                <th class="num">Verified</th><th class="num">Deployability</th><th class="num">Coverage</th></tr>
          </thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </div>
    </section>"""


def render_page(data):
    repos = data.get("repos", [])
    idea = data.get("idea")
    requirements = data.get("requirements", [])
    max_stars = max((r.get("stars", 0) for r in repos), default=0) or 1
    stats = compute_headline_stats(data)

    title = f"RepoBridge: {esc(idea)}" if idea else "RepoBridge dashboard"

    top_sections = ""
    if stats:
        top_sections = hero_section(data, stats) + winner_checklist(repos[0], requirements)

    secondary_sections = [
        metric_bar_chart("Stars", "Linear scale, capped to the highest-starred candidate shown.",
                          repos, "stars", max_stars, SEQUENTIAL_BLUE),
        metric_bar_chart("Verified score", "Recency + contributor count + CI presence, 0-100.",
                          repos, "verified_score", 100, SEQUENTIAL_BLUE),
        metric_bar_chart("Deployability score", "Docker/compose + .env.example + deploy button, 0-100.",
                          repos, "deployability_score", 100, SEQUENTIAL_BLUE),
        coverage_chart(repos),
        requirement_grid(repos, requirements),
        data_table(repos),
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    color-scheme: dark;
    --bg: #0a0b0c;
    --surface: #131517;
    --surface-2: #1b1e21;
    --text-primary: #f4f5f5;
    --text-secondary: #a8adb3;
    --muted: #6b7075;
    --gridline: #24272b;
    --border: rgba(255,255,255,0.08);
    --accent: #3987e5;
    --accent-soft: rgba(57,135,229,0.14);
  }}
  @media (prefers-color-scheme: light) {{
    :root:not([data-theme="dark"]) {{
      color-scheme: light;
      --bg: #f9f9f7;
      --surface: #ffffff;
      --surface-2: #f3f3f1;
      --text-primary: #0b0b0b;
      --text-secondary: #52514e;
      --muted: #898781;
      --gridline: #e1e0d9;
      --border: rgba(11,11,11,0.08);
      --accent: #2a78d6;
      --accent-soft: rgba(42,120,214,0.10);
    }}
  }}
  :root[data-theme="light"] {{
    color-scheme: light;
    --bg: #f9f9f7;
    --surface: #ffffff;
    --surface-2: #f3f3f1;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --muted: #898781;
    --gridline: #e1e0d9;
    --border: rgba(11,11,11,0.08);
    --accent: #2a78d6;
    --accent-soft: rgba(42,120,214,0.10);
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --bg: #0a0b0c;
    --surface: #131517;
    --surface-2: #1b1e21;
    --text-primary: #f4f5f5;
    --text-secondary: #a8adb3;
    --muted: #6b7075;
    --gridline: #24272b;
    --border: rgba(255,255,255,0.08);
    --accent: #3987e5;
    --accent-soft: rgba(57,135,229,0.14);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    line-height: 1.45;
  }}
  .page {{ max-width: 880px; margin: 0 auto; padding: 40px 20px 72px; }}
  .masthead {{ display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }}
  .wordmark {{ font-size: 0.85rem; font-weight: 600; letter-spacing: 0.04em; color: var(--muted); text-transform: uppercase; }}
  .meta {{ color: var(--muted); font-size: 0.8rem; }}
  .query-pill {{
    display: inline-block; background: var(--surface); border: 1px solid var(--border);
    border-radius: 999px; padding: 10px 20px; font-size: 1rem; color: var(--text-secondary);
    margin-bottom: 28px;
  }}
  .hero {{
    background: linear-gradient(180deg, var(--accent-soft), transparent 60%), var(--surface);
    border: 1px solid var(--border);
    border-top: 2px solid var(--accent);
    border-radius: 16px;
    padding: 28px 28px 22px;
    margin-bottom: 20px;
  }}
  .hero-kicker {{ font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--accent); margin-bottom: 8px; }}
  .hero-name {{ margin: 0 0 10px; font-size: 1.7rem; text-wrap: balance; }}
  .hero-name a {{ color: var(--text-primary); text-decoration: none; }}
  .hero-name a:hover {{ text-decoration: underline; }}
  .hero-rationale {{ color: var(--text-secondary); font-size: 0.98rem; max-width: 60ch; margin: 0 0 22px; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; background: var(--border); border-radius: 12px; overflow: hidden; }}
  .stat-tile {{ background: var(--surface-2); padding: 16px 14px; }}
  .stat-value {{ font-size: 1.6rem; font-weight: 700; font-variant-numeric: tabular-nums; }}
  .stat-label {{ font-size: 0.76rem; color: var(--text-secondary); margin-top: 2px; }}
  .stat-sublabel {{ font-size: 0.7rem; color: var(--muted); margin-top: 1px; }}
  .methodology {{ font-size: 0.72rem; color: var(--muted); margin: 14px 2px 0; line-height: 1.5; }}
  .panel {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 16px;
  }}
  .panel h3 {{ margin: 0 0 2px; font-size: 0.95rem; }}
  .panel-subtitle {{ color: var(--muted); font-size: 0.78rem; margin: 0 0 14px; }}
  .checklist-row {{ display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--gridline); }}
  .checklist-row:last-child {{ border-bottom: none; }}
  .checklist-icon {{
    flex: 0 0 auto; width: 20px; height: 20px; border-radius: 50%; color: #fff;
    display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700;
  }}
  .checklist-req {{ flex: 0 0 180px; font-size: 0.85rem; font-weight: 600; }}
  .checklist-evidence {{ flex: 1; font-size: 0.83rem; color: var(--text-secondary); }}
  .checklist-evidence em {{ color: var(--muted); font-style: normal; }}
  .section-label {{ font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); margin: 32px 2px 12px; }}
  .bar-row {{ display: flex; align-items: center; gap: 10px; padding: 3px 0; }}
  .bar-label {{
    width: 34%; min-width: 120px; font-size: 0.82rem; color: var(--text-secondary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }}
  .bar-track {{ flex: 1; height: 18px; background: var(--gridline); border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 0 4px 4px 0; min-width: 3px; }}
  .bar-value {{ width: 110px; text-align: right; font-size: 0.8rem; color: var(--text-secondary); font-variant-numeric: tabular-nums; }}
  .status-label {{ font-weight: 600; }}
  .empty {{ color: var(--muted); font-size: 0.85rem; }}
  .table-scroll {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.8rem; }}
  th, td {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--gridline); white-space: nowrap; }}
  th {{ color: var(--muted); font-weight: 600; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.02em; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  a {{ color: var(--accent); }}
  .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; color: #fff; font-size: 0.7rem; font-weight: 600; white-space: nowrap; }}
  .grid-table th {{ white-space: normal; }}
  footer {{ margin-top: 32px; color: var(--muted); font-size: 0.75rem; text-align: center; }}
  @media (max-width: 620px) {{
    .stat-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .checklist-row {{ flex-direction: column; gap: 2px; }}
    .checklist-req {{ flex: none; }}
  }}
</style>
</head>
<body>
  <div class="page">
    <div class="masthead">
      <span class="wordmark">RepoBridge</span>
      <span class="meta">{len(repos)} candidate{'s' if len(repos) != 1 else ''}{' &middot; ' + esc(data.get('generated_at')) if data.get('generated_at') else ''} &middot; no network calls at render time</span>
    </div>
    {f'<div class="query-pill">{esc(idea)}</div>' if idea else ''}
    {top_sections}
    <div class="section-label">Compared against</div>
    {"".join(secondary_sections)}
    <footer>Generated by RepoBridge from real GitHub data — see the matching .md report for full source citations.</footer>
  </div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate a static HTML dashboard from RepoBridge JSON output.")
    parser.add_argument("input", help="path to a scout.py enrich JSON array, or a SKILL.md sidecar JSON")
    parser.add_argument("--out", help="output HTML path (default: <input>.html)")
    parser.add_argument("--print-stats", action="store_true",
                         help="print the headline stats as JSON instead of writing HTML")
    args = parser.parse_args()

    data = load_data(args.input)

    if args.print_stats:
        stats = compute_headline_stats(data)
        if stats is None:
            print("error: no coverage/requirement data in this file — nothing to summarize", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(stats, indent=2))
        return

    out_path = Path(args.out) if args.out else Path(args.input).with_suffix(".html")
    out_path.write_text(render_page(data))
    print(f"wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
