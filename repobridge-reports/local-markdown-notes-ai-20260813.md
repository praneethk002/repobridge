# RepoBridge Report: local-first markdown notes app with local AI semantic clustering & tagging

## No strong match — closest reference: your-papa/obsidian-Smart2Brain

Close, but no strong match. Tier 1 (whole-project search) topped out at 30% — iwe and Toney both handle flat-markdown storage well but neither has any embedding-based AI. Tier 2 (searching the Obsidian/Logseq plugin ecosystem specifically) found obsidian-Smart2Brain, which genuinely does what was asked: it embeds your vault's notes into vectors via Ollama and runs entirely offline, doubling coverage to 60%. What it doesn't have is a standing auto-clustering view (its embeddings power a chat/Q&A interface, not a passive "related notes" grouping) or tag suggestion at all. The other three Tier 2 finds (claudian, Niki-AI, geminese) looked promising by name but all embed a cloud coding-agent CLI as a vault collaborator, not local embeddings — a real false-positive pattern worth naming: "AI plugin for Obsidian" surfaces agentic-coding-assistant plugins at least as often as semantic-search plugins. Combining candidates doesn't help further — nothing else contributes a capability Smart2Brain lacks, so composition caps at the same 60%. This is a genuine near-miss: building on Smart2Brain's embedding pipeline and adding a clustering view + tag suggestion on top is a much smaller lift than building the embedding infrastructure from scratch, even though it doesn't clear the 70% bar for an unqualified single-pick recommendation.

| Match | Features left | Est. time remaining | Tokens saved |
|---|---|---|---|
| 60% | 3 of 5 (1 missing, 2 partial) | ~2.3d (~14h) | ~45.0K (~60%) |

*Estimate, not a measurement: 8h per missing feature, 3h per partial one; token savings assume ~15,000 tokens to generate one feature from scratch, at half that for a partial. Actual time and token cost depend heavily on your stack and the specific features.*

*No single repo or small combination clears a strong-fit bar (≥70%) for this idea — most of it will need custom building. Numbers above are relative to the closest reference found, not a recommended pick.*

---

Idea requirements evaluated: local-first flat markdown file storage, minimalist markdown editor UI, local on-device AI embeddings, automatic semantic note clustering, semantic tag suggestion.

## Tier 1 — whole-project search

6 candidates survived (search spanned both standalone apps and plugin ecosystems, per the earlier scope decision). Best individual coverage: 30% (iwe, Toney) — below the 70% bar, so this triggered Tier 2.

## Tier 2 — component search (triggered by Tier 1 landing in custom_build)

Searched the idea's 3 technical primitives specifically instead of the whole-app framing:

- **Local embedding model integration** (Ollama, onnx/sentence-transformers) — 0 new candidates as a standalone piece, but the capability showed up bundled inside a plugin below.
- **Semantic vector similarity/clustering** — 0 new candidates as a standalone piece, same story.
- **Obsidian/Logseq semantic AI plugin** — **4 new candidates**, and this is where the real find was: obsidian-Smart2Brain. The other three (claudian, geminese, Niki-AI) are a distinct, common plugin pattern — embedding a cloud coding-agent CLI (Claude Code, Gemini CLI) as a vault collaborator with file/bash access — not semantic embeddings at all, despite "AI" in every description.

10 candidates total after merging, re-ranked by coverage. Full comparison for all 10 is in the dashboard/JSON; detailed cards below cover the ones that actually differentiate.

---

## 1. your-papa/obsidian-Smart2Brain — closest reference (60% coverage)

*Found via: component search — obsidian/logseq semantic AI plugin*

- **URL:** https://github.com/your-papa/obsidian-Smart2Brain
- **Stars:** 1,212 · **Last commit:** 2026-08-12 · **License:** MIT
- **Verified (100/100):** active in the last 12mo, 3+ contributors, has CI.
- **Deployability (0/100):** no Dockerfile/compose, no `.env.example`, no deploy button — but it's an Obsidian plugin, installed via Obsidian's own plugin system, so this dimension doesn't really apply the same way.

| Requirement | Status | Evidence |
|---|---|---|
| Local-first flat markdown file storage | Present | Obsidian plugin operating directly on your vault's flat markdown notes — "It can directly access and process your notes" |
| Minimalist markdown editor UI | Partial | Inherits Obsidian's own editor (the plugin adds a chat sidebar, not its own editor) — reasonably clean, but not marketed as minimalist specifically |
| Local on-device AI embeddings | Present | "All your notes will be embedded into vectors and then retrieved based on the similarity to your query"; runs via Ollama, "operate completely offline" |
| Automatic semantic note clustering | Partial | RAG pipeline retrieves notes by embedding similarity for chat/Q&A — real semantic infrastructure, but query-driven ("chat with your notes"), not a standing auto-grouped view |
| Semantic tag suggestion | Missing | No tagging feature — it's a Q&A/chat interface, not a tag suggester |

**Missing slice to build:** an always-on clustering/grouping view (vs. the existing query-driven chat) and tag suggestion — both of which can reuse this plugin's existing embedding pipeline rather than building one from scratch.

---

## 2. iwe-org/iwe (30% coverage) — a notable non-match despite looking strong

*Found via: whole-project search*

- **URL:** https://github.com/iwe-org/iwe
- **Stars:** 1,394 · **Last commit:** 2026-08-12 · **License:** Apache-2.0
- **Verified (100/100):** active in the last 12mo, 3+ contributors, has CI.

| Requirement | Status | Evidence |
|---|---|---|
| Local-first flat markdown file storage | Present | "Your notes are .md files in a local directory... No cloud, no database, no lock-in." |
| Minimalist markdown editor UI | Partial | Not an editor itself — an LSP adding IDE features (search, refactor, rename) to VS Code/Neovim/Zed/Helix |
| Local on-device AI embeddings | Missing | "IWE itself has no built-in AI"; explicitly does "retrieval by structure, not similarity guessing" — the opposite approach from embeddings |
| Automatic semantic note clustering | Missing | Organizes via explicit links the user creates, not automatic semantic similarity |
| Semantic tag suggestion | Missing | — |

**Why this is worth flagging explicitly:** "knowledge graph" branding and a 1.4k-star, actively-maintained, well-documented project make this look like a strong candidate at a glance. It isn't, for this specific idea — it's built on a philosophically different approach (explicit structural links, not automatic semantic similarity) and says so directly in its own README. A quick skim could easily over-credit this one; the full evidence table is what catches it.

---

## 3-5. The "agentic coding assistant" plugins (30% each) — a naming false-positive to know about

*Found via: component search — obsidian/logseq semantic AI plugin*

**YishenTu/claudian** (14,746★, MIT, verified 100/100), **Momoyu404/geminese** (57★, MIT, verified 66.7/100), and **KeloYuan/Niki-AI** (54★, MIT, verified 33.3/100) all follow the same pattern: they embed a cloud coding-agent CLI (Claude Code, Gemini CLI) inside an Obsidian vault, giving it file read/write and bash access to act as a writing/coding collaborator. None do local embeddings, vector search, or semantic clustering — despite each one's description containing "AI." claudian in particular has by far the highest star count of any candidate in this report (14.7k), which is a good reminder that stars track a different kind of popularity (a generically useful AI-coding-in-Obsidian plugin) than fit for this specific idea.

**Missing slice, all three:** local embeddings, semantic clustering, tag suggestion — same gaps as everything else, none contribute anything Smart2Brain doesn't already cover.

---

## Also considered, lower relevance

| Repo | Coverage | Found via | Why it's here |
|---|---|---|---|
| SourcewareLab/Toney | 30% | whole-project search | Lightweight TUI markdown file manager — real flat-file handling, zero AI |
| tomboy-notes/tomboy-ng | 20% | whole-project search | Classic rich-text note app; markdown is an export format, not native storage; "automatic linking" is exact-title-match, not semantic |
| intrepidkarthi/dailyvox | 10% | whole-project search | iOS voice journal with genuine on-device AI, but for mood/voice analysis, not markdown notes |
| tehtbl/awesome-note-taking | 0% | whole-project search | A curated directory, not an app — surfaced as a search hit, not a usable candidate itself |
| lifeos-plus/lifeos-cli | 0% | whole-project search | Broad SQLite/PostgreSQL-backed life-management CLI; notes are a minor feature, not flat markdown files |

Full evidence for all 10 (every requirement × every repo) is in the JSON sidecar and the dashboard's evidence disclosure.

---

## Bottom line

This is the closest RepoBridge has come to a real match across both test runs today — 60% coverage from a single, actively-maintained plugin is a genuinely strong starting point, just short of the unqualified single-pick bar. The realistic build path:

- **Start from obsidian-Smart2Brain's embedding pipeline** (Ollama-backed, offline, already proven) rather than building local embedding generation from scratch — that's the hardest piece, and it's solved.
- **Add a standing clustering/grouping view** on top of its existing vector store — the embeddings already exist, this is a UI + retrieval-pattern problem, not an infrastructure problem.
- **Add semantic tag suggestion** — same story, reuse the embeddings, add a suggestion UI.
- If a from-scratch standalone editor (rather than an Obsidian plugin) is a hard requirement, iwe's approach to flat-file markdown storage and Toney's minimalist file-navigation UI are the best structural references — but neither has any AI to build on, so that path means building the embedding layer from scratch on top of one of them, a meaningfully bigger lift than extending Smart2Brain.
