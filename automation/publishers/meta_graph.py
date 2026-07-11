#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


def _post(url: str, fields: dict[str, str]) -> dict[str, object]:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8", errors="replace")
        return json.loads(body) if body else {"status": response.status}


def publish_facebook(message: str, link: str | None = None) -> dict[str, object]:
    page_id = os.getenv("META_PAGE_ID", "").strip()
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    version = os.getenv("META_GRAPH_VERSION", "v22.0").strip()
    if not page_id or not token:
        raise RuntimeError("META_PAGE_ID and META_PAGE_ACCESS_TOKEN are required")
    fields = {"message": message, "access_token": token}
    if link:
        fields["link"] = link
    return _post(f"https://graph.facebook.com/{version}/{page_id}/feed", fields)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("text_file", type=Path)
    parser.add_argument("--link")
    args = parser.parse_args()
    message = args.text_file.read_text(encoding="utf-8")
    result = publish_facebook(message, args.link)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
