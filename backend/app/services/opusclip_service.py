"""Optional, opt-in OpusClip ClipAnything helper; never publishes or charges silently."""
from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx


class OpusClipClient:
    BASE = "https://api.opus.pro/api"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPUSCLIP_API_KEY")

    def headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("OPUSCLIP_API_KEY is missing")
        return {"Authorization": f"Bearer {self.api_key}"}

    async def create_shorts(self, source_url: str, *, billing_confirmed: bool,
                            rights_verified: bool, prompt: str = "") -> dict:
        """Submit only sources the user may share with an external clipping platform."""
        if not billing_confirmed:
            raise PermissionError("OpusClip is paid; explicit billing confirmation required")
        if not rights_verified:
            raise PermissionError("Rights to share the source video with OpusClip are unverified")
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Use a valid HTTPS source URL controlled by the operator")
        # Do not download/resolve the supplied URL on our server.
        body = {
            "videoUrl": source_url,
            "curationPref": {
                "model": "ClipAnything",
                "clipDurations": [[30, 60]],
                "genre": "Korean television drama recap",
                "customPrompt": prompt or
                    "Choose source-grounded plot turning points, tension or reversal. Avoid invented events.",
            },
            "renderPref": {"layoutAspectRatio": "portrait"},
            "importPreference": {"sourceLang": "ko"},
        }
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(f"{self.BASE}/clip-projects",
                                         headers=self.headers(), json=body)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise RuntimeError("Unexpected OpusClip project response")
            return result

    async def list_shorts(self, opus_project_id: str) -> dict:
        if not opus_project_id or len(opus_project_id) > 128:
            raise ValueError("Invalid OpusClip project ID")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.BASE}/exportable-clips",
                headers=self.headers(),
                params={"q": "findByProjectId", "projectId": opus_project_id},
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise RuntimeError("Unexpected OpusClip export result")
            return data
