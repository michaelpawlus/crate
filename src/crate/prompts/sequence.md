# SEQUENCE stage — the playlist is an argument

Brief: {{brief}}
Listener sequencing preferences: {{sequencing_prefs}}

Selected tracks (order them ALL; `stretch` marks how challenging each is):

```json
{{tracks_json}}
```

Build the arc:

- **Open accessible.** Track 1 is the handshake — inviting, but with enough
  character to promise the trip is worth taking.
- **Earn the left turn.** Place the most challenging track where the listener
  is warmed up (their preference above says where they tolerate it — default
  around track 4). The track before it must set it up.
- **Vary energy deliberately.** No three consecutive tracks at the same
  intensity; transitions should feel intentional (key/texture/tempo handoffs
  where you can justify them).
- **Land it.** The closer resolves the argument — something that lets the
  listener sit back and feel where they've been.

Write ONE thesis sentence for the whole playlist (it becomes the Spotify
description) and a one-line rationale per position explaining its place in the
arc ("track 4 is the left turn; track 3's outro earns it").

Return JSON:

```json
{"thesis": "…",
 "order": [
   {"id": 3, "rationale": "opener: …"},
   {"id": 0, "rationale": "…"}
 ]}
```

`order` must contain every input id exactly once, in playback order.

Keep each rationale to one sentence. The whole response has to fit in one reply
— if it is cut off mid-way the arc is lost and the playlist falls back to score
order.
