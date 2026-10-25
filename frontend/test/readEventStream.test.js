import test from 'node:test'
import assert from 'node:assert/strict'
import { readEventStream } from '../src/lib/readEventStream.js'

function streamChunks(chunks) {
  return new ReadableStream({
    start(controller) {
      chunks.forEach(chunk => controller.enqueue(chunk))
      controller.close()
    },
  })
}

test('SSE preserves UTF-8 characters and frame boundaries split across chunks', async () => {
  const expected = { type: 'enriched', word_id: 'word-1', definition: '词汇；积累' }
  const encoded = new TextEncoder().encode(`data: ${JSON.stringify(expected)}\n\n`)
  const stream = streamChunks(Array.from(encoded, byte => Uint8Array.of(byte)))
  const events = []
  await readEventStream(stream, event => events.push(event))
  assert.deepEqual(events, [expected])
  assert.equal(stream.locked, false)
})

test('SSE supports CRLF, multiline data, no-space fields and ignores malformed frames', async () => {
  const source = ': heartbeat\r\n\r\ndata:invalid json\r\n\r\ndata:{"type":"enriched",\r\ndata:"word_id":"two"}\r\n\r\ndata: {"word_id":"three"}\n\n'
  const stream = streamChunks([new TextEncoder().encode(source)])
  const events = []
  await readEventStream(stream, event => events.push(event))
  assert.deepEqual(events, [{ type: 'enriched', word_id: 'two' }, { word_id: 'three' }])
})

test('aborting a pending SSE read cancels the stream and releases its lock', async () => {
  const controller = new AbortController()
  let cancelled = 0
  const stream = new ReadableStream({ cancel() { cancelled += 1 } })
  const events = []
  const reading = readEventStream(stream, event => events.push(event), controller.signal)
  controller.abort()
  await reading
  assert.equal(cancelled, 1)
  assert.equal(stream.locked, false)
  assert.deepEqual(events, [])
})

test('an already aborted subscription never emits a buffered frame', async () => {
  const controller = new AbortController()
  controller.abort()
  const stream = streamChunks([new TextEncoder().encode('data: {"word_id":"late"}\n\n')])
  const events = []
  await readEventStream(stream, event => events.push(event), controller.signal)
  assert.deepEqual(events, [])
  assert.equal(stream.locked, false)
})

test('consumer failures still release and cancel the reader', async () => {
  let cancelled = false
  const stream = new ReadableStream({
    start(controller) { controller.enqueue(new TextEncoder().encode('data: {"word_id":"one"}\n\n')) },
    cancel() { cancelled = true },
  })
  await assert.rejects(readEventStream(stream, () => { throw new Error('consumer failed') }), /consumer failed/)
  assert.equal(cancelled, true)
  assert.equal(stream.locked, false)
})
