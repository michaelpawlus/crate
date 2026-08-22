# Rewiring the brain — implementation plan for `curator-dna-spec.md`

Status: Phases 0 and 1 **done and exercised in a live dig** (2026-08-22);
Phases 2-5 proposed. Written 2026-08-20 against commit `9e2e711`.
**Start at §9 (Phase 1 retrospective) — it is where the next session picks up.**

The spec (`curator-dna-spec.md`) is a behavioral taxonomy, not an architecture.
This maps its 16 patterns onto CRATE's actual modules, in the order that most
improves playlists soonest, and records the live probes that constrain the design.

---

## 0. Ground truth (probed 2026-08-20, not assumed)

Four facts, each verified by a live request, that decide major branches below.

**Spotify has no audio intelligence left for this app.** With the stored token:

| Endpoint | Result |
|---|---|
| `GET /v1/audio-features/{id}` | `403` bare-body |
| `GET /v1/audio-analysis/{id}` | `403` bare-body |
| `GET /v1/recommendations` | `404` |

Bare 403 with no "insufficient scope" is the removed/restricted-endpoint
signature already documented in `CLAUDE.md`. **P15 (intra-song moments) cannot be
built on Spotify audio data.** It has to be agent-authored annotation, stored as
opinion with provenance — see Phase 2.

**MusicBrainz recording-level credits are effectively empty for this corpus.**
`inc=artist-rels+work-rels+recording-rels` returned `[]` for D'Angelo "Devil's
Pie", Alice Coltrane "Journey in Satchidananda", and Mulatu Astatke "Yekermo
Sew"; James Brown "Funky Drummer" returned a single `performance` work-rel. MB
is **not** a credits graph for the music CRATE digs.

**Discogs is, and it needs no token.** Unauthenticated `GET
/database/search` and `GET /releases/{id}` both `200`. `extraartists` on an
obscure 1972 Hispavox release returned `Arranged By`, `Directed By`, `Guitar`
(×2), `Written-by` (×3) — exactly the personnel edges P9 traverses. Rate limit
is 25 req/min unauthenticated (60 with a free token). This is the crate-digger's
database and it is open.

**MusicBrainz is still the right release-awareness layer (P8).** `GET /release?
query=label:"Analog Africa"` returns clean label catalogs, and NTS tracklists
already carry per-track ISRC/MBID (`docs/source-access.md` §1) — a free identity
bridge from what a DJ played into the graph.

Consequence: **Discogs = the graph (P9/P10/P13). MusicBrainz = identity and
release awareness (P8). Spotify = resolution and delivery only.**

---

## 1. Where the current brain actually is

The pipeline is three LLM calls and one linear score:

- `pipeline/source.py` — weighted-random 4–7 sources → fetch → one agent call → pool
- `pipeline/triangulate.py` — one batched agent call (`fit`/`stretch`/`conviction`)
  → `score()` = `0.30·provenance + 0.25·cross + 0.25·fit + 0.20·stretch_reward`
- `pipeline/sequence.py` — one agent call for order + thesis

`learning.py` tunes source trust and stretch budget from feedback. **It has never
run.** `~/.crate/taste-signals.json` reads `playlists_generated: 1`,
`feedback_sessions: 0`, `stretch_history: []`. Whatever quality the playlists
have came from the prompts and the 26-source registry — the learning loop has
contributed nothing yet.

That is the single most important planning fact: **any pattern whose payoff
depends on accumulated feedback pays off at zero today.** So the phases below
fix judgment and assembly first, then build the funnel that generates signal,
and only then rewire the learning rules that consume it.

### Pattern coverage today

| | Pattern | State |
|---|---|---|
| P1 | Scheduled intake w/ quota | **absent** — everything is dig-time |
| P2 | Accepted-waste funnel | partial — 60–120 pool → 15, acceptance never measured |
| P3 | Canon/reference corpus | **absent** — taste is prose only |
| P4 | Incentive filter | **absent** — no incentive field on any source |
| P5 | Hysteretic trust | partial — symmetric additive + decay toward 0.5 |
| P6 | Rotating frontier | partial — rotates *sources*, never tags/scenes/geographies |
| P7 | Signed trust (contrary indicators) | **absent** — floor 0.1, cannot go negative |
| P8 | Release-awareness substrate | **absent** |
| P9 | Graph traversal | prompt-level only ("one personnel-hop"), nothing persists |
| P10 | Scene entities | **absent** — `region` is a free-text string |
| P11 | Context stored with music | partial — `sources[].why` yes, traversal path no |
| P12 | Human affective gate | machinery exists, **never invoked**; dig auto-publishes |
| P13 | Causal/lineage model | **absent** — `conviction` is vibe-level |
| P14 | Storytelling assembly | present — thesis + arc + rationale |
| P15 | Intra-song moments | **absent**, and Spotify can no longer supply it |
| P16 | Recontextualization | implicit in prompt, no explicit move |

---

## 2. Phase 1 — Judgment: lineage over vibes (P9, P13, P3, P4-prior) — DONE

The biggest immediate lever, and it needs no feedback history.

**New modules**

- `src/crate/discogs.py` — cached, rate-limited (25/min) client. `search_release`,
  `release_credits(id) -> [{name, role}]`, `artist_releases`. Reuses
  `fetchers.cached_fetch`; 24h TTL is already the house default.
- `src/crate/musicbrainz.py` — `releases_by_label`, `recording_by_isrc`,
  `mbid_for`. Identity + release awareness, 1 req/sec.
- `src/crate/graph.py` — the store. Human-readable per house rule:
  `~/.crate/graph/nodes.jsonl`, `~/.crate/graph/edges.jsonl`.
  Node kinds: `artist | producer | player | label | release | scene | track`.
  Edge kinds: `produced | played-on | arranged | written-by | released-on |
  reissued-by | sample-of | cover-of | scene-member | descendant-of`.
  Every edge carries `source` (which fetcher or which registry source asserted
  it) and `confidence` — an agent-asserted edge is never confused with a
  Discogs-attested one. API: `add_edge`, `neighbors(node, kinds, max_hops)`,
  `walk_from(seeds, budget)`.
- `src/crate/canon.py` + `~/.crate/canon.yaml` — the reference corpus (P3).
  Entries are lineages, not genres (house rule: no genres): a name, 3–8
  anchor records, and one sentence on what the lineage *does*. Seeded from the
  `crate init` interview; grows from `love` verdicts.

**Changed**

- `pipeline/source.py` — after registry fetch, run one graph pass: seed from
  high-affinity nodes (loved artists, trusted labels, this run's fetched
  tracklists), walk 1–2 hops through Discogs credits, and emit those as
  candidates. Provenance rule is unchanged and non-negotiable: the candidate's
  `source` stays the registry source that started the chain, and `why` records
  the traversal path (`Soundway → Analog Africa reissue → arranger X → …`).
  This is P11 as well — the path *is* the encounter context.
- `prompts/triangulate.md` — `conviction` must cite a lineage claim (who begat
  whom, which scene, which credit), not adjacency. Canon anchors go in the
  prompt: judge each candidate *relative to* the internalized references, per
  P3, rather than in a vacuum.
- `seeds.py` + `sources.yaml` — add `incentive: none|low|medium|promotional`
  to every source and audit all 26 (P4). This is a static prior with immediate
  effect, so it lands here rather than with the learning rewire. Bandcamp Daily
  is owned by the store selling the records; label sources vouch for their own
  output; publications carry ad relationships. `triangulate.score()` applies the
  penalty multiplicatively to the provenance term.
- `config.py` — `INCENTIVE_PENALTY = {"none": 1.0, "low": 0.9, "medium": 0.75,
  "promotional": 0.5}`, `GRAPH_MAX_HOPS = 2`, `GRAPH_CANDIDATES_PER_RUN`.
  Guardrail constants, not state — same rule as the existing block.

**New CLI**: `crate graph show <artist>`, `crate canon list|add`.

**Tests**: graph store, traversal, scoring with incentive, canon load — all
deterministic, network mocked, per the house convention.

**Deferred out of Phase 1: scene entities (P10).** The plan scoped `scene` as a
first-class node kind with `crate scenes dive`, and it was not built. The node
kind exists in `graph.NODE_KINDS` and `scene-member` is a declared edge kind, but
nothing writes them and there is no scene command. Two reasons to do it after
Phase 2 rather than inside Phase 1: nothing populates scenes automatically —
Discogs has no scene concept, so they have to be asserted, which makes them the
first *interpretive* edges in a graph that is currently 100% attested — and P16's
recontextualization move is the thing that actually consumes them. Building the
consumer and the data together is the better order.

---

## 3. Phase 2 — Assembly: arc and junctions (P14, P15, P16)

`pipeline/sequence.py` becomes `pipeline/assemble.py`, a real module with its
own objectives rather than a single prompt call.

- **Structural annotation stage** (P15). Spotify's audio endpoints are closed
  (§0), so this is an agent call producing per-track `intro_character`,
  `energy_curve` (a coarse 5-point contour), `key_moment`, `outro_character`.
  Stored in the playlist record and flagged as *asserted, unverified* — it is
  the curator's ear, not measurement, and the liner notes should not pretend
  otherwise.
- **Junction scoring** (P15). A deterministic pass over the agent's proposed
  order: outro character vs next intro character, energy delta, no three
  consecutive same-intensity tracks (already in the prompt as a rule the model
  may quietly ignore — this makes it checkable). Bad junctions are returned to
  the agent for one repair pass, not silently reordered.
- **Recontextualization move** (P16). Exactly one track per playlist must be
  placed deliberately outside its home scene cluster, and the rationale must
  say what the junction buys. Enforced structurally, using the scene entities
  from Phase 1.
- **Non-obvious connection** (P14). The thesis must name one connection the
  listener could not have predicted, and it must be traceable to a graph edge.

---

## 4. Phase 3 — The funnel: intake, queue, frontier (P1, P2, P6, P8, P12)

This is what starts producing the signal everything else learns from.

- `pipeline/intake.py` + `crate intake [--quota N]` — runs against the registry,
  the frontier, and the release substrate; writes nominees to
  `~/.crate/queue.json` with full provenance. Runs whether or not a dig is asked
  for (P1).
- `~/.crate/frontier.yaml` (P6) — rotating tags/scenes/geographies with an
  expiry in cycles. Rotation cadence is a config constant, deliberately not
  learnable: the whole point is that it prevents the taste model from
  overfitting to itself. Note this is a *different* axis from the existing
  source rotation in `source.pick_sources`, which stays.
- `crate queue review` (P12) — the affective gate, and the key change: it sees
  the rejects too. Verdicts on nominees that never reached a playlist are a
  far richer training signal than verdicts on 15 finished tracks. `crate dig`
  then assembles from approved nominees instead of digging cold.
- Acceptance rate as a **health** metric in `crate doctor` (P2). Not an
  optimization target — the spec is explicit that raising it destroys the
  funnel. `doctor` warns in *both* directions: too low means the sources are
  broken, too high means the pool has gone safe and the frontier should rotate.
- launchd agent for the daily intake. `CLAUDE.md` already documents why the env
  vars live in `~/.zshenv` — launchd jobs get no interactive shell — and the
  `cron-to-launchd` skill covers the plist.

---

## 5. Phase 4 — Learning rewire (P5, P7)

Now that queue verdicts exist, the update rules are worth changing.

- **Signed trust, separated from sampling weight** (P7). Keep a non-negative
  *sampling weight* with the existing `SOURCE_WEIGHT_FLOOR = 0.1` so a contrary
  source still gets rotated in, and add a *signed trust* in `[-1, 1]` used in
  scoring. Negative trust flips the sign of that source's endorsement in
  `triangulate.score` — the source stays in the registry as an inverted feature
  instead of being pruned. This is why the two numbers must be separate: the
  exploration floor and the signed weight are answering different questions.
- **Hysteresis** (P5). Replace the symmetric additive delta + decay-toward-0.5
  with: small up-step, full down-step, and damped recovery after a fall
  (`recovering_until`). Trust lost is regained slowly, per Gioia.
- **Probation** for new sources — capped feed share until N verdicts.
- `crate sources weight` CLI bounds change with the signed range; migration
  needed for `sources.yaml` on disk.

---

## 6. Phase 5 — Health and decay

- Drift audit extended to the graph: are traversals revisiting the same
  neighborhoods?
- **Canon decay** — the spec's own open question (Part VI.5): nothing has
  addressed whether entries ever leave the canon. Proposal: canon entries carry
  a last-referenced stamp and are surfaced for retirement, never auto-removed.
  A canon that only grows is a canon that stops meaning anything.

---

## 7. Phase 0 — Do first, small — DONE

1. **Back up `~/.crate`.** `CLAUDE.md` says it exists on exactly one machine and
   nothing backs it up. Phases 1, 3, and 4 all migrate files in it.
2. Record the §0 probe results in `docs/source-access.md`.
3. Fix a stale trap in `CLAUDE.md`: it still says NTS, BBC 6 Music, and
   r/listentothis are dead. Commit `5e7ae8e` revived all three the next day.
4. `crate doctor` migration check for the new `sources.yaml` fields.

---

## 8. What this plan deliberately does not do

- **No SQLite.** The graph could obviously use one. House rule is that all state
  is human-readable files the user may edit by hand, and that rule is load-bearing
  for a tool whose whole premise is that a human stays in the loop. JSONL keeps
  it greppable and hand-editable.
- **No tuning of the guardrails.** Frontier cadence, acceptance band, exploration
  floor, and incentive penalties all go in `config.py` as constants. `config.py`
  already documents why: the learning loop must never be able to optimize away
  the things that keep it from converging.
- **No Discogs token dependency.** Unauthenticated works (§0). A token raises
  the rate limit and can be added later as optional.
- **No claim that P15 is measurement.** It is the agent's ear, labeled as such.

---

## 9. Phase 1 retrospective — read this first

Phases 0 and 1 shipped and ran end to end. Three dry-run digs on 2026-08-22,
the last one published to Spotify (12 of 15 tracks resolved). What follows is
what the live runs taught, because none of it was visible from the tests.

### What the first real dig broke

Every one of these was found by running the thing, not by reading it.

| Failure | Cause | Fixed in |
|---|---|---|
| Dig died at SEQUENCE, losing 91 candidates and the whole traversal | An over-long response was cut off mid-generation; strict JSON parsing discarded everything | `agent.salvage_truncated_json`, and SEQUENCE now degrades to score order |
| Canon anchor `ear — Coil` silently matched Maveth's *Coils Of The Black Earth* | `discogs.search_release` took `results[0]` with no confidence check | `discogs.artist_matches` |
| First version of that fix rejected `Hailu Mergia` vs `Hailu Mergia & The Walias Band` | Whole-string similarity; artist-with-band billing is the *norm* in this corpus | leading-token containment |
| Canon could take every traversal seed | Anchors pushed first into a 6-slot budget | `CANON_SEED_SHARE`, plus anchor rotation by dig count |
| Score spread of 0.038 across a whole playlist | Three of four score terms inert: cross-source 0 for all, stretch 0.50 for 13/15, fit inside 0.75-0.85 | rank-based fit, `also_seen_in`, looser dedupe key |
| Every track dated to its reissue (1970s material stamped 2025) | `year` was ambiguous in the prompt | `year` / `reissue_year` split |
| Two labels supplied 9 of 15 tracks | Rotation guarantees a different source *set*, nothing about its shape | `MIN_SOURCE_TYPES`, `MAX_SOURCE_SHARE` |

Measured before/after on the same registry: score spread 0.038 → 0.154,
distinct fit values 4 → 10, distinct stretch values 2 → 8, cross-source tracks
0 → 1, pre-1990 recordings 2 → 11, empty years 2 → 0.

### What is working

- **Lineage convictions (P13).** The clearest win. One dig placed Hallelujah
  Chicken Run Band and Thomas Mapfumo's Acid Band as an explicit causal pair —
  "the mine-compound band where Mapfumo first put mbira through a guitar amp",
  then "effect, deliberately adjacent". That is the argument the spec asked for.
- **Canon as a judging reference (P3).** A Loraine James track was judged with
  "the same move as the Coil glitch, where the collapse is earned by everything
  stacked before it" — an anchor added an hour earlier, used as the standard.
- **Cross-source, once reachable.** The single corroborated track in the
  published dig (Dur-Dur Band, vouched for by two independent archival labels)
  scored highest by a clear margin.

### Open items for Phase 2 and beyond

1. **The feedback loop is still at zero sessions.** This is now the blocking
   item for the whole plan, not a nice-to-have. Every source trust weight is
   still its seeded value, `stretch_history` is empty, and Phase 4's entire
   purpose is to rewire rules that currently have nothing to consume. The
   2026-08-22 playlist is published and listenable; `crate feedback 2026-08-22`
   is the highest-value next action in this repo.
2. **The credits graph contributed nothing to any dig yet.** It builds correct,
   attested edges — but the canon is indie/art-rock (Big Thief, Blood Orange,
   4AD) while the digs run on global reissue labels, so the leads were for a
   neighbourhood the digs never visited. No liner note has cited a Discogs path.
   Either the canon grows to overlap what gets dug, or seeding becomes
   source-aware (seed the traversal from the *picked sources'* material rather
   than canon-first). Do not build more graph machinery until this is resolved —
   it is currently cost without return.
3. **Cross-source corroboration is thin** (1/15). Possibly structural: sources
   that dig different territory genuinely rarely overlap. Watch it across
   several digs before engineering further.
4. **Fit compression persists at the prompt level** (range still 0.1 after the
   prompt asked for the full range). Rank-based scoring makes this harmless
   today. If it degrades to fewer than `MIN_DISTINCT_FIT_VALUES`, the dig warns.
5. **The best track did not reach Spotify.** The highest-scoring, only
   cross-corroborated track in the published dig was unresolvable
   (`RESOLVE_CONFIDENCE_THRESHOLD` correctly rejected a 0.276 match). Obscure
   global material is exactly what this tool is for and exactly what Spotify
   lacks. Worth deciding whether the unresolved-gems report is a sufficient
   answer or whether the pipeline should over-select to compensate.
6. **Scene entities (P10)** remain deferred — see the note in §2.

### Diagnostics added along the way

- `~/.crate/cache/agent-failures/` — unparseable agent responses are written
  here in full. The exception truncates at 1000 characters, which cannot
  distinguish a cut-off response from a malformed one.
- `crate dig` prints selection health after TRIANGULATE: how many tracks are
  cross-sourced, the fit range, and warnings when fit or stretch is degenerate.
- `crate graph stats`, `crate canon list`, `crate doctor` (registry schema and
  graph size checks).
