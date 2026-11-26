"""数学建模：数据模型、QoS 合成与判定、链路代价归一化。

本层**纯计算、无 IO、无 NetworkX 图依赖**，可独立单测；是所有上层（算法、
感知、控制）的公共词汇表。

- `models.py`：`Node` / `Link` / `Service` / `Requirement` / `Actual` 等实体，
  字段名对齐公开 API 的 JSON 字段。
- `flow.py`：flow 分组（无序端点对）与 flow 级需求聚合（交集）。
- `path_qos.py`：静态路径 QoS 合成（口径严格对齐仿真器 `_compose_qos`）。
- `qos_checker.py`：静态 QoS 容差判定（时延 +1.0、抖动/丢包 +1e-9、误码 +1e-12、
  带宽无容差）。
- `link_quality.py`：链路代价归一化（**只用于路径排序，不参与 QoS 判定**）。
- `measured_qos.py`：实测 QoS 统计（逐秒 `actual.qosMeet`）。

**两套 QoS 必须分开**：静态（提交校验口径）与实测（逐秒评分口径）不可混用。
"""
