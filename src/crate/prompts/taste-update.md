# Update the taste narrative

You maintain a prose model of this listener — the way a friend with a great
ear holds a model of you ("loves rhythmic complexity; allergic to gloss; a
sucker for a great bassline; one curveball per playlist, not four").

Current taste.md:

---
{{taste}}
---

New feedback session:

```json
{{feedback_json}}
```

Propose an updated taste.md. Rules:

- **Conservative edits.** Change only what this feedback actually supports.
  One session is weak evidence; phrase new observations tentatively
  ("early signal:") and only harden them when they repeat.
- A skip on a high-stretch track is NOT evidence of dislike — it may be
  wrong-day. Only repeated misses in the same direction earn an "allergy".
- Keep the structure (Who this listener is / Loves / Allergies / Stretch
  notes) and keep it under ~60 lines. Prose, not bullet-point soup.
- Never remove something the listener wrote themselves unless feedback
  directly contradicts it.

Return ONLY the full proposed taste.md content, no JSON, no commentary.
