"""供应商目录及协议适配；不依赖真实用户配置。"""
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


async def complete(settings, prompt, *, json_output=False):
    protocol = settings['protocol']
    payload = {'model': settings['model'], 'stream': False}
    if protocol == 'ollama':
        path = '/api/generate'
        payload.update(prompt=prompt, format='json')
    else:
        path = '/messages' if protocol == 'anthropic' else '/chat/completions'
        payload['messages'] = [{'role': 'user', 'content': prompt}]
        if protocol == 'anthropic':
            payload['max_tokens'] = 2048
        elif settings.get('provider') == 'deepseek' and json_output:
            # Dictionary lookups should not inherit DeepSeek's default thinking mode.
            payload.update(thinking={'type': 'disabled'},
                           response_format={'type': 'json_object'}, max_tokens=2048)
    async with httpx.AsyncClient(timeout=settings.get('timeout', 120)) as client:
        response = await client.post(settings['base_url'] + path, json=payload, headers=headers(settings))
        response.raise_for_status()
        data = response.json()
    if protocol == 'ollama':
        return data['response'].strip()
    if protocol == 'anthropic':
        return '\n'.join(block['text'] for block in data['content'] if block.get('type') == 'text').strip()
    return data['choices'][0]['message']['content'].strip()
