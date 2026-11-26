"""感知层：把仿真器状态冻结成一致的「网络快照」，并维护事件流。

- `snapshot.py`：`SnapshotSource.fetch()` 一次性拉齐**规划所需的全部输入**
  （拓扑 + 链路 + running 业务详情 + 现状路径 + test 采样范围），打成
  `NetworkSnapshot`。规划器是纯函数，同一快照重算必然同结果——这是闭环
  「不再下发」不动点的依据，所以 epoch 内不再回头读仿真器（批内不重算）。
- `events.py`：`EventSource` 维护 `sinceTsUs` 游标增量拉事件，并过滤出
  「值得重规划」的事件（丢弃自己下发产生的 `pathChanged` 事件，避免自激）。

baseline 与 agents 共用本层，保证两侧看到完全相同的网络视图。
"""
