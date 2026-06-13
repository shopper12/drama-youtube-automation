import os

import httpx


async def notify(title: str, message: str) -> None:
    channel = os.getenv("NOTIFICATION_CHANNEL", "log")
    webhook = os.getenv("NOTIFICATION_WEBHOOK_URL")
    if not webhook:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        if channel == "discord":
            await client.post(webhook, json={"content": f"**{title}**\n{message}"})
        elif channel == "telegram":
            await client.post(webhook, json={"text": f"{title}\n{message}"})
