# RepoBridge

Given an app idea, finds real open-source GitHub repos that already solve most of it and produces an evidence-backed feature-gap report — instead of generating an app from scratch. Retrieval and analysis only; it never writes application code.

**Prerequisites:** GitHub auth via one of:
- `gh auth login` (uses your existing `gh` CLI session), or
- a `GITHUB_TOKEN` environment variable

No other setup — `scout.py` is dependency-free (Python 3 stdlib only).

**Usage:**

```
/repobridge habit tracker with streaks and social accountability
```

Produces three files in `repobridge-reports/`, all from the same data:
- `<slug>-<date>.md` — a ranked shortlist of 3-5 real repos, each with a Present/Partial/Missing feature-map table against your idea, a coverage estimate, and the concrete list of what's still missing
- `<slug>-<date>.json` — the same data as structured JSON
- `<slug>-<date>.html` — a static dashboard generated from the JSON (bar charts for stars/verified/deployability scores, a coverage chart, and the feature-map as a hoverable grid). Open it directly in a browser — no server needed.

You can also run `dashboard.py` by hand against any sidecar JSON:

```
python3 .claude/skills/repobridge/dashboard.py repobridge-reports/<slug>-<date>.json
```

See `SKILL.md` for the full workflow and `../../../docs/plan.md` for the design rationale.
