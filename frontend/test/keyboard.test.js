import test from 'node:test'
import assert from 'node:assert/strict'
import {
  canUseReviewShortcut,
  getReviewShortcutAction,
  isEditableTarget,
  isInteractiveTarget,
  isShortcutEvent,
  isWithinDialog,
} from '../src/lib/keyboard.js'

// 仅模拟 closest 所需的祖先匹配，不依赖浏览器或新增 DOM 测试库。
function target(selectors = [], parent = null) {
  return {
    closest(query) {
      return query.split(/,\s*/).some(selector => selectors.includes(selector))
        ? this
        : parent?.closest(query) || null
    },
  }
}

const page = target()
const reviewArea = target(['[data-review-shortcuts]'])
const card = target(['button'], reviewArea)
const cardLabel = target([], card)
const ordinaryButton = target(['button'])
const link = target(['a[href]'])
const input = target(['input'])
const dialogButton = target(['button'], target(['[role="dialog"]']))
const key = (value, element = page, extra = {}) => ({ key: value, target: element, ...extra })

test('shortcut guard ignores held keys, handled events, composition and modifier combinations', () => {
  assert.equal(isShortcutEvent(key('1')), true)
  for (const extra of [
    { defaultPrevented: true }, { repeat: true }, { isComposing: true }, { keyCode: 229 },
    { nativeEvent: { isComposing: true } }, { nativeEvent: { keyCode: 229 } },
    { ctrlKey: true }, { metaKey: true }, { altKey: true }, { shiftKey: true },
  ]) {
    assert.equal(isShortcutEvent(key('1', page, extra)), false)
  }
  assert.equal(isShortcutEvent(key('?', page, { shiftKey: true }), { allowShift: true }), true)
  assert.equal(isShortcutEvent(key('?', page, { ctrlKey: true }), { allowShift: true }), false)
})

test('editable and dialog checks include descendants and custom input controls', () => {
  for (const selector of ['input', 'textarea', 'select', '[role="textbox"]', '[role="combobox"]', '[contenteditable]:not([contenteditable="false"])']) {
    assert.equal(isEditableTarget(target([], target([selector]))), true)
  }
  assert.equal(isEditableTarget({ isContentEditable: true }), true)
  assert.equal(isEditableTarget(cardLabel), false)
  assert.equal(isWithinDialog(dialogButton), true)
  assert.equal(isWithinDialog(target([], target(['[role="alertdialog"]']))), true)
  assert.equal(isWithinDialog(card), false)
})

test('review accepts its own button descendants while leaving other controls and dialogs alone', () => {
  assert.equal(isInteractiveTarget(cardLabel), true)
  assert.equal(canUseReviewShortcut(key('2', page)), true)
  assert.equal(canUseReviewShortcut(key('2', card)), true)
  assert.equal(canUseReviewShortcut(key('2', cardLabel)), true)
  for (const element of [ordinaryButton, link, input, dialogButton, target(['summary']), target(['[role="tab"]'])]) {
    assert.equal(canUseReviewShortcut(key('2', element)), false)
  }
  const reviewInsideDialog = target(['button'], target(['[data-review-shortcuts]'], target(['[role="dialog"]'])))
  assert.equal(canUseReviewShortcut(key('2', reviewInsideDialog)), false)
  const bodyWhileSavingDialog = { ...page, ownerDocument: { querySelector: () => ({}) } }
  assert.equal(canUseReviewShortcut(key('2', bodyWhileSavingDialog)), false)
})

test('Space and Enter reveal from the page but preserve native button activation', () => {
  for (const value of [' ', 'Enter']) {
    assert.deepEqual(getReviewShortcutAction(key(value), { mode: 'daily' }), { type: 'reveal' })
    assert.deepEqual(getReviewShortcutAction(key(value), { mode: 'all' }), { type: 'reveal' })
    assert.equal(getReviewShortcutAction(key(value, card), { mode: 'daily' }), null)
    assert.equal(getReviewShortcutAction(key(value), { mode: 'daily', flipped: true }), null)
  }
})

test('daily ratings work after focusing a card or a rating button only after the answer is shown', () => {
  const ratingButton = target(['button'], reviewArea)
  for (const element of [page, card, cardLabel, ratingButton]) {
    for (const value of ['1', '2', '3', '4']) {
      assert.deepEqual(getReviewShortcutAction(key(value, element), { mode: 'daily', flipped: true }), { type: 'rate', rating: Number(value) })
      assert.equal(getReviewShortcutAction(key(value, element), { mode: 'daily', flipped: false }), null)
    }
  }
  for (const extra of [{ submitting: true }, { done: true }, { hasCard: false }]) {
    assert.equal(getReviewShortcutAction(key('3', card), { mode: 'daily', flipped: true, ...extra }), null)
  }
})

test('all-word navigation consumes only available previous and revealed next actions', () => {
  for (const element of [page, card, target(['button'], reviewArea)]) {
    assert.equal(getReviewShortcutAction(key('ArrowLeft', element), { mode: 'all' }), null)
    assert.deepEqual(getReviewShortcutAction(key('ArrowLeft', element), { mode: 'all', hasPrevious: true }), { type: 'previous' })
    assert.equal(getReviewShortcutAction(key('ArrowRight', element), { mode: 'all' }), null)
    assert.deepEqual(getReviewShortcutAction(key('ArrowRight', element), { mode: 'all', flipped: true }), { type: 'next' })
  }
  assert.equal(getReviewShortcutAction(key('3', card), { mode: 'all', flipped: true }), null)
  assert.equal(getReviewShortcutAction(key('ArrowLeft', card), { mode: 'daily', hasPrevious: true }), null)
})

test('review actions cannot bypass focus, repeat, IME or browser shortcut protection', () => {
  for (const event of [
    key('3', ordinaryButton), key('3', input), key('3', dialogButton), key('3', link),
    key('3', card, { repeat: true }), key('3', card, { nativeEvent: { isComposing: true } }),
    key('3', card, { metaKey: true }), key('3', card, { defaultPrevented: true }),
    key(' ', page, { shiftKey: true }),
  ]) {
    assert.equal(getReviewShortcutAction(event, { mode: 'daily', flipped: true }), null)
  }
  assert.equal(getReviewShortcutAction(key('ArrowLeft', card, { repeat: true }), { mode: 'all', hasPrevious: true }), null)
})
