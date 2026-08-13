# RepoBridge Report: habit accountability app (conversational scheduling, alarm-style reminders, AI night/morning routines)

## No strong match — closest reference: Pratham754/ZenSlice-Release

Nothing found is close. The best individual match, ZenSlice, is a Windows desktop screen-time tracker — a different platform entirely from the React Native mobile app this idea needs — and it only covers the periodic check-in requirement. Bundel and neuropathAI each cover at most a sliver, and are Android-notification and Firefox-extension projects respectively, neither reusable as a mobile codebase. The core of this idea — conversational AI onboarding that builds a schedule, alarm-grade full-screen interrupts, and scheduled night/morning routine calls — doesn't have an existing open-source analog. Expect to build most of this from scratch, likely composing narrow single-purpose libraries (a full-screen-alarm package, a background scheduler, an LLM chat SDK) rather than forking any one app.

| Match | Features left | Est. time remaining | Tokens saved |
|---|---|---|---|
| 16.7% | 5 of 6 (5 missing, 0 partial) | ~6.7d (~40h) | ~15.0K (~17%) |

*Estimate, not a measurement: 8h per missing feature, 3h per partial one; token savings assume ~15,000 tokens to generate one feature from scratch, at half that for a partial. Actual time and token cost depend heavily on your stack and the specific features.*

*No single repo or small combination clears a strong-fit bar (≥70%) for this idea — most of it will need custom building. Numbers above are relative to the closest reference found, not a recommended pick.*

---

Idea requirements evaluated: conversational onboarding and goal scheduling, full-screen alarm-style reminders, reliable background scheduling, night wind-down routine, morning wake and planning routine, periodic screen-time check-ins.

3 candidates survived search + hard filters (license present and non-copyleft, pushed within 12 months, stars ≥ 10 after two broadening retries — the initial React Native-focused queries returned only generic UI/infra libraries dominated by star count, not actual habit/wellness apps, and a min-stars-30 domain-targeted retry returned zero results before this final pass). All 3 are shown below.

**Platform caveat that applies to every candidate here:** none is React Native. ZenSlice is an Electron desktop app (Windows), Bundel is native Android/Kotlin, neuropathAI is a Firefox browser extension. Even where a requirement is marked Present or Partial below, the underlying code isn't directly portable into a React Native codebase — treat these as conceptual references (how did they solve this problem), not forkable starting points.

---

## 1. Pratham754/ZenSlice-Release — closest reference (16.7% coverage)

- **URL:** https://github.com/Pratham754/ZenSlice-Release
- **Stars:** 11 · **Last commit:** 2026-07-16 · **License:** Apache-2.0
- **Verified (33.3/100):** active in the last 12mo. Not verified: fewer than 3 contributors (solo project), no CI config.
- **Deployability (0/100):** ships as a signed/unsigned desktop release, but no Dockerfile/compose, no `.env.example`, no deploy button — not applicable in the same way for a desktop Electron app.

| Requirement | Status | Evidence |
|---|---|---|
| Conversational onboarding and goal scheduling | Missing | No conversational or goal-setting feature — it's a passive tracker |
| Full-screen alarm-style reminders | Missing | Only a Windows toast notification at limit thresholds, not full-screen |
| Reliable background scheduling | Missing | Runs in system tray tracking usage, but doesn't schedule reminders/events |
| Night wind-down routine | Missing | No mention |
| Morning wake and planning routine | Missing | No mention |
| Periodic screen-time check-ins | Present | "Set a daily cap... Get a Windows notification 5 minutes before the limit and again when you hit it" |

**Missing slice to build:** everything except the check-in concept, and even that needs porting from desktop-polling to mobile-appropriate (battery-safe) tracking.

---

## 2. code-with-the-italians/bundel (8.3% coverage)

- **URL:** https://github.com/code-with-the-italians/bundel
- **Stars:** 294 · **Last commit:** 2026-08-13 · **License:** Apache-2.0
- **Verified (100/100):** active in the last 12mo, 3+ contributors, has CI.
- **Deployability (0/100):** no Dockerfile/compose, no `.env.example`, no deploy button.

| Requirement | Status | Evidence |
|---|---|---|
| Conversational onboarding and goal scheduling | Missing | No mention |
| Full-screen alarm-style reminders | Missing | Batches and releases notifications at set times, not full-screen/unmissable |
| Reliable background scheduling | Partial | "groups up notifications and only releases them in batches, at set times" — timed release logic exists, but for notification batching, not alarm-grade scheduling |
| Night wind-down routine | Missing | No mention |
| Morning wake and planning routine | Missing | No mention |
| Periodic screen-time check-ins | Missing | Reduces notification interruptions rather than checking in on usage |

**Note:** highest star count (294) and best-maintained of the three (CI, 3+ contributors) — but that maturity is on a feature (notification batching) that's only tangentially related to this idea. Worth a look at its Android background-scheduling implementation as a technical reference even though the product concept doesn't match.

**Missing slice to build:** essentially everything specific to this idea.

---

## 3. Modaniels/neuropathAI (8.3% coverage)

- **URL:** https://github.com/Modaniels/neuropathAI
- **Stars:** 11 · **Last commit:** 2026-01-17 · **License:** MIT
- **Verified (33.3/100):** active in the last 12mo. Not verified: fewer than 3 contributors, no CI config.
- **Deployability (0/100):** browser extension, no Dockerfile/compose/.env.example/deploy button applicable.

| Requirement | Status | Evidence |
|---|---|---|
| Conversational onboarding and goal scheduling | Partial | "Personalized coaching after each session" via Gemini AI — post-session AI insight, not an upfront onboarding conversation that builds a schedule |
| Full-screen alarm-style reminders | Missing | A draggable floating widget, not a full-screen takeover |
| Reliable background scheduling | Missing | No mention |
| Night wind-down routine | Missing | No mention |
| Morning wake and planning routine | Missing | No mention |
| Periodic screen-time check-ins | Missing | User-initiated start/stop sessions, not automatic periodic check-ins |

**Note:** the one genuinely relevant idea here is architectural, not code — it calls Gemini after a tracked session to generate personalized coaching text. That "send session data to an LLM, get coaching back" pattern is worth referencing conceptually for the conversational scheduling feature, even though the extension itself (Firefox, browser-usage tracking) has nothing else in common with a mobile alarm/routine app.

**Missing slice to build:** everything except the general "call an LLM for personalized coaching" pattern.

---

## Bottom line

This is genuinely novel territory — no existing open-source project combines conversational AI scheduling, alarm-grade full-screen interrupts, and AI-driven night/morning routine calls into one app. The realistic build path isn't "fork X," it's composing a few narrow, single-purpose pieces:

- A **full-screen alarm/lock-screen package** for React Native (Android full-screen intents + iOS time-sensitive notifications) — this is the single hardest technical piece and the one most worth a dedicated search on its own, separate from "habit tracker" framing.
- A **background task scheduler** reliable enough to fire the night/morning calls even when the app is closed.
- An **LLM chat integration** for the conversational onboarding and nightly/morning check-ins (neuropathAI's "session data → LLM → coaching text" pattern is a reasonable conceptual starting point).
- Your own scheduling/calendar logic and screen-time-check-in timer — genuinely custom, nothing here comes close.

Worth a follow-up RepoBridge run scoped narrowly to just "React Native full-screen alarm" or "React Native local notifications critical alert" — that's the piece most likely to have a real, forkable open-source match, separate from the "whole app" framing this run used.
