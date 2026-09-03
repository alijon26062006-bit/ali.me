import { config } from './config.js';
import {
  upsertUser, updateUser, markOnboarded, recentExpenses, getExpense, deleteExpense, deleteExpenseRange,
  listExpenses, setLimit, setPending, takePending, clearPending, markUpdateProcessed,
} from './db.js';
import {
  sendMessage, editMessageText, answerCallbackQuery, sendDocument, downloadFile, escapeHtml,
} from './telegram.js';
import { parseExpense, parseExpenseLines } from './parse.js';
import { CATEGORIES, getCategory, findExplicitCategory } from './categories.js';
import { formatMoney, matchCurrency, CURRENCY_CODES } from './money.js';
import { periodRange, formatDayHuman, formatDate, addDays, dayKey } from './time.js';
import {
  addExpense, editExpense, buildSummary, limitsStatus, limitWarning, rebaseExpenses, toCsv,
} from './service.js';
import { issueLoginLink } from './auth.js';
import { readReceipt, ocrAvailable } from './ocr.js';
import { understandExpenses, smartParseAvailable } from './smart.js';

export const BOT_COMMANDS = [
  { command: 'start', description: 'Начать и посмотреть подсказку' },
  { command: 'today', description: 'Итоги за сегодня' },
  { command: 'week', description: 'Итоги за неделю' },
  { command: 'month', description: 'Итоги за месяц' },
  { command: 'last', description: 'Последние траты: исправить или удалить' },
  { command: 'undo', description: 'Удалить последнюю трату' },
  { command: 'app', description: 'Открыть веб-панель' },
  { command: 'limits', description: 'Лимиты по категориям' },
  { command: 'export', description: 'Выгрузить траты в CSV' },
  { command: 'settings', description: 'Валюта и часовой пояс' },
  { command: 'help', description: 'Как пользоваться' },
];

/**
 * Страны для первого запуска: часовой пояс и валюта по умолчанию.
 * Всё остальное потом меняется командами /tz и /currency.
 */
const COUNTRIES = [
  { key: 'tj', flag: '🇹🇯', title: 'Таджикистан', tz: 300, currency: 'TJS' },
  { key: 'ru', flag: '🇷🇺', title: 'Россия', tz: 180, currency: 'RUB' },
  { key: 'kz', flag: '🇰🇿', title: 'Казахстан', tz: 300, currency: 'KZT' },
];

const countryByKey = (key) => COUNTRIES.find((country) => country.key === key);

const BUTTONS = {
  today: '📅 Сегодня',
  week: '🗓 Неделя',
  month: '📆 Месяц',
  panel: '📊 Панель',
  last: '🧾 Последние',
  limits: '🎯 Лимиты',
  settings: '⚙️ Настройки',
};

/** Нижнее меню: всё нужное — кнопками. Команды остаются для тех, кто их любит. */
const QUICK_KEYBOARD = {
  keyboard: [
    [{ text: BUTTONS.today }, { text: BUTTONS.week }, { text: BUTTONS.month }],
    [panelButton(), { text: BUTTONS.last }],
    [{ text: BUTTONS.limits }, { text: BUTTONS.settings }],
  ],
  resize_keyboard: true,
  is_persistent: true,
};

function panelButton() {
  // В Telegram панель открывается как Mini App — вход без пароля.
  if (config.publicUrl.startsWith('https://')) {
    return { text: BUTTONS.panel, web_app: { url: config.publicUrl } };
  }
  return { text: BUTTONS.panel };
}

export async function handleUpdate(update) {
  if (update.update_id !== undefined && !markUpdateProcessed(update.update_id)) return;
  if (update.callback_query) return handleCallback(update.callback_query);
  if (update.message) return handleMessage(update.message);
}

async function handleMessage(message) {
  const chat = message.chat;
  if (!chat || chat.type !== 'private') return;
  const user = upsertUser(message.from);

  if (message.photo?.length) return handlePhoto(user, chat.id, message);
  const text = (message.text || message.caption || '').trim();
  if (!text) return;

  if (text.startsWith('/')) return handleCommand(user, chat.id, text);

  switch (text) {
    case BUTTONS.today:
      return sendPeriod(user, chat.id, 'today');
    case BUTTONS.week:
      return sendPeriod(user, chat.id, 'week');
    case BUTTONS.month:
      return sendPeriod(user, chat.id, 'month');
    case BUTTONS.last:
      return sendLast(user, chat.id);
    case BUTTONS.panel:
      return sendPanelLink(user, chat.id);
    case BUTTONS.limits:
      return sendLimits(user, chat.id);
    case BUTTONS.settings:
      return sendSettings(user, chat.id);
    default:
      break;
  }

  // Незавершённый диалог правки: следующее сообщение заменяет трату.
  const pending = takePending(user.id);
  if (pending?.action === 'edit') return applyEdit(user, chat.id, pending.payload.id, text);
  if (pending?.action === 'limit') return applyLimitAmount(user, chat.id, pending.payload.category, text);

  return handleExpenseText(user, chat.id, text);
}

async function handleCommand(user, chatId, text) {
  const [rawCommand, ...rest] = text.split(/\s+/);
  const command = rawCommand.split('@')[0].toLowerCase();
  const args = rest.join(' ').trim();

  switch (command) {
    case '/start':
      return sendStart(user, chatId);
    case '/help':
      return sendHelp(user, chatId);
    case '/today':
      return sendPeriod(user, chatId, 'today');
    case '/week':
      return sendPeriod(user, chatId, 'week');
    case '/month':
    case '/stats':
      return sendPeriod(user, chatId, 'month');
    case '/last':
      return sendLast(user, chatId);
    case '/undo':
      return undoLast(user, chatId);
    case '/app':
    case '/panel':
      return sendPanelLink(user, chatId);
    case '/del':
    case '/delete':
      return deleteById(user, chatId, args);
    case '/edit':
      return startEdit(user, chatId, args);
    case '/limit':
      return handleLimitCommand(user, chatId, args);
    case '/limits':
      return sendLimits(user, chatId);
    case '/export':
      return sendExport(user, chatId);
    case '/currency':
      return handleCurrency(user, chatId, args);
    case '/tz':
      return handleTimezone(user, chatId, args);
    case '/settings':
      return sendSettings(user, chatId);
    case '/cancel':
      clearPending(user.id);
      return sendMessage(chatId, 'Хорошо, отменил.', { reply_markup: QUICK_KEYBOARD });
    case '/add':
      return handleExpenseText(user, chatId, args);
    default:
      return sendMessage(chatId, 'Не знаю такую команду. /help — список того, что я умею.');
  }
}

/* ---------------------------------- траты --------------------------------- */

async function handleExpenseText(user, chatId, text) {
  const entries = parseExpenseLines(text, { defaultCurrency: user.currency });

  // Строки, которые не поддались правилам, отдаём ИИ — он понимает
  // «два кофе по 15 тысяч» и прочую живую речь.
  const unparsed = entries.filter((entry) => !entry.parsed);
  if (unparsed.length > 0 && smartParseAvailable()) {
    try {
      const guesses = await understandExpenses(unparsed.map((entry) => entry.line), {
        currency: user.currency,
      });
      for (const guess of guesses || []) {
        const target = unparsed[guess.lineIndex];
        if (target && !target.parsed) target.parsed = guess;
      }
    } catch (error) {
      console.error('smart parse failed', error.message);
    }
  }

  applyMessageCurrency(entries);

  const parsedEntries = entries.filter((entry) => entry.parsed);
  if (parsedEntries.length === 0) {
    return sendMessage(
      chatId,
      [
        '🤔 Не нашёл сумму',
        '',
        'Напишите трату одним сообщением:',
        '<blockquote>кофе 350\nтакси 900 транспорт\nобед 12$\nвчера продукты 120000</blockquote>',
        'Несколько трат можно прислать списком — по одной в строке.',
      ].join('\n'),
    );
  }

  const created = parsedEntries.map(({ parsed }) =>
    addExpense(user, {
      amount: parsed.amount,
      currency: parsed.currency,
      category: parsed.category,
      note: parsed.note,
      spentAt: parsed.dayShift ? addDays(new Date(), parsed.dayShift) : new Date(),
      source: 'bot',
    }),
  );

  const skipped = entries.filter((entry) => !entry.parsed).map((entry) => entry.line);

  if (created.length === 1) {
    const text = expenseConfirmation(user, created[0], parsedEntries[0].parsed);
    return sendMessage(chatId, skipped.length ? `${text}\n\n${skippedNote(skipped)}` : text, {
      reply_markup: expenseKeyboard(created[0].id),
    });
  }

  return sendMessage(chatId, batchConfirmation(user, created, skipped), {
    reply_markup: {
      inline_keyboard: [
        [
          { text: '🧾 Список', callback_data: 'last:0' },
          { text: '🗑 Удалить всё', callback_data: `delb:${created[0].id}:${created[created.length - 1].id}` },
        ],
      ],
    },
  });
}

/**
 * Валюта, названная в одной строке сообщения, распространяется на остальные:
 * «такси 700 рублей / 459 завтрак» — обе траты в рублях.
 */
function applyMessageCurrency(entries) {
  const explicit = entries.find((entry) => entry.parsed?.currencyExplicit)?.parsed.currency;
  if (!explicit) return;
  for (const entry of entries) {
    if (entry.parsed && !entry.parsed.currencyExplicit) entry.parsed.currency = explicit;
  }
}

function skippedNote(skipped) {
  return `<i>Не понял: ${skipped.map((line) => escapeHtml(line)).join(' · ')}</i>`;
}

/** Одно сообщение — несколько трат: показываем список и общий итог. */
function batchConfirmation(user, expenses, skipped = []) {
  const money = (value, code = user.currency) => escapeHtml(formatMoney(value, code));
  const total = expenses.reduce((sum, expense) => sum + expense.amount_base, 0);
  const today = buildSummary(user, periodRange('today', user.tz_offset));
  const month = buildSummary(user, periodRange('month', user.tz_offset));

  const lines = [
    `✅  Записал <b>${expenses.length} ${plural(expenses.length, 'трату', 'траты', 'трат')}</b> на <b>${money(total)}</b>`,
    '',
  ];

  for (const expense of expenses) {
    const category = getCategory(expense.category);
    lines.push(
      `${category.emoji} <b>${money(expense.amount, expense.currency)}</b> — ${escapeHtml(expense.note)}`,
    );
  }

  lines.push('', `📅 Сегодня <b>${money(today.total)}</b>`, `📆 Месяц <b>${money(month.total)}</b>`);

  const warnings = [...new Set(expenses.map((expense) => limitWarning(user, expense.category)))].filter(Boolean);
  if (warnings.length) lines.push('', ...warnings.map((warning) => escapeHtml(warning)));
  if (skipped.length) lines.push('', skippedNote(skipped));

  return lines.join('\n');
}

function expenseConfirmation(user, expense, parsed) {
  const category = getCategory(expense.category);
  const today = buildSummary(user, periodRange('today', user.tz_offset));
  const month = buildSummary(user, periodRange('month', user.tz_offset));
  const money = (value, code = user.currency) => escapeHtml(formatMoney(value, code));

  const lines = [
    `✅  <b>${money(expense.amount, expense.currency)}</b>  ·  ${category.emoji} ${escapeHtml(category.title)}`,
    `<i>${escapeHtml(expense.note)}</i>`,
  ];

  if (expense.currency !== user.currency) {
    lines.push(`≈ ${money(expense.amount_base)} в итогах`);
  }
  if (dayKey(expense.spent_at, user.tz_offset) !== dayKey(new Date(), user.tz_offset)) {
    lines.push(`🗓 записал на ${formatDayHuman(dayKey(expense.spent_at, user.tz_offset), user.tz_offset)}`);
  }

  lines.push(
    '',
    `📅 Сегодня <b>${money(today.total)}</b>`,
    `📆 Месяц <b>${money(month.total)}</b>`,
  );

  if (parsed?.categorySource === 'default') {
    lines.push('', '<i>Категорию не угадал — поставьте её кнопкой 🗂</i>');
  }

  const warning = limitWarning(user, expense.category);
  if (warning) lines.push('', escapeHtml(warning));

  return lines.join('\n');
}

function expenseKeyboard(id) {
  return {
    inline_keyboard: [
      [
        { text: '🗂 Категория', callback_data: `cats:${id}` },
        { text: '✏️ Исправить', callback_data: `edit:${id}` },
        { text: '🗑 Удалить', callback_data: `del:${id}` },
      ],
    ],
  };
}

function categoriesKeyboard(id) {
  const buttons = CATEGORIES.map((c) => ({
    text: `${c.emoji} ${c.title}`,
    callback_data: `setcat:${id}:${c.key}`,
  }));
  const rows = [];
  for (let i = 0; i < buttons.length; i += 2) rows.push(buttons.slice(i, i + 2));
  rows.push([{ text: '‹ Назад', callback_data: `back:${id}` }]);
  return { inline_keyboard: rows };
}

async function applyEdit(user, chatId, id, text) {
  const current = getExpense(user.id, id);
  if (!current) return sendMessage(chatId, 'Трата уже удалена.');

  const parsed = parseExpense(text, { defaultCurrency: current.currency });
  if (!parsed) {
    // Только сумма или только описание — тоже валидный ввод.
    const explicit = findExplicitCategory(text);
    if (explicit) {
      const updated = editExpense(user, id, { category: explicit.key });
      return sendMessage(chatId, expenseConfirmation(user, updated), {
        reply_markup: expenseKeyboard(id),
      });
    }
    const updated = editExpense(user, id, { note: text });
    return sendMessage(chatId, expenseConfirmation(user, updated), {
      reply_markup: expenseKeyboard(id),
    });
  }

  const updated = editExpense(user, id, {
    amount: parsed.amount,
    currency: parsed.currencyExplicit ? parsed.currency : current.currency,
    category: parsed.categorySource === 'default' ? current.category : parsed.category,
    note: parsed.note,
  });
  return sendMessage(chatId, `✏️ Исправил.\n\n${expenseConfirmation(user, updated)}`, {
    reply_markup: expenseKeyboard(id),
  });
}

async function startEdit(user, chatId, args) {
  const id = Number(args.replace(/^#/, ''));
  const expense = Number.isFinite(id) ? getExpense(user.id, id) : recentExpenses(user.id, 1)[0];
  if (!expense) return sendMessage(chatId, 'Не нашёл такую трату. /last — последние записи.');
  setPending(user.id, 'edit', { id: expense.id });
  return sendMessage(
    chatId,
    `Пришлите исправленный вариант траты «${escapeHtml(expense.note)}» одним сообщением, например <b>кофе 400</b>.\n/cancel — отмена.`,
  );
}

async function deleteById(user, chatId, args) {
  const id = Number(String(args).replace(/^#/, ''));
  if (!Number.isFinite(id)) return sendMessage(chatId, 'Формат: /del 12 (номер видно в /last).');
  const expense = getExpense(user.id, id);
  if (!expense) return sendMessage(chatId, 'Такой траты нет.');
  deleteExpense(user.id, id);
  return sendMessage(
    chatId,
    `🗑 Удалил: ${escapeHtml(formatMoney(expense.amount, expense.currency))} · ${escapeHtml(expense.note)}`,
  );
}

async function undoLast(user, chatId) {
  const [last] = recentExpenses(user.id, 1);
  if (!last) return sendMessage(chatId, 'Пока нечего удалять.');
  deleteExpense(user.id, last.id);
  return sendMessage(
    chatId,
    `↩️ Удалил последнюю трату: ${escapeHtml(formatMoney(last.amount, last.currency))} · ${escapeHtml(last.note)}`,
  );
}

async function sendLast(user, chatId) {
  // Показываем в том же порядке, что и панель: сначала свежие по дате траты.
  const rows = recentExpenses(user.id, 6).sort(
    (a, b) => Date.parse(b.spent_at) - Date.parse(a.spent_at) || b.id - a.id,
  );
  if (rows.length === 0) {
    return sendMessage(chatId, ['🧾 <b>Последние траты</b>', '', 'Пока пусто. Напишите, например: <code>кофе 350</code>'].join('\n'));
  }

  const lines = ['🧾 <b>Последние траты</b>', ''];
  const keyboard = [];
  let currentDay = null;

  rows.forEach((row, index) => {
    const day = dayKey(row.spent_at, user.tz_offset);
    if (day !== currentDay) {
      currentDay = day;
      lines.push(`<i>${formatDayHuman(day, user.tz_offset)}</i>`);
    }
    const category = getCategory(row.category);
    lines.push(
      `${index + 1}. ${category.emoji} <b>${escapeHtml(formatMoney(row.amount, row.currency))}</b> — ${escapeHtml(row.note)}`,
    );
    keyboard.push([
      { text: `✏️ ${index + 1}`, callback_data: `edit:${row.id}` },
      { text: `🗂 ${index + 1}`, callback_data: `cats:${row.id}` },
      { text: `🗑 ${index + 1}`, callback_data: `del:${row.id}` },
    ]);
  });

  lines.push('', '<i>✏️ исправить · 🗂 категория · 🗑 удалить</i>');
  return sendMessage(chatId, lines.join('\n'), { reply_markup: { inline_keyboard: keyboard } });
}

/* --------------------------------- отчёты --------------------------------- */

async function sendPeriod(user, chatId, period) {
  const range = periodRange(period, user.tz_offset);
  const summary = buildSummary(user, range);
  return sendMessage(chatId, renderSummary(user, summary, period), {
    reply_markup: panelInlineKeyboard(),
  });
}

export function renderSummary(user, summary, period) {
  const money = (value) => escapeHtml(formatMoney(value, user.currency));
  const titles = {
    today: `📅 <b>Сегодня</b>, ${formatDate(dayKey(new Date(), user.tz_offset))}`,
    week: '🗓 <b>Эта неделя</b>',
    month: '📆 <b>Этот месяц</b>',
  };
  const lines = [titles[period] || '📊 <b>Итоги</b>', ''];

  if (summary.count === 0) {
    lines.push(
      'Пока пусто — и это хорошая новость 🙂',
      '',
      'Запишите трату одним сообщением:',
      '<code>кофе 350</code>',
    );
    return lines.join('\n');
  }

  lines.push(`💰 <b>${money(summary.total)}</b>`);
  const meta = [`${summary.count} ${plural(summary.count, 'трата', 'траты', 'трат')}`];
  if (period !== 'today') meta.push(`${formatMoney(summary.average, user.currency)} в день`);
  lines.push(escapeHtml(meta.join('  ·  ')), '');

  const top = summary.byCategory.slice(0, 6);
  for (const category of top) {
    lines.push(
      `${category.emoji} ${escapeHtml(category.title)} — <b>${money(category.total)}</b> · ${Math.round(category.share * 100)}%`,
      `<code>${progressBar(category.share)}</code>`,
    );
  }

  if (summary.byCategory.length > top.length) {
    const rest = summary.byCategory.slice(top.length);
    const restTotal = rest.reduce((sum, c) => sum + c.total, 0);
    lines.push(`• и ещё ${rest.length} ${plural(rest.length, 'категория', 'категории', 'категорий')} — ${money(restTotal)}`);
  }

  if (period !== 'today') {
    const busiest = summary.days.reduce((best, day) => (day.total > (best?.total || 0) ? day : best), null);
    if (busiest && busiest.total > 0) {
      lines.push('', `🔺 Самый дорогой день — ${formatDayHuman(busiest.day, user.tz_offset)}, ${money(busiest.total)}`);
    }
  }

  return lines.join('\n');
}

/** Полоска прогресса из блоков: доля 0…1 → «▰▰▰▰▱▱▱▱▱▱». */
function progressBar(share, width = 10) {
  const filled = Math.max(1, Math.min(width, Math.round(share * width)));
  return `${'▰'.repeat(filled)}${'▱'.repeat(width - filled)}`;
}

function panelInlineKeyboard() {
  if (config.publicUrl.startsWith('https://')) {
    return { inline_keyboard: [[{ text: '📊 Открыть панель', web_app: { url: config.publicUrl } }]] };
  }
  return undefined;
}

/* --------------------------- панель, настройки, CSV ------------------------ */

async function sendPanelLink(user, chatId) {
  const month = buildSummary(user, periodRange('month', user.tz_offset));
  const { url } = issueLoginLink(user.id);
  const miniApp = config.publicUrl.startsWith('https://');

  // Внутри Telegram панель открывается как Mini App, ссылка остаётся запасным путём.
  const rows = [];
  if (miniApp) rows.push([{ text: '📊 Открыть панель', web_app: { url: config.publicUrl } }]);
  rows.push([{ text: miniApp ? '🌐 Открыть в браузере' : '📊 Открыть панель', url }]);

  return sendMessage(
    chatId,
    [
      '📊 <b>Ваша панель</b>',
      '',
      `В этом месяце: <b>${escapeHtml(formatMoney(month.total, user.currency))}</b> · ${month.count} ${plural(month.count, 'трата', 'траты', 'трат')}`,
      'Кольцо по категориям, столбики по дням и правка любой траты.',
      '',
      miniApp
        ? '<i>Откроется прямо здесь, в Telegram — ни браузера, ни пароля.</i>'
        : '<i>Ссылка одноразовая и живёт 15 минут: ни регистрации, ни пароля.</i>',
    ].join('\n'),
    { reply_markup: { inline_keyboard: rows } },
  );
}

async function sendSettings(user, chatId) {
  const limits = limitsStatus(user);
  const offset = user.tz_offset;
  const lines = [
    '⚙️ <b>Настройки</b>',
    '',
    `💱 Валюта итогов: <b>${user.currency}</b>`,
    `🕒 Часовой пояс: <b>UTC${offset >= 0 ? '+' : ''}${offset / 60}</b>`,
    `🎯 Лимиты: <b>${limits.length ? `${limits.length} ${plural(limits.length, 'категория', 'категории', 'категорий')}` : 'не заданы'}</b>`,
    ocrAvailable() ? '📷 Чеки по фото: <b>включено</b>' : '📷 Чеки по фото: выключено',
    '',
    '<i>Всё меняется кнопками ниже.</i>',
  ];
  return sendMessage(chatId, lines.join('\n'), {
    reply_markup: {
      inline_keyboard: [
        [
          { text: '💱 Валюта', callback_data: 'setcur:0' },
          { text: '🌍 Страна и время', callback_data: 'setup:0' },
        ],
        [
          { text: '🎯 Лимиты', callback_data: 'limmenu:0' },
          { text: '📄 Экспорт CSV', callback_data: 'export:0' },
        ],
        [{ text: '💡 Как пользоваться', callback_data: 'help:0' }],
      ],
    },
  });
}

async function handleCurrency(user, chatId, args) {
  const code = matchCurrency(args.trim());
  if (!code) {
    return sendMessage(
      chatId,
      `Формат: <code>/currency USD</code>\nДоступны: ${CURRENCY_CODES.join(', ')}`,
    );
  }
  const updated = updateUser(user.id, { currency: code });
  rebaseExpenses(updated);
  return sendMessage(chatId, `Базовая валюта теперь <b>${code}</b>. Итоги пересчитал.`);
}

async function handleTimezone(user, chatId, args) {
  const match = /^([+-]?\d{1,2})(?::(\d{2}))?$/.exec(args.trim().replace(/^utc/i, ''));
  if (!match) return sendMessage(chatId, 'Формат: <code>/tz +5</code> или <code>/tz -3:30</code>');
  const hours = Number(match[1]);
  const minutes = Number(match[2] || 0) * Math.sign(hours || 1);
  const offset = hours * 60 + minutes;
  if (Math.abs(offset) > 14 * 60) return sendMessage(chatId, 'Такого пояса не бывает 🙂');
  updateUser(user.id, { tz_offset: offset });
  return sendMessage(chatId, `Часовой пояс: <b>UTC${offset >= 0 ? '+' : ''}${offset / 60}</b>`);
}

async function handleLimitCommand(user, chatId, args) {
  if (!args) {
    return sendMessage(
      chatId,
      'Формат: <code>/limit кафе 500000</code> — месячный лимит по категории.\n<code>/limit кафе 0</code> — убрать лимит.',
    );
  }
  const parsed = parseExpense(args, { defaultCurrency: user.currency });
  const explicit = findExplicitCategory(args);
  const categoryKey = explicit?.key || parsed?.category;
  const amountMatch = /(\d[\d\s ]*(?:[.,]\d+)?)\s*$/.exec(args);
  const amount = parsed ? parsed.amount : Number(String(amountMatch?.[1] || '').replace(/[\s ]/g, '').replace(',', '.'));

  if (!categoryKey || !Number.isFinite(amount)) {
    return sendMessage(chatId, 'Не понял. Пример: <code>/limit кафе 500000</code>');
  }
  const category = getCategory(categoryKey);
  setLimit(user.id, category.key, amount);
  if (amount <= 0) {
    return sendMessage(chatId, `Лимит по «${category.emoji} ${escapeHtml(category.title)}» снят.`);
  }
  return sendMessage(
    chatId,
    `Лимит по «${category.emoji} ${escapeHtml(category.title)}»: <b>${escapeHtml(formatMoney(amount, user.currency))}</b> в месяц.\nПредупрежу на 80% и при превышении.`,
  );
}

async function sendLimits(user, chatId) {
  const limits = limitsStatus(user);
  const money = (value) => escapeHtml(formatMoney(value, user.currency));
  const lines = ['🎯 <b>Лимиты на этот месяц</b>', ''];

  if (limits.length === 0) {
    lines.push(
      'Пока не заданы.',
      'Выберите категорию кнопкой ниже — предупрежу на 80% и при превышении.',
    );
  } else {
    for (const limit of limits) {
      const percent = Math.round(limit.share * 100);
      const status = limit.share >= 1 ? '🚨' : limit.share >= 0.8 ? '⚠️' : '✅';
      const left = limit.limit - limit.spent;
      lines.push(
        `${status} ${limit.emoji} ${escapeHtml(limit.title)} — ${percent}%`,
        `<code>${progressBar(limit.share)}</code> ${money(limit.spent)} из ${money(limit.limit)}`,
        left >= 0 ? `<i>осталось ${money(left)}</i>` : `<i>перерасход ${money(-left)}</i>`,
        '',
      );
    }
  }

  return sendMessage(chatId, lines.join('\n').trim(), {
    reply_markup: { inline_keyboard: limitsKeyboard(user) },
  });
}

/** Кнопки для лимитов: задать новый и снять существующие. */
function limitsKeyboard(user) {
  const current = new Map(limitsStatus(user).map((limit) => [limit.key, limit]));
  const rows = [[{ text: '➕ Поставить лимит', callback_data: 'limmenu:0' }]];
  for (const limit of current.values()) {
    rows.push([
      { text: `✏️ ${limit.emoji} ${limit.title}`, callback_data: `limset:${limit.key}` },
      { text: '🗑', callback_data: `limdel:${limit.key}` },
    ]);
  }
  return rows;
}

/** Выбор категории, для которой ставим лимит. */
function limitCategoriesKeyboard() {
  const buttons = CATEGORIES.filter((category) => category.key !== 'other').map((category) => ({
    text: `${category.emoji} ${category.title}`,
    callback_data: `limset:${category.key}`,
  }));
  const rows = [];
  for (let i = 0; i < buttons.length; i += 2) rows.push(buttons.slice(i, i + 2));
  return rows;
}

/** Пользователь прислал сумму лимита в ответ на вопрос. */
async function applyLimitAmount(user, chatId, categoryKey, text) {
  const category = getCategory(categoryKey);
  const parsed = parseExpense(text, { defaultCurrency: user.currency });
  const amount = parsed
    ? parsed.amount
    : Number(String(text).replace(/[^\d.,]/g, '').replace(',', '.'));

  if (!Number.isFinite(amount) || amount <= 0) {
    setPending(user.id, 'limit', { category: categoryKey });
    return sendMessage(chatId, 'Не понял сумму. Пришлите число, например <b>500000</b>.');
  }

  setLimit(user.id, category.key, amount);
  await sendMessage(
    chatId,
    [
      `🎯 Лимит по «${category.emoji} ${escapeHtml(category.title)}»: <b>${escapeHtml(formatMoney(amount, user.currency))}</b> в месяц.`,
      'Предупрежу на 80% и при превышении.',
    ].join('\n'),
  );
  return sendLimits(user, chatId);
}

async function sendExport(user, chatId) {
  const rows = listExpenses(user.id, { limit: 100_000 });
  if (rows.length === 0) return sendMessage(chatId, 'Экспортировать пока нечего.');
  const csv = toCsv(rows, user);
  return sendDocument(chatId, {
    filename: `kopeyka-${dayKey(new Date(), user.tz_offset)}.csv`,
    contentType: 'text/csv; charset=utf-8',
    data: Buffer.from(csv, 'utf8'),
    caption: `📄 ${rows.length} ${plural(rows.length, 'трата', 'траты', 'трат')} — открывается в Excel и Google Sheets.`,
  });
}

/* ---------------------------------- фото ---------------------------------- */

async function handlePhoto(user, chatId, message) {
  if (!ocrAvailable()) {
    return sendMessage(
      chatId,
      'Распознавание чеков сейчас выключено. Напишите сумму текстом: <b>продукты 120000</b>',
    );
  }
  const photo = message.photo[message.photo.length - 1];
  const notice = await sendMessage(chatId, '🔍 Смотрю чек…');
  try {
    const file = await downloadFile(photo.file_id);
    const receipt = await readReceipt(file.buffer, mediaTypeOf(file.path));
    if (!receipt) {
      return editMessageText(
        chatId,
        notice.message_id,
        'Не смог прочитать сумму на чеке 😕 Напишите её текстом, например <b>продукты 120000</b>',
      );
    }
    const caption = (message.caption || '').trim();
    const note = caption || receipt.merchant || 'Чек';
    const expense = addExpense(user, {
      amount: receipt.amount,
      currency: receipt.currency || user.currency,
      category: receipt.category,
      note,
      source: 'photo',
    });
    await editMessageText(
      chatId,
      notice.message_id,
      `📷 Распознал чек.\n\n${expenseConfirmation(user, expense)}`,
      { reply_markup: expenseKeyboard(expense.id) },
    );
  } catch (error) {
    console.error('receipt OCR failed', error);
    await editMessageText(
      chatId,
      notice.message_id,
      'С чеком не получилось 😕 Напишите сумму текстом: <b>продукты 120000</b>',
    );
  }
}

function mediaTypeOf(filePath) {
  if (/\.png$/i.test(filePath)) return 'image/png';
  if (/\.webp$/i.test(filePath)) return 'image/webp';
  return 'image/jpeg';
}

/* -------------------------------- callbacks ------------------------------- */

async function handleCallback(query) {
  const user = upsertUser(query.from);
  const chatId = query.message?.chat?.id;
  const messageId = query.message?.message_id;
  const [action, rawId, extra] = String(query.data || '').split(':');
  if (!chatId) return answerCallbackQuery(query.id);

  // Шаги настройки и групповые действия — они не привязаны к одной трате.
  switch (action) {
    case 'ctry': {
      const country = countryByKey(rawId);
      if (!country) return answerCallbackQuery(query.id);
      updateUser(user.id, { tz_offset: country.tz });
      await answerCallbackQuery(query.id, `${country.flag} ${country.title}`);
      return editMessageText(
        chatId,
        messageId,
        [
          `${country.flag} <b>${escapeHtml(country.title)}</b> — время UTC${country.tz >= 0 ? '+' : ''}${country.tz / 60}`,
          '',
          'В какой валюте считать итоги?',
          '<i>Траты можно писать в любой валюте — пересчитаю сам.</i>',
        ].join('\n'),
        { reply_markup: currencyKeyboard(country) },
      );
    }
    case 'cur': {
      const code = matchCurrency(rawId);
      if (!code) return answerCallbackQuery(query.id);
      const wasOnboarded = Boolean(user.onboarded_at);
      const updated = markOnboarded(updateUser(user.id, { currency: code }).id);
      rebaseExpenses(updated);
      await answerCallbackQuery(query.id, `Валюта: ${code}`);
      await editMessageText(chatId, messageId, `💱 Валюта итогов: <b>${code}</b>`);
      // Инструкцию показываем только тем, кто настраивается впервые.
      return wasOnboarded ? sendSettings(updated, chatId) : sendIntro(updated, chatId);
    }
    case 'setup':
      await answerCallbackQuery(query.id);
      return sendStart(user, chatId, { force: true });
    case 'last':
      await answerCallbackQuery(query.id);
      return sendLast(user, chatId);
    case 'help':
      await answerCallbackQuery(query.id);
      return sendHelp(user, chatId);
    case 'export':
      await answerCallbackQuery(query.id, 'Готовлю файл…');
      return sendExport(user, chatId);
    case 'setcur':
      await answerCallbackQuery(query.id);
      return sendMessage(chatId, '💱 В какой валюте считать итоги?', {
        reply_markup: currencyKeyboard({ currency: user.currency }),
      });
    case 'limmenu':
      await answerCallbackQuery(query.id);
      return sendMessage(chatId, '🎯 Для какой категории поставить месячный лимит?', {
        reply_markup: { inline_keyboard: limitCategoriesKeyboard() },
      });
    case 'limset': {
      const category = getCategory(rawId);
      setPending(user.id, 'limit', { category: category.key });
      await answerCallbackQuery(query.id);
      return sendMessage(
        chatId,
        [
          `🎯 Лимит по «${category.emoji} ${escapeHtml(category.title)}» на месяц.`,
          `Пришлите сумму в ${user.currency}, например <b>500000</b>.`,
          '/cancel — отмена.',
        ].join('\n'),
      );
    }
    case 'limdel': {
      const category = getCategory(rawId);
      setLimit(user.id, category.key, 0);
      await answerCallbackQuery(query.id, 'Лимит снят');
      return sendLimits(user, chatId);
    }
    case 'delb': {
      const removed = deleteExpenseRange(user.id, Number(rawId), Number(extra));
      await answerCallbackQuery(query.id, removed ? 'Удалено' : 'Уже удалено');
      return editMessageText(
        chatId,
        messageId,
        `🗑 Удалил ${removed} ${plural(removed, 'трату', 'траты', 'трат')} из этого сообщения.`,
      );
    }
    default:
      break;
  }

  const id = Number(rawId);
  if (!Number.isFinite(id)) return answerCallbackQuery(query.id);

  const expense = getExpense(user.id, id);
  if (!expense) {
    await answerCallbackQuery(query.id, 'Трата уже удалена');
    return;
  }

  switch (action) {
    case 'del': {
      deleteExpense(user.id, id);
      await answerCallbackQuery(query.id, 'Удалено');
      return editMessageText(
        chatId,
        messageId,
        `🗑 Удалено: ${escapeHtml(formatMoney(expense.amount, expense.currency))} · ${escapeHtml(expense.note)}`,
      );
    }
    case 'cats':
      await answerCallbackQuery(query.id);
      return editMessageText(chatId, messageId, 'Выберите категорию:', {
        reply_markup: categoriesKeyboard(id),
      });
    case 'setcat': {
      const updated = editExpense(user, id, { category: extra });
      await answerCallbackQuery(query.id, `Категория: ${getCategory(extra).title}`);
      return editMessageText(chatId, messageId, expenseConfirmation(user, updated), {
        reply_markup: expenseKeyboard(id),
      });
    }
    case 'back':
      await answerCallbackQuery(query.id);
      return editMessageText(chatId, messageId, expenseConfirmation(user, expense), {
        reply_markup: expenseKeyboard(id),
      });
    case 'edit':
      setPending(user.id, 'edit', { id });
      await answerCallbackQuery(query.id, 'Пришлите новый вариант');
      return sendMessage(
        chatId,
        'Пришлите исправленную трату одним сообщением, например <b>кофе 400</b>.\n/cancel — отмена.',
      );
    default:
      return answerCallbackQuery(query.id);
  }
}

/* --------------------------------- тексты --------------------------------- */

async function sendStart(user, chatId, { force = false } = {}) {
  // Настройку спрашиваем один раз: дальше /start просто напоминает, как пользоваться.
  if (user.onboarded_at && !force) return sendIntro(user, chatId, { returning: true });

  return sendMessage(
    chatId,
    [
      `🪙 <b>Копейка</b> — трекер расходов, ${escapeHtml(user.first_name || 'привет')}!`,
      '',
      'Настроим за два касания. Откуда вы?',
      '<i>Это нужно, чтобы «сегодня» считалось по вашему времени.</i>',
    ].join('\n'),
    {
      reply_markup: {
        inline_keyboard: [
          COUNTRIES.map((country) => ({
            text: `${country.flag} ${country.title}`,
            callback_data: `ctry:${country.key}`,
          })),
        ],
      },
    },
  );
}

/** Второй шаг онбординга: валюта, в которой считать итоги. */
function currencyKeyboard(country) {
  const codes = [...new Set([country.currency, 'USD', 'RUB', 'KZT', 'TJS', 'UZS'])].slice(0, 6);
  const buttons = codes.map((code) => ({
    text: `${CURRENCY_LABEL[code] || ''} ${code}`.trim(),
    callback_data: `cur:${code}`,
  }));
  const rows = [];
  for (let i = 0; i < buttons.length; i += 3) rows.push(buttons.slice(i, i + 3));
  return { inline_keyboard: rows };
}

const CURRENCY_LABEL = { TJS: '🇹🇯', RUB: '🇷🇺', KZT: '🇰🇿', UZS: '🇺🇿', USD: '💵', EUR: '💶' };

/** Финал онбординга и обычное приветствие для тех, кто уже настроен. */
async function sendIntro(user, chatId, { returning = false } = {}) {
  const offset = user.tz_offset;
  const lines = [
    returning
      ? `🪙 <b>Копейка</b> на связи, ${escapeHtml(user.first_name || 'привет')}!`
      : '✅ Готово! Настроил под вас.',
    '',
    returning
      ? `Валюта итогов <b>${user.currency}</b>, время UTC${offset >= 0 ? '+' : ''}${offset / 60} — сменить в /settings.`
      : null,
    returning ? '' : null,
    'Напишите трату <b>одним сообщением</b>:',
    '<blockquote>кофе 350\nтакси 900 работа\nобед 12$\nвчера продукты 120000</blockquote>',
    'Можно списком — по одной трате в строке. Категорию подберу сам,',
    'ошибусь — поправите кнопкой под сообщением.',
    '',
    '📅 Итоги: /today · /week · /month',
    '📊 Графики и правки: /app',
    ocrAvailable() ? '📷 Пришлите фото чека — распознаю сумму сам' : null,
  ].filter((line) => line !== null);
  await sendMessage(chatId, lines.join('\n'), { reply_markup: QUICK_KEYBOARD });
}

async function sendHelp(user, chatId) {
  const lines = [
    '💡 <b>Как пользоваться</b>',
    '',
    '<b>Записать трату</b> — одно сообщение:',
    '<blockquote>кофе 350 — сумма и описание\n'
      + 'такси 900 транспорт — категория словом\n'
      + 'обед 12$ — любая валюта\n'
      + 'продукты 12к — 12 000\n'
      + 'вчера аптека 45000 — задним числом</blockquote>',
    ocrAvailable() ? '📷 Фото чека — распознаю сумму сам.' : null,
    '',
    '📅 <b>Итоги</b> — /today · /week · /month',
    '✏️ <b>Исправить</b> — кнопки под тратой, /last, /undo, <code>/del 12</code>',
    '📊 <b>Панель с графиками</b> — /app',
    '🎯 <b>Лимиты</b> — <code>/limit кафе 500000</code>, /limits',
    '📄 <b>Экспорт</b> — /export (Excel, Google Sheets)',
    '⚙️ <b>Настройки</b> — <code>/currency USD</code>, <code>/tz +5</code>, /settings',
  ].filter((line) => line !== null);
  await sendMessage(chatId, lines.join('\n'), { reply_markup: QUICK_KEYBOARD });
}

function plural(count, one, few, many) {
  const n = Math.abs(count) % 100;
  const n1 = n % 10;
  if (n > 10 && n < 20) return many;
  if (n1 > 1 && n1 < 5) return few;
  if (n1 === 1) return one;
  return many;
}
