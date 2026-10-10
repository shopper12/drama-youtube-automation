"""Grounded Gemini episode analysis; output timestamps are proposals, never proof."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any


SCENE_PROMPT = """Analyse only events actually shown or spoken in this episode.
Return a JSON object with a single 'scenes' array (NO markdown):
[{{"start":"MM:SS","end":"MM:SS","event":"factual description in Korean",
  "characters":["names as spoken or identifiable"],"importance":1-5,
  "reason":"why needed to understand this episode","confidence":0.0-1.0,
  "spoiler":true}}]
Pick chronological turning points including setup, causality, key decisions, reversal
and actual ending if present. Do NOT invent future episodes, identities or outcomes.
Do not confuse character dialogue with confirmed facts. Scene boundaries must
match the uploaded video timeline; prefer short contiguous excerpts. If uncertain,
say so in 'event' and give low confidence. Return at most {limit} scenes."""


def seconds(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    parts = str(value).strip().split(":")
    if not parts or len(parts) > 3 or not all(re.fullmatch(r"\d+(?:\.\d+)?", p) for p in parts):
        raise ValueError(f"Invalid timestamp: {value!r}")
    result = 0.0
    for p in parts:
        result = result * 60 + float(p)
    return result


def parse_scenes(raw: str, duration: float, source_id: int, episode: int, max_scenes: int = 24) -> list[dict[str, Any]]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text, flags=re.I)
    data = json.loads(text)
    candidates = data.get("scenes") if isinstance(data, dict) else None
    if not isinstance(candidates, list):
        raise ValueError("Gemini response requires a scenes array")
    result: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        try:
            start, end = seconds(item["start"]), seconds(item["end"])
            importance = int(item.get("importance", 1))
            confidence = float(item.get("confidence", 0))
            event = str(item.get("event", "")).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= start < end <= duration + 0.5 and end-start >= 1 and event):
            continue
        if not (1 <= importance <= 5 and 0 <= confidence <= 1):
            continue
        result.append({
            "source_id": source_id, "episode_number": episode,
            "start_seconds": round(start, 2), "end_seconds": round(min(end, duration), 2),
            "event": event[:1200],
            "characters": [str(v)[:100] for v in item.get("characters", []) if isinstance(v, str)][:20],
            "importance": importance, "confidence": confidence,
            "reason": str(item.get("reason", ""))[:500],
            "spoiler": bool(item.get("spoiler", False)),
            "human_reviewed": False,
        })
    result.sort(key=lambda v: (v["start_seconds"], v["end_seconds"]))
    # Overlapping suggestions are not independently verifiable; keep the stronger.
    deduped: list[dict[str, Any]] = []
    for scene in result:
        if deduped and scene["start_seconds"] < deduped[-1]["end_seconds"]:
            prev = deduped[-1]
            if (scene["importance"], scene["confidence"]) > (prev["importance"], prev["confidence"]):
                deduped[-1] = scene
        else:
            deduped.append(scene)
    return deduped[:max_scenes]


class GeminiVideoAnalyzer:
    """Uses Google Files API + interactions API with explicit timeout and cleanup."""
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_VIDEO_MODEL", "gemini-3.8-flash")

    async def analyze(self, path: Path, duration: float, source_id: int, episode: int) -> list[dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured; analysis not performed")
        if not path.is_file():
            raise FileNotFoundError(path)

        def _call() -> str:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            uploaded = client.files.upload(file=str(path))
            try:
                deadline = time.monotonic() + 900
                while not getattr(uploaded, "state", None) or uploaded.state.name == "PROCESSING":
                    if time.monotonic() > deadline:
                        raise TimeoutError("Gemini video processing timed out")
                    time.sleep(4)
                    uploaded = client.files.get(name=uploaded.name)
                if uploaded.state.name != "ACTIVE":
                    raise RuntimeError(f"Gemini upload failed: {uploaded.state.name}")

                response = client.interactions.create(
                    model=self.model,
                    input=[
                        {"type": "video", "uri": uploaded.uri, "mime_type": uploaded.mime_type},
                        {"type": "text", "text": SCENE_PROMPT.format(limit=int(os.getenv("MAX_SCENES_PER_EPISODE", "24")))},
                    ],
                    background=True,
                )
                while response.status == "in_progress":
                    if time.monotonic() > deadline:
                        raise TimeoutError("Gemini video analysis timed out")
                    time.sleep(5)
                    response = client.interactions.get(response.id)
                if response.status not in ("completed", "succeeded"):
                    raise RuntimeError(f"Gemini analysis status: {response.status}")
                if not response.output_text:
                    raise ValueError("Gemini returned empty video analysis")
                return response.output_text
            finally:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:
                    pass
        raw = await asyncio.to_thread(_call)
        scenes = parse_scenes(raw, duration, source_id, episode, int(os.getenv("MAX_SCENES_PER_EPISODE", "24")))
        if not scenes:
            raise ValueError("AI returned no valid timestamps; human inspection required")
        return scenes


def select_highlights(scenes: list[dict[str, Any]], seconds_budget: float = 360) -> list[dict[str, Any]]:
    """Greedy capped selection, then restore original narrative order."""
    if seconds_budget <= 0:
        raise ValueError("seconds_budget must be positive")
    ranked = sorted(scenes, key=lambda s: (-int(s["importance"]), -float(s["confidence"])))
    chosen: list[dict[str, Any]] = []
    remaining = seconds_budget
    for scene in ranked:
        duration = float(scene["end_seconds"]) - float(scene["start_seconds"])
        if duration <= remaining and duration >= 1:
            chosen.append(scene)
            remaining -= duration
    return sorted(chosen, key=lambda s: (s["episode_number"], s["start_seconds"]))
