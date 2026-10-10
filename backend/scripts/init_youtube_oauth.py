"""One-time interactive OAuth bootstrap on a trusted local computer.

Usage:
  YOUTUBE_CLIENT_SECRET_FILE=/secure/client_secret.json \
  YOUTUBE_TOKEN_FILE=/secure/youtube_token.json \
  python scripts/init_youtube_oauth.py

Never commit OAuth token files.
"""
from pathlib import Path
import os
from google_auth_oauthlib.flow import InstalledAppFlow

scope = ["https://www.googleapis.com/auth/youtube"]
client_secrets = os.environ["YOUTUBE_CLIENT_SECRET_FILE"]
token = Path(os.environ["YOUTUBE_TOKEN_FILE"])
credentials = InstalledAppFlow.from_client_secrets_file(
    client_secrets, scopes=scope
).run_local_server(port=0, access_type="offline", prompt="consent")
token.parent.mkdir(parents=True, exist_ok=True)
token.write_text(credentials.to_json(), encoding="utf-8")
print(f"Saved YouTube OAuth token to {token}; do not commit it")
