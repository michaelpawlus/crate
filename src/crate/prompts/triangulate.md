# TRIANGULATE stage — judge the pool

The listener:

{{taste}}

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

Return JSON:

```json
{"judgments": [
  {"id": 0, "fit": 0.8, "stretch": 0.4, "conviction": "…"}
]}
```

Include every id from the input exactly once.
