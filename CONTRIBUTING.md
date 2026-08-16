# 贡献 ArenaForge

感谢参与 ArenaForge。提交代码前，请先确认改动属于产品运行时、示例环境、
证据格式、网页展示层或文档中的哪一层，避免把案例专用逻辑写进通用执行层。

## 开始之前

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

网页改动需要：

```bash
cd web
npm ci
npm run check
npm run build
```

## 提交要求

- 新功能必须说明用户输入、系统行为和输出产物；
- 运行逻辑改动需要增加或更新测试；
- 证据、ledger、certificate 的字段改动必须同步更新 schema 和文档；
- 不提交 API key、SSH 私钥、个人数据、运行缓存或临时工作区；
- 示例中的科学结论必须与保存的运行产物一致；
- 第三方代码或机制引用必须更新 `docs/third-party-and-data-notices.md`；
- 页面文案保持中文、直接、可验证，不把内部实现名当作用户概念。

## 改动边界

`src/arenaforge/` 是产品扩展层。新的科学环境优先放进
`examples/` 或可选 plugin，不要为单个案例修改通用判断逻辑。

`web/` 是公开产品展示层。它可以解释产品和验证案例，但不应泄露凭据、
内部运行缓存或未验证的外部执行结果。

## Pull Request 自检

提交前至少运行：

```bash
python -m pytest -q
python scripts/build_submission.py
git diff --check
```

如果修改了 `web/`，再运行 `npm run check` 和 `npm run build`。
Pull Request 描述需要包含：改动目的、验证命令、是否改变输出格式、是否涉及
第三方代码或许可证。
