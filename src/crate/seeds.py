"""Seed data written by `crate init`: the initial trusted-source registry and
the taste.md template used before the interview has run."""

SEED_SOURCES: list[dict] = [
    # --- Radio / shows ---
    {
        "name": "NTS",
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
        "type": "radio",
        "access": "rss",
        "endpoint": "https://wfmu.org/playlistfeed.xml",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Station-wide fresh-playlist RSS; playlist pages also scrapeable. Freeform US institution. Best for: outsider, psych, global obscurities.",
    },
    {
        "name": "dublab",
        "type": "radio",
        "access": "manual",
        "endpoint": "https://www.dublab.com",
        "trust": 0.8,
        "feedback_count": 0,
        "notes": "LA future-roots radio. Tracklists inconsistent; use manual ingest or agent web research.",
    },
    {
        "name": "Worldwide FM",
        "type": "radio",
        "access": "manual",
        "endpoint": "https://worldwidefm.net",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Gilles Peterson's station. Best for: jazz-adjacent, Brazilian, broken beat, global soul.",
    },
    {
        "name": "The Lot Radio",
        "type": "radio",
        "access": "manual",
        "endpoint": "https://www.thelotradio.com",
        "trust": 0.75,
        "feedback_count": 0,
        "notes": "NYC streaming radio. Best for: current DJ-scene energy, house/leftfield.",
    },
    {
        "name": "BBC 6 Music",
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
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://numerogroup.bandcamp.com",
        "trust": 0.95,
        "feedback_count": 0,
        "notes": "The gold standard of archival excavation. Best for: private-press soul, gospel funk, folk-funk, eccentric soul.",
    },
    {
        "name": "Light in the Attic",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://lightintheattic.net",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: Japanese ambient/city pop, US folk outsiders, country-soul.",
    },
    {
        "name": "Analog Africa",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://analogafrica.bandcamp.com",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: West African funk, Somali tapes, Caribbean synth.",
    },
    {
        "name": "Soundway",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://soundwayrecords.bandcamp.com",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: Ghanaian highlife, Colombian champeta, SE Asian pop.",
    },
    {
        "name": "Habibi Funk",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://habibifunkrecords.bandcamp.com",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: Arab-world funk, jazz, and disco from the 70s-80s.",
    },
    {
        "name": "Strut",
        "type": "reissue-label",
        "access": "web",
        "endpoint": "https://strut.bandcamp.com",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Best for: Afro-funk, disco edits, spiritual jazz reissues (with !K7).",
    },
    {
        "name": "Mississippi Records",
        "type": "reissue-label",
        "access": "manual",
        "endpoint": "https://mississippirecords.net",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: pre-war blues/gospel, global folk, lo-fi ethnographic beauty.",
    },
    {
        "name": "Awesome Tapes From Africa",
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
        "type": "publication",
        "access": "rss",
        "endpoint": "https://daily.bandcamp.com/feed",
        "trust": 0.8,
        "feedback_count": 0,
        "notes": "Best for: new artists via trusted-filter writing; scene primers and label profiles.",
    },
    {
        "name": "Aquarium Drunkard",
        "type": "publication",
        "access": "rss",
        "endpoint": "https://aquariumdrunkard.com/feed/",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Best for: psych, cosmic country, reissue coverage, transmissions mixes.",
    },
    {
        "name": "The Quietus",
        "type": "publication",
        "access": "rss",
        "endpoint": "https://thequietus.com/feed",
        "trust": 0.8,
        "feedback_count": 0,
        "notes": "Best for: leftfield/experimental, UK underground, Baker's Dozen artist lists.",
    },
    {
        "name": "Passion of the Weiss",
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
        "type": "list-community",
        "access": "manual",
        "endpoint": "https://rateyourmusic.com",
        "trust": 0.7,
        "feedback_count": 0,
        "notes": "Charts and user lists. Scrape-hostile; use manual ingest or agent web research. Best for: canon-checking a scene.",
    },
    {
        "name": "Discogs",
        "type": "list-community",
        "access": "api",
        "endpoint": "https://api.discogs.com",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Credits graph for personnel-hopping; want-list counts as durability signal. Token via DISCOGS_TOKEN env var.",
    },
    {
        "name": "r/listentothis",
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
        "type": "individual",
        "access": "web",
        "endpoint": "https://worldwidefm.net",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: jazz lineage, Brazil, broken beat; his festival/comp selections are pre-vetted.",
    },
    {
        "name": "Floating Points",
        "type": "individual",
        "access": "web",
        "endpoint": "https://www.nts.live/shows/floating-points",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "As digger: deep soul/jazz/ambient 45s. NTS show archives have tracklists.",
    },
    {
        "name": "Madlib / Egon (Now-Again)",
        "type": "individual",
        "access": "web",
        "endpoint": "https://nowagainrecords.bandcamp.com",
        "trust": 0.9,
        "feedback_count": 0,
        "notes": "Best for: global psych-funk, library records, beat-digger canon.",
    },
    {
        "name": "Zach Cowie",
        "type": "individual",
        "access": "manual",
        "endpoint": "",
        "trust": 0.85,
        "feedback_count": 0,
        "notes": "Turquoise Wisdom. Best for: gentle-but-deep selections, ambient/folk/jazz crossovers.",
    },
    {
        "name": "Jamz Supernova",
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
