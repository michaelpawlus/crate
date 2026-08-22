"""Seed data written by `crate init`: the initial trusted-source registry and
the taste.md template used before the interview has run.

`incentive` (P4) is the master heuristic from the curator-DNA spec: source value
is inversely correlated with promotional incentive. It scores *structural
self-interest*, not quality — a label with impeccable taste still profits from
the record it is recommending. `config.INCENTIVE_PENALTY` turns it into a
multiplier on how much that source's vouching counts in TRIANGULATE. The
per-source reasoning is inline below; disagree with any of it by editing
`~/.crate/sources.yaml`, which is authoritative."""

SEED_SOURCES: list[dict] = [
    # --- Radio / shows ---
    {
        "name": "NTS",
        "incentive": "none",
        "type": "radio",
        "access": "api",
        "endpoint": "https://www.nts.live/api/v2",
        # Verified live 2026-07-30. Show aliases retire without notice — when one
        # 404s the fetcher skips it and `crate doctor` names it, so replace it
        # here from https://www.nts.live/api/v2/shows. Known-good alternates:
        # nkisi, moxie, ok-williams, flo, chuquimamani-condori, in-focus.
        "shows": ["floating-points", "tash-lc", "mafalda"],
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Show archives with structured tracklists via unofficial JSON API. Best for: everything; deep global range.",
    },
    {
        "name": "WFMU",
        "incentive": "none",
        "type": "radio",
        "access": "rss",
        "endpoint": "https://wfmu.org/playlistfeed.xml",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Station-wide fresh-playlist RSS; playlist pages also scrapeable. Freeform US institution. Best for: outsider, psych, global obscurities.",
    },
    {
        "name": "dublab",
        "incentive": "none",
        "type": "radio",
        "access": "manual",
        "endpoint": "https://www.dublab.com",
        "trust": 0.8,
        "feedback_count": 0,
        "notes": "LA future-roots radio. Tracklists inconsistent; use manual ingest or agent web research.",
    },
    {
        "name": "Worldwide FM",
        "incentive": "low",
        "type": "radio",
        "access": "manual",
        "endpoint": "https://worldwidefm.net",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Gilles Peterson's station. Best for: jazz-adjacent, Brazilian, broken beat, global soul.",
    },
    {
        "name": "The Lot Radio",
        "incentive": "none",
        "type": "radio",
        "access": "manual",
        "endpoint": "https://www.thelotradio.com",
        "trust": 0.75,
        "feedback_count": 0,
        "notes": "NYC streaming radio. Best for: current DJ-scene energy, house/leftfield.",
    },
    {
        "name": "BBC 6 Music",
        "incentive": "medium",
        "type": "radio",
        "access": "api",
        "endpoint": "https://rms.api.bbc.co.uk/v2/services/bbc_6music/segments/latest",
        "trust": 0.75,
        "feedback_count": 0,
        "notes": "Open BBC Sounds RMS API: live artist/track segments. Best shows: Gideon Coe, Freak Zone.",
    },
    # --- Reissue labels (meta-diggers) ---
    {
        "name": "Numero Group",
        "incentive": "low",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://numerogroup.bandcamp.com",
        "trust": 0.95,
        "feedback_count": 0,
        "notes": "The gold standard of archival excavation. Best for: private-press soul, gospel funk, folk-funk, eccentric soul.",
    },
    {
        "name": "Light in the Attic",
        "incentive": "low",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://lightintheattic.net",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: Japanese ambient/city pop, US folk outsiders, country-soul.",
    },
    {
        "name": "Analog Africa",
        "incentive": "low",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://analogafrica.bandcamp.com",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: West African funk, Somali tapes, Caribbean synth.",
    },
    {
        "name": "Soundway",
        "incentive": "low",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://soundwayrecords.bandcamp.com",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: Ghanaian highlife, Colombian champeta, SE Asian pop.",
    },
    {
        "name": "Habibi Funk",
        "incentive": "low",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://habibifunkrecords.bandcamp.com",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: Arab-world funk, jazz, and disco from the 70s-80s.",
    },
    {
        "name": "Strut",
        "incentive": "low",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://strut.bandcamp.com",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Best for: Afro-funk, disco edits, spiritual jazz reissues (with !K7).",
    },
    {
        "name": "Mississippi Records",
        "incentive": "low",
        "type": "reissue-label",
        "access": "manual",
        "endpoint": "https://mississippirecords.net",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: pre-war blues/gospel, global folk, lo-fi ethnographic beauty.",
    },
    {
        "name": "Awesome Tapes From Africa",
        "incentive": "low",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://awesometapesfromafrica.bandcamp.com",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Best for: cassette-era African pop, Malian balani, Ethiopian keyboard music.",
    },
    # --- Publications / blogs ---
    {
        "name": "Bandcamp Daily",
        "incentive": "medium",
        "type": "publication",
        "access": "rss",
        "endpoint": "https://daily.bandcamp.com/feed",
        "trust": 0.8,
        "feedback_count": 0,
        "notes": "Best for: new artists via trusted-filter writing; scene primers and label profiles.",
    },
    {
        "name": "Aquarium Drunkard",
        "incentive": "low",
        "type": "publication",
        "access": "rss",
        "endpoint": "https://aquariumdrunkard.com/feed/",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Best for: psych, cosmic country, reissue coverage, transmissions mixes.",
    },
    {
        "name": "The Quietus",
        "incentive": "low",
        "type": "publication",
        "access": "rss",
        "endpoint": "https://thequietus.com/feed",
        "trust": 0.8,
        "feedback_count": 0,
        "notes": "Best for: leftfield/experimental, UK underground, Baker's Dozen artist lists.",
    },
    {
        "name": "Passion of the Weiss",
        "incentive": "low",
        "type": "publication",
        "access": "rss",
        "endpoint": "https://powmag.net/feed",
        "trust": 0.8,
        "feedback_count": 0,
        "notes": "Best for: rap deep coverage, LA beat scene, year-end lists that dig.",
    },
    # --- Communities / lists ---
    {
        "name": "Rate Your Music",
        "incentive": "none",
        "type": "list-community",
        "access": "manual",
        "endpoint": "https://rateyourmusic.com",
        "trust": 0.7,
        "feedback_count": 0,
        "notes": "Charts and user lists. Scrape-hostile; use manual ingest or agent web research. Best for: canon-checking a scene.",
    },
    {
        "name": "Discogs",
        "incentive": "none",
        "type": "list-community",
        "access": "api",
        "endpoint": "https://api.discogs.com",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Credits graph for personnel-hopping; want-list counts as durability signal. Token via DISCOGS_TOKEN env var.",
    },
    {
        "name": "r/listentothis",
        "incentive": "none",
        "type": "list-community",
        "access": "api",
        "endpoint": "https://www.reddit.com/r/listentothis/top.rss?t=month",
        "trust": 0.4,
        "feedback_count": 0,
        "notes": "Weak signal — use for triangulation only, never as sole provenance.",
    },
    # --- Individuals (via their shows, mixes, published lists) ---
    {
        "name": "Gilles Peterson",
        "incentive": "low",
        "type": "individual",
        "access": "web",
        "endpoint": "https://worldwidefm.net",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: jazz lineage, Brazil, broken beat; his festival/comp selections are pre-vetted.",
    },
    {
        "name": "Floating Points",
        "incentive": "none",
        "type": "individual",
        "access": "web",
        "endpoint": "https://www.nts.live/shows/floating-points",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "As digger: deep soul/jazz/ambient 45s. NTS show archives have tracklists.",
    },
    {
        "name": "Madlib / Egon (Now-Again)",
        "incentive": "low",
        "type": "individual",
        "access": "web",
        "endpoint": "https://nowagainrecords.bandcamp.com",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: global psych-funk, library records, beat-digger canon.",
    },
    {
        "name": "Zach Cowie",
        "incentive": "none",
        "type": "individual",
        "access": "manual",
        "endpoint": "",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Turquoise Wisdom. Best for: gentle-but-deep selections, ambient/folk/jazz crossovers.",
    },
    {
        "name": "Jamz Supernova",
        "incentive": "none",
        "type": "individual",
        "access": "web",
        "endpoint": "https://www.nts.live/shows/jamz-supernova",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Best for: forward-looking club-soul, UK/SA/global bass connections.",
    },
]

TASTE_TEMPLATE = """# Taste Profile

_This file is the primary model of the listener. Prose first, numbers second.
Edit it by hand any time — manual edits are authoritative._

## Who this listener is

(Not yet interviewed. Run `crate init` to do the taste interview, or write
freely here: artists and records you love, what you can't stand, what a
perfect surprise feels like.)

## Loves

-

## Allergies

-

## Stretch notes

How far and in which directions this listener likes to be pushed. The agent
updates this after feedback sessions; you can veto any change.

-
"""
