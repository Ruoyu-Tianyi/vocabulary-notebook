"""模拟三种协议，不调用真实模型或读取个人配置。"""
import asyncio
import json

import httpx
import pytest

import model_providers as providers


@pytest.mark.parametrize('provider,path,key,response', [
    ('openai', '/v1/chat/completions', 'Authorization', {'choices': [{'message': {'content': 'OK'}}]}),
    ('anthropic', '/v1/messages', 'x-api-key', {'content': [{'type': 'thinking'}, {'type': 'text', 'text': 'OK'}]}),
    ('ollama', '/api/generate', 'Authorization', {'response': 'OK'}),
])
def test_protocol_payload_and_response(monkeypatch, provider, path, key, response):
    original = httpx.AsyncClient
    def handle(request):
        assert request.url.path == path
        assert 'synthetic' in request.headers[key]
        body = json.loads(request.content)
        assert body['model'] == 'model'
        assert body['stream'] is False
        if provider == 'anthropic':
            assert body['max_tokens'] > 0
            assert request.headers['anthropic-version'] == '2023-06-01'
        if provider == 'ollama':
            assert body['prompt'] == 'hello'
            assert body['format'] == 'json'
        else:
            assert body['messages'][0]['content'] == 'hello'
        return httpx.Response(200, json=response)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    settings = providers.resolve(provider, {'model': 'model', 'api_key': 'synthetic'})
    assert asyncio.run(providers.complete(settings, 'hello')) == 'OK'


def test_ollama_discovery_and_legacy_url(monkeypatch):
    original = httpx.AsyncClient
    def handle(request):
        assert request.url.path == '/api/tags'
        return httpx.Response(200, json={'models': [{'name': 'local:8b'}, {'name': 'local:8b'}]})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    settings = providers.resolve('ollama', {'url': 'http://localhost:11434/api/generate/'})
    assert asyncio.run(providers.discover(settings)) == ['local:8b']


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'https://user:key@example.com', 'https://example.com?key=secret', 'http://', 'http://localhost:bad'])
def test_reject_credential_urls(url):
    with pytest.raises(ValueError):
        providers.normalize_url(url, 'openai')


def test_anthropic_pagination(monkeypatch):
    original = httpx.AsyncClient
    def handle(request):
        second = request.url.params.get('after_id') == 'first'
        return httpx.Response(200, json={'data': [{'id': 'second' if second else 'first'}],
                                        'has_more': not second, 'last_id': 'first'})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    assert asyncio.run(providers.discover(providers.resolve('anthropic', {'api_key': 'test'}))) == ['first', 'second']


@pytest.fixture(autouse=True)
def _reset_hint_cache():
    providers._HINTS_UNSUPPORTED.clear()
    yield
    providers._HINTS_UNSUPPORTED.clear()


@pytest.mark.parametrize('provider,json_output', [
    ('deepseek', True), ('deepseek', False), ('openai', True), ('custom', True), ('qwen', True),
])
@pytest.mark.parametrize('base_url', ['https://api.deepseek.com', 'https://gateway.example/v1'])
def test_dictionary_speed_options_follow_provider(monkeypatch, provider, json_output, base_url):
    original = httpx.AsyncClient
    seen = []

    def handle(request):
        body = json.loads(request.content)
        seen.append(body)
        assert str(request.url) == base_url + '/chat/completions'
        assert body['model'] == 'deepseek-flash'
        assert body['stream'] is False
        assert body['messages'] == [{'role': 'user', 'content': 'Return JSON'}]
        if not json_output:
            assert set(body) == {'model', 'stream', 'messages'}
        elif provider == 'deepseek':
            assert body['thinking'] == {'type': 'disabled'}
            assert body['response_format'] == {'type': 'json_object'}
            assert body['max_tokens'] == providers.DICTIONARY_MAX_TOKENS
        elif provider == 'openai':
            assert body['max_completion_tokens'] == providers.DICTIONARY_MAX_TOKENS
            assert 'max_tokens' not in body
        elif provider == 'qwen':
            assert body['enable_thinking'] is False
            assert body['max_tokens'] == providers.DICTIONARY_MAX_TOKENS
        else:
            # Custom APIs only receive the standard output limit, never vendor flags
            # chosen from a matching model name or host.
            assert set(body) == {'model', 'stream', 'messages', 'max_tokens'}
        return httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}]})

    monkeypatch.setattr(httpx, 'AsyncClient',
                        lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    settings = providers.resolve(provider, {'model': 'deepseek-flash', 'api_key': 'synthetic',
                                            'base_url': base_url, 'provider': 'deepseek'})
    assert settings['provider'] == provider
    assert asyncio.run(providers.complete(settings, 'Return JSON', json_output=json_output)) == 'OK'
    assert len(seen) == 1


def test_rejected_speed_options_fall_back_to_plain_request(monkeypatch):
    original = httpx.AsyncClient
    seen = []

    def handle(request):
        body = json.loads(request.content)
        seen.append(body)
        if 'max_tokens' in body:
            return httpx.Response(400, json={'error': 'unsupported parameter'})
        return httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}]})

    monkeypatch.setattr(httpx, 'AsyncClient',
                        lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    settings = providers.resolve('moonshot', {'model': 'm', 'api_key': 'synthetic'})
    assert asyncio.run(providers.complete(settings, 'JSON', json_output=True)) == 'OK'
    assert asyncio.run(providers.complete(settings, 'JSON', json_output=True)) == 'OK'
    # The unsupported model is remembered, so later lookups skip the failing attempt.
    assert ['max_tokens' in body for body in seen] == [True, False, False]


@pytest.mark.parametrize('provider,response,truncated', [
    ('deepseek', {'choices': [{'finish_reason': 'length', 'message': {'content': '{'}}]},
     {'choices': [{'finish_reason': 'stop', 'message': {'content': 'OK'}}]}),
    ('anthropic', {'stop_reason': 'max_tokens', 'content': [{'type': 'text', 'text': '{'}]},
     {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': 'OK'}]}),
    ('ollama', {'done_reason': 'length', 'response': '{'}, {'done_reason': 'stop', 'response': 'OK'}),
])
def test_truncated_lookup_retries_with_larger_limit(monkeypatch, provider, response, truncated):
    original = httpx.AsyncClient
    limits = []

    def handle(request):
        body = json.loads(request.content)
        limit = body['options']['num_predict'] if provider == 'ollama' else body['max_tokens']
        limits.append(limit)
        if provider == 'ollama':
            assert body['keep_alive'] and body['think'] is False
        return httpx.Response(200, json=response if len(limits) == 1 else truncated)

    monkeypatch.setattr(httpx, 'AsyncClient',
                        lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    settings = providers.resolve(provider, {'model': 'm', 'api_key': 'synthetic'})
    assert asyncio.run(providers.complete(settings, 'JSON', json_output=True)) == 'OK'
    assert limits == [providers.DICTIONARY_MAX_TOKENS, providers._RETRY_MAX_TOKENS]


def test_enrichment_requests_deepseek_dictionary_options(monkeypatch):
    import app

    original = httpx.AsyncClient
    seen = []

    def handle(request):
        body = json.loads(request.content)
        seen.append(body)
        assert request.url == 'https://api.deepseek.com/chat/completions'
        assert body['thinking'] == {'type': 'disabled'}
        assert body['response_format'] == {'type': 'json_object'}
        assert body['max_tokens'] == providers.DICTIONARY_MAX_TOKENS
        assert 'contract' in body['messages'][0]['content']
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({
            'phonetic': '/test/', 'definition': 'n. 合同', 'example': 'A contract.'
        })}}]})

    monkeypatch.setattr(app.config, 'get_provider', lambda: 'deepseek')
    monkeypatch.setattr(app.config, 'load_config', lambda: {
        'provider': 'deepseek', 'deepseek': {'model': 'deepseek-flash', 'api_key': 'synthetic'}
    })
    monkeypatch.setattr(httpx, 'AsyncClient',
                        lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    assert asyncio.run(app.enrich_word('contract')) == ('/test/', 'n. 合同', 'A contract.')
    assert len(seen) == 1
