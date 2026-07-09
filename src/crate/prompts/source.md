# SOURCE stage — dig a candidate pool

Tonight's dig uses these trusted sources (your assigned crate for this run):

```json
{{sources_json}}
```

Fetched material from those sources (tracklists, feed items, manual ingests;
`null`/empty means fetching failed — research that source yourself if you have
web access):

```json
{{material_json}}
```

## The listener

Taste profile:

{{taste}}

Brief for this run: {{brief}}
Mood prior for today: {{mood_prior}}
Target playlist length: {{length}} tracks. Stretch budget: {{stretch_budget}} (0–1).

Do NOT include these (already used or banned):

```json
{{exclusions_json}}
```

## Your job

Produce a candidate pool of {{pool_min}}–{{pool_max}} tracks. Work the digger
moves against the assigned sources:

- Pull the strongest tracks from the fetched tracklists and feed items.
- Chain: if a tracklist names an artist worth one personnel-hop or one
  label-hop, follow it — but the provenance stays with the source that
  started the chain (note the hop in `why`).
- For label sources, draw on what that label has released or reissued,
  especially recent and this-quarter output.
- For publication feeds, extract the artists/records the writing vouches for.
- If you have web search, use it to fill gaps: recent tracklists for the
  radio shows, recent releases for the labels. Cache-friendly, focused
  queries.
- Weak-signal sources (e.g. r/listentothis) may only *corroborate* a track
  that another source surfaced — never stand alone.

Rules:

- Every candidate MUST carry provenance: the `source` field must be one of
  the assigned source names, and `why` must say concretely how that source
  vouches for it (which episode, which reissue, which article, which credit
  chain).
- Range matters: spread across eras, regions, and textures. Do not let one
  source or one sound dominate.
- Include a handful of candidates that stretch beyond the taste profile —
  grounded stretches, not randomness.
- Real tracks only. If you are not confident a recording exists, leave it out.

Return JSON:

```json
{"candidates": [
  {"track": "…", "artist": "…", "album": "…", "year": "1974",
   "region": "…", "source": "<assigned source name>",
   "source_type": "radio|reissue-label|publication|list-community|individual",
   "why": "…"}
]}
```
