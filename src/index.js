import { config, assertConfig } from './config.js';
import { createServer } from './server.js';
import { handleUpdate, BOT_COMMANDS } from './bot.js';
import { startPolling, setMyCommands, getMe, setWebhook, deleteWebhook } from './telegram.js';
import { ocrAvailable } from './ocr.js';

const problems = assertConfig();
for (const problem of problems) console.warn(`⚠️  ${problem}`);

const app = createServer();
const server = app.listen(config.port, () => {
  console.log(`🌐 Панель: ${config.publicUrl || `http://localhost:${config.port}`}`);
  console.log(`📷 Распознавание чеков: ${ocrAvailable() ? 'включено' : 'выключено'}`);
});

let stopBot = () => {};

if (config.botToken) {
  try {
    const me = await getMe();
    console.log(`🤖 Бот: @${me.username}`);
    await setMyCommands(BOT_COMMANDS);

    if (config.useWebhook) {
      const url = `${config.publicUrl}/telegram/webhook`;
      await setWebhook(url, config.webhookSecret);
      console.log(`🔗 Вебхук: ${url}`);
    } else {
      await deleteWebhook();
      stopBot = startPolling(handleUpdate);
      console.log('🔄 Режим: long polling');
    }
  } catch (error) {
    console.error('Не удалось запустить бота:', error.message);
    if ([401, 404].includes(error.code)) {
      console.error('Похоже, BOT_TOKEN неверный — возьмите свежий у @BotFather.');
    }
    if (/EAI_AGAIN|ENOTFOUND|getaddrinfo/i.test(error.message)) {
      console.error('Не резолвится api.telegram.org — у контейнера нет рабочего DNS.');
      console.error('Лечится параметром dns в docker-compose.yml (1.1.1.1, 8.8.8.8) и пересборкой.');
    } else if (/ETIMEDOUT|ECONNREFUSED|ECONNRESET|EHOSTUNREACH/i.test(error.message)) {
      console.error('Сеть не пускает к api.telegram.org — проверьте файрвол и доступность Telegram с сервера.');
    }
    console.error('Веб-панель продолжит работать, бот — нет.');
  }
} else {
  console.warn('BOT_TOKEN не задан — работает только веб-панель');
}

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    console.log(`\n${signal}: останавливаюсь…`);
    stopBot();
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 3000).unref();
  });
}
