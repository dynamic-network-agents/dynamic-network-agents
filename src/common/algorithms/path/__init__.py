"""路径域算法：单条路径的生成与选择。

- `k_shortest.py`：Yen K-最短路径（基于 NetworkX `shortest_simple_paths`，
  先把并行边折叠成简单图）。
- `single_flow.py`：早期单 flow 选路（`optimize_flow`）。**已不在闭环里**，
  仅保留做离线对比（T3.2）。

路径**代价**（`common.modeling.link_quality.path_cost`）只用于可行路径之间的
**排序**，不参与 QoS 判定。
"""
