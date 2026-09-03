import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'kopeyka-bot-'));
process.env.DB_PATH = path.join(tmpDir, 'bot.db');
process.env.SESSION_SECRET = 'test-secret-value';
process.env.BOT_TOKEN = '123:test-token';
process.env.DEFAULT_CURRENCY = 'UZS';
process.env.DEFAULT_TZ_OFFSET = '300';

const { handleUpdate } = await import('../src/bot.js');
const { db, recentExpenses } = await import('../src/db.js');

// Подменяем сеть: запоминаем, что бот отправил бы в Telegram.
const sent = [];
globalThis.fetch = async (url, options) => {
  const method = String(url).split('/').pop();
  sent.push({ method, body: JSON.parse(options.body || '{}') });
  return new Response(JSON.stringify({ ok: true, result: { message_id: sent.length, chat: { id: 42 } } }), {
    headers: { 'content-type': 'application/json' },
  });
};

test.after(() => fs.rmSync(tmpDir, { recursive: true, force: true }));

const USER = { id: 42, first_name: 'Тест', username: 'tester' };
let updateId = 100;

const message = (text) => ({
  update_id: (updateId += 1),
  message: { message_id: updateId, from: USER, chat: { id: 42, type: 'private' }, text },
});

const callback = (data) => ({
  update_id: (updateId += 1),
  callback_query: {
    id: String(updateId),
    from: USER,
    data,
    message: { message_id: 1, chat: { id: 42, type: 'private' } },
  },
});

const lastText = () => [...sent].reverse().find((call) => call.method === 'sendMessage')?.body.text || '';

test('текстовое сообщение сохраняет трату и подтверждает её', async () => {
  await handleUpdate(message('кофе 350'));
  const [expense] = recentExpenses(USER.id, 1);
  assert.equal(expense.amount, 350);
  assert.equal(expense.category, 'cafe');
  const text = lastText();
  assert.match(text, /350/);
  assert.match(text, /Кафе/);
  assert.match(text, /Сегодня/);
});

test('один и тот же апдейт не создаёт две траты', async () => {
  const update = message('такси 900 работа');
  await handleUpdate(update);
  await handleUpdate(update);
  const rows = recentExpenses(USER.id, 5).filter((row) => row.note === 'такси работа');
  assert.equal(rows.length, 1);
});

test('/today показывает итог за сегодня', async () => {
  await handleUpdate(message('/today'));
  const text = lastText();
  assert.match(text, /Сегодня/);
  assert.match(text, /1.250/); // 350 + 900 (пробел неразрывный)
});

test('кнопка меняет категорию', async () => {
  const [expense] = recentExpenses(USER.id, 1);
  await handleUpdate(callback(`setcat:${expense.id}:groceries`));
  const [updated] = recentExpenses(USER.id, 1);
  assert.equal(updated.category, 'groceries');
});

test('кнопка удаляет трату', async () => {
  const [expense] = recentExpenses(USER.id, 1);
  await handleUpdate(callback(`del:${expense.id}`));
  assert.ok(!recentExpenses(USER.id, 10).some((row) => row.id === expense.id));
});

test('/undo удаляет последнюю трату', async () => {
  await handleUpdate(message('пицца 60000'));
  const before = recentExpenses(USER.id, 10).length;
  await handleUpdate(message('/undo'));
  assert.equal(recentExpenses(USER.id, 10).length, before - 1);
});

test('нераспознанное сообщение подсказывает формат', async () => {
  const before = recentExpenses(USER.id, 10).length;
  await handleUpdate(message('привет'));
  assert.equal(recentExpenses(USER.id, 10).length, before);
  assert.match(lastText(), /Не нашёл сумму/);
});

test('лимит предупреждает при превышении', async () => {
  await handleUpdate(message('/limit кафе 1000'));
  await handleUpdate(message('кофе 1200'));
  assert.match(lastText(), /Лимит по «Кафе и рестораны» превышен/);
});

test('/app присылает одноразовую ссылку входа', async () => {
  await handleUpdate(message('/app'));
  const call = [...sent].reverse().find((c) => c.method === 'sendMessage');
  const url = call.body.reply_markup.inline_keyboard[0][0].url;
  assert.match(url, /\/auth\?token=/);
  const token = new URL(url).searchParams.get('token');
  const row = db.prepare('SELECT user_id FROM login_tokens WHERE token = ?').get(token);
  assert.equal(row.user_id, USER.id);
});

test('редактирование через кнопку заменяет трату', async () => {
  await handleUpdate(message('такси 5000'));
  const [expense] = recentExpenses(USER.id, 1);
  await handleUpdate(callback(`edit:${expense.id}`));
  await handleUpdate(message('такси 7000'));
  const [updated] = recentExpenses(USER.id, 1);
  assert.equal(updated.id, expense.id);
  assert.equal(updated.amount, 7000);
});

test('несколько трат одним сообщением — по одной на строку', async () => {
  const before = recentExpenses(USER.id, 50).length;
  await handleUpdate(
    message('такси 700рублей до центра\n459 рублей завтрак с лимонадом\n1054 кофе и десерт\n600 такси до дома\n1700 продукты'),
  );
  const rows = recentExpenses(USER.id, 50).slice(0, 5);
  assert.equal(recentExpenses(USER.id, 50).length, before + 5);
  // валюта названа в первых строках и относится ко всему сообщению
  assert.ok(rows.every((row) => row.currency === 'RUB'), 'все траты должны быть в рублях');
  assert.deepEqual(
    rows.map((row) => row.amount).sort((a, b) => a - b),
    [459, 600, 700, 1054, 1700],
  );
  const byNote = new Map(rows.map((row) => [row.note, row.category]));
  assert.equal(byNote.get('такси до центра'), 'transport');
  assert.equal(byNote.get('продукты'), 'groceries');
  assert.match(lastText(), /Записал <b>5 трат<\/b>/);
});

test('кнопка удаляет всю пачку трат из сообщения', async () => {
  const before = recentExpenses(USER.id, 50).length;
  await handleUpdate(message('хлеб 12\nмолоко 30'));
  const [second, first] = recentExpenses(USER.id, 2);
  await handleUpdate(callback(`delb:${first.id}:${second.id}`));
  assert.equal(recentExpenses(USER.id, 50).length, before);
});

test('первый запуск спрашивает страну, потом валюту', async () => {
  await handleUpdate(message('/start'));
  const start = [...sent].reverse().find((call) => call.method === 'sendMessage');
  const countries = start.body.reply_markup.inline_keyboard[0].map((button) => button.callback_data);
  assert.deepEqual(countries, ['ctry:tj', 'ctry:ru', 'ctry:kz']);

  await handleUpdate(callback('ctry:ru'));
  const afterCountry = [...sent].reverse().find((call) => call.method === 'editMessageText');
  assert.match(afterCountry.body.text, /Россия/);
  assert.match(afterCountry.body.text, /UTC\+3/);
  assert.equal(db.prepare('SELECT tz_offset FROM users WHERE id = ?').get(USER.id).tz_offset, 180);

  await handleUpdate(callback('cur:RUB'));
  assert.equal(db.prepare('SELECT currency FROM users WHERE id = ?').get(USER.id).currency, 'RUB');
  assert.match(lastText(), /Итоги/);
});

test('повторный /start не спрашивает настройку заново', async () => {
  await handleUpdate(message('/start'));
  const again = [...sent].reverse().find((call) => call.method === 'sendMessage');
  assert.equal(again.body.reply_markup?.inline_keyboard, undefined, 'кнопок стран быть не должно');
  assert.match(again.body.text, /на связи/);
  assert.match(again.body.text, /сменить в \/settings/);
});

test('кнопка в настройках возвращает мастер настройки', async () => {
  await handleUpdate(callback('setup:0'));
  const setup = [...sent].reverse().find((call) => call.method === 'sendMessage');
  assert.deepEqual(
    setup.body.reply_markup.inline_keyboard[0].map((button) => button.callback_data),
    ['ctry:tj', 'ctry:ru', 'ctry:kz'],
  );
});

test('чужие траты недоступны через колбэк другого пользователя', async () => {
  const [expense] = recentExpenses(USER.id, 1);
  const stranger = {
    update_id: (updateId += 1),
    callback_query: {
      id: 'x',
      from: { id: 999, first_name: 'Чужой' },
      data: `del:${expense.id}`,
      message: { message_id: 1, chat: { id: 999, type: 'private' } },
    },
  };
  await handleUpdate(stranger);
  assert.ok(recentExpenses(USER.id, 5).some((row) => row.id === expense.id));
});
