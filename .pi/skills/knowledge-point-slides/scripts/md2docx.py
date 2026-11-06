#!/usr/bin/env python3
"""Markdown（含 LaTeX 公式）转 Word 推导文档。

优先用项目内 pandoc（tools/pandoc/bin/pandoc），得到 Word 原生公式（可编辑、可编号）；
找不到时降级为 python-docx，公式以 Unicode 文本插入，并在文首注明不可编辑。

用法:
    python3 scripts/md2docx.py work/<slug>/<slug>-公式推导.md work/<slug>/<slug>-公式推导.docx
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def find_pandoc() -> Path | None:
    """按「技能自带 → 逐级上溯的项目 → PATH」顺序找 pandoc。

    技能被搬到别的项目后，仍能找到那个项目的 tools/pandoc/。
    """
    candidates: list[Path] = [SKILL_DIR / "tools" / "pandoc" / "bin" / "pandoc"]
    for ancestor in SKILL_DIR.parents:
        candidates.append(ancestor / "tools" / "pandoc" / "bin" / "pandoc")
        candidates.append(ancestor / "tools" / "pandoc" / "pandoc")
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_mode & 0o111:
            return candidate
    found = shutil.which("pandoc")
    return Path(found) if found else None


def convert_with_pandoc(pandoc: Path, src: Path, dst: Path) -> None:
    command = [
        str(pandoc),
        str(src),
        "--from",
        "markdown+tex_math_dollars+pipe_tables+implicit_figures",
        "--to",
        "docx",
        "--output",
        str(dst),
        "--resource-path",
        str(src.parent),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"pandoc 退出码 {result.returncode}")


def convert_with_python_docx(src: Path, dst: Path) -> None:
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(f"缺少 python-docx：pip install python-docx（原始错误：{exc}）")

    document = Document()
    note = document.add_paragraph()
    run = note.add_run("说明：本文件由 python-docx 生成（未找到 pandoc），公式为 Unicode 文本，不可编辑。")
    run.italic = True
    run.font.size = Pt(9)

    for raw in src.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line:
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            document.add_heading(heading.group(2).strip(), level=len(heading.group(1)))
            continue
        bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet:
            document.add_paragraph(clean_inline(bullet.group(1)), style="List Bullet")
            continue
        numbered = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if numbered:
            document.add_paragraph(clean_inline(numbered.group(1)), style="List Number")
            continue
        if line.strip() in {"---", "***"}:
            document.add_paragraph("─" * 40)
            continue
        document.add_paragraph(clean_inline(line))

    document.save(dst)


def clean_inline(text: str) -> str:
    """去掉 markdown 标记，$…$ 保留为 Unicode 文本。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\$([^$]+)\$", r"\1", text)
    return text.strip()


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip())
        return 1

    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    if not src.is_file():
        print(f"找不到输入文件: {src}")
        return 1
    dst.parent.mkdir(parents=True, exist_ok=True)

    pandoc = find_pandoc()
    if pandoc:
        try:
            convert_with_pandoc(pandoc, src, dst)
            print(f"pandoc {pandoc}\n  {src} -> {dst}（Word 原生公式）")
            return 0
        except RuntimeError as exc:
            print(f"pandoc 转换失败，降级为 python-docx：{exc}")

    convert_with_python_docx(src, dst)
    print(f"python-docx\n  {src} -> {dst}（公式为文本，不可编辑）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
