# 修改记录

- 修改日期：2026-11-25
- 修改内容：Work Bench 拓扑与 Flow 列表两处可用性改动。
  1. 网络拓扑显示链路 ID：`TopologyView.tsx` 新增 `labelsOn` 状态（默认开），节点 ID 与链路 ID 由右下角「显示文字」按钮统一开关（`aria-pressed` + `.is-on` 选中态），替换原先「≤80 节点或放大才显示」的自动密度规则；链路 ID 画在连线中点并沿法线偏移，白色描边 `paint-order` 保证压在风险/选中线上可读，`pointer-events:none` 不影响点选；关闭开关后仍保留当前选中节点/链路的 ID（琥珀加粗）。`index.css` 补 `.topo-labels-toggle.is-on` 与标签 `user-select`。
  2. Flow 列表排序：`FlowAnalysisPage.tsx` 抽出 `compareFlows(sortBy)`，默认按**源节点 → 目的节点**自然序升序（`Intl.Collator{numeric}`，缺节点 ID 的 Flow 置末，兜底 flowKey），`.list-tools` 新增「Flow 排序」下拉，可选 `节点 ID`（默认）/ `不达标优先`（原三级排序）/ `成员数`；`.list-tools` 允许换行。
  验证：`pnpm build` 通过；经 SSH 隧道连服务器真数据（21 节点/31 链路、17 Flow/40 业务）实测——链路 ID 31/31、节点 ID 21/21 渲染且开关可切；Flow 列表按 UAV0001→… 顺序，另两种排序切换行为正确。
