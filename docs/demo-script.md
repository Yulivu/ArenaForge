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

- canonical、8 个阈值剪枝候选和 random 负对照；
- fidelity 和 count rate 随 transmission 的变化；
- edge count、robust score、预算检查和质量门槛；
- `artifacts/exploration_log.jsonl` 中的逐候选记录。

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
- threshold `0.150`：`49` 条连接，最大质量下降 `1.92%`，满足协议并推荐；
- threshold `0.200`：`48` 条连接，但最大质量下降 `2.44%`，被拒绝；
- random sign：质量下降约 `99.98%`，作为负对照失败。

重点解释：系统在固定质量门槛下寻找更简单的可行拓扑。超过预算或质量容差的
候选会作为反证保留，并明确标注拒绝原因。

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
