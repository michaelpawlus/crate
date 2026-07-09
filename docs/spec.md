# CRATE — Claude Code Handoff Spec

**Working name:** `crate` (as in crate-digging). Rename freely.
**One-liner:** A CLI agent that builds Spotify playlists the way an obsessive human curator would — by following trust networks of diggers, labels, and DJs rather than streaming-similarity patterns — and that learns your taste from structured feedback after every playlist.

---

## 1. Mission & Philosophy

The product exists to recreate the experience of having a friend with a great ear: someone whose whole identity is finding music, who digs across every genre, and whose recommendations surprise you *and* land. The tagline ethos: **quality always, no genres.**

Design principles (these are constraints, not vibes):

1. **Curators over correlations.** The unit of trust is a human curator or curatorial institution, never a similarity score. Every track in a playlist must be traceable to at least one trusted human source ("provenance").
2. **Surprise is the product.** If the listener could have predicted the track, the system failed. But surprise must be *grounded* — a track earns its place through quality signals, not randomness.
3. **A playlist is an argument.** Sequencing matters. Track order should have an arc — an opening statement, an earned left turn, a landing. Never shuffle-bag output.
4. **The system learns, but never collapses into a similarity engine.** Feedback tunes the system's model of the listener, but exploration is protected by a hard floor. The failure mode to avoid: three weeks of feedback turns CRATE into Spotify.
5. **CLI-first, composable.** Plain commands, plain files, pipe-friendly output. State lives in human-readable files (JSON/JSONL/Markdown) in a local directory. No daemon, no database server.

---

## 2. Curator Behavior Model (first-class research, not plumbing)

Before writing retrieval code, the implementing agent must build an explicit behavioral model of how obsessive diggers work. This section is the seed; expand it into `docs/curator-model.md` during Phase 0 with real research.

### 2.1 The digger's core moves

- **Lateral personnel-hopping.** Musician credits are edges in a graph. Who played bass on this record → her 1974 solo LP → the engineer on that LP → everything else he touched. Discogs credits are the canonical dataset for this.
- **Label-as-quality-floor.** Certain labels function as pre-vetted quality signals: a curator will buy anything on a label they trust. Reissue labels (Numero Group, Light in the Attic, Analog Africa, Soundway, Awesome Tapes From Africa, Strut) are *meta-diggers* — years of human excavation already done.
- **Curator-chaining.** Trusted ears point to other trusted ears. A DJ's guest mix introduces a new DJ; a compilation's liner notes name the collector who sourced it. The trust network grows by referral, not by search.
- **Scene archaeology.** Given one great record from a scene (city + era + micro-genre), assume there are ten more nearby. Dig the scene, not the sound.
- **Version-hunting.** Covers, dubs, edits, and samples as bridges between worlds. A digger hears a sample and chases the original; hears an original and chases who flipped it.
- **The "first this, then that" instinct.** Sequencing logic: open accessible, earn trust, then place the challenging track where the listener is warmed up. End with something that resolves. Spotify optimizes skip-rate; a curator deliberately risks a skip at track 4 because track 3 earned it.
- **Recency without hype.** Diggers surface *new* artists too — but via trusted filters (a label's new signing, a radio host's first play, a Bandcamp Daily feature), not charts.

### 2.2 The digger's mindset (encode as agent prompt values)

- Quality is genre-agnostic and era-agnostic.
- Obscurity is not a virtue by itself; a famous track can belong if it's the *right* famous track in context.
- Every recommendation is personal — the curator holds a model of the listener and picks *for them*, including calculated stretches slightly beyond their current taste.
- Confidence with humility: strong opinions on what's great, genuine curiosity about what they haven't heard.

### 2.3 Trusted source registry (initial seed — expand during Phase 0)

Maintained as `sources.yaml`, each entry with: name, type (radio show / reissue label / publication / list-community / individual), access method (API, scrape, RSS, manual), trust weight (0–1, tunable by feedback), and notes on what they're best for.

Seed set:

- **Radio/shows:** NTS (show archives + tracklists), WFMU (playlist archives), dublab, Worldwide FM / Gilles Peterson, The Lot Radio, BBC 6 Music selected shows
- **Reissue labels:** Numero Group, Light in the Attic, Analog Africa, Soundway, Strut, Habibi Funk, Mississippi Records, Awesome Tapes From Africa
- **Publications/blogs:** Bandcamp Daily, Aquarium Drunkard, The Quietus, Passion of the Weiss
- **Communities/lists:** Rate Your Music charts and user lists, Discogs (credits graph + collector want-lists), r/listentothis (weak signal, use for triangulation only)
- **Individuals:** Gilles Peterson, Floating Points (as digger), Madlib/egon (Now-Again), Zach Cowie, Jamz Supernova — represented via their shows, mixes, and published lists

**Legal/practical note for the implementer:** prefer official APIs and RSS where available; where scraping is required, respect robots.txt and cache aggressively. Some sources may need a manual-ingest path (paste a tracklist into a file) as a fallback — build that path first since it always works.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────┐
│  crate dig  (main command)                          │
│                                                     │
│  1. INTENT      read brief + taste profile          │
│  2. SOURCE      agentic research across registry    │
│  3. TRIANGULATE score candidates (provenance,       │
│                 cross-source hits, fit, stretch)    │
│  4. SEQUENCE    arc-aware ordering                  │
│  5. RESOLVE     match to Spotify URIs               │
│  6. PUBLISH     create playlist via Spotify API     │
│  7. LOG         write playlist record for feedback  │
└─────────────────────────────────────────────────────┘
        state in ~/.crate/  (all human-readable)
```

### 3.1 State directory layout

```
~/.crate/
  sources.yaml          # trusted source registry with weights
  taste.md              # narrative taste profile (agent-maintained, human-editable)
  taste-signals.json    # structured learned parameters (see §5)
  history/
    2026-07-12-brief.md         # the brief used
    2026-07-12-playlist.json    # tracks, provenance, sequencing rationale
    2026-07-12-feedback.jsonl   # per-track + whole-playlist feedback
  cache/                # scraped tracklists, Discogs lookups, etc.
  exclusions.json       # tracks/artists already used or explicitly banned
```

Human-readable state is a feature: the user can open `taste.md` and edit it directly, and the agent must treat manual edits as authoritative.

### 3.2 Pipeline stages

**INTENT.** Merge three inputs: (a) an optional per-run brief (`--brief "rainy Sunday, instrumental-leaning"`), (b) `taste.md`, (c) `taste-signals.json`. Produce a run spec: target length (default 15 tracks / ~60 min), familiarity ratio, stretch budget, mood constraints.

**SOURCE.** The agentic core. The agent picks 4–7 sources from the registry (weighted by trust score and rotation — never the same set twice in a row), then executes digger moves: pull recent tracklists, chain one or two Discogs credit-hops from a seed track, check what a trusted reissue label released this quarter, cross-reference an RYM list. Target: a candidate pool of 60–120 tracks with provenance attached to each (`{track, artist, source, source_type, why}`).

**TRIANGULATE.** Score each candidate:

- *Provenance weight* — trust score of the source(s) that surfaced it
- *Cross-source bonus* — appeared independently in ≥2 unrelated sources (the strongest quality signal this system has; weight it heavily)
- *Fit* — matches the run spec's mood/energy constraints
- *Stretch value* — estimated distance from the user's current taste centroid; some distance is *rewarded* up to the stretch budget
- *Freshness* — not in `exclusions.json`, not overplayed in user's own Spotify history (optional: read user's top tracks via API and penalize overlap)

**SEQUENCE.** Order the top ~15 as an arc. The agent writes a one-line rationale per position ("track 4 is the left turn; track 3's outro earns it"). Store rationale in the playlist record — it's also what makes feedback interpretable later.

**RESOLVE.** Match to Spotify catalog via Search API. Expect misses (deep cuts often aren't on Spotify). Rules: try album-context search, then artist+track fuzzy match; if confidence is low, drop rather than substitute a wrong version (cover/karaoke pollution is the classic failure). Log unresolvable gems to `history/*-unresolved.md` — these are often the best finds; surface them to the user with Bandcamp/YouTube links.

**PUBLISH.** Create the playlist via Spotify Web API (`playlist-modify-private` scope, OAuth PKCE flow, token cached in `~/.crate/auth.json`). Playlist description gets the run's thesis sentence. Also write a local `.md` companion with full provenance per track — this is the "liner notes" and a key differentiator.

### 3.3 CLI surface

```
crate init                      # OAuth setup, seed sources.yaml, taste interview
crate dig [--brief "..."] [--length N] [--dry-run]
crate feedback [playlist-id]    # interactive feedback session (see §5)
crate feedback --quick "loved 3,7,11; skip 5; too mellow overall"
crate taste                     # print current taste.md + key signals
crate taste edit                # open taste.md in $EDITOR
crate sources [add|weight|list]
crate history [show|replay]
crate doctor                    # auth, API health, cache status
```

Scheduling is the user's problem by design: `crate dig` in cron/systemd-timer. Add `--notify` (write a summary line to stdout suitable for a phone notification via ntfy or similar) but don't build a scheduler.

### 3.4 Implementation notes

- **Language:** Python (uv-managed) or TypeScript — implementer's choice; user works in WSL2/Ubuntu with Claude Code, so either composes fine. Python likely wins on scraping ergonomics.
- **Agent runtime:** the SOURCE/TRIANGULATE/SEQUENCE stages are LLM-agent work (Anthropic API with web access or Claude Code invoked headlessly). Keep prompts in `prompts/` as versioned Markdown — the curator-mindset values from §2.2 live in the system prompt.
- **Determinism boundary:** RESOLVE and PUBLISH are plain deterministic code. Never let the agent free-form call the Spotify API; give it a narrow internal tool surface.

---

## 4. What "quality" means operationally

Because "quality always" is the brand promise, make the definition explicit and testable:

1. **Human provenance** (hard requirement) — every track traceable to a trusted human source.
2. **Triangulation** (strong signal) — independent appearance across unrelated sources.
3. **Durability signals** (soft) — reissued, sampled, covered, or on collector want-lists.
4. **Curatorial conviction** (agent judgment) — the agent must write one sentence per track on *why it belongs*; if it can't, the track is out. This forced-articulation step is cheap and measurably improves selection.

---

## 5. Self-Learning Feedback Loop

The system improves from feedback after every playlist, with guardrails that keep it from converging into a similarity engine.

### 5.1 Feedback capture

Two modes, both writing to `history/<date>-feedback.jsonl`:

**Interactive** (`crate feedback`): walks the playlist track by track. Per track: verdict (`love / like / fine / skip / hate`) plus optional free-text. Then whole-playlist questions: Was anything genuinely surprising? Did the surprise land? Sequencing — did the arc work? One thing you'd change?

**Quick** (`crate feedback --quick "..."`): free-text; the agent parses it into the same structured schema. This is the mode that survives real life — optimize for it.

Feedback record schema:

```json
{"playlist": "2026-07-12", "track_pos": 4, "track": "...", "verdict": "love",
 "note": "never heard anything like this", "tags": ["good-surprise"],
 "source": "NTS/Jamz Supernova", "stretch_score": 0.7}
```

### 5.2 What gets tuned (the learnable parameters)

All in `taste-signals.json`, all inspectable:

- **Source trust weights.** Sources whose tracks get loved gain weight; sources producing skips lose it. Use additive updates with a floor (no source drops below 0.1 — even a cold source deserves occasional rotation) and a decay term so old feedback fades.
- **Stretch calibration.** The key learned parameter: *how far can this listener be stretched, and in which directions?* Track the relationship between a track's stretch score and its verdict. If high-stretch tracks keep landing, raise the stretch budget; if they keep missing, lower it — but never below the exploration floor (§5.4).
- **Familiarity ratio.** Learned mix of anchor tracks (near taste centroid) vs. discoveries.
- **Mood/energy priors.** Time-of-week patterns if playlists are scheduled (Sunday runs skew mellow, etc.).
- **Sequencing preferences.** Does this listener tolerate the track-4 left turn, or should challenges come later?
- **Negative space.** Hard exclusions (hated artists, "never again" attributes) accumulate in `exclusions.json`.

### 5.3 The taste narrative (`taste.md`)

Alongside numeric signals, the agent maintains a *prose* taste profile — the way a human friend holds a model of you ("loves rhythmic complexity; allergic to gloss; a sucker for a great bassline; give him one curveball per playlist, not four"). After each feedback session, the agent proposes a diff to `taste.md`; the user can accept, edit, or reject. Prose is the primary model, numbers are the tuning knobs — this ordering matters. It keeps the system interpretable and keeps the human in the loop on their own taste model.

### 5.4 Anti-convergence guardrails (critical)

Feedback loops on recommenders naturally collapse toward the mean of past likes. Explicit countermeasures:

1. **Exploration floor:** ≥20% of every playlist must come from sources or directions with *no feedback history*. Non-negotiable, not tunable downward by the learning loop.
2. **Distinguish bad surprise from failed surprise.** A skip on a high-stretch track with no "hate" signal is *not* strong negative evidence — it may be wrong-day, wrong-mood. Only repeated misses in the same direction should move weights. Encode this in the update rule (high-stretch skips get ~⅓ the negative weight of low-stretch skips).
3. **Source rotation:** never draw from an identical source set two runs in a row, regardless of weights.
4. **Periodic self-audit:** every ~8 playlists, the agent runs a drift check — compare recent playlists' diversity (era spread, geography, genre entropy) against the first 3 playlists. If diversity has contracted >30%, it reports this to the user and proposes a "reset run" with stretch budget maxed.
5. **Feedback on the feedback:** occasionally (`crate feedback` every ~5th session) ask the meta-question: "Are these playlists getting more or less surprising? Better or worse?" — a direct measurement of the thing the product exists to deliver.

---

## 6. Build Phases

**Phase 0 — Research & scaffolding (1–2 sessions)**
Expand §2 into `docs/curator-model.md` with real source research (which sources have accessible tracklists, which need manual ingest). Write `sources.yaml` seed. Run the taste interview → initial `taste.md`. *Exit criteria: agent can articulate the digger playbook and the source registry has ≥8 working access methods.*

**Phase 1 — MVP pipeline (the walking skeleton)**
`crate dig --dry-run` end-to-end: brief → source (3 sources, manual-ingest fallback allowed) → triangulate → sequence → output a Markdown playlist with provenance and rationale. No Spotify yet. *Exit criteria: user reads the Markdown and would actually want to hear the playlist.*

**Phase 2 — Spotify integration**
OAuth PKCE flow, RESOLVE with the confidence rules, PUBLISH, unresolved-gems report. *Exit criteria: `crate dig` produces a playable playlist in the user's Spotify.*

**Phase 3 — Feedback loop**
Both feedback modes, `taste-signals.json` updates, `taste.md` diffs, exclusions. *Exit criteria: two feedback sessions demonstrably change the third playlist, and the user can see why via `crate taste`.*

**Phase 4 — Guardrails & polish**
Anti-convergence mechanisms, drift audit, source rotation, `crate doctor`, cron-friendly output. *Exit criteria: 8-playlist simulated run shows no diversity collapse.*

---

## 7. Risks & open questions

- **Source access fragility.** Tracklist scraping breaks. Mitigation: manual-ingest path is first-class, cache everything, `crate doctor` reports dead sources.
- **Spotify catalog gaps.** The best digs often aren't streamable. Mitigation: unresolved-gems report reframes this as a feature (your friend saying "this one you have to find on Bandcamp").
- **Spotify API terms.** Verify current developer-policy constraints on programmatic playlist creation for personal use during Phase 2 (personal-use apps are generally fine; don't design for multi-user distribution yet).
- **LLM cost per run.** A full agentic dig may be 50–150 LLM calls. Fine for weekly personal use; note it and cache aggressively.
- **Cold start.** First 2–3 playlists run on the taste interview alone. Set expectations: the product gets good at playlist ~4.
- **Open question:** should feedback eventually include *implicit* signals (Spotify listening history for the playlist — did you actually finish it)? Powerful but adds API polling complexity. Park for Phase 5.

---

## 8. Definition of done (v1)

A cron job runs `crate dig` Friday mornings. A playlist appears in Spotify with a thesis in its description. A Markdown liner-notes file explains where every track came from and why it's there. Sunday, the user runs `crate feedback --quick "..."` from their phone via SSH or their terminal. By week 6, the playlists feel like they were made by someone who *knows* them — and still, every week, at least two tracks they never would have found.
