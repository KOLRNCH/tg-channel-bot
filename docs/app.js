/**
 * Telegram Mini App controller:
 * - Loads channel card & styled buttons from ./config.json (or live preview override)
 * - Generates crisp 24-point starburst clip-path for sticker-shaped buttons
 * - Drives interactive chrome pointer reflections + water-drop concentric ripples
 */

const STORAGE_PREVIEW_KEY = "tg_miniapp_preview_config_v1";

function buildStarburstPolygon(points = 24, outerRadius = 50, innerRadius = 40.5) {
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
  body.classList.remove("bg-telegram-blue", "bg-telegram-dark", "bg-telegram-theme", "card-dark");

  const bgMode = theme.bgMode || "telegram-blue";
  if (bgMode === "telegram-dark") {
    body.classList.add("bg-telegram-dark");
  } else if (bgMode === "telegram-theme") {
    body.classList.add("bg-telegram-theme");
  } else {
    body.classList.add("bg-telegram-blue");
  }

  if (theme.cardTone === "dark") {
    body.classList.add("card-dark");
  }
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

function createStyledButton(btnConfig, fallbackCover) {
  const shape = btnConfig.shape === "starburst" ? "starburst" : "pill";
  const variant = btnConfig.variant || "chrome-iridescent";

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = `fx-btn fx-btn--${variant}` + (shape === "starburst" ? " fx-btn--starburst" : "");
  btn.setAttribute("aria-label", btnConfig.title || "Кнопка");

  const bg = document.createElement("span");
  bg.className = "fx-btn__bg";
  if (variant === "photo-glass") {
    const imgUrl = btnConfig.bgImage || fallbackCover || "./assets/cover.jpg";
    bg.style.backgroundImage = `url("${imgUrl.replace(/"/g, '\\"')}")`;
  }
  btn.appendChild(bg);

  if (variant === "photo-glass") {
    const glass = document.createElement("span");
    glass.className = "fx-btn__glass";
    btn.appendChild(glass);
  }

  if (btnConfig.icon) {
    const icon = document.createElement("span");
    icon.className = "fx-btn__icon";
    icon.textContent = btnConfig.icon;
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
    // Handle keyboard Enter/Space activation cleanly
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
  const coverImg = document.getElementById("coverImg");
  if (config.coverImage) {
    coverBox.hidden = false;
    coverImg.src = config.coverImage;
  } else {
    coverBox.hidden = true;
  }

  document.getElementById("brandTitle").textContent = config.brandTitle || "Добро пожаловать!";
  document.getElementById("brandSubtitle").textContent = config.subtitle || "";

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

  dock.hidden = dock.children.length === 0;
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
