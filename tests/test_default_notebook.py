"""Default notebook fields remain usable even before they have explicit operations."""
import sync_storage as storage


def test_default_book_description_only_change_survives_materialization_and_sync(tmp_path):
    first, second = tmp_path/'first.json', tmp_path/'second.json'
    data = storage.read(first)
    data['notebooks'][0]['description'] = '合同法课程'
    result = storage.commit(first, data)
    assert result['notebooks'][0]['name'] == '默认单词本'
    storage.merge(second, list(result['_sync']['operations'].values()))
    assert storage.read(second)['notebooks'] == result['notebooks']
    assert storage.read(second)['notebooks'][0]['description'] == '合同法课程'


def test_explicit_default_name_is_preserved_on_later_description_changes(tmp_path):
    path = tmp_path/'words.json'
    data = storage.read(path)
    data['notebooks'][0]['name'] = '法律术语'
    storage.commit(path, data)
    data = storage.read(path)
    data['notebooks'][0]['description'] = '新课程说明'
    assert storage.commit(path, data)['notebooks'][0]['name'] == '法律术语'


def test_partial_cache_from_an_older_version_keeps_original_bytes_on_read(tmp_path):
    path = tmp_path/'words.json'
    storage.atomic_write(path, {'words': [], 'notebooks': [{'id': 'default', 'description': '法律'}], '_sync': storage.fresh()})
    before = path.read_bytes()
    assert storage.read(path)['notebooks'][0]['name'] == '默认单词本'
    assert path.read_bytes() == before
