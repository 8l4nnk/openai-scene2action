"""Advisory input screening. No execution or plan-generation capability."""
import math
import os
import time
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict


class GuardVerdict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    decision: Literal['PASS', 'BLOCK', 'HOLD']
    category: Literal['NORMAL', 'INJECTION', 'PHYSICAL_HAZARD', 'UNCERTAIN']


def build_messages(policy, mode, text, image):
    if mode not in ('TEXT', 'IMAGE', 'IMAGE_TEXT'):
        raise ValueError('Invalid input mode')
    if (mode == 'IMAGE' and text) or (mode != 'IMAGE' and not text.strip()):
        raise ValueError('Invalid text for input mode')
    if mode != 'TEXT' and (not image or not image.startswith('data:image/')):
        raise ValueError('A verified local image is required')
    content = []
    if mode != 'IMAGE':
        content.append({'type': 'text', 'text': text})
    if mode != 'TEXT':
        content.append({'type': 'image_url', 'image_url': {'url': image}})
    return [{'role': 'system', 'content': policy}, {'role': 'user', 'content': content}]


def endpoint_config(provider):
    if provider == 'openrouter':
        base, key = 'https://openrouter.ai/api/v1', os.getenv('OPENROUTER_API_KEY')
    elif provider == 'openai':
        base, key = 'https://api.openai.com/v1', os.getenv('OPENAI_API_KEY') or os.getenv('OPENAI_KEY')
    elif provider == 'runpod':
        base, key = os.getenv('S2A_RUNPOD_BASE_URL', ''), os.getenv('S2A_RUNPOD_API_KEY')
        parts = urlsplit(base)
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('Invalid inference URL')
        if not (parts.scheme == 'https' or (parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost'))):
            raise ValueError('Use HTTPS or an SSH tunnel to loopback')
    else:
        raise ValueError('Unknown provider')
    if not key:
        raise ValueError('Missing provider credential')
    return base.rstrip('/'), key


def classify(policy, mode, text, image, model, provider='openrouter', transport=None):
    started = time.perf_counter()
    result = dict(decision='HOLD', category='UNCERTAIN', error=None, usage=None)
    try:
        if not model or not policy.strip():
            raise ValueError('Explicit model and policy are required')
        body = dict(model=model, messages=build_messages(policy, mode, text, image),
                    max_tokens=1024, stream=False,
                    response_format={'type': 'json_schema', 'json_schema': {
                        'name': 'input_screen', 'strict': True, 'schema': GuardVerdict.model_json_schema()}})
        if provider == 'openai':
            body['max_completion_tokens'] = body.pop('max_tokens')
            body['reasoning_effort'] = 'low'
            body['store'] = False
        if provider == 'openrouter':
            body['provider'] = {'require_parameters': True, 'allow_fallbacks': False}
            # Qwen3-VL-32B-Instruct does not advertise reasoning support.
            # With require_parameters=True, sending it can prevent routing.
            if model == 'anthropic/claude-opus-5.5':
                body['reasoning'] = {'effort': 'low'}
        if transport is None:
            base, key = endpoint_config(provider)
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                response = client.post(base+'/chat/completions', json=body,
                                       headers={'Authorization': 'Bearer '+key})
                response.raise_for_status()
                data = response.json()
        else:
            data = transport(**body)
        choice = data['choices'][0]
        if choice['finish_reason'] != 'stop' or choice['message'].get('refusal'):
            raise ValueError('Incomplete or refused classification')
        verdict = GuardVerdict.model_validate_json(choice['message']['content'])
        if verdict.decision == 'PASS' and verdict.category != 'NORMAL':
            raise ValueError('Inconsistent classification')
        result.update(verdict.model_dump())
        # Only known numeric usage fields; never persist arbitrary provider output.
        result['usage'] = {k:v for k,v in (data.get('usage') or {}).items()
                           if k in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'cost')
                           and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)}
        result['response_model'] = data.get('model') if isinstance(data.get('model'),str) else None
    except httpx.HTTPStatusError as error:
        result.update(decision='HOLD', category='UNCERTAIN', error=f'HTTP_{error.response.status_code}')
    except httpx.TimeoutException:
        result.update(decision='HOLD', category='UNCERTAIN', error='MODEL_TIMEOUT')
    except (ValueError, KeyError, IndexError, TypeError):
        result.update(decision='HOLD', category='UNCERTAIN', error='INVALID_RESPONSE_OR_CONFIGURATION')
    except Exception:
        result.update(decision='HOLD', category='UNCERTAIN', error='MODEL_UNAVAILABLE')
    result['latency_ms'] = round((time.perf_counter()-started)*1000, 3)
    return result
