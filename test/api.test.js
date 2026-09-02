import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

// База и секреты — только для теста, до импорта модулей приложения.
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'kopeyka-test-'));
process.env.DB_PATH = path.join(tmpDir, 'test.db');
process.env.SESSION_SECRET = 'test-secret-value';
process.env.DEFAULT_CURRENCY = 'UZS';
process.env.DEFAULT_TZ_OFFSET = '300';

const { createServer } = await import('../src/server.js');
const { upsertUser } = await import('../src/db.js');
const { createSession, COOKIE_NAME } = await import('../src/auth.js');

const server = createServer().listen(0);
const base = `http://127.0.0.1:${server.address().port}`;

test.after(() => {
  server.close();
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

const alice = upsertUser({ id: 1001, first_name: 'Алиса', username: 'alice' });
const bob = upsertUser({ id: 1002, first_name: 'Боб', username: 'bob' });

function as(user, path, options = {}) {
  return fetch(`${base}${path}`, {
    ...options,
    headers: {
      cookie: `${COOKIE_NAME}=${createSession(user.id)}`,
      ...(options.body ? { 'content-type': 'application/json' } : {}),
      ...options.headers,
    },
  });
}

test('без сессии API отвечает 401', async () => {
  const response = await fetch(`${base}/api/me`);
  assert.equal(response.status, 401);
});

test('трата добавляется одной строкой и получает категорию', async () => {
  const response = await as(alice, '/api/expenses', {
    method: 'POST',
    body: JSON.stringify({ text: 'кофе 350' }),
  });
  assert.equal(response.status, 201);
  const { expense } = await response.json();
  assert.equal(expense.amount, 350);
  assert.equal(expense.category, 'cafe');
  assert.equal(expense.note, 'кофе');
});

test('сводка считает итог, категории и дни', async () => {
  await as(alice, '/api/expenses', {
    method: 'POST',
    body: JSON.stringify({ text: 'такси 900 транспорт' }),
  });
  const summary = await (await as(alice, '/api/summary?period=month')).json();
  assert.equal(summary.total, 1250);
  assert.equal(summary.count, 2);
  assert.ok(summary.byCategory.some((c) => c.key === 'transport' && c.total === 900));
  assert.ok(summary.days.length >= 28);
  assert.equal(
    summary.days.reduce((sum, day) => sum + day.total, 0),
    1250,
  );
});

test('чужие траты не видны и не удаляются', async () => {
  const created = await (
    await as(alice, '/api/expenses', { method: 'POST', body: JSON.stringify({ text: 'обед 40000' }) })
  ).json();

  const bobList = await (await as(bob, '/api/expenses?period=month')).json();
  assert.equal(bobList.items.length, 0);

  const bobSummary = await (await as(bob, '/api/summary?period=month')).json();
  assert.equal(bobSummary.total, 0);

  const deleteResponse = await as(bob, `/api/expenses/${created.expense.id}`, { method: 'DELETE' });
  assert.equal(deleteResponse.status, 404);

  const patchResponse = await as(bob, `/api/expenses/${created.expense.id}`, {
    method: 'PATCH',
    body: JSON.stringify({ amount: 1 }),
  });
  assert.equal(patchResponse.status, 404);

  const stillThere = await (await as(alice, `/api/expenses?period=month`)).json();
  assert.ok(stillThere.items.some((item) => item.id === created.expense.id));
});

test('трату можно исправить и удалить', async () => {
  const created = await (
    await as(alice, '/api/expenses', { method: 'POST', body: JSON.stringify({ text: 'кино 60000' }) })
  ).json();
  const id = created.expense.id;

  const patched = await (
    await as(alice, `/api/expenses/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ amount: 75000, category: 'fun', note: 'кино с попкорном' }),
    })
  ).json();
  assert.equal(patched.expense.amount, 75000);
  assert.equal(patched.expense.note, 'кино с попкорном');

  const deleted = await as(alice, `/api/expenses/${id}`, { method: 'DELETE' });
  assert.equal(deleted.status, 200);

  const list = await (await as(alice, '/api/expenses?period=month')).json();
  assert.ok(!list.items.some((item) => item.id === id));
});

test('другая валюта пересчитывается в базовую', async () => {
  const created = await (
    await as(alice, '/api/expenses', { method: 'POST', body: JSON.stringify({ text: 'подписка 10$' }) })
  ).json();
  assert.equal(created.expense.currency, 'USD');
  assert.equal(created.expense.amount, 10);
  assert.ok(created.expense.amountBase > 10, 'в сумах должно быть больше, чем в долларах');
});

test('лимиты возвращают прогресс', async () => {
  await as(alice, '/api/limits', {
    method: 'PUT',
    body: JSON.stringify({ category: 'cafe', amount: 100000 }),
  });
  const { limits } = await (await as(alice, '/api/limits')).json();
  const cafe = limits.find((l) => l.key === 'cafe');
  assert.equal(cafe.limit, 100000);
  // «кофе 350» + «обед 40000» — оба попали в кафе
  assert.equal(cafe.spent, 40350);
  assert.ok(cafe.share > 0.4 && cafe.share < 0.41);
});

test('экспорт отдаёт CSV только своих трат', async () => {
  const response = await as(alice, '/api/export.csv?period=all');
  assert.equal(response.status, 200);
  assert.match(response.headers.get('content-type'), /text\/csv/);
  const body = await response.text();
  assert.match(body, /кофе/);

  const bobCsv = await (await as(bob, '/api/export.csv?period=all')).text();
  assert.doesNotMatch(bobCsv, /кофе/);
});

test('одноразовая ссылка входа работает один раз', async () => {
  const { issueLoginLink } = await import('../src/auth.js');
  const { url } = issueLoginLink(alice.id);
  const token = new URL(url).searchParams.get('token');

  const first = await fetch(`${base}/auth?token=${token}`, { redirect: 'manual' });
  assert.equal(first.status, 302);
  assert.match(first.headers.get('set-cookie') || '', new RegExp(COOKIE_NAME));

  const second = await fetch(`${base}/auth?token=${token}`, { redirect: 'manual' });
  assert.equal(second.status, 401);
});

test('поддельная сессия не пускает', async () => {
  const response = await fetch(`${base}/api/me`, {
    headers: { cookie: `${COOKIE_NAME}=eyJ1aWQiOjEwMDF9.deadbeef` },
  });
  assert.equal(response.status, 401);
});
