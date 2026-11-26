"""ISS-0003 运行时验证：service 级入口 vs flow 级生效/校验。

固定用例（sce20261010-conf02/sce01）：

- flow：UAV0001 <-> UAV0002
- 下发目标：TSV0005（test / data）
- 同 flow 兄弟：BGV0009（background / video）、BGV0020（background / voice）
- 候选路径：L00019 -> L00011 -> L00010 -> L00009 -> L00015 -> L00017

验证四条：
  C1 同 flow 多条业务 GET .../path 返回同一路径；
  C2 只对 TSV0005 POST .../path，三条业务路径一起变，且 pathId/source 一致；
  C3 候选路径对 TSV0005 静态可行、对 BGV0009/BGV0020 的 jitter 静态违规，
     平台仍返回 accepted（说明受理校验只覆盖目标业务）；
  C4 兄弟业务实测回退为软观察，不作为硬断言（实测抖动会波动）。

运行（需 netsim/tx/rx 已启动，sce01 业务处于 running）：

    uv run pytest tests/integration/test_iss0003_flow_path_contract.py -s

测试结束会用基线路径恢复 flow；恢复失败会打印 WARNING。
"""
from __future__ import annotations

import json
import time
from typing import Any

import pytest
import requests

from common.simulator.client import SimulatorClient
from common.modeling.models import LinkParams, Requirement
from common.modeling.path_qos import compose_from_params
from common.modeling.qos_checker import check_qos
from common.config.settings import load_settings, load_tokens

SUITE_SCENE = "sce20261010-conf02/sce01"
FLOW = ("UAV0001", "UAV0002")
TARGET_SID = "TSV0005"
SIBLING_SIDS = ("BGV0009", "BGV0020")
ALL_SIDS = (TARGET_SID, *SIBLING_SIDS)
CANDIDATE_LINKS = ["L00019", "L00011", "L00010", "L00009", "L00015", "L00017"]
# TSV0005 方向的完整基线路径（取自 service-paths.json）。
# 不用 GET path 的返回值做恢复：system 路径对反向业务可能缺少接入链路，
# 直接用残缺路径下发会 1001「段列表不连续」。
ORIGINAL_LINKS = ["L00019", "L00012", "L00015", "L00017"]
ACTUAL_POLL_SECONDS = 24
BASELINE_POLL_SECONDS = 6
ACTUAL_POLL_INTERVAL = 3


def _segments(path: dict[str, Any] | None) -> list[tuple[str, str]]:
    return [
        (str(seg.get("type", "")), str(seg.get("id", "")))
        for seg in (path or {}).get("segments") or []
    ]


def _link_ids(path: dict[str, Any] | None) -> list[str]:
    return [sid for typ, sid in _segments(path) if typ == "link"]


def _fmt_segments(segments: list[tuple[str, str]]) -> str:
    return " -> ".join(f"{typ}:{sid}" for typ, sid in segments) or "(empty)"


def _fmt_path(path: dict[str, Any] | None) -> str:
    return (
        f"pathId={path.get('pathId')} source={path.get('source')} "
        f"segments={_fmt_segments(_segments(path))}"
    )


def _access_link_ids(
    links: list[dict[str, Any]], endpoint_ids: set[str]
) -> set[str]:
    """flow 两端的接入链路：一端在 endpoint_ids、另一端不在的链路。"""
    access: set[str] = set()
    for link in links:
        src = link.get("srcNodeId")
        dst = link.get("dstNodeId")
        if (src in endpoint_ids) != (dst in endpoint_ids):
            access.add(str(link["linkId"]))
    return access


def _core_links(
    path: dict[str, Any] | None, access_ids: set[str]
) -> list[str]:
    return [lid for lid in _link_ids(path) if lid not in access_ids]


def _direction_matches(
    svc: dict[str, Any],
    path: dict[str, Any] | None,
    link_map: dict[str, dict[str, Any]],
) -> bool:
    """返回路径首段是否与业务源节点相接。"""
    link_ids = _link_ids(path)
    if not link_ids:
        return False
    first = link_map.get(link_ids[0]) or {}
    return svc.get("srcNodeId") in {
        first.get("srcNodeId"),
        first.get("dstNodeId"),
    }


def _failed_metrics(
    actual: dict[str, Any], req: Requirement
) -> list[str]:
    failed: list[str] = []
    if (
        actual.get("avgDelayMs") is not None
        and actual["avgDelayMs"] > req.delay_ms + 1.0
    ):
        failed.append("delay")
    if (
        actual.get("jitterMs") is not None
        and actual["jitterMs"] > req.jitter_ms + 1e-9
    ):
        failed.append("jitter")
    if (
        actual.get("effBwBps") is not None
        and actual["effBwBps"] < req.bandwidth_bps
    ):
        failed.append("bandwidth")
    if (
        actual.get("packetLossRate") is not None
        and actual["packetLossRate"] > req.packet_loss_rate + 1e-9
    ):
        failed.append("packet_loss")
    if (
        actual.get("errPct") is not None
        and actual["errPct"] / 100.0 > req.ber + 1e-12
    ):
        failed.append("ber")
    return failed


def _worst_observation(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    for obs in observations:
        if obs.get("qosMeet") is False or obs.get("failed"):
            return obs
    return observations[-1] if observations else {}


def _print_run_info(open_base: str, ctrl_token: str | None) -> None:
    if not ctrl_token:
        print("[ISS-0003] run-info: ctrlToken 不可用，跳过")
        return
    ctrl_base = open_base.replace("/open/v1", "/ctrl/v1")
    try:
        resp = requests.get(
            f"{ctrl_base}/run-info",
            headers={"X-Ctrl-Token": ctrl_token},
            timeout=3,
        )
        payload = resp.json()
        data = payload.get("data", payload)
        print(
            "[ISS-0003] instance: "
            f"suiteId={data.get('suiteId')} scenarioId={data.get('scenarioId')} "
            f"scriptId={data.get('scriptId')} status={data.get('status')}"
        )
        engine = data.get("engine") or {}
        if engine.get("fired"):
            print(
                f"[ISS-0003] WARNING: 当前实例已触发 "
                f"{engine.get('fired')}/{engine.get('total')} 个事件，"
                "链路参数可能已变化"
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[ISS-0003] run-info 读取失败（忽略）: {exc}")


def _sample_actual(
    client: SimulatorClient,
    sids: tuple[str, ...],
    seconds: int,
    requirements: dict[str, Requirement],
    tag: str = "C4",
) -> dict[str, list[dict[str, Any]]]:
    observations: dict[str, list[dict[str, Any]]] = {sid: [] for sid in sids}
    start = time.time()
    deadline = start + seconds
    print(f"[ISS-0003][{tag}] 采样 {seconds}s，间隔 {ACTUAL_POLL_INTERVAL}s")
    while time.time() < deadline:
        elapsed = int(time.time() - start)
        for sid in sids:
            detail = client.get_service(sid)
            actual = detail.get("actual") or {}
            failed = _failed_metrics(actual, requirements[sid])
            obs = {
                "jitterMs": actual.get("jitterMs"),
                "avgDelayMs": actual.get("avgDelayMs"),
                "effBwBps": actual.get("effBwBps"),
                "packetLossRate": actual.get("packetLossRate"),
                "errPct": actual.get("errPct"),
                "qosMeet": actual.get("qosMeet"),
                "failed": failed,
            }
            observations[sid].append(obs)
            req = requirements[sid]
            print(
                f"[ISS-0003][{tag}] t+{elapsed}s {sid}: "
                f"delay={obs['avgDelayMs']} (req<={req.delay_ms}) "
                f"jitter={obs['jitterMs']} (req<={req.jitter_ms}) "
                f"effBw={obs['effBwBps']} (req>={req.bandwidth_bps}) "
                f"loss={obs['packetLossRate']} (req<={req.packet_loss_rate}) "
                f"errPct={obs['errPct']} "
                f"qosMeet={obs['qosMeet']} failed={failed}"
            )
        time.sleep(ACTUAL_POLL_INTERVAL)
    return observations


def _restore(
    client: SimulatorClient,
    sid: str,
    src: str,
    dst: str,
    original_links: list[str],
) -> None:
    print("\n[ISS-0003][RESTORE] ===== 恢复基线路径 =====")
    segments = [{"type": "link", "id": lid} for lid in original_links]
    print(
        f"[ISS-0003][RESTORE] POST /services/{sid}/path "
        f"links={original_links}"
    )
    try:
        result = client.set_service_path(
            sid, src, dst, segments, request_id=client.gen_request_id()
        )
        print(f"[ISS-0003][RESTORE] response={json.dumps(result, ensure_ascii=False)}")
        if result.get("result") != "accepted":
            print(f"[ISS-0003][RESTORE] WARNING: 恢复未 accepted: {result}")
            return
        path = client.get_service_path(sid)
        print(f"[ISS-0003][RESTORE] verified {sid}: {_fmt_path(path)}")
        if _link_ids(path) != original_links:
            print(
                "[ISS-0003][RESTORE] WARNING: 恢复后的 link 序列与基线不一致："
                f"{_link_ids(path)} vs {original_links}"
            )
        else:
            print("[ISS-0003][RESTORE] OK: 路径已恢复（pathId/source 可能变化）")
    except Exception as exc:  # noqa: BLE001
        print(f"[ISS-0003][RESTORE] WARNING: 恢复失败，环境可能未回到基线: {exc}")


@pytest.fixture(scope="module")
def env():
    settings = load_settings()
    sim = settings["simulator"]
    app = settings.get("app", {})
    try:
        tokens = load_tokens(sim.get("token_file"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"无法读取 gateway.json 令牌: {exc}")
    open_tokens = tokens.get("open_tokens") or []
    if not open_tokens:
        pytest.skip("gateway.json 中无 openTokens")

    client = SimulatorClient(
        base_url=sim["base_url"],
        token=open_tokens[0],
        agent_id="verify-iss0003",
        timeout=app.get("http_timeout_sec", 6.0),
    )
    try:
        client.get_time()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"仿真器不可达（netsim 未就绪？）: {exc}")

    _print_run_info(sim["base_url"], tokens.get("ctrl_token"))

    try:
        running = client.get_services(status="running", size=500).get("services", [])
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"读取业务列表失败: {exc}")
    by_id = {svc["serviceId"]: svc for svc in running}
    missing = [sid for sid in ALL_SIDS if sid not in by_id]
    if missing:
        pytest.skip(
            f"缺少 running 业务 {missing}；"
            f"请先启动 {SUITE_SCENE} 并等待业务 running"
        )

    expected_flow = set(FLOW)
    for sid in ALL_SIDS:
        svc = by_id[sid]
        pair = {svc.get("srcNodeId"), svc.get("dstNodeId")}
        if pair != expected_flow:
            pytest.skip(
                f"{sid} 端点为 {sorted(str(x) for x in pair)}，"
                f"与预期 flow {sorted(expected_flow)} 不一致"
            )
    return client, by_id


def test_c1_flow_members_share_one_path(env) -> None:
    client, _ = env
    print("\n[ISS-0003][C1] ===== 同 flow 多条业务是否共用一条路径 =====")
    links = client.get_links(size=1000).get("links", [])
    access_ids = _access_link_ids(links, set(FLOW))
    print(f"[ISS-0003][C1] flow {FLOW} 的接入链路: {sorted(access_ids)}")

    base_core: list[str] | None = None
    raw_by_sid: dict[str, list[tuple[str, str]]] = {}
    for sid in ALL_SIDS:
        path = client.get_service_path(sid)
        raw = _segments(path)
        core = _core_links(path, access_ids)
        raw_by_sid[sid] = raw
        print(
            f"[ISS-0003][C1] {sid}: {_fmt_path(path)} "
            f"| core={core}"
        )
        if base_core is None:
            base_core = core
        else:
            assert core == base_core, (
                f"{sid} 的 core 路径与 {ALL_SIDS[0]} 不同："
                f"{core} vs {base_core}"
            )
    assert base_core, "基线 core 路径为空"

    if len({tuple(raw) for raw in raw_by_sid.values()}) > 1:
        print(
            "[ISS-0003][C1][NOTE] 基线 system 路径的原始 segments 不完全相同："
            "反向业务缺少接入链路（平台 GET path 的表示问题，见 ISS-0004）。"
            "core 路径一致，flow 仍共用同一条路。"
        )
    print(
        f"[ISS-0003][C1] PASS: {len(ALL_SIDS)} 条业务的 core 路径一致 "
        f"（{len(base_core)} 段，不含接入链路）"
    )


def test_c2_c3_c4_service_entry_flow_effect_and_validation_scope(env) -> None:
    client, services = env
    target = services[TARGET_SID]
    src = target["srcNodeId"]
    dst = target["dstNodeId"]

    print("\n[ISS-0003][C2] ===== service 入口 / flow 生效 =====")
    print(
        f"[ISS-0003][C2] flow={FLOW[0]}<->{FLOW[1]} "
        f"target={TARGET_SID} {src}->{dst}"
    )

    details = {sid: client.get_service(sid) for sid in ALL_SIDS}
    requirements: dict[str, Requirement] = {}
    for sid in ALL_SIDS:
        raw_req = details[sid].get("requirement")
        assert raw_req, f"{sid} 缺少 requirement"
        req = Requirement.from_dict(raw_req)
        requirements[sid] = req
        print(
            f"[ISS-0003][C2] {sid} requirement: "
            f"delay<={req.delay_ms} jitter<={req.jitter_ms} "
            f"bw>={req.bandwidth_bps} ber<={req.ber} "
            f"loss<={req.packet_loss_rate}"
        )

    baseline: dict[str, dict[str, Any]] = {}
    for sid in ALL_SIDS:
        path = client.get_service_path(sid)
        baseline[sid] = path
        print(f"[ISS-0003][C2] baseline {sid}: {_fmt_path(path)}")

    baseline_links = _link_ids(baseline[TARGET_SID])
    print(
        f"[ISS-0003][C2] baseline {TARGET_SID} link 序列: {baseline_links}"
    )
    if baseline_links == CANDIDATE_LINKS:
        pytest.skip("当前 flow 已经是候选路径，无法验证切换")
    if baseline_links and baseline_links != ORIGINAL_LINKS:
        print(
            "[ISS-0003][C2][NOTE] 基线 GET path 与 service-paths 的完整路径不一致："
            f"{baseline_links} vs {ORIGINAL_LINKS}。"
            "恢复将使用 ORIGINAL_LINKS，避免用残缺路径下发导致 1001。"
        )

    print("\n[ISS-0003][C4-BASE] ===== 下发前实测基线 =====")
    baseline_observations = _sample_actual(
        client,
        ALL_SIDS,
        BASELINE_POLL_SECONDS,
        requirements,
        tag="C4-BASE",
    )

    print("\n[ISS-0003][C3] ===== 候选路径静态校验范围 =====")
    links = client.get_links(size=1000).get("links", [])
    link_map = {link["linkId"]: link for link in links}
    params: list[LinkParams] = []
    for lid in CANDIDATE_LINKS:
        link = link_map.get(lid)
        assert link is not None, f"链路 {lid} 不在 /links 返回中"
        assert link.get("status", "up") == "up", f"链路 {lid} 当前不是 up"
        raw_params = link.get("params")
        assert raw_params, f"链路 {lid} 缺少 params"
        params.append(LinkParams.from_dict(raw_params))
        print(
            f"[ISS-0003][C3] link {lid} "
            f"{link.get('srcNodeId')}-{link.get('dstNodeId')}: "
            f"delay={raw_params['delayMs']} jitter={raw_params['jitterMs']} "
            f"bw={raw_params['bandwidthBps']} "
            f"loss={raw_params['packetLossRate']} ber={raw_params['ber']}"
        )

    qos = compose_from_params(params)
    print(
        f"[ISS-0003][C3] candidate static QoS: "
        f"delay={qos.delay_ms:.3f} jitter={qos.jitter_ms:.3f} "
        f"bw={qos.bandwidth_bps} loss={qos.packet_loss_rate:.6f} "
        f"ber={qos.ber:.6g}"
    )

    target_result = check_qos(qos, requirements[TARGET_SID])
    print(
        f"[ISS-0003][C3] {TARGET_SID} -> feasible={target_result.feasible} "
        f"violations={target_result.violations} margin={target_result.margin}"
    )
    if not target_result.feasible:
        pytest.skip(
            f"实时链路参数下候选路径对 {TARGET_SID} 不可行: "
            f"{target_result.violations}"
        )

    for sid in SIBLING_SIDS:
        result = check_qos(qos, requirements[sid])
        print(
            f"[ISS-0003][C3] {sid} -> feasible={result.feasible} "
            f"violations={result.violations} margin={result.margin}"
        )
        assert not result.feasible and "jitter" in result.violations, (
            f"预期 {sid} 在候选路径上 jitter 违规，实际 "
            f"feasible={result.feasible} violations={result.violations}；"
            "实时链路参数可能已变化"
        )

    segments = [{"type": "link", "id": lid} for lid in CANDIDATE_LINKS]
    request_id = client.gen_request_id()
    print("\n[ISS-0003][C2] ===== 只对目标业务下发候选路径 =====")
    print(
        f"[ISS-0003][C2] POST /services/{TARGET_SID}/path "
        f"requestId={request_id}"
    )
    print(
        "[ISS-0003][C2] body="
        + json.dumps(
            {"srcNodeId": src, "dstNodeId": dst, "segments": segments},
            ensure_ascii=False,
        )
    )

    changed = False
    try:
        result = client.set_service_path(
            TARGET_SID, src, dst, segments, request_id=request_id
        )
        print(f"[ISS-0003][C2] response={json.dumps(result, ensure_ascii=False)}")
        assert result.get("result") == "accepted", f"下发未 accepted: {result}"
        changed = True

        print("\n[ISS-0003][C2] ===== 下发后复查同 flow 全部业务路径 =====")
        after: dict[str, dict[str, Any]] = {}
        for sid in ALL_SIDS:
            path = client.get_service_path(sid)
            after[sid] = path
            print(f"[ISS-0003][C2] after {sid}: {_fmt_path(path)}")

        target_segments = _segments(after[TARGET_SID])
        for sid in ALL_SIDS:
            assert _segments(after[sid]) == target_segments, (
                f"{sid} 未跟随 flow 路径变化："
                f"{_fmt_segments(_segments(after[sid]))} "
                f"vs {_fmt_segments(target_segments)}"
            )
        assert _link_ids(after[TARGET_SID]) == CANDIDATE_LINKS, (
            f"下发后的路径不是候选路径: {_link_ids(after[TARGET_SID])}"
        )
        path_ids = {after[sid].get("pathId") for sid in ALL_SIDS}
        assert len(path_ids) == 1, f"同 flow 业务的 pathId 不一致: {path_ids}"
        for sid in ALL_SIDS:
            assert after[sid].get("source") == "agent", (
                f"{sid} 的 path source 不是 agent: "
                f"{after[sid].get('source')}"
            )
        for sid in ALL_SIDS:
            svc = services[sid]
            if not _direction_matches(svc, after[sid], link_map):
                print(
                    f"[ISS-0003][C2][NOTE] {sid} 业务方向 "
                    f"{svc['srcNodeId']}->{svc['dstNodeId']}，"
                    "GET 返回的 segments 是 flow 规范方向"
                    "（首段不接业务源节点）；物理路径相同。"
                )
        print(
            f"[ISS-0003][C2] PASS: 三条业务路径均为 "
            f"pathId={path_ids.pop()} source=agent，"
            f"候选路径 {len(CANDIDATE_LINKS)} 段"
        )

        print("\n[ISS-0003][C4-AFTER] ===== 下发后实测 =====")
        observations = _sample_actual(
            client,
            ALL_SIDS,
            ACTUAL_POLL_SECONDS,
            requirements,
            tag="C4-AFTER",
        )

        print("\n[ISS-0003][C4] ===== 下发前后对比 =====")
        attributable: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        already_failing: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for sid in SIBLING_SIDS:
            before = _worst_observation(baseline_observations[sid])
            after_obs = _worst_observation(observations[sid])
            before_bad = (
                bool(before.get("failed")) or before.get("qosMeet") is False
            )
            after_bad = (
                bool(after_obs.get("failed"))
                or after_obs.get("qosMeet") is False
            )
            print(
                f"[ISS-0003][C4] COMPARE {sid}: "
                f"baseline qosMeet={before.get('qosMeet')} "
                f"failed={before.get('failed')} | "
                f"after qosMeet={after_obs.get('qosMeet')} "
                f"failed={after_obs.get('failed')}"
            )
            if after_bad and not before_bad:
                attributable.append((sid, before, after_obs))
                print(
                    f"[ISS-0003][C4] ATTRIBUTABLE {sid}: "
                    "下发后新出现不达标"
                )
            elif after_bad and before_bad:
                already_failing.append((sid, before, after_obs))
                print(
                    f"[ISS-0003][C4] ALREADY_FAILING {sid}: "
                    "下发前已不达标，不能归因于本次改路"
                )
            else:
                print(
                    f"[ISS-0003][C4] NO_DEGRADATION {sid}: "
                    "下发后未见新不达标"
                )

        target_before = _worst_observation(baseline_observations[TARGET_SID])
        target_after = _worst_observation(observations[TARGET_SID])
        print(
            f"[ISS-0003][C4] TARGET {TARGET_SID}: "
            f"baseline qosMeet={target_before.get('qosMeet')} "
            f"failed={target_before.get('failed')} | "
            f"after qosMeet={target_after.get('qosMeet')} "
            f"failed={target_after.get('failed')}"
        )

        if attributable:
            print(
                "[ISS-0003][C4] RESULT: 兄弟业务在下发后新出现实测不达标，"
                "可归因于本次 flow 改路"
            )
        elif already_failing:
            print(
                "[ISS-0003][C4] RESULT: 兄弟业务下发后不达标，但下发前已不达标，"
                "不能归因于本次改路；校验缺口仍由 accepted + 静态违规证明"
            )
        else:
            print(
                "[ISS-0003][C4] RESULT: 未观察到兄弟业务实测回退；"
                "以 accepted + 静态违规作为校验缺口证据"
            )
    finally:
        if changed:
            _restore(client, TARGET_SID, src, dst, ORIGINAL_LINKS)
