import test from 'node:test';
import assert from 'node:assert/strict';
import { periodRange, dayKey, monthRange, daysBetween, formatDayHuman } from '../src/time.js';

const TZ = 300; // UTC+5

test('локальный день считается с учётом часового пояса', () => {
  // 2026-09-02 21:30 UTC — это уже 3 сентября в UTC+5
  assert.equal(dayKey('2026-09-02T21:30:00Z', TZ), '2026-09-03');
  assert.equal(dayKey('2026-09-02T21:30:00Z', 0), '2026-09-02');
});

test('«сегодня» — это локальные сутки', () => {
  const now = new Date('2026-09-02T21:30:00Z');
  const range = periodRange('today', TZ, now);
  assert.equal(range.from.toISOString(), '2026-09-02T19:00:00.000Z');
  assert.equal(range.to.toISOString(), '2026-09-03T19:00:00.000Z');
});

test('неделя начинается с понедельника', () => {
  const now = new Date('2026-09-02T10:00:00Z'); // среда
  const range = periodRange('week', TZ, now);
  assert.equal(dayKey(range.from, TZ), '2026-08-31'); // понедельник
  assert.equal(daysBetween(range.from, range.to, TZ).length, 7);
});

test('месяц покрывает все свои дни', () => {
  const range = monthRange('2026-02', TZ);
  const days = daysBetween(range.from, range.to, TZ);
  assert.equal(days.length, 28);
  assert.equal(days[0], '2026-02-01');
  assert.equal(days[27], '2026-02-28');
});

test('человеческие даты', () => {
  const now = new Date('2026-09-02T10:00:00Z');
  assert.equal(formatDayHuman('2026-09-02', TZ, now), 'сегодня');
  assert.equal(formatDayHuman('2026-09-01', TZ, now), 'вчера');
  assert.equal(formatDayHuman('2026-08-20', TZ, now), '20 августа');
  assert.equal(formatDayHuman('2025-12-31', TZ, now), '31 декабря 2025');
});
