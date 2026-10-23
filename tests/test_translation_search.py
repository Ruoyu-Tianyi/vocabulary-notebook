from tests.local_client import TestClient
import app
import copy
import pytest

@pytest.fixture
def client(monkeypatch):
    data = {'notebooks': [{'id':'default','name':'默认'}, {'id':'finance','name':'金融'}], 'words': [
        {'id':'1','word':'Contract','definition':'n. 合同；契约','created_at':'2026-10-22T00:00:00Z','notebook_id':'default'},
        {'id':'2','word':'Covenant','definition':'n. 合同中的承诺条款','created_at':'2026-10-23T00:00:00Z','notebook_id':'default'},
        {'id':'3','word':'Bond','definition':'n. 合同债券','created_at':'2026-10-23T00:00:00Z','notebook_id':'finance'},
        {'id':'4','word':'Pending','definition':'','created_at':'2026-10-23T00:00:00Z','notebook_id':'default'}]}
    monkeypatch.setattr(app, 'load_words', lambda: copy.deepcopy(data))
    return TestClient(app.app)

def test_chinese_search_before_pagination_and_export(client):
    params = {'q':'  合同　','notebook_id':'default','sort':'created_desc','size':1}
    result = client.get('/api/words', params=params).json()
    assert result['total'] == 2
    assert result['words'][0]['word'] == 'Covenant'
    assert result['available_letters'] == ['c']
    params['page'] = 2
    assert client.get('/api/words', params=params).json()['words'][0]['word'] == 'Contract'
    exported = client.get('/api/words/export', params={'q':' 合同 ', 'notebook_id':'default', 'format':'json'}).json()
    assert {w['word'] for w in exported['words']} == {'Contract','Covenant'}

@pytest.mark.parametrize('query', ['contract', ' CONTRACT ', 'ＣＯＮＴＲＡＣＴ'])
def test_english_normalization(client, query):
    result = client.get('/api/words', params={'q':query}).json()
    assert [w['word'] for w in result['words']] == ['Contract']

def test_search_keeps_notebook_and_date_scopes(client):
    result = client.get('/api/words', params={'q':'合同','notebook_id':'default','date':'2026-10-22'}).json()
    assert [w['word'] for w in result['words']] == ['Contract']
    assert client.get('/api/words',params={'q':'不存在的释义'}).json()['total'] == 0
    assert client.get('/api/words',params={'q':'　 '}).json()['total'] == 4
