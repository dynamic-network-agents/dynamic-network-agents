#!/usr/bin/env bash
# Work Bench 后端一键启动：自动从 simulator/conf/gateway.json 读取公开令牌（不打印、不落盘）。
set -euo pipefail
cd "$(dirname "$0")/.."   # 进入 work_bench/

if [ -z "${SIM_TOKEN:-}" ] && [ -z "${SIM_TOKEN_FILE:-}" ]; then
  # 均未提供时才自动探测 gateway.json（若设置了 SIM_TOKEN_FILE，交由 config.py 读取）
  GW="${SIM_GATEWAY_JSON:-$(pwd)/../simulator/conf/gateway.json}"
  if [ -f "$GW" ]; then
    SIM_TOKEN="$(python3 - "$GW" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))['openTokens'][0])
PY
)"
    export SIM_TOKEN
  fi
fi

PY="${WORKBENCH_PYTHON:-backend/.venv/bin/python}"
if [ ! -x "$PY" ]; then
  PY="python3"
fi

exec "$PY" -m uvicorn backend.main:app \
  --host "${WORKBENCH_HOST:-127.0.0.1}" \
  --port "${WORKBENCH_PORT:-8000}" \
  "$@"
