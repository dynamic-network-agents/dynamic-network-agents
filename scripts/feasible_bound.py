"""场景静态可达性与最优 flow 摆法分析（无脚本/无事件场景）。

回答三件事：
1. **接入段上界**：每个 UAV 只有一条可用接入链路时，某方向在接入链路上的负载
   = 该方向所有业务需求之和，**与路由无关** → 凡该方向超容的 test 业务物理不可达。
2. **各方案达标数**：生成器基线（service-paths.json 的 paths[0]）/ 当前规划器 /
   随机重启搜索的最优，各自能让几条 test 业务达标。
3. **最优 flow 摆法**：达标时每个 flow 应该走哪条路径。

口径（模型近似，不是仿真器规则）：一条 test 业务"达标"= 它**自身方向**上所经每条
链路的利用率 ≤ 100%（全双工、按方向记账；TBF 是每方向一个令牌桶）。这是容量维度的
可达成上界，不含排队时延/抖动/丢包对实测 qosMeet 的影响。

用法：
    PYTHONPATH=src .venv/bin/python scripts/feasible_bound.py <scenario_dir> \
        [--k 30] [--restarts 600] [--seed 7]

示例：
    PYTHONPATH=src .venv/bin/python scripts/feasible_bound.py \
        simulator/data/scenarios/sce20261010-conf02/sce01
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from common.algorithms.topology.capacity import capacity_map, directional_demand  # noqa: E402
from common.algorithms.flow.planner import PlanConfig, normalize_path, plan  # noqa: E402
from common.algorithms.topology.graph import build_graph, node_path_to_link_ids  # noqa: E402
from common.algorithms.path.k_shortest import k_shortest_paths  # noqa: E402
from common.modeling.flow import (  # noqa: E402
    flow_requirement,
    group_services_by_flow,
    service_is_test,
)
from common.modeling.models import Link, Node, Service  # noqa: E402
from common.modeling.path_qos import compose_qos  # noqa: E402
from common.modeling.qos_checker import check_qos  # noqa: E402

USABLE_BW = 1_000_000        # 接入链路"可用"门槛（低于 1Mbps 视为不可承载业务）


# --------------------------------------------------------------------------- 加载
def load_scenario(scenario_dir: Path):
    topo = json.loads((scenario_dir / "net-topo.json").read_text(encoding="utf-8"))
    svcs = json.loads((scenario_dir / "bg-service.json").read_text(encoding="utf-8"))
    nodes = [Node.from_dict(n) for n in topo["nodes"]]
    links = [Link.from_dict(l) for l in topo["links"]]
    graph = build_graph(nodes, links)
    services = [Service.from_dict(s) for s in svcs]
    flows = group_services_by_flow(services)
    sp_path = scenario_dir / "service-paths.json"
    sp = json.loads(sp_path.read_text(encoding="utf-8")) if sp_path.exists() else None
    return topo, services, flows, graph, sp


# --------------------------------------------------------------------------- 接入段
def access_report(topo, services, graph):
    """每个 UAV 的可用接入链路 + 该方向总负载（路由无关）。"""
    nodes = {n["nodeId"]: n for n in topo["nodes"]}
    cap = capacity_map(graph)
    rows = []
    for uid in sorted(x for x in nodes if nodes[x]["nodeType"] == "uav"):
        adj = []
        for l in topo["links"]:
            if l["srcNodeId"] == uid:
                adj.append((l["linkId"], l["params"]["bandwidthBps"]))
            elif l["dstNodeId"] == uid:
                adj.append((l["linkId"], l["params"]["bandwidthBps"]))
        usable = [(lid, bw) for lid, bw in adj if bw > USABLE_BW]
        if not usable:
            rows.append((uid, "-", 0.0, 0.0, 0.0, 0.0, True))
            continue
        main = max(usable, key=lambda x: x[1])
        bw = cap.get(main[0], main[1])
        out = sum(s.requirement.bandwidth_bps or 0 for s in services if s.src_node_id == uid)
        inn = sum(s.requirement.bandwidth_bps or 0 for s in services if s.dst_node_id == uid)
        uo, ui = (out / bw if bw else 0), (inn / bw if bw else 0)
        rows.append((uid, main[0], bw, uo, ui, len(usable), False))
    return rows


def blocked_by_access(services, access_rows):
    """返回 (可达 test 列表, 因接入段超容而不可达的 test 列表)。"""
    by_uav = {r[0]: r for r in access_rows}
    ok, blocked = [], []
    for s in services:
        if not service_is_test(s):
            continue
        r_out = by_uav.get(s.src_node_id)
        r_in = by_uav.get(s.dst_node_id)
        over = []
        if r_out and r_out[3] > 1.0:
            over.append(f"{s.src_node_id} 出向 {r_out[3]:.0%}")
        if r_in and r_in[4] > 1.0:
            over.append(f"{s.dst_node_id} 入向 {r_in[4]:.0%}")
        (blocked if over else ok).append((s, over))
    return ok, blocked


# --------------------------------------------------------------------------- 评估
def load_of(assign, flows, graph):
    ld: dict[tuple[str, int], int] = {}
    for k, p in assign.items():
        if not p:
            continue
        for kk, vv in directional_demand(k[0], flows[k], list(p), graph).items():
            ld[kk] = ld.get(kk, 0) + vv
    return ld


def met_services(assign, flows, graph, cap, ld=None):
    """自身方向最大利用率 ≤100% 的 test 业务列表（模型口径）。

    `ld` 可传入已算好的负载表，避免每次评估都整表重算。
    """
    if ld is None:
        ld = load_of(assign, flows, graph)
    ok = []
    for k, p in assign.items():
        if not p:
            continue
        for s in flows[k]:
            if not service_is_test(s):
                continue
            dd = directional_demand(k[0], [s], list(p), graph)
            u = max(
                (ld.get(kk, 0) / cap[kk[0]] for kk in dd if cap.get(kk[0], 0) > 0),
                default=0.0,
            )
            if u <= 1.0:
                ok.append(s.service_id)
    return ok


def enumerate_candidates(flows, graph, k):
    out = {}
    for key, svcs in flows.items():
        req = flow_requirement(svcs)
        cands = []
        if req is not None:
            for np_ in k_shortest_paths(graph, key[0], key[1], k):
                lid = node_path_to_link_ids(graph, np_)
                if check_qos(compose_qos(lid, graph), req).feasible:
                    cands.append(tuple(lid))
        out[key] = cands or [()]
    return out


# --------------------------------------------------------------------------- 搜索
def _path_load(key, path, flows, graph):
    return directional_demand(key[0], flows[key], list(path), graph)


def greedy(flows, graph, cap, cands, order):
    ld: dict[tuple[str, int], int] = {}
    assign = {}
    for key in order:
        best = None
        for c in cands[key]:
            if not c:
                continue
            dd = _path_load(key, c, flows, graph)
            u = max(
                ((ld.get(kk, 0) + vv) / cap[kk[0]] for kk, vv in dd.items()
                 if cap.get(kk[0], 0) > 0),
                default=0.0,
            )
            fits = all((ld.get(kk, 0) + vv) <= cap[kk[0]] * 0.8 for kk, vv in dd.items())
            key2 = (0 if fits else 1, round(u, 4))
            if best is None or key2 < best[0]:
                best = (key2, c)
        if best is None:
            continue
        assign[key] = best[1]
        for kk, vv in _path_load(key, best[1], flows, graph).items():
            ld[kk] = ld.get(kk, 0) + vv
    return assign, ld


def search_best(flows, graph, cap, cands, restarts, seed):
    """随机重启贪心 + 局部改进；返回 (达标数, 分配, 达标业务列表)。

    局部改进只动「未达标或所在链路已 >90%」的 flow，避免 O(flow×候选) 的全量重估。
    """
    rng = random.Random(seed)
    best = (0, None, [])
    for it in range(restarts):
        order = list(flows)
        mode = it % 4
        if mode == 0:
            order.sort(key=lambda k: (
                -sum(2 ** s.priority for s in flows[k] if service_is_test(s)), k))
        elif mode == 1:
            order.sort(key=lambda k: (
                sum(2 ** s.priority for s in flows[k] if service_is_test(s)), k))
        elif mode == 2:
            rng.shuffle(order)
        else:
            order.sort(key=lambda k: (len(flows[k]), k))
        assign, ld = greedy(flows, graph, cap, cands, order)
        for _ in range(6):
            n = len(met_services(assign, flows, graph, cap, ld))
            total = sum(ld.values())
            # 需要动的 flow：自身未达标，或其路径上有链路已 ≥90%
            hot = {
                k for k, p in assign.items()
                if not p or any(
                    ld.get(kk, 0) / cap[kk[0]] >= 0.9
                    for kk in directional_demand(k[0], flows[k], list(p), graph)
                    if cap.get(kk[0], 0) > 0
                )
            }
            moved = False
            for key in list(hot):
                cur = assign[key]
                old_dd = _path_load(key, cur, flows, graph) if cur else {}
                for c in cands[key]:
                    if c == cur or not c:
                        continue
                    new_dd = _path_load(key, c, flows, graph)
                    # 增量更新负载，避免整表重算
                    trial = dict(ld)
                    for kk, vv in old_dd.items():
                        trial[kk] = trial.get(kk, 0) - vv
                    for kk, vv in new_dd.items():
                        trial[kk] = trial.get(kk, 0) + vv
                    t2 = sum(trial.values())
                    assign[key] = c
                    n2 = len(met_services(assign, flows, graph, cap, trial))
                    if n2 > n or (n2 == n and t2 < total):
                        ld, n, total = trial, n2, t2
                        moved = True
                        break
                    assign[key] = cur
                if not moved:
                    continue
                break
            if not moved:
                break
        n = len(met_services(assign, flows, graph, cap, ld))
        if n > best[0]:
            best = (n, assign, sorted(met_services(assign, flows, graph, cap, ld)))
    return best


# --------------------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description="场景静态可达性与最优 flow 摆法")
    ap.add_argument("scenario_dir")
    ap.add_argument("--k", type=int, default=30, help="候选路径条数")
    ap.add_argument("--restarts", type=int, default=600, help="搜索重启次数")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-search", action="store_true", help="跳过随机搜索（只算上界与现状）")
    args = ap.parse_args()

    scenario_dir = Path(args.scenario_dir)
    topo, services, flows, graph, sp = load_scenario(scenario_dir)
    cap = capacity_map(graph)
    test_svcs = [s for s in services if service_is_test(s)]
    flows_with_test = [k for k, v in flows.items() if any(service_is_test(s) for s in v)]

    print(f"场景：{scenario_dir}")
    print(f"  业务 {len(services)} 条（test {len(test_svcs)}），flow {len(flows)} 个"
          f"（含 test {len(flows_with_test)} 个）")

    # 1) 接入段上界
    rows = access_report(topo, services, graph)
    print("\n[1] 接入段（负载与路由无关）")
    print(f"  {'UAV':10s} {'接入':10s} {'容量':>7s} {'出向':>7s} {'入向':>7s} {'可用链路数':>9s}")
    for uid, lid, bw, uo, ui, n, _ in rows:
        print(f"  {uid:10s} {lid:10s} {bw/1e6:7.0f}M {uo:7.0%} {ui:7.0%} {n:9d}")

    ok, blocked = blocked_by_access(services, rows)
    bound = len(ok)
    print(f"\n[2] 接入段上界：最多 {bound} 条 test 业务可达"
          f"（因接入段超容物理不可达 {len(blocked)} 条）")
    for s, over in blocked:
        print(f"  ✗ {s.service_id} {s.src_node_id}→{s.dst_node_id} p{s.priority}"
              f" {s.service_type}：{'；'.join(over)}")
    for s, _ in ok:
        print(f"  ✓ {s.service_id} {s.src_node_id}→{s.dst_node_id} p{s.priority} {s.service_type}")

    # 2) 生成器基线
    baseline = {}
    if sp:
        for key, svcs in flows.items():
            raw = None
            for s in svcs:
                hit = next((x for x in sp["services"] if x["serviceId"] == s.service_id), None)
                if hit and hit.get("paths"):
                    raw = hit["paths"][0]["links"]
                    break
            baseline[key] = normalize_path(graph, key, raw) or []
        m = sorted(met_services(baseline, flows, graph, cap))
        print(f"\n[3] 生成器基线（service-paths.json paths[0]）：{len(m)}/{len(test_svcs)} 条达标"
              f" -> {m}")

    # 3) 当前规划器
    plans = plan(flows, graph, PlanConfig(candidate_path_count=args.k, enable_local_search=True))
    planner = {k: tuple(p.path) for k, p in plans.items() if p.path}
    m = sorted(met_services(planner, flows, graph, cap))
    print(f"\n[4] 当前规划器（greedy + 局部搜索）：{len(m)}/{len(test_svcs)} 条达标 -> {m}")

    # 4) 随机搜索上界
    if not args.no_search:
        cands = enumerate_candidates(flows, graph, args.k)
        n, assign, m = search_best(flows, graph, cap, cands, args.restarts, args.seed)
        print(f"\n[5] 随机重启搜索（{args.restarts} 次，seed={args.seed}）："
              f"{n}/{len(test_svcs)} 条达标 -> {m}")
        print(f"  {'★ 命中上界' if n == bound else '★ 未命中上界（可能还有更优解）'}")
        print("\n  达标 flow 的摆法：")
        for key, p in sorted(assign.items()):
            t = [s.service_id for s in flows[key] if service_is_test(s)]
            if not t:
                continue
            ok_all = all(x in m for x in t)
            print(f"    {'达标 ' if ok_all else '不达标'}{key[0]}↔{key[1]:12s}"
                  f" {','.join(t):12s} {' > '.join(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
