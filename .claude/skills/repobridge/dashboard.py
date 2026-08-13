#!/usr/bin/env python3
"""RepoBridge dashboard: turns scout.py/SKILL.md JSON output into a static,
self-contained HTML report. Stdlib only — no server, no build step, no CDN.
Open the generated file directly in a browser.

Accepts two input shapes:
  - a plain list (raw `scout.py enrich` output) -> stats-only dashboard
  - a dict with "idea"/"requirements"/"repos" (the SKILL.md sidecar,
    written alongside the markdown report) -> full dashboard, including
    the coverage and requirement-status grid the markdown report describes
"""

import argparse
import html
import json
import sys
from pathlib import Path

GOOD, WARNING, CRITICAL, MUTED = "#0ca30c", "#fab219", "#d03b3b", "#898781"
SEQUENTIAL_BLUE = "#2a78d6"


def load_data(path):
    raw = json.loads(Path(path).read_text())
    if isinstance(raw, list):
        return {"idea": None, "requirements": [], "repos": raw}
    return raw


def coverage_bucket(pct):
    if pct >= 70:
        return "Strong fit", GOOD
    if pct >= 40:
        return "Partial fit", WARNING
    return "Weak fit", CRITICAL


def esc(value):
    return html.escape(str(value if value is not None else ""))


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
    <section class="chart">
      <h3>{esc(title)}</h3>
      <p class="chart-subtitle">{esc(subtitle)}</p>
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
    <section class="chart">
      <h3>Idea coverage</h3>
      <p class="chart-subtitle">Present + half-credit Partial, as a share of stated requirements. Bucketed at &ge;70% strong / &ge;40% partial / below critical.</p>
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
    <section class="chart">
      <h3>Feature-map grid</h3>
      <p class="chart-subtitle">Hover a cell for the evidence quote behind it.</p>
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
    <section class="chart">
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

    title = f"RepoBridge: {esc(idea)}" if idea else "RepoBridge dashboard"
    sections = [
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
    color-scheme: light;
    --surface: #fcfcfb;
    --page: #f9f9f7;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --muted: #898781;
    --gridline: #e1e0d9;
    --border: rgba(11,11,11,0.10);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      color-scheme: dark;
      --surface: #1a1a19;
      --page: #0d0d0d;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --muted: #898781;
      --gridline: #2c2c2a;
      --border: rgba(255,255,255,0.10);
    }}
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --surface: #1a1a19;
    --page: #0d0d0d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --muted: #898781;
    --gridline: #2c2c2a;
    --border: rgba(255,255,255,0.10);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--page);
    color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    line-height: 1.4;
  }}
  .page {{ max-width: 900px; margin: 0 auto; padding: 32px 20px 64px; }}
  h1 {{ font-size: 1.4rem; margin: 0 0 4px; }}
  .meta {{ color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 28px; }}
  .chart {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
  }}
  .chart h3 {{ margin: 0 0 2px; font-size: 1rem; }}
  .chart-subtitle {{ color: var(--muted); font-size: 0.8rem; margin: 0 0 14px; }}
  .bar-row {{ display: flex; align-items: center; gap: 10px; padding: 3px 0; }}
  .bar-label {{
    width: 34%; min-width: 120px; font-size: 0.82rem; color: var(--text-secondary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }}
  .bar-track {{
    flex: 1; height: 20px; background: var(--gridline); border-radius: 4px;
    overflow: hidden;
  }}
  .bar-fill {{ height: 100%; border-radius: 0 4px 4px 0; min-width: 3px; }}
  .bar-value {{
    width: 110px; text-align: right; font-size: 0.82rem; color: var(--text-secondary);
    font-variant-numeric: tabular-nums;
  }}
  .status-label {{ font-weight: 600; }}
  .empty {{ color: var(--muted); font-size: 0.85rem; }}
  .table-scroll {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.82rem; }}
  th, td {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--gridline); white-space: nowrap; }}
  th {{ color: var(--muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.02em; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  a {{ color: var(--text-primary); }}
  .pill {{
    display: inline-block; padding: 2px 8px; border-radius: 999px;
    color: #fff; font-size: 0.72rem; font-weight: 600; white-space: nowrap;
  }}
  .grid-table th {{ white-space: normal; }}
</style>
</head>
<body>
  <div class="page">
    <h1>{title}</h1>
    <p class="meta">{len(repos)} candidate{'s' if len(repos) != 1 else ''}{' &middot; ' + esc(data.get('generated_at')) if data.get('generated_at') else ''} &middot; generated by RepoBridge, no network calls at render time</p>
    {"".join(sections)}
  </div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate a static HTML dashboard from RepoBridge JSON output.")
    parser.add_argument("input", help="path to a scout.py enrich JSON array, or a SKILL.md sidecar JSON")
    parser.add_argument("--out", help="output HTML path (default: <input>.html)")
    args = parser.parse_args()

    data = load_data(args.input)
    out_path = Path(args.out) if args.out else Path(args.input).with_suffix(".html")
    out_path.write_text(render_page(data))
    print(f"wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
