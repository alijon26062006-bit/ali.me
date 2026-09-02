/**
 * Работа с датами. В базе всё хранится в UTC (ISO-строка),
 * а группировка по дням делается в часовом поясе пользователя
 * (смещение в минутах, например 300 для UTC+5).
 */
const MINUTE = 60_000;
const DAY = 86_400_000;

export function toLocal(date, tzOffset) {
  return new Date(new Date(date).getTime() + tzOffset * MINUTE);
}

export function fromLocal(date, tzOffset) {
  return new Date(new Date(date).getTime() - tzOffset * MINUTE);
}

/** Локальная дата в формате YYYY-MM-DD. */
export function dayKey(date, tzOffset) {
  return toLocal(date, tzOffset).toISOString().slice(0, 10);
}

export function localNow(tzOffset) {
  return toLocal(new Date(), tzOffset);
}

/** Начало локального дня (UTC-момент). */
export function startOfLocalDay(date, tzOffset) {
  const local = toLocal(date, tzOffset);
  local.setUTCHours(0, 0, 0, 0);
  return fromLocal(local, tzOffset);
}

export function addDays(date, days) {
  return new Date(new Date(date).getTime() + days * DAY);
}

/**
 * Диапазон [from, to) в UTC для периода.
 * @param {'today'|'yesterday'|'week'|'month'|'prev_month'|'all'} period
 */
export function periodRange(period, tzOffset, now = new Date()) {
  const startToday = startOfLocalDay(now, tzOffset);
  switch (period) {
    case 'today':
      return { from: startToday, to: addDays(startToday, 1), title: 'сегодня' };
    case 'yesterday':
      return { from: addDays(startToday, -1), to: startToday, title: 'вчера' };
    case 'week': {
      const local = toLocal(startToday, tzOffset);
      const weekday = (local.getUTCDay() + 6) % 7; // 0 = понедельник
      const from = addDays(startToday, -weekday);
      return { from, to: addDays(from, 7), title: 'эта неделя' };
    }
    case 'prev_month': {
      const local = toLocal(startToday, tzOffset);
      const from = fromLocal(new Date(Date.UTC(local.getUTCFullYear(), local.getUTCMonth() - 1, 1)), tzOffset);
      const to = fromLocal(new Date(Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), 1)), tzOffset);
      return { from, to, title: 'прошлый месяц' };
    }
    case 'all':
      return { from: new Date(0), to: addDays(startToday, 1), title: 'всё время' };
    case 'month':
    default: {
      const local = toLocal(startToday, tzOffset);
      const from = fromLocal(new Date(Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), 1)), tzOffset);
      const to = fromLocal(new Date(Date.UTC(local.getUTCFullYear(), local.getUTCMonth() + 1, 1)), tzOffset);
      return { from, to, title: 'этот месяц' };
    }
  }
}

/** Диапазон конкретного месяца: «2026-09». */
export function monthRange(monthKey, tzOffset) {
  const m = /^(\d{4})-(\d{2})$/.exec(String(monthKey || ''));
  if (!m) return null;
  const year = Number(m[1]);
  const month = Number(m[2]) - 1;
  if (month < 0 || month > 11) return null;
  return {
    from: fromLocal(new Date(Date.UTC(year, month, 1)), tzOffset),
    to: fromLocal(new Date(Date.UTC(year, month + 1, 1)), tzOffset),
    title: monthTitle(monthKey),
  };
}

const MONTH_NAMES = [
  'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
];

export function monthTitle(monthKey) {
  const m = /^(\d{4})-(\d{2})$/.exec(String(monthKey || ''));
  if (!m) return monthKey;
  return `${MONTH_NAMES[Number(m[2]) - 1]} ${m[1]}`;
}

export function monthKeyOf(date, tzOffset) {
  return dayKey(date, tzOffset).slice(0, 7);
}

/** Список дней (YYYY-MM-DD) внутри диапазона. */
export function daysBetween(from, to, tzOffset) {
  const days = [];
  let cursor = startOfLocalDay(from, tzOffset);
  const end = new Date(to).getTime();
  while (cursor.getTime() < end) {
    days.push(dayKey(cursor, tzOffset));
    cursor = addDays(cursor, 1);
  }
  return days;
}

const MONTH_GENITIVE = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

/** «2 сентября» — всегда дата, без «сегодня»/«вчера». */
export function formatDate(dayKeyValue, now = new Date()) {
  const [year, month, day] = dayKeyValue.split('-');
  const suffix = year === new Date(now).getUTCFullYear().toString() ? '' : ` ${year}`;
  return `${Number(day)} ${MONTH_GENITIVE[Number(month) - 1]}${suffix}`;
}

export function formatDayHuman(dayKeyValue, tzOffset, now = new Date()) {
  if (dayKeyValue === dayKey(now, tzOffset)) return 'сегодня';
  if (dayKeyValue === dayKey(addDays(now, -1), tzOffset)) return 'вчера';
  return formatDate(dayKeyValue, now);
}
