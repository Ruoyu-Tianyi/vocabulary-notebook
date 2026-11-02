"""Course changes cannot receive or delete data using an obsolete AI response."""
import asyncio

import pytest

import app


@pytest.mark.parametrize('change', ['none', 'move', 'name', 'description', 'undo'])
@pytest.mark.parametrize('empty', [False, True])
def test_course_snapshot_guards_writeback_and_cleanup(tmp_path, monkeypatch, change, empty):
    monkeypatch.setattr(app, 'DATA_FILE', tmp_path / 'words.json')
    for name in ('_new_enrichment_candidates', '_enrich_states', '_enriching_ids'):
        monkeypatch.setattr(app, name, {})
    monkeypatch.setattr(app, '_enrich_post_check', lambda *args: (True, ''))
    async def scenario():
        queue = asyncio.Queue()
        monkeypatch.setattr(app, '_enrich_queue', queue)
        monkeypatch.setattr(app, '_event_queue', asyncio.Queue())
        book = app.create_notebook({'name': 'Finance', 'description': 'Bonds and markets'})
        created = await app.create_word({'word': 'security', 'notebook_id': book['id']})
        wid = created['word']['id']
        async def generate(word):
            if change == 'move':
                app.update_word(wid, {'notebook_id': 'default'})
            elif change == 'name':
                app.update_notebook(book['id'], {'name': 'Law'})
            elif change == 'description':
                app.update_notebook(book['id'], {'description': 'Contract law'})
            elif change == 'undo':
                app.update_notebook(book['id'], {'name': 'Law'})
                app.update_notebook(book['id'], {'name': 'Finance'})
            return ('', '', '') if empty else ('/test/', 'n. 证券', 'A security is traded.')
        monkeypatch.setattr(app, 'enrich_word', generate)
        task = asyncio.create_task(app._enrich_worker())
        try:
            await asyncio.wait_for(queue.join(), 3)
            words = app.load_words()['words']
            if empty and change == 'none':
                assert not words
            else:
                assert len(words) == 1
                assert words[0]['definition'] == ('n. 证券' if change == 'none' else '')
            if change != 'none':
                assert app._enrich_states[wid]['status'] == 'failed'
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    asyncio.run(scenario())
