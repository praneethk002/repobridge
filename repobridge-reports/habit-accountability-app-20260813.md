# RepoBridge Report: habit accountability app (conversational scheduling, alarm-style reminders, AI night/morning routines)

## No strong match — closest reference: Pratham754/ZenSlice-Release

Still no strong match after a targeted second search. Tier 1 (whole-project search) found ZenSlice, bundel, and neuropathAI, none close and all wrong-platform. Tier 2 searched specifically for the idea's three technical primitives — full-screen alarm, background scheduler, conversational AI chat — and found exactly one new, more relevant reference: dnschat, a real React Native/Expo app with a working LLM chat interface (its DNS-over-TXT transport is a novelty, irrelevant here, but the chat-UI + LLM-integration pattern is a legitimate reference for the conversational-onboarding piece). Nothing surfaced for full-screen alarm or background scheduling specifically — those remain genuinely unaddressed by anything findable on GitHub. Joint coverage across the top 3 candidates is 33.3%, still well short of the 70% bar, so this stays a custom-build call: use dnschat as a conceptual reference for the chat layer, and expect the alarm/scheduling core to be built from platform primitives (Android full-screen intents, iOS time-sensitive notifications) rather than any existing library found here.

| Match | Features left | Est. time remaining | Tokens saved |
|---|---|---|---|
| 16.7% | 5 of 6 (5 missing, 0 partial) | ~6.7d (~40h) | ~15.0K (~17%) |

*Estimate, not a measurement: 8h per missing feature, 3h per partial one; token savings assume ~15,000 tokens to generate one feature from scratch, at half that for a partial. Actual time and token cost depend heavily on your stack and the specific features.*

*No single repo or small combination clears a strong-fit bar (≥70%) for this idea — most of it will need custom building. Numbers above are relative to the closest reference found, not a recommended pick.*

---

Idea requirements evaluated: conversational onboarding and goal scheduling, full-screen alarm-style reminders, reliable background scheduling, night wind-down routine, morning wake and planning routine, periodic screen-time check-ins.

## Tier 1 — whole-project search

3 candidates survived search + hard filters (license present and non-copyleft, pushed within 12 months, stars ≥ 10 after two broadening retries — the initial React Native-focused queries returned only generic UI/infra libraries dominated by star count, not actual habit/wellness apps, and a min-stars-30 domain-targeted retry returned zero results before this final pass).

Coverage topped out at 16.7% (ZenSlice) — below the 70% strong-fit bar, so this triggered Tier 2.

## Tier 2 — component search (triggered by Tier 1 landing in custom_build)

Rather than stop at "nothing found," searched specifically for the idea's 3 technical primitives instead of the whole-app framing:

- **Full-screen alarm** (React Native full-screen alarm / lock-screen takeover, critical alert full-screen intent) — **0 new candidates.** This capability appears to be genuinely rare or unindexed under these terms on GitHub.
- **Background scheduler** (React Native reliable background task scheduler, background fetch exact alarm) — **0 new candidates.**
- **Conversational AI chat** (React Native AI chatbot SDK, LLM chat interface) — **1 new candidate: dnschat.**

Search floor had to drop to min-stars 5 (from 30) before even that one candidate survived — this is a genuinely under-served niche, not a search-phrasing problem alone.

4 candidates total after merging Tier 1 + Tier 2, re-ranked by coverage. All 4 are shown below.

**Platform caveat that applies to every candidate here:** only dnschat is React Native. ZenSlice is an Electron desktop app (Windows), Bundel is native Android/Kotlin, neuropathAI is a Firefox browser extension. Even where a requirement is marked Present or Partial below, most of this code isn't directly portable into a React Native codebase — treat non-RN candidates as conceptual references (how did they solve this problem), not forkable starting points.

---

## 1. Pratham754/ZenSlice-Release — closest reference (16.7% coverage)

*Found via: whole-project search*

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

*Found via: whole-project search*

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

**Note:** highest star count (294) and best-maintained of the four (CI, 3+ contributors) — but that maturity is on a feature (notification batching) that's only tangentially related to this idea. Worth a look at its Android background-scheduling implementation as a technical reference even though the product concept doesn't match.

**Missing slice to build:** essentially everything specific to this idea.

---

## 3. mneves75/dnschat (8.3% coverage)

*Found via: component search — conversational AI chat*

- **URL:** https://github.com/mneves75/dnschat
- **Stars:** 74 · **Last commit:** 2026-08-09 · **License:** MIT
- **Verified (66.7/100):** active in the last 12mo, has CI. Not verified: fewer than 3 contributors.
- **Deployability (0/100):** no Dockerfile/compose, no `.env.example`, no deploy button.

| Requirement | Status | Evidence |
|---|---|---|
| Conversational onboarding and goal scheduling | Partial | "provides a modern, ChatGPT-like chat interface... to communicate with an LLM" — a real React Native/Expo chat UI + LLM integration, but a generic chat log, not a scheduling-building onboarding flow |
| Full-screen alarm-style reminders | Missing | No mention |
| Reliable background scheduling | Missing | No mention |
| Night wind-down routine | Missing | No mention |
| Morning wake and planning routine | Missing | No mention |
| Periodic screen-time check-ins | Missing | No mention |

**Note:** the only candidate actually written in React Native/Expo. Its DNS-over-TXT transport (sending chat prompts as DNS queries to avoid API keys) is a novelty specific to its own concept and irrelevant here — any real build would use a normal HTTP LLM API instead. What's genuinely reusable is the chat-UI shell and message-history pattern in an RN/Expo app, which this run's Tier 1 search (framed around "habit tracker" and "wellness") would never have surfaced — it only turned up by searching for the conversational-chat component specifically.

**Missing slice to build:** everything except the chat-UI shell pattern.

---

## 4. Modaniels/neuropathAI (8.3% coverage)

*Found via: whole-project search*

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

**Note:** the "send session data to an LLM, get coaching back" pattern is worth referencing conceptually, but dnschat (above) is the stronger reference for the conversational piece specifically, since it's actually React Native rather than a Firefox extension.

**Missing slice to build:** everything except the general "call an LLM for personalized coaching" pattern.

---

## Bottom line

This is genuinely novel territory, confirmed by two search passes rather than assumed after one: no existing open-source project combines conversational AI scheduling, alarm-grade full-screen interrupts, and AI-driven night/morning routine calls into one app, and a dedicated second search for the idea's hardest technical pieces still didn't find a full-screen-alarm or background-scheduler library. The realistic build path is composing narrow, single-purpose pieces:

- A **full-screen alarm/lock-screen package** for React Native (Android full-screen intents + iOS time-sensitive notifications) — still the single hardest piece, and the Tier 2 search confirms it's not something a GitHub keyword search surfaces easily. Worth checking native Android/iOS ecosystems directly (not RN-wrapped) for prior art, or accepting this is closer to greenfield.
- A **background task scheduler** reliable enough to fire the night/morning calls even when the app is closed — same story, nothing found.
- An **LLM chat integration** for the conversational onboarding — dnschat's chat-UI shell (ignore its DNS transport) and neuropathAI's "session → LLM → coaching" pattern are both legitimate conceptual starting points here.
- Your own scheduling/calendar logic and screen-time-check-in timer — genuinely custom, nothing here comes close.
