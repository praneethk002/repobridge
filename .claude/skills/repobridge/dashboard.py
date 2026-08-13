#!/usr/bin/env python3
"""RepoBridge dashboard: turns the SKILL.md JSON sidecar into a static,
self-contained HTML report. Stdlib only — no server, no build step, no CDN.
Open the generated file directly in a browser.

Accepts two input shapes:
  - a dict with "idea"/"requirements"/"repos" (the SKILL.md sidecar) ->
    full dashboard: hero card for the pick, headline stats, a
    checklist + runner-up split, and a compare-card grid for every
    candidate, with the exhaustive evidence table folded into a
    <details> disclosure so the page stays scannable without hiding data
  - a plain list (raw `scout.py enrich` output, no ranking/coverage data)
    -> compare cards only, no hero (nothing to crown as "best")

`repos` is expected pre-sorted best-first — this script does not re-rank;
ranking is whatever order Claude put them in during Step 4 of SKILL.md.

The "pick" itself has three possible modes, decided by compute_pick() —
a fixed coverage-threshold rule, never an LLM judgment call:
  - "single": the best repo alone clears SINGLE_REPO_THRESHOLD.
  - "composition": no single repo does, but the top few together clear
    it with a real margin — the requirement-by-requirement attribution
    is derived mechanically here, never hand-written by Claude.
  - "custom_build": nothing clears the bar, alone or combined — said
    plainly rather than forcing a pick that doesn't exist.

--print-stats prints compute_pick()'s output (mode included) as JSON,
without writing HTML — SKILL.md reads the mode from this to decide what
to write next, and the markdown report and dashboard can never drift
apart (one formula, read twice, not recomputed by hand in two places).
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

# Pick-mode thresholds. All three modes are derived mechanically from
# coverage already in the sidecar — never decided by Claude free-hand.
SINGLE_REPO_THRESHOLD = 70       # reuses coverage_bucket()'s "Strong fit" cutoff
COMPOSITION_CANDIDATE_LIMIT = 3  # stitching more than 3 repos isn't a practical recommendation
COMPOSITION_MARGIN = 10          # joint coverage must beat the single best by this much to be worth the added complexity


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


def _status_counts(statuses, requirements):
    present = sum(1 for r in requirements if statuses.get(r, {}).get("status") == "present")
    partial = sum(1 for r in requirements if statuses.get(r, {}).get("status") == "partial")
    missing = len(requirements) - present - partial
    return present, partial, missing


def _stat_fields(present, partial, missing, total):
    hours = missing * HOURS_PER_MISSING_FEATURE + partial * HOURS_PER_PARTIAL_FEATURE
    tokens_full_build = total * TOKENS_PER_FEATURE
    tokens_remaining = (missing + partial * PARTIAL_TOKEN_FRACTION) * TOKENS_PER_FEATURE
    tokens_saved = max(0, tokens_full_build - tokens_remaining)
    match_pct = (present + partial * 0.5) / total * 100 if total else 0.0

    return {
        "match_pct": round(match_pct, 1),
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


def compute_joint_requirement_status(repos, requirements, limit=COMPOSITION_CANDIDATE_LIMIT):
    """For each requirement, the best status found among the top `limit`
    repos (present > partial > missing), attributed to whichever repo
    provided it. This is the entire "composition" — mechanically derived,
    never hand-written by Claude."""
    rank = {"present": 2, "partial": 1, "missing": 0}
    candidates = repos[:limit]
    composition = []
    for req in requirements:
        best_repo, best_status, best_evidence = None, "missing", ""
        for r in candidates:
            entry = r.get("requirement_status", {}).get(req, {"status": "missing", "evidence": ""})
            status = entry.get("status", "missing")
            if rank[status] > rank[best_status]:
                best_repo, best_status = r["full_name"], status
                best_evidence = entry.get("evidence", "")
        composition.append({
            "requirement": req, "full_name": best_repo,
            "status": best_status, "evidence": best_evidence,
        })
    return composition


def compute_pick(data):
    repos = data.get("repos", [])
    requirements = data.get("requirements", [])
    if not repos or not requirements or not repos[0].get("requirement_status"):
        return None

    best = repos[0]
    best_stats = _stat_fields(*_status_counts(best.get("requirement_status", {}), requirements), len(requirements))

    if best_stats["match_pct"] >= SINGLE_REPO_THRESHOLD:
        return {**best_stats, "mode": "single", "best_pick": best["full_name"]}

    composition = compute_joint_requirement_status(repos, requirements)
    comp_counts = (
        sum(1 for c in composition if c["status"] == "present"),
        sum(1 for c in composition if c["status"] == "partial"),
        sum(1 for c in composition if c["status"] == "missing"),
    )
    comp_stats = _stat_fields(*comp_counts, len(requirements))

    if (comp_stats["match_pct"] >= SINGLE_REPO_THRESHOLD
            and comp_stats["match_pct"] - best_stats["match_pct"] >= COMPOSITION_MARGIN):
        contributing = []
        for c in composition:
            if c["full_name"] and c["full_name"] not in contributing:
                contributing.append(c["full_name"])
        return {**comp_stats, "mode": "composition", "composition": composition, "contributing_repos": contributing}

    return {
        **best_stats, "mode": "custom_build", "closest_repo": best["full_name"],
        "note": (
            f"No single repo or small combination clears a strong-fit bar (≥{SINGLE_REPO_THRESHOLD}%) "
            "for this idea — most of it will need custom building. Numbers above are relative to the "
            "closest reference found, not a recommended pick."
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
    mode = stats["mode"]
    rationale = data.get("pick_rationale")
    match_pct = stats["match_pct"]

    if mode == "single":
        best = repos[0]
        kicker = "Best match"
        title_block = f'<h2 class="hero-name"><a href="{esc(best.get("url", "#"))}">{esc(best["full_name"])}</a></h2>'
    elif mode == "composition":
        url_by_name = {r["full_name"]: r.get("url", "#") for r in repos}
        chips = "".join(
            f'<a class="hero-chip" href="{esc(url_by_name.get(name, "#"))}">{esc(name)}</a>'
            for name in stats["contributing_repos"]
        )
        kicker = "Composed pick"
        title_block = f'<div class="hero-chips">{chips}</div>'
    else:
        closest = repos[0]
        kicker = "No strong match"
        title_block = (
            f'<h2 class="hero-name">Closest reference: '
            f'<a href="{esc(closest.get("url", "#"))}">{esc(closest["full_name"])}</a></h2>'
        )

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
      <div class="hero-kicker">{esc(kicker)}</div>
      {title_block}
      {f'<p class="hero-rationale">{esc(rationale)}</p>' if rationale else ''}
      <div class="stat-grid">{tiles}</div>
      <p class="methodology">{esc(stats["methodology_note"])}</p>
      {f'<p class="methodology">{esc(stats["note"])}</p>' if stats.get("note") else ''}
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
    <div class="panel panel-half">
      <h3>What {esc(best['full_name'])} covers</h3>
      {"".join(rows)}
    </div>"""


def composition_checklist(composition):
    icon_style = {
        "present": (GOOD, "✓"),
        "partial": (WARNING, "~"),
        "missing": (MUTED, "–"),
    }
    rows = []
    for entry in composition:
        color, icon = icon_style.get(entry["status"], icon_style["missing"])
        evidence = entry.get("evidence", "")
        via = f' <span class="checklist-via">via {esc(entry["full_name"])}</span>' if entry.get("full_name") else ""
        rows.append(f"""
        <div class="checklist-row">
          <span class="checklist-icon" style="background:{color};">{icon}</span>
          <span class="checklist-req">{esc(entry['requirement'])}</span>
          <span class="checklist-evidence">{esc(evidence) if evidence else '<em>Not covered</em>'}{via}</span>
        </div>""")
    return f"""
    <div class="panel panel-half">
      <h3>How the pieces fit</h3>
      {"".join(rows)}
    </div>"""


def runner_up_list(repos, exclude_names):
    others = [r for r in repos if r["full_name"] not in exclude_names]
    if not others:
        return ""
    rows = []
    for r in others:
        pct = r.get("coverage_pct")
        _, color = coverage_bucket(pct) if pct is not None else (None, MUTED)
        pct_label = f"{pct:.0f}%" if pct is not None else "—"
        rows.append(f"""
        <div class="runner-row">
          <a href="{esc(r.get('url', '#'))}" class="runner-name">{esc(r['full_name'])}</a>
          <span class="pill" style="background:{color};">{pct_label}</span>
        </div>""")
    return f"""
    <div class="panel panel-half">
      <h3>Runner-ups</h3>
      <p class="panel-subtitle">Considered and ranked below the pick.</p>
      {"".join(rows)}
    </div>"""


def mini_metric(label, value):
    if value is None:
        return f'<div class="mini-row"><span class="mini-label">{esc(label)}</span><span class="mini-track"></span></div>'
    frac = max(0.0, min(value / 100, 1.0))
    return f"""
        <div class="mini-row">
          <span class="mini-label">{esc(label)}</span>
          <span class="mini-track"><span class="mini-fill" style="width:{frac * 100:.0f}%;"></span></span>
          <span class="mini-value">{value:.0f}</span>
        </div>"""


def compare_cards(repos):
    cards = []
    for r in repos:
        pct = r.get("coverage_pct")
        label, color = coverage_bucket(pct) if pct is not None else ("No coverage data", MUTED)
        cards.append(f"""
        <div class="compare-card">
          <div class="compare-head">
            <a href="{esc(r.get('url', '#'))}">{esc(r['full_name'])}</a>
            {f'<span class="pill" style="background:{color};" title="{esc(label)}">{pct:.0f}%</span>' if pct is not None else ''}
          </div>
          <div class="compare-meta">{esc(r.get('stars', '—'))}★ &middot; {esc(r.get('license_spdx') or 'no license')} &middot; {esc((r.get('pushed_at') or '')[:10] or '—')}</div>
          {f'<div class="compare-found-via">{esc(r["found_via"])}</div>' if r.get('found_via') else ''}
          {mini_metric("Verified", r.get('verified_score'))}
          {mini_metric("Deploy", r.get('deployability_score'))}
        </div>""")
    return f"""
    <div class="section-label">All candidates, side by side</div>
    <div class="compare-grid">{"".join(cards)}</div>"""


def evidence_table(repos, requirements):
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
    <div class="table-scroll">
      <table class="grid-table">
        <thead><tr><th></th>{header_cells}</tr></thead>
        <tbody>{"".join(body_rows)}</tbody>
      </table>
    </div>"""


def full_data_table(repos):
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
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr><th>Repo</th><th class="num">Stars</th><th>License</th><th>Last commit</th>
              <th class="num">Verified</th><th class="num">Deployability</th><th class="num">Coverage</th></tr>
        </thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </div>"""


def evidence_disclosure(repos, requirements):
    grid = evidence_table(repos, requirements)
    table = full_data_table(repos)
    if not grid and not table:
        return ""
    return f"""
    <details class="disclosure">
      <summary>Full evidence table &amp; raw data — every requirement, every repo</summary>
      {grid}
      {table}
    </details>"""


def render_page(data):
    repos = data.get("repos", [])
    idea = data.get("idea")
    requirements = data.get("requirements", [])
    stats = compute_pick(data)

    title = f"RepoBridge: {esc(idea)}" if idea else "RepoBridge dashboard"

    top_sections = ""
    if stats:
        if stats["mode"] == "composition":
            left = composition_checklist(stats["composition"])
            exclude = set(stats["contributing_repos"])
        else:
            left = winner_checklist(repos[0], requirements)
            exclude = {repos[0]["full_name"]}
        top_sections = hero_section(data, stats) + f"""
    <div class="split">
      {left}
      {runner_up_list(repos, exclude)}
    </div>"""

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
  .page {{ max-width: 980px; margin: 0 auto; padding: 40px 20px 72px; }}
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
    margin-bottom: 16px;
  }}
  .hero-kicker {{ font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--accent); margin-bottom: 8px; }}
  .hero-name {{ margin: 0 0 10px; font-size: 1.7rem; text-wrap: balance; }}
  .hero-name a {{ color: var(--text-primary); text-decoration: none; }}
  .hero-name a:hover {{ text-decoration: underline; }}
  .hero-rationale {{ color: var(--text-secondary); font-size: 0.98rem; max-width: 60ch; margin: 0 0 22px; }}
  .hero-chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 10px; }}
  .hero-chip {{
    display: inline-block; background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 999px; padding: 6px 16px; font-size: 1.05rem; font-weight: 600;
    color: var(--text-primary); text-decoration: none;
  }}
  .hero-chip:hover {{ text-decoration: underline; }}
  .checklist-via {{ color: var(--accent); font-size: 0.72rem; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 2px; background: var(--border); border-radius: 12px; overflow: hidden; }}
  .stat-tile {{ background: var(--surface-2); padding: 16px 14px; }}
  .stat-value {{ font-size: 1.6rem; font-weight: 700; font-variant-numeric: tabular-nums; }}
  .stat-label {{ font-size: 0.76rem; color: var(--text-secondary); margin-top: 2px; }}
  .stat-sublabel {{ font-size: 0.7rem; color: var(--muted); margin-top: 1px; }}
  .methodology {{ font-size: 0.72rem; color: var(--muted); margin: 14px 2px 0; line-height: 1.5; }}
  .split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 8px; }}
  .panel {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
  }}
  .panel-half {{ display: flex; flex-direction: column; }}
  .panel h3 {{ margin: 0 0 2px; font-size: 0.95rem; }}
  .panel-subtitle {{ color: var(--muted); font-size: 0.78rem; margin: 0 0 14px; }}
  .checklist-row {{ display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--gridline); }}
  .checklist-row:last-child {{ border-bottom: none; }}
  .checklist-icon {{
    flex: 0 0 auto; width: 20px; height: 20px; border-radius: 50%; color: #fff;
    display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700;
  }}
  .checklist-req {{ flex: 0 0 42%; font-size: 0.83rem; font-weight: 600; }}
  .checklist-evidence {{ flex: 1; font-size: 0.8rem; color: var(--text-secondary); }}
  .checklist-evidence em {{ color: var(--muted); font-style: normal; }}
  .runner-row {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--gridline); }}
  .runner-row:last-child {{ border-bottom: none; }}
  .runner-name {{ color: var(--text-primary); text-decoration: none; font-size: 0.85rem; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .runner-name:hover {{ text-decoration: underline; }}
  .section-label {{ font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); margin: 28px 2px 12px; }}
  .compare-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .compare-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
  .compare-head {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px; }}
  .compare-head a {{ font-size: 0.88rem; font-weight: 600; color: var(--text-primary); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .compare-head a:hover {{ text-decoration: underline; }}
  .compare-meta {{ font-size: 0.74rem; color: var(--muted); margin-bottom: 12px; }}
  .compare-found-via {{ font-size: 0.7rem; color: var(--accent); margin: -8px 0 10px; }}
  .mini-row {{ display: flex; align-items: center; gap: 8px; margin-top: 6px; }}
  .mini-label {{ width: 52px; flex: 0 0 auto; font-size: 0.7rem; color: var(--text-secondary); }}
  .mini-track {{ flex: 1; height: 6px; background: var(--gridline); border-radius: 3px; overflow: hidden; }}
  .mini-fill {{ display: block; height: 100%; background: var(--accent); border-radius: 3px; }}
  .mini-value {{ width: 24px; text-align: right; font-size: 0.7rem; color: var(--muted); font-variant-numeric: tabular-nums; }}
  .disclosure {{ margin-top: 24px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }}
  .disclosure summary {{ cursor: pointer; padding: 14px 20px; font-size: 0.82rem; font-weight: 600; color: var(--text-secondary); list-style: none; }}
  .disclosure summary::-webkit-details-marker {{ display: none; }}
  .disclosure summary::before {{ content: "▸"; display: inline-block; margin-right: 8px; color: var(--accent); transition: transform 0.15s; }}
  .disclosure[open] summary::before {{ transform: rotate(90deg); }}
  .disclosure > .table-scroll {{ padding: 0 20px 20px; }}
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
  @media (max-width: 720px) {{
    .split {{ grid-template-columns: 1fr; }}
    .stat-grid {{ grid-template-columns: repeat(2, 1fr); }}
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
    {compare_cards(repos)}
    {evidence_disclosure(repos, requirements)}
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
        stats = compute_pick(data)
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
