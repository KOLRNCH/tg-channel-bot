"""Private chat router redirecting subscribers to the channel Mini App."""

from __future__ import annotations

from urllib.parse import urlparse

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.keyboards import resolve_button_url
from app.post_config import PostConfig, PostConfigStore
from app.settings import Settings

MENU_REDIRECT_HTML = (
    "✦ <b>Меню канала</b>\n\n"
    "Все ссылки, соцсети и предложка находятся в мини-приложении.\n"
    "Нажмите кнопку ниже, чтобы открыть его 👇"
)


def resolve_miniapp_menu_url(config: PostConfig, bot_username: str | None) -> str:
    """Resolve the Mini App launch URL from post buttons or fall back to `/menu`."""
    username = (bot_username or "your_bot").lstrip("@")
    for btn in config.buttons:
        resolved = resolve_button_url(btn.url, username)
        parsed = urlparse(resolved)
        if parsed.netloc in {"t.me", "telegram.me"}:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0].lower() == username.lower():
                return resolved
    return f"https://t.me/{username}/menu"


def build_open_menu_kb(menu_url: str) -> InlineKeyboardMarkup:
    """Build a single-button keyboard opening the channel Mini App."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✦ Открыть меню канала",
                    url=menu_url,
                    style="primary",
                )
            ]
        ]
    )


def create_feedback_router(
    settings: Settings,
    store: PostConfigStore,
) -> Router:
    """Create the private-chat router that points users to the channel Mini App."""
    router = Router(name="feedback")
    is_admin = F.from_user.id.in_(settings.admin_ids)

    @router.message(is_admin, F.chat.type == ChatType.PRIVATE, CommandStart())
    async def admin_start(message: Message) -> None:
        await message.answer(
            "⚙️ <b>Вы вошли как администратор.</b>\n"
            "Используйте /admin для настройки закреплённого поста, кнопок и Mini App.",
            parse_mode="HTML",
        )

    @router.message(is_admin, F.chat.type == ChatType.PRIVATE)
    async def admin_pm_hint(message: Message) -> None:
        await message.answer(
            "⚙️ Используйте /admin для управления закреплённым постом и Mini App."
        )

    @router.message(F.chat.type == ChatType.PRIVATE, ~is_admin)
    async def subscriber_open_menu(message: Message, bot: Bot) -> None:
        """Reply to any subscriber message with a single button to open the Mini App."""
        me = await bot.get_me()
        menu_url = resolve_miniapp_menu_url(store.load(), me.username)
        await message.answer(
            MENU_REDIRECT_HTML,
            parse_mode="HTML",
            reply_markup=build_open_menu_kb(menu_url),
        )

    return router
