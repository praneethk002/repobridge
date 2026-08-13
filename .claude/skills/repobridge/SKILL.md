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

## Step 5 — Final ranking

Combine your Step 4 relevance read with `repo['verified_score']` and `repo['deployability_score']` to pick the final **top 3-5**. This is a judgment call, not a re-sort by `metadata_score` — a repo that ranked #1 on stars/recency but covers little of the actual idea should not out-rank a smaller, better-fitting repo here.

## Step 6 — Write the report

Create `repobridge-reports/` if it doesn't exist. Write `repobridge-reports/<slug>-<YYYYMMDD>.md`, where `<slug>` is the idea in kebab-case, truncated to ~40 chars.

For each of the top 3-5 repos, include:

- **Name, URL, stars, last commit date, license** (note explicitly if copyleft — `scout.py` already excludes copyleft by default, so this only applies if the user ran with `--allow-copyleft` semantics were overridden; otherwise omit the note)
- **Verified rationale** — list the specific `verified_signals` that passed (e.g. "active in the last 12mo, 3+ contributors, has CI"), not a vibe-based claim
- **Feature-map table** — requirements as rows, Present/Partial/Missing per repo, with the evidence quote
- **Coverage %**
- **Missing slice** — the concrete, named list of what's not covered, i.e. what a developer would actually need to build

After writing, summarize in chat: the top pick, why, and the file path. Don't paste the full report inline — point to the file.

## Guardrails

- Never fabricate a repo, star count, license, or feature-match that didn't come from `scout.py`'s output.
- Never call the GitHub API by any path other than `scout.py`.
- If `scout.py` reports a rate-limit or auth error, stop and surface it — don't retry in a loop.
- This skill produces a report, not code. Do not clone repos or write application code as part of this skill.
