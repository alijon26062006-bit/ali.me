import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';
import { config } from './config.js';

fs.mkdirSync(path.dirname(config.dbPath), { recursive: true });

export const db = new Database(config.dbPath);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
CREATE TABLE IF NOT EXISTS users (
  id          INTEGER PRIMARY KEY,           -- telegram user id
  first_name  TEXT,
  username    TEXT,
  currency    TEXT NOT NULL DEFAULT 'UZS',
  tz_offset   INTEGER NOT NULL DEFAULT 300,  -- минуты от UTC
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS expenses (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount      REAL NOT NULL,                 -- сумма в валюте траты
  currency    TEXT NOT NULL,
  amount_base REAL NOT NULL,                 -- пересчёт в базовую валюту пользователя
  category    TEXT NOT NULL,
  note        TEXT NOT NULL DEFAULT '',
  spent_at    TEXT NOT NULL,                 -- ISO UTC
  source      TEXT NOT NULL DEFAULT 'bot',   -- bot | web | photo
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_expenses_user_time ON expenses(user_id, spent_at);

CREATE TABLE IF NOT EXISTS limits (
  user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category  TEXT NOT NULL,
  amount    REAL NOT NULL,
  PRIMARY KEY (user_id, category)
);

CREATE TABLE IF NOT EXISTS login_tokens (
  token       TEXT PRIMARY KEY,
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at  TEXT NOT NULL,
  used_at     TEXT
);

-- Незавершённые диалоги бота (редактирование траты, подтверждение чека).
CREATE TABLE IF NOT EXISTS pending (
  user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  action      TEXT NOT NULL,
  payload     TEXT NOT NULL DEFAULT '{}',
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Идемпотентность: Telegram может прислать один и тот же апдейт дважды.
CREATE TABLE IF NOT EXISTS processed_updates (
  update_id   INTEGER PRIMARY KEY,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
`);

export function upsertUser({ id, first_name, username }) {
  db.prepare(
    `INSERT INTO users (id, first_name, username, currency, tz_offset)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET first_name = excluded.first_name, username = excluded.username`,
  ).run(id, first_name || '', username || '', config.defaultCurrency, config.defaultTzOffset);
  return getUser(id);
}

export function getUser(id) {
  return db.prepare('SELECT * FROM users WHERE id = ?').get(id);
}

export function updateUser(id, fields) {
  const allowed = ['currency', 'tz_offset'];
  const entries = Object.entries(fields).filter(([key]) => allowed.includes(key));
  if (entries.length === 0) return getUser(id);
  const sql = `UPDATE users SET ${entries.map(([k]) => `${k} = ?`).join(', ')} WHERE id = ?`;
  db.prepare(sql).run(...entries.map(([, v]) => v), id);
  return getUser(id);
}

export function insertExpense(expense) {
  const info = db
    .prepare(
      `INSERT INTO expenses (user_id, amount, currency, amount_base, category, note, spent_at, source)
       VALUES (@user_id, @amount, @currency, @amount_base, @category, @note, @spent_at, @source)`,
    )
    .run(expense);
  return getExpense(expense.user_id, info.lastInsertRowid);
}

/** Всегда фильтруем по user_id — чужие траты недоступны по определению. */
export function getExpense(userId, id) {
  return db.prepare('SELECT * FROM expenses WHERE id = ? AND user_id = ?').get(id, userId);
}

export function updateExpense(userId, id, fields) {
  const allowed = ['amount', 'currency', 'amount_base', 'category', 'note', 'spent_at'];
  const entries = Object.entries(fields).filter(([key]) => allowed.includes(key));
  if (entries.length === 0) return getExpense(userId, id);
  const sql = `UPDATE expenses SET ${entries.map(([k]) => `${k} = ?`).join(', ')}, updated_at = datetime('now')
               WHERE id = ? AND user_id = ?`;
  db.prepare(sql).run(...entries.map(([, v]) => v), id, userId);
  return getExpense(userId, id);
}

export function deleteExpense(userId, id) {
  return db.prepare('DELETE FROM expenses WHERE id = ? AND user_id = ?').run(id, userId).changes > 0;
}

export function listExpenses(userId, { from, to, limit = 500, offset = 0, category } = {}) {
  const clauses = ['user_id = ?'];
  const params = [userId];
  if (from) {
    clauses.push('spent_at >= ?');
    params.push(new Date(from).toISOString());
  }
  if (to) {
    clauses.push('spent_at < ?');
    params.push(new Date(to).toISOString());
  }
  if (category) {
    clauses.push('category = ?');
    params.push(category);
  }
  return db
    .prepare(
      `SELECT * FROM expenses WHERE ${clauses.join(' AND ')}
       ORDER BY spent_at DESC, id DESC LIMIT ? OFFSET ?`,
    )
    .all(...params, limit, offset);
}

export function recentExpenses(userId, limit = 10) {
  return db
    .prepare('SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT ?')
    .all(userId, limit);
}

export function sumBetween(userId, from, to) {
  const row = db
    .prepare(
      `SELECT COALESCE(SUM(amount_base), 0) AS total, COUNT(*) AS count
       FROM expenses WHERE user_id = ? AND spent_at >= ? AND spent_at < ?`,
    )
    .get(userId, new Date(from).toISOString(), new Date(to).toISOString());
  return { total: row.total, count: row.count };
}

export function sumByCategory(userId, from, to) {
  return db
    .prepare(
      `SELECT category, SUM(amount_base) AS total, COUNT(*) AS count
       FROM expenses WHERE user_id = ? AND spent_at >= ? AND spent_at < ?
       GROUP BY category ORDER BY total DESC`,
    )
    .all(userId, new Date(from).toISOString(), new Date(to).toISOString());
}

/** Суммы по локальным дням пользователя. */
export function sumByDay(userId, from, to, tzOffset) {
  return db
    .prepare(
      `SELECT date(spent_at, ? || ' minutes') AS day, SUM(amount_base) AS total, COUNT(*) AS count
       FROM expenses WHERE user_id = ? AND spent_at >= ? AND spent_at < ?
       GROUP BY day ORDER BY day`,
    )
    .all(String(tzOffset), userId, new Date(from).toISOString(), new Date(to).toISOString());
}

export function getLimits(userId) {
  return db.prepare('SELECT category, amount FROM limits WHERE user_id = ?').all(userId);
}

export function setLimit(userId, category, amount) {
  if (!amount || amount <= 0) {
    db.prepare('DELETE FROM limits WHERE user_id = ? AND category = ?').run(userId, category);
    return null;
  }
  db.prepare(
    `INSERT INTO limits (user_id, category, amount) VALUES (?, ?, ?)
     ON CONFLICT(user_id, category) DO UPDATE SET amount = excluded.amount`,
  ).run(userId, category, amount);
  return { category, amount };
}

export function setPending(userId, action, payload = {}) {
  db.prepare(
    `INSERT INTO pending (user_id, action, payload, created_at)
     VALUES (?, ?, ?, datetime('now'))
     ON CONFLICT(user_id) DO UPDATE SET action = excluded.action, payload = excluded.payload,
                                        created_at = excluded.created_at`,
  ).run(userId, action, JSON.stringify(payload));
}

export function takePending(userId) {
  const row = db.prepare('SELECT * FROM pending WHERE user_id = ?').get(userId);
  if (!row) return null;
  db.prepare('DELETE FROM pending WHERE user_id = ?').run(userId);
  // Диалог живёт 10 минут, чтобы забытое «изменить» не съело следующую трату.
  if (Date.now() - new Date(`${row.created_at}Z`).getTime() > 10 * 60_000) return null;
  return { action: row.action, payload: JSON.parse(row.payload) };
}

export function clearPending(userId) {
  db.prepare('DELETE FROM pending WHERE user_id = ?').run(userId);
}

export function markUpdateProcessed(updateId) {
  const info = db
    .prepare('INSERT OR IGNORE INTO processed_updates (update_id) VALUES (?)')
    .run(updateId);
  if (Math.random() < 0.01) {
    db.prepare("DELETE FROM processed_updates WHERE created_at < datetime('now', '-1 day')").run();
  }
  return info.changes > 0;
}

export function createLoginToken(userId, token, ttlMinutes = 15) {
  db.prepare('DELETE FROM login_tokens WHERE user_id = ?').run(userId);
  const expiresAt = new Date(Date.now() + ttlMinutes * 60_000).toISOString();
  db.prepare('INSERT INTO login_tokens (token, user_id, expires_at) VALUES (?, ?, ?)').run(
    token,
    userId,
    expiresAt,
  );
  return { token, expiresAt };
}

export function consumeLoginToken(token) {
  const row = db.prepare('SELECT * FROM login_tokens WHERE token = ?').get(token);
  if (!row) return null;
  db.prepare('DELETE FROM login_tokens WHERE token = ?').run(token);
  if (row.used_at) return null;
  if (new Date(row.expires_at).getTime() < Date.now()) return null;
  return row.user_id;
}
