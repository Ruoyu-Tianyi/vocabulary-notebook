"""供应商目录及协议适配；不依赖真实用户配置。"""
import asyncio
import os
from urllib.parse import urlsplit

import httpx


# 地址是 API 根路径；模型目录以服务端返回为准，避免固定过期模型。
_ROWS = [
    ('ollama', 'Ollama', 'http://localhost:11434', 'ollama', 'OLLAMA_API_KEY'),
    ('deepseek', 'DeepSeek', 'https://api.deepseek.com', 'openai', 'DEEPSEEK_API_KEY'),
    ('openai', 'OpenAI', 'https://api.openai.com/v1', 'openai', 'OPENAI_API_KEY'),
    ('anthropic', 'Anthropic / Claude', 'https://api.anthropic.com/v1', 'anthropic', 'ANTHROPIC_API_KEY'),
    ('gemini', 'Google Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', 'openai', 'GEMINI_API_KEY'),
    ('qwen', '通义千问 / 百炼', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'openai', 'DASHSCOPE_API_KEY'),
    ('moonshot', 'Kimi / Moonshot', 'https://api.moonshot.cn/v1', 'openai', 'MOONSHOT_API_KEY'),
    ('zhipu', '智谱 GLM', 'https://open.bigmodel.cn/api/paas/v4', 'openai', 'ZHIPU_API_KEY'),
    ('siliconflow', '硅基流动', 'https://api.siliconflow.cn/v1', 'openai', 'SILICONFLOW_API_KEY'),
    ('openrouter', 'OpenRouter', 'https://openrouter.ai/api/v1', 'openai', 'OPENROUTER_API_KEY'),
    ('groq', 'Groq', 'https://api.groq.com/openai/v1', 'openai', 'GROQ_API_KEY'),
    ('mistral', 'Mistral AI', 'https://api.mistral.ai/v1', 'openai', 'MISTRAL_API_KEY'),
    ('together', 'Together AI', 'https://api.together.ai/v1', 'openai', 'TOGETHER_API_KEY'),
    ('fireworks', 'Fireworks AI', 'https://api.fireworks.ai/inference/v1', 'openai', 'FIREWORKS_API_KEY'),
    ('xai', 'xAI / Grok', 'https://api.x.ai/v1', 'openai', 'XAI_API_KEY'),
    ('custom', '自定义 API', '', 'openai', ''),
]
PROVIDERS = {p: dict(id=p, name=n, base_url=u, protocol=t, env_key=e) for p, n, u, t, e in _ROWS}


def normalize_url(url, protocol):
    url = url.strip().rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('API 地址必须是有效的 HTTP(S) 地址，不能包含账号、查询参数或片段')
    try:
        parsed.port
    except ValueError:
        raise ValueError('API 地址端口无效') from None
    suffixes = ('/api/generate', '/api/chat', '/api/tags') if protocol == 'ollama' else ('/chat/completions', '/messages', '/models')
    for suffix in suffixes:
        if url.endswith(suffix):
            url = url[:-len(suffix)]
            break
    return url


def resolve(provider, values):
    preset = PROVIDERS[provider]
    protocol = values.get('protocol', preset['protocol']) if provider == 'custom' else preset['protocol']
    if protocol not in ('openai', 'anthropic', 'ollama'):
        raise ValueError('不支持的 API 协议')
    key = values.get('api_key', '').strip() or os.environ.get(preset['env_key'], '').strip()
    return {**values, 'provider': provider, 'protocol': protocol,
            'base_url': normalize_url(values.get('base_url') or values.get('url') or preset['base_url'], protocol),
            'api_key': key}


def headers(settings):
    key = settings.get('api_key')
    if settings['protocol'] == 'anthropic':
        return {'x-api-key': key, 'anthropic-version': '2023-06-01'} if key else {}
    return {'Authorization': f'Bearer {key}'} if key else {}


async def discover(settings):
    protocol = settings['protocol']
    path = '/api/tags' if protocol == 'ollama' else '/models'
    models = set()
    params = {}
    async with httpx.AsyncClient(timeout=15) as client:
        # Anthropic 目录分页；设置上限避免异常网关无限循环。
        for _ in range(20):
            response = await client.get(settings['base_url'] + path, headers=headers(settings), params=params)
            response.raise_for_status()
            data = response.json()
            rows = data['models'] if protocol == 'ollama' else data['data']
            for item in rows:
                name = item.get('name' if protocol == 'ollama' else 'id')
                if isinstance(name, str) and name:
                    models.add(name)
            if protocol != 'anthropic' or not data.get('has_more'):
                break
            cursor = data.get('last_id')
            if not cursor or params.get('after_id') == cursor:
                raise ValueError('invalid model pagination')
            params = {'after_id': cursor}
    return sorted(models)


# 词典查询输出很短（一般 < 400 token），限制长度并关闭推理可显著缩短等待。
DICTIONARY_MAX_TOKENS = 1024
_RETRY_MAX_TOKENS = 2048
# 本地模型常驻内存，避免每次查词都重新加载。
OLLAMA_KEEP_ALIVE = '30m'
# 供应商拒绝提速参数时回退到最简请求，并记住该模型以免重复失败。
_HINTS_UNSUPPORTED = set()
_client_state = {}


def _client():
    """复用连接（keep-alive），省去每次查词的 TCP/TLS 握手。"""
    loop = asyncio.get_running_loop()
    factory = httpx.AsyncClient
    if (_client_state.get('loop') is not loop or _client_state.get('factory') is not factory
            or _client_state['client'].is_closed):
        _client_state.update(loop=loop, factory=factory, client=factory(timeout=120))
    return _client_state['client']


def _speed_hints(settings, max_tokens):
    """仅用于词典查询的提速参数；各供应商只发送其文档化的字段。"""
    provider = settings.get('provider')
    protocol = settings['protocol']
    model = str(settings.get('model', '')).lower()
    if protocol == 'ollama':
        return {'think': False, 'options': {'num_predict': max_tokens, 'temperature': 0}}
    if protocol == 'anthropic':
        return {'temperature': 0, 'thinking': {'type': 'disabled'}}
    if provider == 'deepseek':
        return {'thinking': {'type': 'disabled'}, 'response_format': {'type': 'json_object'},
                'max_tokens': max_tokens}
    if provider == 'openai':
        hints = {'max_completion_tokens': max_tokens, 'response_format': {'type': 'json_object'}}
        if model.startswith(('o1', 'o3', 'o4', 'gpt-5')):
            hints['reasoning_effort'] = 'low'
        else:
            hints['temperature'] = 0
        return hints
    hints = {'max_tokens': max_tokens}
    if provider == 'custom':
        return hints
    hints['temperature'] = 0
    if provider in ('qwen', 'siliconflow'):
        hints['enable_thinking'] = False
    elif provider == 'zhipu':
        hints['thinking'] = {'type': 'disabled'}
    elif provider == 'gemini':
        hints['reasoning_effort'] = 'none'
    return hints


def _truncated(protocol, data):
    if protocol == 'ollama':
        return data.get('done_reason') == 'length'
    if protocol == 'anthropic':
        return data.get('stop_reason') == 'max_tokens'
    return (data.get('choices') or [{}])[0].get('finish_reason') == 'length'


async def complete(settings, prompt, *, json_output=False):
    protocol = settings['protocol']
    payload = {'model': settings['model'], 'stream': False}
    if protocol == 'ollama':
        path = '/api/generate'
        payload.update(prompt=prompt, format='json', keep_alive=OLLAMA_KEEP_ALIVE)
    else:
        path = '/messages' if protocol == 'anthropic' else '/chat/completions'
        payload['messages'] = [{'role': 'user', 'content': prompt}]
        if protocol == 'anthropic':
            payload['max_tokens'] = DICTIONARY_MAX_TOKENS if json_output else 2048
    key = (settings.get('provider'), settings['base_url'], settings['model'])
    use_hints = json_output and key not in _HINTS_UNSUPPORTED
    max_tokens = DICTIONARY_MAX_TOKENS
    client = _client()
    timeout = settings.get('timeout', 120)
    for _ in range(3):
        body = {**payload, **(_speed_hints(settings, max_tokens) if use_hints else {})}
        if protocol == 'anthropic' and use_hints:
            body['max_tokens'] = max_tokens
        response = await client.post(settings['base_url'] + path, json=body,
                                     headers=headers(settings), timeout=timeout)
        if use_hints and response.status_code in (400, 422):
            # 兼容不支持提速参数的模型或网关：改用最简请求重试一次。
            _HINTS_UNSUPPORTED.add(key)
            use_hints = False
            continue
        response.raise_for_status()
        data = response.json()
        if use_hints and max_tokens < _RETRY_MAX_TOKENS and _truncated(protocol, data):
            # 极少数多义词释义较长：被截断时放宽一次长度限制。
            max_tokens = _RETRY_MAX_TOKENS
            continue
        break
    if protocol == 'ollama':
        return data['response'].strip()
    if protocol == 'anthropic':
        return '\n'.join(block['text'] for block in data['content'] if block.get('type') == 'text').strip()
    return data['choices'][0]['message']['content'].strip()
