"""Spotify Web API client: OAuth PKCE (no client secret) plus the narrow,
deterministic surface the pipeline is allowed to touch. The agent never calls
this module — RESOLVE and PUBLISH are plain code (§3.4)."""

import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from difflib import SequenceMatcher
from typing import Any

import httpx

from . import config

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"

# Version pollution: if these appear in the found album/artist but not in the
# query, the match is almost certainly the wrong version.
POLLUTION_TERMS = ("karaoke", "tribute", "made famous", "originally performed",
                   "in the style of", "8-bit", "lullaby", "kidz")


class SpotifyError(RuntimeError):
    pass


class NotAuthenticated(SpotifyError):
    pass


def client_id() -> str:
    import os

    cid = os.environ.get("CRATE_SPOTIFY_CLIENT_ID", "")
    if not cid:
        auth = _load_auth()
        cid = auth.get("client_id", "")
    if not cid:
        raise NotAuthenticated(
            "No Spotify client ID. Create an app at "
            "https://developer.spotify.com/dashboard, add redirect URI "
            f"{config.SPOTIFY_REDIRECT_URI}, then run `crate init`."
        )
    return cid


def _load_auth() -> dict[str, Any]:
    path = config.auth_path()
    return json.loads(path.read_text()) if path.exists() else {}


def _save_auth(data: dict[str, Any]) -> None:
    config.auth_path().parent.mkdir(parents=True, exist_ok=True)
    config.auth_path().write_text(json.dumps(data, indent=2))
    config.auth_path().chmod(0o600)


# --- PKCE flow ---

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None

    def do_GET(self):  # noqa: N802
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _CallbackHandler.code = query.get("code", [None])[0]
        _CallbackHandler.error = query.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        msg = "Authorized — you can close this tab and return to the terminal." \
            if _CallbackHandler.code else f"Authorization failed: {_CallbackHandler.error}"
        self.wfile.write(f"<html><body><h2>CRATE</h2><p>{msg}</p></body></html>".encode())

    def log_message(self, *args):  # silence request logging
        pass


def authorize(explicit_client_id: str | None = None) -> None:
    """Run the PKCE flow: open browser, catch the callback, store tokens."""
    cid = explicit_client_id or client_id()
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    params = {
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": config.SPOTIFY_REDIRECT_URI,
        "scope": config.SPOTIFY_SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "state": secrets.token_urlsafe(16),
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    _CallbackHandler.code = None
    _CallbackHandler.error = None
    server = http.server.HTTPServer(("127.0.0.1", config.SPOTIFY_REDIRECT_PORT), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("Opening browser for Spotify authorization…")
    print(f"If it doesn't open, visit:\n{url}\n")
    webbrowser.open(url)
    thread.join(timeout=300)
    server.server_close()

    if not _CallbackHandler.code:
        raise SpotifyError(f"Authorization did not complete: {_CallbackHandler.error or 'timeout'}")

    resp = httpx.post(
        TOKEN_URL,
        data={
            "client_id": cid,
            "grant_type": "authorization_code",
            "code": _CallbackHandler.code,
            "redirect_uri": config.SPOTIFY_REDIRECT_URI,
            "code_verifier": verifier,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise SpotifyError(f"Token exchange failed: {resp.text}")
    tokens = resp.json()
    _save_auth(
        {
            "client_id": cid,
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "expires_at": time.time() + tokens.get("expires_in", 3600) - 60,
        }
    )


def access_token() -> str:
    auth = _load_auth()
    if not auth.get("access_token"):
        raise NotAuthenticated("Not authorized with Spotify. Run `crate init`.")
    if time.time() < auth.get("expires_at", 0):
        return auth["access_token"]
    resp = httpx.post(
        TOKEN_URL,
        data={
            "client_id": auth["client_id"],
            "grant_type": "refresh_token",
            "refresh_token": auth["refresh_token"],
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise NotAuthenticated(f"Token refresh failed ({resp.status_code}); run `crate init` again.")
    tokens = resp.json()
    auth["access_token"] = tokens["access_token"]
    auth["refresh_token"] = tokens.get("refresh_token", auth["refresh_token"])
    auth["expires_at"] = time.time() + tokens.get("expires_in", 3600) - 60
    _save_auth(auth)
    return auth["access_token"]


def _request(method: str, path: str, **kwargs) -> Any:
    for attempt in range(3):
        resp = httpx.request(
            method,
            f"{API}{path}",
            headers={"Authorization": f"Bearer {access_token()}"},
            timeout=30,
            **kwargs,
        )
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 2)) + 1)
            continue
        if resp.status_code >= 400:
            raise SpotifyError(f"{method} {path} → {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.content else {}
    raise SpotifyError(f"{method} {path}: rate-limited after retries")


# --- Narrow API surface ---

def me() -> dict[str, Any]:
    return _request("GET", "/me")


def _norm(s: str) -> str:
    s = s.lower()
    for junk in ("(", ")", "[", "]", "-", "  "):
        s = s.replace(junk, " ")
    return " ".join(s.split())


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def search_track(track: str, artist: str, album: str | None = None) -> dict[str, Any] | None:
    """Find the best catalog match with a confidence score. Tries album-context
    search first, then artist+track. Returns
    {uri, name, artists, album, confidence} or None."""
    queries = []
    if album:
        queries.append(f'track:"{track}" artist:"{artist}" album:"{album}"')
    queries.append(f'track:"{track}" artist:"{artist}"')
    queries.append(f"{track} {artist}")

    best: dict[str, Any] | None = None
    for q in queries:
        data = _request("GET", "/search", params={"q": q, "type": "track", "limit": 5})
        for item in data.get("tracks", {}).get("items", []):
            found_artists = ", ".join(a["name"] for a in item["artists"])
            found_album = item["album"]["name"]
            conf = 0.6 * _similarity(track, item["name"]) + 0.4 * _similarity(artist, found_artists)
            haystack = f"{found_album} {found_artists}".lower()
            query_text = f"{track} {artist} {album or ''}".lower()
            if any(term in haystack and term not in query_text for term in POLLUTION_TERMS):
                conf *= 0.3
            candidate = {
                "uri": item["uri"],
                "name": item["name"],
                "artists": found_artists,
                "album": found_album,
                "confidence": round(conf, 3),
            }
            if best is None or candidate["confidence"] > best["confidence"]:
                best = candidate
        if best and best["confidence"] >= 0.9:
            break  # good enough; skip weaker query forms
    return best


def create_playlist(name: str, description: str, public: bool = False) -> dict[str, Any]:
    user_id = me()["id"]
    return _request(
        "POST",
        f"/users/{user_id}/playlists",
        json={"name": name, "description": description[:300], "public": public},
    )


def add_tracks(playlist_id: str, uris: list[str]) -> None:
    for i in range(0, len(uris), 100):
        _request("POST", f"/playlists/{playlist_id}/tracks", json={"uris": uris[i : i + 100]})


def top_tracks(limit: int = 50) -> list[dict[str, str]]:
    """User's recent top tracks, used as a freshness penalty in TRIANGULATE."""
    data = _request("GET", "/me/top/tracks", params={"limit": limit, "time_range": "medium_term"})
    return [
        {"track": t["name"], "artist": ", ".join(a["name"] for a in t["artists"])}
        for t in data.get("items", [])
    ]
