/**
 * Категории трат.
 *
 * Цвета — из проверенной валидатором категориальной палитры (см. README):
 * здесь светлые значения для API, парные тёмные живут в CSS-переменных
 * --cat-<ключ>, чтобы графики читались в обеих темах. Ключ категории стабилен и хранится в базе,
 * название и эмодзи используются в боте и панели.
 *
 * `aliases` — слова, по которым категорию можно указать явно
 * («такси 900 транспорт»). `keywords` — слова, по которым категория
 * угадывается из описания («кофе 350» → Кафе).
 */
export const CATEGORIES = [
  {
    key: 'groceries',
    title: 'Продукты',
    emoji: '🛒',
    color: '#1baf7a',
    aliases: ['продукты', 'еда', 'groceries', 'food', 'oziq'],
    keywords: [
      'магазин', 'супермаркет', 'продукт', 'молоко', 'хлеб', 'яйца', 'мясо', 'курица',
      'овощи', 'фрукты', 'сыр', 'вода', 'корзина', 'базар', 'рынок', 'korzinka', 'makro',
      'havas', 'grocery', 'market', 'milk', 'bread',
    ],
  },
  {
    key: 'cafe',
    title: 'Кафе и рестораны',
    emoji: '☕',
    color: '#eb6834',
    aliases: ['кафе', 'ресторан', 'cafe', 'restaurant'],
    keywords: [
      'кофе', 'капучино', 'латте', 'американо', 'чай', 'обед', 'ужин', 'завтрак', 'ланч',
      'бургер', 'пицца', 'шаурма', 'самса', 'плов', 'лагман', 'суши', 'бар', 'пиво',
      'коктейль', 'десерт', 'мороженое', 'кондитерская', 'столовая', 'фастфуд', 'доставка еды',
      'coffee', 'lunch', 'dinner', 'pizza', 'burger', 'wolt', 'yandex eda',
    ],
  },
  {
    key: 'transport',
    title: 'Транспорт',
    emoji: '🚕',
    color: '#2a78d6',
    aliases: ['транспорт', 'transport', 'дорога'],
    keywords: [
      'такси', 'яндекс', 'yandex go', 'uber', 'bolt', 'мийок', 'метро', 'автобус', 'маршрутка',
      'поезд', 'билет', 'самолет', 'самолёт', 'авиабилет', 'бензин', 'заправка', 'газ',
      'парковка', 'каршеринг', 'мойка', 'шиномонтаж', 'taxi', 'metro', 'bus', 'fuel', 'petrol',
    ],
  },
  {
    key: 'home',
    title: 'Дом и счета',
    emoji: '🏠',
    color: '#4a3aa7',
    aliases: ['дом', 'жильё', 'жилье', 'счета', 'home', 'uy'],
    keywords: [
      'аренда', 'квартира', 'коммуналка', 'коммунальные', 'свет', 'электричество', 'вода счет',
      'отопление', 'ипотека', 'ремонт', 'мебель', 'посуда', 'бытовая химия', 'уборка',
      'rent', 'utilities', 'furniture',
    ],
  },
  {
    key: 'connection',
    title: 'Связь и подписки',
    emoji: '📱',
    color: '#008300',
    aliases: ['связь', 'подписки', 'подписка', 'интернет', 'internet'],
    keywords: [
      'мобильная связь', 'телефон', 'интернет', 'вайфай', 'wifi', 'ucell', 'beeline', 'uzmobile',
      'humans', 'мтс', 'netflix', 'spotify', 'youtube', 'подписк', 'хостинг', 'домен', 'icloud',
      'apple', 'google one', 'chatgpt', 'claude', 'subscription',
    ],
  },
  {
    key: 'health',
    title: 'Здоровье',
    emoji: '💊',
    color: '#e87ba4',
    aliases: ['здоровье', 'health', 'аптека'],
    keywords: [
      'аптека', 'лекарств', 'таблетк', 'врач', 'клиника', 'анализы', 'стоматолог', 'зубной',
      'массаж', 'очки', 'линзы', 'страховка', 'pharmacy', 'doctor', 'dentist',
    ],
  },
  {
    key: 'sport',
    title: 'Спорт',
    emoji: '🏋️',
    color: '#0e9bb0',
    aliases: ['спорт', 'sport', 'фитнес'],
    keywords: ['зал', 'спортзал', 'фитнес', 'бассейн', 'тренер', 'йога', 'gym', 'fitness', 'pool'],
  },
  {
    key: 'shopping',
    title: 'Покупки',
    emoji: '🛍️',
    color: '#eda100',
    aliases: ['покупки', 'shopping', 'одежда'],
    keywords: [
      'одежда', 'обувь', 'кроссовк', 'футболка', 'джинсы', 'куртка', 'носки', 'сумка',
      'косметика', 'парфюм', 'техника', 'наушники', 'телефон новый', 'ноутбук', 'зарядка',
      'clothes', 'shoes', 'uniqlo', 'zara', 'wildberries', 'ozon',
    ],
  },
  {
    key: 'fun',
    title: 'Развлечения',
    emoji: '🎬',
    color: '#e34948',
    aliases: ['развлечения', 'fun', 'досуг'],
    keywords: [
      'кино', 'театр', 'концерт', 'игра', 'steam', 'playstation', 'боулинг', 'бильярд',
      'клуб', 'парк', 'аттракцион', 'книга', 'выставка', 'cinema', 'concert', 'game',
    ],
  },
  {
    key: 'education',
    title: 'Образование',
    emoji: '📚',
    color: '#8a8f1e',
    aliases: ['образование', 'учеба', 'учёба', 'education'],
    keywords: [
      'курс', 'учебник', 'репетитор', 'школа', 'универ', 'колледж', 'контракт', 'семинар',
      'course', 'tuition', 'udemy', 'coursera',
    ],
  },
  {
    key: 'gifts',
    title: 'Подарки и помощь',
    emoji: '🎁',
    color: '#9b4fd1',
    aliases: ['подарки', 'подарок', 'gifts', 'помощь'],
    keywords: ['подарок', 'цветы', 'донат', 'благотвор', 'свадьба', 'день рождения', 'gift', 'flowers'],
  },
  {
    key: 'pets',
    title: 'Питомцы',
    emoji: '🐾',
    color: '#96601f',
    aliases: ['питомцы', 'животные', 'pets'],
    keywords: ['корм', 'ветеринар', 'кот', 'кошка', 'собака', 'наполнитель', 'vet', 'pet'],
  },
  {
    key: 'other',
    title: 'Прочее',
    emoji: '💸',
    color: '#7a8290',
    aliases: ['прочее', 'другое', 'other', 'misc'],
    keywords: [],
  },
];

export const CATEGORY_BY_KEY = new Map(CATEGORIES.map((c) => [c.key, c]));

export const DEFAULT_CATEGORY = 'other';

export function getCategory(key) {
  return CATEGORY_BY_KEY.get(key) || CATEGORY_BY_KEY.get(DEFAULT_CATEGORY);
}

export function categoryLabel(key) {
  const c = getCategory(key);
  return `${c.emoji} ${c.title}`;
}

/** Явное указание категории словом в сообщении: «такси 900 транспорт». */
export function findExplicitCategory(text) {
  const words = normalize(text).split(/\s+/).filter(Boolean);
  for (const category of CATEGORIES) {
    for (const alias of category.aliases) {
      if (words.includes(alias)) {
        return { key: category.key, matched: alias };
      }
    }
  }
  return null;
}

/** Угадывание категории по описанию: «кофе 350» → cafe. */
export function guessCategory(text) {
  const haystack = ` ${normalize(text)} `;
  let best = null;
  for (const category of CATEGORIES) {
    for (const keyword of category.keywords) {
      const needle = normalize(keyword);
      if (!needle) continue;
      const idx = haystack.indexOf(needle.includes(' ') ? needle : ` ${needle}`);
      if (idx === -1) continue;
      // Более длинное совпадение считаем более точным.
      if (!best || needle.length > best.length) {
        best = { key: category.key, length: needle.length, matched: keyword };
      }
    }
  }
  return best ? { key: best.key, matched: best.matched } : null;
}

export function normalize(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}
