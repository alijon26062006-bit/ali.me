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
