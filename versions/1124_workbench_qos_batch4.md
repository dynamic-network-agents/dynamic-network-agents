# 修改记录

- 修改日期：2026-11-24
- 修改内容：Work Bench 第四批（E-01 / E-03）。新增 `analysis/qos.py`（静态路径 QoS：D=Σd、J=√Σj²、B=min、L=1−∏(1−p)、E≈Σε，容差 +1.0/+1e-9/+1e-12/带宽无，缺参数不做部分合成）与 `analysis/load.py`（链路需求侧负载：flow/service 数、demand、capacity、utilization，measured 标估计）；Service 增加 `staticQoS/staticCheck`，Flow 增加静态可行性计数，Snapshot 增加 `linkLoads`；前端 Service 详情展示静态合成与可行性，Flow 表加静态列，新增链路负载 Top 12 表。服务器环境实测：40 业务/17 Flow，实测 17 达标/18 不达标，静态 40 全可行，需求/容量最高 2.57。新增 `tests/integration/test_workbench_qos_crosscheck.py`：同一组 golden case 与主项目 `src/math_modeling` 对拍（4 例通过），确保两套静态 QoS 公式/容差不漂移。
