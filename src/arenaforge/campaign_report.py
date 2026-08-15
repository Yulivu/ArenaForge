"""Human-readable and portable outputs for Campaigns."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from .campaign_projection import campaign_dir, project_campaign


def write_campaign_report(path: str | Path, output: str | Path | None = None) -> Path:
    root = campaign_dir(path)
    data = project_campaign(root)
    target = Path(output).expanduser().resolve() if output else root / "REPORT.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_campaign_report(data), encoding="utf-8")
    return target


def export_campaign(path: str | Path, output: str | Path | None = None) -> Path:
    root = campaign_dir(path)
    report = write_campaign_report(root)
    target = (
        Path(output).expanduser().resolve()
        if output
        else root / "exports" / f"{data_id(root)}-reproducibility.zip"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in root.rglob("*"):
            if not item.is_file() or "exports" in item.relative_to(root).parts:
                continue
            archive.write(item, item.relative_to(root).as_posix())
        if report.name != "REPORT.md":
            archive.write(report, report.relative_to(root).as_posix())
    return target


def render_campaign_report(data: dict[str, Any]) -> str:
    protocol = data.get("protocol", {})
    candidates = data.get("candidates", [])
    recommendation = data.get("recommended_candidate")
    budget = data.get("budget", {})
    integrity = data.get("integrity", {})
    lines = [
        f"# ArenaForge 研究活动报告：{data.get('campaign_id', 'campaign')}",
        "",
        f"**项目**：`{data.get('project_name') or 'unknown'}`",
        f"**活动状态**：`{data.get('status') or 'unknown'}`",
        f"**研究问题**：{data.get('research_question') or '—'}",
        "",
        "## 研究协议",
        "",
        f"- 指标：`{protocol.get('metric') or '—'}`（{protocol.get('direction') or '—'}）",
        f"- 执行后端：`{protocol.get('backend') or '—'}`",
        f"- 随机种子：`{', '.join(str(seed) for seed in protocol.get('seeds', [])) or '—'}`",
        f"- 训练命令：`{protocol.get('train_command') or '—'}`",
        f"- 评估命令：`{protocol.get('eval_command') or '—'}`",
        "",
        "## 结论",
        "",
        (
            f"推荐方案：**{recommendation.get('label') or recommendation.get('hypothesis_id')}**，"
            f"平均分数为 `{recommendation.get('mean_score')}`。"
            if isinstance(recommendation, dict)
            else "当前没有通过协议约束的推荐方案。"
        ),
        "",
        "| 候选方案 | 状态 | 平均分数 | 相对基线变化 | 完成种子 |",
        "|---|---|---:|---:|---:|",
    ]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        lines.append(
            "| {label} | `{status}` | {score} | {improvement} | {done}/{required} |".format(
                label=_md(candidate.get("label") or candidate.get("hypothesis_id")),
                status=candidate.get("status", "planned"),
                score=_fmt(candidate.get("mean_score")),
                improvement=_fmt(candidate.get("improvement")),
                done=candidate.get("completed_seeds", 0),
                required=candidate.get("required_seeds", 0),
            )
        )
    lines.extend(
        [
            "",
            "## 完整性与结论边界",
            "",
            f"- 保护路径检查：`{integrity.get('protected_paths_clean')}`",
            f"- 无效候选方案：`{', '.join(integrity.get('invalid_candidates', [])) or '无'}`",
            f"- 运行预算：`{budget.get('used_runs', 0)}/{budget.get('max_runs', '—')}`",
            "",
            "本报告只描述已记录的项目、协议、运行与指标；它不自动证明因果关系或普适性。",
            "",
        ]
    )
    return "\n".join(lines)


def data_id(root: Path) -> str:
    value = json.loads((root / "campaign.json").read_text(encoding="utf-8"))
    return str(value.get("campaign_id") or root.name)


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _md(value: Any) -> str:
    return str(value or "—").replace("|", "\\|").replace("\n", " ")
