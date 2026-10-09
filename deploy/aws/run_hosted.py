"""Run one hosted simulator process with root-managed runtime configuration."""
import json
import os
from pathlib import Path

import uvicorn

ALLOWED = {'S2A_PUBLIC_HOST', 'S2A_LOGIN_PASSWORD_SHA256', 'S2A_SESSION_SECRET',
           'S2A_INPUT_GUARD_PROVIDER', 'S2A_INPUT_GUARD_MODEL', 'OPENROUTER_API_KEY',
           'OPENAI_API_KEY', 'OPENAI_MODEL'}


if __name__ == '__main__':
    runtime = json.loads(Path('/etc/scene2action/runtime.json').read_text())
    if not set(runtime) <= ALLOWED or not all(isinstance(v, str) for v in runtime.values()):
        raise ValueError('Invalid runtime configuration')
    os.environ.update(runtime)
    os.environ['S2A_GEOMETRY_BACKEND'] = 'native'
    from scene2action.hosting import create_hosted_app
    uvicorn.run(create_hosted_app(), host='127.0.0.1', port=8765,
                proxy_headers=True, forwarded_allow_ips='127.0.0.1', access_log=False, workers=1)
