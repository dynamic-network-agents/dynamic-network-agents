"""拓扑域算法：网络图构建与方向容量记账。

- `graph.py`：`build_graph` 从 API 载荷建 NetworkX MultiGraph（只收 `status=up`
  链路与 `status=online` 节点、按 nodeId 显式剔除 `EXT001`、边属性携带 5 项
  链路参数）；另含路径工具 `validate_path` / `node_path_to_link_ids` /
  `link_endpoints`。
- `capacity.py`：方向容量记账（全双工 TBF 按方向，两个方向是独立令牌桶，
  方向键 `(link_id, sign)`）。

**构图必须用 `get_links()` 的链路列表**（带 params），不能用
`get_topology()["links"]`（不带 params，参数会全为 0）。
"""
