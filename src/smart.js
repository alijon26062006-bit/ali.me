import Anthropic from '@anthropic-ai/sdk';
import { config } from './config.js';
import { CURRENCY_CODES } from './money.js';
import { CATEGORIES } from './categories.js';

let client = null;

function getClient() {
  if (!config.anthropicApiKey) return null;
  if (!client) client = new Anthropic({ apiKey: config.anthropicApiKey });
  return client;
}

export const smartParseAvailable = () => Boolean(config.anthropicApiKey);

const EXPENSES_TOOL = {
  name: 'save_expenses',
  description: 'Записать траты, распознанные в сообщении пользователя.',
  strict: true,
  input_schema: {
    type: 'object',
    properties: {
      expenses: {
        type: 'array',
        description: 'По одной записи на каждую трату. Пустой массив, если трат в тексте нет.',
        items: {
          type: 'object',
          properties: {
            line: { type: 'integer', description: 'Номер строки из списка, к которой относится трата', minimum: 1 },
            amount: { type: 'number', description: 'Сумма траты, положительное число' },
            currency: {
              type: 'string',
              enum: [...CURRENCY_CODES, 'DEFAULT'],
              description: 'Код валюты, если он назван словом или символом, иначе DEFAULT',
            },
            category: { type: 'string', enum: CATEGORIES.map((c) => c.key) },
            note: { type: 'string', description: 'Короткое описание траты, 1–4 слова, без суммы' },
            day_shift: {
              type: 'integer',
              description: 'Сдвиг дня: 0 — сегодня, -1 — вчера, -2 — позавчера',
              minimum: -7,
              maximum: 0,
            },
          },
          required: ['line', 'amount', 'currency', 'category', 'note', 'day_shift'],
          additionalProperties: false,
        },
      },
    },
    required: ['expenses'],
    additionalProperties: false,
  },
};

const SYSTEM = [
  'Ты разбираешь сообщения пользователя трекера личных расходов на отдельные траты.',
  'Каждая трата — сумма, короткое описание и категория.',
  'Суммы бывают словами («штука», «полтинник», «пара тысяч»), с сокращениями («12к», «1.5 млн») и с количеством («два кофе по 15000» = одна трата на 30000).',
  'Если валюта названа в одной части сообщения, она относится ко всему сообщению, пока не указана другая.',
  'Не выдумывай траты: если суммы нет, верни пустой массив.',
  'Описание пиши по-русски, коротко и без суммы.',
].join(' ');

/**
 * Разбирает строки, с которыми не справились правила.
 * Возвращает массив трат, каждая знает номер своей строки (`lineIndex`).
 *
 * Работает только если задан ANTHROPIC_API_KEY, иначе сразу null.
 */
export async function understandExpenses(lines, { currency, timeoutMs = 20_000 } = {}) {
  const anthropic = getClient();
  if (!anthropic || lines.length === 0) return null;

  const numbered = lines.map((line, index) => `${index + 1}. ${line}`).join('\n');
  const response = await anthropic.messages.create(
    {
      model: config.ocrModel,
      max_tokens: 2000,
      system: SYSTEM,
      tools: [EXPENSES_TOOL],
      tool_choice: { type: 'tool', name: 'save_expenses' },
      messages: [
        {
          role: 'user',
          content:
            `Валюта пользователя по умолчанию: ${currency}.\n` +
            `Разбери эти строки на траты (по порядку, строка может дать одну трату или ни одной):\n${numbered}`,
        },
      ],
    },
    { timeout: timeoutMs },
  );

  const block = response.content.find((item) => item.type === 'tool_use');
  const expenses = block?.input?.expenses;
  if (!Array.isArray(expenses)) return null;

  return expenses
    .filter((item) => Number(item.amount) > 0)
    .map((item) => ({
      lineIndex: Math.max(0, Math.min(lines.length - 1, Number(item.line) - 1)),
      amount: Number(item.amount),
      currency: item.currency === 'DEFAULT' ? null : item.currency,
      currencyExplicit: item.currency !== 'DEFAULT',
      category: item.category,
      categorySource: 'ai',
      note: String(item.note || '').slice(0, 120),
      dayShift: Number(item.day_shift) || 0,
    }));
}
