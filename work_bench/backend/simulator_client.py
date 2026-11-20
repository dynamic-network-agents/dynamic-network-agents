"""仿真公开 API client（work_bench 独立实现，不 import src）。

统一处理响应包络 {code,msg,data}、超时、频控退避（1005）、提交幂等（requestId）。
只暴露查询 GET 与唯一的写接口 set_service_path；日志/异常信息均不含 Token。
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Optional

import requests


class SimulatorError(Exception):
    """仿真器返回非 0 错误码或连接失败。"""

    def __init__(self, code: int, msg: str, envelope: Optional[dict] = None):
        self.code = code
        self.msg = msg
        self.envelope = envelope
        super().__init__(f"simulator error {code}: {msg}")


class SimulatorClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        agent_id: str = "workbench",
        timeout: float = 6.0,
        max_retries: int = 2,
        backoff_base: float = 0.5,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.agent_id = agent_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._req_seq = 0

    # ------------------------------------------------------------------ 基础
    def _headers(self, retry_of: Optional[str] = None) -> dict[str, str]:
        headers = {"X-Open-Token": self.token}
        if self.agent_id:
            headers["X-Agent-Id"] = self.agent_id
        if retry_of:
            headers["X-Retry-Of"] = retry_of
        return headers

    def gen_request_id(self) -> str:
        prefix = self.agent_id or "workbench"
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        seq = self._req_seq
        self._req_seq += 1
        return f"{prefix}-{ts}-{seq:03d}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Any:
        url = self.base_url + path
        retry_of: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.request(
                    method,
                    url,
                    headers=self._headers(retry_of),
                    params=params,
                    json=json,
                    timeout=self.timeout,
                )
            except requests.Timeout:
                if attempt < self.max_retries:
                    retry_of = retry_of or self.gen_request_id()
                    time.sleep(self.backoff_base * (2 ** attempt))
                    continue
                raise SimulatorError(2000, "请求超时") from None
            except requests.RequestException as exc:
                raise SimulatorError(2000, f"连接失败: {type(exc).__name__}") from exc

            try:
                envelope = resp.json()
            except ValueError:
                raise SimulatorError(2000, f"非 JSON 响应: {resp.status_code}") from None

            code = envelope.get("code")
            if code == 0:
                return envelope.get("data")
            if code == 1005:  # 频控：退避重试
                if attempt < self.max_retries:
                    time.sleep(self.backoff_base * (2 ** attempt))
                    continue
            raise SimulatorError(code, envelope.get("msg", ""), envelope)

        raise SimulatorError(1005, "频控重试次数耗尽")

    # ------------------------------------------------------------------ 查询
    def get_topology(self, type: Optional[str] = None) -> dict:
        return self._request("GET", "/topology", params={"type": type} if type else None)

    def get_links(self) -> dict:
        return self._request("GET", "/links")

    def get_services(self) -> dict:
        return self._request("GET", "/services")

    def get_service(self, service_id: str) -> dict:
        return self._request("GET", f"/services/{service_id}")

    def get_events(self, since_ts_us: int = 0, limit: int = 500) -> dict:
        return self._request(
            "GET", "/events", params={"sinceTsUs": since_ts_us, "limit": limit}
        )

    def get_time(self) -> dict:
        return self._request("GET", "/time")

    # ------------------------------------------------------------------ 唯一写接口
    def set_service_path(
        self, service_id: str, src_node_id: str, dst_node_id: str, segments: list[dict],
    ) -> dict:
        body = {
            "requestId": self.gen_request_id(),
            "srcNodeId": src_node_id,
            "dstNodeId": dst_node_id,
            "segments": segments,
        }
        return self._request("POST", f"/services/{service_id}/path", json=body)
