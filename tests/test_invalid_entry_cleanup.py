"""Only unchanged new entries rejected by the model may be auto-removed."""
import asyncio
import copy
import json
import httpx
import pytest
import app
import sync_storage as storage


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'DATA_FILE', tmp_path / 'words.json')
    monkeypatch.setattr(app, '_new_enrichment_candidates', {})
    monkeypatch.setattr(app, '_enrich_jobs', {})
    monkeypatch.setattr(app, '_enriching_ids', {})
    monkeypatch.setattr(app.config, 'get_ai_settings', lambda: {'configured': True})
    monkeypatch.setattr(app, '_enrich_post_check', lambda *args: (True, ''))
    return tmp_path


@pytest.mark.parametrize('change', ['none', 'edit', 'edit-back', 'move', 'review', 'course', 'old', 'restart'])
def test_empty_model_reply_removes_only_unchanged_new_word(isolated, monkeypatch, change):
    async def scenario():
        queue, events = asyncio.Queue(), asyncio.Queue()
        entered, release = asyncio.Event(), asyncio.Event()
        monkeypatch.setattr(app, '_enrich_queue', queue)
        monkeypatch.setattr(app, '_event_queue', events)
        async def empty(*args):
            entered.set()
            await release.wait()
            return '', '', ''
        monkeypatch.setattr(app, 'enrich_word', empty)
        created = await app.create_word({'word': 'xyzabc'})
        word_id = created['word']['id']
        baseline = copy.deepcopy(app.load_words())
        if change in ('old', 'restart'):
            app._new_enrichment_candidates.clear()
        task = asyncio.create_task(app._enrich_worker())
        try:
            await asyncio.wait_for(entered.wait(), 2)
            if change in ('edit', 'edit-back'):
                app.update_word(word_id, {'definition': 'n. 人工释义'})
                if change == 'edit-back':
                    app.update_word(word_id, {'definition': ''})
            elif change == 'move':
                book = app.create_notebook({'name': '法律'})['notebook']['id']
                app.update_word(word_id, {'notebook_id': book})
            elif change == 'review':
                data = app.load_words()
                data['words'][0]['review_history'] = [{'id': 'review', 'rating': 3, 'at': '2026-10-18T00:00:00Z'}]
                app.save_words(data)
            elif change == 'course':
                app.update_notebook('default', {'name': '合同法'})
            before = app.DATA_FILE.read_bytes()
            release.set()
            await asyncio.wait_for(queue.join(), 2)
            event = events.get_nowait()
            assert event['removed'] is (change == 'none')
            if change == 'none':
                assert app.load_words()['words'] == []
                assert app._enrich_jobs[word_id]['status'] == 'removed'
                # A stale offline device cannot restore the entry, in either merge order.
                remote = isolated / 'second.json'
                storage.atomic_write(remote, baseline)
                storage.merge(remote, list(app.load_words()['_sync']['operations'].values()))
                assert storage.read(remote)['words'] == []
                storage.merge(app.DATA_FILE, list(baseline['_sync']['operations'].values()))
                assert app.load_words()['words'] == []
            else:
                assert app.DATA_FILE.read_bytes() == before
                assert len(app.load_words()['words']) == 1
            assert word_id not in app._new_enrichment_candidates
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    asyncio.run(scenario())


@pytest.mark.parametrize('outcome', ['network', '401', '402', '429', '500', 'bad-json', 'missing-fields', 'empty', 'valid'])
def test_provider_failures_never_trigger_cleanup(isolated, monkeypatch, outcome):
    real_client = httpx.AsyncClient
    def response(request):
        if outcome == 'network':
            raise httpx.ConnectError('test offline', request=request)
        if outcome.isdigit():
            return httpx.Response(int(outcome), json={'error': 'test failure'})
        content = {'bad-json': 'invalid', 'missing-fields': '{}', 'empty': json.dumps(dict(phonetic='', definition='', example='')),
                   'valid': json.dumps(dict(phonetic='/x/', definition='n. 测试', example='A valid example.'))}[outcome]
        return httpx.Response(200, json={'choices': [{'message': {'content': content}}]})
    monkeypatch.setattr(app.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(response), **kw))
    monkeypatch.setattr(app.config, 'get_deepseek_config', lambda: {'api_key': 'fake-test-key', 'model': 'test'})
    async def scenario():
        queue, events = asyncio.Queue(), asyncio.Queue()
        monkeypatch.setattr(app, '_enrich_queue', queue)
        monkeypatch.setattr(app, '_event_queue', events)
        created = await app.create_word({'word': 'contract'})
        task = asyncio.create_task(app._enrich_worker())
        try:
            await asyncio.wait_for(queue.join(), 2)
            words = app.load_words()['words']
            event = events.get_nowait()
            if outcome == 'empty':
                assert not words and event['removed'] is True
            else:
                assert len(words) == 1
                if outcome == 'valid':
                    assert words[0]['definition'] == 'n. 测试'
                else:
                    assert event['removed'] is False
                    assert app.get_word(created['word']['id'])['enrichment']['status'] == 'failed'
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    asyncio.run(scenario())
