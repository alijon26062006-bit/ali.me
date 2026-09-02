import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { config } from './config.js';
import {
  getUser, upsertUser, updateUser, listExpenses, getExpense, deleteExpense,
  setLimit, getLimits,
} from './db.js';
import {
  addExpense, editExpense, buildSummary, limitsStatus, rebaseExpenses,
  expenseToJson, categoriesJson, toCsv,
} from './service.js';
import { parseExpense } from './parse.js';
import { getCategory } from './categories.js';
import { CURRENCY_CODES, isCurrency } from './money.js';
import { periodRange, monthRange, monthKeyOf, dayKey } from './time.js';
import {
  COOKIE_NAME, cookieOptions, createSession, verifySession, loginWithToken,
  verifyWebAppInitData, verifyTelegramLogin,
} from './auth.js';
import { handleUpdate } from './bot.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(here, '..', 'public');

export function createServer() {
  const app = express();
  app.disable('x-powered-by');
  app.set('trust proxy', 1);
  app.use(express.json({ limit: '1mb' }));
  app.use(cookies);

  app.get('/healthz', (req, res) => res.json({ ok: true, uptime: process.uptime() }));

  // Данные для экрана входа: ссылка на бота.
  app.get('/api/public', (req, res) => res.json({ botUsername: config.botUsername || null }));

  /* ------------------------------- вход ---------------------------------- */

  // Одноразовая ссылка из бота: /auth?token=...
  app.get('/auth', (req, res) => {
    const result = loginWithToken(String(req.query.token || ''));
    if (!result) {
      return res.status(401).sendFile(path.join(publicDir, 'login.html'));
    }
    res.cookie(COOKIE_NAME, result.session, cookieOptions());
    res.redirect('/');
  });

  // Панель, открытая внутри Telegram (Mini App).
  app.post('/api/auth/webapp', (req, res) => {
    const tgUser = verifyWebAppInitData(req.body?.initData);
    if (!tgUser) return res.status(401).json({ error: 'invalid initData' });
    const user = upsertUser({
      id: tgUser.id,
      first_name: tgUser.first_name,
      username: tgUser.username,
    });
    res.cookie(COOKIE_NAME, createSession(user.id), cookieOptions());
    res.json({ ok: true });
  });

  // Запасной вход — виджет Telegram Login.
  app.post('/api/auth/widget', (req, res) => {
    const userId = verifyTelegramLogin(req.body || {});
    if (!userId) return res.status(401).json({ error: 'invalid signature' });
    const user = upsertUser({
      id: userId,
      first_name: req.body.first_name,
      username: req.body.username,
    });
    res.cookie(COOKIE_NAME, createSession(user.id), cookieOptions());
    res.json({ ok: true });
  });

  app.post('/api/auth/logout', (req, res) => {
    res.clearCookie(COOKIE_NAME, { ...cookieOptions(), maxAge: undefined });
    res.json({ ok: true });
  });

  /* -------------------------------- API ---------------------------------- */

  const api = express.Router();
  api.use(requireUser);

  api.get('/me', (req, res) => {
    const { user } = req;
    res.json({
      user: {
        id: user.id,
        firstName: user.first_name,
        username: user.username,
        currency: user.currency,
        tzOffset: user.tz_offset,
        today: dayKey(new Date(), user.tz_offset),
        month: monthKeyOf(new Date(), user.tz_offset),
      },
      categories: categoriesJson(),
      currencies: CURRENCY_CODES,
      botUsername: config.botUsername || null,
    });
  });

  api.get('/summary', (req, res) => {
    const { user } = req;
    const range = resolveRange(req.query, user.tz_offset);
    if (!range) return res.status(400).json({ error: 'bad period' });
    res.json({
      ...buildSummary(user, range),
      month: req.query.month || monthKeyOf(new Date(), user.tz_offset),
      limits: limitsStatus(user),
    });
  });

  api.get('/expenses', (req, res) => {
    const { user } = req;
    const range = resolveRange(req.query, user.tz_offset);
    if (!range) return res.status(400).json({ error: 'bad period' });
    const rows = listExpenses(user.id, {
      from: range.from,
      to: range.to,
      category: req.query.category || undefined,
      limit: Math.min(Number(req.query.limit) || 500, 2000),
      offset: Number(req.query.offset) || 0,
    });
    res.json({ items: rows.map((row) => expenseToJson(row, user)) });
  });

  api.post('/expenses', (req, res) => {
    const { user } = req;
    const body = req.body || {};

    // Быстрый ввод из панели — тот же разбор, что и в боте.
    if (body.text && body.amount === undefined) {
      const parsed = parseExpense(body.text, { defaultCurrency: user.currency });
      if (!parsed) return res.status(400).json({ error: 'no amount' });
      const expense = addExpense(user, {
        amount: parsed.amount,
        currency: parsed.currency,
        category: body.category || parsed.category,
        note: parsed.note,
        spentAt: body.spentAt || shiftedDate(parsed.dayShift),
        source: 'web',
      });
      return res.status(201).json({ expense: expenseToJson(expense, user) });
    }

    const amount = Number(body.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      return res.status(400).json({ error: 'bad amount' });
    }
    const expense = addExpense(user, {
      amount,
      currency: isCurrency(body.currency) ? body.currency : user.currency,
      category: getCategory(body.category).key,
      note: body.note || '',
      spentAt: body.spentAt || new Date(),
      source: 'web',
    });
    res.status(201).json({ expense: expenseToJson(expense, user) });
  });

  api.patch('/expenses/:id', (req, res) => {
    const { user } = req;
    const id = Number(req.params.id);
    if (!getExpense(user.id, id)) return res.status(404).json({ error: 'not found' });
    const body = req.body || {};
    const patch = {};
    if (body.amount !== undefined) {
      const amount = Number(body.amount);
      if (!Number.isFinite(amount) || amount <= 0) return res.status(400).json({ error: 'bad amount' });
      patch.amount = amount;
    }
    if (body.currency !== undefined && isCurrency(body.currency)) patch.currency = body.currency;
    if (body.category !== undefined) patch.category = body.category;
    if (body.note !== undefined) patch.note = String(body.note);
    if (body.spentAt !== undefined) patch.spentAt = body.spentAt;
    const updated = editExpense(user, id, patch);
    res.json({ expense: expenseToJson(updated, user) });
  });

  api.delete('/expenses/:id', (req, res) => {
    const ok = deleteExpense(req.user.id, Number(req.params.id));
    if (!ok) return res.status(404).json({ error: 'not found' });
    res.json({ ok: true });
  });

  api.get('/limits', (req, res) => {
    res.json({ limits: limitsStatus(req.user), raw: getLimits(req.user.id) });
  });

  api.put('/limits', (req, res) => {
    const { category, amount } = req.body || {};
    const key = getCategory(category).key;
    setLimit(req.user.id, key, Number(amount) || 0);
    res.json({ limits: limitsStatus(req.user) });
  });

  api.patch('/settings', (req, res) => {
    const fields = {};
    if (req.body?.currency && isCurrency(req.body.currency)) {
      fields.currency = String(req.body.currency).toUpperCase();
    }
    if (req.body?.tzOffset !== undefined) {
      const offset = Number(req.body.tzOffset);
      if (Number.isFinite(offset) && Math.abs(offset) <= 14 * 60) fields.tz_offset = offset;
    }
    const updated = updateUser(req.user.id, fields);
    if (fields.currency && fields.currency !== req.user.currency) rebaseExpenses(updated);
    res.json({ ok: true, currency: updated.currency, tzOffset: updated.tz_offset });
  });

  api.get('/export.csv', (req, res) => {
    const { user } = req;
    const range = resolveRange(req.query, user.tz_offset);
    const rows = listExpenses(user.id, { from: range?.from, to: range?.to, limit: 100_000 });
    res.setHeader('content-type', 'text/csv; charset=utf-8');
    res.setHeader(
      'content-disposition',
      `attachment; filename="kopeyka-${dayKey(new Date(), user.tz_offset)}.csv"`,
    );
    res.send(toCsv(rows, user));
  });

  app.use('/api', api);

  /* ------------------------------ вебхук --------------------------------- */

  if (config.useWebhook) {
    app.post('/telegram/webhook', async (req, res) => {
      if (config.webhookSecret &&
          req.get('x-telegram-bot-api-secret-token') !== config.webhookSecret) {
        return res.sendStatus(401);
      }
      res.sendStatus(200); // отвечаем сразу, обработка — в фоне
      try {
        await handleUpdate(req.body);
      } catch (error) {
        console.error('webhook handler failed', error);
      }
    });
  }

  /* ------------------------------ статика -------------------------------- */

  app.get('/', (req, res) => {
    const userId = verifySession(req.cookies[COOKIE_NAME]);
    if (userId && getUser(userId)) return res.sendFile(path.join(publicDir, 'index.html'));
    res.sendFile(path.join(publicDir, 'login.html'));
  });

  app.use(express.static(publicDir, { index: false, maxAge: '1h' }));

  app.use((req, res) => res.status(404).json({ error: 'not found' }));
  app.use((error, req, res, next) => {
    console.error('server error', error);
    res.status(500).json({ error: 'internal error' });
  });

  return app;
}

/* ------------------------------ утилиты ---------------------------------- */

function cookies(req, res, next) {
  const header = req.headers.cookie || '';
  req.cookies = Object.fromEntries(
    header
      .split(';')
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        const index = part.indexOf('=');
        if (index === -1) return [part, ''];
        return [part.slice(0, index), decodeURIComponent(part.slice(index + 1))];
      }),
  );
  next();
}

/** Все API-запросы работают только со своими данными. */
function requireUser(req, res, next) {
  const userId = verifySession(req.cookies?.[COOKIE_NAME]);
  const user = userId ? getUser(userId) : null;
  if (!user) return res.status(401).json({ error: 'unauthorized' });
  req.user = user;
  next();
}

function resolveRange(query, tzOffset) {
  if (query.month) return monthRange(String(query.month), tzOffset);
  if (query.from && query.to) {
    const from = new Date(String(query.from));
    const to = new Date(String(query.to));
    if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return null;
    return { from, to, title: '' };
  }
  const period = String(query.period || 'month');
  if (!['today', 'yesterday', 'week', 'month', 'prev_month', 'all'].includes(period)) return null;
  return periodRange(period, tzOffset);
}

function shiftedDate(dayShift) {
  return new Date(Date.now() + (dayShift || 0) * 86_400_000);
}
