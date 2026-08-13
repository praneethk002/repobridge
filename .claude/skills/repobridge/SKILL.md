---
name: repobridge
description: Given an app idea, scout real open-source GitHub repos that already solve most of it and produce an evidence-backed feature-gap report — before writing any code. Use when the user describes an app they want to build and wants to know what already exists, or explicitly invokes /repobridge.
---

# RepoBridge

Find existing, well-maintained open-source repos that match a user's app idea, and produce an honest report of what's already covered vs. what's genuinely missing. This skill does **retrieval and analysis only** — it never writes application code and never recommends cloning/forking as a final step; it hands the user (or a later Claude Code session) a shortlist and a gap list to act on.

All GitHub access goes through `scout.py` in this skill's directory. Never call the GitHub API directly (e.g. via WebFetch) — `scout.py` is the single place auth, filtering, and error-handling logic live, and it's the only thing that keeps request counts and context usage bounded.

## Step 1 — Validate and decompose the idea

If the idea text is empty or just whitespace, ask the user for an actual idea instead of proceeding.

Otherwise, decompose the idea into:
- **4-6 search query phrases** — plain keywords capturing different angles/synonyms of the idea. Do not include GitHub search qualifiers (`stars:`, `topic:`, etc.) — `scout.py` adds those itself.
- **One additional query aimed at an "awesome list"** for the idea's domain, e.g. `awesome self-hosted` or `awesome habit tracker` — phrase it the way such a list would actually be named.
- **A short requirements list** — the concrete features/capabilities implied by the idea, as short noun phrases (e.g. `streak tracking`, `social accountability`, `push reminders`). This becomes both the scoring keywords and the rows of the feature-map table later. Keep it to what the user actually asked for — don't invent requirements they didn't imply.
- **Optional topics** — 1-3 GitHub topics likely relevant, only if genuinely obvious (e.g. `react`, `self-hosted`). Skip if unsure; it narrows results and a wrong guess loses good candidates.

## Step 2 — Search (metadata-only, cheap)

Run:

```
python3 .claude/skills/repobridge/scout.py search \
  --queries "<q1>" "<q2>" ... \
  --requirements "<r1>" "<r2>" ... \
  [--topics "<t1>" ...] \
  --min-stars 50 --limit 30
```

If this exits non-zero, read the stderr message and relay it to the user plainly — a rate-limit, auth failure, or "no candidates survived filtering" are all real outcomes to report, not to work around or paper over with invented data. If filtering was too strict, you may retry once with broader queries or `--min-stars 20`, but say so explicitly.

This returns metadata-only JSON (no README content) for all surviving candidates, already ranked by `metadata_score`. Do not fetch or reason about README content yet — that's Step 3.

## Step 3 — Enrich only the shortlist

Select the top 5-8 candidates by `metadata_score` from Step 2's output (fewer if there aren't 5-8 survivors). Don't hand-pick outside this ranking — it's the objective, auditable signal at this stage.

Run:

```
python3 .claude/skills/repobridge/scout.py enrich --repos <full_name1> <full_name2> ...
```

This fetches README text (truncated, `readme_excerpt`), `verified_score`/`verified_signals`, and `deployability_score`/`deployability_signals` for just these repos.

## Step 4 — Score relevance as a strict evaluator

For each enriched repo, read `readme_excerpt` and evaluate it against the requirements list from Step 1. **Act as a skeptical product evaluator, not a cheerleader:**

- Mark each requirement **Present / Partial / Missing**.
- Every Present or Partial needs a one-line evidence quote or close paraphrase from the README. No evidence, no Present.
- Most requirements on most repos should land Partial or Missing. A repo that scores Present across the board should be rare, and if one shows up, double-check it actually holds up rather than accepting it at face value.
- Compute **coverage %** = (Present × 1 + Partial × 0.5) / total requirements.

## Step 5 — Final ranking and the single best pick

Combine your Step 4 relevance read with `repo['verified_score']` and `repo['deployability_score']` to rank the final **top 3-5**. This is a judgment call, not a re-sort by `metadata_score` — a repo that ranked #1 on stars/recency but covers little of the actual idea should not out-rank a smaller, better-fitting repo here.

Whichever repo you rank #1 is **the pick** — the dashboard and report both lead with it as a single answer, with the rest shown as the comparison behind it. Write one or two sentences on *why* it's the pick (what tipped it over the runner-up, and its most consequential gap) — this becomes `pick_rationale` in the sidecar below. Don't hedge into "it depends" — if the evidence is genuinely too close to call, say that plainly instead of forcing a pick.

## Step 6 — Write the report, sidecar, and dashboard

Create `repobridge-reports/` if it doesn't exist. Write `repobridge-reports/<slug>-<YYYYMMDD>.md`, where `<slug>` is the idea in kebab-case, truncated to ~40 chars.

Write the JSON sidecar **first** (`repobridge-reports/<slug>-<YYYYMMDD>.json`) — the markdown report is written from it, not the other way around, so the two can't disagree. Match this shape exactly (it feeds the dashboard, so the keys are load-bearing), with **`repos` ordered best-first** — `repos[0]` is read as the pick, not re-derived:

```json
{
  "idea": "<the original idea text>",
  "requirements": ["<requirement 1>", "<requirement 2>", ...],
  "generated_at": "<ISO 8601 timestamp>",
  "pick_rationale": "<1-2 sentences: why repos[0] over the runner-up, and its main gap>",
  "repos": [
    {
      "full_name": "owner/repo", "url": "...", "stars": 0,
      "license_spdx": "MIT", "pushed_at": "<ISO 8601>",
      "verified_score": 0.0, "deployability_score": 0.0,
      "coverage_pct": 0.0,
      "requirement_status": {
        "<requirement>": {"status": "present|partial|missing", "evidence": "<quote or paraphrase, empty string if missing>"}
      }
    }
  ]
}
```

Then pull the headline numbers instead of computing them by hand:

```
python3 .claude/skills/repobridge/dashboard.py repobridge-reports/<slug>-<YYYYMMDD>.json --print-stats
```

This prints `match_pct`, `features_left` (with the present/partial/missing breakdown), `estimated_hours_remaining`/`estimated_days_remaining`, `estimated_tokens_saved`/`estimated_tokens_saved_pct`, and a `methodology_note` — all derived from the sidecar you just wrote, by one fixed formula. Use these exact numbers in the markdown report's opening section (pick name, `pick_rationale`, then the four headline stats and the methodology note verbatim — these are estimates, and the report should say so as plainly as the dashboard does). Do not recompute or restate them differently than what this command prints.

The rest of the markdown follows the existing detail format, for all top 3-5 repos:

- **Name, URL, stars, last commit date, license** (note explicitly if copyleft — `scout.py` already excludes copyleft by default, so this only applies if the user ran with `--allow-copyleft` semantics were overridden; otherwise omit the note)
- **Verified rationale** — list the specific `verified_signals` that passed (e.g. "active in the last 12mo, 3+ contributors, has CI"), not a vibe-based claim
- **Feature-map table** — requirements as rows, Present/Partial/Missing per repo, with the evidence quote
- **Coverage %**
- **Missing slice** — the concrete, named list of what's not covered, i.e. what a developer would actually need to build

Finally, generate the dashboard:

```
python3 .claude/skills/repobridge/dashboard.py repobridge-reports/<slug>-<YYYYMMDD>.json
```

This writes `repobridge-reports/<slug>-<YYYYMMDD>.html` — a static, self-contained file with no network calls at render time, leading with a hero card for the pick (headline stats + why) and the full comparison below it. Do not hand-write or skip this file; it's generated purely from the sidecar you already wrote, so it can never show data the report doesn't.

After writing all three, summarize in chat: the pick, why, its headline stats, and the three file paths (`.md`, `.json`, `.html`). Don't paste the full report inline — point to the files.

## Guardrails

- Never fabricate a repo, star count, license, or feature-match that didn't come from `scout.py`'s output.
- Never call the GitHub API by any path other than `scout.py`.
- If `scout.py` reports a rate-limit or auth error, stop and surface it — don't retry in a loop.
- This skill produces a report, not code. Do not clone repos or write application code as part of this skill.
- The dashboard is always generated from the JSON sidecar via `dashboard.py`, never hand-written — that's what guarantees it can't show anything the report doesn't.
- The time and token-savings figures are heuristic estimates from `dashboard.py --print-stats`, not measurements. Always carry the `methodology_note` alongside them — never present them as precise or committed.
