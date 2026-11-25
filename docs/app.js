/**
 * Telegram Mini App controller:
 * - Procedural 3D Bayer-dithered rotating cyber-star canvas (inspired by cyber-sigil/CRT dither)
 * - Pure-code monochrome liquid chrome buttons with platform accent glow + water-drop ripples
 * - Config driven by ./config.json (or live preview override from editor.html)
 */

const STORAGE_PREVIEW_KEY = "tg_miniapp_preview_config_v1";

const SVG_ICONS = {
  youtube: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.6 7.2a2.9 2.9 0 0 0-2-2C17.8 4.7 12 4.7 12 4.7s-5.8 0-7.6.5a2.9 2.9 0 0 0-2 2A30 30 0 0 0 2 12a30 30 0 0 0 .4 4.8 2.9 2.9 0 0 0 2 2c1.8.5 7.6.5 7.6.5s5.8 0 7.6-.5a2.9 2.9 0 0 0 2-2A30 30 0 0 0 22 12a30 30 0 0 0-.4-4.8ZM10 15.2V8.8L15.6 12 10 15.2Z"/></svg>`,
  twitch: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M4.3 3 3 6.3v12.8h4.7V22h2.7l2.9-2.9h4.1L21 15.5V3H4.3Zm14.9 11.6-2.9 2.9h-4.7l-2.6 2.6v-2.6H5.2V4.8h14v9.8ZM15.5 8h-1.8v5h1.8V8Zm-4.8 0H8.9v5h1.8V8Z"/></svg>`,
  telegram: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.5 4.3 2.9 11.5c-1.3.5-1.3 1.3-.2 1.6l4.7 1.5 11-6.9c.5-.3 1-.1.6.2l-8.9 8-.3 4.9c.5 0 .7-.2 1-.5l2.3-2.2 4.8 3.5c.9.5 1.5.2 1.7-.8L22.6 5.6c.3-1.2-.5-1.8-1.1-1.3Z"/></svg>`,
  suggest: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 10h8"/><path d="M8 14h4"/></svg>`,
  donate: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z"/></svg>`,
  discord: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19.3 5.3A16 16 0 0 0 15.4 4l-.4.8a14.4 14.4 0 0 0-6 0L8.6 4a16 16 0 0 0-3.9 1.3C2.2 9 1.5 12.6 1.8 16.2a16.2 16.2 0 0 0 4.8 2.4l1-1.6a10.4 10.4 0 0 1-1.6-.8l.4-.3a11.4 11.4 0 0 0 11.2 0l.4.3c-.5.3-1 .6-1.6.8l1 1.6a16.2 16.2 0 0 0 4.8-2.4c.4-4.2-.6-7.8-2.9-10.9ZM9.5 14c-.9 0-1.6-.8-1.6-1.8s.7-1.8 1.6-1.8 1.6.8 1.6 1.8-.7 1.8-1.6 1.8Zm5 0c-.9 0-1.6-.8-1.6-1.8s.7-1.8 1.6-1.8 1.6.8 1.6 1.8-.7 1.8-1.6 1.8Z"/></svg>`,
  tiktok: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M15.5 3h2.9a4.8 4.8 0 0 0 3.6 3.5v2.9a7.7 7.7 0 0 1-3.6-1v6.2a6 6 0 1 1-5.2-5.9v3a3.1 3.1 0 1 0 2.3 3V3Z"/></svg>`,
  kick: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M4 3h5v6h3V6h3V3h5v6h-3v3h-3v3h3v3h3v3h-5v-3h-3v-3H9v6H4V3Z"/></svg>`,
  vk: `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3 6.5h3.2c.2 4.1 2 6.6 3.7 7V6.5h3v4c1.7-.2 3.5-2 4.1-4h3c-.5 2.5-2.3 4.3-3.6 5 1.3.6 3.3 2.2 4 5h-3.3c-.7-2.1-2.3-3.7-4.2-3.9v3.9h-.5C6.8 16.5 3.6 12.6 3 6.5Z"/></svg>`,
  instagram: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg>`,
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

/**
 * Procedural 3D Bayer-dithered rotating 4-point cyber star renderer.
 * Low internal pixel buffer (188x96) upscaled with crisp pixelated edges for fast 60fps.
 */
function createDitherStarRenderer(canvas) {
  const ctx = canvas.getContext("2d", { alpha: false });
  const W = canvas.width;
  const H = canvas.height;
  const img = ctx.createImageData(W, H);
  const data = img.data;
  const zBuf = new Float32Array(W * H);
  const shadeBuf = new Float32Array(W * H);

  // 4x4 Bayer matrix normalized to [0..1)
  const BAYER = [
    0 / 16, 8 / 16, 2 / 16, 10 / 16,
    12 / 16, 4 / 16, 14 / 16, 6 / 16,
    3 / 16, 11 / 16, 1 / 16, 9 / 16,
    15 / 16, 7 / 16, 13 / 16, 5 / 16
  ];

  // 3D beveled 4-point cyber star vertices
  const VERTS = [
    [0, -1.28, 0],     // 0: top tip
    [0.24, -0.26, 0],  // 1: top-right waist
    [0.95, 0.04, 0],   // 2: right tip
    [0.22, 0.28, 0],   // 3: bottom-right waist
    [0, 1.28, 0],      // 4: bottom tip
    [-0.22, 0.28, 0],  // 5: bottom-left waist
    [-0.95, 0.04, 0],  // 6: left tip
    [-0.24, -0.26, 0], // 7: top-left waist
    [0, 0, 0.27],      // 8: front apex
    [0, 0, -0.27]      // 9: back apex
  ];

  const TRIS = [];
  for (let i = 0; i < 8; i++) {
    const next = (i + 1) % 8;
    TRIS.push([8, i, next]);
    TRIS.push([9, next, i]);
  }

  let rafId = 0;
  let running = false;
  let glitchBoost = 0;
  let startTime = performance.now();
  const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  canvas.addEventListener("pointerdown", () => {
    glitchBoost = 1.0;
  });

  function renderFrame(now) {
    const t = (now - startTime) * 0.001;
    const rotY = reducedMotion ? 0.45 : t * 1.15;
    const rotX = Math.sin(t * 0.7) * 0.22;
    const rotZ = -0.24 + Math.cos(t * 0.5) * 0.08;

    const cy = Math.cos(rotY), sy = Math.sin(rotY);
    const cx = Math.cos(rotX), sx = Math.sin(rotX);
    const cz = Math.cos(rotZ), sz = Math.sin(rotZ);

    const proj = new Array(VERTS.length);
    for (let i = 0; i < VERTS.length; i++) {
      let [x, y, z] = VERTS[i];
      // Rotate Y
      const x1 = x * cy + z * sy;
      const z1 = -x * sy + z * cy;
      // Rotate X
      const y2 = y * cx - z1 * sx;
      const z2 = y * sx + z1 * cx;
      // Rotate Z
      const x3 = x1 * cz - y2 * sz;
      const y3 = x1 * sz + y2 * cz;

      const depth = 3.2 - z2;
      const scale = 112 / depth;
      proj[i] = [W * 0.5 + x3 * scale, H * 0.5 + y3 * scale, z2, x3, y3];
    }

    zBuf.fill(-1e9);
    shadeBuf.fill(-1);

    // Light direction (top-left bright chrome highlight + rim)
    const lx = -0.5, ly = -0.58, lz = 0.64;

    for (let tIdx = 0; tIdx < TRIS.length; tIdx++) {
      const [ia, ib, ic] = TRIS[tIdx];
      const a = proj[ia], b = proj[ib], c = proj[ic];

      // Screen-space signed area
      const area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
      if (area <= 0) continue;

      // 3D face normal
      const ux = b[3] - a[3], uy = b[4] - a[4], uz = b[2] - a[2];
      const vx = c[3] - a[3], vy = c[4] - a[4], vz = c[2] - a[2];
      let nx = uy * vz - uz * vy;
      let ny = uz * vx - ux * vz;
      let nz = ux * vy - uy * vx;
      const nLen = Math.hypot(nx, ny, nz) || 1;
      nx /= nLen; ny /= nLen; nz /= nLen;

      const diff = Math.max(0, nx * lx + ny * ly + nz * lz);
      const spec = Math.pow(Math.max(0, nz), 3.2);
      const rim = Math.pow(1 - Math.abs(nz), 1.7) * 0.55;
      const shade = Math.min(1, 0.18 + diff * 0.68 + spec * 0.52 + rim);

      const minX = Math.max(0, Math.floor(Math.min(a[0], b[0], c[0])));
      const maxX = Math.min(W - 1, Math.ceil(Math.max(a[0], b[0], c[0])));
      const minY = Math.max(0, Math.floor(Math.min(a[1], b[1], c[1])));
      const maxY = Math.min(H - 1, Math.ceil(Math.max(a[1], b[1], c[1])));

      const invArea = 1 / area;
      for (let py = minY; py <= maxY; py++) {
        for (let px = minX; px <= maxX; px++) {
          const w0 = ((b[0] - px) * (c[1] - py) - (b[1] - py) * (c[0] - px)) * invArea;
          const w1 = ((c[0] - px) * (a[1] - py) - (c[1] - py) * (a[0] - px)) * invArea;
          const w2 = 1 - w0 - w1;
          if (w0 < 0 || w1 < 0 || w2 < 0) continue;

          const z = w0 * a[2] + w1 * b[2] + w2 * c[2];
          const idx = py * W + px;
          if (z > zBuf[idx]) {
            zBuf[idx] = z;
            shadeBuf[idx] = shade;
          }
        }
      }
    }

    // Periodic subtle slice-glitch burst (like frames 00:06-00:08 of reference)
    const periodic = (!reducedMotion && (t % 4.2) > 3.92) ? 0.85 : 0;
    const glitch = Math.max(periodic, glitchBoost);
    glitchBoost = Math.max(0, glitchBoost - 0.06);

    // Clear pixel buffer to deep void #070709
    for (let y = 0; y < H; y++) {
      const sliceShift = glitch > 0.1 && ((y >> 2) % 3 === 0)
        ? Math.round(Math.sin(y * 0.4 + t * 40) * 7 * glitch)
        : 0;

      for (let x = 0; x < W; x++) {
        const sx = x - sliceShift;
        const outIdx = (y * W + x) * 4;

        if (sx < 0 || sx >= W) {
          data[outIdx] = 7;
          data[outIdx + 1] = 7;
          data[outIdx + 2] = 10;
          data[outIdx + 3] = 255;
          continue;
        }

        const shade = shadeBuf[y * W + sx];
        const leftShade = sx > 0 ? shadeBuf[y * W + sx - 1] : -1;
        const rightShade = sx < W - 1 ? shadeBuf[y * W + sx + 1] : -1;

        const bayer = BAYER[((y & 3) << 2) | (x & 3)];

        if (shade >= 0) {
          // Bayer dither threshold across dark chrome -> crisp silver -> pure white
          const lit = shade > bayer;
          const bright = shade > bayer + 0.34;

          if (bright) {
            data[outIdx] = 244;
            data[outIdx + 1] = 246;
            data[outIdx + 2] = 252;
          } else if (lit) {
            // Subtle crimson-silver digital midtone highlight
            data[outIdx] = 198;
            data[outIdx + 1] = 148;
            data[outIdx + 2] = 166;
          } else {
            data[outIdx] = 36;
            data[outIdx + 1] = 24;
            data[outIdx + 2] = 32;
          }
        } else if (leftShade >= 0 && bayer < 0.72) {
          // Chromatic right edge bleed (crimson-pink)
          data[outIdx] = 245;
          data[outIdx + 1] = 45;
          data[outIdx + 2] = 95;
        } else if (rightShade >= 0 && bayer < 0.72) {
          // Chromatic left edge bleed (violet-indigo)
          data[outIdx] = 148;
          data[outIdx + 1] = 72;
          data[outIdx + 2] = 248;
        } else {
          // Subtle digital grid dots in the dark void
          const bgDot = (x % 8 === 0 && y % 8 === 0) ? 20 : 7;
          data[outIdx] = bgDot;
          data[outIdx + 1] = bgDot;
          data[outIdx + 2] = bgDot + 3;
        }
        data[outIdx + 3] = 255;
      }
    }

    ctx.putImageData(img, 0, 0);
    if (running && !reducedMotion) {
      rafId = requestAnimationFrame(renderFrame);
    }
  }

  return {
    start() {
      if (running) return;
      running = true;
      renderFrame(performance.now());
    },
    stop() {
      running = false;
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
    }
  };
}

let starRenderer = null;

function getTelegramWebApp() {
  return window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
}

function applyTheme(theme = {}) {
  const body = document.body;
  body.classList.remove("bg-cyber-void", "bg-monochrome-chrome", "bg-telegram-blue", "bg-telegram-theme", "card-dark", "card-light");

  const bgMode = theme.bgMode || "cyber-void";
  if (bgMode === "monochrome-chrome") {
    body.classList.add("bg-monochrome-chrome");
  } else if (bgMode === "telegram-blue") {
    body.classList.add("bg-telegram-blue");
  } else if (bgMode === "telegram-theme") {
    body.classList.add("bg-telegram-theme");
  } else {
    body.classList.add("bg-cyber-void");
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

function isSafeUrl(url) {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" || parsed.protocol === "tg:";
  } catch (_) {
    return false;
  }
}

function openTargetUrl(url) {
  if (!isSafeUrl(url)) return;
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
  const variant = btnConfig.variant || "cyber-dither";
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
  arrow.textContent = "->";
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
  const ditherCanvas = document.getElementById("ditherCanvas");
  const chromeHero = document.getElementById("chromeHero");
  const coverImg = document.getElementById("coverImg");
  const coverBadge = document.getElementById("coverBadge");

  if (!starRenderer && ditherCanvas) {
    starRenderer = createDitherStarRenderer(ditherCanvas);
  }

  const mode = config.coverMode || (config.coverImage ? "image" : "dither-star");
  if (mode === "none") {
    coverBox.hidden = true;
    starRenderer?.stop();
  } else if (mode === "image" && config.coverImage) {
    coverBox.hidden = false;
    ditherCanvas.hidden = true;
    chromeHero.hidden = true;
    coverImg.hidden = false;
    coverImg.src = config.coverImage;
    starRenderer?.stop();
  } else if (mode === "chrome-code") {
    coverBox.hidden = false;
    ditherCanvas.hidden = true;
    chromeHero.hidden = false;
    coverImg.hidden = true;
    starRenderer?.stop();
  } else {
    coverBox.hidden = false;
    ditherCanvas.hidden = false;
    chromeHero.hidden = true;
    coverImg.hidden = true;
    starRenderer?.start();
  }

  coverBadge.hidden = !config.coverBadge;
  coverBadge.textContent = config.coverBadge || "";

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
    previewBar.hidden = false;
    const saved = localStorage.getItem(STORAGE_PREVIEW_KEY);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (_) {}
    }
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
