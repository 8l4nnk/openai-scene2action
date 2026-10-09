#!/bin/bash
set -euo pipefail
# Arguments are fixed generated names, never operator/model input.
bucket="$1"
release_key="$2"
runtime_key="$3"
region=ap-southeast-2
dnf install -y python3.12 python3.12-pip gcc-c++ nginx awscli-2
id s2a >/dev/null 2>&1 || useradd --system --home-dir /opt/scene2action --shell /sbin/nologin s2a
install -d -m 755 /opt/scene2action/current
install -d -m 750 -o root -g s2a /etc/scene2action
aws s3 cp "s3://${bucket}/${release_key}" /tmp/scene2action-release.tar.gz --region "$region" --only-show-errors
tar -xzf /tmp/scene2action-release.tar.gz -C /opt/scene2action/current
cd /opt/scene2action/current
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r deploy/aws/requirements.txt
.venv/bin/python scripts/build_native.py --compiler /usr/bin/g++
install -d -m 750 -o s2a -g s2a .data
chown -R s2a:s2a .data
aws s3 cp "s3://${bucket}/${runtime_key}" /etc/scene2action/runtime.json --region "$region" --only-show-errors
chown root:s2a /etc/scene2action/runtime.json
chmod 640 /etc/scene2action/runtime.json
.venv/bin/python - <<'PY'
import json
import re
from pathlib import Path
host = json.loads(Path('/etc/scene2action/runtime.json').read_text())['S2A_PUBLIC_HOST']
if not re.fullmatch(r'[a-z0-9-]+\.cloudfront\.net', host):
    raise ValueError('Invalid public host')
config = '''server {
  listen 80 default_server;
  server_name _;
  client_max_body_size 16k;
  location / {
    proxy_pass http://127.0.0.1:8765;
    proxy_set_header Host PUBLIC_HOST;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-For $http_x_forwarded_for;
    proxy_read_timeout 120s;
    proxy_buffering off;
  }
}'''
Path('/etc/nginx/conf.d/scene2action.conf').write_text(config.replace('PUBLIC_HOST', host))
PY
# AL2023's package includes a default server; use an explicit minimal main configuration.
cat > /etc/nginx/nginx.conf <<'NGINX'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;
events { worker_connections 1024; }
http {
  include /etc/nginx/mime.types;
  default_type application/octet-stream;
  access_log off;
  sendfile on;
  include /etc/nginx/conf.d/scene2action.conf;
}
NGINX
cat > /etc/systemd/system/scene2action.service <<'UNIT'
[Unit]
Description=Scene2Action authenticated simulation workbench
After=network-online.target
Wants=network-online.target
[Service]
User=s2a
Group=s2a
WorkingDirectory=/opt/scene2action/current
ExecStart=/opt/scene2action/current/.venv/bin/python -m deploy.aws.run_hosted
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/scene2action/current/.data
UMask=0027
[Install]
WantedBy=multi-user.target
UNIT
nginx -t
systemctl daemon-reload
systemctl enable --now scene2action nginx
echo 'Scene2Action services started'
