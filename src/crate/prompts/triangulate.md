# TRIANGULATE stage — judge the pool

The listener:

{{taste}}

## The canon this ear is calibrated on

Judge each candidate *relative to these references*, not in a vacuum. This is
what the listener has internalised — the standard a new record has to meet, and
the lineage it either extends, argues with, or ignores.

{{canon}}

Brief: {{brief}}
Stretch budget: {{stretch_budget}} (0 = only comfort zone, 1 = maximum range).

Candidate pool (deduplicated; `sources` lists every independent source that
surfaced the track — multiple sources is the strongest quality signal):

```json
{{candidates_json}}
```

For EVERY candidate, judge:

- `fit` (0–1): how well it serves this brief and mood — energy, texture,
  moment. Not similarity to past taste; a stretch track can have high fit.
- `stretch` (0–1): distance from the listener's current taste centroid.
  0 = squarely inside their world, 1 = a different planet.
- `conviction`: ONE sentence on why this track belongs — the sentence you'd
  say handing them the record. If you cannot write a real one, return an
  empty string and the track is cut. No filler ("great track", "a classic").
  Name the thing: the bassline, the arrangement choice, the scene it opens.

  Where you can, make it a **lineage** claim rather than a resemblance claim.
  "Sounds like X" is the similarity engine this tool exists to replace; "the
  same arranger who did X, three years before he found the sound you know him
  for" is an argument. Who begat whom, which scene produced it, which credit
  connects it — cite the causal link, not the vibe-adjacency. If you genuinely
  don't know the lineage, describe what the record *does* instead. Never invent
  a credit, a scene, or an influence to make a better sentence.

Return JSON:

```json
{"judgments": [
  {"id": 0, "fit": 0.8, "stretch": 0.4, "conviction": "…"}
]}
```

Include every id from the input exactly once.
