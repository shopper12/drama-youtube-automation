"""Configure a real YouTube Data API gateway from an existing OAuth token."""
from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .youtube_upload_service import GoogleYouTubeGateway, LocalYouTubeGateway, set_youtube_gateway

YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"


def configure_youtube_gateway() -> str:
    provider = os.getenv("YOUTUBE_PROVIDER", "local").lower()
    if provider == "local":
        set_youtube_gateway(LocalYouTubeGateway())
        return "local"
    if provider != "google":
        raise ValueError(f"Unknown YOUTUBE_PROVIDER: {provider}")
    path = Path(os.getenv("YOUTUBE_TOKEN_FILE", ""))
    if not path.is_file():
        raise RuntimeError("YOUTUBE_TOKEN_FILE not found. Run scripts/init_youtube_oauth.py locally.")
    credentials = Credentials.from_authorized_user_file(str(path), [YOUTUBE_SCOPE])
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        path.write_text(credentials.to_json(), encoding="utf-8")
    if not credentials.valid:
        raise RuntimeError("YouTube OAuth token is not valid")
    set_youtube_gateway(GoogleYouTubeGateway(build("youtube", "v3", credentials=credentials)))
    return "google"
