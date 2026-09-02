import crypto from 'node:crypto';
import { config } from './config.js';
import { createLoginToken, consumeLoginToken, getUser } from './db.js';

export const COOKIE_NAME = 'kopeyka_session';

const secret = config.sessionSecret || crypto.randomBytes(32).toString('hex');
if (!config.sessionSecret) {
  console.warn('SESSION_SECRET не задан — сгенерирован временный ключ, сессии сбросятся при рестарте');
}

const b64url = (buffer) => Buffer.from(buffer).toString('base64url');

function sign(data) {
  return crypto.createHmac('sha256', secret).update(data).digest('base64url');
}

/** Компактный подписанный токен сессии: payload.signature */
export function createSession(userId, days = config.sessionDays) {
  const payload = b64url(
    JSON.stringify({ uid: userId, exp: Date.now() + days * 86_400_000 }),
  );
  return `${payload}.${sign(payload)}`;
}

export function verifySession(token) {
  if (!token || typeof token !== 'string') return null;
  const [payload, signature] = token.split('.');
  if (!payload || !signature) return null;
  const expected = sign(payload);
  const a = Buffer.from(signature);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  try {
    const data = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    if (!data.uid || !data.exp || data.exp < Date.now()) return null;
    return data.uid;
  } catch {
    return null;
  }
}

/** Одноразовая ссылка входа, которую присылает бот. */
export function issueLoginLink(userId) {
  const token = crypto.randomBytes(24).toString('base64url');
  const { expiresAt } = createLoginToken(userId, token, 15);
  const base = config.publicUrl || `http://localhost:${config.port}`;
  return { url: `${base}/auth?token=${token}`, expiresAt };
}

export function loginWithToken(token) {
  const userId = consumeLoginToken(token);
  if (!userId) return null;
  const user = getUser(userId);
  if (!user) return null;
  return { user, session: createSession(user.id) };
}

/**
 * Проверка данных Telegram Login Widget (запасной способ входа).
 * https://core.telegram.org/widgets/login#checking-authorization
 */
export function verifyTelegramLogin(data) {
  const { hash, ...rest } = data || {};
  if (!hash || !config.botToken) return null;
  const checkString = Object.keys(rest)
    .sort()
    .map((key) => `${key}=${rest[key]}`)
    .join('\n');
  const secretKey = crypto.createHash('sha256').update(config.botToken).digest();
  const computed = crypto.createHmac('sha256', secretKey).update(checkString).digest('hex');
  if (computed !== hash) return null;
  if (Math.abs(Date.now() / 1000 - Number(rest.auth_date || 0)) > 86_400) return null;
  return Number(rest.id);
}

/**
 * Проверка initData из Telegram Mini App — панель открывается прямо
 * внутри Telegram и логинит пользователя без ссылок и паролей.
 * https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
 */
export function verifyWebAppInitData(initData) {
  if (!initData || !config.botToken) return null;
  const params = new URLSearchParams(initData);
  const hash = params.get('hash');
  if (!hash) return null;
  params.delete('hash');
  params.delete('signature');
  const checkString = [...params.entries()]
    .map(([key, value]) => `${key}=${value}`)
    .sort()
    .join('\n');
  const secretKey = crypto.createHmac('sha256', 'WebAppData').update(config.botToken).digest();
  const computed = crypto.createHmac('sha256', secretKey).update(checkString).digest('hex');
  if (computed !== hash) return null;
  const authDate = Number(params.get('auth_date') || 0);
  if (!authDate || Math.abs(Date.now() / 1000 - authDate) > 86_400) return null;
  try {
    const user = JSON.parse(params.get('user') || 'null');
    return user && user.id ? user : null;
  } catch {
    return null;
  }
}

export function cookieOptions() {
  return {
    httpOnly: true,
    sameSite: 'lax',
    secure: config.publicUrl.startsWith('https://'),
    maxAge: config.sessionDays * 86_400_000,
    path: '/',
  };
}
