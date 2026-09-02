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

export const ocrAvailable = () => Boolean(config.anthropicApiKey);

const RECEIPT_TOOL = {
  name: 'save_receipt',
  description: 'Записать данные распознанного чека.',
  strict: true,
  input_schema: {
    type: 'object',
    properties: {
      readable: {
        type: 'boolean',
        description: 'true, если на фото действительно чек и итоговая сумма читается',
      },
      total: {
        type: 'number',
        description: 'Итоговая сумма к оплате. 0, если прочитать не удалось.',
      },
      currency: {
        type: 'string',
        enum: [...CURRENCY_CODES, 'UNKNOWN'],
        description: 'Код валюты чека или UNKNOWN',
      },
      merchant: {
        type: 'string',
        description: 'Название магазина или заведения, пустая строка если не видно',
      },
      category: {
        type: 'string',
        enum: CATEGORIES.map((c) => c.key),
        description: 'Наиболее подходящая категория траты',
      },
    },
    required: ['readable', 'total', 'currency', 'merchant', 'category'],
    additionalProperties: false,
  },
};

const SYSTEM = [
  'Ты помогаешь трекеру расходов разобрать фотографию чека.',
  'Верни только итоговую сумму (ИТОГО / TOTAL / Jami / К оплате), а не сумму отдельной позиции.',
  'Если на фото не чек или сумма не читается — верни readable=false.',
  'Никогда не выдумывай сумму.',
].join(' ');

/**
 * Распознаёт чек по фото. Возвращает null, если OCR выключен
 * (не задан ANTHROPIC_API_KEY) или чек не прочитался.
 */
export async function readReceipt(buffer, mediaType = 'image/jpeg') {
  const anthropic = getClient();
  if (!anthropic) return null;

  const response = await anthropic.messages.create({
    model: config.ocrModel,
    max_tokens: 2000,
    system: SYSTEM,
    tools: [RECEIPT_TOOL],
    tool_choice: { type: 'tool', name: 'save_receipt' },
    messages: [
      {
        role: 'user',
        content: [
          {
            type: 'image',
            source: { type: 'base64', media_type: mediaType, data: buffer.toString('base64') },
          },
          { type: 'text', text: 'Разбери этот чек.' },
        ],
      },
    ],
  });

  const block = response.content.find((item) => item.type === 'tool_use');
  if (!block) return null;
  const data = block.input;
  if (!data?.readable || !(Number(data.total) > 0)) return null;

  return {
    amount: Number(data.total),
    currency: data.currency === 'UNKNOWN' ? null : data.currency,
    merchant: String(data.merchant || '').slice(0, 80),
    category: data.category,
  };
}
