"""仿真公开 API client：鉴权、轮询、path 下发、事件、启动仿真。

统一处理响应包络 {code,msg,data}、超时重试（X-Retry-Of）、频控退避（1005）、
提交类幂等（requestId）。只做 HTTP 层，返回 data 原文；解析交给 math_modeling。
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Optional

import requests


class SimulatorError(Exception):
    """仿真器返回非 0 错误码。"""

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
        agent_id: str = "",
        timeout: float = 6.0,
        max_retries: int = 3,
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
        h = {"X-Open-Token": self.token}
        if self.agent_id:
            h["X-Agent-Id"] = self.agent_id
        if retry_of:
            h["X-Retry-Of"] = retry_of
        return h

    def gen_request_id(self) -> str:
        """幂等 requestId：{agentId}-{YYYYMMddHHmmss}-{三位序号}。"""
        prefix = self.agent_id or "agent"
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
        retry_of: Optional[str] = None,
    ) -> Any:
        url = self.base_url + path
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
                # 超时重传：带上 X-Retry-Of 关联原请求
                if attempt < self.max_retries:
                    retry_of = retry_of or self.gen_request_id()
                    time.sleep(self.backoff_base * (2 ** attempt))
                    continue
                raise
            except requests.RequestException as exc:
                raise SimulatorError(2000, f"连接失败: {exc}") from exc

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
        params = {"type": type} if type else None
        return self._request("GET", "/topology", params=params)

    def get_nodes(
        self, type: Optional[str] = None, status: Optional[str] = None,
        page: Optional[int] = None, size: Optional[int] = None,
    ) -> dict:
        params = {}
        if type:
            params["type"] = type
        if status:
            params["status"] = status
        if page is not None:
            params["page"] = page
        if size is not None:
            params["size"] = size
        return self._request("GET", "/nodes", params=params)

    def get_node(self, node_id: str) -> dict:
        return self._request("GET", f"/nodes/{node_id}")

    def get_links(
        self, node_id: Optional[str] = None, status: Optional[str] = None,
        page: Optional[int] = None, size: Optional[int] = None,
    ) -> dict:
        params = {}
        if node_id:
            params["nodeId"] = node_id
        if status:
            params["status"] = status
        if page is not None:
            params["page"] = page
        if size is not None:
            params["size"] = size
        return self._request("GET", "/links", params=params)

    def get_link(self, link_id: str) -> dict:
        return self._request("GET", f"/links/{link_id}")

    def get_services(
        self, status: Optional[str] = None, node_id: Optional[str] = None,
        page: Optional[int] = None, size: Optional[int] = None,
    ) -> dict:
        params = {}
        if status:
            params["status"] = status
        if node_id:
            params["nodeId"] = node_id
        if page is not None:
            params["page"] = page
        if size is not None:
            params["size"] = size
        return self._request("GET", "/services", params=params)

    def get_service(self, service_id: str) -> dict:
        return self._request("GET", f"/services/{service_id}")

    def get_service_path(self, service_id: str) -> dict:
        return self._request("GET", f"/services/{service_id}/path")

    def get_events(self, since_ts_us: int = 0, limit: int = 100) -> dict:
        return self._request("GET", "/events", params={"sinceTsUs": since_ts_us, "limit": limit})

    def get_time(self) -> dict:
        return self._request("GET", "/time")

    # ------------------------------------------------------------------ 提交
    def set_service_path(
        self, service_id: str, src_node_id: str, dst_node_id: str,
        segments: list[dict], request_id: Optional[str] = None,
    ) -> dict:
        """segments: [{"type":"link","id":"L00201"}, ...]，必须连续贯通。"""
        body = {
            "requestId": request_id or self.gen_request_id(),
            "srcNodeId": src_node_id,
            "dstNodeId": dst_node_id,
            "segments": segments,
        }
        return self._request("POST", f"/services/{service_id}/path", json=body)

    def start_simulation(
        self, suite_id: str, scenario_id: str, script_id: str,
        request_id: Optional[str] = None,
    ) -> dict:
        body = {
            "requestId": request_id or self.gen_request_id(),
            "suiteId": suite_id,
            "scenarioId": scenario_id,
            "scriptId": script_id,
        }
        return self._request("POST", "/simulation/start", json=body)
