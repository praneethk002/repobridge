# RepoBridge PoC — Implementation Plan

## Context

RepoBridge's thesis: when a developer has an app idea, an AI tool should find and evaluate existing open-source repos that already solve most of it, instead of generating everything from scratch. The highest-risk, highest-uncertainty part of this idea is **Scout + Analyze** — can we reliably turn a vague idea into a ranked, evidence-backed shortlist of real repos with an honest feature-gap breakdown? That's what this PoC validates. Step 3 (diff-only code generation) is explicitly out of scope — it's the low-risk part and doesn't need proving first.

Runtime model (per user decision): this runs **inside Claude Code**, not as a standalone scripted product. Claude Code does all the semantic reasoning (query generation, README relevance scoring, gap analysis) using its existing session — no separate `ANTHROPIC_API_KEY` or billing. The only code artifact is a small dependency-free Python helper script that does the deterministic, mechanical GitHub API plumbing (search, filter, fetch, rule-based scoring) — kept separate from the LLM reasoning so that part is fast, cheap, and doesn't burn Claude's context on pagination/JSON handling.

Working directory (per user decision): built in place in `/Users/neeth/Documents/Trials/Recycle_me` (folder name is unrelated/pre-existing, ignored).

## Architecture

Enrichment (README + file structure) is deliberately deferred to a *third* stage, after cheap metadata-only scoring narrows the field — this is the fix for the context-suffocation and wasted-request risks flagged in review (see Design Notes below).

```
/repobridge <idea text>   (Claude Code skill)
        │
        ▼
1. Claude decomposes the idea → search queries, topics, explicit requirement list,
   plus one "awesome-list" discovery query for the idea's domain
        │
        ▼
2. Bash → scout.py stage=search (pure stdlib, no LLM) → GitHub Search API
   - multi-query search (~6-8 queries incl. awesome-list query), dedupe by repo id
   - metadata comes free in the search response (stars, license, pushed_at, topics,
     description) — no extra per-repo call needed at this stage
   - hard filters: no license → drop; copyleft (GPL/AGPL) → drop by default, kept only
     with --allow-copyleft; pushed_at older than 12mo → drop (true abandonment)
   - if an awesome-list repo was found, fetch just its README and extract linked repo
     names as bonus candidates fed back into the same filter pass
   - metadata-only rule-based score (stars, recency-weighted, topic/keyword overlap
     with idea requirements) → ranks all ~20-30 survivors, no HTTP cost beyond search
   - emits ranked JSON (metadata only) to stdout
        │
        ▼
3. Bash → scout.py stage=enrich <top 5-8 repo ids from step 2>
   - NOW fetch, only for these 5-8: README (truncated ~4000 chars), one
     git/trees?recursive=1 call per repo (checks for Dockerfile, docker-compose.yml,
     .env.example, .github/workflows/* in a single request instead of four),
     contributor count
   - compute verified_score (recency + ≥3 contributors + license + CI present) and
     deployability_score (Dockerfile/compose + .env.example + deploy-button pattern)
   - emits enriched JSON for just these 5-8 to stdout (~8-12k tokens total, not 30k+)
        │
        ▼
4. Claude reads the enriched JSON, scores relevance per candidate against the idea
   as a strict evaluator (not a cheerleader — most candidates should NOT score high),
   builds the Present/Partial/Missing table per requirement
        │
        ▼
5. Claude combines relevance_score + verified_score + deployability_score → picks top 3-5
        │
        ▼
6. Claude writes a markdown report to repobridge-reports/<slug>.md and summarizes in chat
```

## Design notes (from plan review)

- **Enrichment is gated behind metadata scoring.** Fetching README + running structural checks for all 30 candidates before narrowing was the main flaw in the original draft — it risked dumping ~30k tokens of unstructured markdown into one turn and doing ~150 HTTP calls where ~24 suffice. Splitting `scout.py` into a `search` stage (metadata-only, free) and an `enrich` stage (heavy, capped at 5-8) fixes both.
- **Rate limits, corrected:** the 30/min cap applies specifically to `/search/repositories` (~6-8 calls here, no risk). Enrichment calls hit the core content API (5000/hr authenticated) — 24 calls wouldn't have crashed it either, but doing them lazily on a short-list is still strictly better on latency and robustness, so the fix stands on its own merits.
- **Curated lists, via GitHub itself, not a new API.** Awesome-lists are themselves GitHub repos, so "search for the domain's awesome-list and mine its README for links" reuses the same search + README-fetch primitives already in scout.py — no Brave Search integration, no new API key, keeps the zero-new-dependency constraint intact.
- **Copyleft:** hard-blocked by default (`--allow-copyleft` to override), not just flagged — a non-technical builder using this unsupervised shouldn't be able to silently walk into a GPL/AGPL obligation on a closed-source project.
- **Liveness threshold kept at 12 months, not tightened to 6.** A stable, feature-complete repo can go 8-10 months without a commit without being abandoned — hard-excluding it is a false positive against exactly the kind of "boring, finished" code this tool should prefer. Recency is instead a *continuous* factor in the ranking score, so an actively-maintained repo naturally outranks a barely-alive one among survivors, without discarding good mature code outright. Revisit this if it produces bad results in the validation pass.

## Files to create

- `.claude/skills/repobridge/SKILL.md` — the workflow instructions Claude Code follows (the 6 steps above, written as directive prose: how to decompose the idea, how to invoke scout.py's two stages and with what args, how to score relevance as a strict evaluator, the exact report format to produce). This is the core "intelligence" of the tool — no separate prompt files needed.
- `.claude/skills/repobridge/scout.py` — stdlib-only Python (urllib, json, base64, argparse — no `pip install` required, zero setup friction). Two subcommands:
  - `search`: `search_repos(queries, topics, min_stars, pushed_since_months, allow_copyleft)` — hits `/search/repositories` across all queries incl. the awesome-list query, merges + dedupes by repo id, applies hard filters, computes metadata-only rule-based score, emits ranked JSON (no README/structure calls)
  - `enrich <repo_ids...>`: for the 5-8 ids Claude selects from `search` output — fetches README (contents API, base64-decoded, truncated ~4000 chars), one `git/trees?recursive=1` call for structural checks, contributor count; computes `verified_score` and `deployability_score`; emits enriched JSON
  - Auth: use `GITHUB_TOKEN` env var if set; otherwise shell out to `gh api` if the user's `gh` CLI is already authenticated (avoids requiring a fresh PAT for setup)
  - Fail loudly with a clear message on 403/rate-limit rather than silently returning partial results
- `.claude/skills/repobridge/README.md` — one paragraph: prerequisites (`gh auth login` or `GITHUB_TOKEN`), what `/repobridge <idea>` does, example invocation
- `repobridge-reports/` — output directory for generated markdown reports (created on first run, not committed as empty dir)

No `requirements.txt`, no database, no server — matches the zero-compute constraint from the design phase.

## Report format (what SKILL.md instructs Claude to produce)

SKILL.md should explicitly instruct Claude to act as a strict product evaluator, not a cheerleader — most candidates should land as Partial/Missing on most requirements; a repo that scores high across the board should be rare and should hold up to scrutiny. For each of the top 3-5 repos:
- Name, URL, stars, last commit date, license (with copyleft flag if applicable), primary language
- `verified` rationale — the specific rule-based signals that passed, not a vibe
- Feature-map table: idea requirements as rows × Present/Partial/Missing with a one-line evidence quote from the README
- Coverage % estimate
- Explicit "missing slice" — the concrete feature list still to be built

## Guardrails (lean + maintainable + safe)

- **One file, one job.** `scout.py` stays a single flat script (~150-250 lines) with plain functions, not a package — no premature module splitting, no config framework, no plugin system. Two subcommands (`search`, `enrich`), stdlib only.
- **Fail loud, never degrade silently.** Missing auth, a 403/rate-limit, a malformed API response, or zero search results after filtering all print a clear error to stderr and exit non-zero — never fall back to guessed/partial data that looks like a real result.
- **Validate before calling.** Check `GITHUB_TOKEN`/`gh auth status` once at startup, not lazily mid-run. Reject empty/whitespace idea input before any API calls.
- **No dynamic execution of fetched content.** README text and repo metadata are treated strictly as data — never `eval`'d, never shelled out, never used to construct file paths. This matters because README content is untrusted external input.
- **Deterministic scoring stays deterministic.** `verified_score`/`deployability_score` are plain arithmetic over explicit boolean signals, printed alongside the score in the JSON output — so a result is always auditable back to the exact rule that produced it, not a hidden weighting.
- **No network calls outside scout.py.** Claude never calls GitHub directly (e.g. via WebFetch) — all retrieval goes through the script so filtering/auth/error-handling logic lives in one auditable place, not split across the skill prompt and ad hoc tool calls.
- **No secrets in output.** Reports and JSON payloads never echo the token itself; scout.py reads it from env and never logs it, including in error messages.

## Verification

1. Confirm GitHub auth path works: `gh auth status` or `GITHUB_TOKEN` env var present.
2. Run `scout.py search` standalone against 2-3 hardcoded queries first, inspect the metadata-only JSON output for correctness (dedupe working, filters correct, awesome-list bonus candidates appearing, scores computed) — confirm no README/structural HTTP calls happen at this stage.
3. Run `scout.py enrich` against a handful of ids from step 2, confirm only those repos get README + tree-API calls, and check the payload size stays small (~8-12k tokens for 5-8 repos, not 30k+).
4. Invoke `/repobridge` with a real idea (e.g. "habit tracker with streaks and social accountability") end-to-end, inspect the generated report by hand.
5. Run the 10-15 diverse idea validation pass discussed earlier — manually grade shortlist relevance and gap-analysis honesty against what a 10-minute manual GitHub search would surface. This is the actual bar, not test coverage.
