#!/usr/bin/env python3
"""校验知识点讲解 HTML 幻灯片是否符合 references/deck-contract.md。

用法:
    python3 scripts/check_deck.py work/<slug>/<slug>.html
    python3 scripts/check_deck.py work/<slug>/<slug>.html --min-pages 8 --max-pages 12
    python3 scripts/check_deck.py work/<slug>/<slug>.html --skip-docx

退出码: 0 通过；1 有 error（warning 不影响退出码）。
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

# ---- 规则常量 -------------------------------------------------------------

MIN_PAGES = 8
MAX_PAGES = 12
MIN_BODY_PX = 20
MIN_ANY_PX = 18
MIN_PITFALLS = 3
MIN_DETAILS = 3

TITLE_BANNED = ["介绍", "概述", "简介", "小结", "总结", "谢谢", "欢迎提问", "Q&A", "目录", "参考文献"]
GLOBAL_BANNED = ["谢谢观看", "谢谢聆听", "欢迎提问", "你学到了什么", "Q&A", "感谢聆听"]
DERIVATION_CHAIN = ["两边取对数", "代入整理得", "移项得", "两边求导得", "整理可得"]

SLIDE_RE = re.compile(
    r"(<section\b[^>]*class\s*=\s*\"[^\"]*\bslide\b[^\"]*\"[^>]*>)(.*?)</section>",
    re.S,
)
PAGE_ATTR_RE = re.compile(r"data-page\s*=\s*\"(\d+)\"")
EQ_ATTR_RE = re.compile(r"data-eq\s*=\s*\"(\d+)\"")
H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.S)
TAG_RE = re.compile(r"<[^>]+>")

RESOURCE_RE = re.compile(
    r"<(?:img|script|link|iframe|source|video|audio)\b[^>]*(?:src|href)\s*=\s*[\"'](https?:)?//",
    re.I,
)
CSS_URL_RE = re.compile(r"url\(\s*[\"']?(https?:)?//", re.I)
CSS_IMPORT_RE = re.compile(r"@import", re.I)
FONT_SIZE_RE = re.compile(r"font-size\s*:\s*([\d.]+)\s*px", re.I)
BODY_FONT_RE = re.compile(r"(?:^|[\s,}])body\s*\{([^}]*)\}", re.I | re.S)


class Report:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []

    def error(self, rule: str, message: str) -> None:
        self.items.append(("error", rule, message))

    def warn(self, rule: str, message: str) -> None:
        self.items.append(("warning", rule, message))

    def ok(self, rule: str) -> None:
        self.items.append(("ok", rule, ""))

    @property
    def errors(self) -> int:
        return sum(1 for level, _, _ in self.items if level == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for level, _, _ in self.items if level == "warning")


def text_of(fragment: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", fragment)).strip()


# ---- 各段检查 -------------------------------------------------------------


def check_structure(
    html: str, slides: list[tuple[str, str]], report: Report, min_pages: int, max_pages: int
) -> list[int]:
    count = len(slides)
    if count == 0:
        report.error("结构", "没有找到 <section class=\"slide\">，无法解析页")
        return []
    if not (min_pages <= count <= max_pages):
        report.error("页数", f"{count} 页，要求 {min_pages}–{max_pages} 页")
    else:
        report.ok("页数")

    pages: list[int] = []
    for index, (open_tag, _) in enumerate(slides, start=1):
        match = PAGE_ATTR_RE.search(open_tag)
        if not match:
            report.error("结构", f"第 {index} 个 section 缺 data-page")
            pages.append(index)
            continue
        value = int(match.group(1))
        pages.append(value)
        if value != index:
            report.error("结构", f"data-page 不连续：第 {index} 个 section 写着 {value}")

    for index, (_, body) in enumerate(slides, start=1):
        h1 = H1_RE.search(body)
        title = text_of(h1.group(1)) if h1 else ""
        if not title:
            report.error("标题", f"第 {index} 页缺非空 <h1>")
            continue
        for word in TITLE_BANNED:
            if word in title:
                report.error("标题", f"第 {index} 页标题含「{word}」：标题要写结论句，不是话题名 → {title}")
                break
    return pages


def check_banned(html: str, report: Report) -> None:
    hit = False
    for word in GLOBAL_BANNED:
        if word in html:
            report.error("禁用词", f"出现「{word}」")
            hit = True
    if not hit:
        report.ok("禁用词")

    chain_hit = False
    for phrase in DERIVATION_CHAIN:
        if phrase in html:
            report.error("推导链", f"出现「{phrase}」：推导属于 docx，幻灯片只留结果")
            chain_hit = True
    if not chain_hit:
        report.ok("推导链")

    if re.search(r"^\s*[-*]\s*注意", html, re.M):
        report.warn("易错点", "出现「注意 XX」式条目：必须写成 错误做法/现象/正确做法 三段式")


def check_pitfalls(html: str, report: Report) -> None:
    counts = {key: html.count(key) for key in ("错误做法", "现象", "正确做法")}
    if min(counts.values()) < MIN_PITFALLS:
        report.error(
            "易错点",
            f"三段式不足：{counts}，每项至少 {MIN_PITFALLS} 条",
        )
    else:
        report.ok("易错点")


def check_formulas(slides: list[tuple[str, str]], report: Report) -> set[int]:
    numbers: list[int] = []
    for index, (_, body) in enumerate(slides, start=1):
        found = [int(value) for value in EQ_ATTR_RE.findall(body)]
        if len(found) > 1:
            report.error("公式", f"第 {index} 页有 {len(found)} 条公式，每页最多 1 条")
        numbers.extend(found)

    if not numbers:
        report.warn("公式", "全篇没有 data-eq 公式：确认是否真的不需要公式")
        return set()

    expected = list(range(1, len(numbers) + 1))
    if sorted(numbers) != expected:
        report.error("公式", f"式号不连续：得到 {sorted(numbers)}，应为 1..{len(numbers)}")
    else:
        report.ok("公式")
    return set(numbers)


def check_last_page(slides: list[tuple[str, str]], report: Report) -> None:
    if not slides:
        return
    body = slides[-1][1]
    count = len(re.findall(r"<details\b", body))
    if count < MIN_DETAILS:
        report.error("自测", f"末页只有 {count} 个 <details>，至少 {MIN_DETAILS} 道可折叠答案")
    else:
        report.ok("自测")


def check_offline(html: str, report: Report) -> None:
    problems: list[str] = []
    for match in RESOURCE_RE.finditer(html):
        problems.append(match.group(0)[:80])
    if CSS_URL_RE.search(html):
        problems.append("CSS url(https://…)")
    if CSS_IMPORT_RE.search(html):
        problems.append("@import")
    if problems:
        for problem in problems[:5]:
            report.error("离线", f"外部资源：{problem}")
    else:
        report.ok("离线")


def check_css(html: str, report: Report) -> None:
    if not re.search(r"overflow\s*:\s*hidden", html, re.I):
        report.error("布局", "缺 overflow: hidden（会出现滚动条）")
    if not re.search(r"100(?:d)?vh", html):
        report.error("布局", "缺 100vh（1 页 1 屏）")
    if re.search(r"overflow\s*:\s*(auto|scroll)", html, re.I) and not re.search(
        r"overflow\s*:\s*hidden", html, re.I
    ):
        report.warn("布局", "出现 overflow: auto/scroll")

    body_match = BODY_FONT_RE.search(html)
    base = None
    if body_match:
        size = FONT_SIZE_RE.search(body_match.group(1))
        if size:
            base = float(size.group(1))
    if base is None:
        report.warn("字号", "没能从 body 规则里读出 font-size，人工确认正文 ≥20px")
    elif base < MIN_BODY_PX:
        report.error("字号", f"body font-size {base:g}px < {MIN_BODY_PX}px")

    small = [float(value) for value in FONT_SIZE_RE.findall(html)]
    tiny = [value for value in small if value < MIN_ANY_PX]
    if tiny:
        report.error("字号", f"出现 {min(tiny):g}px 字号（下限 {MIN_ANY_PX}px）")
    elif base is not None and base >= MIN_BODY_PX:
        report.ok("字号")


def check_nav(html: str, report: Report) -> None:
    missing = [
        name
        for name, pattern in (
            ("ArrowRight", r"ArrowRight"),
            ("ArrowLeft", r"ArrowLeft"),
            ("wheel", r"wheel"),
        )
        if not re.search(pattern, html)
    ]
    if missing:
        report.error("翻页", f"缺键盘/滚轮翻页：{', '.join(missing)}")
    else:
        report.ok("翻页")


def check_docx(html_path: Path, eq_numbers: set[int], report: Report) -> None:
    docx = html_path.with_name(f"{html_path.stem}-公式推导.docx")
    if not docx.is_file():
        report.error("docx", f"缺 {docx.name}：缺 docx 视为整单未交付")
        return

    try:
        with zipfile.ZipFile(docx) as archive:
            xml = archive.read("word/document.xml").decode("utf-8", "replace")
    except (KeyError, zipfile.BadZipFile) as exc:
        report.error("docx", f"读不出正文 XML：{exc}")
        return

    plain = text_of(xml)
    found = {int(value) for value in re.findall(r"式\s*[（(]?\s*(\d+)\s*[）)]?", plain)}
    if not found:
        report.error("docx", "docx 里找不到「式 (N)」编号，无法与幻灯片对应")
        return
    missing = sorted(eq_numbers - found)
    extra = sorted(found - eq_numbers) if eq_numbers else []
    if missing:
        report.error("docx", f"docx 缺幻灯片上的式号：{missing}")
    if extra:
        report.warn("docx", f"docx 多出幻灯片没有的式号：{extra}")
    if not re.search(r"假设|近似条件|A1", plain):
        report.warn("docx", "没找到假设/近似条件章节（要求文首单列 A1、A2…）")
    if not missing:
        report.ok("docx")


def check_shots(html_path: Path, pages: list[int], report: Report) -> None:
    shots = html_path.parent / "shots"
    if not shots.is_dir():
        report.warn("截图", "缺 shots/ 目录：验收 G 要求每页缩略截图")
        return
    images = [p for p in shots.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    if len(images) < len(pages):
        report.warn("截图", f"shots/ 只有 {len(images)} 张，页数 {len(pages)}")
    else:
        report.ok("截图")


# ---- 主流程 ---------------------------------------------------------------


COLOR = sys.stdout.isatty() and sys.platform != "win32"


def paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def main() -> int:
    parser = argparse.ArgumentParser(description="校验知识点讲解 HTML 幻灯片")
    parser.add_argument("html", help="幻灯片 HTML 路径")
    parser.add_argument("--min-pages", type=int, default=MIN_PAGES)
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    parser.add_argument("--skip-docx", action="store_true", help="不检查推导 docx")
    parser.add_argument("--skip-shots", action="store_true", help="不检查截图")
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.is_file():
        print(f"找不到文件: {html_path}")
        return 1

    html = html_path.read_text(encoding="utf-8", errors="replace")
    slides = [(m.group(1), m.group(2)) for m in SLIDE_RE.finditer(html)]
    report = Report()

    pages = check_structure(html, slides, report, args.min_pages, args.max_pages)
    check_banned(html, report)
    check_pitfalls(html, report)
    eq_numbers = check_formulas(slides, report)
    check_last_page(slides, report)
    check_offline(html, report)
    check_css(html, report)
    check_nav(html, report)
    if not args.skip_docx:
        check_docx(html_path, eq_numbers, report)
    if not args.skip_shots:
        check_shots(html_path, pages, report)

    print(f"检查: {html_path}")
    for level, rule, message in report.items:
        if level == "ok":
            print(f"  {paint('✓', '32')} {rule}")
        elif level == "warning":
            print(f"  {paint('!', '33')} {rule}: {message}")
        else:
            print(f"  {paint('✗', '31')} {rule}: {message}")

    print()
    summary = f"{len(pages)} 页，{report.errors} 个错误，{report.warnings} 个警告"
    if report.errors == 0:
        print(paint(f"通过：{summary}", "32"))
        return 0
    print(paint(f"未通过：{summary}", "31"))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
