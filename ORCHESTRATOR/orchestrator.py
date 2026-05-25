#!/usr/bin/env python3
"""
Minimal file-based orchestrator for MCR.

This first version does not call Codex, Hermes, Claude, GitHub, or any network
API. It turns inbox.md into task files that a human or later runner can consume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "inbox.md"
TASKS = ROOT / "tasks.json"
DISPATCH = ROOT / "dispatch.md"
REPORTS = ROOT / "reports.md"


@dataclass(frozen=True)
class Task:
    id: str
    assignee: str
    goal: str
    input_files: list[str]
    expected_output: str
    status: str = "pending"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(text: str, assignee: str, index: int) -> str:
    digest = hashlib.sha1(f"{assignee}:{index}:{text}".encode("utf-8")).hexdigest()
    return f"T-{digest[:8]}"


def read_inbox(path: Path) -> list[str]:
    if not path.exists():
        return []

    items: list[str] = []
    current: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                items.append(" ".join(current).strip())
                current = []
            continue
        if line.startswith("#"):
            continue
        if line.startswith(">"):
            line = line.lstrip("> ").strip()
        if line.startswith(("-", "*")):
            line = line.lstrip("-* ").strip()
        if line in {"把新需求写在这里。每个任务用一行或一个短段落即可。"}:
            continue
        current.append(line)

    if current:
        items.append(" ".join(current).strip())

    return [item for item in items if item]


def infer_input_files(request: str) -> list[str]:
    text = request.lower()
    files = ["ORCHESTRATOR/inbox.md"]

    if "access_history" in text:
        files.extend(
            [
                "runtime/",
                "tests/test_g2_replay.py",
                "tests/test_event_gate.py",
            ]
        )
    if "readme" in text or "文档" in request:
        files.append("README.md")
    if "抖音" in request or "素材" in request:
        files.extend(["docs/", "releases/"])
    if "github" in text or "commit" in text or "push" in text:
        files.append(".git/")

    return list(dict.fromkeys(files))


def split_request(request: str) -> list[tuple[str, str, str]]:
    lowered = request.lower()
    includes_code = any(
        token in lowered
        for token in ["mcr", "access_history", "cap", "runtime", "代码", "测试"]
    )
    includes_docs = any(token in lowered for token in ["readme", "文档", "说明"])
    includes_media = any(token in request for token in ["抖音", "素材", "短视频", "发布"])

    assignments: list[tuple[str, str, str]] = []

    if includes_code:
        assignments.append(
            (
                "codex",
                f"实现并最小化修改代码以完成需求：{request}",
                "代码补丁，保持 G2 replay 和 event gate 约束不破坏。",
            )
        )
        assignments.append(
            (
                "hermes",
                f"运行验证并准备提交：{request}",
                "测试结果、git diff 摘要、commit/push 状态建议。",
            )
        )
    else:
        assignments.append(
            (
                "codex",
                f"拆解并执行本地文件任务：{request}",
                "可检查的文件变更或明确的阻塞说明。",
            )
        )

    assignments.append(
        (
            "claude",
            f"审查需求、风险和说明文档是否一致：{request}",
            "审查意见，重点列出风险、遗漏测试和 README 修改建议。",
        )
    )

    assignments.append(
        (
            "human",
            f"确认调度结果是否符合真实意图：{request}",
            "批准、改写或取消该任务。",
        )
    )

    assignments.append(
        (
            "github",
            f"在实现和验证完成后提交并推送：{request}",
            "commit hash、push 结果、PR 或分支状态。",
        )
    )

    if includes_docs:
        assignments.append(
            (
                "claude",
                f"整理 README 或用户文档：{request}",
                "README 更新建议或文档补丁。",
            )
        )

    if includes_media:
        assignments.append(
            (
                "human",
                f"准备抖音素材 brief：{request}",
                "标题、口播要点、画面素材清单和发布检查表。",
            )
        )

    return assignments


def build_tasks(requests: Iterable[str]) -> list[Task]:
    tasks: list[Task] = []
    for request in requests:
        input_files = infer_input_files(request)
        for assignee, goal, expected in split_request(request):
            tasks.append(
                Task(
                    id=stable_id(goal, assignee, len(tasks) + 1),
                    assignee=assignee,
                    goal=goal,
                    input_files=input_files,
                    expected_output=expected,
                )
            )
    return tasks


def write_tasks(tasks: list[Task], requests: list[str]) -> None:
    payload = {
        "generated_at": now_iso(),
        "source": "inbox.md",
        "requests": requests,
        "tasks": [asdict(task) for task in tasks],
    }
    TASKS.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_dispatch(tasks: list[Task]) -> None:
    by_assignee: dict[str, list[Task]] = {}
    for task in tasks:
        by_assignee.setdefault(task.assignee, []).append(task)

    lines = ["# Dispatch", "", f"Generated: {now_iso()}", ""]
    for assignee in ["codex", "hermes", "claude", "github", "human"]:
        assigned = by_assignee.get(assignee, [])
        if not assigned:
            continue
        lines.extend([f"## {assignee}", ""])
        for task in assigned:
            lines.extend(
                [
                    f"### {task.id}",
                    "",
                    f"- status: {task.status}",
                    f"- goal: {task.goal}",
                    f"- input_files: {', '.join(task.input_files)}",
                    f"- expected_output: {task.expected_output}",
                    "",
                ]
            )

    DISPATCH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_reports(tasks: list[Task], requests: list[str]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    counts: dict[str, int] = {}
    for task in tasks:
        counts[task.assignee] = counts.get(task.assignee, 0) + 1

    lines = [
        "# Reports",
        "",
        f"## {today}",
        "",
        f"- inbox_requests: {len(requests)}",
        f"- generated_tasks: {len(tasks)}",
        "- status: dispatch generated, execution not started",
        "",
        "### By assignee",
        "",
    ]
    for assignee in sorted(counts):
        lines.append(f"- {assignee}: {counts[assignee]}")

    lines.extend(
        [
            "",
            "### Next",
            "",
            "- Human reviews dispatch.md.",
            "- Selected assignees execute their tasks manually or through a future runner.",
            "- Execution results are appended back into reports.md.",
        ]
    )

    REPORTS.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run() -> int:
    requests = read_inbox(INBOX)
    tasks = build_tasks(requests)
    write_tasks(tasks, requests)
    write_dispatch(tasks)
    write_reports(tasks, requests)
    print(f"requests={len(requests)} tasks={len(tasks)}")
    print(f"wrote={TASKS.name},{DISPATCH.name},{REPORTS.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MCR orchestration files.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run using the current inbox.md example task.",
    )
    parser.parse_args()
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
