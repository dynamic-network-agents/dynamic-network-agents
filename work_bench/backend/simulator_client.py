"""仿真 API client（work_bench 独立实现，不 import src）。

统一处理响应包络 {code,msg,data}、超时、频控退避（1005）、提交幂等（requestId）。
鉴权头由 auth_mode 决定：
- `ctrl`（默认）→ `X-Ctrl-Token`，与仿真器官方前端同一条账本（front_stat），不计入 agent 调用统计；
- `open`         → `X-Open-Token`，会计入 agent 调用统计（仅供显式降级）。
只暴露查询 GET 与唯一的写接口 set_service_path；日志/异常信息均不含 Token。
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Optional

import requests

AUTH_CTRL = "ctrl"
AUTH_OPEN = "open"
_HEADERS = {AUTH_CTRL: "X-Ctrl-Token", AUTH_OPEN: "X-Open-Token"}


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
        auth_mode: str = AUTH_CTRL,
        *,
        ctrl_base_url: str = "",
        agent_id: str = "workbench",
        timeout: float = 6.0,
        max_retries: int = 2,
        backoff_base: float = 0.5,
    ):
        if auth_mode not in _HEADERS:
            raise ValueError(f"auth_mode 只支持 ctrl/open，收到 {auth_mode!r}")
        self.base_url = base_url.rstrip("/")
        self.ctrl_base_url = (ctrl_base_url or "").rstrip("/")
        self.token = token
        self.auth_mode = auth_mode
        self.agent_id = agent_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._req_seq = 0

    # ------------------------------------------------------------------ 基础
    @property
    def header_name(self) -> str:
        return _HEADERS[self.auth_mode]

    @property
    def svc_meta_available(self) -> bool:
        return bool(self.ctrl_base_url)

    def _headers(self, retry_of: Optional[str] = None) -> dict[str, str]:
        headers = {self.header_name: self.token}
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
        base: Optional[str] = None,
    ) -> Any:
        url = (base or self.base_url) + path
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

    def get_links_all(
        self, page_size: int = 500, max_pages: int = 20
    ) -> tuple[list[dict], int, bool]:
        """分页取全链路（仿真器 page/size，默认单页 500）。"""
        return self._get_all_pages("/links", "links", page_size, max_pages)

    def get_services_all(
        self, page_size: int = 500, max_pages: int = 20
    ) -> tuple[list[dict], int, bool]:
        """分页取全业务（列表元素不含 actual，实测值要逐条取详情）。"""
        return self._get_all_pages("/services", "services", page_size, max_pages)

    def _get_all_pages(
        self, path: str, key: str, page_size: int, max_pages: int
    ) -> tuple[list[dict], int, bool]:
        items: list[dict] = []
        pages = 0
        complete = False
        page = 1
        size = max(1, min(2000, int(page_size)))
        while page <= max_pages:
            data = self._request("GET", path, params={"page": page, "size": size})
            chunk = (data or {}).get(key) or []
            items.extend(chunk)
            pages += 1
            if len(chunk) < size:
                complete = True
                break
            page += 1
        return items, pages, complete

    def get_service(self, service_id: str) -> dict:
        return self._request("GET", f"/services/{service_id}")

    def get_events(self, since_ts_us: int = 0, limit: int = 500) -> dict:
        return self._request(
            "GET", "/events", params={"sinceTsUs": since_ts_us, "limit": limit}
        )

    def get_time(self) -> dict:
        return self._request("GET", "/time")

    def get_svc_meta(self) -> dict[str, dict]:
        """控制面接口：{serviceId: {category, serviceType, startAtSec}}。

        公开 API 会显式删掉 category（openapi.py 的 `it.pop('category')`），
        这张表是仿真器运行时的真值，用于替代离线 bg-service.json 分类。
        """
        if not self.svc_meta_available:
            raise SimulatorError(1003, "未配置控制面基址（SIM_CTRL_BASE_URL）")
        data = self._request("GET", "/svc-meta", base=self.ctrl_base_url)
        meta = (data or {}).get("meta") if isinstance(data, dict) else None
        return meta if isinstance(meta, dict) else {}

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
