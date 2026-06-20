"""[9] PUBLISH — upload a finished MP4 to YouTube via the Data API v3.

First-time setup (one-off, ~5 min) — see docs/youtube-setup.md:
  1. Google Cloud Console -> new project -> enable "YouTube Data API v3".
  2. OAuth consent screen: External, add yourself as a test user.
  3. Create credentials -> OAuth client ID -> **Desktop app** -> download JSON.
  4. Save it as client_secret.json in the repo root (or set YT_CLIENT_SECRETS).

The first upload opens a browser to grant access; the token is cached in
yt_token.json (YT_TOKEN_STORE) and refreshed automatically afterwards.
"""
from __future__ import annotations
import os, pathlib

ROOT = pathlib.Path(__file__).parent.parent.parent
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _path(env: str, default: str) -> pathlib.Path:
    p = pathlib.Path(os.getenv(env, default))
    return p if p.is_absolute() else (ROOT / p)


def client_secrets_path() -> pathlib.Path:
    return _path("YT_CLIENT_SECRETS", "client_secret.json")


def token_path() -> pathlib.Path:
    return _path("YT_TOKEN_STORE", "yt_token.json")


def configured() -> bool:
    """True once a client_secret.json or a cached token exists."""
    return client_secrets_path().exists() or token_path().exists()


class NeedsAuthSetup(RuntimeError):
    """No client_secret.json and no cached token — user must do OAuth setup."""


def get_credentials(allow_console: bool = True):
    """Load cached creds, refresh, or run the consent flow. Returns Credentials."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    tok = token_path()
    creds = None
    if tok.exists():
        creds = Credentials.from_authorized_user_file(str(tok), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        tok.write_text(creds.to_json(), encoding="utf-8")
        return creds

    secrets = client_secrets_path()
    if not secrets.exists():
        raise NeedsAuthSetup(
            f"no {secrets.name} found — follow docs/youtube-setup.md to create an "
            "OAuth client (Desktop app) and save it as client_secret.json.")
    if not allow_console:
        raise NeedsAuthSetup("YouTube authorization required — run the consent flow.")

    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
    # Desktop-app clients accept any localhost port, so port=0 picks a free one.
    creds = flow.run_local_server(port=0, prompt="consent")
    tok.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _parse_tags(tags) -> list[str]:
    if isinstance(tags, list):
        items = tags
    else:
        items = (tags or "").replace("\n", ",").split(",")
    return [t.strip() for t in items if t and t.strip()]


def upload(video_path: str, title: str, description: str = "", tags=None,
           privacy: str = "private", category_id: str = "27",
           on_progress=None, allow_console: bool = True) -> dict:
    """Upload `video_path` to YouTube. Returns {id, url}. category 27 = Education.

    `on_progress(percent)` is called during the resumable upload."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError

    vp = pathlib.Path(video_path)
    if not vp.exists():
        raise FileNotFoundError(f"no video at {vp}")
    if privacy not in ("private", "unlisted", "public"):
        privacy = "private"

    creds = get_credentials(allow_console=allow_console)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {"title": (title or vp.stem)[:100],
                    "description": description or "",
                    "tags": _parse_tags(tags),
                    "categoryId": category_id},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(vp), mimetype="video/mp4", chunksize=4 * 1024 * 1024,
                            resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    try:
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status and on_progress:
                on_progress(int(status.progress() * 100))
    except HttpError as e:  # surface YouTube's reason (quota, etc.)
        raise RuntimeError(f"YouTube API error: {e}") from e

    vid = response.get("id", "")
    if on_progress:
        on_progress(100)
    return {"id": vid, "url": f"https://youtu.be/{vid}" if vid else ""}
