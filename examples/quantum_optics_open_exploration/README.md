# ArenaForge Reference Arena #1：Quantum Optics

## 这是一个示例 Arena，不是产品本体

ArenaForge 是通用系统；本目录提供第一个可复现的科学环境实例：
面向高维纠缠制备的损耗鲁棒量子实验探索。

它证明 ArenaForge 可以把一个尚未结构化为标准 benchmark 的物理问题，
转成 Agent 可持续探索、评价和回放的运行闭环。

研究问题：

> 在最多 55 条实验连接、且每个损耗点的 fidelity 和 count rate 相对规范图
> 下降不超过 2% 的条件下，能否找到连接数最少的三光子、四维 GHZ 制备图？

这不是“让模型把分数调高”。Agent 必须在一个带有物理约束、资源预算和质量门槛的环境中：

```text
候选实验拓扑
  -> 光学状态模拟
  -> fidelity / count-rate / edge-count / quality-gate 反馈
  -> transmission-loss sweep
  -> 记录正结果、退化结果和失败路径
  -> 形成可复查的推荐
```

## 环境接口

### 固定部分

- 目标态：三光子四维 GHZ，`|000> + |111> + |222> + |333>`；
- 辅助光子预算：3；
- PyTheus 的图拓扑和后选择规则；
- 统一的 loss sweep：`1.0, 0.95, 0.9, 0.8, 0.7`；
- 连接数预算：最多 `55` 条；
- 质量容差：每个损耗点的 fidelity 和 count rate 相对规范图下降不超过 `2%`；
- 目标：在满足质量门槛的候选中最小化 edge count；
- 结果必须同时报告 fidelity 和 count rate。

### Agent 可探索部分

- 图中的实验连接和边权；
- 稀疏化/保留哪些连接；
- fidelity 与 count-rate 的权衡；
- 在不同 transmission level 下是否保持有效。

### Agent 观察

每一轮 Agent 看到：

- 当前候选图及其 edge count；
- canonical baseline 和历史候选的 loss-sweep 结果；
- fidelity、count rate、robust score、预算可行性和质量门槛结果；
- 当前 seed、剩余运行预算和受保护路径状态；
- 上一轮候选是 supported、refuted 还是 inconclusive，以及对应日志。

Agent 不直接看到或修改评估器内部实现；它只能通过候选训练命令或隔离分支提交新的图结构假设。

### 发现信号

以下任一项都可以形成研究信号：

- 某个拓扑在多个 loss level 下同时保持较高 fidelity 和 count rate；
- 高 fidelity 方案在损耗下系统性崩溃；
- 稀疏拓扑牺牲少量理想分数但显著提高鲁棒性；
- 常见“减少边数即可更稳”的直觉被反例推翻。
- 在明确资源预算和质量门槛下，发现连接数更少的可行拓扑。

## 运行

ArenaForge 已保存一份真实 PyTheus 优化结果作为 replay 起点。

```bash
PYTHONPATH=src python scripts/run_quantum_optics_exploration.py
```

Windows PowerShell 可使用：

```bash
$env:PYTHONPATH="src"
python scripts/run_quantum_optics_exploration.py
```

默认使用 example 内置的 `vendor/pytheus`，不需要额外下载。

## 结果

运行后生成：

- `artifacts/exploration_results.json`
- `artifacts/exploration_log.jsonl`
- `artifacts/evidence.json`
- `artifacts/ledger.jsonl`
- `artifacts/problem_certificate.json`
- 每个候选的图和边权；
- fidelity、count rate、edge count；
- transmission-loss 曲线；
- 推荐候选和研究范围。

`ledger.jsonl` 是 hash-chained 运行轨迹，`problem_certificate.json` 是对本次
replay 的 scoped 结论。当前证书明确记录：阈值 `0.150` 的候选用 49 条连接
满足 55 条预算，并且所有损耗点的质量下降不超过 2%；这不等于实验室结论。

## 诚实边界

当前损耗是可解释的 per-edge transmission proxy，不等价于实验室光学标定。
它用于构造可复查的开放探索环境和比较协议；若进入复赛，需要进一步接入
实验参数或更高保真度的光学噪声模型。

## 在 ArenaForge 中的角色

```text
ArenaForge 通用运行时
  -> Reference Arena 协议
  -> Quantum Optics 环境
  -> PyTheus 物理模拟
  -> 结构化反馈与证据证书
```

未来可以在不重写 ArenaForge 核心运行时的情况下替换为材料、生物、
小分子或机器学习科学问题环境。

## 来源与许可

- PyTheus：`third_party/pytheus/`
- PyTheus 原项目：`https://github.com/artificial-scientist-lab/PyTheus`
- PyTheus 许可证：MIT
