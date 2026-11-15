// When Vocove is shown inside another page's iframe (for example study notes
// with a vocabulary side panel), the parent may send
//   { type: 'vocove:prefill-word', word: '...' }
// to put a word into the "add word" box. Only the direct parent is accepted,
// and the message never saves anything: the user still confirms with Enter or
// the save button, so an embedding page cannot write to the library.
export const PREFILL_TYPE = 'vocove:prefill-word'
export const PREFILL_ACK_TYPE = 'vocove:prefill-ack'
export const PREFILL_MAX_LENGTH = 80

export function readPrefillMessage(event, parentWindow) {
  if (!event || !parentWindow || event.source !== parentWindow) return null
  const data = event.data
  if (!data || typeof data !== 'object' || data.type !== PREFILL_TYPE || typeof data.word !== 'string') return null
  const word = data.word.replace(/\s+/g, ' ').trim()
  if (!word || word.length > PREFILL_MAX_LENGTH) return null
  return word
}

// A page opened from file:// has the opaque origin "null", which postMessage
// cannot target directly; the acknowledgement carries no library data.
export function replyTarget(origin) {
  return !origin || origin === 'null' ? '*' : origin
}
