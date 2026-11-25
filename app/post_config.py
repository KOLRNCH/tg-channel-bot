"""Persistent JSON configuration for the channel welcome post and styled buttons."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

ButtonStyleName = Literal["default", "primary", "success", "danger"]
VALID_STYLES: tuple[ButtonStyleName, ...] = ("default", "primary", "success", "danger")

DEFAULT_WELCOME_HTML = (
    "👋 <b>Добро пожаловать на канал!</b>\n\n"
    "<blockquote>Здесь выходят анонсы стримов, ролики, новости и закулисье — всё самое важное в одном месте.</blockquote>\n\n"
    "📌 <b>Полезные ссылки под постом:</b>\n"
    "• <b>YouTube</b> — основные видео, нарезки и гайды\n"
    "• <b>Twitch</b> — прямые эфиры и общение в реальном времени\n"
    "• <b>Чат в ТГ</b> — наше комьюнити и обсуждения\n"
    "• <b>Предложка</b> — написать лично админу (у каждого свой отдельный диалог)\n\n"
    "<i>Жми на нужную кнопку ниже 👇</i>"
)

DEFAULT_FEEDBACK_GREETING_HTML = (
    "📩 <b>Привет! Это предложка и личная связь с автором канала.</b>\n\n"
    "Просто отправь сюда своё сообщение — текст, фото, видео, кружок или файл.\n"
    "Для тебя автоматически создаётся <b>отдельный диалог</b>, и ответ придёт прямо в этот чат."
)


@dataclass(slots=True)
class ButtonConfig:
    """Single inline URL button configuration."""

    id: str
    text: str
    url: str
    row: int = 1
    style: ButtonStyleName = "default"
    icon_custom_emoji_id: str | None = None

    def normalized_style(self) -> ButtonStyleName:
        """Return a valid button style, falling back to 'default'."""
        return self.style if self.style in VALID_STYLES else "default"


@dataclass(slots=True)
class PostConfig:
    """Welcome post content, buttons, and last published message reference."""

    text_html: str = DEFAULT_WELCOME_HTML
    photo_file_id: str | None = None
    photo_path: str | None = None
    feedback_greeting_html: str = DEFAULT_FEEDBACK_GREETING_HTML
    buttons: list[ButtonConfig] = field(default_factory=list)
    published_channel_id: int | str | None = None
    published_message_id: int | None = None
    published_has_media: bool = False

    def find_button(self, button_id: str) -> ButtonConfig | None:
        """Return the button matching `button_id`, or None."""
        for button in self.buttons:
            if button.id == button_id:
                return button
        return None

    def next_row_number(self) -> int:
        """Return the next row index for appending a new button row."""
        if not self.buttons:
            return 1
        return max(btn.row for btn in self.buttons) + 1

    def add_button(
        self,
        text: str,
        url: str,
        row: int | None = None,
        style: ButtonStyleName = "default",
        icon_custom_emoji_id: str | None = None,
    ) -> ButtonConfig:
        """Create and append a new button to the configuration."""
        clean_style: ButtonStyleName = style if style in VALID_STYLES else "default"
        button = ButtonConfig(
            id=uuid.uuid4().hex[:8],
            text=text.strip(),
            url=url.strip(),
            row=row if row and row > 0 else self.next_row_number(),
            style=clean_style,
            icon_custom_emoji_id=icon_custom_emoji_id.strip() if icon_custom_emoji_id else None,
        )
        self.buttons.append(button)
        return button

    def remove_button(self, button_id: str) -> bool:
        """Remove a button by ID; return True if removed."""
        before = len(self.buttons)
        self.buttons = [btn for btn in self.buttons if btn.id != button_id]
        return len(self.buttons) < before

    def move_button(self, button_id: str, direction: int) -> bool:
        """Shift a button earlier (-1) or later (+1) in the list."""
        idx = next((i for i, btn in enumerate(self.buttons) if btn.id == button_id), None)
        if idx is None:
            return False
        target = idx + direction
        if target < 0 or target >= len(self.buttons):
            return False
        self.buttons[idx], self.buttons[target] = self.buttons[target], self.buttons[idx]
        return True


def create_default_post_config() -> PostConfig:
    """Create the initial welcome post preset with YouTube, Twitch, TG chat, and Предложка."""
    return PostConfig(
        buttons=[
            ButtonConfig(
                id="youtube",
                text="▶ YouTube",
                url="https://www.youtube.com/@your_channel",
                row=1,
                style="danger",
            ),
            ButtonConfig(
                id="twitch",
                text="🟣 Twitch",
                url="https://www.twitch.tv/your_channel",
                row=1,
                style="default",
            ),
            ButtonConfig(
                id="tg_chat",
                text="💬 Чат в ТГ",
                url="https://t.me/your_chat",
                row=2,
                style="primary",
            ),
            ButtonConfig(
                id="suggest",
                text="📩 Предложка",
                url="https://t.me/{bot_username}?start=suggest",
                row=3,
                style="success",
            ),
        ]
    )


class PostConfigStore:
    """Loads and persists `PostConfig` to a JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> PostConfig:
        """Load config from disk, or initialize with defaults on first run."""
        if not self.path.exists():
            config = create_default_post_config()
            self.save(config)
            return config

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        buttons = [
            ButtonConfig(
                id=str(item.get("id") or uuid.uuid4().hex[:8]),
                text=str(item["text"]),
                url=str(item["url"]),
                row=int(item.get("row", 1)),
                style=item.get("style", "default") if item.get("style") in VALID_STYLES else "default",
                icon_custom_emoji_id=item.get("icon_custom_emoji_id") or None,
            )
            for item in raw.get("buttons", [])
        ]
        return PostConfig(
            text_html=str(raw.get("text_html") or DEFAULT_WELCOME_HTML),
            photo_file_id=raw.get("photo_file_id") or None,
            photo_path=raw.get("photo_path") or None,
            feedback_greeting_html=str(
                raw.get("feedback_greeting_html") or DEFAULT_FEEDBACK_GREETING_HTML
            ),
            buttons=buttons,
            published_channel_id=raw.get("published_channel_id"),
            published_message_id=raw.get("published_message_id"),
            published_has_media=bool(raw.get("published_has_media", False)),
        )

    def save(self, config: PostConfig) -> None:
        """Atomically persist `PostConfig` to JSON with readable UTF-8 formatting."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(config)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)
