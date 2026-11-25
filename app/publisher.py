"""Publishing, previewing, pinning, and live-updating the channel welcome post."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import FSInputFile, InputMediaPhoto, Message

from app.keyboards import build_channel_keyboard
from app.post_config import PostConfig


class PostTypeMismatchError(RuntimeError):
    """Raised when attempting to switch between text-only and media posts in-place."""


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Outcome of publishing or updating the channel welcome post."""

    message_id: int
    pinned: bool
    pin_warning: str | None = None


def _resolve_photo_input(config: PostConfig) -> str | FSInputFile | None:
    """Return a Telegram file_id or FSInputFile if a banner image is configured."""
    if config.photo_file_id:
        return config.photo_file_id
    if config.photo_path:
        path = Path(config.photo_path)
        if path.exists():
            return FSInputFile(path)
    return None


async def send_welcome_post(
    bot: Bot,
    chat_id: int | str,
    config: PostConfig,
    bot_username: str | None,
    *,
    pin: bool = False,
) -> PublishResult:
    """Send the formatted welcome post with styled inline buttons to a chat or channel."""
    markup = build_channel_keyboard(config, bot_username=bot_username)
    photo = _resolve_photo_input(config)

    if photo is not None:
        sent: Message = await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=config.text_html,
            parse_mode="HTML",
            reply_markup=markup,
        )
        if sent.photo:
            config.photo_file_id = sent.photo[-1].file_id
    else:
        sent = await bot.send_message(
            chat_id=chat_id,
            text=config.text_html,
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=True,
        )

    pinned = False
    pin_warning: str | None = None
    if pin:
        try:
            await bot.pin_chat_message(
                chat_id=chat_id,
                message_id=sent.message_id,
                disable_notification=True,
            )
            pinned = True
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            pin_warning = f"Пост опубликован, но не удалось закрепить: {exc.message}"

    return PublishResult(message_id=sent.message_id, pinned=pinned, pin_warning=pin_warning)


async def update_published_post(
    bot: Bot,
    config: PostConfig,
    bot_username: str | None,
) -> None:
    """Edit the already published pinned post in-place without changing its message ID."""
    if not config.published_channel_id or not config.published_message_id:
        raise ValueError("Пост ещё не опубликован через бота.")

    photo = _resolve_photo_input(config)
    has_media_now = photo is not None
    if has_media_now != config.published_has_media:
        raise PostTypeMismatchError(
            "Telegram не позволяет добавить или убрать фото у уже существующего поста. "
            "Нажмите «📢 Опубликовать и закрепить заново»."
        )

    markup = build_channel_keyboard(config, bot_username=bot_username)
    chat_id = config.published_channel_id
    message_id = config.published_message_id

    try:
        if has_media_now and photo is not None:
            await bot.edit_message_media(
                chat_id=chat_id,
                message_id=message_id,
                media=InputMediaPhoto(
                    media=photo,
                    caption=config.text_html,
                    parse_mode="HTML",
                ),
                reply_markup=markup,
            )
        else:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=config.text_html,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=True,
            )
    except TelegramBadRequest as exc:
        if "message is not modified" in exc.message.lower():
            return
        raise
