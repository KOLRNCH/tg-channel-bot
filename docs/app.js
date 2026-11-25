/**
 * Telegram Mini App controller:
 * - Zero-image procedural chrome header & crisp inline SVG platform icons
 * - Monochrome chrome buttons with platform accent glow + water-drop concentric ripples
 * - Loads config from ./config.json (or live preview override from editor.html)
 */

const STORAGE_PREVIEW_KEY = "tg_miniapp_preview_config_v1";

const SVG_ICONS = {
  youtube: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.6 7.2a2.9 2.9 0 0 0-2-2C17.8 4.7 12 4.7 12 4.7s-5.8 0-7.6.5a2.9 2.9 0 0 0-2 2A30 30 0 0 0 2 12a30 30 0 0 0 .4 4.8 2.9 2.9 0 0 0 2 2c1.8.5 7.6.5 7.6.5s5.8 0 7.6-.5a2.9 2.9 0 0 0 2-2A30 30 0 0 0 22 12a30 30 0 0 0-.4-4.8ZM10 15.2V8.8L15.6 12 10 15.2Z"/></svg>`,
  twitch: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M4.3 3 3 6.3v12.8h4.7V22h2.7l2.9-2.9h4.1L21 15.5V3H4.3Zm14.9 11.6-2.9 2.9h-4.7l-2.6 2.6v-2.6H5.2V4.8h14v9.8ZM15.5 8h-1.8v5h1.8V8Zm-4.8 0H8.9v5h1.8V8Z"/></svg>`,
  telegram: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.5 4.3 2.9 11.5c-1.3.5-1.3 1.3-.2 1.6l4.7 1.5 11-6.9c.5-.3 1-.1.6.2l-8.9 8-.3 4.9c.5 0 .7-.2 1-.5l2.3-2.2 4.8 3.5c.9.5 1.5.2 1.7-.8L22.6 5.6c.3-1.2-.5-1.8-1.1-1.3Z"/></svg>`,
  suggest: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 10h8"/><path d="M8 14h4"/></svg>`,
  link: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>`
};

function buildStarburstPolygon(points = 24, outerRadius = 50, innerRadius = 41) {
  const coords = [];
  const total = points * 2;
  for (let i = 0; i < total; i++) {
    const angle = (i * Math.PI) / points - Math.PI / 2;
    const r = i % 2 === 0 ? outerRadius : innerRadius;
    const x = (50 + r * Math.cos(angle)).toFixed(2);
    const y = (50 + r * Math.sin(angle)).toFixed(2);
    coords.push(`${x}% ${y}%`);
  }
  return `polygon(${coords.join(", ")})`;
}

document.documentElement.style.setProperty("--starburst-clip", buildStarburstPolygon());

function getTelegramWebApp() {
  return window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
}

function applyTheme(theme = {}) {
  const body = document.body;
  body.classList.remove("bg-monochrome-chrome", "bg-telegram-blue", "bg-telegram-theme", "card-dark", "card-light");

  const bgMode = theme.bgMode || "monochrome-chrome";
  if (bgMode === "telegram-blue") {
    body.classList.add("bg-telegram-blue");
  } else if (bgMode === "telegram-theme") {
    body.classList.add("bg-telegram-theme");
  } else {
    body.classList.add("bg-monochrome-chrome");
  }

  body.classList.add(theme.cardTone === "light" ? "card-light" : "card-dark");
}

function spawnWaterDrop(buttonEl, clientX, clientY) {
  const rippleLayer = buttonEl.querySelector(".ripple-layer");
  if (!rippleLayer) return;

  const rect = buttonEl.getBoundingClientRect();
  const x = clientX !== undefined ? clientX - rect.left : rect.width / 2;
  const y = clientY !== undefined ? clientY - rect.top : rect.height / 2;
  const maxDim = Math.max(rect.width, rect.height) * 2.25;

  const drop = document.createElement("span");
  drop.className = "water-drop";
  drop.style.left = `${x}px`;
  drop.style.top = `${y}px`;
  drop.style.setProperty("--ripple-size", `${Math.ceil(maxDim)}px`);

  drop.innerHTML = `
    <span class="water-flash"></span>
    <span class="water-ring"></span>
    <span class="water-ring water-ring--2"></span>
    <span class="water-ring water-ring--3"></span>
  `;

  rippleLayer.appendChild(drop);
  setTimeout(() => drop.remove(), 1150);
}

function openTargetUrl(url) {
  if (!url) return;
  const tg = getTelegramWebApp();

  if (tg && tg.initData) {
    if (/^https?:\/\/t\.me\//i.test(url) || /^tg:\/\//i.test(url)) {
      tg.openTelegramLink(url);
      return;
    }
    tg.openLink(url);
    return;
  }

  window.open(url, "_blank", "noopener,noreferrer");
}

function renderButtonIcon(iconEl, iconValue) {
  const key = (iconValue || "").trim().toLowerCase();
  if (SVG_ICONS[key]) {
    iconEl.innerHTML = SVG_ICONS[key];
    return;
  }
  if (iconValue) {
    iconEl.textContent = iconValue;
    return;
  }
  iconEl.innerHTML = SVG_ICONS.link;
}

function createStyledButton(btnConfig, fallbackCover) {
  const shape = btnConfig.shape === "starburst" ? "starburst" : "pill";
  const variant = btnConfig.variant || "chrome-mono";
  const accent = btnConfig.accent || "silver";

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className =
    `fx-btn fx-btn--${variant} fx-btn--accent-${accent}` +
    (shape === "starburst" ? " fx-btn--starburst" : "");
  btn.setAttribute("aria-label", btnConfig.title || "Кнопка");

  const bg = document.createElement("span");
  bg.className = "fx-btn__bg";
  if (variant === "photo-glass") {
    const imgUrl = btnConfig.bgImage || fallbackCover || "";
    if (imgUrl) {
      bg.style.backgroundImage = `url("${imgUrl.replace(/"/g, '\\"')}")`;
    }
  }
  btn.appendChild(bg);

  if (variant === "photo-glass") {
    const glass = document.createElement("span");
    glass.className = "fx-btn__glass";
    btn.appendChild(glass);
  }

  if (btnConfig.icon !== "none") {
    const icon = document.createElement("span");
    icon.className = "fx-btn__icon";
    renderButtonIcon(icon, btnConfig.icon);
    btn.appendChild(icon);
  }

  const meta = document.createElement("span");
  meta.className = "fx-btn__meta";

  const title = document.createElement("span");
  title.className = "fx-btn__title";
  title.textContent = btnConfig.title || "Ссылка";
  meta.appendChild(title);

  if (btnConfig.subtitle) {
    const sub = document.createElement("span");
    sub.className = "fx-btn__sub";
    sub.textContent = btnConfig.subtitle;
    meta.appendChild(sub);
  }
  btn.appendChild(meta);

  const arrow = document.createElement("span");
  arrow.className = "fx-btn__arrow";
  arrow.textContent = "→";
  btn.appendChild(arrow);

  const rippleLayer = document.createElement("span");
  rippleLayer.className = "ripple-layer";
  btn.appendChild(rippleLayer);

  let lastPointerDownAt = 0;

  btn.addEventListener("pointermove", (ev) => {
    const rect = btn.getBoundingClientRect();
    const px = ((ev.clientX - rect.left) / rect.width) * 100;
    const py = ((ev.clientY - rect.top) / rect.height) * 100;
    btn.style.setProperty("--btn-mx", `${px.toFixed(1)}%`);
    btn.style.setProperty("--btn-my", `${py.toFixed(1)}%`);
  });

  btn.addEventListener("pointerdown", (ev) => {
    lastPointerDownAt = Date.now();
    btn.classList.add("is-pressed");
    spawnWaterDrop(btn, ev.clientX, ev.clientY);

    const tg = getTelegramWebApp();
    if (tg && tg.HapticFeedback) {
      try {
        tg.HapticFeedback.impactOccurred("medium");
      } catch (_) {}
    }
  });

  const release = () => btn.classList.remove("is-pressed");
  btn.addEventListener("pointerup", release);
  btn.addEventListener("pointerleave", release);
  btn.addEventListener("pointercancel", release);

  btn.addEventListener("click", () => {
    if (Date.now() - lastPointerDownAt > 500) {
      spawnWaterDrop(btn);
    }
    const targetUrl = btnConfig.url;
    setTimeout(() => openTargetUrl(targetUrl), 250);
  });

  if (shape === "starburst") {
    const wrap = document.createElement("div");
    wrap.className = "starburst-wrap";
    wrap.appendChild(btn);
    return { el: wrap, isStarburst: true };
  }

  return { el: btn, isStarburst: false };
}

function renderApp(config) {
  applyTheme(config.theme);

  const coverBox = document.getElementById("coverBox");
  const chromeHero = document.getElementById("chromeHero");
  const coverImg = document.getElementById("coverImg");
  const coverBadge = document.getElementById("coverBadge");

  const mode = config.coverMode || (config.coverImage ? "image" : "chrome-code");
  if (mode === "none") {
    coverBox.hidden = true;
  } else if (mode === "image" && config.coverImage) {
    coverBox.hidden = false;
    chromeHero.hidden = true;
    coverImg.hidden = false;
    coverImg.src = config.coverImage;
  } else {
    coverBox.hidden = false;
    chromeHero.hidden = false;
    coverImg.hidden = true;
    coverBadge.hidden = !config.coverBadge;
    coverBadge.textContent = config.coverBadge || "";
  }

  document.getElementById("brandTitle").textContent = config.brandTitle || "Добро пожаловать!";
  document.getElementById("brandSubtitle").textContent = config.subtitle || "";

  const wrapper = document.getElementById("cardWrapper");
  const stack = document.getElementById("buttonsStack");
  const dock = document.getElementById("starburstDock");
  stack.innerHTML = "";
  dock.innerHTML = "";

  const buttons = Array.isArray(config.buttons) ? config.buttons : [];
  let starburstCount = 0;

  buttons.forEach((btnCfg) => {
    const { el, isStarburst } = createStyledButton(btnCfg, config.coverImage);
    if (isStarburst && starburstCount < 2) {
      dock.appendChild(el);
      starburstCount += 1;
    } else {
      if (isStarburst) {
        el.style.margin = "4px auto 0";
      }
      stack.appendChild(el);
    }
  });

  const hasStarburst = dock.children.length > 0;
  dock.hidden = !hasStarburst;
  wrapper.classList.toggle("has-starburst", hasStarburst);
}

async function loadInitialConfig() {
  const params = new URLSearchParams(window.location.search);
  const previewBar = document.getElementById("previewBar");

  if (params.get("preview") === "1") {
    const saved = localStorage.getItem(STORAGE_PREVIEW_KEY);
    if (saved) {
      try {
        previewBar.hidden = false;
        return JSON.parse(saved);
      } catch (_) {}
    }
  }

  const tg = getTelegramWebApp();
  if (!tg || !tg.initData) {
    previewBar.hidden = false;
  }

  const resp = await fetch(`./config.json?v=${Date.now()}`);
  if (!resp.ok) {
    throw new Error(`Failed to load config.json: ${resp.status}`);
  }
  return resp.json();
}

window.addEventListener("DOMContentLoaded", async () => {
  const tg = getTelegramWebApp();
  if (tg) {
    tg.ready();
    tg.expand();
  }

  window.addEventListener("message", (event) => {
    if (event.data && event.data.type === "MINIAPP_CONFIG_UPDATE") {
      renderApp(event.data.config);
    }
  });

  try {
    const config = await loadInitialConfig();
    renderApp(config);
  } catch (err) {
    console.error(err);
    document.getElementById("brandSubtitle").textContent =
      "Не удалось загрузить config.json. Проверьте файл конфигурации.";
  }
});
