# Parse quick feedback

The listener left free-text feedback on playlist {{playlist_stamp}}:

---
{{feedback_text}}
---

The playlist was:

```json
{{tracks_json}}
```

Convert the feedback into structured records. Rules:

- Track references may be by position number ("loved 3 and 7"), artist, or
  title — resolve them against the tracklist above.
- Verdicts: `love`, `like`, `fine`, `skip`, `hate`. Map natural language
  sensibly ("amazing" → love, "didn't do it for me" → skip, "never again" →
  hate). Tracks not mentioned get NO record — do not invent verdicts.
- Whole-playlist observations ("too mellow overall", "the ending dragged")
  become records with `"track_pos": null` and the observation in `note`.
- Useful tags when clearly implied: `good-surprise`, `failed-surprise`,
  `too-safe`, `sequencing`, `mood-mismatch`.

Return JSON:

```json
{"records": [
  {"track_pos": 3, "verdict": "love", "note": "…", "tags": ["good-surprise"]},
  {"track_pos": null, "verdict": null, "note": "too mellow overall", "tags": ["mood-mismatch"]}
]}
```
