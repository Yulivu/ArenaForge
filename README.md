# ArenaForge

ArenaForge 是一个面向开放科学问题的研究执行系统。

它接住研究流程中最难稳定复用的一段：

```text
研究问题
  -> 协议确认
  -> 候选探索
  -> 受控执行
  -> 证据判断
  -> 论文或决策
```

研究者提供一个真实问题、一个可运行项目或模拟器，以及希望验证的目标。
ArenaForge 会把问题整理成可确认的研究协议，组织 Agent 提出的候选假设，
在隔离工作区中执行实验，统一比较结果，并输出带有代码、命令、日志、指标
和适用范围的研究材料。

## 先看产品

- 产品页：<https://yulivu.github.io/ArenaForge/>
- 验证案例：<https://yulivu.github.io/ArenaForge/case/>

产品页回答“它解决什么问题”；本仓库回答“它如何运行、如何复现、当前边界是什么”。

## 三分钟审阅路径

评委或新贡献者可以按下面顺序阅读：

1. [产品工作流](docs/product-workflow.md)：用户输入什么，系统做什么，最后得到什么。
2. [架构说明](docs/architecture.md)：Study、Campaign、执行后端和证据层如何连接。
3. [通用分类示例](examples/ml_classification/README.md)：最短的本地闭环。
4. [量子科学验证案例](examples/quantum_optics_open_exploration/README.md)：开放探索环境中的完整运行事实。
5. [委员会审阅指南](docs/committee-review.md)：从干净环境启动、验证和检查产物。
6. [GOAI 交付清单](docs/goai-deliverables.md)：比赛提交材料与当前状态。

## 解决的具体问题

科研项目通常已经有研究问题和可运行代码，困难出现在后续执行阶段：

- 候选方案、代码版本和实验条件不断增加，结果难以对应；
- 不同实验使用了不同的数据划分、指标或资源条件，分数不能直接比较；
- 失败实验、反例和停止原因没有被保留，最后只剩一条最好结果；
- 论文或组内决策需要重新整理实验上下文，复核成本很高。

ArenaForge 将这些工作组织成一个 **Study**。Study 的持久化执行对象是
**Experiment Campaign**，它包含协议、候选、运行、证据、判断和复现材料。
系统的重点是让一个研究结论可以回到：

```text
结论
  -> 证据
  -> 指标和约束检查
  -> 命令与日志
  -> 代码提交和运行环境
```

它不替代研究者提出科学问题，也不替代论文写作。它负责把已经值得研究的问题
推进成一套可运行、可比较、可复查的实验结果。

## 一次运行的输入与输出

### 用户输入

最小输入只有三类：

1. **项目**：已有 ML 仓库、科学模拟器或其他可执行环境；
2. **研究问题**：希望验证的具体判断；
3. **评价目标**：指标和方向，或允许系统从项目中提出候选后确认。

例如：

```text
项目：examples/ml_classification
问题：哪种正则化策略能稳定提高保留集准确率？
约束：不能修改 eval.py 和数据
目标：最大化 held-out accuracy
```

系统会扫描项目并提出训练命令、评估命令、baseline、数据划分、可修改路径、
保护路径、种子、预算和停止条件。高影响字段必须在执行前确认，不会静默猜测。
普通 Python ML 项目不需要手写 ArenaForge 专用 adapter。

### 系统输出

一次完成的 Study 至少包含：

- 研究简报和已确认协议；
- baseline、候选假设和每个候选的代码差异；
- 分支、commit、工作区、命令、日志和环境指纹；
- 开发集与保留集指标；
- 支持、反驳、证据不足、无效和失败记录；
- evidence graph、hash-chained ledger 和 problem certificate；
- 可重新打开的 WebUI 和可复现结果包。

## 最短本地闭环

环境要求：

- Python `>=3.10`
- Git
- 项目自身的 Python 依赖

安装并运行测试：

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

运行内置分类 Campaign：

```bash
python -m arenaforge campaign-create \
  --project examples/ml_classification \
  --campaign-id classification-campaign \
  --question "哪种正则化策略能稳定提高保留集准确率？" \
  --metric score \
  --seeds 17,27,37 \
  --max-runs 12

python -m arenaforge campaign-plan \
  --campaign examples/ml_classification/.arenaforge/campaigns/classification-campaign \
  --candidates examples/campaign_candidates.example.json

python -m arenaforge campaign-run \
  --campaign examples/ml_classification/.arenaforge/campaigns/classification-campaign

python -m arenaforge web \
  --run examples/ml_classification/.arenaforge/campaigns/classification-campaign
```

这条路径不需要模型 API。它用于验证协议、隔离执行、指标比较、证据记录和
WebUI 回放。

## 自主研究路径

配置模型 API 后，Agent 可以参与研究简报、假设生成和候选推进：

```bash
python -m arenaforge research-run \
  --project examples/ml_classification \
  --run-id classification-research \
  --max-cycles 3 \
  --max-turns 40 \
  "Improve held-out classification accuracy without changing eval.py or data."
```

原生 provider 或 OpenAI-compatible endpoint：

```bash
python -m arenaforge research-run \
  --project examples/ml_classification \
  --provider openai-responses \
  --model gpt-4o \
  --base-url "$OPENAI_BASE_URL" \
  --api-key "$OPENAI_API_KEY" \
  "Improve held-out classification accuracy."
```

API 凭据只从命令行环境或本地配置读取，不提交到仓库。没有 API 时，系统仍然
可以运行确定性示例、打开已保存运行、检查 ledger、查看证据和导出结果。

## 远程执行

SSH GPU 后端负责准备 manifest、远程任务目录、日志、状态和结果回收。
它不会在没有主机、凭据和已验证 host key 的情况下假装完成远程实验。

```text
本地协议
  -> 资源预检
  -> SSH manifest
  -> 远程任务 / GPU 队列
  -> 状态与日志回收
  -> 本地证据汇总
```

相关命令和配置见：

- `docs/reproducibility.md`
- `docs/architecture.md`
- `examples/queue_config.example.yaml`

## 仓库结构

```text
src/arenaforge/              Python 产品运行时、CLI、证据和队列
schemas/                     contract、evidence、ledger、certificate 等 schema
examples/ml_classification/  通用 ML 分类闭环
examples/ml_regression/      通用 ML 回归闭环
examples/quantum_optics.../  开放科学验证环境与真实 replay 产物
evidence/                    已核验的运行证据
docs/                        产品、架构、复现和比赛材料
web/                         Astro 产品展示站
scripts/                     构建、快照、验证和提交包脚本
third_party/                 第三方代码与许可证归档
tests/                       Python 单元和集成测试
```

## 当前验证范围

仓库当前可直接验证：

- 分类和回归项目的本地多候选、多 seed 执行；
- Git worktree 隔离，以及非 Git 项目的复制工作区回退；
- 保护路径检查和协议违规拦截；
- supported、refuted、inconclusive、invalid 等确定性判断；
- 运行日志、代码差异、指标、预算和环境记录；
- evidence graph、ledger hash 链、problem certificate；
- WebUI 的协议、候选、运行、证据、报告和导出视图；
- SSH/HPC manifest、preflight、resume、pull 和 aggregation 接口；
- 没有 API 时的 replay 和离线证据检查。

仍需要外部资源才能验证的能力：

- 真实模型 API 驱动的自主研究循环；
- 真实 SSH GPU 主机上的提交、断线恢复和结果回收；
- 公开部署环境中的在线运行。

这些边界会在运行状态和文档中明确显示，仓库不把接口存在写成外部实验已经完成。

## 验证案例

`examples/quantum_optics_open_exploration/` 提供一个完整的开放科学环境：
在固定质量门槛和损耗条件下，探索更简单的高维纠缠制备图。

它的作用是验证 ArenaForge 能否组织一个没有标准榜单的科学探索问题：

```text
问题和环境
  -> 固定比较协议
  -> 边际影响筛查、阈值策略和随机负对照
  -> 统一损耗扫描
  -> 保留正结果、失败边界和独立复核
  -> 生成证据与结果证书
```

该目录中的运行记录、搜索轨迹、ledger 和 certificate 都是仓库的一部分。
案例的科学结论只适用于声明的模拟环境、损耗代理模型和评价协议。

## 开源与第三方边界

- [贡献规范](CONTRIBUTING.md)
- [第三方与数据说明](docs/third-party-and-data-notices.md)
- [上游运行时许可证](third_party/upstream-runtime/LICENSE)
- [网页展示层归属说明](web/NOTICE)

ArenaForge 的产品扩展、示例和文档与第三方依赖分开管理。第三方代码、许可证、
归属和修改边界保留在仓库中；API 密钥、个人数据和运行缓存不进入版本库。

## 构建提交包

```bash
python scripts/build_submission.py
```

脚本会在干净临时目录中运行内置分类和回归示例，检查证书和 ledger，
并生成 `dist/ArenaForge-submission/`。提交包不包含 API 凭据、运行缓存或
用户本地工作区。

比赛材料只在 `docs/` 和 `deliverables/` 中维护，公开产品页不承载内部提交说明。
