#!/usr/bin/env bash
# Work Bench 后端一键启动。
# 默认从 simulator/conf/gateway.json 读取 ctrlToken（仿真器前端同款通道，调用不计入 agent 统计）；
# 只有找不到 ctrlToken 时才退回公开令牌，并在启动日志里明确标注 SIM_AUTH=open。
# 令牌只进进程环境，不打印、不落盘。
set -euo pipefail
cd "$(dirname "$0")/.."   # 进入 work_bench/

if [ -z "${SIM_CTRL_TOKEN:-}" ] && [ -z "${SIM_TOKEN:-}" ] && [ -z "${SIM_TOKEN_FILE:-}" ]; then
  # 均未提供时才自动探测 gateway.json（若设置了 SIM_TOKEN_FILE，交由 config.py 读取）
  GW="${SIM_GATEWAY_JSON:-$(pwd)/../simulator/conf/gateway.json}"
  if [ -f "$GW" ]; then
    read -r AUTH TOKEN < <(python3 - "$GW" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("none ")
    raise SystemExit(0)
ctrl = str(d.get("ctrlToken") or "")
opens = d.get("openTokens") or []
if ctrl:
    print("ctrl", ctrl)
elif opens:
    print("open", str(opens[0]))
else:
    print("none ")
PY
)
    case "$AUTH" in
      ctrl) export SIM_CTRL_TOKEN="$TOKEN" ;;
      open)
        export SIM_AUTH=open
        export SIM_TOKEN="$TOKEN"
        echo "[workbench] gateway.json 无 ctrlToken，降级使用公开令牌（调用会计入 agent 统计）" >&2
        ;;
    esac
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
