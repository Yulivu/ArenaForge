# ArenaForge 评委审阅指南

这份指南给第一次打开仓库的人使用。目标是在几分钟内确认产品定位、运行闭环
和当前可核验的证据。

## 1. 先看产品位置

ArenaForge 负责研究流程中的三段：

```text
研究问题
  -> 协议确认
  -> 探索执行
  -> 证据判断
  -> 论文或决策
```

用户已有研究问题和可运行环境。系统帮助用户确认比较协议、组织候选实验、
保存每次运行，并把结果交回后续研究流程。

产品页：

- <https://yulivu.github.io/ArenaForge/>
- <https://yulivu.github.io/ArenaForge/case/>

## 2. 在干净环境运行确定性示例

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

然后按照根目录 README 的分类 Campaign 命令运行一次本地闭环。这个路径不需要
模型 API，适合检查协议、候选、隔离工作区、指标、判断和 WebUI。

## 3. 检查最终产物

一次运行完成后，重点查看：

- `research_contract.json`：执行前确认的研究问题和协议；
- `experiment_plan.json`：候选假设、对照和预算；
- `runs/*/run.json`：代码、命令、环境和运行状态；
- `evidence.json` 或 evidence graph：结果如何支持或反驳假设；
- `ledger.jsonl`：按 hash 链连接的运行事件；
- `problem_certificate.json`：结论、适用范围和未能证明的内容。

检查重点是结论能否回到代码提交、命令、日志和指标，而不是只看一个最终分数。

## 4. 查看开放科学验证案例

量子科学案例位于：

`examples/quantum_optics_open_exploration/`

它提供一个没有标准排行榜的科学问题环境，包含固定规则、Agent 观察和行动、
统一损耗扫描、策略参照、负对照、搜索轨迹和结果证书。案例不代表通用产品只
服务于量子科学，它用于展示通用执行系统如何承载一类开放探索问题。

## 5. API 和远程资源边界

没有模型 API 时，可以运行确定性 Campaign、replay、证据检查和 WebUI。
配置 API 后，才会启动真实的自主研究循环。配置 SSH GPU 主机、凭据和已验证
host key 后，才可以进行真实远程执行。

仓库会把这些状态区分为已完成、可回放、待配置和被阻塞，评审可以据此判断
哪些是源码能力，哪些需要外部资源。

## 6. 开源检查

仓库包含：

- Python 源码、schema、测试和可运行示例；
- Web 产品页源代码和构建配置；
- 真实示例的运行产物；
- 第三方代码、许可证和归属说明；
- 构建提交包的脚本。

提交包构建：

```bash
python scripts/build_submission.py
```

生成目录：

`dist/ArenaForge-submission/`

这个目录应当能作为赛委会离线审阅和复现的入口。
