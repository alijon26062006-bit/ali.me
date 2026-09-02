/**
 * Валюты и форматирование сумм.
 *
 * Курсы — ориентировочные и нужны только для того, чтобы показать один
 * общий итог, когда траты записаны в разных валютах. Их можно переопределить
 * переменной окружения RATES, например: RATES='{"USD":1,"UZS":12600,"RUB":92}'
 * (значение = сколько единиц валюты в одном долларе).
 */
const DEFAULT_RATES_PER_USD = {
  USD: 1,
  EUR: 0.92,
  UZS: 12600,
  RUB: 92,
  KZT: 480,
  KGS: 87,
  TJS: 10.9,
  UAH: 41,
  TRY: 34,
  GBP: 0.79,
};

export const CURRENCIES = {
  UZS: { code: 'UZS', symbol: "so'm", decimals: 0, aliases: ['сум', 'сўм', 'сум.', 'som', "so'm", 'uzs', 'сумов'] },
  USD: { code: 'USD', symbol: '$', decimals: 2, aliases: ['$', 'usd', 'доллар', 'долларов', 'бакс', 'dollar'] },
  EUR: { code: 'EUR', symbol: '€', decimals: 2, aliases: ['€', 'eur', 'евро', 'euro'] },
  RUB: { code: 'RUB', symbol: '₽', decimals: 0, aliases: ['₽', 'rub', 'руб', 'рубль', 'рублей', 'ruble'] },
  KZT: { code: 'KZT', symbol: '₸', decimals: 0, aliases: ['₸', 'kzt', 'тенге'] },
  KGS: { code: 'KGS', symbol: 'сом', decimals: 0, aliases: ['kgs', 'сом'] },
  TJS: { code: 'TJS', symbol: 'смн', decimals: 2, aliases: ['tjs', 'сомони'] },
  UAH: { code: 'UAH', symbol: '₴', decimals: 0, aliases: ['₴', 'uah', 'гривна', 'грн'] },
  TRY: { code: 'TRY', symbol: '₺', decimals: 0, aliases: ['₺', 'try', 'лира'] },
  GBP: { code: 'GBP', symbol: '£', decimals: 2, aliases: ['£', 'gbp', 'фунт'] },
};

export const CURRENCY_CODES = Object.keys(CURRENCIES);

let ratesPerUsd = { ...DEFAULT_RATES_PER_USD };
try {
  if (process.env.RATES) {
    ratesPerUsd = { ...ratesPerUsd, ...JSON.parse(process.env.RATES) };
  }
} catch {
  console.warn('RATES: не удалось разобрать JSON, используются курсы по умолчанию');
}

export function isCurrency(code) {
  return Boolean(code && CURRENCIES[String(code).toUpperCase()]);
}

/** Ищет код валюты по слову: «$», «usd», «сум». */
export function matchCurrency(word) {
  const w = String(word || '').toLowerCase().replace(/\.$/, '');
  if (!w) return null;
  if (CURRENCIES[w.toUpperCase()]) return w.toUpperCase();
  for (const [code, meta] of Object.entries(CURRENCIES)) {
    if (meta.aliases.includes(w)) return code;
  }
  return null;
}

export function convert(amount, from, to) {
  const f = String(from).toUpperCase();
  const t = String(to).toUpperCase();
  if (f === t) return round(amount, decimalsOf(t));
  const rf = ratesPerUsd[f];
  const rt = ratesPerUsd[t];
  if (!rf || !rt) return round(amount, decimalsOf(t));
  return round((amount / rf) * rt, decimalsOf(t));
}

export function decimalsOf(code) {
  return CURRENCIES[String(code).toUpperCase()]?.decimals ?? 2;
}

export function round(value, decimals = 2) {
  const f = 10 ** decimals;
  return Math.round((value + Number.EPSILON) * f) / f;
}

export function formatMoney(amount, code = 'UZS') {
  const currency = CURRENCIES[String(code).toUpperCase()];
  const decimals = currency?.decimals ?? 2;
  const value = Number(amount) || 0;
  const body = value.toLocaleString('ru-RU', {
    minimumFractionDigits: Math.abs(value % 1) > 0 ? decimals : 0,
    maximumFractionDigits: decimals,
  });
  const symbol = currency?.symbol || code;
  return symbol === '$' || symbol === '€' || symbol === '£' ? `${symbol}${body}` : `${body} ${symbol}`;
}
