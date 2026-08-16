# ArenaForge GOAI Demo Script

## Opening

先说明 ArenaForge 是通用开放科学探索系统；本次以 Quantum Optics 作为
第一个 Reference Arena：

```text
物理问题
  -> 固定实验协议
  -> Agent 提出候选拓扑
  -> PyTheus 模拟与损耗扫描
  -> 多分支比较
  -> 正负证据和 scoped conclusion
```

## 1. Replay 一个真实探索

```bash
PYTHONPATH=src python scripts/run_quantum_optics_exploration.py
```

展示：

- 74 次单边扰动形成的边际影响筛查；
- 25 次通过质量门槛的连续删边行动，以及第 26 次边界失败；
- 作为策略参照保留的阈值剪枝和 random 负对照；
- fidelity 和 count rate 随 transmission 的变化；
- edge count、robust score、预算检查和质量门槛；
- `artifacts/search_trace.json` 与 `artifacts/exploration_log.jsonl` 中的完整轨迹。

## 2. 运行 ArenaForge Campaign

```bash
PYTHONPATH=src python -m arenaforge campaign-create \
  --project examples/quantum_optics_open_exploration \
  --campaign-id qo-loss-campaign-v3 \
  --question "Find the simplest GHZ preparation graph under a 55-edge budget and 2% per-point quality tolerance." \
  --metric edge_count \
  --direction minimize \
  --seeds 17,27 \
  --max-runs 8

PYTHONPATH=src python -m arenaforge campaign-plan \
  --campaign examples/quantum_optics_open_exploration/.arenaforge/campaigns/qo-loss-campaign-v3 \
  --candidates examples/quantum_optics_open_exploration/candidates.example.json

PYTHONPATH=src python -m arenaforge campaign-run \
  --campaign examples/quantum_optics_open_exploration/.arenaforge/campaigns/qo-loss-campaign-v3
```

## 3. 解释结果

Replay 当前会得到：

- canonical：`74` 条连接，robust score `0.763186`，超过预算；
- sensitivity-guided：筛查 `74` 条连接后连续接受 `25` 次删边，得到 `49` 条连接；
- 第 `26` 次删边会得到 `48` 条连接，但最大质量下降 `2.32%`，触发质量边界；
- 独立验证损耗点 `0.98, 0.85, 0.75` 的最大质量下降为 `1.80%`；
- threshold `0.150`：`49` 条连接，作为权重阈值启发式参照保留；
- random sign：质量下降约 `99.98%`，作为负对照失败。

重点解释：系统先从真实反馈中学习边的边际影响，再连续采取删边行动。质量边界、
启发式参照和随机负对照都会保留为可核验的反证。

## 4. 打开 WebUI

```bash
PYTHONPATH=src python -m arenaforge web \
  --run examples/quantum_optics_open_exploration/.arenaforge/campaigns/qo-loss-campaign-v3
```

WebUI 中应展示 Campaign 状态、候选比较、运行日志、证据、完整性状态和导出入口。

## 5. 交付说明

最终附件由以下命令构建：

```bash
PYTHONPATH=src python scripts/build_goai_submission.py
```

生成：

```text
dist/AI4R_OPEN_ArenaForge.zip
```

正式提交前，参赛团队仍需自行填写官方 4 页问题定义 PDF、团队介绍、公开仓库 URL 和 Demo URL。
