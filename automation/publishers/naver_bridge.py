#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def publish(markdown_path: Path, title: str | None = None) -> dict[str, object]:
    url = os.getenv("NAVER_BLOG_BRIDGE_URL", "").strip()
    token = os.getenv("NAVER_BLOG_BRIDGE_TOKEN", "").strip()
    if not url:
        raise RuntimeError("NAVER_BLOG_BRIDGE_URL is required")

    markdown = markdown_path.read_text(encoding="utf-8")
    resolved_title = title or next(
        (line.removeprefix("# ").strip() for line in markdown.splitlines() if line.startswith("# ")),
        markdown_path.stem,
    )
    payload = json.dumps(
        {
            "title": resolved_title,
            "markdown": markdown,
            "source": "unified-media-automation",
        },
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {
                "status": response.status,
                "body": json.loads(body) if body else {},
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Naver bridge failed: HTTP {exc.code}: {body}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--title")
    args = parser.parse_args()
    result = publish(args.markdown, args.title)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
