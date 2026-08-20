# Source Access Audit

**Audited:** 2026-07-08, from a WSL2/datacenter-egress environment. Every claim marked
**verified** was tested live on that date (WebFetch and/or `curl`); observations note
which client worked, since several sources block datacenter/plain-curl traffic but not
browser-grade clients. Re-verify before building ingestion — unofficial endpoints drift.

> **Re-checked 2026-07-29 from macOS on a residential connection**, via
> `crate doctor` (which exercises only the `api`/`rss` tiers; `web`/`manual`
> sources route through the agent and are not HTTP-fetched here).
>
> The egress change turned out **not** to matter — no source became reachable
> because of it, and none of the three current failures is a block. What did
> happen is drift in the three weeks since the original audit:
>
> | Source | Result | Cause |
> |---|---|---|
> | NTS | `404` on `/api/v2/shows/{show}/episodes` | Unofficial endpoint moved. Not a block — the request arrived and the path is gone |
> | BBC 6 Music | `400` on `rms.api.bbc.co.uk/v2/services/bbc_6music/segments/latest` | Request shape no longer accepted |
> | r/listentothis | `403 Blocked` | Reddit rejects generic user agents regardless of source IP; residential egress did not help. Needs a real `User-Agent`, not a different network |
>
> Fetching cleanly: WFMU, Bandcamp Daily, Aquarium Drunkard, The Quietus,
> Passion of the Weiss. Discogs returns empty rather than erroring.
>
> Takeaway for the next reader: when a source here fails, suspect **endpoint
> drift or client headers before egress**. A 4xx means the request arrived. The
> original note about datacenter blocking is a real phenomenon but was not the
> operative cause of any failure observed on this host.
>
> **All three fixed 2026-07-30** (#2, #3, #4). The diagnoses were each different
> from the first guess, so record what they actually were:
>
> - **NTS** — the API is *unchanged*. `/api/v2/shows/{alias}/episodes/{ep}/tracklist`
>   is still correct (v1 now answers `410 Gone. Please migrate to /api/v2`). Two of
>   the three seeded **show aliases** had retired: `jamz-supernova` and `zakia`
>   404, `floating-points` was fine all along. Because the fetch ran inside a dict
>   comprehension, the first 404 propagated and took the whole source down with
>   it. Now verified live: 187 tracks across `floating-points`, `tash-lc`,
>   `mafalda`. Aliases rot — enumerate current ones at `/api/v2/shows`.
> - **BBC 6 Music** — `segments/latest` now rejects any page limit above 10
>   (`400`, "Page limit must be between 1 and 10"); the code asked for 30. Note
>   `latest` is a small rolling window: it reports `total: 9` and **ignores
>   `offset`**, so there is nothing to paginate.
> - **r/listentothis** — not a User-Agent problem, which was the obvious guess.
>   The public JSON listings 403 for *every* client tried: the crate UA, a
>   desktop Firefox UA, a macOS Chrome UA, and `old.reddit.com`. The **Atom feed
>   for the same listing serves fine** — and wants the descriptive crate UA, since
>   a browser UA is rate-limited to `429` immediately. Titles carry the metadata
>   inline: `Artist - Track [genre] (year)`.

> **Probed 2026-08-20** while planning the curator-DNA rewire
> (`docs/curator-dna-plan.md`). These are the substrates the graph and
> release-awareness layers depend on, so they were tested before being designed
> against.
>
> **Spotify's audio-intelligence endpoints are gone for this app.** With the
> stored token from `~/.crate/auth.json`:
>
> | Endpoint | Result |
> |---|---|
> | `GET /v1/audio-features/{id}` | `403`, bare `{"error":{"status":403}}` |
> | `GET /v1/audio-analysis/{id}` | `403`, same bare body |
> | `GET /v1/recommendations?seed_tracks=…` | `404` |
>
> A bare 403 with no "insufficient scope" message is the removed/restricted
> signature already documented in `CLAUDE.md` for `/playlists/{id}/tracks`.
> There is no per-track energy, key, tempo, or section data available. Anything
> that wants intra-song structure has to assert it, not measure it.
>
> **MusicBrainz recording relationships are effectively empty for this corpus.**
> `GET /ws/2/recording/{mbid}?inc=artist-rels+work-rels+recording-rels` returned
> `[]` for D'Angelo "Devil's Pie", Alice Coltrane "Journey in Satchidananda", and
> Mulatu Astatke "Yekermo Sew"; James Brown "Funky Drummer" returned a single
> `performance` work-rel and no personnel. MusicBrainz is **not** a credits
> source for the music CRATE digs. (Search itself is fine — the recording lookups
> all resolved; the relationship payloads are just unpopulated. Note also that
> `/ws/2/isrc/…` answered `503 currently busy` on the first attempt: MB sheds
> load under pressure, so treat 503 as retry-later, not as dead.)
>
> **Discogs is the credits graph, and it needs no token.** Unauthenticated
> `GET /database/search?type=release` and `GET /releases/{id}` both `200`.
> `extraartists` on an obscure 1972 Hispavox release carried
> `Arranged By [Arreglos]`, `Directed By [Dirección Musical]`, `Guitar` (×2) and
> `Written-by` (×3) — real personnel edges, on exactly the kind of release the
> registry's reissue labels point at. Rate limit is 25 req/min unauthenticated,
> 60 with a free personal token; the existing `fetchers.cached_fetch` layer
> matters here.
>
> **MusicBrainz keeps the release-awareness job.** `GET /ws/2/release?query=
> label:"Analog Africa"` returns clean label catalogs, and NTS tracklists already
> carry per-track ISRC/MBID (§1 below) — a free identity bridge from "a trusted
> DJ played this" into the graph.
>
> Division of labour that follows: **Discogs = credits graph, MusicBrainz =
> identity and release awareness, Spotify = resolution and delivery only.**

Verdict key: `access: api | rss | scrape | manual` (best available tier; a source can
also support lower tiers).

## Contents

1. [NTS Radio](#1-nts-radio)
2. [WFMU](#2-wfmu)
3. [dublab](#3-dublab)
4. [Worldwide FM](#4-worldwide-fm)
5. [The Lot Radio](#5-the-lot-radio)
6. [BBC 6 Music](#6-bbc-6-music)
7. [Bandcamp Daily](#7-bandcamp-daily)
8. [Aquarium Drunkard](#8-aquarium-drunkard)
9. [The Quietus](#9-the-quietus)
10. [Passion of the Weiss (POW MAG)](#10-passion-of-the-weiss-pow-mag)
11. [Rate Your Music](#11-rate-your-music)
12. [Discogs API](#12-discogs-api)
13. [r/listentothis (Reddit)](#13-rlistentothis-reddit)
14. [Bandcamp label pages (reissue labels)](#14-bandcamp-label-pages-reissue-labels)

---

## 1. NTS Radio

**The crown jewel.** Unofficial but clean, unauthenticated JSON API. All endpoints
below **verified 2026-07-08**.

**URL patterns:**

```
https://www.nts.live/api/v2/shows/<show-alias>/episodes?offset=0&limit=12
https://www.nts.live/api/v2/shows/<show-alias>/episodes/<episode-alias>/tracklist
```

**Observed:**
- `GET /shows/the-do-you-breakfast-show/episodes?limit=3` → JSON with `results[]`
  (fields: `name`, `episode_alias`, `show_alias`, `broadcast` ISO-8601, `description`,
  `moods`, `media`, `audio_sources` incl. Mixcloud/SoundCloud URLs, `links[]` including
  the tracklist endpoint URL) and `metadata` (`count: 2005`, `offset`, `limit`) —
  standard offset pagination.
- Tracklist endpoint **verified with rich data**:
  `GET /shows/questing-w-zakia/episodes/questing-w-zakia-15th-september-2024/tracklist`
  → 23 tracks, each with `artist`, `title`, `uid`, `offset`, `duration`, `acr_id`,
  `isrc_id`, `deezer_track_id`, `musicbrainz_track_id`. The ISRC/MusicBrainz IDs make
  Spotify matching nearly free.
- **Caveat:** tracklists are not universal. A 2021 episode of The Do!! You!!! Breakfast
  Show returned `count: 0, results: []`. Expect empty tracklists on older episodes and
  some shows; handle gracefully and fall back to episode `description` text (NTS often
  embeds tracklists there too — unverified, check per show).
- Show aliases are the slug in `nts.live/shows/<alias>` URLs. No auth, no API key, no
  rate-limit headers observed. Be polite (cache, throttle) — it's unofficial.

**access: api** — confidence: high (both endpoints tested live; unofficial, so pin no
guarantees on stability).

## 2. WFMU

Playlist discovery via RSS + per-show HTML scrape. Both **verified 2026-07-08**.

**URL patterns:**

```
https://wfmu.org/playlistfeed.xml          # RSS: every newly published playlist, station-wide
https://wfmu.org/archivefeed/mp3.xml       # RSS: MP3 archive feed (advertised in page <head>; not fetched)
https://www.wfmu.org/playlists             # index of all shows (HTML)
https://www.wfmu.org/playlists/shows/<id>  # individual playlist page (HTML)
```

**Observed:**
- `playlistfeed.xml` → RSS 2.0, fresh (items from Jul 8 2026, e.g. "Bodega Pop with
  Gary Sullivan"), each item linking `wfmu.org/playlists/shows/<numeric id>`.
- Playlist pages are clean, old-school HTML tables with semantic classes:
  `<th class="song col_artist">Artist`, `col_song_title`, `col_album_title` — trivially
  scrapable with any HTML parser.
- **Client note:** WebFetch got 403 on `wfmu.org/playlists`; plain `curl` with a browser
  User-Agent got 200 everywhere. Use a browser UA.
- Per-show archives exist at `wfmu.org/playlists/<show-code>` (e.g. two-letter codes,
  visible from the index page). No JSON API found.

**access: rss** (discovery) + scrape (tracklists) — confidence: high (feed and playlist
table structure both observed live).

## 3. dublab

**Observed/researched:**
- `dublab.com/archive` is a JavaScript-rendered app — no server-side HTML worth
  scraping without a headless browser; no public API documented anywhere indexed.
- Primary usable archive is their Mixcloud (`mixcloud.com/dublab/`); Mixcloud has an
  official API (`api.mixcloud.com/dublab/cloudcasts/`) for show metadata, but Mixcloud
  cloudcasts rarely include full tracklists programmatically.
- Tracklists appear as one-off blog posts (e.g. "Tracklist & Blurb" posts on
  dublab.com) — irregular, not feed-structured.
- `onlineradiobox.com/us/dublab/playlist/` mirrors a rolling 7-day now-playing log —
  third-party, scrape-only, quality unverified.

**access: manual** (or headless scrape via Mixcloud API for metadata) — confidence:
medium (based on search + page behavior; no live tracklist extraction demonstrated).

## 4. Worldwide FM

**Observed/researched:**
- Station is active in 2026 (episodes on `worldwidefm.net` through mid-2026; legacy
  content at `archive.worldwidefm.net`). No API or feed found.
- Tracklist coverage on the site itself is inconsistent.
- Best programmatic path is third-party: `tracklists.thomaslaupstad.com` posts full
  tracklists for Gilles Peterson WWFM episodes (multiple 2026 episodes confirmed in
  search results, e.g. Jan 8 and Jan 29 2026 shows) and is a plain WordPress blog —
  standard `/feed/` RSS very likely (not fetched). 1001tracklists also indexes some
  shows (aggressively anti-bot, see RYM-style caveats).

**access: scrape** (via third-party tracklist blogs; site itself closer to manual) —
confidence: medium (activity and third-party coverage confirmed; no live fetch of
worldwidefm.net performed).

## 5. The Lot Radio

**Observed/researched:**
- Their relaunched website (per DJ Mag coverage) has on-demand playback, resident
  archive pages, and **time-stamped tracklists** — but no documented API; site is
  modern JS (expect headless scraping).
- Archives mirrored on Mixcloud (`mixcloud.com/thelotradio/`) and SoundCloud — Mixcloud
  API usable for episode metadata, not reliable for tracklists.
- Third-party tracklist coverage: 1001tracklists source page, MixesDB category,
  set79.com (claims 115 analyzed sets with timestamps).

**access: scrape** — confidence: medium (tracklist existence confirmed via press +
aggregators; site structure not fetched live).

## 6. BBC 6 Music

**Verified 2026-07-08:** the BBC Sounds backend ("RMS") is an open, unauthenticated
JSON API.

**URL patterns:**

```
https://rms.api.bbc.co.uk/v2/services/bbc_6music/segments/latest        # now/recently playing tracks
https://rms.api.bbc.co.uk/v2/experience/inline/schedules/bbc_6music/<YYYY-MM-DD>  # day schedule
https://rms.api.bbc.co.uk/v2/versions/<version-pid>/segments            # per-episode tracklist (pattern known, NOT verified today)
https://www.bbc.co.uk/programmes/<pid>.json                             # programme metadata JSON
```

**Observed:**
- `segments/latest` → 200, JSON `SegmentItemsResponse`: music segments with
  `titles.primary` (artist), `titles.secondary` (track), `offset.start/end`,
  `now_playing` flag. Live example: Phoebe Bridgers — "Lost Boys".
- Schedule endpoint → 200, `broadcast_summary` items with start/end times and episode
  URNs/pids (e.g. `urn:bbc:radio:episode:m000y61w`) — enumerate a day's episodes, then
  resolve each episode's version pid to pull its segments.
- `bbc.co.uk/programmes/<pid>.json` → 200 JSON (brand metadata, `aggregated_episode_count`,
  service info). Old-style but alive.
- Swagger exists at `rms.api.bbc.co.uk/docs/swagger.json` (referenced in responses).
  Unofficial/undocumented for third parties; geo-blocking possible for some media
  endpoints (metadata worked fine from a US egress).

**access: api** — confidence: high for live/recent segments and schedules (tested);
medium for per-episode historical tracklists (episode→version→segments chain not
exercised end-to-end today).

## 7. Bandcamp Daily

**Verified 2026-07-08.**

```
https://daily.bandcamp.com/feed
```

**Observed:** valid RSS 2.0, TTL 60, items current to the fetch date (Jul 7–8 2026:
"The Best Latin Music on Bandcamp, June 2026", a Smirk album review, a Mal Waldron
feature). Excerpt-only descriptions — fetch the article page for full text and the
embedded album links (article pages are standard server-rendered HTML). Category
archives exist on the site (best-of columns per genre/month) — ideal Move-6 input.

**access: rss** — confidence: high.

## 8. Aquarium Drunkard

**Verified 2026-07-08.**

```
https://aquariumdrunkard.com/feed/
```

**Observed:** working WordPress RSS, hourly updates, items current (Jul 7–9 2026,
incl. Transmissions podcast episodes with enclosures). Excerpts only; article pages are
standard WordPress HTML, easy to fetch for full text/embeds. WordPress conventions mean
`aquariumdrunkard.com/category/<cat>/feed/` per-category feeds almost certainly work
(not tested).

**access: rss** — confidence: high.

## 9. The Quietus

**Verified 2026-07-08.**

```
https://thequietus.com/feed/
```

**Observed:** valid RSS 2.0 (WordPress with podcast namespaces). **Client note:**
WebFetch got 403 (Cloudflare); `curl` with a browser User-Agent got the feed fine. Use
a browser UA and cache. Site is WordPress, so category feeds and article scraping follow
standard conventions.

**access: rss** — confidence: high (feed fetched live; mildly picky about clients).

## 10. Passion of the Weiss (POW MAG)

**Verified 2026-07-08 — note the rebrand/move.**

```
https://www.passionweiss.com/feed/   →  301 → https://powmag.net/
https://www.powmag.net/feed          # working Substack RSS
```

**Observed:** Passion of the Weiss now lives on Substack as **POW MAG** at
`powmag.net`; the old domain 301s there. `powmag.net/feed` returns a valid Substack
RSS 2.0 feed (channel title "POW MAG"). Substack feeds include full or near-full post
content; Substack also exposes unofficial JSON at `/api/v1/posts` on publication
domains (not tested).

**access: rss** — confidence: high (redirect chain and feed both observed live).

## 11. Rate Your Music

**Researched (not fetched — deliberately).**

- **No public API.** RYM's own development page says an API is planned, "register
  interest," no ETA — status unchanged for years.
- Aggressively anti-bot: community scrapers (`dbeley/rymscraper`, Apify actors,
  parse.bot managed endpoints) rely on full browser impersonation and often residential
  proxies, and break routinely. Charts/lists pages are the most protected surfaces.
- Realistic CRATE usage: **manual ingest** — user exports/copies a chart or list page,
  or the agent uses RYM data points already quoted elsewhere. Do not build a pipeline
  on scraping RYM; it will be brittle and violates their ToS.

**access: manual** — confidence: high (consistent across all sources; hostility is
well-documented and long-standing).

## 12. Discogs API

**Verified 2026-07-08.** Official, documented REST API — the backbone for Move 1
(personnel-hopping).

```
https://api.discogs.com/artists/<id>                 # artist: name, realname, profile, groups, namevariations, urls
https://api.discogs.com/artists/<id>/releases        # paginated discography (documented; not fetched today)
https://api.discogs.com/releases/<id>                # release incl. credits
https://api.discogs.com/database/search?q=...        # REQUIRES auth token
```

**Observed:**
- `GET /artists/23755` (Miles Davis) → full JSON **without authentication**.
- `GET /releases/249504` → release JSON incl. `extraartists[]` — the credits array
  that powers personnel-hopping: each entry has `name`, `anv` (name variation), `role`
  (e.g. "Design", "Engineer", "Drums"), `tracks` (scoping), `id`, `resource_url`.
  Also `tracklist[]`, `labels[]`, `genres`, `styles`, `year`, `community.have/want`.
- **Rate limits observed live via headers:** `x-discogs-ratelimit: 25` (unauthenticated,
  per minute, per IP), with `-remaining` / `-used` counters. Documented: 60/min with a
  personal access token — get a token (free, discogs.com/settings/developers) and send
  `Authorization: Discogs token=<token>`.
- A **descriptive User-Agent is required** by ToS (generic UAs get throttled/blocked).
  `/database/search` requires auth; entity endpoints don't. Nonexistent IDs return
  `{"message": "That release does not exist..."}` with a JSON body.

**access: api** (official) — confidence: high.

## 13. r/listentothis (Reddit)

**Tested 2026-07-08 — blocked from this environment.**

```
https://www.reddit.com/r/listentothis/top.json?t=week&limit=25   # public JSON listing (blocked here)
https://oauth.reddit.com/r/listentothis/top?t=week               # official OAuth API (not tested)
```

**Observed:**
- WebFetch refuses reddit.com outright; `curl` with a custom UA got **403 + an HTML
  challenge page** (Reddit blocks datacenter IPs / non-browser clients since the 2023
  API changes). The classic `.json` suffix endpoints still exist and typically work
  from residential IPs with a proper User-Agent, but are not dependable
  infrastructure.
- Reliable path: **official OAuth API** — create a script-type app
  (reddit.com/prefs/apps), authenticate via `praw` or raw OAuth2; free tier is 100
  queries/min, ample for pulling `top`/`hot` listings. Fields per post: `title`
  (r/listentothis enforces "Artist -- Title [genre] (year)" formatting — parse it),
  `url` (the media link), `score`, `created_utc`.

**access: api** (OAuth required in practice) — confidence: high that anonymous
JSON is unreliable from cloud IPs (observed); high that OAuth works (well-documented,
not exercised today).

## 14. Bandcamp label pages (reissue labels)

**Tested 2026-07-08 (Numero Group as the probe).**

```
https://numerogroup.bandcamp.com/music        # label discography page
```

**Observed:**
- Plain `curl` (browser UA) → 200 but a 3 KB **"Client Challenge"** anti-bot
  interstitial (JS challenge; Bandcamp hardened against scrapers). WebFetch's
  browser-grade fetcher **succeeded**: full discography page with album grid (Hüsker
  Dü, Karate, Jejune...) — so the pages are gettable with a client that passes the
  challenge (headless browser / agent-browser skill), just not with raw HTTP.
- When the real page loads, discography data is embedded as JSON in `data-client-items`
  / `data-blob` attributes — parse those rather than the DOM.
- **No RSS** on label pages. **No official API.** Community-documented unofficial
  mobile endpoints exist (`bandcamp.com/api/mobile/24/band_details`, POST with
  `band_id`) — unverified today, historically functional; treat as bonus, not
  foundation.
- Label homes for the Move-2 labels (only Numero verified live; verify others on first
  use): `numerogroup.bandcamp.com` (verified), `lightintheattic.bandcamp.com`,
  `analogafrica.bandcamp.com`, `soundwayrecords.bandcamp.com`,
  `habibifunkrecords.bandcamp.com`, `strut.bandcamp.com` (likely; unverified). Note
  Light in the Attic and Numero also run their own web stores; Bandcamp Daily coverage
  (Section 7) and Discogs label pages (Section 12: label entity endpoints) are
  challenge-free fallbacks for the same catalog data.

**access: scrape** (browser-grade client required) — confidence: medium-high (challenge
behavior and successful browser-grade fetch both observed on Numero; other label
subdomains unverified).

---

## Summary matrix

| Source | Verdict | Verified live today | Notes |
|---|---|---|---|
| NTS Radio | api | yes (episodes + tracklist) | unofficial JSON; ISRC/MBID per track; older eps may be empty |
| WFMU | rss + scrape | yes (feed + playlist page) | browser UA required; clean HTML tables |
| dublab | manual | no | JS site; Mixcloud metadata only |
| Worldwide FM | scrape | no | third-party tracklist blogs are the path |
| The Lot Radio | scrape | no | new site has tracklists; JS-heavy |
| BBC 6 Music | api | yes (segments + schedule) | open RMS JSON API |
| Bandcamp Daily | rss | yes | excerpts; fetch articles for links |
| Aquarium Drunkard | rss | yes | WordPress; hourly |
| The Quietus | rss | yes (curl) | 403s picky clients |
| Passion of the Weiss | rss | yes | moved to Substack: powmag.net/feed |
| Rate Your Music | manual | n/a | no API, scrape-hostile; don't build on it |
| Discogs | api | yes (artist, release, headers) | official; 25/min unauth, 60/min token; UA required |
| r/listentothis | api (OAuth) | 403 observed anon | anonymous .json blocked from cloud IPs |
| Bandcamp labels | scrape | yes (Numero) | anti-bot challenge; browser-grade client works |
