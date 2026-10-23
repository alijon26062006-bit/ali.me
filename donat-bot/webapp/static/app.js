/* Donat shop Telegram Mini App — vanilla JS, no build step. */
(() => {
  "use strict";

  const tg = window.Telegram && window.Telegram.WebApp;
  const $app = document.getElementById("app");
  const $tabbar = document.getElementById("tabbar");
  const $sheet = document.getElementById("sheet-root");
  const $toast = document.getElementById("toast");

  // ------------------------------------------------------------------ icons (Lucide paths)
  const P = {
    eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    eyeOff: '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.53 13.53 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><path d="M2 2l20 20"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    crosshair: '<circle cx="12" cy="12" r="10"/><path d="M22 12h-4M6 12H2M12 6V2M12 22v-4"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    right: '<path d="m9 18 6-6-6-6"/>',
    back: '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    arrow: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    cart: '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    gem: '<path d="M6 3h12l4 6-10 13L2 9Z"/><path d="M11 3 8 9l4 13 4-13-3-6"/><path d="M2 9h20"/>',
    award: '<circle cx="12" cy="8" r="6"/><path d="M15.48 12.89 17 22l-5-3-5 3 1.52-9.11"/>',
    listChecks: '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8M13 12h8M13 18h8"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    hash: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
    clipboard: '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    card: '<rect width="20" height="14" x="2" y="5" rx="2"/><path d="M2 10h20"/>',
    wallet: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    package: '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    receipt: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
    ticket: '<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M13 5v2M13 17v2M13 11v2"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    palette: '<circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.65-.75 1.65-1.69 0-.44-.18-.84-.44-1.13-.29-.29-.44-.65-.44-1.13a1.64 1.64 0 0 1 1.67-1.67h2c3.05 0 5.55-2.5 5.55-5.55C21.97 6.01 17.46 2 12 2z"/>',
    languages: '<path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/>',
    coins: '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>',
    lock: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    star: '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/>',
    copy: '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.59 13.51 6.83 3.98M15.41 6.51l-6.82 3.98"/>',
    pencil: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
    crown: '<path d="m2 4 3 12h14l3-12-6 7-4-7-4 7-6-7zM5 20h14"/>',
    gamepad: '<path d="M6 12h4M8 10v4M15 13h.01M18 11h.01"/><rect width="20" height="12" x="2" y="6" rx="2"/>',
    flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
    sparkles: '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>',
    del: '<path d="M20 5H9l-7 7 7 7h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2Z"/><path d="m18 9-6 6M12 9l6 6"/>',
    message: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    // filled (tab bar)
    homeF: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    bagF: '<path d="M7 8V7a5 5 0 0 1 10 0v1h2.2a1 1 0 0 1 1 .92l.8 11A2 2 0 0 1 19 23H5a2 2 0 0 1-2-2.08l.8-11A1 1 0 0 1 4.8 8zm2 0h6V7a3 3 0 0 0-6 0z"/>',
    headsetF: '<path d="M12 2a9 9 0 0 0-9 9v6a3 3 0 0 0 3 3h1a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1H5v-1a7 7 0 0 1 14 0v1h-2a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h1.9a2.5 2.5 0 0 1-2.4 2H14a1 1 0 0 0 0 2h2.5a4.5 4.5 0 0 0 4.5-4.5V11a9 9 0 0 0-9-9z"/>',
    userF: '<circle cx="12" cy="7.5" r="4.5"/><path d="M3 21a9 9 0 0 1 18 0 1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>',
  };
  const icon = (name, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name] || ""}</svg>`;

  // product artwork
  const ART = {
    gem: () => `<svg viewBox="0 0 120 120" aria-hidden="true"><defs>
        <linearGradient id="gmA" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d6f3ff"/><stop offset=".45" stop-color="#47b4ff"/><stop offset="1" stop-color="#0f3fb0"/></linearGradient>
        <linearGradient id="gmB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7fd0ff"/><stop offset="1" stop-color="#1747c4"/></linearGradient></defs>
        <ellipse cx="60" cy="103" rx="42" ry="7" fill="#000" opacity=".35"/>
        <rect x="18" y="86" width="84" height="12" rx="3" fill="#20242e"/>
        <polygon points="22,46 40,24 80,24 98,46 60,96" fill="url(#gmA)"/>
        <polygon points="22,46 98,46 60,96" fill="url(#gmB)" opacity=".75"/>
        <polygon points="40,24 50,46 60,24" fill="#e6f8ff" opacity=".85"/><polygon points="60,24 70,46 80,24" fill="#9ad8ff" opacity=".8"/>
        <polygon points="50,46 60,96 70,46" fill="#5cc2ff" opacity=".55"/>
        <polygon points="16,62 26,52 36,62 26,80" fill="url(#gmA)" opacity=".9"/>
        <circle cx="74" cy="33" r="3" fill="#fff"/><path d="M74 25v16M66 33h16" stroke="#fff" stroke-width="1.2" opacity=".8"/></svg>`,
    coin: () => `<svg viewBox="0 0 120 120" aria-hidden="true"><defs>
        <linearGradient id="cnA" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff2b0"/><stop offset=".5" stop-color="#f2b81f"/><stop offset="1" stop-color="#8a5a00"/></linearGradient></defs>
        <ellipse cx="60" cy="104" rx="40" ry="6" fill="#000" opacity=".35"/>
        <rect x="26" y="34" width="68" height="60" rx="14" fill="#6b4300" transform="rotate(-8 60 64)"/>
        <rect x="24" y="26" width="68" height="60" rx="14" fill="url(#cnA)" transform="rotate(-8 60 56)"/>
        <rect x="31" y="33" width="54" height="46" rx="10" fill="none" stroke="#7a4d00" stroke-width="3" transform="rotate(-8 60 56)"/>
        <text x="58" y="66" text-anchor="middle" font-family="Unbounded, sans-serif" font-weight="800" font-size="24" fill="#5a3700" transform="rotate(-8 60 56)">UC</text></svg>`,
    voucher: (p) => {
      const s = (p.subtitle || p.title).toLowerCase();
      const [c1, c2, l] = /моҳ|bulan|month|30/.test(s) ? ["#ffcf4d", "#e08a00", "M"] : /lite/.test(s) ? ["#6ea8ff", "#2747c8", "W"] : ["#d17bff", "#7a2bd6", "W"];
      return `<svg viewBox="0 0 120 120" aria-hidden="true"><defs><linearGradient id="vc${l}${c1.slice(1, 3)}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs>
        <ellipse cx="60" cy="100" rx="44" ry="6" fill="#000" opacity=".35"/>
        <rect x="16" y="34" width="88" height="56" rx="8" fill="url(#vc${l}${c1.slice(1, 3)})"/>
        <rect x="16" y="34" width="88" height="56" rx="8" fill="none" stroke="#fff" stroke-opacity=".35"/>
        <text x="30" y="72" font-family="Unbounded, sans-serif" font-weight="800" font-size="26" fill="#fff">${l}</text>
        <text x="98" y="46" text-anchor="end" font-family="Inter, sans-serif" font-weight="800" font-size="7" fill="#fff" opacity=".9">FREE FIRE</text>
        <g fill="#8fd3ff"><polygon points="62,80 70,70 78,80 70,92"/><polygon points="78,84 84,76 90,84 84,93" opacity=".85"/><polygon points="50,86 55,79 60,86 55,93" opacity=".8"/></g></svg>`;
    },
    ticket: () => `<svg viewBox="0 0 120 120" aria-hidden="true"><g transform="translate(46 46) scale(1.15)" fill="none" stroke="#8b8d96" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${P.ticket}</g></svg>`,
    star: () => `<svg viewBox="0 0 120 120" aria-hidden="true"><defs><linearGradient id="stA" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff3a8"/><stop offset=".6" stop-color="#ffc21a"/><stop offset="1" stop-color="#e07b00"/></linearGradient></defs>
        <ellipse cx="60" cy="102" rx="36" ry="6" fill="#000" opacity=".35"/>
        <path transform="translate(18 16) scale(3.5)" d="${"M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"}" fill="url(#stA)" stroke="#fff" stroke-opacity=".4" stroke-width=".4"/></svg>`,
  };
  const art = (p) => (ART[p.art] || ART.gem)(p);
  // Pictures from the supplier API (games and packs); drawn artwork is the fallback when there is none
  // or the picture fails to load.
  const safeImg = (u) => (typeof u === "string" && (/^https?:\/\/[^\s"'<>()]+$/.test(u) || /^\/media\/[\w.-]+(\?v=\d+)?$/.test(u)) ? u : "");
  const imgTag = (u, cls, fallback) => `<img class="${cls}" src="${esc(u)}" alt="" loading="lazy" decoding="async"
      onerror="this.outerHTML=this.dataset.fb ? decodeURIComponent(this.dataset.fb) : ''" data-fb="${encodeURIComponent(fallback || "")}">`;
  const productArt = (p) => safeImg(p.image) ? imgTag(p.image, "pimg", art(p)) : art(p);

  // ------------------------------------------------------------------ i18n
  const I18N = {
    tj: {
      morning: "Субҳ ба хайр", day: "Рӯз ба хайр", evening: "Шом ба хайр", night: "Шаби хуш",
      balance: "Баланс", topup: "Пур кардан", history: "Таърих", search: "Бозиро ёбед...", inCatalog: "бозӣ дар каталог",
      sensTitle: "Настройка ФФ «Ҳассосият»", sensSub: "Аз рӯи телефон ва соли барориш", free: "РОЙГОН",
      categories: "Категорияҳо", choose: "Бозиро интихоб кунед", buy: "Харидан", allGames: "Ҳамаи бозиҳо",
      home: "Асосӣ", purchases: "Харидҳо", support: "Дастгирӣ", profile: "Профил",
      multi: "Якчанд маҳсулот интихоб кардан", product: "Маҳсулот", gameId: "ID-и бозӣ", paste: "Гузоштан",
      payMethod: "Тарзи пардохт", agree: "Ман бо <a href='#/terms'>шартҳои истифода</a> розӣ ҳастам", pay: "Пардохт кардан",
      checkout: "Расмиатсозии фармоиш", chooseBank: "Бонкро интихоб кунед", fromBalance: "Аз баланс", available: "Дастрас",
      topupTitle: "Пур кардани баланс", addToBalance: "Ба балансатон илова", chooseAmount: "Маблағро интихоб кунед",
      amount: "Маблағ", onlyThese: "Танҳо ин маблағҳо дастрасанд", rateDC: "қурби ДС", somoni: "сомонӣ",
      orders: "Фармоишҳо", finance: "Молия", total: "Ҳамагӣ", spent: "Хароҷот", order: "фармоиш",
      all: "Ҳама", pending: "Интизор", done: "Иҷро шуда", cancelled: "Бекор", empty: "Ҳоло холӣ аст",
      st_done: "Иҷро шуд", st_processing: "Дар раванд", st_unpaid: "Интизори пардохт", st_cancelled: "Бекор",
      st_waiting: "Интизори чек", st_review: "Дар санҷиш", st_approved: "Тасдиқ шуд", st_rejected: "Рад шуд",
      tx_topup: "Пуркунӣ", tx_purchase: "Харид", tx_refund: "Бозгашт", tx_referral: "Бонуси ҳамкорӣ", tx_admin: "Ислоҳи админ",
      buyerLevel: "Сатҳи харидор", curLevel: "Сатҳи ҳозира", toNext: "То {n}: боз {x} харид лозим аст", maxLevel: "Сатҳи олӣ!",
      yourInfo: "Маълумоти шумо", ordersDone: "Фармоишҳо", spentAll: "Хароҷот", refs: "Дӯстон", since: "Аз сана",
      partner: "Барномаи ҳамкорӣ", partnerSub: "То {p}% аз ҳар хариди дӯстони шумо", settings: "Танзимот",
      theme: "Мавзӯъ", dark: "Торик", light: "Равшан", auto: "Автоматӣ", language: "Забон", currency: "Асъор", pin: "Рамзи PIN",
      verified: "Тасдиқшуда", safe: "Бехатар", notifications: "Огоҳиномаҳо", noNotif: "Огоҳинома нест",
      enterPin: "PIN-ро ворид кунед", newPin: "PIN-и навро ворид кунед", wrongPin: "PIN нодуруст",
      orderCreated: "Фармоиш қабул шуд!", requestCreated: "Дархост сохта шуд",
      requestHint: "Рақами корт ва дастур ба чати бот фиристода шуд. Маблағи дақиқро гузаронед ва расми чекро ба чат фиристед.",
      toChat: "Ба чат гузаштан", ok: "Хуб", uidError: "ID-и бозиро дуруст ворид кунед", copied: "Нусхабардорӣ шуд",
      chatWithSupport: "Ба дастгирӣ нависед", supportSub: "Ҳар рӯз, одатан дар 5 дақиқа ҷавоб медиҳем",
      reviews: "Баҳо ва шарҳҳо", reviewsSub: "Шарҳҳои харидорони мо", faq: "Саволҳои маъмул",
      faq1q: "Донат чанд вақт меояд?", faq1a: "Одатан то 1 дақиқа пас аз пардохт. Баъзан то 15 дақиқа.",
      faq2q: "Пароли аккаунт лозим аст?", faq2a: "Не. Танҳо ID-и бозӣ (UID) лозим аст. Ҳеҷ гоҳ паролро ба касе надиҳед.",
      faq3q: "Агар ID-ро хато ворид кунам?", faq3a: "Фавран ба дастгирӣ нависед. Агар донат ҳанӯз фиристода нашуда бошад, фармоишро ислоҳ мекунем.",
      faq4q: "Чӣ тавр пул пардохт кунам?", faq4a: "Алиф, Душанбе Сити, дигар бонкҳо, интиқол аз Русия ё банкомат. Расми чекро ба чати бот фиристед.",
      sensInfo: "Танзимоти тавсияшавандаро аз рӯи телефони худ гиред", brand: "Бренди телефон", ram: "Хотираи амалиётӣ (RAM)",
      year: "Соли барориш", generate: "Ҳисоб кардан", general: "Умумӣ", redDot: "Red Dot", scope2: "2x Scope", scope4: "4x Scope",
      sniper: "Снайпер", freeLook: "Free Look", fireBtn: "Андозаи тугмаи оташ", dpi: "DPI (тавсия)",
      selected: "Интихоб шуд", shareRef: "Даъват кардан", copyLink: "Нусха", terms: "Шартҳои истифода",
      termsText: "Пардохт пас аз тасдиқи чек ба баланс ворид мешавад. Фармоиш ба ID-е, ки шумо ворид кардед, фиристода мешавад — масъулияти дурустии ID бар дӯши харидор аст. Пас аз иҷро бозгашти пул имконнопазир аст. Агар фармоиш иҷро нашавад, маблағ ба баланс баргардонида мешавад.",
      checking: "Санҷиши аккаунт…", accountNotFound: "Аккаунт бо ин ID ёфт нашуд", account: "Аккаунт", noMethods: "Ҳоло тарзи пардохт дастрас нест. Ба дастгирӣ нависед.", cats: "категория", noResults: "Ҳеҷ чиз ёфт нашуд", insufficient: "Баланс нокифоя — бонкро интихоб кунед",
    },
    ru: {
      morning: "Доброе утро", day: "Добрый день", evening: "Добрый вечер", night: "Доброй ночи",
      balance: "Баланс", topup: "Пополнить", history: "История", search: "Найти игру...", inCatalog: "игр в каталоге",
      sensTitle: "Настройка FF «Чувствительность»", sensSub: "По модели телефона и году выпуска", free: "БЕСПЛАТНО",
      categories: "Категории", choose: "Выберите игру", buy: "Купить", allGames: "Все игры",
      home: "Главная", purchases: "Покупки", support: "Поддержка", profile: "Профиль",
      multi: "Выбрать несколько товаров", product: "Товар", gameId: "ID в игре", paste: "Вставить",
      payMethod: "Способ оплаты", agree: "Я согласен с <a href='#/terms'>условиями использования</a>", pay: "Оплатить",
      checkout: "Оформление заказа", chooseBank: "Выберите банк", fromBalance: "С баланса", available: "Доступно",
      topupTitle: "Пополнение баланса", addToBalance: "Пополнение баланса", chooseAmount: "Выберите сумму",
      amount: "Сумма", onlyThese: "Доступны только эти суммы", rateDC: "курс ДС", somoni: "сомони",
      orders: "Заказы", finance: "Финансы", total: "Всего", spent: "Расходы", order: "заказов",
      all: "Все", pending: "Ожидание", done: "Выполнено", cancelled: "Отмена", empty: "Пока пусто",
      st_done: "Выполнен", st_processing: "В процессе", st_unpaid: "Ожидает оплаты", st_cancelled: "Отменён",
      st_waiting: "Ждём чек", st_review: "На проверке", st_approved: "Подтверждено", st_rejected: "Отклонено",
      tx_topup: "Пополнение", tx_purchase: "Покупка", tx_refund: "Возврат", tx_referral: "Партнёрский бонус", tx_admin: "Корректировка",
      buyerLevel: "Уровень покупателя", curLevel: "Текущий уровень", toNext: "До {n}: осталось {x}", maxLevel: "Максимальный уровень!",
      yourInfo: "Ваши данные", ordersDone: "Заказы", spentAll: "Потрачено", refs: "Друзья", since: "С нами с",
      partner: "Партнёрская программа", partnerSub: "До {p}% с каждой покупки ваших друзей", settings: "Настройки",
      theme: "Тема", dark: "Тёмная", light: "Светлая", auto: "Авто", language: "Язык", currency: "Валюта", pin: "PIN-код",
      verified: "Подтверждён", safe: "Безопасно", notifications: "Уведомления", noNotif: "Нет уведомлений",
      enterPin: "Введите PIN", newPin: "Придумайте PIN", wrongPin: "Неверный PIN",
      orderCreated: "Заказ принят!", requestCreated: "Заявка создана",
      requestHint: "Номер карты и инструкция отправлены в чат бота. Переведите точную сумму и отправьте фото чека в чат.",
      toChat: "Перейти в чат", ok: "Хорошо", uidError: "Введите корректный ID", copied: "Скопировано",
      chatWithSupport: "Написать в поддержку", supportSub: "Каждый день, обычно отвечаем за 5 минут",
      reviews: "Оценки и отзывы", reviewsSub: "Отзывы наших покупателей", faq: "Частые вопросы",
      faq1q: "Как быстро приходит донат?", faq1a: "Обычно до 1 минуты после оплаты. Иногда до 15 минут.",
      faq2q: "Нужен пароль от аккаунта?", faq2a: "Нет. Нужен только игровой ID (UID). Никогда никому не сообщайте пароль.",
      faq3q: "Что если я ошибся в ID?", faq3a: "Сразу напишите в поддержку. Если донат ещё не отправлен — исправим заказ.",
      faq4q: "Как оплатить?", faq4a: "Алиф, Душанбе Сити, другие банки, перевод из России или банкомат. Отправьте фото чека в чат бота.",
      sensInfo: "Получите рекомендуемые настройки под ваш телефон", brand: "Бренд телефона", ram: "Оперативная память (RAM)",
      year: "Год выпуска", generate: "Рассчитать", general: "Общая", redDot: "Red Dot", scope2: "Прицел 2x", scope4: "Прицел 4x",
      sniper: "Снайпер", freeLook: "Свободный обзор", fireBtn: "Размер кнопки огня", dpi: "DPI (рекомендация)",
      selected: "Выбрано", shareRef: "Пригласить", copyLink: "Копировать", terms: "Условия использования",
      termsText: "Оплата зачисляется на баланс после проверки чека. Заказ отправляется на указанный вами ID — ответственность за правильность ID несёт покупатель. После выполнения возврат невозможен. Если заказ не выполнен, сумма возвращается на баланс.",
      checking: "Проверяем аккаунт…", accountNotFound: "Аккаунт с таким ID не найден", account: "Аккаунт", noMethods: "Сейчас способы оплаты недоступны. Напишите в поддержку.", cats: "категорий", noResults: "Ничего не найдено", insufficient: "Недостаточно средств — выберите банк",
    },
  };
  let LANG = "tj";
  const T = (k, vars) => {
    let s = (I18N[LANG] && I18N[LANG][k]) || I18N.tj[k] || k;
    if (vars) for (const [a, b] of Object.entries(vars)) s = s.replace(`{${a}}`, b);
    return s;
  };

  // ------------------------------------------------------------------ helpers
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
  };
  const haptic = (type = "light") => { try { tg && tg.HapticFeedback.impactOccurred(type); } catch { /* not in Telegram */ } };
  const S = { boot: null, user: null, catalog: [], hidden: store.get("hideBalance", false), multi: false, selected: new Map(),
              checkout: null, historyTab: "orders", historyFilter: "all", history: null, search: "" };

  function fmtNum(n, digits = 2) {
    const [int, frac] = Math.abs(Number(n)).toFixed(digits).split(".");
    return (Number(n) < 0 ? "-" : "") + int.replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (frac ? "." + frac : "");
  }
  function money(amount, opts = {}) {
    const cur = opts.cur || (S.user && S.user.currency) || "TJS";
    if (cur === "RUB") return { v: fmtNum(Math.round(amount / S.boot.rub_rate), 0), u: "₽" };
    return { v: fmtNum(amount), u: "см" };
  }
  const moneyHTML = (amount, opts) => { const m = money(amount, opts); return `${m.v}<small>${m.u}</small>`; };
  const moneyText = (amount, opts) => { const m = money(amount, opts); return `${m.v} ${m.u}`; };
  const initials = (u) => ((u.first_name || u.username || "U").replace(/[^\p{L}\p{N}]/gu, "").slice(0, 2) || "U").toUpperCase();
  const dateKey = (ts) => new Date(ts * 1000).toLocaleDateString(LANG === "ru" ? "ru-RU" : "ru-RU", { day: "numeric", month: "short", year: "numeric" });
  const timeOf = (ts) => new Date(ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });

  function toast(msg, isErr = false) {
    $toast.textContent = msg;
    $toast.className = "toast show" + (isErr ? " err" : "");
    clearTimeout(toast.t);
    toast.t = setTimeout(() => ($toast.className = "toast"), 2600);
  }

  async function api(path, body) {
    const headers = { "Content-Type": "application/json" };
    if (tg && tg.initData) headers.Authorization = "tma " + tg.initData;
    const res = await fetch("/api" + path, { method: body ? "POST" : "GET", headers, body: body ? JSON.stringify(body) : undefined });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Хатогӣ. Боз кӯшиш кунед");
    return data;
  }

  function applyTheme() {
    let theme = (S.user && S.user.theme) || "dark";
    if (theme === "auto") theme = tg && tg.colorScheme ? tg.colorScheme : (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    document.documentElement.dataset.theme = theme;
    const bg = theme === "light" ? "#f5f5fb" : "#0d0d1f";
    try { tg.setHeaderColor(bg); tg.setBackgroundColor(bg); tg.setBottomBarColor && tg.setBottomBarColor(bg); } catch { /* old client */ }
  }

  function openLink(url) {
    if (!url) return;
    if (tg && /^https:\/\/t\.me\//.test(url)) tg.openTelegramLink(url);
    else if (tg) tg.openLink(url);
    else window.open(url, "_blank");
  }

  function copy(text) {
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => toast(T("copied")), () => {
      const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); toast(T("copied")); } catch { /* ignore */ } ta.remove();
    });
  }

  const catById = (id) => S.catalog.find((c) => c.id === id);
  const productById = (id) => { for (const c of S.catalog) for (const p of c.products) if (p.id === id) return [p, c]; return [null, null]; };

  // ------------------------------------------------------------------ router
  const ROOT = new Set(["home", "history", "support", "profile"]);
  function route() {
    const h = location.hash.replace(/^#\/?/, "");
    const [name, arg] = h.split("/");
    return { name: name || "home", arg: arg ? decodeURIComponent(arg) : "" };
  }
  const go = (hash) => { if (location.hash === hash) render(); else location.hash = hash; };

  function render() {
    const r = route();
    const view = VIEWS[r.name] || VIEWS.home;
    closeSheet();
    $app.innerHTML = view(r.arg);
    $app.classList.toggle("no-tabbar", !ROOT.has(r.name));
    renderTabbar(ROOT.has(r.name) ? r.name : null);
    if (view.after) view.after(r.arg);
    window.scrollTo(0, 0);
    if (tg) {
      if (ROOT.has(r.name)) tg.BackButton.hide(); else tg.BackButton.show();
    }
  }

  function renderTabbar(active) {
    $tabbar.hidden = !active;
    if (!active) return;
    const tabs = [["home", "homeF", T("home")], ["history", "bagF", T("purchases")], ["support", "headsetF", T("support")], ["profile", "userF", T("profile")]];
    $tabbar.innerHTML = tabs.map(([id, ic, label]) =>
      `<button class="${id === active ? "on" : ""}" data-go="#/${id === "home" ? "" : id}" aria-label="${esc(label)}" ${id === active ? 'aria-current="page"' : ""}>${icon(ic)}<span>${esc(label)}</span></button>`).join("");
  }

  const topbar = (title) => `<div class="topbar"><button class="back" data-back aria-label="Back">${icon("back")}</button><h1 class="page-title">${esc(title)}</h1><span></span></div>`;

  // ------------------------------------------------------------------ views
  const VIEWS = {};

  VIEWS.home = () => {
    const u = S.user;
    const hr = new Date().getHours();
    const [greet, gic] = hr < 5 ? [T("night"), "moon"] : hr < 12 ? [T("morning"), "sun"] : hr < 17 ? [T("day"), "sun"] : hr < 22 ? [T("evening"), "moon"] : [T("night"), "moon"];
    const bal = money(u.balance);
    const featured = S.catalog.filter((c) => c.group === "featured");
    const groups = ["games", "ff_regions", "services", "telegram"].map((g) => [g, S.catalog.filter((c) => c.group === g)]).filter(([, l]) => l.length);
    const groupIcon = { games: "gamepad", ff_regions: "flame", services: "sparkles", telegram: "send" };
    return `
      <header class="header">
        <div class="avatar">${u.photo_url ? `<img src="${esc(u.photo_url)}" alt="">` : esc(initials(u))}</div>
        <div class="grow"><div class="greet">${icon(gic)}${esc(greet)}</div><div class="hello ellipsis">${esc(u.username || u.first_name || "")}</div></div>
        <button class="icon-btn" data-go="#/notifications" aria-label="${esc(T("notifications"))}">${icon("bell")}${u.unread ? `<span class="badge">${u.unread > 9 ? "9+" : u.unread}</span>` : ""}</button>
      </header>
      <section class="balance" aria-label="${esc(T("balance"))}">
        <div class="balance-label">${esc(T("balance").toUpperCase())}<button data-act="toggle-hide" aria-label="Show/hide">${icon(S.hidden ? "eyeOff" : "eye")}</button></div>
        <div class="balance-amount">${S.hidden ? "•••••" : bal.v}<small>${bal.u.toUpperCase()}</small></div>
        <div class="balance-actions">
          <button class="pill-btn" data-go="#/topup"><span class="ic">${icon("plus")}</span><span class="sep"></span>${esc(T("topup"))}</button>
          <button class="pill-btn" data-act="history-finance"><span class="ic">${icon("history")}</span><span class="sep"></span>${esc(T("history"))}</button>
        </div>
      </section>
      <label class="search">${icon("search")}<span class="sr-only">${esc(T("search"))}</span>
        <input id="q" type="search" placeholder="${esc(T("search"))}" value="${esc(S.search)}" autocomplete="off">
        <span class="chip">${S.catalog.length} ${esc(T("inCatalog"))}</span></label>
      <div id="search-results"></div>
      <button class="promo" data-go="#/sens"><span class="ring">${icon("crosshair")}</span>
        <span class="grow"><b>${esc(T("sensTitle"))}</b><span class="muted ellipsis">${esc(T("sensSub"))}</span></span><span class="btn-tag">${esc(T("free"))}</span></button>
      <div class="section-title">${esc(T("categories"))}<small>${esc(T("choose"))}</small></div>
      ${featured.map(banner).join("")}
      ${groups.map(([g, list]) => g === "telegram" && list.length === 1
        ? `<div class="acc"><button data-go="#/cat/${list[0].id}">${safeImg(list[0].image) ? `<span class="logo-sq" style="width:28px;height:28px;border-radius:8px">${imgTag(list[0].image, "", "")}</span>` : icon("send")}<span>Telegram</span>${icon("right", "chev")}</button></div>`
        : `<div class="acc" data-acc><button aria-expanded="false">${icon(groupIcon[g])}<span>${esc(groupTitle(g))} (${list.length})</span>${icon("down", "chev")}</button>
            <div class="acc-body">${list.map(gameRow).join("")}</div></div>`).join("")}
    `;
  };
  VIEWS.home.after = () => {
    const q = document.getElementById("q");
    const out = document.getElementById("search-results");
    const run = () => {
      S.search = q.value.trim();
      const s = S.search.toLowerCase();
      if (!s) { out.innerHTML = ""; return; }
      const found = S.catalog.filter((c) => c.title.toLowerCase().includes(s));
      out.innerHTML = `<div class="list" style="margin-top:10px;padding:6px">${found.length ? found.map(gameRow).join("") : `<div class="empty">${esc(T("noResults"))}</div>`}</div>`;
    };
    q.addEventListener("input", run);
    run();
  };

  function groupTitle(g) {
    if (g === "games") return T("allGames");
    if (g === "ff_regions") return LANG === "ru" ? "Free Fire — другие регионы" : "Free Fire — дигар регионҳо";
    if (g === "services") return LANG === "ru" ? "Сервисы" : "Хизматрасониҳо";
    return S.boot.groups[g] || g;
  }

  function banner(c) {
    const [c1, c2] = c.colors;
    return `<button class="banner" data-go="#/cat/${c.id}" style="--accent:${c1}" aria-label="${esc(c.title)}">
      ${safeImg(c.banner_image)
        ? `<span class="bg photo" style="background:linear-gradient(90deg, rgba(8,8,20,.78) 0%, rgba(8,8,20,.35) 45%, transparent 70%), url('${esc(c.banner_image)}') center / cover no-repeat, ${c2}"></span>`
        : `<span class="bg ${safeImg(c.image) ? "photo" : ""}" data-mark="${safeImg(c.image) ? "" : esc(c.short)}" style="background:${safeImg(c.image)
        ? `linear-gradient(90deg, ${c2}f2 0%, ${c2}b3 45%, transparent 85%), url('${esc(c.image)}') right center / cover no-repeat, ${c2}`
        : `radial-gradient(circle at 80% 30%, ${c1}aa, transparent 55%), linear-gradient(120deg, ${c2}, #0a0a0c)`}"></span>`}
      <span class="content"><span class="kicker" style="color:${c1}">${esc(c.banner_kicker || "")}</span>
      <span class="big" style="display:block;--big:${(c.banner || c.title).length > 6 ? 30 : 40}px">${esc(c.banner || c.title)}</span>
      <span class="buy">${esc(T("buy"))}<i>${icon("arrow")}</i></span></span></button>`;
  }

  function gameRow(c) {
    const [c1, c2] = c.colors;
    const logo = safeImg(c.image) ? imgTag(c.image, "", esc(c.short)) : esc(c.short);
    return `<button class="game-row" data-go="#/cat/${c.id}"><span class="logo-sq" style="background:linear-gradient(145deg, ${c1}, ${c2})">${logo}</span>
      <span class="grow"><span class="ellipsis" style="display:block;font-weight:700">${esc(c.title)}</span>
      <span class="muted" style="font-size:13px">${c.products.length} ${LANG === "ru" ? "товаров" : "маҳсулот"} · ${esc(T("buy").toLowerCase())} ${moneyText(Math.min(...c.products.map((p) => p.price)))}+</span></span>${icon("right", "chev")}</button>`;
  }

  VIEWS.group = (g) => {
    const list = S.catalog.filter((c) => c.group === g);
    return `${topbar(groupTitle(g))}<div class="list" style="padding:6px">${list.map(gameRow).join("") || `<div class="empty">${esc(T("empty"))}</div>`}</div>`;
  };

  VIEWS.cat = (id) => {
    const c = catById(id);
    if (!c) return `${topbar("")}<div class="empty">${esc(T("noResults"))}</div>`;
    if (S.curCat !== id) { S.curCat = id; S.tab = null; S.selected.clear(); }
    const tab = S.tab && c.tabs.some((t) => t.id === S.tab) ? S.tab : c.tabs[0].id;
    S.tab = tab;
    const products = c.products.filter((p) => p.tab === tab);
    const tabs = c.tabs.length > 1 ? `<div class="seg" role="tablist">${c.tabs.map((t) =>
      `<button role="tab" aria-selected="${t.id === tab}" class="${t.id === tab ? "on" : ""}" data-tab="${t.id}">${icon(t.icon)}${esc(t.title)}</button>`).join("")}</div>` : "";
    const selTotal = [...S.selected.entries()].reduce((s, [pid, q]) => s + (productById(pid)[0]?.price || 0) * q, 0);
    return `${topbar(c.title)}${tabs}
      <div class="toggle-row"><span class="ic">${icon("listChecks")}</span><span class="grow muted" style="font-weight:600">${esc(T("multi"))}</span>
        <button class="switch" role="switch" aria-checked="${S.multi}" data-act="multi" aria-label="${esc(T("multi"))}"></button></div>
      <div class="grid">${products.map((p) => productCard(p, c)).join("")}</div>
      ${S.multi && S.selected.size ? `<div class="cta-bar"><button class="cta" data-act="buy-selected">${icon("cart")}${esc(T("buy"))} (${S.selected.size}) · ${moneyText(selTotal)}</button></div>` : ""}`;
  };

  function productCard(p, c) {
    const sel = S.selected.has(p.id);
    const isMain = p.art === "gem" || p.art === "coin";
    return `<div class="prod ${sel ? "sel" : ""}" data-prod="${p.id}" role="button" tabindex="0" aria-label="${esc(p.title)}">
      ${S.multi ? `<span class="check">${sel ? icon("check") : ""}</span>` : ""}
      <div class="art">${productArt(p)}${!isMain ? `<button class="info-btn" data-info="${p.id}" aria-label="Info">${icon("info")}</button>` : ""}</div>
      <div class="title">${esc(p.title)}</div>${p.subtitle ? `<div class="sub">${esc(p.subtitle)}</div>` : ""}
      <div class="foot"><div class="price">${moneyHTML(p.price)}</div>
      <button class="cart-btn ${isMain ? "accent" : ""}" data-cart="${p.id}" aria-label="${esc(T("buy"))}">${icon("cart")}</button></div></div>`;
  }

  // ---- checkout
  VIEWS.checkout = () => {
    const co = S.checkout;
    if (!co || !co.items.length) { setTimeout(() => history.back(), 0); return ""; }
    const c = catById(co.cat);
    const lines = co.items.map((it) => [productById(it.product_id)[0], it.qty]).filter(([p]) => p);
    const total = lines.reduce((s, [p, q]) => s + p.price * q, 0);
    co.total = total;
    const firstBank = S.boot.methods[0] ? S.boot.methods[0].id : "balance";
    if (!co.method || (co.method !== "balance" && !S.boot.methods.some((m) => m.id === co.method))) {
      co.method = S.user.balance >= total ? "balance" : firstBank;
    }
    const title = lines.map(([p, q]) => p.title + (q > 1 ? ` ×${q}` : "")).join(", ");
    const fields = (lines[0] && lines[0][0].fields && lines[0][0].fields.length) ? lines[0][0].fields
      : [{ key: "player_id", label: c ? c.uid_label : T("gameId"), placeholder: c ? c.uid_placeholder : "" }];
    co.fieldDefs = fields;
    co.fields = co.fields || {};
    const f0 = fields[0];
    if (!co.fields[f0.key] && co.uid) co.fields[f0.key] = co.uid;
    return `${topbar(T("checkout"))}
      <div class="summary"><span class="ic">${c && safeImg(c.image) ? imgTag(c.image, "", icon("gem")) : icon(lines[0] && lines[0][0].art === "coin" ? "coins" : "gem")}</span>
        <span class="grow"><span class="k">${esc(T("product").toUpperCase())}</span><span class="v" style="display:block">${esc(title)}</span></span>
        <span class="amt">${moneyHTML(total)}</span></div>
      <label class="label" for="uid">${esc(f0.label)}</label>
      <div class="field" id="uid-field">${icon(f0.key === "telegram_username" ? "send" : "hash")}<input id="uid" data-field="${esc(f0.key)}"
        inputmode="${f0.key === "player_id" ? "numeric" : "text"}" autocomplete="off" placeholder="${esc(f0.placeholder)}" value="${esc(co.fields[f0.key] || "")}">
        <button class="ghost-btn" data-act="paste">${icon("clipboard")}${esc(T("paste"))}</button></div>
      <div id="uid-err"></div><div id="uid-nick">${nickHTML(co)}</div>
      ${fields.slice(1).map((f) => `<label class="label" for="f-${esc(f.key)}">${esc(f.label)}</label>
        <div class="field">${icon("hash")}<input id="f-${esc(f.key)}" data-field="${esc(f.key)}" autocomplete="off" placeholder="${esc(f.placeholder)}" value="${esc(co.fields[f.key] || "")}"></div>`).join("")}
      <span class="label">${esc(T("payMethod"))}</span>
      <button class="select" data-act="choose-method">${methodBadge(co.method)}<span class="grow ellipsis">${esc(methodTitle(co.method))}</span><span class="chev-box">${icon("down")}</span></button>
      ${co.method === "balance" && S.user.balance < total ? `<div class="err-text">${esc(T("insufficient"))}</div>` : ""}
      <div class="check-row"><button class="box" role="checkbox" aria-checked="${!!co.agree}" data-act="agree" aria-label="agree">${co.agree ? icon("check") : ""}</button><span>${T("agree")}</span></div>
      <div class="cta-bar"><button class="cta" id="pay-btn" data-act="pay" ${co.agree ? "" : "disabled"}>${icon("card")}${esc(T("pay"))}</button></div>`;
  };
  VIEWS.checkout.after = () => {
    const co = S.checkout;
    if (!co || !document.getElementById("uid")) return;
    document.querySelectorAll("[data-field]").forEach((input) => input.addEventListener("input", () => {
      co.fields[input.dataset.field] = input.value.trim();
      co.uid = co.fields[co.fieldDefs[0].key] || "";
      document.getElementById("uid-field").classList.remove("error");
      document.getElementById("uid-err").innerHTML = "";
      scheduleNickCheck();
    }));
    if (co.uid && co.nick === undefined) scheduleNickCheck();
  };

  // Player nickname check (supplier /accounts/check) — shows who will receive the donat before paying.
  function nickHTML(co) {
    if (!co || co.nick === undefined || co.nick === null) return "";
    if (co.nick === "...") return `<div class="nick muted">${esc(T("checking"))}</div>`;
    if (co.nick === false) return `<div class="err-text">${esc(T("accountNotFound"))}</div>`;
    return co.nick ? `<div class="nick">${icon("check")} ${esc(T("account"))}: <b>${esc(co.nick)}</b></div>` : "";
  }
  function scheduleNickCheck() {
    const co = S.checkout;
    clearTimeout(scheduleNickCheck.t);
    co.nick = undefined;
    const box = document.getElementById("uid-nick");
    if (box) box.innerHTML = "";
    if ((co.uid || "").length < 4) return;
    scheduleNickCheck.t = setTimeout(async () => {
      const key = JSON.stringify(co.fields);
      co.nick = "..."; if (box) box.innerHTML = nickHTML(co);
      try {
        const r = await api("/check", { product_id: co.items[0].product_id, fields: co.fields });
        if (JSON.stringify(co.fields) !== key) return;  // the customer kept typing
        co.nick = !r.supported ? null : (r.valid ? (r.player_name || "") : false);
      } catch { co.nick = null; }
      const b = document.getElementById("uid-nick");
      if (b) b.innerHTML = nickHTML(co);
    }, 700);
  }

  const BANK_STYLE = {
    alif: ["#fff", "#16a34a", "alif"], dc: ["#fff", "#1d4ed8", "DC"], bank: ["var(--tint-1)", "var(--primary)", "🏦"],
    rus: ["#fff", "#16a34a", "RU"], balance: ["var(--tint-1)", "var(--primary)", ""],
  };
  function methodBadge(id) {
    if (id === "balance") return `<span class="bank-logo" style="background:var(--tint-1);color:var(--primary-text);border:1px solid var(--tint-border)">${icon("wallet")}</span>`;
    const m = S.boot.methods.find((x) => x.id === id) || {};
    const [bg, fg, label] = BANK_STYLE[m.icon] || BANK_STYLE.bank;
    if (m.icon === "bank") return `<span class="bank-logo" style="background:var(--tint-1);color:var(--primary-text);border:1px solid var(--tint-border)">${icon("card")}</span>`;
    return `<span class="bank-logo" style="background:${bg};color:${fg}">${esc(label)}</span>`;
  }
  const methodTitle = (id) => id === "balance" ? `${T("fromBalance")} · ${moneyText(S.user.balance)}` : (S.boot.methods.find((m) => m.id === id) || {}).title || id;

  function methodSheet(current, withBalance, onPick) {
    const opts = (withBalance ? [{ id: "balance", title: T("fromBalance"), subtitle: `${T("available")}: ${moneyText(S.user.balance)}` }] : []).concat(S.boot.methods);
    openSheet(`<div class="sheet-head"><h3>${esc(T("chooseBank"))}</h3><button class="close-btn" data-close aria-label="Close">${icon("x")}</button></div>
      ${opts.map((m) => `<button class="opt ${m.id === current ? "on" : ""}" data-pick="${m.id}">${methodBadge(m.id)}
        <span class="grow"><b>${esc(m.title)}</b><span class="muted">${esc(m.subtitle)}</span></span><span class="radio">${m.id === current ? icon("check") : ""}</span></button>`).join("")}`,
      (el) => el.querySelectorAll("[data-pick]").forEach((b) => b.addEventListener("click", () => { haptic(); onPick(b.dataset.pick); closeSheet(); })));
  }

  async function pay() {
    const co = S.checkout;
    const c = catById(co.cat);
    const uid = (co.uid || "").trim();
    const f0 = co.fieldDefs[0];
    const okFirst = f0.key === "player_id" ? /^[A-Za-z0-9_-]{3,32}$/.test(uid)
      : f0.key === "telegram_username" ? /^@?[A-Za-z0-9_]{4,32}$/.test(uid) : uid.length >= 3;
    const missing = co.fieldDefs.slice(1).find((f) => !(co.fields[f.key] || "").trim());
    if (!okFirst || co.nick === false || missing) {
      document.getElementById("uid-field").classList.add("error");
      document.getElementById("uid-err").innerHTML = `<div class="err-text">${esc(co.nick === false ? T("accountNotFound") : missing ? missing.label : T("uidError"))}</div>`;
      document.getElementById(missing ? "f-" + missing.key : "uid").focus();
      return;
    }
    if (co.method === "balance" && S.user.balance < co.total) { toast(T("insufficient"), true); return; }
    const btn = document.getElementById("pay-btn");
    btn.disabled = true; btn.innerHTML = `<span class="spin"></span>`;
    try {
      const uids = store.get("uids", {}); uids[co.cat] = uid; store.set("uids", uids);
      const res = await api("/order", { items: co.items, uid, fields: co.fields, method: co.method });
      haptic("medium");
      S.selected.clear(); S.multi = false;
      await refreshUser();
      if (res.status === "unpaid") requestSheet(res);
      else { toast(T("orderCreated")); S.historyTab = "orders"; go("#/history"); }
    } catch (e) {
      toast(e.message, true);
      btn.disabled = false; btn.innerHTML = `${icon("card")}${esc(T("pay"))}`;
    }
  }

  function requestSheet(res) {
    openSheet(`<div class="center" style="padding:8px 4px 4px">
        <div style="width:72px;height:72px;margin:0 auto 14px;border-radius:50%;display:grid;place-items:center;background:var(--primary-soft);color:var(--primary-text)">${icon("receipt")}</div>
        <h3 style="margin:0 0 6px;font-size:21px">${esc(T("requestCreated"))}</h3>
        <div class="chip" style="margin-bottom:12px">${esc(res.topup)} · ${moneyText(res.amount, { cur: "TJS" })}</div>
        <p class="muted" style="margin:0 0 20px">${esc(T("requestHint"))}</p>
        <button class="cta" data-act="to-chat">${icon("send")}${esc(T("toChat"))}</button>
        <button class="cta" data-close style="margin-top:10px;background:var(--surface-3);color:var(--text)">${esc(T("ok"))}</button></div>`);
  }

  // ---- top-up
  VIEWS.topup = () => {
    const tp = S.topup || (S.topup = { amount: 0, method: S.boot.methods[0] ? S.boot.methods[0].id : "" });
    if (!S.boot.methods.length) return `${topbar(T("topupTitle"))}<div class="empty">${icon("card")}<div>${esc(T("noMethods"))}</div></div>`;
    const rub = tp.amount ? Math.round(tp.amount / S.boot.rub_rate) : 0;
    return `${topbar(T("topupTitle"))}
      <div class="summary"><span class="ic">${icon("wallet")}</span><span class="grow"><span class="k">${esc(T("addToBalance").toUpperCase())}</span>
        <span class="v" style="display:block">${esc(T("chooseAmount"))}</span></span><span class="amt" style="color:var(--muted)">${moneyHTML(tp.amount, { cur: "TJS" })}</span></div>
      <div class="card" style="margin-top:14px;border-radius:22px">
        <div class="label center" style="margin-top:0">${esc(T("amount"))}</div>
        <div class="amounts">${S.boot.topup_amounts.map((a) => `<button class="amount ${a === tp.amount ? "on" : ""}" data-amount="${a}">${a}<small>СМ</small></button>`).join("")}</div>
        <p class="muted" style="font-size:13px;margin:12px 2px 0">${esc(T("onlyThese"))}</p>
        <div class="conv"><div><b>${fmtNum(tp.amount, 0)}</b><span>${esc(T("somoni"))}</span></div><div><b>${fmtNum(rub, 0)}</b><span>₽</span></div>
          <span class="rate">1 ₽ = ${S.boot.rub_rate} ${esc(T("somoni"))} · ${esc(T("rateDC"))}</span></div>
      </div>
      <span class="label">${esc(T("payMethod"))}</span>
      <button class="select" data-act="topup-method">${methodBadge(tp.method)}<span class="grow ellipsis">${esc(methodTitle(tp.method))}</span><span class="chev-box">${icon("down")}</span></button>
      <div class="cta-bar"><button class="cta" id="topup-btn" data-act="do-topup" ${tp.amount ? "" : "disabled"}>${icon("wallet")}${esc(T("topup"))}</button></div>`;
  };

  async function doTopup() {
    const btn = document.getElementById("topup-btn");
    btn.disabled = true; btn.innerHTML = `<span class="spin"></span>`;
    try {
      const res = await api("/topup", { amount: S.topup.amount, method: S.topup.method });
      haptic("medium");
      requestSheet(res);
    } catch (e) { toast(e.message, true); }
    btn.disabled = false; btn.innerHTML = `${icon("wallet")}${esc(T("topup"))}`;
  }

  // ---- history
  VIEWS.history = () => {
    const h = S.history;
    const tabs = `<div class="seg"><button class="${S.historyTab === "orders" ? "on" : ""}" data-htab="orders">${esc(T("orders"))}</button>
      <button class="${S.historyTab === "finance" ? "on" : ""}" data-htab="finance">${esc(T("finance"))}</button></div>`;
    if (!h) return `<h1 class="page-title">${esc(T("history"))}</h1>${tabs}<div class="empty"><span class="spin" style="display:inline-block;width:28px;height:28px;border:3px solid var(--border);border-top-color:var(--primary-text);border-radius:50%;animation:spin .8s linear infinite"></span></div>`;
    let body;
    if (S.historyTab === "orders") {
      const doneSum = h.orders.filter((o) => o.status === "done").reduce((s, o) => s + o.amount, 0);
      const map = { all: null, pending: ["processing", "unpaid"], done: ["done"], cancelled: ["cancelled"] };
      const list = h.orders.filter((o) => !map[S.historyFilter] || map[S.historyFilter].includes(o.status));
      body = `<div class="stats2"><div><span class="ic" style="background:var(--primary-soft);color:var(--primary-text)">${icon("package")}</span>
          <span><span class="k">${esc(T("total").toUpperCase())}</span><span class="v" style="display:block">${h.orders.length}<small>${esc(T("order"))}</small></span></span></div>
        <div><span class="ic" style="background:rgba(34,197,94,.14);color:var(--success)">${icon("receipt")}</span>
          <span><span class="k">${esc(T("spent").toUpperCase())}</span><span class="v" style="display:block">${moneyHTML(doneSum)}</span></span></div></div>
        <div class="seg sm" style="margin-top:14px">${["all", "pending", "done", "cancelled"].map((f) =>
          `<button class="${S.historyFilter === f ? "on" : ""}" data-hfilter="${f}">${esc(T(f))}</button>`).join("")}</div>
        ${grouped(list, (o) => `<div class="item"><span class="ic">${icon(o.items[0] && /ваучер|level/i.test(o.items[0].title) ? "ticket" : "package")}</span>
          <span class="grow"><span class="t ellipsis" style="display:block">${esc(o.items.map((i) => i.title + (i.qty > 1 ? " ×" + i.qty : "")).join(", "))}</span>
          <span class="s ellipsis" style="display:block">${timeOf(o.created_at)} · ${esc(methodName(o.method))} · ID ${esc(o.uid)}</span></span>
          <span class="r"><b>${moneyText(o.amount)}</b><br><span class="status ${o.status}">${esc(T("st_" + o.status))}</span></span></div>`)}`;
    } else {
      const rows = h.transactions.map((t) => ({ ...t, _k: "tx" })).concat(h.topups.filter((t) => t.status !== "approved").map((t) => ({ ...t, _k: "top" })))
        .sort((a, b) => b.created_at - a.created_at);
      const income = h.transactions.filter((t) => t.amount > 0).reduce((s, t) => s + t.amount, 0);
      body = `<div class="stats2"><div><span class="ic" style="background:rgba(34,197,94,.14);color:var(--success)">${icon("plus")}</span>
          <span><span class="k">${esc(T("topup").toUpperCase())}</span><span class="v" style="display:block">${moneyHTML(income)}</span></span></div>
        <div><span class="ic" style="background:var(--primary-soft);color:var(--primary-text)">${icon("wallet")}</span>
          <span><span class="k">${esc(T("balance").toUpperCase())}</span><span class="v" style="display:block">${moneyHTML(S.user.balance)}</span></span></div></div>
        ${grouped(rows, (r) => r._k === "tx"
          ? `<div class="item"><span class="ic">${icon(r.amount > 0 ? "plus" : "cart")}</span><span class="grow"><span class="t" style="display:block">${esc(T("tx_" + r.kind))}</span>
              <span class="s">${timeOf(r.created_at)} · ${esc(r.ref || "")}</span></span><span class="r"><b class="${r.amount > 0 ? "plus" : ""}">${r.amount > 0 ? "+" : ""}${moneyText(r.amount)}</b></span></div>`
          : `<div class="item"><span class="ic">${icon("receipt")}</span><span class="grow"><span class="t" style="display:block">${esc(r.code)}</span>
              <span class="s">${timeOf(r.created_at)} · ${esc(methodName(r.method))}</span></span><span class="r"><b>${moneyText(r.amount)}</b><br><span class="status ${r.status}">${esc(T("st_" + r.status))}</span></span></div>`)}`;
    }
    return `<h1 class="page-title">${esc(T("history"))}</h1>${tabs}${body}`;
  };
  VIEWS.history.after = () => { if (!S.history) loadHistory(); };
  const methodName = (id) => id === "balance" ? T("balance") : (S.boot.methods.find((m) => m.id === id) || {}).title || id;

  function grouped(list, rowFn) {
    if (!list.length) return `<div class="empty">${icon("package")}<div>${esc(T("empty"))}</div></div>`;
    const days = new Map();
    for (const it of list) { const k = dateKey(it.created_at); if (!days.has(k)) days.set(k, []); days.get(k).push(it); }
    return [...days.entries()].map(([d, items]) => `<div class="day">${esc(d)}</div><div class="list">${items.map(rowFn).join("")}</div>`).join("");
  }

  async function loadHistory() {
    try { S.history = await api("/history"); if (route().name === "history") render(); } catch (e) { toast(e.message, true); }
  }

  // ---- support
  VIEWS.support = () => `<h1 class="page-title">${esc(T("support"))}</h1>
    <button class="promo" data-link="${esc(S.boot.support_url)}"><span class="ring">${icon("message")}</span>
      <span class="grow"><b>${esc(T("chatWithSupport"))}</b><span class="muted">${esc(T("supportSub"))}</span></span>${icon("right")}</button>
    <button class="ref card" data-link="${esc(S.boot.reviews_url)}"><span class="ic">${icon("star")}</span>
      <span class="grow"><b style="display:block">${esc(T("reviews"))}</b><span class="muted" style="font-size:13px">${esc(T("reviewsSub"))}</span></span><span class="go">${icon("arrow")}</span></button>
    <div class="section-title">${esc(T("faq"))}</div>
    <div class="list faq">${[1, 2, 3, 4].map((n) => `<details><summary>${esc(T(`faq${n}q`))}${icon("down")}</summary><p>${esc(T(`faq${n}a`))}</p></details>`).join("")}</div>
    <button class="ref card" data-go="#/terms" style="margin-top:14px"><span class="ic">${icon("shield")}</span><span class="grow"><b>${esc(T("terms"))}</b></span><span class="go">${icon("right")}</span></button>`;

  VIEWS.terms = () => `${topbar(T("terms"))}<div class="card"><p style="margin:0;color:var(--muted)">${esc(T("termsText"))}</p></div>`;

  // ---- profile
  VIEWS.profile = () => {
    const u = S.user;
    const lvl = u.level;
    const since = new Date(u.created_at * 1000).toLocaleDateString("ru-RU");
    return `<h1 class="page-title">${esc(T("profile"))}</h1>
      <section class="pcard"><div class="brand-row"><span class="mk">${esc(shopMark())}</span>${esc(S.boot.shop_name.toUpperCase())}<span class="chip">${icon("award")}${esc(lvl.title)}</span></div>
        <div class="who"><div class="avatar">${u.photo_url ? `<img src="${esc(u.photo_url)}" alt="">` : esc(initials(u))}</div>
          <div class="grow"><div class="name ellipsis">${esc(u.first_name || u.username || "")}</div>
          <div class="muted ellipsis" style="font-size:14px">${u.username ? "@" + esc(u.username) + " • " : ""}ID ${u.id}</div></div></div>
        <div class="ok-row"><span>${esc(T("verified"))}</span><span>${esc(T("safe"))}</span></div></section>
      <div class="section-title">${esc(T("buyerLevel"))}</div>
      <div class="card"><div class="lvl-head"><div><div class="k muted" style="font-size:12px;font-weight:700;letter-spacing:.08em">${esc(T("curLevel").toUpperCase())}</div>
        <div style="font-weight:800;font-size:18px;color:var(--primary-text)">${esc(lvl.title)}</div></div><div class="pct">${lvl.progress}<small>%</small></div></div>
        <div class="progress"><i style="width:${Math.max(0, Math.min(100, lvl.progress))}%"></i></div>
        <div class="muted" style="font-size:14px">${lvl.next_title ? esc(T("toNext", { n: lvl.next_title, x: moneyText(lvl.next_left) })) : esc(T("maxLevel"))}</div></div>
      <div class="section-title">${esc(T("yourInfo"))}</div>
      <div class="info-grid">
        <div class="card"><div class="k">${esc(T("balance"))}</div><div class="v">${moneyText(u.balance)}</div></div>
        <div class="card"><div class="k">${esc(T("ordersDone"))}</div><div class="v">${u.orders_done}</div></div>
        <div class="card"><div class="k">${esc(T("spentAll"))}</div><div class="v">${moneyText(u.total_spent)}</div></div>
        <div class="card"><div class="k">${esc(T("since"))}</div><div class="v">${esc(since)}</div></div></div>
      <button class="ref card" data-act="referral"><span class="ic">${icon("users")}</span>
        <span class="grow"><b style="display:block">${esc(T("partner"))}</b><span class="muted" style="font-size:14px">${T("partnerSub", { p: `<b style="color:var(--primary-text)">${S.boot.referral_percent}</b>` })}</span></span>
        <span class="go">${icon("arrow")}</span></button>
      <div class="section-title">${esc(T("settings"))}</div>
      <div class="settings">
        <div class="setting"><span class="ic">${icon("palette")}</span><span class="name">${esc(T("theme"))}</span>
          <label class="mini-select"><span class="sr-only">${esc(T("theme"))}</span><select id="theme-select">${["dark", "light", "auto"].map((t) =>
            `<option value="${t}" ${u.theme === t ? "selected" : ""}>${esc(T(t))}</option>`).join("")}</select>${icon("down")}</label></div>
        <div class="setting"><span class="ic">${icon("languages")}</span><span class="name">${esc(T("language"))}</span>
          <div class="seg mini"><button class="${u.lang === "tj" ? "on" : ""}" data-set="lang:tj">Тоҷикӣ</button><button class="${u.lang === "ru" ? "on" : ""}" data-set="lang:ru">Русский</button></div></div>
        <div class="setting"><span class="ic">${icon("coins")}</span><span class="name">${esc(T("currency"))}</span>
          <div class="seg mini"><button class="${u.currency === "TJS" ? "on" : ""}" data-set="currency:TJS">Сомонӣ</button><button class="${u.currency === "RUB" ? "on" : ""}" data-set="currency:RUB">Рубл ₽</button></div></div>
        <div class="setting"><span class="ic">${icon("lock")}</span><span class="name">${esc(T("pin"))}</span>
          <button class="switch" role="switch" aria-checked="${u.has_pin}" data-act="pin-toggle" aria-label="PIN"></button></div>
      </div>`;
  };
  const shopMark = () => S.boot.shop_name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

  function referralSheet() {
    const u = S.user;
    openSheet(`<div class="sheet-head"><h3>${esc(T("partner"))}</h3><button class="close-btn" data-close aria-label="Close">${icon("x")}</button></div>
      <p class="muted" style="margin-top:0">${T("partnerSub", { p: S.boot.referral_percent })}</p>
      <div class="info-grid" style="margin-bottom:14px"><div class="card"><div class="k">${esc(T("refs"))}</div><div class="v">${u.referrals}</div></div>
        <div class="card"><div class="k">${esc(T("balance"))} +</div><div class="v">${moneyText(u.ref_earned)}</div></div></div>
      <div class="field"><input readonly value="${esc(u.ref_link)}" aria-label="link"><button class="ghost-btn" data-copy="${esc(u.ref_link)}">${icon("copy")}${esc(T("copyLink"))}</button></div>
      <button class="cta" style="margin-top:14px" data-act="share-ref">${icon("share")}${esc(T("shareRef"))}</button>`);
  }

  // ---- notifications
  VIEWS.notifications = () => `${topbar(T("notifications"))}<div id="notif"><div class="empty">…</div></div>`;
  VIEWS.notifications.after = async () => {
    try {
      const { items } = await api("/notifications");
      const box = document.getElementById("notif");
      if (!box) return;
      box.innerHTML = items.length ? grouped(items, (n) => `<div class="item" style="align-items:flex-start"><span class="ic" style="${n.is_read ? "" : "color:var(--primary-text);border-color:var(--primary-text)"}">${icon("bell")}</span>
        <span class="grow"><span style="display:block;font-size:15px;white-space:pre-line">${esc(n.text.replace(/<[^>]+>/g, ""))}</span><span class="s">${timeOf(n.created_at)}</span></span></div>`)
        : `<div class="empty">${icon("bell")}<div>${esc(T("noNotif"))}</div></div>`;
      if (S.user.unread) { await api("/notifications/read", {}); S.user.unread = 0; }
    } catch (e) { toast(e.message, true); }
  };

  // ---- FF sensitivity generator
  const BRANDS = ["Samsung", "Xiaomi / Redmi / POCO", "iPhone", "Tecno / Infinix", "Realme / OPPO", "Vivo", "Huawei / Honor", "Дигар"];
  VIEWS.sens = () => {
    const s = S.sens || (S.sens = store.get("sens", { brand: 0, ram: 4, year: 2022 }));
    const years = []; for (let y = new Date().getFullYear(); y >= 2017; y--) years.push(y);
    return `${topbar(T("sensTitle"))}
      <p class="muted center" style="margin-top:0">${esc(T("sensInfo"))}</p>
      <label class="label" for="s-brand">${esc(T("brand"))}</label>
      <select id="s-brand" class="native-select">${BRANDS.map((b, i) => `<option value="${i}" ${i === s.brand ? "selected" : ""}>${esc(b)}</option>`).join("")}</select>
      <label class="label" for="s-ram">${esc(T("ram"))}</label>
      <select id="s-ram" class="native-select">${[2, 3, 4, 6, 8, 12, 16].map((r) => `<option value="${r}" ${r === s.ram ? "selected" : ""}>${r} GB</option>`).join("")}</select>
      <label class="label" for="s-year">${esc(T("year"))}</label>
      <select id="s-year" class="native-select">${years.map((y) => `<option ${y === s.year ? "selected" : ""}>${y}</option>`).join("")}</select>
      <div id="sens-out">${s.result ? sensResult(s.result) : ""}</div>
      <div class="cta-bar"><button class="cta" data-act="sens">${icon("crosshair")}${esc(T("generate"))}</button></div>`;
  };
  function calcSens(s) {
    // Heuristic: weaker / older devices need higher sensitivity to compensate for lower touch sampling.
    const perf = Math.min(1, (s.ram / 12) * 0.6 + ((s.year - 2017) / 9) * 0.4);
    const brandAdj = [2, 4, -6, 6, 3, 3, 1, 4][s.brand] || 0;
    const base = Math.round(96 - perf * 18 + brandAdj);
    const cap = (v) => Math.max(40, Math.min(100, Math.round(v)));
    return { general: cap(base + 4), redDot: cap(base), scope2: cap(base - 4), scope4: cap(base - 8), sniper: cap(base - 38),
             freeLook: cap(base - 20), fireBtn: Math.round(48 + (1 - perf) * 10), dpi: s.brand === 2 ? "—" : String(Math.round(400 + perf * 160)) };
  }
  const sensResult = (r) => `<div class="sens-res">${[["general", r.general], ["redDot", r.redDot], ["scope2", r.scope2], ["scope4", r.scope4], ["sniper", r.sniper],
    ["freeLook", r.freeLook], ["fireBtn", r.fireBtn + "%"], ["dpi", r.dpi]].map(([k, v]) =>
    `<div class="card"><div class="muted" style="font-size:13px;font-weight:600">${esc(T(k))}</div><div class="v">${esc(v)}</div></div>`).join("")}</div>`;

  // ------------------------------------------------------------------ sheets
  function openSheet(html, onMount) {
    $sheet.innerHTML = `<div class="sheet-wrap" data-close-bg><div class="sheet" role="dialog" aria-modal="true">${html}</div></div>`;
    const wrap = $sheet.firstElementChild;
    wrap.addEventListener("click", (e) => { if (e.target === wrap || e.target.closest("[data-close]")) closeSheet(); });
    if (onMount) onMount(wrap);
  }
  function closeSheet() { $sheet.innerHTML = ""; }

  // ------------------------------------------------------------------ PIN
  function pinScreen(title, onDone) {
    let val = "";
    const el = document.createElement("div");
    el.className = "pin";
    const draw = () => {
      el.innerHTML = `<div style="width:64px;height:64px;border-radius:20px;display:grid;place-items:center;background:var(--primary-soft);color:var(--primary-text)">${icon("lock")}</div>
        <div style="font-weight:800;font-size:20px">${esc(title)}</div>
        <div class="pin-dots">${[0, 1, 2, 3].map((i) => `<i class="${i < val.length ? "on" : ""}"></i>`).join("")}</div>
        <div class="keypad">${[1, 2, 3, 4, 5, 6, 7, 8, 9, "", 0, "del"].map((k) => k === "" ? "<span></span>"
          : `<button data-k="${k}" aria-label="${k === "del" ? "delete" : k}">${k === "del" ? icon("del") : k}</button>`).join("")}</div>`;
    };
    draw();
    el.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-k]");
      if (!b) return;
      haptic();
      if (b.dataset.k === "del") val = val.slice(0, -1); else if (val.length < 4) val += b.dataset.k;
      draw();
      if (val.length === 4) {
        const ok = await onDone(val);
        if (ok) el.remove();
        else { val = ""; draw(); el.querySelector(".pin-dots").classList.add("shake"); try { tg.HapticFeedback.notificationOccurred("error"); } catch { /* */ } }
      }
    });
    document.body.appendChild(el);
  }

  // ------------------------------------------------------------------ events
  document.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-go],[data-back],[data-act],[data-tab],[data-cart],[data-prod],[data-info],[data-amount],[data-htab],[data-hfilter],[data-set],[data-link],[data-copy],[data-acc] > button");
    if (!t) return;
    if (t.matches("[data-acc] > button")) {
      const acc = t.parentElement; acc.classList.toggle("open"); t.setAttribute("aria-expanded", acc.classList.contains("open")); haptic(); return;
    }
    const d = t.dataset;
    if (d.go !== undefined) { haptic(); go(d.go); return; }
    if (d.back !== undefined) { history.length > 1 ? history.back() : go("#/"); return; }
    if (d.link) { openLink(d.link); return; }
    if (d.copy) { copy(d.copy); return; }
    if (d.tab) { S.tab = d.tab; haptic(); render(); return; }
    if (d.info) {
      e.stopPropagation();
      const [p, c] = productById(d.info);
      openSheet(`<div class="sheet-head"><h3>${esc(p.title)}</h3><button class="close-btn" data-close aria-label="Close">${icon("x")}</button></div>
        <div class="prod" style="pointer-events:none"><div class="art" style="max-width:220px;margin:0 auto;width:100%">${productArt(p)}</div></div>
        <p class="muted">${esc(p.subtitle || c.title)}</p><div class="price" style="margin-bottom:16px">${moneyHTML(p.price)}</div>
        <button class="cta" data-cart="${p.id}">${icon("cart")}${esc(T("buy"))}</button>`);
      return;
    }
    if (d.cart || d.prod) {
      const pid = d.cart || d.prod;
      const [, c] = productById(pid);
      if (S.multi) {
        if (S.selected.has(pid)) S.selected.delete(pid); else S.selected.set(pid, 1);
        haptic(); render(); return;
      }
      haptic("medium");
      S.checkout = { cat: c.id, items: [{ product_id: pid, qty: 1 }], uid: store.get("uids", {})[c.id] || "", agree: store.get("agree", false) };
      go("#/checkout");
      return;
    }
    if (d.amount) { S.topup.amount = Number(d.amount); haptic(); render(); return; }
    if (d.htab) { S.historyTab = d.htab; render(); return; }
    if (d.hfilter) { S.historyFilter = d.hfilter; render(); return; }
    if (d.set) {
      const [k, v] = d.set.split(":");
      try { S.user = await api("/settings", { [k]: v }); LANG = S.user.lang; applyTheme(); render(); haptic(); } catch (err) { toast(err.message, true); }
      return;
    }
    switch (d.act) {
      case "toggle-hide": S.hidden = !S.hidden; store.set("hideBalance", S.hidden); render(); break;
      case "history-finance": S.historyTab = "finance"; go("#/history"); break;
      case "multi": S.multi = !S.multi; if (!S.multi) S.selected.clear(); haptic(); render(); break;
      case "buy-selected": {
        const items = [...S.selected.entries()].map(([product_id, qty]) => ({ product_id, qty }));
        const [, c] = productById(items[0].product_id);
        S.checkout = { cat: c.id, items, uid: store.get("uids", {})[c.id] || "", agree: store.get("agree", false) };
        go("#/checkout"); break;
      }
      case "paste": {
        const put = (txt) => {
          const v = (txt || "").trim(); if (!v) return;
          S.checkout.uid = v; S.checkout.fields[S.checkout.fieldDefs[0].key] = v; S.checkout.nick = undefined; render();
        };
        if (tg && tg.readTextFromClipboard && tg.isVersionAtLeast && tg.isVersionAtLeast("6.4")) tg.readTextFromClipboard(put);
        else if (navigator.clipboard && navigator.clipboard.readText) navigator.clipboard.readText().then(put, () => document.getElementById("uid").focus());
        break;
      }
      case "agree": S.checkout.agree = !S.checkout.agree; store.set("agree", S.checkout.agree); haptic(); render(); break;
      case "choose-method": methodSheet(S.checkout.method, true, (m) => { S.checkout.method = m; render(); }); break;
      case "topup-method": methodSheet(S.topup.method, false, (m) => { S.topup.method = m; render(); }); break;
      case "pay": pay(); break;
      case "do-topup": doTopup(); break;
      case "to-chat": if (tg) tg.close(); else openLink(`https://t.me/${S.boot.bot_username}`); break;
      case "referral": referralSheet(); break;
      case "share-ref": {
        const url = `https://t.me/share/url?url=${encodeURIComponent(S.user.ref_link)}&text=${encodeURIComponent(S.boot.shop_name)}`;
        openLink(url); break;
      }
      case "pin-toggle":
        if (S.user.has_pin) {
          pinScreen(T("enterPin"), async (old) => { try { await api("/pin", { old, pin: null }); S.user.has_pin = false; render(); return true; } catch { return false; } });
        } else {
          pinScreen(T("newPin"), async (pin) => { try { await api("/pin", { pin }); S.user.has_pin = true; render(); return true; } catch (err) { toast(err.message, true); return true; } });
        }
        break;
      case "sens": {
        const s = S.sens;
        s.brand = Number(document.getElementById("s-brand").value);
        s.ram = Number(document.getElementById("s-ram").value);
        s.year = Number(document.getElementById("s-year").value);
        s.result = calcSens(s);
        store.set("sens", s);
        document.getElementById("sens-out").innerHTML = sensResult(s.result);
        document.getElementById("sens-out").scrollIntoView({ behavior: "smooth" });
        haptic("medium");
        break;
      }
    }
  });
  document.addEventListener("change", async (e) => {
    if (e.target.id !== "theme-select") return;
    try { S.user = await api("/settings", { theme: e.target.value }); applyTheme(); render(); haptic(); } catch (err) { toast(err.message, true); }
  });
  document.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.matches(".prod[role=button]")) { e.preventDefault(); e.target.click(); }
  });

  window.addEventListener("hashchange", () => {
    const n = route().name;
    if (n === "history") S.history = null;
    render();
  });
  if (tg) tg.BackButton.onClick(() => (history.length > 1 ? history.back() : go("#/")));

  async function refreshUser() {
    try { S.user = await api("/me"); } catch { /* keep old */ }
  }

  // ------------------------------------------------------------------ boot
  async function boot() {
    if (tg) { tg.ready(); tg.expand(); try { tg.disableVerticalSwipes && tg.disableVerticalSwipes(); } catch { /* */ } }
    const splash = document.getElementById("splash");
    const started = Date.now();
    try {
      S.boot = await api("/bootstrap");
    } catch (e) {
      splash.querySelector(".splash-tag").textContent = e.message;
      return;
    }
    S.user = S.boot.user;
    S.catalog = S.boot.catalog;
    LANG = S.user.lang;
    document.title = S.boot.shop_name;
    document.getElementById("splash-name").textContent = S.boot.shop_name;
    document.getElementById("splash-mark").textContent = shopMark();
    applyTheme();
    const start = tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param;
    if (start && !location.hash) location.hash = "#/" + start.replace(/_/g, "/");
    await new Promise((r) => setTimeout(r, Math.max(0, 900 - (Date.now() - started))));
    $app.hidden = false;
    render();
    splash.classList.add("hide");
    setTimeout(() => splash.remove(), 400);
    if (S.user.has_pin) {
      pinScreen(T("enterPin"), async (pin) => { try { return (await api("/pin/verify", { pin })).ok; } catch { return false; } });
    }
  }
  boot();
})();
