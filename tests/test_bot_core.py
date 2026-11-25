"""Unit tests for channel post configuration, styled keyboards, SQLite DB, and publisher."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import User

from app.db import Database
from app.handlers.feedback import format_topic_title, format_user_card
from app.keyboards import (
    build_channel_keyboard,
    build_miniapp_menu_kb,
    build_miniapp_presets_kb,
    is_valid_button_url,
    resolve_button_url,
)
from app.miniapp_config import MiniAppConfigStore
from app.post_config import ButtonConfig, PostConfig, PostConfigStore, create_default_post_config
from app.publisher import PostTypeMismatchError, send_welcome_post, update_published_post
from app.settings import load_settings, parse_admin_ids, parse_chat_id


def test_settings_parsers_and_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert parse_chat_id("@my_channel") == "@my_channel"
    assert parse_chat_id(" -1001234567890 ") == -1001234567890
    assert parse_admin_ids("111, 222, 111") == (111, 222)

    with pytest.raises(ValueError):
        parse_admin_ids("abc")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "BOT_TOKEN=999:real_token_here\n"
        "ADMIN_IDS=42,84\n"
        "CHANNEL_ID=@test_chan\n"
        "FEEDBACK_GROUP_ID=-100555666\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)
    monkeypatch.delenv("FEEDBACK_GROUP_ID", raising=False)

    settings = load_settings(tmp_path)
    assert settings.bot_token == "999:real_token_here"
    assert settings.admin_ids == (42, 84)
    assert settings.channel_id == "@test_chan"
    assert settings.feedback_group_id == -100555666


def test_post_config_roundtrip_and_button_mutations(tmp_path: Path) -> None:
    store = PostConfigStore(tmp_path / "post_config.json")
    cfg = store.load()
    assert [btn.id for btn in cfg.buttons] == ["youtube", "twitch", "tg_chat", "suggest"]

    added = cfg.add_button(
        text="Boosty",
        url="https://boosty.to/creator",
        row=2,
        style="primary",
        icon_custom_emoji_id="5432109876543210987",
    )
    assert added.row == 2
    assert cfg.move_button(added.id, -1) is True
    assert cfg.find_button(added.id) is not None
    store.save(cfg)

    reloaded = store.load()
    reloaded_btn = reloaded.find_button(added.id)
    assert reloaded_btn is not None
    assert reloaded_btn.style == "primary"
    assert reloaded_btn.icon_custom_emoji_id == "5432109876543210987"
    assert reloaded.remove_button(added.id) is True
    assert reloaded.find_button(added.id) is None


def test_styled_keyboard_builder_and_url_validation() -> None:
    cfg = create_default_post_config()
    cfg.buttons[1].icon_custom_emoji_id = "1234567890123456789"
    markup = build_channel_keyboard(cfg, bot_username="@my_creator_bot")
    assert markup is not None

    # Default layout: row 1 (YouTube + Twitch), row 2 (TG Chat), row 3 (Предложка)
    assert [len(row) for row in markup.inline_keyboard] == [2, 1, 1]

    yt_btn, twitch_btn = markup.inline_keyboard[0]
    chat_btn = markup.inline_keyboard[1][0]
    suggest_btn = markup.inline_keyboard[2][0]

    assert yt_btn.style == "danger"
    assert twitch_btn.style is None
    assert twitch_btn.icon_custom_emoji_id == "1234567890123456789"
    assert chat_btn.style == "primary"
    assert suggest_btn.style == "success"
    assert suggest_btn.url == "https://t.me/my_creator_bot?start=suggest"

    assert resolve_button_url("https://t.me/{bot_username}?start=1", "test_bot") == (
        "https://t.me/test_bot?start=1"
    )
    assert resolve_button_url("https://t.me/{bot_username}/menu", "test_bot") == (
        "https://t.me/test_bot/menu"
    )
    assert is_valid_button_url("https://youtube.com/@demo")
    assert is_valid_button_url("tg://resolve?domain=demo&direct")
    assert not is_valid_button_url("ftp://invalid.example")
    assert not is_valid_button_url("not a url")


def test_miniapp_config_json_valid() -> None:
    import json

    cfg_path = Path(__file__).resolve().parent.parent / "docs" / "config.json"
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert data["brandTitle"]
    assert data["coverMode"] == "dither-star"
    assert len(data["buttons"]) == 4
    assert any(btn["shape"] == "starburst" for btn in data["buttons"])
    assert all(btn["variant"] in {"cyber-dither", "chrome-silver"} for btn in data["buttons"])
    assert all(is_valid_button_url(btn["url"]) for btn in data["buttons"])


def test_miniapp_store_add_move_delete(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    store = MiniAppConfigStore(cfg_path)
    cfg = store.load()
    added = cfg.add_button(
        title="Discord",
        subtitle="Голосовой сервер",
        url="https://discord.gg/demo",
        icon="discord",
        accent="discord",
    )
    assert cfg.find_button(added.id) is not None
    cfg.add_button(title="Boosty", url="https://boosty.to/demo", icon="donate", accent="donate")
    assert cfg.move_button(added.id, 1) is True
    store.save(cfg)

    reloaded = store.load()
    assert [b.title for b in reloaded.buttons] == ["Boosty", "Discord"]
    assert len(build_miniapp_menu_kb(reloaded, has_github_token=True).inline_keyboard) == 5
    assert len(build_miniapp_presets_kb().inline_keyboard) >= 5
    assert reloaded.remove_button(added.id) is True


async def test_database_topic_and_dm_mappings(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.db")
    await db.connect()
    try:
        topic = await db.upsert_topic(
            user_id=1001,
            topic_thread_id=77,
            username="alice",
            full_name="Alice",
        )
        assert topic.topic_thread_id == 77
        assert (await db.get_topic_by_thread(77)).user_id == 1001  # type: ignore[union-attr]

        assert await db.is_user_banned(1001) is False
        await db.set_user_banned(1001, True)
        assert await db.is_user_banned(1001) is True
        await db.set_user_banned(1001, False)
        assert await db.is_user_banned(1001) is False

        await db.save_dm_link(admin_message_id=505, user_id=1001)
        assert await db.get_user_by_dm(505) == 1001
        assert await db.get_user_by_dm(999) is None
    finally:
        await db.close()


async def test_publisher_send_pin_and_update() -> None:
    bot = AsyncMock()
    bot.send_message.return_value = SimpleNamespace(message_id=321)

    cfg = PostConfig(
        text_html="<b>Привет!</b>",
        buttons=[ButtonConfig(id="yt", text="YouTube", url="https://youtube.com", row=1, style="danger")],
    )
    res = await send_welcome_post(bot, "@chan", cfg, "demo_bot", pin=True)
    assert res.message_id == 321
    assert res.pinned is True
    bot.pin_chat_message.assert_awaited_once_with(
        chat_id="@chan",
        message_id=321,
        disable_notification=True,
    )

    cfg.published_channel_id = "@chan"
    cfg.published_message_id = res.message_id
    cfg.published_has_media = False
    await update_published_post(bot, cfg, "demo_bot")
    bot.edit_message_text.assert_awaited_once()

    # Switching text-only published post to photo must raise explicit guidance
    cfg.photo_file_id = "AgACAgIAAxkBAA..."
    with pytest.raises(PostTypeMismatchError):
        await update_published_post(bot, cfg, "demo_bot")


def test_feedback_topic_formatting() -> None:
    user = User(id=555, is_bot=False, first_name="Макс", last_name="<Stream>", username="max_tv")
    assert format_topic_title(user) == "Макс <Stream> (@max_tv) • 555"
    card = format_user_card(user)
    assert "&lt;Stream&gt;" in card
    assert "@max_tv" in card
    assert "<code>555</code>" in card
