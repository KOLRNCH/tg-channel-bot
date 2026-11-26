"""Admin panel handlers for editing the welcome post, button styles, and publishing."""

from __future__ import annotations

import html
from typing import Any

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.keyboards import (
    STYLE_BADGES,
    build_admin_main_kb,
    build_button_edit_kb,
    build_buttons_list_kb,
    build_cancel_kb,
    build_miniapp_accent_picker_kb,
    build_miniapp_btn_edit_kb,
    build_miniapp_menu_kb,
    build_miniapp_presets_kb,
    build_photo_menu_kb,
    build_style_picker_kb,
    is_valid_button_url,
)
from app.miniapp_config import (
    MINIAPP_PRESETS,
    MiniAppButton,
    MiniAppConfig,
    MiniAppConfigStore,
    push_miniapp_config_to_github,
)
from app.post_config import ButtonConfig, ButtonStyleName, PostConfig, PostConfigStore, VALID_STYLES
from app.publisher import PostTypeMismatchError, send_welcome_post, update_published_post
from app.settings import Settings


class AdminState(StatesGroup):
    """FSM states for interactive admin editing in private chat."""

    waiting_post_text = State()
    waiting_feedback_text = State()
    waiting_photo = State()
    waiting_emoji_inspect = State()
    adding_btn_text = State()
    adding_btn_url = State()
    adding_btn_row = State()
    adding_btn_style = State()
    adding_miniapp_name = State()
    editing_btn_text = State()
    editing_btn_url = State()
    editing_btn_row = State()
    editing_btn_emoji = State()
    adding_ma_title = State()
    adding_ma_url = State()
    editing_ma_title = State()
    editing_ma_subtitle = State()
    editing_ma_btn_title = State()
    editing_ma_btn_sub = State()
    editing_ma_btn_url = State()


def create_admin_router(
    settings: Settings,
    store: PostConfigStore,
    miniapp_store: MiniAppConfigStore | None = None,
) -> Router:
    """Create the admin router restricted to configured `ADMIN_IDS`."""
    router = Router(name="admin")
    admin_filter = F.from_user.id.in_(settings.admin_ids)
    ma_store = miniapp_store or MiniAppConfigStore(settings.miniapp_config_path)

    def _admin_summary_text(config: PostConfig) -> str:
        status = (
            f"Опубликован (ID: <code>{config.published_message_id}</code> в "
            f"<code>{html.escape(str(config.published_channel_id))}</code>)"
            if config.published_message_id
            else "Ещё не опубликован"
        )
        photo_state = "Да" if (config.photo_file_id or config.photo_path) else "Нет"
        return (
            "⚙️ <b>Панель управления каналом</b>\n\n"
            f"📢 <b>Канал:</b> <code>{html.escape(str(settings.channel_id))}</code>\n"
            f"📌 <b>Закреплённый пост:</b> {status}\n"
            f"🖼 <b>Обложка:</b> {photo_state}\n"
            f"🔘 <b>Кнопок:</b> {len(config.buttons)}"
        )

    def _button_details_text(btn: ButtonConfig) -> str:
        style_label = STYLE_BADGES.get(btn.normalized_style(), btn.style)
        emoji_label = f"<code>{btn.icon_custom_emoji_id}</code>" if btn.icon_custom_emoji_id else "нет"
        return (
            "🔘 <b>Настройка кнопки</b>\n\n"
            f"<b>Текст:</b> {html.escape(btn.text)}\n"
            f"<b>Ссылка:</b> <code>{html.escape(btn.url)}</code>\n"
            f"<b>Ряд:</b> {btn.row}\n"
            f"<b>Стиль:</b> {style_label}\n"
            f"<b>Кастом-эмодзи ID:</b> {emoji_label}"
        )

    async def _show_home(target: Message | CallbackQuery, config: PostConfig) -> None:
        text = _admin_summary_text(config)
        markup = build_admin_main_kb(config)
        if isinstance(target, CallbackQuery) and target.message:
            try:
                await target.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
                return
            except TelegramBadRequest:
                await target.message.answer(text, parse_mode="HTML", reply_markup=markup)
                return
        if isinstance(target, Message):
            await target.answer(text, parse_mode="HTML", reply_markup=markup)

    async def _show_buttons(target: Message | CallbackQuery, config: PostConfig) -> None:
        text = (
            "🔘 <b>Кнопки под постом</b>\n\n"
            "Кнопки с одинаковым номером ряда отображаются рядом в одной строке.\n"
            "Нажмите на любую кнопку ниже, чтобы изменить ссылку, текст, ряд или цветной стиль:"
        )
        markup = build_buttons_list_kb(config)
        if isinstance(target, CallbackQuery) and target.message:
            await target.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        elif isinstance(target, Message):
            await target.answer(text, parse_mode="HTML", reply_markup=markup)

    async def _show_miniapp_menu(target: Message | CallbackQuery, config: MiniAppConfig) -> None:
        sync_note = (
            f"Автодеплой в <code>{html.escape(settings.github_repo)}</code> включён ✅"
            if settings.github_token
            else "Автодеплой на GitHub: добавьте <code>GITHUB_TOKEN</code> в <code>.env</code> (пока сохраняет локально в <code>docs/config.json</code>)"
        )
        text = (
            "🌐 <b>Управление Mini App-визиткой</b>\n\n"
            f"<b>Заголовок:</b> {html.escape(config.brandTitle)}\n"
            f"<b>Кнопок:</b> {len(config.buttons)}\n"
            f"{sync_note}\n\n"
            "<i>Нажмите на кнопку для настройки или добавьте новую:</i>"
        )
        markup = build_miniapp_menu_kb(config, has_github_token=bool(settings.github_token))
        if isinstance(target, CallbackQuery) and target.message:
            await target.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        elif isinstance(target, Message):
            await target.answer(text, parse_mode="HTML", reply_markup=markup)

    def _miniapp_btn_details(btn: MiniAppButton) -> str:
        shape_name = "⭐ Угловая звёздочка" if btn.shape == "starburst" else "▬ Капсула"
        return (
            "✨ <b>Кнопка Mini App</b>\n\n"
            f"<b>Название:</b> {html.escape(btn.title)}\n"
            f"<b>Подпись:</b> {html.escape(btn.subtitle or '—')}\n"
            f"<b>Ссылка:</b> <code>{html.escape(btn.url)}</code>\n"
            f"<b>Форма:</b> {shape_name}\n"
            f"<b>Акцент:</b> <code>{html.escape(btn.accent)}</code>"
        )

    @router.message(Command("id"))
    async def cmd_id(message: Message) -> None:
        """Show current chat ID, topic thread ID (if any), and sender user ID for easy setup."""
        parts = [
            f"💬 <b>Chat ID:</b> <code>{message.chat.id}</code>",
            f"👤 <b>Ваш User ID:</b> <code>{message.from_user.id if message.from_user else 'unknown'}</code>",
        ]
        if message.message_thread_id:
            parts.append(f"🧵 <b>Topic Thread ID:</b> <code>{message.message_thread_id}</code>")
        await message.reply("\n".join(parts), parse_mode="HTML")

    @router.message(admin_filter, F.chat.type == ChatType.PRIVATE, Command("admin", "panel"))
    async def cmd_admin(message: Message, state: FSMContext) -> None:
        await state.clear()
        await _show_home(message, store.load())

    @router.message(admin_filter, F.chat.type == ChatType.PRIVATE, Command("cancel"))
    async def cmd_cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Действие отменено.")
        await _show_home(message, store.load())

    @router.callback_query(admin_filter, F.data == "adm:home")
    async def cb_home(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await _show_home(callback, store.load())
        await callback.answer()

    @router.callback_query(admin_filter, F.data == "adm:cancel")
    async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await _show_home(callback, store.load())
        await callback.answer("Отменено")

    @router.callback_query(admin_filter, F.data == "adm:preview")
    async def cb_preview(callback: CallbackQuery, bot: Bot) -> None:
        if not callback.message:
            return
        config = store.load()
        me = await bot.get_me()
        await send_welcome_post(
            bot=bot,
            chat_id=callback.message.chat.id,
            config=config,
            bot_username=me.username,
            pin=False,
        )
        await callback.answer("Предпросмотр отправлен")

    @router.callback_query(admin_filter, F.data == "adm:edit_text")
    async def cb_edit_text(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(AdminState.waiting_post_text)
        if callback.message:
            await callback.message.edit_text(
                "✏️ <b>Отправьте новый текст приветственного поста.</b>\n\n"
                "Можно использовать встроенное форматирование Telegram (жирный, курсив, цитаты, ссылки, премиум-эмодзи) — оно сохранится автоматически.",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.waiting_post_text, F.text)
    async def msg_new_post_text(message: Message, state: FSMContext) -> None:
        config = store.load()
        config.text_html = message.html_text
        store.save(config)
        await state.clear()
        await message.answer("✅ Текст приветствия обновлён!")
        await _show_home(message, config)

    @router.callback_query(admin_filter, F.data == "adm:edit_feedback_text")
    async def cb_edit_feedback_text(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(AdminState.waiting_feedback_text)
        if callback.message:
            await callback.message.edit_text(
                "📩 <b>Отправьте новый текст приветствия предложки.</b>\n\n"
                "Его видят подписчики, когда нажимают на кнопку «Предложка» и запускают бота.",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.waiting_feedback_text, F.text)
    async def msg_new_feedback_text(message: Message, state: FSMContext) -> None:
        config = store.load()
        config.feedback_greeting_html = message.html_text
        store.save(config)
        await state.clear()
        await message.answer("✅ Приветствие предложки обновлено!")
        await _show_home(message, config)

    @router.callback_query(admin_filter, F.data == "adm:edit_photo")
    async def cb_edit_photo(callback: CallbackQuery) -> None:
        config = store.load()
        has_photo = bool(config.photo_file_id or config.photo_path)
        if callback.message:
            await callback.message.edit_text(
                "🖼 <b>Обложка приветственного поста</b>\n\n"
                "Вы можете прикрепить баннер к посту или оставить пост чисто текстовым.",
                parse_mode="HTML",
                reply_markup=build_photo_menu_kb(has_photo),
            )
        await callback.answer()

    @router.callback_query(admin_filter, F.data == "adm:photo_upload")
    async def cb_photo_upload(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(AdminState.waiting_photo)
        if callback.message:
            await callback.message.edit_text(
                "📤 <b>Отправьте картинку (как фото, не файлом)</b> для обложки поста.",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.waiting_photo, F.photo)
    async def msg_photo_received(message: Message, state: FSMContext) -> None:
        assert message.photo
        config = store.load()
        config.photo_file_id = message.photo[-1].file_id
        config.photo_path = None
        store.save(config)
        await state.clear()
        await message.answer("✅ Обложка сохранена!")
        await _show_home(message, config)

    @router.callback_query(admin_filter, F.data == "adm:photo_clear")
    async def cb_photo_clear(callback: CallbackQuery) -> None:
        config = store.load()
        config.photo_file_id = None
        config.photo_path = None
        store.save(config)
        await _show_home(callback, config)
        await callback.answer("Обложка удалена")

    @router.callback_query(admin_filter, F.data == "adm:emoji_id")
    async def cb_emoji_id(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(AdminState.waiting_emoji_inspect)
        if callback.message:
            await callback.message.edit_text(
                "🧩 <b>Узнать ID кастомного эмодзи</b>\n\n"
                "Пришлите сюда сообщение с нужным кастомным (премиум) эмодзи — я верну его числовой ID для кнопок.\n"
                "<i>Примечание Telegram: на кнопках в канале иконка из кастом-эмодзи отображается, если у бота есть коллекционный юзернейм с Fragment (либо в чатах с ботом при наличии Premium).</i>",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.waiting_emoji_inspect, F.text)
    async def msg_emoji_inspect(message: Message, state: FSMContext) -> None:
        ids = [
            entity.custom_emoji_id
            for entity in (message.entities or [])
            if entity.type == "custom_emoji" and entity.custom_emoji_id
        ]
        if not ids:
            await message.answer(
                "В этом сообщении не найдено кастомных эмодзи. Отправьте премиум-эмодзи из набора или нажмите «Отмена».",
                reply_markup=build_cancel_kb(),
            )
            return
        lines = "\n".join(f"• <code>{eid}</code>" for eid in ids)
        await state.clear()
        await message.answer(f"🧩 <b>Найденные ID:</b>\n{lines}", parse_mode="HTML")
        await _show_home(message, store.load())

    @router.callback_query(admin_filter, F.data == "adm:buttons")
    async def cb_buttons(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await _show_buttons(callback, store.load())
        await callback.answer()

    @router.callback_query(admin_filter, F.data.startswith("adm:btn:"))
    async def cb_button_detail(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        button_id = callback.data.split(":", 2)[2]
        config = store.load()
        btn = config.find_button(button_id)
        if not btn:
            await callback.answer("Кнопка не найдена", show_alert=True)
            await _show_buttons(callback, config)
            return
        if callback.message:
            await callback.message.edit_text(
                _button_details_text(btn),
                parse_mode="HTML",
                reply_markup=build_button_edit_kb(btn),
            )
        await callback.answer()

    @router.callback_query(admin_filter, F.data == "adm:btn_add_miniapp")
    async def cb_btn_add_miniapp(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(AdminState.adding_miniapp_name)
        if callback.message:
            await callback.message.edit_text(
                "✨ <b>Кнопка для Mini App-визитки</b>\n\n"
                "Отправьте <b>короткое имя приложения</b> из <code>@BotFather</code> (команда <code>/newapp</code>, например <code>menu</code>) "
                "или готовую ссылку вида <code>https://t.me/your_bot/menu</code>:",
                parse_mode="HTML",
                reply_markup=build_cancel_kb("adm:buttons"),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.adding_miniapp_name, F.text)
    async def msg_add_miniapp_name(message: Message, state: FSMContext) -> None:
        raw = message.text.strip().lstrip("/")
        if raw.startswith(("http://", "https://", "tg://")):
            if not is_valid_button_url(raw):
                await message.answer(
                    "⚠️ Некорректная ссылка. Введите короткое имя (например <code>menu</code>) или URL <code>https://t.me/...</code>:",
                    parse_mode="HTML",
                    reply_markup=build_cancel_kb("adm:buttons"),
                )
                return
            url = raw
        elif raw.replace("_", "").isalnum():
            url = f"https://t.me/{{bot_username}}/{raw}"
        else:
            await message.answer(
                "⚠️ Короткое имя Mini App должно содержать только латиницу, цифры или <code>_</code> (например <code>menu</code>).",
                parse_mode="HTML",
                reply_markup=build_cancel_kb("adm:buttons"),
            )
            return

        config = store.load()
        config.add_button(
            text="✨ Меню и ссылки",
            url=url,
            style="primary",
        )
        store.save(config)
        await state.clear()
        await message.answer("✅ Кнопка Mini App добавлена! Нажмите на неё в списке, если хотите поменять текст, ряд или цвет.")
        await _show_buttons(message, config)

    @router.callback_query(admin_filter, F.data == "adm:btn_add")
    async def cb_btn_add(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(AdminState.adding_btn_text)
        if callback.message:
            await callback.message.edit_text(
                "➕ <b>Новая кнопка — Шаг 1/4</b>\n\nВведите текст кнопки (например: <code>🎵 TikTok</code>):",
                parse_mode="HTML",
                reply_markup=build_cancel_kb("adm:buttons"),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.adding_btn_text, F.text)
    async def msg_add_btn_text(message: Message, state: FSMContext) -> None:
        await state.update_data(new_btn_text=message.text.strip())
        await state.set_state(AdminState.adding_btn_url)
        await message.answer(
            "➕ <b>Шаг 2/4</b> — отправьте ссылку для кнопки (например <code>https://...</code> или <code>https://t.me/{bot_username}?start=suggest</code>):",
            parse_mode="HTML",
            reply_markup=build_cancel_kb("adm:buttons"),
        )

    @router.message(admin_filter, AdminState.adding_btn_url, F.text)
    async def msg_add_btn_url(message: Message, state: FSMContext) -> None:
        url = message.text.strip()
        if not is_valid_button_url(url):
            await message.answer(
                "⚠️ Ссылка должна начинаться с <code>https://</code>, <code>http://</code> или <code>tg://</code>. Попробуйте ещё раз:",
                parse_mode="HTML",
                reply_markup=build_cancel_kb("adm:buttons"),
            )
            return
        config = store.load()
        await state.update_data(new_btn_url=url)
        await state.set_state(AdminState.adding_btn_row)
        await message.answer(
            f"➕ <b>Шаг 3/4</b> — введите номер ряда (число, например <code>1</code>, чтобы поставить рядом с уже существующими, или <code>{config.next_row_number()}</code> для нового ряда):",
            parse_mode="HTML",
            reply_markup=build_cancel_kb("adm:buttons"),
        )

    @router.message(admin_filter, AdminState.adding_btn_row, F.text)
    async def msg_add_btn_row(message: Message, state: FSMContext) -> None:
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 1:
            await message.answer(
                "⚠️ Введите целое число больше 0 (например `1`, `2`, `3`).",
                reply_markup=build_cancel_kb("adm:buttons"),
            )
            return
        await state.update_data(new_btn_row=int(raw))
        await state.set_state(AdminState.adding_btn_style)
        await message.answer(
            "➕ <b>Шаг 4/4</b> — выберите цветной стиль кнопки:",
            parse_mode="HTML",
            reply_markup=build_style_picker_kb("adm:newstyle", "adm:buttons"),
        )

    @router.callback_query(admin_filter, AdminState.adding_btn_style, F.data.startswith("adm:newstyle:"))
    async def cb_add_btn_style(callback: CallbackQuery, state: FSMContext) -> None:
        style_raw = callback.data.split(":", 2)[2]
        style: ButtonStyleName = style_raw if style_raw in VALID_STYLES else "default"  # type: ignore[assignment]
        data: dict[str, Any] = await state.get_data()
        config = store.load()
        config.add_button(
            text=data["new_btn_text"],
            url=data["new_btn_url"],
            row=data["new_btn_row"],
            style=style,
        )
        store.save(config)
        await state.clear()
        await _show_buttons(callback, config)
        await callback.answer("Кнопка добавлена!")

    @router.callback_query(admin_filter, F.data.startswith("adm:btn_style_menu:"))
    async def cb_btn_style_menu(callback: CallbackQuery) -> None:
        button_id = callback.data.split(":", 2)[2]
        if callback.message:
            await callback.message.edit_text(
                "🎨 <b>Выберите стиль цвета кнопки:</b>",
                parse_mode="HTML",
                reply_markup=build_style_picker_kb(
                    f"adm:setstyle:{button_id}",
                    f"adm:btn:{button_id}",
                ),
            )
        await callback.answer()

    @router.callback_query(admin_filter, F.data.startswith("adm:setstyle:"))
    async def cb_btn_set_style(callback: CallbackQuery) -> None:
        _, _, button_id, style_raw = callback.data.split(":", 3)
        config = store.load()
        btn = config.find_button(button_id)
        if not btn:
            await callback.answer("Кнопка не найдена", show_alert=True)
            return
        btn.style = style_raw if style_raw in VALID_STYLES else "default"  # type: ignore[assignment]
        store.save(config)
        if callback.message:
            await callback.message.edit_text(
                _button_details_text(btn),
                parse_mode="HTML",
                reply_markup=build_button_edit_kb(btn),
            )
        await callback.answer("Стиль обновлён")

    @router.callback_query(admin_filter, F.data.startswith("adm:btn_text:"))
    async def cb_btn_edit_text(callback: CallbackQuery, state: FSMContext) -> None:
        button_id = callback.data.split(":", 2)[2]
        await state.set_state(AdminState.editing_btn_text)
        await state.update_data(edit_btn_id=button_id)
        if callback.message:
            await callback.message.edit_text(
                "✏️ Отправьте новый текст для кнопки:",
                reply_markup=build_cancel_kb(f"adm:btn:{button_id}"),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.editing_btn_text, F.text)
    async def msg_btn_edit_text(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        button_id = data["edit_btn_id"]
        config = store.load()
        btn = config.find_button(button_id)
        if btn:
            btn.text = message.text.strip()
            store.save(config)
        await state.clear()
        if btn:
            await message.answer(
                _button_details_text(btn),
                parse_mode="HTML",
                reply_markup=build_button_edit_kb(btn),
            )

    @router.callback_query(admin_filter, F.data.startswith("adm:btn_url:"))
    async def cb_btn_edit_url(callback: CallbackQuery, state: FSMContext) -> None:
        button_id = callback.data.split(":", 2)[2]
        await state.set_state(AdminState.editing_btn_url)
        await state.update_data(edit_btn_id=button_id)
        if callback.message:
            await callback.message.edit_text(
                "🔗 Отправьте новую ссылку (<code>https://...</code> или <code>tg://...</code>):",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(f"adm:btn:{button_id}"),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.editing_btn_url, F.text)
    async def msg_btn_edit_url(message: Message, state: FSMContext) -> None:
        url = message.text.strip()
        data = await state.get_data()
        button_id = data["edit_btn_id"]
        if not is_valid_button_url(url):
            await message.answer(
                "⚠️ Некорректная ссылка. Укажите URL вида <code>https://...</code>",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(f"adm:btn:{button_id}"),
            )
            return
        config = store.load()
        btn = config.find_button(button_id)
        if btn:
            btn.url = url
            store.save(config)
        await state.clear()
        if btn:
            await message.answer(
                _button_details_text(btn),
                parse_mode="HTML",
                reply_markup=build_button_edit_kb(btn),
            )

    @router.callback_query(admin_filter, F.data.startswith("adm:btn_row:"))
    async def cb_btn_edit_row(callback: CallbackQuery, state: FSMContext) -> None:
        button_id = callback.data.split(":", 2)[2]
        await state.set_state(AdminState.editing_btn_row)
        await state.update_data(edit_btn_id=button_id)
        if callback.message:
            await callback.message.edit_text(
                "📐 Введите новый номер ряда (целое число ≥ 1):",
                reply_markup=build_cancel_kb(f"adm:btn:{button_id}"),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.editing_btn_row, F.text)
    async def msg_btn_edit_row(message: Message, state: FSMContext) -> None:
        raw = message.text.strip()
        data = await state.get_data()
        button_id = data["edit_btn_id"]
        if not raw.isdigit() or int(raw) < 1:
            await message.answer(
                "⚠️ Введите число от 1 и выше.",
                reply_markup=build_cancel_kb(f"adm:btn:{button_id}"),
            )
            return
        config = store.load()
        btn = config.find_button(button_id)
        if btn:
            btn.row = int(raw)
            store.save(config)
        await state.clear()
        if btn:
            await message.answer(
                _button_details_text(btn),
                parse_mode="HTML",
                reply_markup=build_button_edit_kb(btn),
            )

    @router.callback_query(admin_filter, F.data.startswith("adm:btn_emoji:"))
    async def cb_btn_edit_emoji(callback: CallbackQuery, state: FSMContext) -> None:
        button_id = callback.data.split(":", 2)[2]
        await state.set_state(AdminState.editing_btn_emoji)
        await state.update_data(edit_btn_id=button_id)
        if callback.message:
            await callback.message.edit_text(
                "🧩 Пришлите <b>кастомный эмодзи</b>, его числовой ID, или слово <code>удалить</code> для сброса иконки:",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(f"adm:btn:{button_id}"),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.editing_btn_emoji, F.text)
    async def msg_btn_edit_emoji(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        button_id = data["edit_btn_id"]
        raw = message.text.strip()
        config = store.load()
        btn = config.find_button(button_id)
        if not btn:
            await state.clear()
            return

        custom_ids = [
            e.custom_emoji_id
            for e in (message.entities or [])
            if e.type == "custom_emoji" and e.custom_emoji_id
        ]
        if raw.lower() in {"удалить", "нет", "clear", "none", "-"}:
            btn.icon_custom_emoji_id = None
        elif custom_ids:
            btn.icon_custom_emoji_id = custom_ids[0]
        elif raw.isdigit():
            btn.icon_custom_emoji_id = raw
        else:
            await message.answer(
                "⚠️ Отправьте кастомный эмодзи, его числовой ID или напишите <code>удалить</code>.",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(f"adm:btn:{button_id}"),
            )
            return

        store.save(config)
        await state.clear()
        await message.answer(
            _button_details_text(btn),
            parse_mode="HTML",
            reply_markup=build_button_edit_kb(btn),
        )

    @router.callback_query(admin_filter, F.data.startswith("adm:btn_up:"))
    async def cb_btn_up(callback: CallbackQuery) -> None:
        button_id = callback.data.split(":", 2)[2]
        config = store.load()
        moved = config.move_button(button_id, -1)
        if moved:
            store.save(config)
        btn = config.find_button(button_id)
        if btn and moved and callback.message:
            await callback.message.edit_text(
                _button_details_text(btn),
                parse_mode="HTML",
                reply_markup=build_button_edit_kb(btn),
            )
        await callback.answer("Перемещено" if moved else "Уже первая")

    @router.callback_query(admin_filter, F.data.startswith("adm:btn_down:"))
    async def cb_btn_down(callback: CallbackQuery) -> None:
        button_id = callback.data.split(":", 2)[2]
        config = store.load()
        moved = config.move_button(button_id, 1)
        if moved:
            store.save(config)
        btn = config.find_button(button_id)
        if btn and moved and callback.message:
            await callback.message.edit_text(
                _button_details_text(btn),
                parse_mode="HTML",
                reply_markup=build_button_edit_kb(btn),
            )
        await callback.answer("Перемещено" if moved else "Уже последняя")

    @router.callback_query(admin_filter, F.data.startswith("adm:btn_del:"))
    async def cb_btn_del(callback: CallbackQuery) -> None:
        button_id = callback.data.split(":", 2)[2]
        config = store.load()
        removed = config.remove_button(button_id)
        if removed:
            store.save(config)
        await _show_buttons(callback, config)
        await callback.answer("Кнопка удалена" if removed else "Кнопка не найдена")

    @router.callback_query(admin_filter, F.data == "adm:publish_new")
    async def cb_publish_new(callback: CallbackQuery, bot: Bot) -> None:
        config = store.load()
        me = await bot.get_me()
        try:
            result = await send_welcome_post(
                bot=bot,
                chat_id=settings.channel_id,
                config=config,
                bot_username=me.username,
                pin=True,
            )
        except Exception as exc:
            await callback.answer(f"Ошибка публикации: {exc}", show_alert=True)
            return

        config.published_channel_id = settings.channel_id
        config.published_message_id = result.message_id
        config.published_has_media = bool(config.photo_file_id or config.photo_path)
        store.save(config)

        await _show_home(callback, config)
        note = result.pin_warning or "Пост опубликован и закреплён в канале!"
        await callback.answer(note, show_alert=bool(result.pin_warning))

    @router.callback_query(admin_filter, F.data == "adm:update_published")
    async def cb_update_published(callback: CallbackQuery, bot: Bot) -> None:
        config = store.load()
        me = await bot.get_me()
        try:
            await update_published_post(bot=bot, config=config, bot_username=me.username)
        except PostTypeMismatchError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        except Exception as exc:
            await callback.answer(f"Не удалось обновить пост: {exc}", show_alert=True)
            return

        store.save(config)
        await callback.answer("✅ Закреплённый пост в канале обновлён!")

    # --- Mini App button & header manager (docs/config.json) ---

    @router.callback_query(admin_filter, F.data == "adm:miniapp")
    async def cb_miniapp_menu(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await _show_miniapp_menu(callback, ma_store.load())
        await callback.answer()

    @router.callback_query(admin_filter, F.data == "adm:ma_text")
    async def cb_ma_text(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(AdminState.editing_ma_title)
        if callback.message:
            await callback.message.edit_text(
                "✏️ <b>Заголовок Mini App</b>\n\nОтправьте новый заголовок карточки (например <code>Мой Хаб</code>):",
                parse_mode="HTML",
                reply_markup=build_cancel_kb("adm:miniapp"),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.editing_ma_title, F.text)
    async def msg_ma_title(message: Message, state: FSMContext) -> None:
        config = ma_store.load()
        config.brandTitle = message.text.strip()
        ma_store.save(config)
        await state.set_state(AdminState.editing_ma_subtitle)
        await message.answer(
            "📝 Теперь отправьте описание под заголовком (или точку <code>.</code>, чтобы оставить текущее):",
            parse_mode="HTML",
            reply_markup=build_cancel_kb("adm:miniapp"),
        )

    @router.message(admin_filter, AdminState.editing_ma_subtitle, F.text)
    async def msg_ma_subtitle(message: Message, state: FSMContext) -> None:
        config = ma_store.load()
        if message.text.strip() != ".":
            config.subtitle = message.text.strip()
            ma_store.save(config)
        await state.clear()
        await message.answer("✅ Шапка Mini App обновлена!")
        await _show_miniapp_menu(message, config)

    @router.callback_query(admin_filter, F.data == "adm:ma_add")
    async def cb_ma_add(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        if callback.message:
            await callback.message.edit_text(
                "➕ <b>Добавить кнопку в Mini App</b>\n\nВыберите площадку (подставим иконку и цвет автоматически) или «Своя кнопка»:",
                parse_mode="HTML",
                reply_markup=build_miniapp_presets_kb(),
            )
        await callback.answer()

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_preset:"))
    async def cb_ma_preset(callback: CallbackQuery, state: FSMContext) -> None:
        preset_key = callback.data.split(":", 2)[2]
        preset = MINIAPP_PRESETS.get(preset_key, MINIAPP_PRESETS["custom"])
        await state.update_data(ma_preset_key=preset_key)
        if preset_key == "custom":
            await state.set_state(AdminState.adding_ma_title)
            if callback.message:
                await callback.message.edit_text(
                    "➕ Введите название новой кнопки (например <code>Мой Steam</code>):",
                    parse_mode="HTML",
                    reply_markup=build_cancel_kb("adm:miniapp"),
                )
        else:
            await state.update_data(ma_new_title=preset["title"])
            await state.set_state(AdminState.adding_ma_url)
            if callback.message:
                await callback.message.edit_text(
                    f"➕ <b>Кнопка «{html.escape(preset['title'])}»</b>\n\n"
                    f"Отправьте ссылку (например <code>{html.escape(preset['url_hint'])}</code>):",
                    parse_mode="HTML",
                    reply_markup=build_cancel_kb("adm:miniapp"),
                )
        await callback.answer()

    @router.message(admin_filter, AdminState.adding_ma_title, F.text)
    async def msg_ma_add_title(message: Message, state: FSMContext) -> None:
        await state.update_data(ma_new_title=message.text.strip())
        await state.set_state(AdminState.adding_ma_url)
        await message.answer(
            "🔗 Отправьте ссылку для новой кнопки (<code>https://...</code> или <code>tg://...</code>):",
            parse_mode="HTML",
            reply_markup=build_cancel_kb("adm:miniapp"),
        )

    @router.message(admin_filter, AdminState.adding_ma_url, F.text)
    async def msg_ma_add_url(message: Message, state: FSMContext, bot: Bot) -> None:
        raw_url = message.text.strip()
        if not is_valid_button_url(raw_url):
            await message.answer(
                "⚠️ Ссылка должна начинаться с <code>https://</code>, <code>http://</code> или <code>tg://</code>:",
                parse_mode="HTML",
                reply_markup=build_cancel_kb("adm:miniapp"),
            )
            return

        data = await state.get_data()
        preset = MINIAPP_PRESETS.get(data.get("ma_preset_key", "custom"), MINIAPP_PRESETS["custom"])
        me = await bot.get_me()
        resolved_url = raw_url.replace("{bot_username}", (me.username or "your_bot").lstrip("@"))

        config = ma_store.load()
        btn = config.add_button(
            title=data.get("ma_new_title") or preset["title"],
            subtitle=preset["subtitle"],
            url=resolved_url,
            icon=preset["icon"],
            variant=preset["variant"],
            accent=preset["accent"],
            shape=preset["shape"],
        )
        ma_store.save(config)
        await state.clear()
        await message.answer(
            f"✅ Кнопка <b>{html.escape(btn.title)}</b> добавлена! Не забудьте нажать «🚀 Обновить сайт на GitHub».",
            parse_mode="HTML",
        )
        await _show_miniapp_menu(message, config)

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_btn:"))
    async def cb_ma_btn_detail(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        button_id = callback.data.split(":", 2)[2]
        config = ma_store.load()
        btn = config.find_button(button_id)
        if not btn:
            await callback.answer("Кнопка не найдена", show_alert=True)
            await _show_miniapp_menu(callback, config)
            return
        if callback.message:
            await callback.message.edit_text(
                _miniapp_btn_details(btn),
                parse_mode="HTML",
                reply_markup=build_miniapp_btn_edit_kb(btn),
            )
        await callback.answer()

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_btn_title:"))
    async def cb_ma_btn_title(callback: CallbackQuery, state: FSMContext) -> None:
        button_id = callback.data.split(":", 2)[2]
        await state.set_state(AdminState.editing_ma_btn_title)
        await state.update_data(edit_ma_btn_id=button_id)
        if callback.message:
            await callback.message.edit_text(
                "✏️ Введите новое название кнопки:",
                reply_markup=build_cancel_kb(f"adm:ma_btn:{button_id}"),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.editing_ma_btn_title, F.text)
    async def msg_ma_btn_title(message: Message, state: FSMContext) -> None:
        button_id = (await state.get_data())["edit_ma_btn_id"]
        config = ma_store.load()
        btn = config.find_button(button_id)
        if btn:
            btn.title = message.text.strip()
            ma_store.save(config)
        await state.clear()
        if btn:
            await message.answer(
                _miniapp_btn_details(btn),
                parse_mode="HTML",
                reply_markup=build_miniapp_btn_edit_kb(btn),
            )

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_btn_sub:"))
    async def cb_ma_btn_sub(callback: CallbackQuery, state: FSMContext) -> None:
        button_id = callback.data.split(":", 2)[2]
        await state.set_state(AdminState.editing_ma_btn_sub)
        await state.update_data(edit_ma_btn_id=button_id)
        if callback.message:
            await callback.message.edit_text(
                "📝 Введите новую подпись под кнопкой (или <code>-</code> чтобы убрать):",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(f"adm:ma_btn:{button_id}"),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.editing_ma_btn_sub, F.text)
    async def msg_ma_btn_sub(message: Message, state: FSMContext) -> None:
        button_id = (await state.get_data())["edit_ma_btn_id"]
        config = ma_store.load()
        btn = config.find_button(button_id)
        if btn:
            val = message.text.strip()
            btn.subtitle = "" if val == "-" else val
            ma_store.save(config)
        await state.clear()
        if btn:
            await message.answer(
                _miniapp_btn_details(btn),
                parse_mode="HTML",
                reply_markup=build_miniapp_btn_edit_kb(btn),
            )

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_btn_url:"))
    async def cb_ma_btn_url(callback: CallbackQuery, state: FSMContext) -> None:
        button_id = callback.data.split(":", 2)[2]
        await state.set_state(AdminState.editing_ma_btn_url)
        await state.update_data(edit_ma_btn_id=button_id)
        if callback.message:
            await callback.message.edit_text(
                "🔗 Отправьте новую ссылку (<code>https://...</code> или <code>tg://...</code>):",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(f"adm:ma_btn:{button_id}"),
            )
        await callback.answer()

    @router.message(admin_filter, AdminState.editing_ma_btn_url, F.text)
    async def msg_ma_btn_url(message: Message, state: FSMContext) -> None:
        button_id = (await state.get_data())["edit_ma_btn_id"]
        url = message.text.strip()
        if not is_valid_button_url(url):
            await message.answer(
                "⚠️ Некорректная ссылка. Используйте <code>https://...</code> или <code>tg://...</code>:",
                parse_mode="HTML",
                reply_markup=build_cancel_kb(f"adm:ma_btn:{button_id}"),
            )
            return
        config = ma_store.load()
        btn = config.find_button(button_id)
        if btn:
            btn.url = url
            ma_store.save(config)
        await state.clear()
        if btn:
            await message.answer(
                _miniapp_btn_details(btn),
                parse_mode="HTML",
                reply_markup=build_miniapp_btn_edit_kb(btn),
            )

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_btn_shape:"))
    async def cb_ma_btn_shape(callback: CallbackQuery) -> None:
        button_id = callback.data.split(":", 2)[2]
        config = ma_store.load()
        btn = config.find_button(button_id)
        if not btn:
            await callback.answer("Не найдена", show_alert=True)
            return
        btn.shape = "starburst" if btn.shape != "starburst" else "pill"
        if btn.shape == "starburst" and btn.variant == "cyber-dither":
            btn.variant = "chrome-silver"
        elif btn.shape == "pill" and btn.variant == "chrome-silver":
            btn.variant = "cyber-dither"
        ma_store.save(config)
        if callback.message:
            await callback.message.edit_text(
                _miniapp_btn_details(btn),
                parse_mode="HTML",
                reply_markup=build_miniapp_btn_edit_kb(btn),
            )
        await callback.answer("Форма переключена")

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_btn_accent_menu:"))
    async def cb_ma_accent_menu(callback: CallbackQuery) -> None:
        button_id = callback.data.split(":", 2)[2]
        if callback.message:
            await callback.message.edit_text(
                "🎨 <b>Выберите цвет акцента площадки:</b>",
                parse_mode="HTML",
                reply_markup=build_miniapp_accent_picker_kb(button_id),
            )
        await callback.answer()

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_setaccent:"))
    async def cb_ma_setaccent(callback: CallbackQuery) -> None:
        _, _, button_id, accent = callback.data.split(":", 3)
        config = ma_store.load()
        btn = config.find_button(button_id)
        if btn:
            btn.accent = accent
            ma_store.save(config)
        if btn and callback.message:
            await callback.message.edit_text(
                _miniapp_btn_details(btn),
                parse_mode="HTML",
                reply_markup=build_miniapp_btn_edit_kb(btn),
            )
        await callback.answer("Акцент обновлён")

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_btn_up:"))
    async def cb_ma_btn_up(callback: CallbackQuery) -> None:
        button_id = callback.data.split(":", 2)[2]
        config = ma_store.load()
        moved = config.move_button(button_id, -1)
        if moved:
            ma_store.save(config)
        btn = config.find_button(button_id)
        if btn and moved and callback.message:
            await callback.message.edit_text(
                _miniapp_btn_details(btn),
                parse_mode="HTML",
                reply_markup=build_miniapp_btn_edit_kb(btn),
            )
        await callback.answer("Выше" if moved else "Уже первая")

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_btn_down:"))
    async def cb_ma_btn_down(callback: CallbackQuery) -> None:
        button_id = callback.data.split(":", 2)[2]
        config = ma_store.load()
        moved = config.move_button(button_id, 1)
        if moved:
            ma_store.save(config)
        btn = config.find_button(button_id)
        if btn and moved and callback.message:
            await callback.message.edit_text(
                _miniapp_btn_details(btn),
                parse_mode="HTML",
                reply_markup=build_miniapp_btn_edit_kb(btn),
            )
        await callback.answer("Ниже" if moved else "Уже последняя")

    @router.callback_query(admin_filter, F.data.startswith("adm:ma_btn_del:"))
    async def cb_ma_btn_del(callback: CallbackQuery) -> None:
        button_id = callback.data.split(":", 2)[2]
        config = ma_store.load()
        removed = config.remove_button(button_id)
        if removed:
            ma_store.save(config)
        await _show_miniapp_menu(callback, config)
        await callback.answer("Кнопка удалена" if removed else "Не найдена")

    @router.callback_query(admin_filter, F.data == "adm:ma_push")
    async def cb_ma_push(callback: CallbackQuery) -> None:
        config = ma_store.load()
        ma_store.save(config)
        if not settings.github_token:
            await callback.answer(
                "Сохранено локально в docs/config.json. Чтобы пушить прямо из бота, добавьте GITHUB_TOKEN в .env!",
                show_alert=True,
            )
            return
        try:
            commit_sha = await push_miniapp_config_to_github(
                config_path=settings.miniapp_config_path,
                github_token=settings.github_token,
                github_repo=settings.github_repo,
                branch=settings.github_branch,
            )
        except Exception as exc:
            await callback.answer(f"Ошибка отправки в GitHub: {exc}", show_alert=True)
            return
        await callback.answer(
            f"✅ Отправлено на GitHub ({commit_sha})! Сайт обновится через ~20–30 сек.",
            show_alert=True,
        )

    return router
