# Curator DNA: A Behavioral Taxonomy of Elite Music Curators

**Purpose:** Reverse-engineer the discovery and curation behavior of world-class human music curators into an implementable pattern language for CRATE.

**Subjects (Phase 1 evidence base):** Ted Gioia (critic/historian), Questlove (DJ/curator/historian), Gilles Peterson (broadcaster/label owner), John Peel (broadcaster, secondary evidence).

**Method:** Patterns admitted only if attested by at least one primary source (subject describing their own process) and ideally corroborated across two or more subjects. Each pattern includes its evidence and a CRATE implementation note.

---

## Part I — Intake Patterns (how they consume)

### P1. Fixed intake ritual with a volume quota
- **Evidence:** Gioia: 2–3 hrs/day of new music, 1,000+ new releases/year. Questlove: Sunday sessions of 3–5 hrs dedicated to new music. Peterson: frames constant consumption as professional necessity (sommelier/chef analogy — you never stop tasting).
- **Principle:** Discovery is a scheduled discipline, not an on-demand activity. Volume is the input; taste is the filter, never the throttle.
- **CRATE:** A scheduled intake job (daily/weekly) with an explicit quota of candidate tracks/albums pulled from the source registry. The job runs whether or not the user asks.

### P2. High-volume, low-conversion funnel with accepted waste
- **Evidence:** Gioia: finding 1–2 good new albums is "a significant achievement"; assembling 100/year consumes more time than writing books; Bandcamp digging wastes "a huge amount" of time due to zero quality control — and it's still his #2 source.
- **Principle:** ~90–95% rejection is the normal, healthy state. Waste is the cost of reaching music no editorial channel surfaces. Optimizing for conversion rate destroys the funnel's value.
- **CRATE:** Track acceptance rate as a *health* metric, not an optimization target. If acceptance climbs too high, the intake pool has become too safe — trigger frontier rotation (P6).

### P3. Repetition builds the internal model
- **Evidence:** Questlove attributes encyclopedic recall to hearing the same songs 9–15x/week for years on radio. Gioia teaches internalizing a Charlie Parker solo by singing along until phrasing/cadence is absorbed without knowing the theory.
- **Principle:** The curator's "embedding space" is built by deep repeated exposure to canonical material, not broad shallow exposure alone. The reference library is as important as the discovery feed.
- **CRATE:** Maintain a canon/reference corpus per genre or lineage that the taste model is anchored against. New candidates are evaluated relative to internalized references, not in a vacuum.

---

## Part II — Source Patterns (where signal comes from)

### P4. Incentive filter as the master heuristic
- **Evidence:** Gioia's entire best-to-worst ranking reduces to one question: is this source paid to promote? Top: unpaid trusted friends, obscure regional bloggers, quirky fan playlists (never official/promoted ones). Bottom: publicists, label PR, mimetic newspaper reviews. Musicians count only when praise is *disinterested* — never their own record or a friend's. He treats his own distance from labels/publicists as a feature protecting his independence.
- **Principle:** Source value is inversely correlated with promotional incentive. Passion without payroll is the strongest signal class that exists.
- **CRATE:** Every source in the registry carries an incentive score. Promotional provenance (press release, label PR, sponsored placement, official editorial playlist) applies a heavy prior penalty regardless of content.

### P5. Weighted trust registry with asymmetric (hysteretic) updates
- **Evidence:** Gioia: a "small crew" of trusted personal recommenders whose emails he always reads; 30–40 blogs/Substacks in routine rotation, kept only if hit rate stays high; a *very* short list of trusted labels; trust lost is regained slowly ("just beginning to trust [a storied jazz label] again, but I still want more evidence"). Peterson: trusted reissue labels as doors into scenes; global network of shop owners and local experts. Gioia's general advice: find a guide you trust and let them open your ears.
- **Principle:** The core discovery engine is a small, weighted graph of trusted intermediaries — people, labels, shows, blogs — where weight is earned by demonstrated hit rate and decays asymmetrically: slow to rise, fast to fall, very slow to recover.
- **CRATE:** Source registry with per-source trust weight updated from user feedback on that source's candidates. Update rule is hysteretic, not a symmetric rolling average. New sources start on probation with limited feed share.

### P6. Rotating exploration frontier (anti-rut engineering)
- **Evidence:** Gioia: 73 Bandcamp bookmarks across wildly diverse tags (microtonal, Ethiopia, shamanic, Appalachian, just intonation, Bulgaria, folktronica) that "constantly change"; explicitly never keeps the same routine — Mongolia one day, Croatian folk singers the next; goal is to "encounter music that is fresh and different."
- **Principle:** The exploration arm is not ε-greedy over a fixed pool. The candidate *pool itself* rotates on a schedule, deliberately preventing the curator (or system) from overfitting to its own taste model.
- **CRATE:** Maintain a frontier list of tags/scenes/geographies. Each intake cycle samples a rotating subset; frontier entries expire and are replaced. Rotation cadence is a first-class config value.

### P7. Contrary indicators as an inverted signal class
- **Evidence:** Gioia: some blogs are useful specifically because their endorsements reliably predict music "few people — or perhaps nobody — will actually enjoy."
- **Principle:** A source with consistent negative correlation is not noise; it is signal with a flipped sign.
- **CRATE:** Trust weights are signed. Sources can go negative and remain in the registry as inverted features rather than being pruned.

### P8. Release-awareness layer decoupled from taste
- **Evidence:** Gioia values AllMusic (genre-sortable new-release database, visited ~2x/week) and even piracy trackers purely for *coverage* — "what exists this week," especially European releases invisible to US media — while ignoring their opinions entirely.
- **Principle:** Knowing what came out is a separate problem from knowing what's good. Comprehensive release awareness requires dedicated infrastructure; editorial outlets systematically under-cover.
- **CRATE:** A release-ingest substrate (MusicBrainz, Bandcamp new-release feeds by tag, Discogs) that feeds the funnel and is fully decoupled from the scoring layer.

### P9. Graph traversal over search
- **Evidence:** Crate-digger lineage (Premier, Madlib, Dilla school): check song credits, then dig everything a producer touched; read artist interviews for what *they* listen to. Questlove's deep attention to personnel (knowing the writer, drummer, mixer on everything); his reverence for connectors like Alan Leeds who thread through James Brown → P-Funk → Prince → D'Angelo. Peterson: deep dives into record personnel as a defining trait of his radio approach.
- **Principle:** The metadata graph — credits, producers, session players, labels, samples, remixes — IS the discovery engine. Curators follow edges, not queries.
- **CRATE:** Model music as a graph (artist–producer–label–sample–scene edges). Discovery jobs traverse edges from high-affinity nodes. Every accepted track expands the traversal frontier.

### P10. Scene-anchored digging
- **Evidence:** Peterson digs locally wherever he works (Recife shopping while in Brazil; Sicilian music for Sicilian curation); credits reissue labels (Soundway, Analogue Africa) with opening doors to local scenes; describes finding expert hosts "anywhere in the world." Gioia keeps ~a dozen country/region-focused blogs (Sounds and Colours, World Music Central, African Music Forum) in rotation.
- **Principle:** Scenes — geographic and temporal — are natural units of discovery. Anchoring queries to a scene surfaces coherent clusters that similarity search misses.
- **CRATE:** Scene entities (city/region/era/label-cluster) as first-class objects. Periodic scene-dive jobs that exhaust a scene's graph neighborhood rather than sampling globally.

---

## Part III — Judgment Patterns (how they decide)

### P11. Context stored with the music
- **Evidence:** Peterson: "It's all about context, the when and where of how you hear something" — hearing Salif Keita as mainstream on French radio (not ghettoized) permanently shaped his curation; epiphany records are remembered with full situational detail (Mulatu Astatke in Soul Jazz Records, Soho).
- **Principle:** Provenance and encounter-context are part of the data, not metadata exhaust. How/where a track was found affects how it is understood and later deployed.
- **CRATE:** Store discovery provenance (source, scene, date, traversal path) with every track. Surface it at playlist-assembly time; use it in explanations.

### P12. The affective gate is final and human
- **Evidence:** Peterson: "I look for music that touches me... I'm not going to play any records I don't like." Gioia's trusted crew is defined by "big ears, warm hearts" — passion, not credentials. Gioia unlearned over-analytic listening in favor of felt response ("more like the dancer at the disco" than the musicologist).
- **Principle:** Every analytical layer proposes; a felt human response disposes. The final filter is never delegated.
- **CRATE:** The system never auto-adds to the library. It nominates; Michael's feedback loop (already in CRATE) is the terminal gate, and that feedback is the primary training signal for trust weights (P5) and the taste model.

### P13. Historian's causal model, not similarity model
- **Evidence:** Questlove's books are organized as influence-and-history arguments (one essential track per year; hip-hop as lineage). Peterson traces his own taste through named mentors and epiphany records; connects Northern Soul to the deep-digging ethos. Reynolds/Gioia write genre history as causal narrative. Madlib/Shadow school treated as "music historians" and "librarians of musical culture."
- **Principle:** Elite curators hold a causal/influence model (who begat whom, what scene produced what sound) layered on top of any similarity intuition. This is what lets them make non-obvious connections that feel inevitable.
- **CRATE:** Encode influence edges (mentor, sample-of, scene-descendant, cover-of) distinct from acoustic similarity. Playlist logic and explanations should be able to cite lineage, not just vibe-adjacency.

---

## Part IV — Assembly Patterns (how playlists get made)

### P14. Curation as storytelling
- **Evidence:** Crate-digger tradition: the true art is "building a pattern that tells a story no one else has told." Questlove's MasterClass frames curation as constructing a musical experience for an audience.
- **Principle:** A playlist is a narrative artifact with an arc, not a ranked list of good tracks. Sequencing is a distinct craft from selection.
- **CRATE:** Playlist assembly is a separate module from discovery/scoring, with its own objectives: arc shape, tension/release, thematic through-line, at least one non-obvious connection per playlist.

### P15. Intra-song awareness (moments, not just tracks)
- **Evidence:** Questlove: knowing songs is "like dating" — noticing where they slow down, change key, drop out; dedicated MasterClass lessons on finding "remarkable moments" inside songs and on transitions.
- **Principle:** Assembly operates at the sub-track level — energy contours, entrances, breakdowns, endings — because transitions are built from moments.
- **CRATE:** Store per-track structural annotations (energy curve, key moments, intro/outro character). Sequencer optimizes junctions, not just adjacency of track-level features.

### P16. Contextual re-framing (de-ghettoization)
- **Evidence:** Peterson's refusal to ghettoize — playing African music "in the mix with other stuff," mainstream-adjacent, as he heard it on French radio; his club nights where disparate scenes shared a floor and seemingly incompatible tracks became anthems together.
- **Principle:** Placement changes meaning. A track's power often comes from the unexpected company it keeps.
- **CRATE:** Sequencer should have an explicit "recontextualization" move: deliberately placing a track outside its home-scene cluster when the junction supports it.

---

## Part V — Composite Architecture Sketch

```
[Release-awareness substrate]  (P8: MusicBrainz / Bandcamp tags / Discogs)
            |
[Source registry w/ signed, hysteretic trust weights]  (P4, P5, P7)
            |
[Intake scheduler w/ quota + rotating frontier]  (P1, P2, P6)
            |
[Graph traversal + scene dives]  (P9, P10)
            |
[Taste model anchored on canon corpus]  (P3, P13)
            |
[Nomination queue → HUMAN AFFECTIVE GATE]  (P12)
            |
[Library w/ provenance + structural annotations]  (P11, P15)
            |
[Playlist assembler: narrative arc + junction optimization + recontextualization]  (P14, P15, P16)
            |
[Feedback loop → updates trust weights + taste model]  (P5, P12)
```

## Part VI — Open Questions / Next Evidence

1. **Questlove MasterClass (lessons 3, 7, 8):** how he absorbs music; playlist construction method; finding remarkable moments. Expected to enrich P3, P14, P15.
2. **QLS episode w/ Gilles Peterson:** two subjects on method simultaneously; expected corroboration for P5, P9, P10, P13.
3. **Peel (*Margrave of the Marshes*) and *Mo' Meta Blues*:** the "listen to everything, no genre filter" discipline (P2 extreme case) and formative-repetition detail (P3).
4. **Gioia annual 100-best lists:** labeled ground truth of his funnel's output; useful for validating any model of his taste.
5. **Unresolved:** how curators handle *decay* — do tracks/artists ever exit the canon? No subject has addressed forgetting yet.
