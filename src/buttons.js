/**
 * Стили кнопок Telegram.
 *
 * Bot API (с 9 февраля 2026) принимает у inline-кнопок поле `style`:
 *   primary — синяя, success — зелёная, danger — красная.
 * Если стиль не указан, клиент рисует кнопку своим обычным цветом;
 * старые версии Telegram поле просто игнорируют.
 *
 * Здесь цвет назначается по роли действия, а не на глаз:
 *   action  — главное действие экрана (открыть панель, исправить, выбрать)
 *   confirm — создание и подтверждение (поставить лимит, сохранить)
 *   destroy — необратимое (удалить трату, снять лимит)
 *   plain   — второстепенное (назад, категории, справка) — без цвета
 */
export const ROLE_STYLE = {
  action: 'primary',
  confirm: 'success',
  destroy: 'danger',
  plain: null,
};

export const BUTTON_ROLES = Object.keys(ROLE_STYLE);

/** Собирает inline-кнопку: текст, действие и цвет по роли. */
export function button(text, action, role = 'plain') {
  const style = ROLE_STYLE[role] ?? null;
  return {
    text,
    ...action,
    ...(style ? { style } : {}),
  };
}

/** Кнопка с callback_data. */
export const cbButton = (text, data, role) => button(text, { callback_data: data }, role);

/** Кнопка со ссылкой. */
export const urlButton = (text, url, role) => button(text, { url }, role);

/** Кнопка, открывающая Mini App. */
export const appButton = (text, url, role = 'action') => button(text, { web_app: { url } }, role);

/** Убирает стили — запасной путь, если Bot API их не принял. */
export function stripStyles(markup) {
  if (!markup?.inline_keyboard) return markup;
  return {
    ...markup,
    inline_keyboard: markup.inline_keyboard.map((row) =>
      row.map(({ style, ...rest }) => rest),
    ),
  };
}
