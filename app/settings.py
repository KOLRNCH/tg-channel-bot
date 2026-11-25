"""Application environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def parse_chat_id(raw: str) -> int | str:
    """Convert numeric chat ID strings to int while keeping @usernames intact."""
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("Chat ID must not be empty")
    if cleaned.lstrip("-").isdigit():
        return int(cleaned)
    return cleaned


def parse_admin_ids(raw: str) -> tuple[int, ...]:
    """Parse comma-separated Telegram user IDs into a non-empty tuple of ints."""
    ids: list[int] = []
    for chunk in raw.split(","):
        cleaned = chunk.strip()
        if not cleaned:
            continue
        if not cleaned.lstrip("-").isdigit():
            raise ValueError(f"Invalid admin ID: {cleaned!r}")
        ids.append(int(cleaned))
    if not ids:
        raise ValueError("ADMIN_IDS must contain at least one numeric Telegram user ID")
    return tuple(dict.fromkeys(ids))


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    bot_token: str
    admin_ids: tuple[int, ...]
    channel_id: int | str
    feedback_group_id: int | None
    config_path: Path
    db_path: Path

    @property
    def primary_admin_id(self) -> int:
        """Return the first configured admin ID for fallback PM delivery."""
        return self.admin_ids[0]


def load_settings(base_dir: Path | None = None) -> Settings:
    """Load and validate application settings from `.env` and environment variables."""
    root = base_dir or Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token or "ExampleToken" in bot_token:
        raise ValueError("BOT_TOKEN is not configured in .env")

    admin_ids = parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    channel_id = parse_chat_id(os.getenv("CHANNEL_ID", ""))

    raw_group = os.getenv("FEEDBACK_GROUP_ID", "").strip()
    feedback_group_id: int | None = None
    if raw_group:
        parsed_group = parse_chat_id(raw_group)
        if not isinstance(parsed_group, int):
            raise ValueError("FEEDBACK_GROUP_ID must be a numeric supergroup ID (e.g. -100...)")
        feedback_group_id = parsed_group

    data_dir = root / "data"
    return Settings(
        bot_token=bot_token,
        admin_ids=admin_ids,
        channel_id=channel_id,
        feedback_group_id=feedback_group_id,
        config_path=data_dir / "post_config.json",
        db_path=data_dir / "bot.db",
    )
