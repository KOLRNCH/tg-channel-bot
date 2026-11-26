"""Bot entry point wiring configuration, SQLite storage, and routers."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.handlers.admin import create_admin_router
from app.handlers.feedback import create_feedback_router
from app.miniapp_config import MiniAppConfigStore
from app.post_config import PostConfigStore
from app.settings import load_settings


async def run_bot() -> None:
    """Initialize bot services and start long polling."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    settings = load_settings()
    store = PostConfigStore(settings.config_path)
    store.load()
    miniapp_store = MiniAppConfigStore(settings.miniapp_config_path)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(create_admin_router(settings, store, miniapp_store))
    dp.include_router(create_feedback_router(settings, store))

    me = await bot.get_me()
    logging.info("Бот запущен: @%s (admin IDs: %s)", me.username, settings.admin_ids)

    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await bot.session.close()


def main() -> None:
    """Synchronous CLI entry point."""
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
