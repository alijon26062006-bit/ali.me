import 'dotenv/config';
import path from 'node:path';

function bool(value, fallback = false) {
  if (value === undefined || value === '') return fallback;
  return ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase());
}

function int(value, fallback) {
  const n = Number.parseInt(value ?? '', 10);
  return Number.isFinite(n) ? n : fallback;
}

export const config = {
  botToken: process.env.BOT_TOKEN || '',
  botUsername: (process.env.BOT_USERNAME || '').replace(/^@/, ''),

  port: int(process.env.PORT, 3000),
  // Публичный адрес панели, например https://kopeyka.example.com
  // Используется для ссылки входа, которую присылает бот.
  publicUrl: (process.env.PUBLIC_URL || '').replace(/\/+$/, ''),

  // Секрет для подписи cookie-сессий. Обязателен в проде.
  sessionSecret: process.env.SESSION_SECRET || '',
  sessionDays: int(process.env.SESSION_DAYS, 30),

  dbPath: process.env.DB_PATH || path.join(process.cwd(), 'data', 'kopeyka.db'),

  defaultCurrency: (process.env.DEFAULT_CURRENCY || 'UZS').toUpperCase(),
  // Часовой пояс по умолчанию в минутах от UTC (300 = UTC+5, Ташкент).
  defaultTzOffset: int(process.env.DEFAULT_TZ_OFFSET, 300),

  // Режим получения апдейтов: polling (по умолчанию) или webhook.
  useWebhook: bool(process.env.USE_WEBHOOK, false),
  webhookSecret: process.env.WEBHOOK_SECRET || '',

  // Необязательно: распознавание чеков по фото через Anthropic API.
  anthropicApiKey: process.env.ANTHROPIC_API_KEY || '',
  ocrModel: process.env.OCR_MODEL || 'claude-opus-5',

  isProd: process.env.NODE_ENV === 'production',
};

export function assertConfig() {
  const problems = [];
  if (!config.botToken) problems.push('BOT_TOKEN не задан — бот не запустится');
  if (!config.sessionSecret) {
    if (config.isProd) problems.push('SESSION_SECRET не задан (обязателен в production)');
  }
  if (config.useWebhook && !config.publicUrl) {
    problems.push('USE_WEBHOOK=1 требует PUBLIC_URL');
  }
  return problems;
}

export const ocrEnabled = () => Boolean(config.anthropicApiKey);
