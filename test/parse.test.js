import test from 'node:test';
import assert from 'node:assert/strict';
import { parseExpense } from '../src/parse.js';

const parse = (text) => parseExpense(text, { defaultCurrency: 'UZS' });

test('сумма после описания', () => {
  const result = parse('кофе 350');
  assert.equal(result.amount, 350);
  assert.equal(result.note, 'кофе');
  assert.equal(result.category, 'cafe');
});

test('сумма перед описанием', () => {
  const result = parse('350 кофе');
  assert.equal(result.amount, 350);
  assert.equal(result.category, 'cafe');
});

test('описание с несколькими словами и категория из ключевого слова', () => {
  const result = parse('такси 900 работа');
  assert.equal(result.amount, 900);
  assert.equal(result.category, 'transport');
  assert.equal(result.note, 'такси работа');
});

test('явная категория словом', () => {
  const result = parse('шаверма 25000 продукты');
  assert.equal(result.category, 'groceries');
  assert.equal(result.note, 'шаверма');
});

test('пробел как разделитель тысяч', () => {
  assert.equal(parse('продукты 1 200').amount, 1200);
  assert.equal(parse('аренда 3 500 000').amount, 3500000);
});

test('запятая как десятичный разделитель', () => {
  assert.equal(parse('обед 12,50 usd').amount, 12.5);
});

test('«1,200» — это тысячи', () => {
  assert.equal(parse('такси 1,200').amount, 1200);
});

test('сокращение к / k', () => {
  assert.equal(parse('продукты 12к').amount, 12000);
  assert.equal(parse('продукты 12k').amount, 12000);
  assert.equal(parse('машина 1.5млн').amount, 1500000);
});

test('валюта символом и кодом', () => {
  assert.equal(parse('обед 12$').currency, 'USD');
  assert.equal(parse('обед $12').currency, 'USD');
  assert.equal(parse('обед 12 usd').currency, 'USD');
  assert.equal(parse('обед 12 usd').note, 'обед');
});

test('валюта по умолчанию — базовая валюта пользователя', () => {
  const result = parse('кофе 350');
  assert.equal(result.currency, 'UZS');
  assert.equal(result.currencyExplicit, false);
});

test('«вчера» переносит трату на день назад', () => {
  const result = parse('вчера продукты 120000');
  assert.equal(result.dayShift, -1);
  assert.equal(result.note, 'продукты');
});

test('количество не путается с суммой', () => {
  const result = parse('2 кофе 700');
  assert.equal(result.amount, 700);
});

test('единицы измерения не считаются суммой', () => {
  const result = parse('вода 5л 12000');
  assert.equal(result.amount, 12000);
});

test('без суммы — null', () => {
  assert.equal(parse('привет'), null);
  assert.equal(parse(''), null);
});

test('неизвестное описание попадает в «прочее»', () => {
  const result = parse('пылесосный мешок 45000');
  assert.equal(result.category, 'other');
  assert.equal(result.categorySource, 'default');
});
