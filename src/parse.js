import { matchCurrency } from './money.js';
import { findExplicitCategory, guessCategory, DEFAULT_CATEGORY, getCategory } from './categories.js';

const MULTIPLIERS = [
  { match: ['кк', 'kk', 'млн', 'mln', 'm', 'м'], factor: 1_000_000 },
  { match: ['к', 'k', 'тыс', 'тысяч', 'тысячи', 'тыща'], factor: 1_000 },
];

const DATE_WORDS = [
  { words: ['сегодня', 'today'], shift: 0 },
  { words: ['вчера', 'yesterday'], shift: -1 },
  { words: ['позавчера'], shift: -2 },
];

const CURRENCY_SYMBOLS = "$€₽₸₴₺£";

/**
 * Разбирает сообщение вида «кофе 350», «такси 900 работа», «5$ обед вчера».
 *
 * @returns {{amount:number, currency:string|null, note:string, category:string,
 *            categorySource:'explicit'|'guess'|'default', dayShift:number}|null}
 */
export function parseExpense(input, options = {}) {
  const raw = String(input || '').replace(/^\/(add|трата|expense)\b/i, ' ');
  if (!raw.trim()) return null;

  // «1 200» и «1 200,50» → «1200» / «1200,50»
  const merged = raw.replace(/(\d)[\s ](?=\d{3}(?!\d))/g, '$1');
  const tokens = merged.split(/\s+/).filter(Boolean);

  let dayShift = 0;
  const kept = [];
  for (const token of tokens) {
    const clean = token.toLowerCase().replace(/ё/g, 'е').replace(/[.,!?]+$/, '');
    const dateWord = DATE_WORDS.find((d) => d.words.includes(clean));
    if (dateWord) {
      dayShift = dateWord.shift;
      continue;
    }
    kept.push(token);
  }

  const candidates = [];
  kept.forEach((token, index) => {
    const parsed = parseAmountToken(token);
    if (!parsed) return;
    let currency = parsed.currency;
    let currencyIndex = -1;
    // Валюта может стоять отдельным словом: «350 usd» или «usd 350».
    if (!currency) {
      const next = matchCurrency(kept[index + 1]);
      const prev = index > 0 ? matchCurrency(kept[index - 1]) : null;
      if (next) {
        currency = next;
        currencyIndex = index + 1;
      } else if (prev) {
        currency = prev;
        currencyIndex = index - 1;
      }
    }
    candidates.push({ value: parsed.value, index, currency, currencyIndex });
  });

  if (candidates.length === 0) return null;

  // Приоритет — у числа с явной валютой, иначе берём самое крупное.
  const withCurrency = candidates.filter((c) => c.currency);
  const pool = withCurrency.length > 0 ? withCurrency : candidates;
  const chosen = pool.reduce((best, c) => (c.value >= best.value ? c : best), pool[0]);
  if (!(chosen.value > 0)) return null;

  const noteTokens = kept.filter((_, i) => i !== chosen.index && i !== chosen.currencyIndex);
  let note = noteTokens.join(' ').replace(/\s+/g, ' ').trim();

  let category = DEFAULT_CATEGORY;
  let categorySource = 'default';

  const explicit = findExplicitCategory(note);
  if (explicit) {
    category = explicit.key;
    categorySource = 'explicit';
    const rest = stripWord(note, explicit.matched);
    if (rest) note = rest;
  } else {
    const guess = guessCategory(note);
    if (guess) {
      category = guess.key;
      categorySource = 'guess';
    }
  }

  if (!note) note = getCategory(category).title;

  return {
    amount: chosen.value,
    currency: chosen.currency || options.defaultCurrency || null,
    currencyExplicit: Boolean(chosen.currency),
    note: note.slice(0, 120),
    category,
    categorySource,
    dayShift,
  };
}

/** «350», «350сум», «$5», «12к», «1200,50» → число. */
export function parseAmountToken(token) {
  let text = String(token).trim();
  if (!text) return null;

  let currency = null;

  // Символ валюты в начале: «$5»
  const leading = text.match(new RegExp(`^([${CURRENCY_SYMBOLS}])\\s*(.+)$`, 'u'));
  if (leading) {
    currency = matchCurrency(leading[1]);
    text = leading[2];
  }

  const m = text.match(/^(\d+(?:[.,]\d+)?)(.*)$/u);
  if (!m) return null;

  let numeric = m[1];
  let rest = (m[2] || '').trim().replace(/[.,!?]+$/, '');

  // «1,200» / «1.200» — это тысячи, а «0,5» и «350,50» — дробь.
  const groupSeparated = /^([1-9]\d{0,2})[.,](\d{3})$/.exec(numeric);
  let value = groupSeparated
    ? Number(`${groupSeparated[1]}${groupSeparated[2]}`)
    : Number(numeric.replace(',', '.'));
  if (!Number.isFinite(value)) return null;

  if (rest) {
    const lower = rest.toLowerCase().replace(/ё/g, 'е');
    const multiplier = MULTIPLIERS.find((entry) =>
      entry.match.some((suffix) => lower === suffix || lower.startsWith(suffix)),
    );
    if (multiplier) {
      const suffix = multiplier.match.find((s) => lower === s || lower.startsWith(s));
      value *= multiplier.factor;
      rest = rest.slice(suffix.length);
    }
  }

  if (rest) {
    const found = matchCurrency(rest);
    if (found) currency = found;
    else if (!currency) return null; // «5кг», «2шт» — это не сумма
  }

  return { value, currency };
}

function stripWord(text, word) {
  return text
    .split(/\s+/)
    .filter((t) => t.toLowerCase().replace(/ё/g, 'е').replace(/[^\p{L}\p{N}]/gu, '') !== word)
    .join(' ')
    .trim();
}
