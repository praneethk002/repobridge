# RepoBridge Report: habit tracker with streaks and social accountability

## The pick: redpangilinan/iotawise

Highest requirement coverage of the four candidates (70%): real streak tracking, a working dashboard, and Google auth already in place. Verified active with 3+ contributors, though it lacks CI and still needs social features and finished push notifications.

| Match | Features left | Est. time remaining | Tokens saved |
|---|---|---|---|
| 70% | 2 of 5 (1 missing, 1 partial) | ~1.8d (~11h) | ~52.5K (~70%) |

*Estimate, not a measurement: 8h per missing feature, 3h per partial one; token savings assume ~15,000 tokens to generate one feature from scratch, at half that for a partial. Actual time and token cost depend heavily on your stack and the specific features.*

---

Idea requirements evaluated: streak tracking, social accountability, reminders, progress visualization, multi-user.

4 candidates survived search + hard filters (license present and non-copyleft, pushed within 12 months, stars ≥ 50). All 4 are included below since fewer than 5 survived — none were cut for space.

**Headline finding: none of the 4 candidates have any social accountability feature.** If that's a core requirement, it's the one piece every option here forces you to build yourself, regardless of which you pick.

---

## 1. redpangilinan/iotawise — best fit (70% coverage)

- **URL:** https://github.com/redpangilinan/iotawise
- **Stars:** 264 · **Last commit:** 2025-10-29 · **License:** MIT
- **Verified (66.7/100):** active in the last 12mo, 3+ contributors. Not verified: no CI config found.
- **Deployability (33.3/100):** ships a `.env.example`. Not verified: no Dockerfile/compose, no one-click deploy button.

| Requirement | Status | Evidence |
|---|---|---|
| Streak tracking | Present | "Activity Streak Monitoring" listed as a feature |
| Social accountability | Missing | No mention anywhere in the README |
| Reminders | Partial | "Web Push Notifications (coming soon)" — explicitly not shipped yet |
| Progress visualization | Present | "Dashboard Analytics" feature |
| Multi-user | Present | "Google Authentication" implies per-user accounts |

**Missing slice to build:** social accountability (partners/groups/sharing), finish push notifications (currently unshipped).

---

## 2. lehashree/eco-habit-tracker (40% coverage)

- **URL:** https://github.com/lehashree/eco-habit-tracker
- **Stars:** 53 · **Last commit:** 2026-04-05 · **License:** MIT
- **Verified (33.3/100):** active in the last 12mo. Not verified: fewer than 3 contributors (looks like a solo project), no CI config.
- **Deployability (0/100):** no Dockerfile/compose, no `.env.example`, no deploy button.

| Requirement | Status | Evidence |
|---|---|---|
| Streak tracking | Present | "🔥 Streak system to stay consistent" |
| Social accountability | Missing | No mention |
| Reminders | Missing | Not in feature list or roadmap |
| Progress visualization | Present | "📊 Weekly progress visualization" |
| Multi-user | Missing | README's own "Future Improvements" list includes "🔐 User authentication" — confirms it doesn't exist yet |

**Missing slice to build:** social accountability, reminders, user accounts/multi-user (author has already flagged this as not-yet-built).

---

## 3. MuffinTheDragon/daily-habit-tracker (40% coverage)

- **URL:** https://github.com/MuffinTheDragon/daily-habit-tracker
- **Stars:** 80 · **Last commit:** 2026-01-04 · **License:** MIT
- **Verified (33.3/100):** active in the last 12mo. Not verified: fewer than 3 contributors, no CI config.
- **Deployability (0/100):** no Dockerfile/compose, no `.env.example`, no deploy button (live demo is hosted, but nothing in-repo automates deployment).

| Requirement | Status | Evidence |
|---|---|---|
| Streak tracking | Present | "Streaks based, track and beat your longest streaks", plus Duolingo-style streak freezes |
| Social accountability | Missing | No mention |
| Reminders | Missing | No mention |
| Progress visualization | Present | "Visual map for tracking consistency" |
| Multi-user | Missing | No auth/accounts mentioned; positions itself as offline-first single-user |

**Missing slice to build:** social accountability, reminders, user accounts/multi-user.

---

## 4. daya0576/beaverhabits — most mature, weakest fit for this idea (20% coverage)

- **URL:** https://github.com/daya0576/beaverhabits
- **Stars:** 1,813 · **Last commit:** 2026-08-09 · **License:** BSD-3-Clause
- **Verified (100/100):** active in the last 12mo, 3+ contributors, has CI.
- **Deployability (0/100):** ships Docker run/compose instructions in prose, but scout.py found no `Dockerfile`/`docker-compose.yml` in the repo tree itself, and no `.env.example`.

| Requirement | Status | Evidence |
|---|---|---|
| Streak tracking | Partial | Repo is topic-tagged `streaks`, but the visible README doesn't describe streak mechanics directly — full feature list lives in an external wiki this tool didn't fetch |
| Social accountability | Missing | No mention |
| Reminders | Missing | No mention |
| Progress visualization | Missing | No mention in visible README (may exist in the wiki, unverified) |
| Multi-user | Partial | `TRUSTED_LOCAL_EMAIL` env var implies an auth/account concept, but this reads as single-tenant self-hosting, not social multi-user |

**Note on ranking:** this is by far the most popular, actively maintained, best-run project of the four (1.8k stars, CI, 3+ contributors) — but it's the weakest match for *this specific idea's* requirements based on visible evidence. Worth a manual look at its wiki before ruling it out entirely, but it should not be the top pick on relevance grounds alone.

**Missing slice to build:** social accountability, reminders, progress visualization, (streak/multi-user need wiki verification).

---

## Bottom line

No repo here covers social accountability — that's custom work no matter what. **iotawise** is the strongest starting point (70% coverage, real auth, real dashboard, just needs social features + finished notifications bolted on). If popularity/maintenance maturity matters more than exact feature fit, **beaverhabits** is the safer long-term bet but needs more built on top.
