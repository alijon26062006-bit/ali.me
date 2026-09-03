/* Копейка — панель. Ванильный JS: без сборки, без внешних библиотек. */

const CURRENCY = {
  UZS: { symbol: "so'm", decimals: 0 },
  USD: { symbol: '$', decimals: 2 },
  EUR: { symbol: '€', decimals: 2 },
  RUB: { symbol: '₽', decimals: 0 },
  KZT: { symbol: '₸', decimals: 0 },
  KGS: { symbol: 'сом', decimals: 0 },
  TJS: { symbol: 'смн', decimals: 2 },
  UAH: { symbol: '₴', decimals: 0 },
  TRY: { symbol: '₺', decimals: 0 },
  GBP: { symbol: '£', decimals: 2 },
};

const MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'];
const MONTHS_GEN = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
const WEEKDAYS = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
const PERIOD_LABEL = { today: 'Потрачено сегодня', week: 'Потрачено за неделю', month: 'Потрачено за месяц' };

/** В кольце показываем максимум 8 долей: 7 категорий и «Другое». */
const DONUT_SLICES = 7;

const state = {
  me: null,
  period: 'month',
  month: null,
  summary: null,
  expenses: [],
  categoryFilter: null,
  dayFilter: null,
  openId: null,
  shownTotal: 0,
};

const $ = (id) => document.getElementById(id);
const tg = window.Telegram?.WebApp;
if (tg?.initData) {
  tg.ready();
  tg.expand();
}

/* ------------------------------- сеть ---------------------------------- */

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    credentials: 'same-origin',
    headers: options.body ? { 'content-type': 'application/json' } : undefined,
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (response.status === 401) {
    location.replace('/');
    throw new Error('unauthorized');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

const query = () =>
  state.period === 'month' && state.month ? `month=${state.month}` : `period=${state.period}`;

async function load() {
  const [summary, expenses] = await Promise.all([
    api(`/summary?${query()}`),
    api(`/expenses?${query()}&limit=1000`),
  ]);
  state.summary = summary;
  state.expenses = expenses.items;
  render();
}

/* ---------------------------- форматирование ---------------------------- */

function money(amount, code = state.me?.user.currency || 'UZS') {
  const meta = CURRENCY[code] || { symbol: code, decimals: 2 };
  const value = Number(amount) || 0;
  const body = value.toLocaleString('ru-RU', {
    minimumFractionDigits: Math.abs(value % 1) > 0 ? meta.decimals : 0,
    maximumFractionDigits: meta.decimals,
  });
  return ['$', '€', '£'].includes(meta.symbol) ? `${meta.symbol}${body}` : `${body} ${meta.symbol}`;
}

function compact(amount) {
  const value = Math.round(Number(amount) || 0);
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value >= 10_000_000 ? 0 : 1)} млн`;
  if (value >= 10_000) return `${Math.round(value / 1000)} тыс`;
  return value.toLocaleString('ru-RU');
}

function plural(count, one, few, many) {
  const n = Math.abs(count) % 100;
  const n1 = n % 10;
  if (n > 10 && n < 20) return many;
  if (n1 > 1 && n1 < 5) return few;
  if (n1 === 1) return one;
  return many;
}

const catColor = (key) => `var(--cat-${key})`;

function dayTitle(day) {
  if (day === state.me?.user.today) return 'сегодня';
  if (day === shiftDay(state.me.user.today, -1)) return 'вчера';
  const [y, m, d] = day.split('-').map(Number);
  const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${d} ${MONTHS_GEN[m - 1]}, ${weekday}`;
}

const dayShort = (day) => {
  const [y, m, d] = day.split('-').map(Number);
  return `${d} ${MONTHS_GEN[m - 1].slice(0, 3)}`;
};

function shiftDay(day, delta) {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + delta)).toISOString().slice(0, 10);
}

/** Локальное время траты, «14:05». */
const localTime = (expense) =>
  new Date(Date.parse(expense.spentAt) + state.me.user.tzOffset * 60000).toISOString().slice(11, 16);

/** Полное локальное время — чтобы правка даты не сдвигала порядок трат. */
const localTimeIso = (expense) =>
  new Date(Date.parse(expense.spentAt) + state.me.user.tzOffset * 60000).toISOString().slice(11, 23);

const toUtcIso = (day, timeIso) =>
  new Date(Date.parse(`${day}T${timeIso}Z`) - state.me.user.tzOffset * 60000).toISOString();

function monthTitle(monthKey) {
  const [y, m] = monthKey.split('-');
  return `${MONTHS[Number(m) - 1]}${y === state.me.user.month.slice(0, 4) ? '' : ` ${y}`}`;
}

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ------------------------------- рендер --------------------------------- */

function render() {
  renderHero();
  renderDonut();
  renderLegend();
  renderBars();
  renderLimits();
  renderChips();
  renderList();
}

function renderHero() {
  const { summary } = state;
  $('hero-label').textContent =
    state.period === 'month' && state.month !== state.me.user.month
      ? `Потрачено: ${monthTitle(state.month)}`
      : PERIOD_LABEL[state.period];

  countUp(summary.total);

  const parts = [`${summary.count} ${plural(summary.count, 'трата', 'траты', 'трат')}`];
  if (state.period !== 'today' && summary.count > 0) parts.push(`${money(summary.average)} в день`);
  $('total-meta').textContent = parts.join('  ·  ');

  renderHeroStats();

  // Мини-график последних двух недель — только если он и правда что-то показывает.
  const tail = summary.days.slice(-14);
  const filled = tail.filter((d) => d.total > 0).length;
  const spark = $('spark');
  spark.hidden = filled < 5;
  if (!spark.hidden) {
    const max = Math.max(...tail.map((d) => d.total), 1);
    spark.innerHTML = tail
      .map((d) => `<i style="height:${Math.max(10, (d.total / max) * 100)}%" class="${d.total > 0 ? 'on' : ''}"></i>`)
      .join('');
  }

  const nav = $('month-nav');
  nav.hidden = state.period !== 'month';
  if (state.period === 'month') {
    $('month-label').textContent = monthTitle(state.month || state.me.user.month);
    $('month-next').disabled = (state.month || state.me.user.month) >= state.me.user.month;
  }
  $('export-link').href = `/api/export.csv?${query()}`;
}

/** Средний чек и самая крупная трата — вместо пустого места под итогом. */
function renderHeroStats() {
  const items = state.expenses;
  const node = $('hero-stats');
  if (items.length === 0) {
    node.innerHTML = '';
    return;
  }
  const biggest = items.reduce((best, item) => (item.amountBase > best.amountBase ? item : best), items[0]);
  const average = items.reduce((sum, item) => sum + item.amountBase, 0) / items.length;
  const top = state.summary.byCategory[0];
  node.innerHTML = `
    <div class="hero-stat"><span>Средний чек</span><b class="num">${money(average)}</b></div>
    <div class="hero-stat"><span>Крупнейшая · ${escapeHtml(biggest.note)}</span><b class="num">${money(biggest.amountBase)}</b></div>
    ${top ? `<div class="hero-stat"><span>Больше всего</span><b>${top.emoji} ${escapeHtml(top.title)}</b></div>` : ''}`;
}

/** Плавный счётчик итога — цифры «набегают» при переключении периода. */
function countUp(target) {
  const node = $('total');
  const from = state.shownTotal;
  const started = performance.now();
  const duration = Math.abs(target - from) > 0 ? 420 : 0;
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || duration === 0) {
    state.shownTotal = target;
    node.textContent = money(target);
    return;
  }
  const step = (now) => {
    const progress = Math.min(1, (now - started) / duration);
    const eased = 1 - (1 - progress) ** 3;
    node.textContent = money(from + (target - from) * eased);
    if (progress < 1) requestAnimationFrame(step);
    else state.shownTotal = target;
  };
  requestAnimationFrame(step);
}

/** Категории для графика: топ-7 и «Другое» — больше восьми долей глаз не различает. */
function chartCategories() {
  const items = state.summary.byCategory.filter((c) => c.total > 0);
  if (items.length <= DONUT_SLICES + 1) return items;
  const head = items.slice(0, DONUT_SLICES);
  const rest = items.slice(DONUT_SLICES);
  return [
    ...head,
    {
      key: 'other',
      title: 'Другое',
      emoji: '•',
      total: rest.reduce((sum, c) => sum + c.total, 0),
      count: rest.reduce((sum, c) => sum + c.count, 0),
      share: rest.reduce((sum, c) => sum + c.share, 0),
      grouped: rest.length,
    },
  ];
}

function renderDonut() {
  const svg = $('donut');
  const items = chartCategories();
  const total = items.reduce((sum, c) => sum + c.total, 0);
  const radius = 82;
  const circumference = 2 * Math.PI * radius;
  const gap = items.length > 1 ? 3 : 0;
  let offset = 0;

  if (total <= 0) {
    svg.innerHTML = `
      <circle cx="110" cy="110" r="${radius}" fill="none" style="stroke:var(--surface-2)" stroke-width="26"></circle>
      <text x="110" y="115" text-anchor="middle" style="fill:var(--text-3)" font-size="13">нет трат</text>`;
    svg.classList.remove('has-active');
    return;
  }

  const slices = items
    .map((item) => {
      const length = Math.max((item.total / total) * circumference - gap, 1.5);
      const circle = `<circle class="slice${state.categoryFilter === item.key ? ' active' : ''}"
        data-key="${item.key}" cx="110" cy="110" r="${radius}" fill="none"
        style="stroke:${catColor(item.key)}" stroke-width="26"
        stroke-dasharray="${length} ${circumference - length}"
        stroke-dashoffset="${-offset}" transform="rotate(-90 110 110)">
        <title>${item.emoji} ${item.title}: ${money(item.total)} · ${Math.round(item.share * 100)}%</title>
      </circle>`;
      offset += (item.total / total) * circumference;
      return circle;
    })
    .join('');

  const focus = state.categoryFilter ? items.find((c) => c.key === state.categoryFilter) : null;

  svg.innerHTML = `${slices}
    <text x="110" y="104" text-anchor="middle" style="fill:var(--text)" font-size="21" font-weight="700">
      ${escapeHtml(compact(focus ? focus.total : total))}
    </text>
    <text x="110" y="126" text-anchor="middle" style="fill:var(--text-3)" font-size="12">
      ${escapeHtml(focus ? `${focus.emoji} ${focus.title}` : state.me.user.currency)}
    </text>`;

  svg.classList.toggle('has-active', Boolean(state.categoryFilter));
  svg.querySelectorAll('.slice').forEach((slice) => {
    slice.addEventListener('click', () => toggleCategory(slice.dataset.key));
  });
}

function renderLegend() {
  const legend = $('legend');
  const items = chartCategories();
  const max = Math.max(...items.map((c) => c.total), 1);

  $('cat-note').textContent = items.length
    ? `${items.length} ${plural(items.length, 'категория', 'категории', 'категорий')}`
    : '';

  if (items.length === 0) {
    legend.innerHTML =
      '<div class="empty-state"><span class="big">🍰</span>Запишите первую трату — здесь появится разбивка<small>Например: кофе 350</small></div>';
    return;
  }

  legend.innerHTML = items
    .map(
      (item) => `
      <button class="legend-item" data-key="${item.key}" aria-pressed="${state.categoryFilter === item.key}">
        <span class="dot" style="background:${catColor(item.key)}"></span>
        <span class="legend-title">${item.emoji} ${escapeHtml(item.title)}${
          item.grouped ? `<small>${item.grouped} ${plural(item.grouped, 'категория', 'категории', 'категорий')}</small>` : ''
        }</span>
        <span class="legend-value num">${money(item.total)}</span>
        <span class="legend-track"><i style="width:${(item.total / max) * 100}%;background:${catColor(item.key)}"></i></span>
      </button>`,
    )
    .join('');

  legend.querySelectorAll('.legend-item').forEach((button) => {
    button.addEventListener('click', () => toggleCategory(button.dataset.key));
  });
}

function renderBars() {
  const bars = $('bars');
  const days = state.summary.days;
  const max = Math.max(...days.map((d) => d.total), 1);
  const busiest = days.reduce((best, day) => (day.total > (best?.total || 0) ? day : best), null);

  $('days-note').textContent =
    busiest && busiest.total > 0 ? `пик — ${dayShort(busiest.day)}, ${money(busiest.total)}` : '';

  bars.innerHTML = days
    .map((day) => {
      const height = day.total > 0 ? Math.max(6, Math.round((day.total / max) * 100)) : 3;
      const classes = ['bar'];
      if (day.total === 0) classes.push('zero');
      if (day.day === state.me.user.today) classes.push('today');
      return `<div class="${classes.join(' ')}" data-day="${day.day}" aria-pressed="${state.dayFilter === day.day}"
        data-tip="${escapeHtml(`${dayTitle(day.day)} · ${money(day.total)}`)}"><i style="height:${height}%"></i></div>`;
    })
    .join('') + '<div class="bars-tip" id="bars-tip"></div>';

  const tip = $('bars-tip');
  const showTip = (bar) => {
    tip.textContent = bar.dataset.tip;
    tip.classList.add('show');
    const width = bars.clientWidth;
    const half = tip.offsetWidth / 2 + 4;
    const center = bar.offsetLeft + bar.offsetWidth / 2;
    tip.style.left = `${Math.min(Math.max(center, half), width - half)}px`;
  };

  bars.querySelectorAll('.bar').forEach((bar) => {
    bar.addEventListener('mouseenter', () => showTip(bar));
    bar.addEventListener('click', () => {
      showTip(bar);
      toggleDay(bar.dataset.day);
    });
  });
  bars.addEventListener('mouseleave', () => tip.classList.remove('show'));

  $('bars-axis').innerHTML =
    days.length > 1
      ? `<span>${dayShort(days[0].day)}</span><span>${dayShort(days[days.length - 1].day)}</span>`
      : '';
}

function renderLimits() {
  const limits = state.summary.limits || [];
  $('limits-card').hidden = limits.length === 0;
  $('limits').innerHTML = limits
    .map((limit) => {
      const share = Math.min(limit.share, 1);
      const color = limit.share >= 1 ? 'var(--danger)' : limit.share >= 0.8 ? 'var(--warning)' : catColor(limit.key);
      const left = limit.limit - limit.spent;
      return `<div>
        <div class="limit-head">
          <span>${limit.emoji} ${escapeHtml(limit.title)}</span>
          <span class="num"><b>${money(limit.spent)}</b> <span style="color:var(--text-3)">из ${money(limit.limit)}</span></span>
        </div>
        <div class="limit-bar"><div class="limit-fill" style="width:${share * 100}%;background:${color}"></div></div>
        <div class="section-note" style="margin-top:5px">${
          left >= 0 ? `осталось ${money(left)}` : `перерасход ${money(-left)}`
        }</div>
      </div>`;
    })
    .join('');
}

/** Быстрые подсказки: то, что вы пишете чаще всего. */
function renderChips() {
  const counts = new Map();
  for (const expense of state.expenses) {
    const note = (expense.note || '').trim().toLowerCase();
    if (!note || note.length > 20) continue;
    counts.set(note, (counts.get(note) || 0) + 1);
  }
  const popular = [...counts.entries()]
    .filter(([, count]) => count > 1)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([note]) => note);

  const defaults = ['кофе 350', 'такси 900', 'продукты 120000'];
  const chips = [...popular, ...defaults.filter((d) => !popular.includes(d.split(' ')[0]))].slice(0, 4);
  $('chips').innerHTML = chips
    .map((text) => `<button class="chip" type="button" data-text="${escapeHtml(text)}">${escapeHtml(text)}</button>`)
    .join('');
  $('chips').querySelectorAll('.chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const input = $('quick-input');
      input.value = popular.includes(chip.dataset.text) ? `${chip.dataset.text} ` : chip.dataset.text;
      input.focus();
    });
  });
}

function renderList() {
  const list = $('list');
  let items = state.expenses;
  if (state.categoryFilter && state.categoryFilter !== 'other') {
    items = items.filter((e) => e.category === state.categoryFilter);
  } else if (state.categoryFilter === 'other') {
    const shown = chartCategories().map((c) => c.key);
    items = items.filter((e) => !shown.includes(e.category) || e.category === 'other');
  }
  if (state.dayFilter) items = items.filter((e) => e.day === state.dayFilter);

  const note = [];
  if (state.categoryFilter) {
    const category = chartCategories().find((c) => c.key === state.categoryFilter);
    if (category) note.push(`${category.emoji} ${category.title}`);
  }
  if (state.dayFilter) note.push(dayTitle(state.dayFilter));
  $('filter-note').innerHTML = note.length
    ? `${escapeHtml(note.join(' · '))} <button class="icon-btn" id="clear-filter" style="height:24px;padding:0 8px;font-size:12px">сбросить</button>`
    : `${items.length} ${plural(items.length, 'запись', 'записи', 'записей')}`;
  $('clear-filter')?.addEventListener('click', () => {
    state.categoryFilter = null;
    state.dayFilter = null;
    render();
  });

  if (items.length === 0) {
    list.innerHTML = `<div class="empty-state"><span class="big">🧾</span>Трат за этот период нет
      <small>Запишите первую в форме выше или прямо в боте</small></div>`;
    return;
  }

  const groups = new Map();
  for (const expense of items) {
    if (!groups.has(expense.day)) groups.set(expense.day, []);
    groups.get(expense.day).push(expense);
  }

  list.innerHTML = [...groups.entries()]
    .map(([day, rows]) => {
      const total = rows.reduce((sum, row) => sum + row.amountBase, 0);
      return `<div class="day-group">
        <div class="day-head"><span>${dayTitle(day)}</span><b class="num">${money(total)}</b></div>
        ${rows.map(renderExpense).join('')}
      </div>`;
    })
    .join('');

  list.querySelectorAll('[data-expense]').forEach((element) => {
    element.addEventListener('click', () => {
      const id = Number(element.dataset.expense);
      state.openId = state.openId === id ? null : id;
      renderList();
    });
  });
  bindEditor();
}

function renderExpense(expense) {
  if (state.openId === expense.id) return renderEditor(expense);
  const converted =
    expense.currency !== expense.baseCurrency
      ? `<small class="num">${money(expense.amountBase, expense.baseCurrency)}</small>`
      : '';
  return `<div class="expense" data-expense="${expense.id}">
    <div class="emoji" style="--cat:${catColor(expense.category)}">${expense.categoryEmoji}</div>
    <div class="expense-main">
      <div class="expense-note">${escapeHtml(expense.note || expense.categoryTitle)}</div>
      <div class="expense-sub">${escapeHtml(expense.categoryTitle)} · ${localTime(expense)}${
        expense.source === 'photo' ? ' · 📷 чек' : ''
      }</div>
    </div>
    <div class="expense-amount num">${money(expense.amount, expense.currency)}${converted}</div>
  </div>`;
}

function renderEditor(expense) {
  const categories = state.me.categories
    .map((c) => `<option value="${c.key}" ${c.key === expense.category ? 'selected' : ''}>${c.emoji} ${c.title}</option>`)
    .join('');
  const currencies = state.me.currencies
    .map((code) => `<option value="${code}" ${code === expense.currency ? 'selected' : ''}>${code}</option>`)
    .join('');
  return `<div class="editor" data-editor="${expense.id}">
    <div class="row">
      <input type="number" step="any" min="0" id="edit-amount" value="${expense.amount}" aria-label="Сумма">
      <select id="edit-currency" aria-label="Валюта" style="max-width:104px">${currencies}</select>
    </div>
    <input type="text" id="edit-note" value="${escapeHtml(expense.note)}" placeholder="Описание" aria-label="Описание">
    <div class="row">
      <select id="edit-category" aria-label="Категория">${categories}</select>
      <input type="date" id="edit-date" value="${expense.day}" aria-label="Дата" style="max-width:168px">
    </div>
    <div class="actions">
      <button class="btn danger" id="edit-delete" type="button">Удалить</button>
      <span style="flex:1"></span>
      <button class="btn" id="edit-cancel" type="button">Отмена</button>
      <button class="btn save" id="edit-save" type="button">Сохранить</button>
    </div>
  </div>`;
}

function bindEditor() {
  const editor = document.querySelector('[data-editor]');
  if (!editor) return;
  const id = Number(editor.dataset.editor);
  editor.addEventListener('click', (event) => event.stopPropagation());

  $('edit-cancel').addEventListener('click', () => {
    state.openId = null;
    renderList();
  });

  $('edit-delete').addEventListener('click', async () => {
    await api(`/expenses/${id}`, { method: 'DELETE' });
    state.openId = null;
    toast('Трата удалена');
    await load();
  });

  $('edit-save').addEventListener('click', async () => {
    const amount = Number($('edit-amount').value);
    if (!(amount > 0)) return toast('Сумма должна быть больше нуля');
    const original = state.expenses.find((e) => e.id === id);
    await api(`/expenses/${id}`, {
      method: 'PATCH',
      body: {
        amount,
        currency: $('edit-currency').value,
        category: $('edit-category').value,
        note: $('edit-note').value,
        spentAt: toUtcIso($('edit-date').value, original ? localTimeIso(original) : '12:00:00.000'),
      },
    });
    state.openId = null;
    toast('Сохранено');
    await load();
  });
}

/* ------------------------------ действия -------------------------------- */

function toggleCategory(key) {
  state.categoryFilter = state.categoryFilter === key ? null : key;
  state.dayFilter = null;
  render();
}

function toggleDay(day) {
  state.dayFilter = state.dayFilter === day ? null : day;
  render();
}

let toastTimer;
function toast(message) {
  const element = $('toast');
  element.textContent = message;
  element.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove('show'), 2400);
  tg?.HapticFeedback?.impactOccurred?.('light');
}

/* ------------------------------- запуск --------------------------------- */

function setPeriod(period) {
  state.period = period;
  state.dayFilter = null;
  if (period === 'month') state.month = state.month || state.me.user.month;
  document.querySelectorAll('#tabs button').forEach((button) => {
    button.setAttribute('aria-selected', String(button.dataset.period === period));
  });
  load().catch((error) => toast(error.message));
}

function shiftMonth(delta) {
  const [y, m] = (state.month || state.me.user.month).split('-').map(Number);
  state.month = new Date(Date.UTC(y, m - 1 + delta, 1)).toISOString().slice(0, 7);
  load().catch((error) => toast(error.message));
}

async function boot() {
  try {
    state.me = await api('/me');
  } catch {
    location.replace('/');
    return;
  }
  state.month = state.me.user.month;

  if (state.me.user.firstName) {
    $('greeting').textContent = `Привет, ${state.me.user.firstName}`;
  }

  if (state.me.botUsername) {
    $('bot-link').href = `https://t.me/${state.me.botUsername}`;
  } else {
    $('bot-link').hidden = true;
  }

  $('currency').innerHTML = state.me.currencies
    .map((code) => `<option value="${code}" ${code === state.me.user.currency ? 'selected' : ''}>${code}</option>`)
    .join('');
  $('tz').innerHTML = Array.from({ length: 27 }, (_, i) => (i - 12) * 60)
    .map((offset) => `<option value="${offset}" ${offset === state.me.user.tzOffset ? 'selected' : ''}>UTC${offset >= 0 ? '+' : ''}${offset / 60}</option>`)
    .join('');

  document.querySelectorAll('#tabs button').forEach((button) => {
    button.addEventListener('click', () => setPeriod(button.dataset.period));
  });
  $('month-prev').addEventListener('click', () => shiftMonth(-1));
  $('month-next').addEventListener('click', () => shiftMonth(1));

  $('quick-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const input = $('quick-input');
    const button = event.currentTarget.querySelector('button');
    const text = input.value.trim();
    if (!text) return;
    button.disabled = true;
    try {
      const { expense } = await api('/expenses', { method: 'POST', body: { text } });
      input.value = '';
      toast(`Записал: ${money(expense.amount, expense.currency)} · ${expense.categoryEmoji} ${expense.categoryTitle}`);
      await load();
    } catch (error) {
      toast(error.message === 'no amount' ? 'Не нашёл сумму. Например: кофе 350' : error.message);
    } finally {
      button.disabled = false;
    }
  });

  $('currency').addEventListener('change', async (event) => {
    await api('/settings', { method: 'PATCH', body: { currency: event.target.value } });
    state.me.user.currency = event.target.value;
    state.shownTotal = 0;
    toast('Валюта обновлена');
    await load();
  });

  $('tz').addEventListener('change', async (event) => {
    await api('/settings', { method: 'PATCH', body: { tzOffset: Number(event.target.value) } });
    state.me = await api('/me');
    toast('Часовой пояс обновлён');
    await load();
  });

  $('logout').addEventListener('click', async () => {
    await api('/auth/logout', { method: 'POST' });
    location.replace('/');
  });

  document.querySelector('.wrap').classList.add('fade-in');
  setPeriod('month');
}

boot();
