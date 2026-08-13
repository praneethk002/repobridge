---
name: repobridge
description: Given an app idea, scout real open-source GitHub repos that already solve most of it and produce an evidence-backed feature-gap report — before writing any code. Use when the user describes an app they want to build and wants to know what already exists, or explicitly invokes /repobridge.
---

# RepoBridge

Find existing, well-maintained open-source repos that match a user's app idea, and produce an honest report of what's already covered vs. what's genuinely missing. This skill does **retrieval and analysis only** — it never writes application code and never recommends cloning/forking as a final step; it hands the user (or a later Claude Code session) a shortlist and a gap list to act on.

All GitHub access goes through `scout.py` in this skill's directory. Never call the GitHub API directly (e.g. via WebFetch) — `scout.py` is the single place auth, filtering, and error-handling logic live, and it's the only thing that keeps request counts and context usage bounded.

## Step 0 — Confirm the idea before any scouting

This is a real gate, not a formality: **zero `scout.py` calls happen before it clears.** Decomposing an idea straight into search queries risks locking in a guessed interpretation before anyone can correct it.

- Reflect the idea back in plain language: what the app does, who it's for if that's implied, and the features you understand it to require.
- If the idea is already specific and well-formed, a single-turn reflect-and-confirm is enough — e.g. "Here's my read: an app that does X, Y, Z. Sound right, or is there more before I start searching?" Don't manufacture multiple rounds of questions for an idea that's already clear just to look thorough.
- If it's genuinely ambiguous in ways that would change the search queries or requirements list (unclear scope, unclear must-have vs. nice-to-have, unclear platform), ask 1-3 targeted clarifying questions — not an exhaustive interrogation.
- Wait for explicit confirmation ("yes," "go ahead," "looks right") before proceeding to Step 1. If the user changes the idea mid-conversation, restart from the updated understanding.

## Step 1 — Validate and decompose the idea

Only after Step 0's confirmation. If the idea text is somehow still empty or just whitespace at this point, ask the user for an actual idea instead of proceeding.

Decompose the confirmed idea into:
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

## Step 5 — Final ranking, then let the script decide the pick mode

Combine your Step 4 relevance read with `repo['verified_score']` and `repo['deployability_score']` to rank the final **top 3-5**, ordered best-first. This is a judgment call, not a re-sort by `metadata_score` — a repo that ranked #1 on stars/recency but covers little of the actual idea should not out-rank a smaller, better-fitting repo here.

Don't decide by hand whether the answer is one repo, a combination, or neither — that's `dashboard.py --print-stats`'s job (Step 6), computed from a fixed coverage threshold, not a judgment call:

- **single** — the best repo alone covers ≥70% of requirements. It's the pick, full stop.
- **composition** — no single repo clears 70%, but the top 3 together do, with a real margin over the best single repo. The requirement-by-requirement attribution (which repo covers what) is derived mechanically by the script, never assigned by hand.
- **custom_build** — nothing clears 70%, alone or combined. Say so plainly rather than forcing a pick that doesn't exist.

## Step 6 — Write the sidecar, learn the mode, then the report and dashboard

Create `repobridge-reports/` if it doesn't exist. This step runs in two passes because the mode isn't known until the script computes it — don't guess it yourself.

**Pass 1 — write the sidecar without `pick_rationale`.** Write `repobridge-reports/<slug>-<YYYYMMDD>.json` (`<slug>` = idea in kebab-case, truncated to ~40 chars), matching this shape exactly, with **`repos` ordered best-first**:

```json
{
  "idea": "<the original idea text>",
  "requirements": ["<requirement 1>", "<requirement 2>", ...],
  "generated_at": "<ISO 8601 timestamp>",
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

**Pass 2 — learn the mode and stats, then patch in `pick_rationale`:**

```
python3 .claude/skills/repobridge/dashboard.py repobridge-reports/<slug>-<YYYYMMDD>.json --print-stats
```

Read `mode` off the output, then write `pick_rationale` into the sidecar to match it — this is the one thing that still needs your judgment, everything else in the output is arithmetic:
- `mode: "single"` → 1-2 sentences on why `repos[0]` beat the runner-up, and its main gap.
- `mode: "composition"` → 1-2 sentences on why stitching `contributing_repos` together makes sense (and note if their licenses/stacks are actually compatible — that's a real judgment call the script can't make).
- `mode: "custom_build"` → 1-2 sentences on why nothing clears the bar, don't hedge into "it depends" if the evidence is genuinely this thin.

Use the `--print-stats` output verbatim in the markdown report's opening section — `match_pct`, `features_left` (with the present/partial/missing breakdown), `estimated_hours_remaining`/`estimated_days_remaining`, `estimated_tokens_saved`/`estimated_tokens_saved_pct`, `methodology_note`, and (`custom_build` only) `note`. These are estimates; say so as plainly as the dashboard does. Do not recompute or restate them differently than what the command printed.

The rest of the markdown depends on the mode:
- **single/custom_build**: the existing detail format, for all top 3-5 repos — Name/URL/stars/last commit/license (flag explicitly if copyleft, which only happens if `--allow-copyleft` was used), verified rationale (the specific `verified_signals` that passed, not a vibe), the Present/Partial/Missing feature-map table with evidence quotes, coverage %, and the missing slice.
- **composition**: same per-repo detail format, plus a "how the pieces fit" table up top — one row per requirement, which repo covers it and how, straight from `--print-stats`'s `composition` array (don't re-derive it).

Finally, generate the dashboard:

```
python3 .claude/skills/repobridge/dashboard.py repobridge-reports/<slug>-<YYYYMMDD>.json
```

This writes `repobridge-reports/<slug>-<YYYYMMDD>.html` — mode-aware, self-contained, no network calls at render time. Do not hand-write or skip this file; it's generated purely from the sidecar you already wrote, so it can never show data the report doesn't.

After writing all three, summarize in chat: the pick (or composition, or the custom-build call), why, its headline stats, and the three file paths (`.md`, `.json`, `.html`). Don't paste the full report inline — point to the files.

## Guardrails

- Never fabricate a repo, star count, license, or feature-match that didn't come from `scout.py`'s output.
- Never call the GitHub API by any path other than `scout.py`.
- If `scout.py` reports a rate-limit or auth error, stop and surface it — don't retry in a loop.
- This skill produces a report, not code. Do not clone repos or write application code as part of this skill.
- The dashboard is always generated from the JSON sidecar via `dashboard.py`, never hand-written — that's what guarantees it can't show anything the report doesn't.
- The time and token-savings figures are heuristic estimates from `dashboard.py --print-stats`, not measurements. Always carry the `methodology_note` alongside them — never present them as precise or committed.
- The pick mode (single/composition/custom_build) and the composition's requirement-to-repo attribution always come from `dashboard.py --print-stats` — never decided or assigned by hand, even when the answer seems obvious.
- Step 0's confirmation gate is not optional and not skippable because an idea "looks clear enough" — even a one-turn reflect-and-confirm still has to happen before Step 1.
