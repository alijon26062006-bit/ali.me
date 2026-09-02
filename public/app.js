/* Панель «Копейка» — без сборки и внешних библиотек. */

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

const state = {
  me: null,
  period: 'month',
  month: null,
  summary: null,
  expenses: [],
  categoryFilter: null,
  dayFilter: null,
  openId: null,
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

function query() {
  return state.period === 'month' && state.month
    ? `month=${state.month}`
    : `period=${state.period}`;
}

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
  return ['$', '€', '£'].includes(meta.symbol) ? `${meta.symbol}${body}` : `${body} ${meta.symbol}`;
}

function plural(count, one, few, many) {
  const n = Math.abs(count) % 100;
  const n1 = n % 10;
  if (n > 10 && n < 20) return many;
  if (n1 > 1 && n1 < 5) return few;
  if (n1 === 1) return one;
  return many;
}

function dayTitle(day) {
  if (day === state.me?.user.today) return 'сегодня';
  const [y, m, d] = day.split('-').map(Number);
  const yesterday = shiftDay(state.me.user.today, -1);
  if (day === yesterday) return 'вчера';
  const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${d} ${MONTHS_GEN[m - 1]}, ${weekday}`;
}

/** Локальное время траты в поясе пользователя, «14:05». */
function localTime(expense) {
  const shifted = new Date(Date.parse(expense.spentAt) + state.me.user.tzOffset * 60000);
  return shifted.toISOString().slice(11, 16);
}

/** Полное локальное время с секундами — чтобы правка даты не сдвигала порядок трат. */
function localTimeIso(expense) {
  return new Date(Date.parse(expense.spentAt) + state.me.user.tzOffset * 60000).toISOString().slice(11, 23);
}

/** Обратный пересчёт: локальные дата и время → UTC ISO. */
function toUtcIso(day, timeIso) {
  return new Date(Date.parse(`${day}T${timeIso}Z`) - state.me.user.tzOffset * 60000).toISOString();
}

function shiftDay(day, delta) {
  const [y, m, d] = day.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d + delta));
  return date.toISOString().slice(0, 10);
}

function monthTitle(monthKey) {
  const [y, m] = monthKey.split('-');
  const current = state.me.user.month.slice(0, 4);
  return `${MONTHS[Number(m) - 1]}${y === current ? '' : ` ${y}`}`;
}

/* ------------------------------- рендер --------------------------------- */

function render() {
  renderHeader();
  renderDonut();
  renderLegend();
  renderBars();
  renderLimits();
  renderList();
}

function renderHeader() {
  const { summary } = state;
  $('total').textContent = money(summary.total);
  const parts = [`${summary.count} ${plural(summary.count, 'трата', 'траты', 'трат')}`];
  if (state.period !== 'today') parts.push(`в среднем ${money(summary.average)} в день`);
  $('total-meta').textContent = parts.join(' · ');

  const nav = $('month-nav');
  nav.hidden = state.period !== 'month';
  if (state.period === 'month') {
    $('month-label').textContent = monthTitle(state.month || state.me.user.month);
    $('month-next').disabled = (state.month || state.me.user.month) >= state.me.user.month;
  }
  $('export-link').href = `/api/export.csv?${query()}`;
}

function renderDonut() {
  const svg = $('donut');
  const items = state.summary.byCategory.filter((c) => c.total > 0);
  const total = items.reduce((sum, c) => sum + c.total, 0);
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  const rings = items
    .map((item) => {
      const length = total > 0 ? (item.total / total) * circumference : 0;
      const circle = `<circle class="ring" data-key="${item.key}" cx="100" cy="100" r="${radius}"
        fill="none" stroke="${item.color}" stroke-width="${state.categoryFilter === item.key ? 30 : 24}"
        stroke-dasharray="${Math.max(length - 1.5, 0)} ${circumference}"
        stroke-dashoffset="${-offset}" transform="rotate(-90 100 100)" style="cursor:pointer">
        <title>${item.emoji} ${item.title}: ${money(item.total)}</title></circle>`;
      offset += length;
      return circle;
    })
    .join('');

  svg.innerHTML = total > 0
    ? `${rings}
       <text x="100" y="96" text-anchor="middle" fill="currentColor" font-size="17" font-weight="700">
         ${items[0]?.emoji || ''} ${Math.round((items[0]?.share || 0) * 100)}%
       </text>
       <text x="100" y="118" text-anchor="middle" style="fill:var(--muted)" font-size="12">
         ${items[0]?.title || ''}
       </text>`
    : `<circle cx="100" cy="100" r="70" fill="none" style="stroke:var(--surface-2)" stroke-width="24"></circle>
       <text x="100" y="105" text-anchor="middle" style="fill:var(--muted)" font-size="13">нет трат</text>`;

  svg.querySelectorAll('.ring').forEach((ring) => {
    ring.addEventListener('click', () => toggleCategory(ring.dataset.key));
  });
}

function renderLegend() {
  const legend = $('legend');
  const items = state.summary.byCategory.filter((c) => c.total > 0);
  if (items.length === 0) {
    legend.innerHTML = '<div class="hint">Запишите первую трату — здесь появится разбивка.</div>';
    return;
  }
  legend.innerHTML = items
    .map(
      (item) => `
      <button class="legend-item" data-key="${item.key}" aria-pressed="${state.categoryFilter === item.key}">
        <span class="dot" style="background:${item.color}"></span>
        <span class="legend-title">${item.emoji} ${item.title}</span>
        <span class="legend-value">${money(item.total)}</span>
        <span class="legend-share">${Math.round(item.share * 100)}%</span>
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
  bars.innerHTML = days
    .map((day) => {
      const height = day.total > 0 ? Math.max(6, Math.round((day.total / max) * 100)) : 3;
      const classes = ['bar'];
      if (day.total === 0) classes.push('zero');
      if (day.day === state.me.user.today) classes.push('today');
      return `<div class="${classes.join(' ')}" data-day="${day.day}" aria-pressed="${state.dayFilter === day.day}"
        title="${dayTitle(day.day)}: ${money(day.total)}"><i style="height:${height}%"></i></div>`;
    })
    .join('');
  bars.querySelectorAll('.bar').forEach((bar) => {
    bar.addEventListener('click', () => toggleDay(bar.dataset.day));
  });

  const axis = $('bars-axis');
  if (days.length > 1) {
    axis.innerHTML = `<span>${dayTitle(days[0].day)}</span><span>${dayTitle(days[days.length - 1].day)}</span>`;
  } else {
    axis.innerHTML = '';
  }
}

function renderLimits() {
  const limits = state.summary.limits || [];
  $('limits-card').hidden = limits.length === 0;
  $('limits').innerHTML = limits
    .map((limit) => {
      const share = Math.min(limit.share, 1);
      const color = limit.share >= 1 ? 'var(--danger)' : limit.share >= 0.8 ? '#fbbf24' : limit.color;
      return `<div>
        <div class="limit-head">
          <span>${limit.emoji} ${limit.title}</span>
          <span>${money(limit.spent)} / ${money(limit.limit)}</span>
        </div>
        <div class="limit-bar"><div class="limit-fill" style="width:${share * 100}%;background:${color}"></div></div>
      </div>`;
    })
    .join('');
}

function renderList() {
  const list = $('list');
  let items = state.expenses;
  if (state.categoryFilter) items = items.filter((e) => e.category === state.categoryFilter);
  if (state.dayFilter) items = items.filter((e) => e.day === state.dayFilter);

  const note = [];
  if (state.categoryFilter) {
    const category = state.me.categories.find((c) => c.key === state.categoryFilter);
    note.push(`${category.emoji} ${category.title}`);
  }
  if (state.dayFilter) note.push(dayTitle(state.dayFilter));
  $('filter-note').innerHTML = note.length
    ? `— ${note.join(', ')} <button class="icon-btn" id="clear-filter" style="padding:2px 8px">сбросить</button>`
    : '';
  $('clear-filter')?.addEventListener('click', () => {
    state.categoryFilter = null;
    state.dayFilter = null;
    render();
  });

  if (items.length === 0) {
    list.innerHTML = '<div class="empty-state">Трат за этот период нет.<br>Запишите первую — в форме выше или в боте.</div>';
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
        <div class="day-head"><span>${dayTitle(day)}</span><span>${money(total)}</span></div>
        ${rows.map(renderExpense).join('')}
      </div>`;
    })
    .join('');

  list.querySelectorAll('[data-expense]').forEach((element) => {
    element.addEventListener('click', () => {
      state.openId = state.openId === Number(element.dataset.expense) ? null : Number(element.dataset.expense);
      renderList();
    });
  });
  bindEditor();
}

function renderExpense(expense) {
  if (state.openId === expense.id) return renderEditor(expense);
  const converted = expense.currency !== expense.baseCurrency
    ? `<small>${money(expense.amountBase, expense.baseCurrency)}</small>`
    : '';
  return `<div class="expense" data-expense="${expense.id}">
    <div class="emoji">${expense.categoryEmoji}</div>
    <div class="expense-main">
      <div class="expense-note">${escapeHtml(expense.note || expense.categoryTitle)}</div>
      <div class="expense-sub">${expense.categoryTitle} · ${localTime(expense)}</div>
    </div>
    <div class="expense-amount">${money(expense.amount, expense.currency)}${converted}</div>
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
      <select id="edit-currency" aria-label="Валюта" style="max-width:100px">${currencies}</select>
    </div>
    <input type="text" id="edit-note" value="${escapeHtml(expense.note)}" placeholder="Описание" aria-label="Описание">
    <div class="row">
      <select id="edit-category" aria-label="Категория">${categories}</select>
      <input type="date" id="edit-date" value="${expense.day}" aria-label="Дата" style="max-width:160px">
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
    const day = $('edit-date').value;
    const original = state.expenses.find((e) => e.id === id);
    const time = original ? localTimeIso(original) : '12:00:00.000';
    await api(`/expenses/${id}`, {
      method: 'PATCH',
      body: {
        amount,
        currency: $('edit-currency').value,
        category: $('edit-category').value,
        note: $('edit-note').value,
        spentAt: toUtcIso(day, time),
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

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

let toastTimer;
function toast(message) {
  const element = $('toast');
  element.textContent = message;
  element.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove('show'), 2200);
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
  const date = new Date(Date.UTC(y, m - 1 + delta, 1));
  state.month = date.toISOString().slice(0, 7);
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
    const text = input.value.trim();
    if (!text) return;
    try {
      const { expense } = await api('/expenses', { method: 'POST', body: { text } });
      input.value = '';
      toast(`Записал: ${money(expense.amount, expense.currency)} · ${expense.categoryTitle}`);
      await load();
    } catch (error) {
      toast(error.message === 'no amount' ? 'Не нашёл сумму. Например: кофе 350' : error.message);
    }
  });

  $('currency').addEventListener('change', async (event) => {
    await api('/settings', { method: 'PATCH', body: { currency: event.target.value } });
    state.me.user.currency = event.target.value;
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

  setPeriod('month');
}

boot();
