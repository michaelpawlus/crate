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

## Credits-graph leads

People and labels one or two hops out from tonight's material and from the
listener's canon, pulled from **Discogs release credits** — these are attested,
not guessed. `path` is how each was reached.

```json
{{graph_leads_json}}
```

These are leads to dig, not candidates. A name here means "this person's other
work is worth checking tonight", nothing more — you still have to find the music
and say why it belongs. An empty list just means the graph is thin tonight; dig
the sources normally.

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
- A lead from the credits graph does NOT become the source. The registry source
  that started the chain stays the source; put the hop in `why` and name who
  attested it — "via WFMU's play of X → arranger Y (Discogs credit) → this".
  How a record was found is part of what it means, so the path is the record.
- Range matters: spread across eras, regions, and textures. Do not let one
  source or one sound dominate. No single source should account for more than
  about a third of your pool — if one assigned source is doing most of the
  work, you have stopped digging and started transcribing.
- **Look for corroboration.** Before you finish, re-read the other sources'
  material and ask which of your candidates *another* assigned source also
  vouches for. Two independent sources landing on the same record is the
  strongest quality signal in this whole system, and it is invisible unless you
  look for it deliberately — you are working one source at a time, so nothing
  else will find it. Put every corroborating source in `also_seen_in`. Only
  name a source that genuinely vouches for it; an invented second voucher is
  worse than none.
- Include a handful of candidates that stretch beyond the taste profile —
  grounded stretches, not randomness.
- **At least {{recent_target}} candidates must be music made in the last
  {{recent_within_years}} years** — judged on `year`, not `reissue_year`.
  Selection reserves slots for these, and it cannot reserve what you do not
  return: hand back nothing recent and the playlist is archival by default.
  Find them the way you find everything else — a label's new signing, a radio
  host's first play, a publication vouching for a current record — never a
  chart and never recency for its own sake. A new track that does not fit the
  argument is worse than none.
- Real tracks only. If you are not confident a recording exists, leave it out.
- **`year` is when the music was made, not when a label put it out again.** A
  1977 Zimbabwean single on a 2025 Analog Africa compilation is `"year": "1977",
  "reissue_year": "2025"` — never `"year": "2025"`. Most of what the reissue
  labels surface is decades old and the catalogue date is the reissue; getting
  this wrong makes the liner notes lie and tells the drift audit a crate of
  1970s records is a contemporary dig. If you only know the decade, say
  `"1970s"`. If you genuinely do not know, leave `year` empty rather than
  filling it with the reissue date.

Return JSON:

```json
{"candidates": [
  {"track": "…", "artist": "…", "album": "…",
   "year": "1974", "reissue_year": "2016",
   "region": "…", "source": "<assigned source name>",
   "source_type": "radio|reissue-label|publication|list-community|individual",
   "why": "…",
   "also_seen_in": [
     {"source": "<another assigned source>", "why": "how that one vouches for it"}
   ]}
]}
```

`reissue_year` and `also_seen_in` are optional — omit them rather than guessing.
Keep each `why` to one or two sentences; a long pool of long strings is what
makes a response run out of room before it is finished.
