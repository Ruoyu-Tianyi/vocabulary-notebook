import test from 'node:test'
import assert from 'node:assert/strict'
import { shuffle } from '../src/lib/shuffle.js'

test('shuffle preserves every card without changing the source deck', () => {
  const cards = Array.from({ length: 20 }, (_, id) => ({ id }))
  const original = [...cards]
  const shuffled = shuffle(cards, 12345)
  assert.deepEqual(cards, original)
  assert.notEqual(shuffled, cards)
  assert.deepEqual([...shuffled].sort((a, b) => a.id - b.id), cards)
})

test('the same seed is stable while a new seed produces a new order', () => {
  const cards = Array.from({ length: 20 }, (_, index) => index)
  assert.deepEqual(shuffle(cards, 12345), shuffle(cards, 12345))
  assert.notDeepEqual(shuffle(cards, 12345), shuffle(cards, 12346))
})

test('shuffle handles empty and single-card decks', () => {
  assert.deepEqual(shuffle([], 1), [])
  assert.deepEqual(shuffle(['only'], 1), ['only'])
})
