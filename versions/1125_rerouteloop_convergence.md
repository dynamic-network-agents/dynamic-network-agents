# 1125 · 基线选路闭环：收敛判据 + 增量下发

修改日期：2026-11-25
对应任务：`docs/task_split/flow_planner_task.md` 阶段 4 重做（T4.2 闭环重写）

## 修改内容

- `src/baseline/reroute_loop.py` 重写为 **epoch 状态机**（IDLE / SETTLING / VERIFYING）：
  一次 epoch = 一次冻结快照 + 一次规划 + 一个下发批 + 一次校验。
- 修掉三处「永远下发不完」的根因：
  1. 忽略自己下发产生的 `service_state_changed(pathChanged=true, running)` 事件（原来自激）；
  2. 路径比较容忍反序（仿真器按提交顺序存 flow 路径，原判据恒不相等）；
  3. 规划器保持纯函数（同输入同输出），下发前用 Δscore 闸门拦掉零收益改路。
- 评估过「把 incumbent 喂进贪心、现状优先」的做法并**放弃**：sce05 上分数 592→384、
  仍有 43 个 flow 抖动（贪心顺序敏感，反而破坏确定性）。
- 新增「批内不重算 / 批后静置 + 多窗投票 / 失配路径进惩罚集 / 有界纠正轮 / 全场批次预算」。
- 规划器 `least_contention` 改为按候选路径**自身**链路方向的利用率，修掉存在不可避瓶颈时的并列退化。
- 硬失败（F1/F2）flow 在现状可用时**钉住**，不再每轮重排。
- 静默期心跳只检查「上一轮预测达标」的 flow，硬失败 flow 不参与收敛判据。
- 新增配置项（`configs/app.yaml`）：`reroute_min_gain`、`settle_sec`、`verify_windows`、
  `verify_votes`、`corrective_rounds`、`trigger_settle_sec`、`heartbeat_sec`、
  `min_switch_interval_sec`、`batch_pace_sec`、`max_batches_per_run`。
- 新增 `scripts/smoke_epoch.py`：用真实 sce01 场景 + 假 client 跑完整闭环，验证
  「T0 一次批 → 静默 → 断链一次批 → 静默」且无重复下发。
- 新增/扩充单测：方向容忍、自事件过滤、一次批后不再下发、静置期事件中止、
  Δmin 拦截零收益改路、硬失败零动作、实测失配纠正、批次预算、纯函数确定性、断链必须改路。
