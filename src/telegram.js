import { config } from './config.js';

const API = (method) => `https://api.telegram.org/bot${config.botToken}/${method}`;

export class TelegramError extends Error {
  constructor(method, description, code) {
    super(`Telegram ${method} failed: ${description}`);
    this.code = code;
    this.description = description;
  }
}

export async function callApi(method, params = {}) {
  let response;
  try {
    response = await fetch(API(method), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(params),
    });
  } catch (error) {
    // fetch прячет причину в cause — без неё в логе остаётся бесполезное «fetch failed».
    const code = error.cause?.code || error.code || '';
    const detail = error.cause?.message || error.message;
    throw new TelegramError(method, `нет связи с api.telegram.org${code ? ` (${code})` : ''}: ${detail}`, 0);
  }
  const data = await response
    .json()
    .catch(() => ({ ok: false, description: `HTTP ${response.status}, ответ не JSON`, error_code: response.status }));
  if (!data.ok) throw new TelegramError(method, data.description, data.error_code || response.status);
  return data.result;
}

export function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function sendMessage(chatId, text, extra = {}) {
  return callApi('sendMessage', {
    chat_id: chatId,
    text,
    parse_mode: 'HTML',
    link_preview_options: { is_disabled: true },
    ...extra,
  });
}

export function editMessageText(chatId, messageId, text, extra = {}) {
  return callApi('editMessageText', {
    chat_id: chatId,
    message_id: messageId,
    text,
    parse_mode: 'HTML',
    link_preview_options: { is_disabled: true },
    ...extra,
  });
}

export function answerCallbackQuery(id, text = '', extra = {}) {
  return callApi('answerCallbackQuery', { callback_query_id: id, text, ...extra });
}

export function deleteMessage(chatId, messageId) {
  return callApi('deleteMessage', { chat_id: chatId, message_id: messageId });
}

export async function sendDocument(chatId, { filename, contentType, data, caption }) {
  const form = new FormData();
  form.append('chat_id', String(chatId));
  if (caption) {
    form.append('caption', caption);
    form.append('parse_mode', 'HTML');
  }
  form.append('document', new Blob([data], { type: contentType }), filename);
  const response = await fetch(API('sendDocument'), { method: 'POST', body: form });
  const result = await response.json().catch(() => ({ ok: false, description: 'invalid JSON' }));
  if (!result.ok) throw new TelegramError('sendDocument', result.description, result.error_code);
  return result.result;
}

/** Скачивает файл (например, фото чека) во временный буфер. */
export async function downloadFile(fileId) {
  const file = await callApi('getFile', { file_id: fileId });
  const url = `https://api.telegram.org/file/bot${config.botToken}/${file.file_path}`;
  const response = await fetch(url);
  if (!response.ok) throw new TelegramError('downloadFile', `HTTP ${response.status}`, response.status);
  return {
    buffer: Buffer.from(await response.arrayBuffer()),
    path: file.file_path,
  };
}

export function setMyCommands(commands) {
  return callApi('setMyCommands', { commands });
}

export function getMe() {
  return callApi('getMe');
}

export function setWebhook(url, secretToken) {
  return callApi('setWebhook', {
    url,
    secret_token: secretToken || undefined,
    allowed_updates: ['message', 'callback_query'],
    drop_pending_updates: false,
  });
}

export function deleteWebhook() {
  return callApi('deleteWebhook', { drop_pending_updates: false });
}

/**
 * Long polling. Переподключается при ошибках, чтобы бот не «умирал»
 * от одной сетевой проблемы.
 */
export function startPolling(handleUpdate) {
  let offset = 0;
  let stopped = false;

  (async () => {
    while (!stopped) {
      try {
        const updates = await callApi('getUpdates', {
          offset,
          timeout: 30,
          allowed_updates: ['message', 'callback_query'],
        });
        for (const update of updates) {
          offset = update.update_id + 1;
          try {
            await handleUpdate(update);
          } catch (error) {
            console.error('update handler failed', error);
          }
        }
      } catch (error) {
        if (error instanceof TelegramError && error.code === 409) {
          console.error('Telegram: конфликт getUpdates — запущен другой экземпляр бота или включён вебхук');
        } else {
          console.error('polling error', error.message);
        }
        await new Promise((resolve) => setTimeout(resolve, 3000));
      }
    }
  })();

  return () => {
    stopped = true;
  };
}
