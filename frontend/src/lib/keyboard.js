const EDITABLE_SELECTOR = 'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="combobox"]'
const INTERACTIVE_SELECTOR = `${EDITABLE_SELECTOR}, button, a[href], summary, [role="button"], [role="link"], [role="menuitem"], [role="tab"], [role="checkbox"], [role="radio"], [role="switch"], [role="slider"], [role="spinbutton"], [tabindex]:not([tabindex="-1"])`
const DIALOG_SELECTOR = 'dialog[open], [role="dialog"], [role="alertdialog"], [aria-modal="true"]'

function closest(target, selector) {
  const element = typeof target?.closest === 'function' ? target : target?.parentElement
  return element?.closest?.(selector) || null
}

export function isShortcutEvent(event, { allowShift = false } = {}) {
  return !(
    event.defaultPrevented || event.repeat || event.isComposing || event.nativeEvent?.isComposing ||
    event.keyCode === 229 || event.nativeEvent?.keyCode === 229 ||
    event.ctrlKey || event.metaKey || event.altKey || (!allowShift && event.shiftKey)
  )
}

export function isEditableTarget(target) {
  return Boolean(target?.isContentEditable || closest(target, EDITABLE_SELECTOR))
}

export function isWithinDialog(target) {
  return Boolean(closest(target, DIALOG_SELECTOR))
}

export function isInteractiveTarget(target) {
  return Boolean(closest(target, INTERACTIVE_SELECTOR))
}

export function canUseReviewShortcut(event) {
  if (!isShortcutEvent(event) || isEditableTarget(event.target) || isWithinDialog(event.target)) return false
  // 模态提交期间控件可能全部禁用并失焦，仍须阻断背后的复习操作。
  if (event.target?.ownerDocument?.querySelector('[aria-modal="true"], dialog[open]')) return false
  if (!isInteractiveTarget(event.target)) return true
  // 卡片和本轮操作按钮允许数字/方向键，其他页面控件仍保留自己的键盘行为。
  const button = closest(event.target, 'button')
  return Boolean(button && closest(button, '[data-review-shortcuts]'))
}

export function getReviewShortcutAction(event, {
  mode,
  hasCard = true,
  flipped = false,
  hasPrevious = false,
  submitting = false,
  done = false,
} = {}) {
  if (!hasCard || done || submitting || !canUseReviewShortcut(event)) return null
  if ((event.key === ' ' || event.key === 'Enter') && !flipped && !isInteractiveTarget(event.target)) {
    return { type: 'reveal' }
  }
  if (mode === 'daily' && flipped && ['1', '2', '3', '4'].includes(event.key)) {
    return { type: 'rate', rating: Number(event.key) }
  }
  if (mode === 'all' && event.key === 'ArrowLeft' && hasPrevious) return { type: 'previous' }
  if (mode === 'all' && event.key === 'ArrowRight' && flipped) return { type: 'next' }
  return null
}
