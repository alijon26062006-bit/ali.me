import {
  insertExpense, updateExpense, getExpense, listExpenses,
  sumBetween, sumByCategory, sumByDay, getLimits,
} from './db.js';
import { convert, formatMoney, round, decimalsOf } from './money.js';
import { getCategory, CATEGORIES } from './categories.js';
import { daysBetween, dayKey, periodRange } from './time.js';

/**
 * Создаёт трату. `amount` — в валюте `currency`, в базу дополнительно
 * кладётся пересчёт в базовую валюту пользователя, чтобы итоги считались
 * одним SUM без конвертаций на лету.
 */
export function addExpense(user, { amount, currency, category, note, spentAt, source = 'bot' }) {
  const code = (currency || user.currency).toUpperCase();
  const value = round(Number(amount), decimalsOf(code));
  return insertExpense({
    user_id: user.id,
    amount: value,
    currency: code,
    amount_base: convert(value, code, user.currency),
    category: getCategory(category).key,
    note: String(note || '').slice(0, 200),
    spent_at: (spentAt ? new Date(spentAt) : new Date()).toISOString(),
    source,
  });
}

export function editExpense(user, id, patch) {
  const current = getExpense(user.id, id);
  if (!current) return null;
  const fields = {};
  if (patch.category !== undefined) fields.category = getCategory(patch.category).key;
  if (patch.note !== undefined) fields.note = String(patch.note).slice(0, 200);
  if (patch.spentAt !== undefined) fields.spent_at = new Date(patch.spentAt).toISOString();
  if (patch.amount !== undefined || patch.currency !== undefined) {
    const code = (patch.currency || current.currency).toUpperCase();
    const value = round(Number(patch.amount ?? current.amount), decimalsOf(code));
    fields.amount = value;
    fields.currency = code;
    fields.amount_base = convert(value, code, user.currency);
  }
  return updateExpense(user.id, id, fields);
}

/** Пересчитывает amount_base после смены базовой валюты пользователя. */
export function rebaseExpenses(user) {
  const rows = listExpenses(user.id, { limit: 100_000 });
  for (const row of rows) {
    updateExpense(user.id, row.id, {
      amount_base: convert(row.amount, row.currency, user.currency),
    });
  }
}

/**
 * Сводка за период: итог, разбивка по категориям и по дням, лимиты.
 * Всё в базовой валюте пользователя.
 */
export function buildSummary(user, range) {
  const { from, to } = range;
  const tz = user.tz_offset;
  const { total, count } = sumBetween(user.id, from, to);
  const byCategoryRows = sumByCategory(user.id, from, to);
  const byDayRows = new Map(sumByDay(user.id, from, to, tz).map((r) => [r.day, r]));
  const limitsByCategory = new Map(getLimits(user.id).map((l) => [l.category, l.amount]));

  const byCategory = byCategoryRows.map((row) => {
    const category = getCategory(row.category);
    return {
      key: category.key,
      title: category.title,
      emoji: category.emoji,
      color: category.color,
      total: round(row.total, 2),
      count: row.count,
      share: total > 0 ? row.total / total : 0,
      limit: limitsByCategory.get(category.key) || null,
    };
  });

  const days = daysBetween(from, to, tz).map((day) => ({
    day,
    total: round(byDayRows.get(day)?.total || 0, 2),
    count: byDayRows.get(day)?.count || 0,
  }));

  const daysElapsed = days.filter((d) => d.day <= dayKey(new Date(), tz)).length || days.length;

  return {
    from: new Date(from).toISOString(),
    to: new Date(to).toISOString(),
    title: range.title || '',
    currency: user.currency,
    total: round(total, 2),
    count,
    average: daysElapsed > 0 ? round(total / daysElapsed, 2) : 0,
    byCategory,
    days,
  };
}

/** Прогресс по лимитам за текущий месяц. */
export function limitsStatus(user, now = new Date()) {
  const range = periodRange('month', user.tz_offset, now);
  const spent = new Map(sumByCategory(user.id, range.from, range.to).map((r) => [r.category, r.total]));
  return getLimits(user.id)
    .map((limit) => {
      const category = getCategory(limit.category);
      const used = spent.get(limit.category) || 0;
      return {
        key: category.key,
        title: category.title,
        emoji: category.emoji,
        color: category.color,
        limit: limit.amount,
        spent: round(used, 2),
        share: limit.amount > 0 ? used / limit.amount : 0,
      };
    })
    .sort((a, b) => b.share - a.share);
}

/**
 * Проверка лимита после добавления траты: возвращает предупреждение,
 * если категория перешагнула 80% или 100% месячного лимита.
 */
export function limitWarning(user, categoryKey, now = new Date()) {
  const status = limitsStatus(user, now).find((l) => l.key === categoryKey);
  if (!status) return null;
  if (status.share >= 1) {
    return `🚨 Лимит по «${status.title}» превышен: ${formatMoney(status.spent, user.currency)} из ${formatMoney(status.limit, user.currency)}`;
  }
  if (status.share >= 0.8) {
    return `⚠️ По «${status.title}» израсходовано ${Math.round(status.share * 100)}% лимита (${formatMoney(status.spent, user.currency)} из ${formatMoney(status.limit, user.currency)})`;
  }
  return null;
}

export function expenseToJson(row, user) {
  const category = getCategory(row.category);
  return {
    id: row.id,
    amount: row.amount,
    currency: row.currency,
    amountBase: row.amount_base,
    baseCurrency: user.currency,
    category: category.key,
    categoryTitle: category.title,
    categoryEmoji: category.emoji,
    categoryColor: category.color,
    note: row.note,
    spentAt: row.spent_at,
    day: dayKey(row.spent_at, user.tz_offset),
    source: row.source,
  };
}

export function categoriesJson() {
  return CATEGORIES.map((c) => ({ key: c.key, title: c.title, emoji: c.emoji, color: c.color }));
}

/** CSV-экспорт: разделитель — запятая, кодировка UTF-8 с BOM для Excel. */
export function toCsv(rows, user) {
  const header = ['id', 'date', 'time', 'amount', 'currency', `amount_${user.currency.toLowerCase()}`, 'category', 'note', 'source'];
  const lines = [header.join(',')];
  for (const row of rows) {
    const local = new Date(new Date(row.spent_at).getTime() + user.tz_offset * 60_000);
    lines.push(
      [
        row.id,
        local.toISOString().slice(0, 10),
        local.toISOString().slice(11, 16),
        row.amount,
        row.currency,
        row.amount_base,
        getCategory(row.category).title,
        row.note,
        row.source,
      ]
        .map(csvCell)
        .join(','),
    );
  }
  return `﻿${lines.join('\n')}\n`;
}

function csvCell(value) {
  const text = String(value ?? '');
  return /[",\n;]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}
