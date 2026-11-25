"""Mini App JSON configuration store and optional GitHub Pages publisher."""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import aiohttp

MINIAPP_PRESETS: dict[str, dict[str, str]] = {
    "youtube": {
        "title": "YouTube",
        "subtitle": "Видео и нарезки",
        "icon": "youtube",
        "variant": "cyber-dither",
        "accent": "youtube",
        "shape": "pill",
        "url_hint": "https://www.youtube.com/@your_channel",
    },
    "twitch": {
        "title": "Twitch",
        "subtitle": "Прямые эфиры",
        "icon": "twitch",
        "variant": "cyber-dither",
        "accent": "twitch",
        "shape": "pill",
        "url_hint": "https://www.twitch.tv/your_channel",
    },
    "telegram": {
        "title": "Чат в ТГ",
        "subtitle": "Комьюнити и мемы",
        "icon": "telegram",
        "variant": "cyber-dither",
        "accent": "telegram",
        "shape": "pill",
        "url_hint": "https://t.me/your_chat",
    },
    "suggest": {
        "title": "ПРЕДЛОЖКА",
        "subtitle": "Личный чат",
        "icon": "suggest",
        "variant": "chrome-silver",
        "accent": "emerald",
        "shape": "starburst",
        "url_hint": "https://t.me/{bot_username}?start=suggest",
    },
    "donate": {
        "title": "Поддержать",
        "subtitle": "Boosty / Донаты",
        "icon": "donate",
        "variant": "cyber-dither",
        "accent": "donate",
        "shape": "pill",
        "url_hint": "https://boosty.to/your_page",
    },
    "discord": {
        "title": "Discord",
        "subtitle": "Голосовой сервер",
        "icon": "discord",
        "variant": "cyber-dither",
        "accent": "discord",
        "shape": "pill",
        "url_hint": "https://discord.gg/your_invite",
    },
    "tiktok": {
        "title": "TikTok",
        "subtitle": "Клипы и шортсы",
        "icon": "tiktok",
        "variant": "cyber-dither",
        "accent": "tiktok",
        "shape": "pill",
        "url_hint": "https://www.tiktok.com/@your_profile",
    },
    "kick": {
        "title": "Kick",
        "subtitle": "Стримы",
        "icon": "kick",
        "variant": "cyber-dither",
        "accent": "kick",
        "shape": "pill",
        "url_hint": "https://kick.com/your_channel",
    },
    "custom": {
        "title": "Новая кнопка",
        "subtitle": "Полезная ссылка",
        "icon": "link",
        "variant": "cyber-dither",
        "accent": "silver",
        "shape": "pill",
        "url_hint": "https://example.com",
    },
}


@dataclass(slots=True)
class MiniAppButton:
    """Single button entry rendered inside the GitHub Pages Mini App."""

    id: str
    title: str
    subtitle: str = ""
    url: str = "https://t.me/"
    icon: str = "link"
    variant: str = "cyber-dither"
    accent: str = "silver"
    shape: str = "pill"
    bgImage: str = ""


@dataclass(slots=True)
class MiniAppConfig:
    """Full configuration schema matching `docs/config.json`."""

    brandTitle: str = "Добро пожаловать!"
    subtitle: str = "Стримы, свежие видео, чат комьюнити и личная предложка — всё в одном цифровом хабе."
    coverMode: str = "dither-star"
    coverBadge: str = "HUB // ONLINE"
    coverImage: str = ""
    theme: dict[str, str] = field(
        default_factory=lambda: {"bgMode": "cyber-void", "cardTone": "dark"}
    )
    buttons: list[MiniAppButton] = field(default_factory=list)

    def find_button(self, button_id: str) -> MiniAppButton | None:
        """Return Mini App button by ID or None."""
        for btn in self.buttons:
            if btn.id == button_id:
                return btn
        return None

    def add_button(
        self,
        *,
        title: str,
        url: str,
        subtitle: str = "",
        icon: str = "link",
        variant: str = "cyber-dither",
        accent: str = "silver",
        shape: str = "pill",
    ) -> MiniAppButton:
        """Append a new styled button to the Mini App."""
        button = MiniAppButton(
            id=f"btn_{uuid.uuid4().hex[:8]}",
            title=title.strip(),
            subtitle=subtitle.strip(),
            url=url.strip(),
            icon=icon,
            variant=variant,
            accent=accent,
            shape=shape,
        )
        self.buttons.append(button)
        return button

    def remove_button(self, button_id: str) -> bool:
        """Delete a button by ID; return True if removed."""
        before = len(self.buttons)
        self.buttons = [btn for btn in self.buttons if btn.id != button_id]
        return len(self.buttons) < before

    def move_button(self, button_id: str, direction: int) -> bool:
        """Move button up (-1) or down (+1) in the list."""
        idx = next((i for i, b in enumerate(self.buttons) if b.id == button_id), None)
        if idx is None:
            return False
        target = idx + direction
        if target < 0 or target >= len(self.buttons):
            return False
        self.buttons[idx], self.buttons[target] = self.buttons[target], self.buttons[idx]
        return True


class MiniAppConfigStore:
    """Reads and writes `docs/config.json`."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> MiniAppConfig:
        """Load `docs/config.json` from disk or return defaults."""
        if not self.path.exists():
            cfg = MiniAppConfig()
            self.save(cfg)
            return cfg

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        buttons = [
            MiniAppButton(
                id=str(item.get("id") or f"btn_{uuid.uuid4().hex[:8]}"),
                title=str(item.get("title") or "Ссылка"),
                subtitle=str(item.get("subtitle") or ""),
                url=str(item.get("url") or "https://t.me/"),
                icon=str(item.get("icon") or "link"),
                variant=str(item.get("variant") or "cyber-dither"),
                accent=str(item.get("accent") or "silver"),
                shape=str(item.get("shape") or "pill"),
                bgImage=str(item.get("bgImage") or ""),
            )
            for item in raw.get("buttons", [])
        ]
        theme = dict(raw.get("theme") or {"bgMode": "cyber-void", "cardTone": "dark"})
        return MiniAppConfig(
            brandTitle=str(raw.get("brandTitle") or "Добро пожаловать!"),
            subtitle=str(raw.get("subtitle") or ""),
            coverMode=str(raw.get("coverMode") or "dither-star"),
            coverBadge=str(raw.get("coverBadge") or ""),
            coverImage=str(raw.get("coverImage") or ""),
            theme=theme,
            buttons=buttons,
        )

    def save(self, config: MiniAppConfig) -> None:
        """Atomically persist `docs/config.json`."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(config)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)


async def push_miniapp_config_to_github(
    config_path: Path,
    github_token: str,
    github_repo: str,
    branch: str = "main",
    repo_file_path: str = "docs/config.json",
) -> str:
    """Commit and push `docs/config.json` directly via GitHub Contents API."""
    api_url = f"https://api.github.com/repos/{github_repo}/contents/{repo_file_path}"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    content_bytes = config_path.read_bytes()
    content_b64 = base64.b64encode(content_bytes).decode("ascii")

    async with aiohttp.ClientSession(headers=headers) as session:
        sha: str | None = None
        async with session.get(api_url, params={"ref": branch}) as get_resp:
            if get_resp.status == 200:
                meta = await get_resp.json()
                sha = meta.get("sha")
            elif get_resp.status != 404:
                err_text = await get_resp.text()
                raise RuntimeError(f"GitHub GET error ({get_resp.status}): {err_text[:200]}")

        body: dict[str, object] = {
            "message": "Update Mini App config via Telegram admin bot",
            "content": content_b64,
            "branch": branch,
        }
        if sha:
            body["sha"] = sha

        async with session.put(api_url, json=body) as put_resp:
            if put_resp.status not in (200, 201):
                err_text = await put_resp.text()
                raise RuntimeError(f"GitHub PUT error ({put_resp.status}): {err_text[:200]}")
            res = await put_resp.json()
            commit_sha = str((res.get("commit") or {}).get("sha") or "")[:7]
            return commit_sha
