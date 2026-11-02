"""Domain notebooks do not infer meaning from classification labels or change old words."""
import asyncio
import json
import httpx

import pytest

import app
import notebook_contexts as contexts
import sync_storage
from tests.local_client import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'DATA_FILE', tmp_path / 'words.json')
    monkeypatch.setattr(app, '_new_enrichment_candidates', {})
    monkeypatch.setattr(app, '_enriching_ids', {})
    async def enqueue(items):
        pass
    monkeypatch.setattr(app, '_enqueue_enrich_batch', enqueue)
    return TestClient(app.app)


def book(client, name, preset=''):
    response = client.post('/api/notebooks', json={'name': name, 'context_id': preset})
    assert response.status_code == 200, response.text
    return response.json()


def test_classification_and_context_are_independent(client):
    ordinary = book(client, '金融英语')
    finance = book(client, '第一学期', 'finance')
    assert contexts.prompt_for(ordinary['id']) == ''
    assert 'finance' in contexts.prompt_for(finance['id'])
    renamed = client.put('/api/notebooks/' + finance['id'], json={'name': '法律英语'}).json()
    assert renamed['context_id'] == 'finance'
    assert client.put('/api/notebooks/' + ordinary['id'], json={'context_id': 'law'}).status_code == 422
    assert client.post('/api/notebooks', json={'name': 'Invalid', 'context_id': 'unknown'}).status_code == 422
    assert len(client.get('/api/notebooks').json()['contexts']) == 3


def test_cross_context_add_does_not_copy_but_explicit_copy_does(client):
    finance = book(client, 'Finance', 'finance')
    law = book(client, 'Law', 'law')
    original = client.post('/api/words', json={'word': 'security', 'definition': 'n. 证券', 'notebook_id': finance['id']}).json()['word']
    added = client.post('/api/words', json={'word': 'security', 'notebook_id': law['id']}).json()['word']
    assert added['definition'] == ''
    ordinary = client.post('/api/words', json={'word': 'security'}).json()['word']
    assert ordinary['definition'] == ''
    assert client.delete('/api/words/' + added['id']).status_code == 200
    copied = client.post('/api/words/copy', json={'word_ids': [original['id']], 'notebook_id': law['id']})
    assert copied.status_code == 200, copied.text
    assert next(w for w in app.load_words()['words'] if w['notebook_id'] == law['id'])['definition'] == original['definition']


@pytest.mark.parametrize('preset', contexts.PRESETS)
def test_context_survives_sync_without_new_fields(client, tmp_path, preset):
    created = book(client, preset, preset)
    data = app.load_words()
    operations = list(data['_sync']['operations'].values())
    sync_storage.validate_operations(operations)
    other = tmp_path / 'other.json'
    sync_storage.merge(other, operations)
    restored = next(b for b in sync_storage.read(other)['notebooks'] if b['id'] == created['id'])
    assert contexts.context_id(restored['id']) == preset
    assert set(restored) == {'id', 'name', 'description', 'created_at'}


@pytest.mark.parametrize('preset', contexts.PRESETS)
def test_worker_uses_selected_preset(client, monkeypatch, preset):
    created = book(client, 'Unrelated name', preset)
    wid = client.post('/api/words', json={'word': 'security', 'notebook_id': created['id']}).json()['word']['id']
    async def scenario():
        queue = asyncio.Queue()
        monkeypatch.setattr(app, '_enrich_queue', queue)
        monkeypatch.setattr(app, '_event_queue', asyncio.Queue())
        monkeypatch.setattr(app, '_enrich_post_check', lambda *args: (True, ''))
        async def generate(word, context):
            assert word == 'Security'
            assert context == contexts.prompt_for(created['id'])
            return '/test/', 'n. 测试', 'A security example.'
        monkeypatch.setattr(app, 'enrich_word', generate)
        queue.put_nowait((wid, 'Security'))
        task = asyncio.create_task(app._enrich_worker())
        try:
            await asyncio.wait_for(queue.join(), 3)
            assert app.get_word(wid)['word']['definition'] == 'n. 测试'
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    asyncio.run(scenario())


def test_restoring_deleted_context_book_keeps_context(client):
    created = book(client, 'Finance', 'finance')
    word = client.post('/api/words', json={'word': 'bond', 'definition': 'test', 'notebook_id': created['id']}).json()['word']
    exported = client.get('/api/words/export', params={'notebook_id': created['id']}).json()
    client.delete('/api/words/' + word['id'])
    client.delete('/api/notebooks/' + created['id'])
    assert client.post('/api/library/import', json=exported).status_code == 200
    restored = next(b for b in app.load_words()['notebooks'] if b['id'] != 'default')
    assert restored['id'] != created['id']
    assert contexts.context_id(restored['id']) == 'finance'


@pytest.mark.parametrize('provider', ['ollama', 'deepseek'])
def test_course_context_reaches_both_model_providers(monkeypatch, provider):
    real_client = httpx.AsyncClient
    seen = []
    def respond(request):
        payload = json.loads(request.content)
        prompt = payload['prompt'] if provider == 'ollama' else payload['messages'][0]['content']
        seen.append(prompt)
        result = json.dumps({'phonetic': '/test/', 'definition': 'n. 证券', 'example': 'A security is traded.'})
        return httpx.Response(200, json={'response': result} if provider == 'ollama' else {'choices': [{'message': {'content': result}}]})
    monkeypatch.setattr(app.config, 'get_provider', lambda: provider)
    monkeypatch.setattr(app.config, 'get_deepseek_config', lambda: {'api_key': 'synthetic', 'model': 'test'})
    monkeypatch.setattr(app.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    result = asyncio.run(app.enrich_word('Security', 'Finance: Bonds and markets'))
    assert result[1] == 'n. 证券'
    assert 'Domain guidance: Finance: Bonds and markets' in seen[0]
