"""Keyboard builders for the styled channel welcome post and admin editor."""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlparse

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.post_config import ButtonConfig, ButtonStyleName, PostConfig

STYLE_BADGES: dict[ButtonStyleName, str] = {
    "default": "⚪ Стандартная",
    "primary": "🔵 Синяя (primary)",
    "success": "🟢 Зелёная (success)",
    "danger": "🔴 Красная (danger)",
}

STYLE_DOTS: dict[ButtonStyleName, str] = {
    "default": "⚪",
    "primary": "🔵",
    "success": "🟢",
    "danger": "🔴",
}


def resolve_button_url(url_template: str, bot_username: str | None = None) -> str:
    """Substitute `{bot_username}` placeholder when building live Telegram URLs."""
    cleaned = url_template.strip()
    if "{bot_username}" in cleaned:
        username = (bot_username or "your_bot").lstrip("@")
        return cleaned.replace("{bot_username}", username)
    return cleaned


def is_valid_button_url(url: str) -> bool:
    """Check whether a button URL has an allowed HTTP(S) or tg:// scheme."""
    resolved = resolve_button_url(url, "example_bot")
    parsed = urlparse(resolved)
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.netloc)
    if parsed.scheme == "tg":
        return bool(parsed.netloc or parsed.path)
    return False


def build_channel_keyboard(
    config: PostConfig,
    bot_username: str | None = None,
) -> InlineKeyboardMarkup | None:
    """Build the Telegram inline keyboard with custom styles and row layout."""
    if not config.buttons:
        return None

    rows_map: dict[int, list[InlineKeyboardButton]] = defaultdict(list)
    for btn in config.buttons:
        style = btn.normalized_style()
        kwargs: dict[str, object] = {
            "text": btn.text,
            "url": resolve_button_url(btn.url, bot_username),
        }
        if style != "default":
            kwargs["style"] = style
        if btn.icon_custom_emoji_id:
            kwargs["icon_custom_emoji_id"] = btn.icon_custom_emoji_id
        rows_map[btn.row].append(InlineKeyboardButton(**kwargs))

    keyboard = [rows_map[row_idx] for row_idx in sorted(rows_map)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_admin_main_kb(config: PostConfig) -> InlineKeyboardMarkup:
    """Build the main `/admin` control panel keyboard."""
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="👁 Предпросмотр поста",
                callback_data="adm:preview",
                style="primary",
            ),
        ],
        [
            InlineKeyboardButton(text="✏️ Текст приветствия", callback_data="adm:edit_text"),
            InlineKeyboardButton(text="🖼 Обложка (фото)", callback_data="adm:edit_photo"),
        ],
        [
            InlineKeyboardButton(
                text=f"🔘 Кнопки и стили ({len(config.buttons)})",
                callback_data="adm:buttons",
            ),
            InlineKeyboardButton(
                text="📩 Текст предложки",
                callback_data="adm:edit_feedback_text",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🧩 Узнать ID кастом-эмодзи",
                callback_data="adm:emoji_id",
            ),
        ],
    ]

    if config.published_message_id:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔄 Обновить закреплённый пост",
                    callback_data="adm:update_published",
                    style="success",
                ),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="📢 Опубликовать и закрепить заново",
                callback_data="adm:publish_new",
                style="danger" if config.published_message_id else "success",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_photo_menu_kb(has_photo: bool) -> InlineKeyboardMarkup:
    """Build photo/banner submenu keyboard."""
    rows = [
        [InlineKeyboardButton(text="📤 Загрузить новое фото", callback_data="adm:photo_upload", style="primary")],
    ]
    if has_photo:
        rows.append([InlineKeyboardButton(text="🗑 Убрать фото", callback_data="adm:photo_clear", style="danger")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_buttons_list_kb(config: PostConfig) -> InlineKeyboardMarkup:
    """Build the list of configured post buttons with row and style badges."""
    rows: list[list[InlineKeyboardButton]] = []
    for btn in config.buttons:
        dot = STYLE_DOTS.get(btn.normalized_style(), "⚪")
        emoji_tag = " 🧩" if btn.icon_custom_emoji_id else ""
        label = f"{dot} [Ряд {btn.row}] {btn.text}{emoji_tag}"
        rows.append(
            [InlineKeyboardButton(text=label[:60], callback_data=f"adm:btn:{btn.id}")]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Добавить кнопку",
                callback_data="adm:btn_add",
                style="success",
            ),
            InlineKeyboardButton(
                text="✨ Кнопка Mini App",
                callback_data="adm:btn_add_miniapp",
                style="primary",
            ),
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_button_edit_kb(button: ButtonConfig) -> InlineKeyboardMarkup:
    """Build per-button editor keyboard."""
    bid = button.id
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"adm:btn_text:{bid}"),
                InlineKeyboardButton(text="🔗 Изменить ссылку", callback_data=f"adm:btn_url:{bid}"),
            ],
            [
                InlineKeyboardButton(
                    text=f"🎨 Стиль: {STYLE_DOTS.get(button.normalized_style(), '⚪')}",
                    callback_data=f"adm:btn_style_menu:{bid}",
                    style=button.normalized_style() if button.normalized_style() != "default" else None,
                ),
                InlineKeyboardButton(
                    text="🧩 Эмодзи ID",
                    callback_data=f"adm:btn_emoji:{bid}",
                ),
            ],
            [
                InlineKeyboardButton(text="📐 Номер ряда", callback_data=f"adm:btn_row:{bid}"),
                InlineKeyboardButton(text="⬆️ Выше", callback_data=f"adm:btn_up:{bid}"),
                InlineKeyboardButton(text="⬇️ Ниже", callback_data=f"adm:btn_down:{bid}"),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить кнопку",
                    callback_data=f"adm:btn_del:{bid}",
                    style="danger",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ К списку кнопок", callback_data="adm:buttons")],
        ]
    )


def build_style_picker_kb(prefix: str, back_callback: str) -> InlineKeyboardMarkup:
    """Build color style selection keyboard for adding or editing a button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔴 Красная (danger)",
                    callback_data=f"{prefix}:danger",
                    style="danger",
                ),
                InlineKeyboardButton(
                    text="🔵 Синяя (primary)",
                    callback_data=f"{prefix}:primary",
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🟢 Зелёная (success)",
                    callback_data=f"{prefix}:success",
                    style="success",
                ),
                InlineKeyboardButton(
                    text="⚪ Стандартная",
                    callback_data=f"{prefix}:default",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)],
        ]
    )


def build_cancel_kb(back_callback: str = "adm:cancel") -> InlineKeyboardMarkup:
    """Build a single cancel button for FSM text/link input steps."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=back_callback, style="danger")]
        ]
    )


def build_topic_header_kb(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    """Build moderation buttons pinned at the start of a subscriber's feedback topic."""
    ban_btn = (
        InlineKeyboardButton(
            text="✅ Разблокировать",
            callback_data=f"fb:unban:{user_id}",
            style="success",
        )
        if is_banned
        else InlineKeyboardButton(
            text="🚫 Заблокировать",
            callback_data=f"fb:ban:{user_id}",
            style="danger",
        )
    )
    return InlineKeyboardMarkup(inline_keyboard=[[ban_btn]])


def build_submission_actions_kb(user_id: int) -> InlineKeyboardMarkup:
    """Build quick publish button attached to incoming user submissions in the topic."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Опубликовать в канал",
                    callback_data=f"fb:publish:{user_id}",
                    style="primary",
                )
            ]
        ]
    )
