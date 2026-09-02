/**
 * Демо-данные для локальной разработки:
 *   node scripts/seed.js <telegram_user_id>
 * Заполняет два месяца трат и печатает ссылку для входа в панель.
 */
import { upsertUser } from '../src/db.js';
import { addExpense } from '../src/service.js';
import { issueLoginLink } from '../src/auth.js';

const userId = Number(process.argv[2] || 424242);
const user = upsertUser({ id: userId, first_name: 'Демо', username: 'demo' });

const SAMPLES = [
  ['кофе', 'cafe', 25000, 35000],
  ['обед', 'cafe', 45000, 90000],
  ['такси', 'transport', 20000, 60000],
  ['метро', 'transport', 2000, 4000],
  ['продукты', 'groceries', 80000, 350000],
  ['аптека', 'health', 30000, 120000],
  ['кино', 'fun', 60000, 120000],
  ['интернет', 'connection', 90000, 150000],
  ['спортзал', 'sport', 250000, 400000],
  ['подарок', 'gifts', 150000, 400000],
];

const random = (min, max) => Math.round((min + Math.random() * (max - min)) / 1000) * 1000;

let created = 0;
for (let daysAgo = 60; daysAgo >= 0; daysAgo -= 1) {
  // В последние две недели трат больше — чтобы демо-панель выглядела живой.
  const count = daysAgo <= 14 ? 1 + Math.floor(Math.random() * 3) : Math.floor(Math.random() * 3);
  for (let i = 0; i < count; i += 1) {
    const [note, category, min, max] = SAMPLES[Math.floor(Math.random() * SAMPLES.length)];
    const spentAt = new Date(Date.now() - daysAgo * 86_400_000 - (i * 3 + 1) * 3_600_000);
    addExpense(user, { amount: random(min, max), category, note, spentAt, source: 'bot' });
    created += 1;
  }
}

console.log(`Создано трат: ${created} для пользователя ${userId}`);
console.log(`Ссылка для входа: ${issueLoginLink(userId).url}`);
