"""A remote edit-and-revert still protects a new entry from automatic deletion."""
import asyncio
import pytest
import app
import sync_storage as storage


def test_remote_edit_then_revert_is_not_treated_as_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'DATA_FILE', tmp_path/'local.json')
    monkeypatch.setattr(app, '_new_enrichment_candidates', {})
    monkeypatch.setattr(app, '_enrich_states', {})
    monkeypatch.setattr(app, '_enriching_ids', {})
    async def scenario():
        monkeypatch.setattr(app, '_enrich_queue', asyncio.Queue())
        monkeypatch.setattr(app, '_event_queue', asyncio.Queue())
        wid=(await app.create_word({'word':'xyztypo'}))['word']['id']
        remote=tmp_path/'remote.json'
        storage.merge(remote,list(app.load_words()['_sync']['operations'].values()))
        data=storage.read(remote)
        data['words'][0]['definition']='n. 人工内容'
        storage.commit(remote,data)
        data=storage.read(remote)
        data['words'][0]['definition']=''
        storage.commit(remote,data)
        storage.merge(app.DATA_FILE,list(storage.read(remote)['_sync']['operations'].values()))
        before=app.DATA_FILE.read_bytes()
        async def empty(_word): return '', '', ''
        monkeypatch.setattr(app,'enrich_word',empty)
        worker=asyncio.create_task(app._enrich_worker())
        try:
            await asyncio.wait_for(app._enrich_queue.join(),2)
            assert app.DATA_FILE.read_bytes()==before
            assert app.get_word(wid)['word']['id']==wid
            assert not app._event_queue.get_nowait()['removed']
        finally:
            worker.cancel()
            with pytest.raises(asyncio.CancelledError): await worker
    asyncio.run(scenario())
