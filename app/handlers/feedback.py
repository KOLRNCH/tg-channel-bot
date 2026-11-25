"""Separate-dialogue feedback box ("предложка") using Forum Topics or admin PM replies."""

from __future__ import annotations

import html
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message, ReactionTypeEmoji, User

from app.db import Database, UserTopic
from app.keyboards import build_submission_actions_kb, build_topic_header_kb
from app.post_config import PostConfigStore
from app.settings import Settings

logger = logging.getLogger(__name__)


def format_topic_title(user: User) -> str:
    """Format a compact, readable forum topic name for a subscriber."""
    name = (user.full_name or "Пользователь").strip()
    username_part = f" (@{user.username})" if user.username else ""
    title = f"{name}{username_part} • {user.id}"
    return title[:128]


def format_user_card(user: User) -> str:
    """Format the pinned header card inside a subscriber's private dialogue topic."""
    username_line = f"@{html.escape(user.username)}" if user.username else "без username"
    return (
        "👤 <b>Новый диалог в предложке</b>\n\n"
        f"<b>Имя:</b> {html.escape(user.full_name or 'Без имени')}\n"
        f"<b>Username:</b> {username_line}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n\n"
        "<i>Пишите сообщения прямо в эту тему — бот доставит их пользователю в ЛС.</i>"
    )


def create_feedback_router(
    settings: Settings,
    store: PostConfigStore,
    db: Database,
) -> Router:
    """Create the feedback router supporting per-user Forum Topics and PM fallback."""
    router = Router(name="feedback")
    is_admin = F.from_user.id.in_(settings.admin_ids)

    async def _create_and_pin_topic(bot: Bot, user: User, group_id: int) -> UserTopic:
        topic = await bot.create_forum_topic(chat_id=group_id, name=format_topic_title(user))
        record = await db.upsert_topic(
            user_id=user.id,
            topic_thread_id=topic.message_thread_id,
            username=user.username,
            full_name=user.full_name or "Пользователь",
        )
        header = await bot.send_message(
            chat_id=group_id,
            message_thread_id=topic.message_thread_id,
            text=format_user_card(user),
            parse_mode="HTML",
            reply_markup=build_topic_header_kb(user.id, is_banned=record.is_banned),
        )
        try:
            await bot.pin_chat_message(
                chat_id=group_id,
                message_id=header.message_id,
                disable_notification=True,
            )
        except TelegramBadRequest:
            pass
        return record

    async def _ensure_topic(bot: Bot, user: User, group_id: int) -> tuple[UserTopic, bool]:
        existing = await db.get_topic_by_user(user.id)
        if existing is not None:
            return existing, False
        created = await _create_and_pin_topic(bot, user, group_id)
        return created, True

    async def _copy_to_topic_with_actions(
        bot: Bot,
        group_id: int,
        thread_id: int,
        message: Message,
        user_id: int,
    ) -> None:
        markup = build_submission_actions_kb(user_id)
        try:
            await bot.copy_message(
                chat_id=group_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                message_thread_id=thread_id,
                reply_markup=markup,
            )
        except TelegramBadRequest as exc:
            msg_lower = exc.message.lower()
            if "reply markup" in msg_lower or "can't be used" in msg_lower:
                await bot.copy_message(
                    chat_id=group_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    message_thread_id=thread_id,
                )
                return
            raise

    @router.message(F.chat.type == ChatType.PRIVATE, CommandStart())
    async def cmd_start(message: Message) -> None:
        config = store.load()
        if message.from_user and message.from_user.id in settings.admin_ids:
            await message.answer(
                f"{config.feedback_greeting_html}\n\n"
                "⚙️ <i>Вы вошли как администратор. Для настройки поста и кнопок откройте /admin.</i>",
                parse_mode="HTML",
            )
            return
        await message.answer(config.feedback_greeting_html, parse_mode="HTML")

    @router.message(is_admin, F.chat.type == ChatType.PRIVATE, F.reply_to_message)
    async def admin_pm_reply_to_subscriber(message: Message, bot: Bot) -> None:
        """Deliver admin replies in fallback PM mode back to the subscriber."""
        if not message.reply_to_message:
            return
        target_user_id = await db.get_user_by_dm(message.reply_to_message.message_id)
        if target_user_id is None:
            return
        try:
            await bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            await message.reply("✅ Ответ отправлен подписчику.")
        except TelegramForbiddenError:
            await message.reply("⚠️ Пользователь заблокировал бота и не может получить сообщение.")

    @router.message(is_admin, F.chat.type == ChatType.PRIVATE)
    async def admin_pm_hint(message: Message) -> None:
        await message.answer(
            "⚙️ Используйте /admin для редактирования закреплённого поста и кнопок.\n"
            "Если предложка настроена через группу-форум, отвечайте подписчикам прямо в их темах."
        )

    @router.message(F.chat.type == ChatType.PRIVATE, ~is_admin)
    async def subscriber_incoming_message(message: Message, bot: Bot) -> None:
        """Route any subscriber message into their dedicated forum topic or admin PM."""
        user = message.from_user
        if user is None:
            return

        if await db.is_user_banned(user.id):
            await message.answer("⛔ Вы заблокированы в предложке этого канала.")
            return

        if settings.feedback_group_id is not None:
            group_id = settings.feedback_group_id
            try:
                topic, just_created = await _ensure_topic(bot, user, group_id)
                try:
                    await _copy_to_topic_with_actions(
                        bot, group_id, topic.topic_thread_id, message, user.id
                    )
                except TelegramBadRequest as exc:
                    if "thread not found" in exc.message.lower():
                        topic = await _create_and_pin_topic(bot, user, group_id)
                        just_created = True
                        await _copy_to_topic_with_actions(
                            bot, group_id, topic.topic_thread_id, message, user.id
                        )
                    else:
                        raise
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                logger.exception("Failed to route feedback to topic group %s", group_id)
                await message.answer(
                    "⚠️ Сейчас не удалось доставить сообщение. Попробуйте чуть позже."
                )
                try:
                    await bot.send_message(
                        chat_id=settings.primary_admin_id,
                        text=(
                            "⚠️ <b>Ошибка предложки:</b> не удалось создать тему в группе "
                            f"<code>{group_id}</code>.\n"
                            "Проверьте, что в группе включены <b>Темы (Topics)</b>, "
                            "а у бота есть права администратора на управление темами.\n"
                            f"Детали: <code>{html.escape(exc.message)}</code>"
                        ),
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
                return

            try:
                await message.react([ReactionTypeEmoji(emoji="👍")])
            except TelegramBadRequest:
                pass

            if just_created:
                await message.answer(
                    "✅ Диалог открыт! Сообщение передано автору, ответ придёт прямо в этот чат."
                )
            return

        # Fallback PM mode when FEEDBACK_GROUP_ID is not configured
        username_part = f" (@{user.username})" if user.username else ""
        header = await bot.send_message(
            chat_id=settings.primary_admin_id,
            text=(
                f"📩 <b>Новое сообщение в предложку</b>\n"
                f"От: {html.escape(user.full_name or 'Пользователь')}{html.escape(username_part)} "
                f"[<code>{user.id}</code>]\n"
                "<i>Ответьте (Reply) на это сообщение, чтобы написать пользователю.</i>"
            ),
            parse_mode="HTML",
        )
        copied = await bot.copy_message(
            chat_id=settings.primary_admin_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await db.save_dm_link(header.message_id, user.id)
        await db.save_dm_link(copied.message_id, user.id)
        await message.answer("✅ Сообщение отправлено автору! Ответ придёт сюда.")

    @router.message(
        is_admin,
        F.chat.id == settings.feedback_group_id if settings.feedback_group_id is not None else F.chat.id == 0,
        F.message_thread_id,
    )
    async def admin_topic_reply(message: Message, bot: Bot) -> None:
        """Forward admin messages written inside a user's topic back to that subscriber."""
        if message.from_user and message.from_user.is_bot:
            return
        if message.text and message.text.startswith("/"):
            return
        # Ignore Telegram forum/pin service messages
        if any(
            getattr(message, attr, None) is not None
            for attr in (
                "forum_topic_created",
                "forum_topic_edited",
                "forum_topic_closed",
                "forum_topic_reopened",
                "pinned_message",
            )
        ):
            return

        assert message.message_thread_id is not None
        topic = await db.get_topic_by_thread(message.message_thread_id)
        if topic is None:
            return

        try:
            await bot.copy_message(
                chat_id=topic.user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            try:
                await message.react([ReactionTypeEmoji(emoji="⚡")])
            except TelegramBadRequest:
                pass
        except TelegramForbiddenError:
            await message.reply("⚠️ Подписчик заблокировал бота и не может получить сообщение.")
        except Exception as exc:
            logger.exception("Failed to relay admin reply to user %s", topic.user_id)
            await message.reply(f"⚠️ Не удалось доставить сообщение: {exc}")

    @router.callback_query(is_admin, F.data.startswith("fb:ban:"))
    async def cb_ban_user(callback: CallbackQuery, bot: Bot) -> None:
        user_id = int(callback.data.split(":", 2)[2])
        await db.set_user_banned(user_id, True)
        if callback.message:
            await callback.message.edit_reply_markup(
                reply_markup=build_topic_header_kb(user_id, is_banned=True)
            )
            if callback.message.message_thread_id and settings.feedback_group_id:
                try:
                    await bot.close_forum_topic(
                        chat_id=settings.feedback_group_id,
                        message_thread_id=callback.message.message_thread_id,
                    )
                except TelegramBadRequest:
                    pass
        await callback.answer("Пользователь заблокирован")

    @router.callback_query(is_admin, F.data.startswith("fb:unban:"))
    async def cb_unban_user(callback: CallbackQuery, bot: Bot) -> None:
        user_id = int(callback.data.split(":", 2)[2])
        await db.set_user_banned(user_id, False)
        if callback.message:
            await callback.message.edit_reply_markup(
                reply_markup=build_topic_header_kb(user_id, is_banned=False)
            )
            if callback.message.message_thread_id and settings.feedback_group_id:
                try:
                    await bot.reopen_forum_topic(
                        chat_id=settings.feedback_group_id,
                        message_thread_id=callback.message.message_thread_id,
                    )
                except TelegramBadRequest:
                    pass
        await callback.answer("Пользователь разблокирован")

    @router.callback_query(is_admin, F.data.startswith("fb:publish:"))
    async def cb_publish_submission(callback: CallbackQuery, bot: Bot) -> None:
        if not callback.message:
            return
        try:
            await bot.copy_message(
                chat_id=settings.channel_id,
                from_chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=None,
            )
        except Exception as exc:
            await callback.answer(f"Ошибка публикации в канал: {exc}", show_alert=True)
            return

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass
        await callback.answer("✅ Опубликовано в канал!")

    return router
