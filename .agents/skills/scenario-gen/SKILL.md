---
name: scenario-gen
description: 54所赛题仿真环境场景库与场景脚本（script-NN.json）的交互式生成流程。当用户要求生成/调整/新增场景、场景集合、场景库、配置集（gen_conf）、业务需求、链路布设、脚本事件，或要求重新生成拓扑图/业务图/事件图/场景统计（<场景标识>-stats.md，含业务路径清单）、做业务可行性审计时使用——即使没说"场景"二字（如"再出10个更大的场景""脚本事件加密度""新增一种链路类型"）也应触发。生成类请求必须先按必选项清单逐项收集（每项给默认值），收集全才写入配置并生成。
---

# 场景库与场景脚本生成（交互式收集 → 写入 → 生成 → 复验证）

**赛题对应关系**：本技能服务中国电科"网信杯"人工智能创新大赛智能体应用赛道**B03赛题"资源受限环境下通信网络资源管控"**（承办单位：中国电科网络通信研究院，即中国电科54所）。赛题名称自20261010版《赛题发布清单》起不含"智能体"尾，历史文档中的旧称"资源受限环境下通信网络资源管控智能体"指同一赛题。

数据与生成器定位：本包根下的 simulator/ 目录（技能随包置于 `.agents/skills/`，以包为工作目录即自动加载，产物链命令自定位、不依赖当前工作目录）。生成器与校验脚本为发布件（未经许可不得修改）；可调参数在配置集 params.yaml（data下）、生成逻辑默认参数在 `gen_scripts/gen_internal.yaml`、链路能力范围在 `conf/linkTypes.json`。
接口报文契约见 `doc/仿真软件接口.md`（随包发布件）；其余生成规则以本技能、配置集 params.yaml 注释、gen_internal.yaml 与 conf/linkTypes.json 为准。


## 第一步：说明当前生成逻辑（数值从哪来）

用户问"多少场景/多少测试脚本/多少节点/多少业务是怎么定的"时，先简答再收集：
**参赛方关心的数值全部来自配置集 `data/gen_conf<序号>/params.yaml`**——场景个数与规模
（scenario_count＋scale_ranges 区间或 scenario_table 显式表）、每场景脚本数（scripts_per_scenario）、
场景区域与每簇地面节点（area_km/cluster_gnd）、测试时长与事件时间参数（test_duration_min/event_window_min/
intra_gap_sec/inter_gap_min）；其余生成逻辑（业务类型构成与QoS区间、事件模型、网络形态、标识编址）
固化在 `gen_scripts/gen_internal.yaml`，不收集。生成器只含逻辑、不含数值；
链路参数范围引用 conf/linkTypes.json。

## 第二步：交互式收集生成要求（本技能核心流程）

完整参数清单、默认值与每项用途见 **references/params.md**（场景全局 G1~G3、网络规模 N1~N8、事件规模 E1~E4）。执行纪律：

1. **逐项问**：按 params.md 的 G→N→E 顺序用 AskUserQuestion 分批问（每批≤4个），
   每项必须给出默认值（"默认＝…"），用户可答"默认"或"全默认"跳过；
   提问话术按 **references/params.md 开头"提问话术纪律"** 执行——用户可见文本不出现
   内部编号/键名/配置集标识，选项＝默认值＋讲清依据的推荐值＋自定义；
   套件标识不问（自动派生）；事件密度（每簇事件数/事件簇数）不问但总览给出默认值；
   事件窗口单独问、参数两元＝T0后分钟数与Tend前分钟数（双侧偏移），默认 [3, 4]；
2. **复述确认**：收集完成后给出**参数总览**（每项取值，含默认补齐项、派生项及其规则），
   请用户确认，**确认通过才开始生成；用户可取消，取消即停止不写文件**；冲突项此时暴露
   （如总链路数低于结构下限、事件窗口不早于测试时长——加载器会报错，收集时先拦）；
3. **收集全才写入**：创建 `gen_conf<下一序号>/params.yaml`（单文件，参照 gen_conf01 现样例），
   然后生成并复验证。未收集全之前不写文件、不跑生成器；
4. 用户要求违反赛题要求/红线（如规模超无人平台≥300验收档需单列场景行）时指出冲突并给替代方案，不静默改。

## 产物链与命令

以下命令用脚本自身位置定位，不依赖当前工作目录（`SCRIPT_DIR` 为本技能目录，
可用 `SCRIPT_DIR="$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")"` 方式获取）：

```bash
SCRIPT_DIR="$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")"   # 本技能目录（.agents/skills/scenario-gen）
SIM="$SCRIPT_DIR/../../../simulator"                                 # simulator 根（包内布局：.agents/skills/scenario-gen → 包根三层）

python3 "$SIM/gen_scripts/gen_scenarios.py" --conf gen_conf<NN>               # 生成 → $SIM/data/scenarios/sce<YYYYMMdd>-conf<NN>/（配置集在data/下解析；套件名当日自动生成，params.yaml 写 version 可固定）
python3 "$SIM/gen_scripts/plot_topo.py" "$SIM/data/scenarios/sce<YYYYMMdd>-conf<NN>"/sce*   # 拓扑图 → $SIM/data/figures/<套件>/<场景>/
python3 "$SIM/gen_scripts/plot_services.py" --split "$SIM/data/scenarios/sce<YYYYMMdd>-conf<NN>"/sce*   # 业务关系图（汇总+8张拆分）→ 同上
python3 "$SIM/gen_scripts/plot_events.py" "$SIM/data/scenarios/sce<YYYYMMdd>-conf<NN>"/sce*   # 事件图（逐脚本横带、事件时刻竖线、按事件簇描框标数、横轴0~Tend分钟，观事件发生规律）→ 同上
python3 "$SIM/gen_scripts/export_scenario_stats.py" "$SIM/data/scenarios/sce<YYYYMMdd>-conf<NN>"/sce*   # 场景统计 → 每场景 <场景标识>-stats.md
python3 "$SCRIPT_DIR/scripts/validate_library.py" --conf gen_conf<NN>  # 全量复验证（默认最新套件；另一套件用--lib显式指定同后缀套件）
```

生成后必跑 `validate_library.py` 全量复验证，零违规才算完成；规模/难度/业务/链路任一变更后按产物链
重跑图与 `<场景标识>-stats.md` 保持同步。

