#!/usr/bin/env python3
"""校验知识点讲解 HTML 幻灯片是否符合 references/deck-contract.md。

用法:
    python3 scripts/check_deck.py work/<slug>/<slug>.html
    python3 scripts/check_deck.py work/<slug>/<slug>.html --max-anim 3
    python3 scripts/check_deck.py work/<slug>/<slug>.html --max-eq 4      # 需要时手动设上限

退出码: 0 通过；1 有 error（warning 不影响退出码）。

检查分两层：
  · 形式层（页码可见、字号、离线、翻页、体积）
  · 语义层（坐标系一致性、几何标注方向、式图绑定、页预算、HTML 内推导）
  · 公式预备段（公理清单 + P 式）：C1 孤儿符号闭包 / C2 被用到与冗余 /
    C3 版式 / C4 公理链完整 / C5 公理清单合规，独立在 check_formula_section()
语义层规则全部是「声明式」的：脚本不认识具体学科的量，只比对
figure 的 data-x / data-y / data-xscale / data-yscale 声明、公式里的
<var data-sym>、标注上的 data-span，以及页面自己的 data-kind / data-eq / data-used-in。

页数不设上下限：预备段长度 = 从终点量到停点的链长，正文长度 = 算例走完所需页数。
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
from pathlib import Path

# ---- 规则常量 -------------------------------------------------------------

MIN_PAGES = 1  # 页数不设上下限；S3 只要求 calc 占比 ≥ 50%
MAX_PAGES = 999
MIN_BODY_PX = 20
MIN_ANY_PX = 18
MIN_PITFALLS = 3
MAX_EQ = 0  # 0 = 不设上限（「全篇核心式 ≤3 条」已取消）；需要时用 --max-eq 手动收紧
MAX_ANIM = 3  # 动画页上限
MAX_HTML_KB = 320  # 超过就提示改用「数据 + 渲染函数」
MAX_INLINE_POINTS = 2400  # 单条 polyline 的坐标串长度上限

# 没有自测/例题页：末页是结论页，页角色只剩这五种
KINDS = {"axioms", "formula", "origin", "theory", "calc", "pitfall"}  # summary（结论页）已取消
# 公式预备段：第 1 页公理清单（axioms），随后每条 P 一页（formula）
PREP_EQ_RE = re.compile(r"^P(\d+)$")
AXIOM_ITEM_RE = re.compile(
    r"<li\b([^>]*?data-axiom\s*=\s*\"(A\d+)\"[^>]*)>(.*?)</li>", re.S | re.I
)
AXIOM_ID_RE = re.compile(r"(?<![\w])A\d+(?!\d)")
AXIOM_EQ_RE = re.compile(r"<span\b[^>]*class=\"[^\"]*\beq\b[^\"]*\"[^>]*>(.*?)</span>", re.S | re.I)
AXIOM_NOTE_RE = re.compile(r"<span\b[^>]*class=\"[^\"]*\bnote\b[^\"]*\"[^>]*>(.*?)</span>", re.S | re.I)
AXIOM_TAGS = ("定义", "约定", "定律", "经验事实")
AXIOM_TAG_BANNED = ["教科书结论", "已知结论", "显然", "由…可知", "由…推得"]
AXIOM_APPROX = ["较大时", "较小时", "忽略", "可略", "近似"]
# C6：幻灯片页面上禁止元话语（关于本文档怎么组织 / 讲解者做了什么）
META_BANNED = [
    "开讲前",
    "本文档",
    "不再假设",
    "为了讲清楚",
    "本节只",
    "后面会",
    "接下来我们",
    "不在这几条里",
    "先钉死",
    "请记住",
    "需要说明的是",
]
# C7c：真实变换（取对数 / 引入近似 / 相减 / 与 A 对照定系数）；只有「代数/数值/换单位」不算
REAL_TRANSFORM_RE = re.compile(r"近似|取对数|自然对数|换底|相减|两点|差商|对照|系数|除以|消去|消掉|积分|极限")
# 符号 token：希腊字母单字 + ASCII 标识符（含下标）
SYM_TOKEN_RE = re.compile(r"[ηκλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ]|[A-Za-z][A-Za-z0-9_₀-₉]*")
# C4：这些词一律不许用来跳步（全篇生效）
STEP_BANNED = [
    ("由式", "不许用「由式 (N) 得」跳步：把第 N 式的内容直接写出来再往下推"),
    ("由 P", "预备段内部不许用「由 P1 得 P2」代替推理；正文引用 P 号写「依据：P3」"),
    ("由上可知", "不许用「由上可知」跳步"),
    ("显然", "不许用「显然」跳步"),
    ("易得", "不许用「易得」跳步"),
    ("已知结论", "不许把推论当公理（「已知结论」）"),
]
# 预备段每步的依据只许是这些来源
STEP_BASIS_OK = re.compile(r"A\d+|代数|量纲|近似|定义|约定|数值|误差|边界|条件|定律|经验事实")

# 「只有换了坐标系才看得见」的词：出现即要求本页纵轴是对数轴
PHENOMENON = ["变平", "弯曲", "偏离直线", "拐点", "线性区"]

# 出现这些操作词，本页必须有一条给出该操作定义式的公式
OPERATIONS = ["补偿", "外推", "换算", "折算", "归一化", "校正"]

TITLE_BANNED = ["介绍", "概述", "简介", "小结", "总结", "谢谢", "欢迎提问", "Q&A", "目录", "参考文献"]
# 结论页已取消：末页标题不许是「结论 / 小结 / 总结 / 综上 / 回顾」
LAST_TITLE_BANNED = ["结论", "小结", "总结", "综上", "回顾", "学到"]
# 推导里禁止用「由式 (N) 得」代替推理，禁止解释符号含义
DERIV_BANNED = [
    ("由式", "推导不能靠「由式 (N) 得」：把这一步从定义 / 物理前提重新写出来"),
    ("由 (", "推导不能靠「由 (N.k)」：同上，重写这一步的推理"),
    ("其中", "推导里不许解释符号含义（「其中 … 为 …」）：符号只出现在公式的 <var data-sym> 与单位行里"),
    ("分别表示", "推导里不许解释符号含义（「… 分别表示 …」）"),
    ("符号说明", "推导里不许放符号说明"),
    ("符号含义", "推导里不许放符号含义"),
    ("指的是", "推导里不许解释符号含义（「… 指的是 …」）"),
]
SYMBOL_GLOSS_RE = re.compile(r"(?<![\w])[A-Za-zη][A-Za-z0-9_₀-₉]{0,5}\s*(?:为|是)\s*[\u4e00-\u9fa5]{2,}")
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
ATTR_RE = re.compile(r"([\w:.-]+)\s*=\s*\"([^\"]*)\"")
VAR_SYM_RE = re.compile(r"<var\b[^>]*data-sym\s*=\s*\"([^\"]*)\"", re.I)
ANY_SYM_RE = re.compile(r"data-sym\s*=\s*\"([^\"]*)\"", re.I)
PATH_D_RE = re.compile(r"\b[dp]=\"([^\"]+)\"")
POINTS_RE = re.compile(r"\bpoints=\"([^\"]+)\"")
# 10ⁿ 刻度：上标（10⁻²）或带 caret（10^-2 / 10^2）；ASCII 形式必须带 ^，
# 否则线性轴上的「100」「105」会被误判成对数刻度（已踩过）。
LOG_TICK_RE = re.compile(r"10[⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+|10\^-?\d+|10e-?\d+")
UNIT_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mV/dec|mV\s*dec|dec|mA/cm²|mA/cm2)")
# 「数 + 单位」的通用写法：132.6 mV/dec、49.8 kJ/mol、−6.00 K、5.0 dec 都算。
# 之前写死 mV/dec/mA/V/Ω，换成别的知识点（kJ/mol、K）就永远判「没代入数」。
UNIT_TOKEN_RE = re.compile(r"\d\s*(?:[A-Za-zµΩ°‰%][A-Za-z0-9µΩ°‰%/·²³⁻¹^*]*)")
PITFALL_WORD = "错误做法"
PG_RE = re.compile(r"<span\b[^>]*class=\"[^\"]*\bpg\b[^\"]*\"[^>]*>(.*?)</span>", re.S)
RECAST_RE = re.compile(r"<[a-z]+\b[^>]*class=\"[^\"]*\brecast\b[^\"]*\"[^>]*>(.*?)</[a-z]+>", re.S)

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


# ---- 通用解析 -------------------------------------------------------------


def text_of(fragment: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", fragment)).strip()


def sym_key(name: str) -> str:
    """符号归一：去掉下划线/上标标记与空白，E_eq 与 E<sub>eq</sub> 视为同一符号。"""
    return re.sub(r"[_\s]+", "", name)


def attrs_of(tag: str) -> dict[str, str]:
    return {key.lower(): value for key, value in ATTR_RE.findall(tag)}


def find_tags(html: str, name: str) -> list[tuple[dict[str, str], str]]:
    """返回 [(属性字典, 内层 HTML), …]；同名标签不嵌套时可靠。"""
    pattern = re.compile(rf"<{name}\b([^>]*)>(.*?)</{name}>", re.S | re.I)
    return [(attrs_of(match.group(1)), match.group(2)) for match in pattern.finditer(html)]


def has_class(attrs: dict[str, str], name: str) -> bool:
    return name in attrs.get("class", "").split()


def core_label(text: str) -> str:
    """轴标签/标注 → 量名核心：只取等号左边，去掉单位括号、log 记号、空白、前导 Δ。"""
    value = text_of(text)
    value = value.split("=")[0]
    value = re.sub(r"\[[^\]]*\]", "", value)
    value = value.replace("log₁₀", "").replace("log10", "").replace("log", "")
    value = value.strip().lstrip("Δ").strip()
    return re.sub(r"\s+", "", value)


def core_decl(value: str) -> str:
    value = value.replace("log₁₀", "").replace("log10", "").replace("log", "")
    return re.sub(r"\s+", "", value.strip().lstrip("Δ"))


def contains_quantity(text: str, quantity: str) -> bool:
    """量名是否出现在正文里；ASCII 标识符按单词边界，避免 E 命中 E_eq。"""
    quantity = quantity.strip()
    if not quantity:
        return True
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_ ]*", quantity):
        body = re.escape(quantity).replace(r"\ ", r"\s+")
        return re.search(rf"(?<![\w]){body}(?![\w])", text) is not None
    return quantity in text


def figure_syms(figure_inner: str) -> set[str]:
    return {value.strip() for value in ANY_SYM_RE.findall(figure_inner) if value.strip()}


def paths_of(figure_inner: str) -> set[str]:
    values = set()
    for match in PATH_D_RE.finditer(figure_inner):
        values.add(re.sub(r"\s+", " ", match.group(1)).strip())
    for match in POINTS_RE.finditer(figure_inner):
        values.add("pts:" + re.sub(r"\s+", " ", match.group(1)).strip())
    return values


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


# ---- 形式层检查 -----------------------------------------------------------


def check_structure(
    slides: list[tuple[str, str]], report: Report, min_pages: int, max_pages: int
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
        if index == len(slides):
            for word in LAST_TITLE_BANNED:
                if word in title:
                    report.error(
                        "标题",
                        f"最后一页标题含「{word}」（{title}）：结论页已取消，末页停在那一步算出的数上，"
                        "标题就写这个数（如「b = 126 mV/dec，比模型真值大 5%」）",
                    )
                    break
    return pages


def check_page_numbers(slides: list[tuple[str, str]], report: Report) -> None:
    total = len(slides)
    bad = 0
    for index, (_, body) in enumerate(slides, start=1):
        match = PG_RE.search(body)
        if not match:
            report.error("页码", f"第 {index} 页缺可见页码：需要 <span class=\"pg\">{index} / {total}</span>")
            bad += 1
            continue
        shown = re.sub(r"\s+", "", text_of(match.group(1)))
        expect = f"{index}/{total}"
        if shown != expect:
            report.error("页码", f"第 {index} 页页码写的是「{shown}」，应为「{expect}」")
            bad += 1
    if not bad:
        report.ok("页码")


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
        report.error("易错点", f"三段式不足：{counts}，每项至少 {MIN_PITFALLS} 条")
    else:
        report.ok("易错点")


def check_no_quiz(html: str, slides: list[tuple[str, str]], report: Report) -> None:
    """末页不许是例题/自测；全篇不出现自测式提问。"""
    for word in ("自测", "例题", "练习题", "习题", "思考题"):
        if word in html:
            report.error(
                "去自测",
                f"出现「{word}」：自测/例题页已取消，讲解停在最后一个算例上",
            )
            return
    if slides and slides[-1][1].count("<details") >= 2:
        report.warn("去自测", "末页仍有多个 <details>：确认不是变相的自测页")
    report.ok("去自测")


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
    fixed_canvas = re.search(r"height\s*:\s*900px", html) and re.search(
        r"transform\s*:\s*scale|zoom\s*:", html, re.I
    )
    if not re.search(r"100(?:d)?vh", html) and not fixed_canvas:
        report.error("布局", "既没有 100vh，也没有「1600×900 固定画布 + 缩放」：做不到 1 页 1 屏")
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


# ---- 语义层：坐标系 -------------------------------------------------------


class SlideInfo:
    """一页的图与公式摘要。"""

    def __init__(self, index: int, open_tag: str, body: str) -> None:
        self.index = index
        self.body = body
        self.open_tag = open_tag
        self.open_attrs = attrs_of(open_tag)
        self.kind = self.open_attrs.get("data-kind", "")
        figures = [inner for attrs, inner in find_tags(body, "figure") if has_class(attrs, "fig")]
        self.figure_inner = figures[0] if figures else ""
        fig_attrs = {}
        for attrs, inner in find_tags(body, "figure"):
            if has_class(attrs, "fig"):
                fig_attrs = attrs
                break
        self.fig_attrs = fig_attrs
        self.has_figure = bool(figures)
        self.x = fig_attrs.get("data-x", "").strip()
        self.y = fig_attrs.get("data-y", "").strip()
        self.xscale = fig_attrs.get("data-xscale", "linear").strip().lower()
        self.yscale = fig_attrs.get("data-yscale", "linear").strip().lower()
        self.anim = fig_attrs.get("data-anim", "").strip()
        self.texts = find_tags(self.figure_inner, "text")

    def ax_label(self, axis: str) -> str | None:
        for attrs, inner in self.texts:
            if has_class(attrs, "ax") and attrs.get("data-axis", "").lower() == axis:
                return text_of(inner)
        return None

    def plain_text(self) -> str:
        return text_of(self.body)

    def figure_inner_text(self) -> str:
        return text_of(self.figure_inner)


def check_axes(slides: list[SlideInfo], report: Report) -> None:
    """R2/R2′：每张图声明 x/y，轴标签规范，刻度形态与刻度一致。"""
    problems = 0
    for slide in slides:
        if not slide.has_figure:
            continue
        if not slide.x or not slide.y:
            report.error(
                "坐标系",
                f"第 {slide.index} 页的 <figure class=\"fig\"> 缺 data-x / data-y："
                "图必须声明两个轴是哪个量、什么刻度",
            )
            problems += 1
            continue
        for axis, quantity, scale in (("x", slide.x, slide.xscale), ("y", slide.y, slide.yscale)):
            label = slide.ax_label(axis)
            if label is None:
                report.error(
                    "坐标系",
                    f"第 {slide.index} 页缺 {axis} 轴标签：需要 "
                    f"<text class=\"ax\" data-axis=\"{axis}\">{quantity} [单位]</text>",
                )
                problems += 1
                continue
            if "对数" in label:
                report.error(
                    "坐标系",
                    f"第 {slide.index} 页 {axis} 轴写成「{label}」：对数轴写 log₁₀ 加单位，"
                    "禁止「（对数）」这类括号注释",
                )
                problems += 1
            if scale == "log":
                if "log" not in label:
                    report.error(
                        "坐标系",
                        f"第 {slide.index} 页 {axis} 轴声明为 log，标签却写「{label}」："
                        "应形如 log₁₀ " + quantity + " [单位]",
                    )
                    problems += 1
            else:
                if "log" in label:
                    report.error(
                        "坐标系",
                        f"第 {slide.index} 页 {axis} 轴声明为线性，标签却含 log：「{label}」",
                    )
                    problems += 1
            if core_label(label) != core_decl(quantity):
                report.error(
                    "坐标系",
                    f"第 {slide.index} 页 {axis} 轴标签「{label}」与 data-{axis}=\"{quantity}\" 不是同一个量："
                    "换坐标就必须换标签",
                )
                problems += 1

        # 刻度形态：刻度文本用 data-axis 标明属于哪个轴，逐轴核对
        untagged = 0
        for attrs, inner in slide.texts:
            if has_class(attrs, "ax"):
                continue
            if attrs.get("data-axis", "").lower() not in {"x", "y"}:
                untagged += 1
        if untagged:
            report.error(
                "坐标系",
                f"第 {slide.index} 页有 {untagged} 个刻度没标 data-axis："
                "刻度属于哪个轴说不清，就无法核对「换刻度」是否漏改",
            )
            problems += 1

        for axis, scale in (("x", slide.xscale), ("y", slide.yscale)):
            ticks = [
                text_of(inner)
                for attrs, inner in slide.texts
                if not has_class(attrs, "ax") and attrs.get("data-axis", "").lower() == axis
            ]
            log_ticks = [tick for tick in ticks if LOG_TICK_RE.search(tick)]
            if scale == "log":
                if any(tick.strip() == "0" for tick in ticks):
                    report.error(
                        "坐标系",
                        f"第 {slide.index} 页 {axis} 轴是 log，刻度里却出现 0：log 轴上没有 0",
                    )
                    problems += 1
                if len(log_ticks) < 2:
                    report.error(
                        "坐标系",
                        f"第 {slide.index} 页 {axis} 轴是 log，刻度却不是 10ⁿ 形式："
                        "换刻度类型也是换坐标的一部分",
                    )
                    problems += 1
            elif log_ticks:
                report.error(
                    "坐标系",
                    f"第 {slide.index} 页 {axis} 轴是线性，刻度却出现 {log_ticks[0]}：刻度没跟着刻度类型改",
                )
                problems += 1
    if not problems:
        report.ok("坐标系")


def check_recast(slides: list[SlideInfo], report: Report) -> None:
    """R3：换坐标（量或刻度）必须同时改标签+刻度+图注+正文，并有一行 recast 说明。"""
    previous: SlideInfo | None = None
    problems = 0
    for slide in slides:
        if not slide.has_figure:
            continue
        if previous is not None:
            changed_x = core_decl(previous.x) != core_decl(slide.x)
            changed_y = core_decl(previous.y) != core_decl(slide.y)
            scale_changed = (previous.xscale, previous.yscale) != (slide.xscale, slide.yscale)
            if changed_x or changed_y or scale_changed:
                recast = RECAST_RE.search(slide.body)
                recast_text = text_of(recast.group(1)) if recast else ""
                if not recast:
                    report.error(
                        "坐标变换",
                        f"第 {slide.index} 页换了坐标（{previous.x}/{previous.yscale} → "
                        f"{slide.x}/{slide.yscale}），但没有 <p class=\"recast\">…</p> 说明这一跳",
                    )
                    problems += 1
                else:
                    if changed_x and not (
                        contains_quantity(recast_text, previous.x) and contains_quantity(recast_text, slide.x)
                    ):
                        report.error(
                            "坐标变换",
                            f"第 {slide.index} 页 recast 没写清从哪个量换到哪个量："
                            f"「{recast_text}」应同时出现 {previous.x} 与 {slide.x}",
                        )
                        problems += 1
                    if changed_x and contains_quantity(slide.figure_inner_text(), previous.x):
                        report.error(
                            "坐标变换",
                            f"第 {slide.index} 页横轴已换成 {slide.x}，图上还留着旧量名 {previous.x}："
                            "轴标签、刻度、图注、标注要一起换",
                        )
                        problems += 1
                    if changed_y and not (
                        contains_quantity(recast_text, previous.y) and contains_quantity(recast_text, slide.y)
                    ):
                        report.error(
                            "坐标变换",
                            f"第 {slide.index} 页 recast 没写清纵轴变化：应同时出现 {previous.y} 与 {slide.y}",
                        )
                        problems += 1
                    if changed_y and contains_quantity(slide.figure_inner_text(), previous.y):
                        report.error(
                            "坐标变换",
                            f"第 {slide.index} 页纵轴已换成 {slide.y}，图上还留着旧量名 {previous.y}",
                        )
                        problems += 1
                    if scale_changed and not (changed_x or changed_y):
                        need = "log" if slide.yscale == "log" and previous.yscale != "log" else "线性"
                        if need not in recast_text:
                            report.error(
                                "坐标变换",
                                f"第 {slide.index} 页改了刻度类型，recast 必须点明（含「{need}」）：「{recast_text}」",
                            )
                            problems += 1
        previous = slide
    if not problems:
        report.ok("坐标变换")


def check_dims(slides: list[SlideInfo], report: Report) -> None:
    """R4：几何标注的方向必须与声明的轴一致（Δx 只能横着，Δy 只能竖着）。"""
    problems = 0
    for slide in slides:
        if not slide.has_figure:
            continue
        for attrs, inner in find_tags(slide.figure_inner, "g"):
            if not has_class(attrs, "dim"):
                continue
            span = attrs.get("data-span", "").strip().lower()
            if span not in {"x", "y"}:
                report.error(
                    "标注方向",
                    f"第 {slide.index} 页的标注「{text_of(inner)}」缺 data-span=\"x|y\"："
                    "说不清量的是横边还是竖边",
                )
                problems += 1
                continue
            expect = slide.x if span == "x" else slide.y
            got = core_label(text_of(inner))
            if core_decl(got) != core_decl(expect):
                report.error(
                    "标注方向",
                    f"第 {slide.index} 页标「{text_of(inner)}」画在 {span} 方向，但 {span} 轴是 {expect}："
                    "Δ 标注画反了",
                )
                problems += 1
    if not problems:
        report.ok("标注方向")


def check_phenomenon(slides: list[SlideInfo], report: Report) -> None:
    """R6：只在换了坐标才看得见的描述，必须出现在对数纵轴的那一页。"""
    problems = 0
    for slide in slides:
        if slide.kind in {"formula", "axioms"}:
            # 预备段页在讲「这式什么时候不能用」，允许出现失效描述；它没有图，也不谈现象
            continue
        text = slide.plain_text()
        hits = [word for word in PHENOMENON if word in text]
        if not hits:
            continue
        if not slide.has_figure:
            report.error(
                "现象描述",
                f"第 {slide.index} 页说「{hits[0]}」却没有图：现象必须能当场在图上指出",
            )
            problems += 1
            continue
        if slide.yscale != "log":
            report.error(
                "现象描述",
                f"第 {slide.index} 页说「{hits[0]}」，但本页纵轴是 {slide.yscale}："
                "「变平/偏离直线」只有在纵轴取对数后才成立，说明坐标系才能说现象",
            )
            problems += 1
    if not problems:
        report.ok("现象描述")


# ---- 语义层：公式 ---------------------------------------------------------


class Formula:
    def __init__(self, index: int, number: int, inner: str) -> None:
        self.page = index
        self.number = number
        # 只取 <details> 之前的公式主体：否则推导表里的「=」会被当成公式的一部分
        head = inner.split("<details", 1)[0]
        cleaned = re.sub(r"<span\b[^>]*class=\"[^\"]*\beqno\b[^\"]*\"[^>]*>.*?</span>", "", head, flags=re.S)
        self.units = " ".join(
            text_of(m.group(1))
            for m in re.finditer(r"<span\b[^>]*class=\"[^\"]*\bunits\b[^\"]*\"[^>]*>(.*?)</span>", cleaned, re.S)
        )
        self.expr = text_of(re.sub(r"<span\b[^>]*class=\"[^\"]*\bunits\b[^\"]*\"[^>]*>.*?</span>", "", cleaned, flags=re.S))
        self.syms = {value.strip() for value in VAR_SYM_RE.findall(inner) if value.strip()}
        lhs = self.expr.split("=")[0] if "=" in self.expr else ""
        self.lhs = re.sub(r"\s+", "", lhs)
        self.eq_id = str(number)  # 正文「1」… 或预备段「P1」…
        self.used_in = ""
        self.stop = ""
        self.axiom = ""
        self.page_eq = ""


def collect_formulas(
    slides: list[SlideInfo], report: Report, max_eq: int
) -> tuple[list[Formula], list[Formula]]:
    """拆成两套号：正文核心式（data-eq="1"…）与预备段（data-eq="P1"…）。两套号永不复用。"""
    body: list[Formula] = []
    prep: list[Formula] = []
    per_page: dict[int, int] = {}
    for slide in slides:
        for attrs, inner in find_tags(slide.body, "div"):
            if not has_class(attrs, "formula"):
                continue
            raw = attrs.get("data-eq", "").strip()
            per_page[slide.index] = per_page.get(slide.index, 0) + 1
            if PREP_EQ_RE.match(raw):
                formula = Formula(slide.index, int(PREP_EQ_RE.match(raw).group(1)), inner)
                formula.eq_id = raw
                formula.used_in = (attrs.get("data-used-in", "") or "").strip()
                formula.stop = (attrs.get("data-stop", "") or "").strip()
                formula.axiom = (attrs.get("data-axiom", "") or "").strip()
                formula.page_eq = (slide.open_attrs.get("data-eq", "") or "").strip()
                prep.append(formula)
            elif raw.isdigit():
                formula = Formula(slide.index, int(raw), inner)
                formula.eq_id = raw
                body.append(formula)
            else:
                report.error(
                    "公式",
                    f"第 {slide.index} 页有公式缺 data-eq 编号（正文写 1、2…，预备段写 P1、P2…）",
                )

    for index, count in per_page.items():
        if count > 1:
            report.error("公式", f"第 {index} 页有 {count} 条公式，每页最多 1 条")

    numbers = [formula.number for formula in body]
    if not numbers:
        report.warn("公式", "全篇没有正文 data-eq 公式：确认是否真的不需要公式")
    else:
        if sorted(numbers) != list(range(1, len(numbers) + 1)):
            report.error("公式", f"正文式号不连续：得到 {sorted(numbers)}，应为 1..{len(numbers)}")
        if max_eq and len(numbers) > max_eq:
            report.error(
                "公式最小集",
                f"全篇正文 {len(numbers)} 条公式，超过 --max-eq {max_eq}："
                "同一个关系全篇只写一次，后续页引用前面的式号，不要移项另编号",
            )

        seen: dict[str, int] = {}
        for formula in body:
            key = formula.lhs
            if not key:
                continue
            if key in seen:
                report.error(
                    "公式最小集",
                    f"式 ({formula.number}) 与式 ({seen[key]}) 左边都是「{key}」："
                    "这不是新公式，是同一关系的变形或代入，应引用前面的式号",
                )
            else:
                seen[key] = formula.number
        if (not max_eq or len(numbers) <= max_eq) and len(seen) == len([f for f in body if f.lhs]):
            report.ok("公式最小集")

    prep_numbers = [formula.number for formula in prep]
    if prep_numbers and sorted(prep_numbers) != list(range(1, len(prep_numbers) + 1)):
        report.error(
            "预备段",
            f"P 号不连续：得到 {sorted(prep_numbers)}，应为 P1..P{len(prep_numbers)}（一条链一个号，不许跳号）",
        )
    return body, prep


def check_formula_binding(slides: list[SlideInfo], formulas: list[Formula], report: Report) -> None:
    """R7：公式的符号必须标 data-sym，且至少一个量出现在本页图上；操作词页必须有式。"""
    problems = 0
    by_page: dict[int, list[Formula]] = {}
    for formula in formulas:
        by_page.setdefault(formula.page, []).append(formula)
        if len(formula.syms) < 2:
            report.error(
                "式图绑定",
                f"式 ({formula.eq_id}) 只标了 {len(formula.syms)} 个符号："
                "每个符号写成 <var data-sym=\"…\">，否则无法核对它在图上有没有出现",
            )
            problems += 1

    for slide in slides:
        page_formulas = by_page.get(slide.index, [])
        prep_page = slide.kind in {"formula", "axioms"}
        if page_formulas and not slide.has_figure and not prep_page:
            report.warn(
                "式图绑定",
                f"第 {slide.index} 页有公式却没有图：符号与图的对应关系无法核对，人工补",
            )
        for formula in page_formulas:
            if not formula.units:
                report.error(
                    "式图绑定",
                    f"式 ({formula.eq_id}) 没有单位行：式子的 LHS/RHS 要有 <span class=\"units\">…</span> 写清量 + 单位",
                )
                problems += 1
            if prep_page:
                # 预备段页可以不带图；「式里的量必须在图上指得到」只管正文页
                continue
            if not slide.has_figure:
                continue
            shared = formula.syms & figure_syms(slide.figure_inner)
            if not shared:
                report.error(
                    "式图绑定",
                    f"式 ({formula.eq_id}) 的符号 {sorted(formula.syms)} 一个都不在第 {slide.index} 页图上："
                    "公式当页必须能在图上指到它的量",
                )
                problems += 1

        if prep_page:
            continue
        text = slide.plain_text()
        hits = [word for word in OPERATIONS if word in text]
        # 只在「图上演示这个操作」的页面强制配式；纯理论页可能只是提到它
        if hits and not page_formulas and slide.has_figure:
            report.error(
                "操作式",
                f"第 {slide.index} 页讲了「{hits[0]}」，却没有给出该操作的定义式："
                "关键操作必须先给公式，再讲后果，不能只在正文里描述",
            )
            problems += 1
    if not problems:
        report.ok("式图绑定")


# ---- 语义层：页预算 -------------------------------------------------------


def check_kinds(slides: list[SlideInfo], report: Report) -> None:
    """R11/S2：页角色必须显式声明，且预算合规（预备段在最前、条件页在前、错例 ≤1、末页不算总）。"""
    if not slides:
        return
    problems = 0
    kinds: dict[str, list[int]] = {}
    for slide in slides:
        if slide.kind not in KINDS:
            report.error(
                "页预算",
                f"第 {slide.index} 页 data-kind=\"{slide.kind}\" 不在 {'/'.join(sorted(KINDS))} 里："
                "不声明角色就无法核对页预算；summary（结论页）已取消",
            )
            problems += 1
            continue
        kinds.setdefault(slide.kind, []).append(slide.index)

    formula_pages = kinds.get("formula", [])
    axioms_pages = kinds.get("axioms", [])
    body_pages = [slide for slide in slides if slide.kind not in {"formula", "axioms"}]
    origin_pages = kinds.get("origin", [])
    if axioms_pages != [1]:
        report.error(
            "页预算",
            f"data-kind=\"axioms\" 的页在 {axioms_pages or '（没有）'}：公理清单页必须是第 1 页且只有一页",
        )
        problems += 1
    if formula_pages and formula_pages != list(range(2, 2 + len(formula_pages))):
        report.error(
            "页预算",
            f"formula 页在 {formula_pages}：P 段必须紧跟第 1 页公理清单、从第 2 页起连续（P1 → P2…），"
            "不许中间插正文页",
        )
        problems += 1
    if len(origin_pages) > 1:
        report.error("页预算", f"origin 页有 {origin_pages} 页：起点原图只占一页")
        problems += 1
    if origin_pages:
        expect = 1 + len(formula_pages) + 1
        if origin_pages[0] != expect:
            report.error(
                "页预算",
                f"起点原图页在第 {origin_pages[0]} 页：预备段（1 页公理清单 + {len(formula_pages)} 页 P）"
                f"共 {1 + len(formula_pages)} 页，原图页必须紧跟在它后面，即第 {expect} 页",
            )
            problems += 1
    elif slides:
        report.error("页预算", "没有 data-kind=\"origin\" 的页：起点材料原图必须原样出现一次")
        problems += 1

    if slides and slides[-1].kind not in {"calc", "pitfall"}:
        report.error(
            "页预算",
            f"最后一页是 data-kind=\"{slides[-1].kind}\"：结论页已取消，末页必须停在最后一个算例（calc）"
            "或错例（pitfall）上，不再另起一页总结",
        )
        problems += 1
    if len(kinds.get("pitfall", [])) > 1:
        report.error(
            "页预算",
            f"错例页 {kinds['pitfall']} 共 {len(kinds['pitfall'])} 页，上限 1 页："
            "错误示例不占正文页，三段式易错点集中一页说明",
        )
        problems += 1
    if kinds.get("pitfall") is None and "错误做法" in " ".join(slide.plain_text() for slide in slides):
        report.error(
            "页预算",
            "全篇有三段式易错点却没有 data-kind=\"pitfall\" 的页：错例要集中在一页，不要散在分析页里",
        )
        problems += 1
    for slide in slides:
        if slide.kind != "pitfall" and "错误做法" in slide.plain_text():
            report.error(
                "页预算",
                f"第 {slide.index} 页（data-kind=\"{slide.kind}\"）里写了错误做法：错例只占 1 页，"
                "推导页只讲正例；错误要先用理论说清，不用一页一个例子",
            )
            problems += 1
    theory = kinds.get("theory", [])
    calc = kinds.get("calc", [])
    if not theory:
        report.error("页预算", "没有 data-kind=\"theory\" 的条件页：必须先讲清成立条件，再开始取数")
        problems += 1
    elif calc and min(theory) > min(calc):
        report.error(
            "页预算",
            f"条件页在第 {min(theory)} 页，第一次计算在第 {min(calc)} 页：理论与成立条件必须排在计算之前",
        )
        problems += 1
    # S3：calc 占比按正文页（不含预备段）算，预备段不是算例
    if calc and len(body_pages) and len(calc) * 2 < len(body_pages):
        report.error(
            "页预算",
            f"正例推导只有 {len(calc)} 页（正文 {len(body_pages)} 页）：讲解页应以正例推导为主，至少一半",
        )
        problems += 1
    if not problems:
        report.ok("页预算")


def check_animations(slides: list[SlideInfo], report: Report, max_anim: int) -> None:
    """R8/R9：第 1 页不许叠后文标记；动画有配额、不重复、错例页不许有。"""
    problems = 0
    anim_pages = [slide for slide in slides if slide.anim]
    if len(anim_pages) > max_anim:
        report.error("动画", f"{len(anim_pages)} 页带动画，上限 {max_anim} 页")
        problems += 1
    seen: dict[str, int] = {}
    for slide in anim_pages:
        if slide.anim in seen:
            report.error(
                "动画",
                f"第 {slide.index} 页与第 {seen[slide.anim]} 页用了同一种动画（{slide.anim}）："
                "同一类动画全篇只用一次，重复等于没讲新东西",
            )
            problems += 1
        else:
            seen[slide.anim] = slide.index
        if PITFALL_WORD in slide.plain_text():
            report.error(
                "动画",
                f"第 {slide.index} 页是错误示例页却带动画：错例不需要演示过程，用一张静态对比图 + 三段式文字",
            )
            problems += 1

    for slide in slides:
        if not slide.has_figure or slide.kind in {"formula", "axioms"}:
            # 预备段页的「禁动画 / 禁高亮带」由 check_formula_section 的 C3 管
            continue
        if slide.index == 1:
            overlays = []
            if slide.anim:
                overlays.append("data-anim")
            if re.search(r"class=\"[^\"]*\bdim\b", slide.figure_inner):
                overlays.append("class=\"dim\" 标注")
            if overlays:
                report.error(
                    "第 1 页",
                    f"第 1 页叠了后文才出现的标记（{'、'.join(overlays)}）："
                    "起点页只放原图，第 1 页的标题只能是原图上肉眼可见的事实",
                )
                problems += 1
    if not problems:
        report.ok("动画")


def check_duplicate_figures(slides: list[SlideInfo], report: Report) -> None:
    """R10：两页用同一张图 = 没有视觉增量。

    轴钱、基础曲线这类「骨架」在多页里重复是正常的，先把所有页面都用的
    path 剔除，只比每页特有的部分。
    """
    problems = 0
    drawn = [(slide.index, paths_of(slide.figure_inner)) for slide in slides if slide.has_figure]
    if len(drawn) < 2:
        return report.ok("重复图")

    counts: dict[str, int] = {}
    for _, values in drawn:
        for value in values:
            counts[value] = counts.get(value, 0) + 1
    threshold = max(3, len(drawn) // 2)
    skeleton = {value for value, count in counts.items() if count >= threshold}

    distinctive = [(index, values - skeleton) for index, values in drawn]
    full = dict(drawn)
    for index, values in distinctive:
        if values or index == 1:
            continue
        identical = any(
            other != index and jaccard(full[index], full[other]) >= 0.9 for other in full
        )
        if not identical:
            report.warn(
                "视觉增量",
                f"第 {index} 页的图没有任何专属元素（全是其它页也有的骨架）：这页在视觉上没有新东西",
            )

    for i in range(len(distinctive)):
        for j in range(i + 1, len(distinctive)):
            left_index, left = distinctive[i]
            right_index, right = distinctive[j]
            if left and right:
                score = jaccard(left, right)
                if score >= 0.9:
                    report.error(
                        "重复图",
                        f"第 {left_index} 页与第 {right_index} 页的图几乎是同一张（专属元素相似度 {score:.2f}）："
                        "每页必须比上一页多一个视觉元素，不是把同一张图再讲一遍",
                    )
                    problems += 1
            elif not left and not right:
                # 两页都没有专属元素：看整张图是不是一模一样
                score = jaccard(full[left_index], full[right_index])
                if score >= 0.9:
                    report.error(
                        "重复图",
                        f"第 {left_index} 页与第 {right_index} 页是同一张图（整体相似度 {score:.2f}）："
                        "把同一张图再讲一遍不产生视觉增量",
                    )
                    problems += 1
    if not problems:
        report.ok("重复图")


# ---- HTML 内推导 ----------------------------------------------------------


def check_derivation(
    slides: list[SlideInfo], formulas: list[Formula], report: Report
) -> None:
    """D1：每条公式的推导必须自己把前因后果走完。

    契约（2026-11 修订）：
      · 不解释符号含义（「其中 j 为电流密度」这类一律不要，符号只在 <var data-sym> 与单位行里）；
      · 不用「由式 (N) 得」代替推理——第 N 式只是结论，读者要的是这一步怎么来的；
      · 从起点（定义 / 物理前提 / 实验事实）出发，一次一步走到本页的数；
      · 一页写不下可以分片：<details class="deriv" data-eq="2" data-part="2">…</details>，
        第 1 片与公式同页，续片落在后面的 calc 页，分片号从 1 连续。
    """

    def rows_of(inner: str) -> list[list[str]]:
        rows: list[list[str]] = []
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", inner, re.S):
            cells = [text_of(cell) for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.S)]
            if cells and cells[0] in {"步骤", "编号", "step"}:
                continue
            rows.append(cells)
        return rows

    blocks: dict[tuple[int, int], tuple[int, str]] = {}
    for slide in slides:
        for attrs, inner in find_tags(slide.body, "details"):
            if not has_class(attrs, "deriv"):
                continue
            raw = attrs.get("data-eq", "").strip()
            if PREP_EQ_RE.match(raw):
                # P 式的推导由 check_formula_section 的 C4 单独查（依据集、公理链、停点）
                continue
            if not raw.isdigit():
                report.error(
                    "推导",
                    f"第 {slide.index} 页的 <details class=\"deriv\"> 缺 data-eq：推导块必须挂在某条公式上",
                )
                continue
            part_raw = (attrs.get("data-part", "") or "1").strip()
            if not part_raw.isdigit() or int(part_raw) < 1:
                report.error(
                    "推导",
                    f"第 {slide.index} 页式 ({raw}) 的 data-part=\"{part_raw}\" 不是正整数：分片号从 1 开始",
                )
                continue
            blocks[(int(raw), int(part_raw))] = (slide.index, inner)

    if not formulas:
        return report.ok("推导")

    kind_of = {slide.index: slide.kind for slide in slides}
    problems = 0

    for formula in formulas:
        eq = formula.number
        parts = sorted(part for (number, part) in blocks if number == eq)
        first = blocks.get((eq, 1))
        if first is None:
            report.error(
                "推导",
                f"式 ({eq}) 没有 data-eq=\"{eq}\" 的推导块第 1 片：推导必须与公式同页起步",
            )
            problems += 1
            continue
        if first[0] != formula.page:
            report.error(
                "推导",
                f"式 ({eq}) 的第 1 片在第 {first[0]} 页、公式在第 {formula.page} 页：第 1 片必须与公式同页",
            )
            problems += 1
        if parts != list(range(1, len(parts) + 1)):
            report.error("推导", f"式 ({eq}) 的推导分片是 {parts}：必须从 1 连续编号")
            problems += 1
        for part in parts[1:]:
            page = blocks[(eq, part)][0]
            if page <= formula.page:
                report.error("推导", f"式 ({eq}) 的第 {part} 片在第 {page} 页：续片必须排在公式页之后")
                problems += 1
            elif kind_of.get(page) != "calc":
                report.error(
                    "推导",
                    f"式 ({eq}) 的第 {part} 片在第 {page} 页（data-kind=\"{kind_of.get(page)}\"）："
                    "推导续页必须是 calc，讲的还是这一条式子",
                )
                problems += 1

        texts: list[str] = []
        rows: list[list[str]] = []
        for part in parts:
            inner = blocks[(eq, part)][1]
            texts.append(text_of(inner))
            part_rows = rows_of(inner)
            if not part_rows:
                report.error("推导", f"式 ({eq}) 的第 {part} 片没有步骤行")
                problems += 1
            rows.extend(part_rows)
        text = " ".join(texts)
        where = "第 " + "、".join(str(blocks[(eq, p)][0]) for p in parts) + " 页"

        # ① 不许解释符号、不许用「由式 (N) 得」代替推理
        banned_hits = [(word, why) for word, why in DERIV_BANNED if word in text]
        if banned_hits:
            word, why = banned_hits[0]
            report.error("推导", f"{where}式 ({eq}) 的推导出现「{word}」：{why}")
            problems += 1
        # 量纲检查行里说「dec 无量纲」「mV/dec 相除无量纲」属量纲说明，不算符号释义
        gloss = None
        for cells in rows:
            basis = cells[-1] if cells else ""
            if "量纲" in basis:
                continue
            for cell in cells[:-1] or cells:
                gloss = SYMBOL_GLOSS_RE.search(cell)
                if gloss:
                    break
            if gloss:
                break
        if gloss:
            report.error(
                "推导",
                f"{where}式 ({eq}) 的推导在解释符号：「{gloss.group(0)}」。符号含义写在公式的 "
                "<var data-sym> 与单位行里，推导只写「怎么算出来的」",
            )
            problems += 1

        # ② 至少三步：起点 → 变换 → 代入本页的数
        if len(rows) < 3:
            report.error(
                "推导",
                f"{where}式 ({eq}) 的推导只有 {len(rows)} 步：至少三步（起点 / 变换 / 代入本页的数），"
                "一页写不下就加 data-part 续到下一页",
            )
            problems += 1

        # ③ 依据列要落到具体来源
        if "依据" not in text:
            report.error(
                "推导",
                f"{where}式 ({eq}) 的推导缺「依据」列：每步要注明 定义 / 物理前提 / 实验事实 / 假设 A1 / 代数 / 量纲 / 误差",
            )
            problems += 1
        vague = []
        for cells in rows:
            basis = cells[-1] if cells else ""
            if not re.search(
                r"定义|前提|实验|事实|近似\s*A\d|假设\s*A\d|代数|量纲|极限|误差|适用|边界|消",
                basis,
            ):
                vague.append(basis[:24] or "（空）")
        if vague:
            report.error(
                "推导",
                f"{where}式 ({eq}) 有 {len(vague)} 步的依据没说清来源：{vague[:2]}——"
                "要写「定义：…」「物理前提：…」「假设 A1」「代数：…」「量纲检查」，不能只写「整理得」",
            )
            problems += 1

        # ④ 必须把本页的数代进去
        substituted = any(
            re.search(r"=\s*[−-]?\d", cell) and UNIT_TOKEN_RE.search(cell)
            for cells in rows
            for cell in cells
        )
        if not substituted:
            report.error(
                "推导",
                f"{where}式 ({eq}) 的推导没有代入本页的数：至少一行写「(250−150) mV / 1.667 dec = 60.0 mV/dec」，"
                "否则读者不知道这式怎么落到这页的结论",
            )
            problems += 1

        # ⑤ 误差或失效边界
        if not re.search(r"误差|偏差|适用|失效|忽略|不成立|边界", text):
            report.error(
                "推导",
                f"{where}式 ({eq}) 的推导没写误差或失效边界：这个式子在什么条件下不成立、偏差多大，必须给一行",
            )
            problems += 1

        # ⑥ 引用假设编号
        if not re.search(r"A\d", text):
            report.error("推导", f"{where}式 ({eq}) 没引用假设编号（A1、A2…）：假设要在条件页列清，推导里逐处引用")
            problems += 1

    stray = sorted({number for (number, _part) in blocks} - {formula.number for formula in formulas})
    if stray:
        report.error("推导", f"推导块 data-eq={stray} 找不到对应公式")

    first_formula, last_formula = formulas[0], formulas[-1]
    for formula in {first_formula.number: first_formula, last_formula.number: last_formula}.values():
        text_all = " ".join(
            text_of(blocks[(formula.number, part)][1])
            for part in sorted(p for (number, p) in blocks if number == formula.number)
        )
        if "量纲" not in text_all:
            report.error(
                "推导",
                f"式 ({formula.number}) 的推导里没有量纲检查：首末两式各查一次，量纲不符一眼就能发现",
            )
            problems += 1

    if not problems:
        report.ok("推导")


# ---- 公式预备段：公理清单 + P 式（C1–C5） ---------------------------------


def rows_of_table(inner: str) -> list[list[str]]:
    """把推导表的行拆成单元格文本，跳过表头。"""
    rows: list[list[str]] = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", inner, re.S):
        cells = [text_of(cell) for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.S)]
        if cells and cells[0] in {"步骤", "编号", "step"}:
            continue
        rows.append(cells)
    return rows


class Axiom:
    """A 节的一条：标签 + 式子 + 注记 + 被哪些页用到。"""

    def __init__(self, aid: str, tag: str, eq: str, note: str, used_in: str, text: str) -> None:
        self.id = aid
        self.tag = tag
        self.eq = eq
        self.note = note
        self.used_in = used_in
        self.text = text

    @property
    def lhs(self) -> str:
        return normalize_expr(self.eq).split("=")[0]

    @property
    def rhs(self) -> str:
        parts = normalize_expr(self.eq).split("=")
        return "=".join(parts[1:]) if len(parts) > 1 else ""


def normalize_expr(value: str) -> str:
    """归一化式子：去标签/单位/括号注记/空白，≡ 当 =。"""
    text = text_of(value)
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = text.replace("≡", "=").replace("＝", "=")
    return re.sub(r"[\s　]+", "", text)


def parse_axioms(page_body: str) -> dict[str, Axiom]:
    """解第 1 页的 <li data-axiom="A1" data-used-in="5,7"><b>[定义]</b> <span class="eq">…</span></li>。"""
    axioms: dict[str, Axiom] = {}
    for raw_attrs, aid, inner in AXIOM_ITEM_RE.findall(page_body):
        attrs = attrs_of(raw_attrs)
        text = text_of(inner)
        tag = next((item for item in AXIOM_TAGS if f"[{item}]" in text), "")
        eq_match = AXIOM_EQ_RE.search(inner)
        if eq_match:
            # 下标写法 E<sub>eq</sub> 去标签后必须连成 Eeq，不能变成 "E eq" 两个 token
            eq = TAG_RE.sub("", eq_match.group(1)).strip()
        elif "</b>" in inner:
            eq = text_of(inner.split("</b>", 1)[-1])
        else:
            eq = text
        note_match = AXIOM_NOTE_RE.search(inner)
        note = text_of(note_match.group(1)) if note_match else ""
        if aid in axioms:
            continue
        axioms[aid] = Axiom(aid, tag, eq, note, (attrs.get("data-used-in", "") or "").strip(), text)
    return axioms


def check_meta_discourse(slides: list[SlideInfo], report: Report) -> None:
    """C6：幻灯片页面上禁止元话语（标题 / lead / .io / 列表）。"""
    problems = 0
    for slide in slides:
        fields: list[tuple[str, str]] = []
        h1 = H1_RE.search(slide.body)
        if h1:
            fields.append(("标题", text_of(h1.group(1))))
        for attrs, inner in find_tags(slide.body, "p"):
            # 标题、lead、.io、普通段落都算「页面正文」；元话语一句都不许留
            fields.append(("正文", text_of(inner)))
        for list_attrs, list_inner in find_tags(slide.body, "ul"):
            if not (has_class(list_attrs, "items") or has_class(list_attrs, "pit")):
                continue
            for item in re.findall(r"<li\b[^>]*>(.*?)</li>", list_inner, re.S):
                fields.append(("正文", text_of(item)))
        for where, content in fields:
            for word in META_BANNED:
                if word in content:
                    report.error(
                        "元话语",
                        f"第 {slide.index} 页{where}出现元话语「{word}」：「{content[:60]}」——"
                        "幻灯片上只留知识，讲解者的说明移到交付说明或折叠的 div.notes",
                    )
                    problems += 1
                    break
    if not problems:
        report.ok("元话语")


def prep_deriv_blocks(slides: list[SlideInfo]) -> dict[tuple[str, str], tuple[int, str]]:
    """收集所有 data-eq="P*" 的推导块：(P 号, 分片) → (页号, 内层 HTML)。"""
    blocks: dict[tuple[str, str], tuple[int, str]] = {}
    for slide in slides:
        for attrs, inner in find_tags(slide.body, "details"):
            if not has_class(attrs, "deriv"):
                continue
            raw = (attrs.get("data-eq", "") or "").strip()
            if not PREP_EQ_RE.match(raw):
                continue
            part = (attrs.get("data-part", "") or "1").strip()
            blocks[(raw, part)] = (slide.index, inner)
    return blocks


def check_prep_admission(
    prep: list[Formula],
    axioms: dict[str, Axiom],
    blocks: dict[tuple[str, str], tuple[int, str]],
    report: Report,
) -> None:
    """C7：P 段准入——定义不推导。

    a) P 的式子归一化后等于某条 A 的式子 → error（定义 / 约定 / 纯换算不许立 P 页）；
    b) 推导里「依据 A×」且该行式子与该 A 一字不差的行 ≥2 → error（照抄公理凑步数）；
    c) 推导 <3 步，或真实变换 <2 步 → error（照抄 A → 代常数 → 换单位不算推导）。
    """
    problems = 0
    for formula in prep:
        eq = formula.eq_id
        norm = normalize_expr(formula.expr)
        restated = False
        for axiom in axioms.values():
            if norm and norm == normalize_expr(axiom.eq):
                report.error(
                    "定义不推导",
                    f"{eq} 是 {axiom.id} 的重述，定义不推导："
                    "定义 / 约定 / 纯换算式写进 A 节，P 只留给真正推出来的式子",
                )
                problems += 1
                restated = True
                break
        if restated:
            continue

        parts = sorted(
            (part for (raw, part) in blocks if raw == eq), key=lambda x: int(x) if x.isdigit() else 0
        )
        rows: list[list[str]] = []
        for part in parts:
            rows.extend(rows_of_table(blocks[(eq, part)][1]))
        if not rows:
            continue  # 缺推导块由 C4 报，这里不重复

        copies = 0
        real = 0
        for cells in rows:
            basis = cells[-1] if cells else ""
            body = normalize_expr(cells[1]) if len(cells) > 1 else ""
            hit = AXIOM_ID_RE.search(basis)
            matched_axiom = axioms.get(hit.group(0)) if hit else None
            verbatim = bool(matched_axiom and body and body == normalize_expr(matched_axiom.eq))
            if verbatim:
                copies += 1
            if not verbatim and REAL_TRANSFORM_RE.search(basis):
                real += 1
        if copies >= 2:
            report.error(
                "定义不推导",
                f"{eq} 的推导有 {copies} 行直接照抄公理式子（依据 A× 且一字不差）："
                "公理只当起点写一次，后面的行必须是变换",
            )
            problems += 1
        if len(rows) < 3:
            report.error(
                "定义不推导",
                f"{eq} 的推导只有 {len(rows)} 步（<3）：P 段准入要求至少 3 步，定义不推导也不许跳步",
            )
            problems += 1
        elif real < 2:
            report.error(
                "定义不推导",
                f"{eq} 的推导只有 {real} 步是真实变换（<2）：照抄 A → 代常数 → 换单位不算推导，"
                "至少要有两步取对数 / 引入近似 / 相减 / 与 A 对照定系数",
            )
            problems += 1
    if not problems:
        report.ok("定义不推导")


def check_axiom_scope(
    axioms: dict[str, Axiom], goal: str, slides: list[SlideInfo], report: Report
) -> None:
    """C8：目标量不进 A 节 / 公理不互推 / [约定] 标签复核。"""
    problems = 0
    if not goal:
        report.error(
            "公理清单",
            "第 1 页缺 data-goal：本文档的终点量没声明，无法校验目标量是否被当成了公理",
        )
        problems += 1
    for axiom in axioms.values():
        if goal:
            lhs_tokens = set(SYM_TOKEN_RE.findall(axiom.lhs))
            if axiom.lhs == goal or goal in lhs_tokens:
                report.error(
                    "公理清单",
                    f"{axiom.id} 的 LHS 是终点量 {goal}，目标量不许进公理清单（它是对照推出的结果）："
                    f"把 {goal} 的首次出现放进 P 的推导里",
                )
                problems += 1
        rhs = axiom.rhs
        for other in axioms.values():
            if other.id == axiom.id or not other.lhs:
                continue
            lhs = other.lhs
            # 「以另一条 A 的 LHS 开头」：RHS 的第一个符号就是它（避免把 BV 里的 η 误判成互推）
            if rhs.startswith(lhs) and (
                len(rhs) == len(lhs) or not re.match(r"[A-Za-z0-9_₀-₉]", rhs[len(lhs)])
            ):
                report.error(
                    "公理清单",
                    f"{axiom.id} 的 RHS 以 {other.id} 的 LHS「{lhs}」开头：公理之间不许互推",
                )
                problems += 1
                break
        if axiom.tag == "约定" and re.search(r"测量得到|实测|测得|measured", axiom.text):
            report.warn(
                "公理清单",
                f"{axiom.id} 标了 [约定] 却写了「测量得到 / 实测」：约定是刻度 / 参考点的选择，"
                "具体体系的测量值应该标 [经验事实]",
            )
    if not problems:
        report.ok("公理清单")


def check_formula_section(
    slides: list[SlideInfo],
    prep: list[Formula],
    html: str,
    html_path: Path,
    report: Report,
) -> dict[str, int]:
    """公式预备段：C1 孤儿符号 / C2 被用到与冗余 / C3 版式 / C4 公理链 / C5 公理清单。

    预备段契约（详见 references/deck-contract.md）：
      · 第 1 页 data-kind="axioms"，放公理清单 A1…An（data-goal 声明终点量，不挂 data-eq / deriv）；
      · 随后每条 P 一页（data-eq="P1"…），一页只讲一条式，续页用 data-part；
      · 每条 A 必带 data-used-in（它被哪些页用到），未被任何页用到就是冗余；
      · 每条 P 必带 data-used-in（正文哪页用它）、data-stop（为何不再往下推）、data-axiom（起点 A 号）；
      · P 的推导首步依据只能是 A 编号或「定义」，之后只许 A 编号 / 代数 / 量纲 / 近似及条件；
      · 定义 / 约定 / 纯换算式不许占 P 号（见 check_prep_admission 的 C7）。
    """
    stats = {"axioms": 0, "prep": 0, "body": 0, "calc": 0, "ratio": 0}
    if not slides:
        return stats

    formula_pages = [slide for slide in slides if slide.kind == "formula"]
    axioms_pages = [slide for slide in slides if slide.kind == "axioms"]
    body_pages = [slide for slide in slides if slide.kind not in {"formula", "axioms"}]
    calc_pages = [slide for slide in slides if slide.kind == "calc"]
    stats.update(
        prep=len(formula_pages) + (1 if axioms_pages else 0),
        body=len(body_pages),
        calc=len(calc_pages),
        ratio=int(round(100 * len(calc_pages) / len(body_pages))) if body_pages else 0,
    )
    problems = 0

    # ---- C4 公理链完整：全文禁跳步词 ----
    plain = text_of(html)
    for word, why in STEP_BANNED:
        if word in plain:
            report.error("公理链", f"全文出现「{word}」：{why}")
            problems += 1
    for bad in AXIOM_TAG_BANNED:
        if f"[{bad}]" in plain:
            report.error("公理清单", f"出现禁止的标签「[{bad}]」：推论不许升格为公理，它必须给推导")
            problems += 1
    if re.search(r"式\s*[（(]\s*P\d", plain):
        report.error(
            "预备段",
            "出现「式 (P…)」写法：两套号永不复用，正文引用预备式只写「P2」，不写「式 (P2)」",
        )
        problems += 1

    # ---- C3 版式：第 1 页是公式页；预备段一页一条式；无动画/高亮带/滑块 ----
    if slides[0].kind != "axioms":
        report.error(
            "预备段",
            f"第 1 页 data-kind=\"{slides[0].kind}\"：全篇最前面必须是公理清单页（data-kind=\"axioms\"），"
            "起点原图页顺延到预备段之后",
        )
        problems += 1

    axiom_page = slides[0]
    if any(has_class(attrs, "formula") for attrs, _ in find_tags(axiom_page.body, "div")):
        report.error("预备段", "第 1 页（公理清单页）挂了 <div class=\"formula\">：公理页不挂 data-eq、不挂推导")
        problems += 1
    if any(has_class(attrs, "deriv") for attrs, _ in find_tags(axiom_page.body, "details")):
        report.error("预备段", "第 1 页（公理清单页）挂了推导块：定义不推导，公理页只列条目")
        problems += 1
    axioms = parse_axioms(axiom_page.body)
    stats["axioms"] = len(axioms)
    if not axioms:
        report.error(
            "公理清单",
            "第 1 页没有公理清单：需要 <ol class=\"axioms\"><li data-axiom=\"A1\"><b>[定义]</b> …</li>…</ol>，"
            "开讲前先把要用的每条式子从公理出发推一遍",
        )
        problems += 1

    # ---- C5 公理清单合规 ----
    for aid, axiom in axioms.items():
        text = axiom.text
        tags = [tag for tag in AXIOM_TAGS if f"[{tag}]" in text]
        if len(tags) != 1:
            report.error(
                "公理清单",
                f"{aid} 的标签是 {tags or '（无）'}：每条公理只能带 [定义] / [约定] / [定律] / [经验事实] 之一",
            )
            problems += 1
        for bad in AXIOM_TAG_BANNED:
            if bad in text:
                report.error(
                    "公理清单",
                    f"{aid} 用了禁止的标签/说法「{bad}」：推论不许升格为公理，它必须给推导",
                )
                problems += 1
                break
        for word in AXIOM_APPROX:
            if word in text:
                report.error(
                    "公理清单",
                    f"{aid} 里写了近似「{word}」：近似写在引用它的那一步的「依据」列，并当场给数值"
                    "（如「η = 150 mV 时还原项占 2.9×10⁻³」），不许进公理清单",
                )
                problems += 1
                break

    # ---- C3 预备段页：一页一条 P，禁动画/高亮带/滑块，.io 行 ----
    seen_eq: dict[str, int] = {}
    for formula in prep:
        if formula.eq_id in seen_eq:
            report.error(
                "预备段",
                f"{formula.eq_id} 同时出现在第 {seen_eq[formula.eq_id]} 页与第 {formula.page} 页："
                "一条 P 只占一页，续页用 <details class=\"deriv\" data-part=\"2\">，不重开公式",
            )
            problems += 1
        else:
            seen_eq[formula.eq_id] = formula.page
        if formula.page_eq and formula.page_eq != formula.eq_id:
            report.error(
                "预备段",
                f"第 {formula.page} 页 section 的 data-eq=\"{formula.page_eq}\" 与公式的 "
                f"data-eq=\"{formula.eq_id}\" 不一致：页与式必须同号",
            )
            problems += 1

    for slide in formula_pages + axioms_pages:
        page_text = slide.open_tag + slide.body
        overlays = []
        if "data-anim" in page_text:
            overlays.append("data-anim 动画")
        if re.search(r"class=\"[^\"]*\bdim\b", page_text):
            overlays.append("class=\"dim\" 高亮带")
        if re.search(r"<input\b[^>]*type\s*=\s*\"range\"", page_text, re.I):
            overlays.append("滑块")
        if overlays:
            report.error(
                "预备段",
                f"第 {slide.index} 页（data-kind=\"formula\"）放了 {'、'.join(overlays)}："
                "预备段只放式子和推导，禁动画、禁高亮带、禁滑块",
            )
            problems += 1

    for slide in formula_pages:
        has_formula = any(
            has_class(attrs, "formula") for attrs, _ in find_tags(slide.body, "div")
        )
        has_part = bool(
            re.search(r"<details\b[^>]*class=\"[^\"]*\bderiv\b[^\"]*\"[^>]*data-eq\s*=\s*\"P\d+\"", slide.body)
        )
        if not has_formula and not has_part:
            report.error(
                "预备段",
                f"第 {slide.index} 页是 data-kind=\"formula\" 却既不是公理清单页、也不是某条 P 的页："
                "预备段不许拿来凑页数",
            )
            problems += 1

    # ---- C4 公理链完整：P 的推导 ----
    prep_blocks: dict[tuple[str, str], tuple[int, str]] = {}
    for slide in slides:
        for attrs, inner in find_tags(slide.body, "details"):
            if not has_class(attrs, "deriv"):
                continue
            raw = (attrs.get("data-eq", "") or "").strip()
            if not PREP_EQ_RE.match(raw):
                continue
            part = (attrs.get("data-part", "") or "1").strip()
            prep_blocks[(raw, part)] = (slide.index, inner)

    for formula in prep:
        eq = formula.eq_id
        if not formula.used_in.isdigit():
            report.error(
                "预备段",
                f"{eq} 缺 data-used-in（这条式在正文第几页被用）：答不出就不该进预备段",
            )
            problems += 1
        if not formula.stop:
            report.error(
                "预备段",
                f"{eq} 缺 data-stop（停点理由：为什么推到这一式就不再往下）：空着视为没写",
            )
            problems += 1
        if not formula.axiom:
            report.error("预备段", f"{eq} 缺 data-axiom（这条链的起点 A 号）：答不出不许进预备段")
            problems += 1
        elif axioms and formula.axiom not in axioms:
            report.error(
                "公理清单",
                f"{eq} 的 data-axiom=\"{formula.axiom}\" 在 A 节里不存在：起点必须指向已声明的公理",
            )
            problems += 1

        io = re.search(r"<p\b[^>]*class=\"[^\"]*\bio\b[^\"]*\"[^>]*>(.*?)</p>", slides[formula.page - 1].body, re.S)
        io_text = text_of(io.group(1)) if io else ""
        if "吃进" not in io_text or "吐出" not in io_text:
            report.error(
                "预备段",
                f"第 {formula.page} 页（{eq}）缺 .io 行：要写清「吃进：…（第几页读得到）→ 吐出：… + 单位」",
            )
            problems += 1

        parts = sorted((p for (raw, p) in prep_blocks if raw == eq), key=lambda x: int(x) if x.isdigit() else 0)
        if not parts:
            report.error("预备段", f"{eq} 没有 data-eq=\"{eq}\" 的推导块：每条 P 式必须同页给推导")
            problems += 1
            continue
        if "1" not in parts:
            report.error("预备段", f"{eq} 的推导分片不从 1 开始：{parts}")
            problems += 1
            continue
        if parts != [str(i) for i in range(1, len(parts) + 1)]:
            report.error("预备段", f"{eq} 的推导分片是 {parts}：必须从 1 连续编号")
            problems += 1
        if prep_blocks[(eq, "1")][0] != formula.page:
            report.error(
                "预备段",
                f"{eq} 的推导第 1 片在第 {prep_blocks[(eq, '1')][0]} 页、公式在第 {formula.page} 页：第 1 片必须与公式同页",
            )
            problems += 1

        rows: list[list[str]] = []
        texts: list[str] = []
        for part in parts:
            page, inner = prep_blocks[(eq, part)]
            if part != "1" and slides[page - 1].kind != "formula":
                report.error(
                    "预备段",
                    f"{eq} 的第 {part} 片在第 {page} 页（data-kind=\"{slides[page - 1].kind}\"）："
                    "预备段续页仍是 formula 页",
                )
                problems += 1
            texts.append(text_of(inner))
            part_rows = rows_of_table(inner)
            if not part_rows:
                report.error("预备段", f"{eq} 的第 {part} 片没有步骤行")
                problems += 1
            rows.extend(part_rows)
        text = " ".join(texts)
        where = f"第 {formula.page} 页 {eq}"

        # C4-1 首步依据必须是 A 编号或「定义」
        first_basis = rows[0][-1] if rows and rows[0] else ""
        hit = AXIOM_ID_RE.search(first_basis)
        if not ((hit and hit.group(0) in axioms) or "定义" in first_basis):
            report.error(
                "公理链",
                f"{eq} 推导首步依据为「{first_basis}」，未命中公理清单（推论当公理）："
                "首步只能写 A 编号或「定义」",
            )
            problems += 1

        # C4-2 之后每步的依据只许 A 编号 / 代数 / 量纲 / 近似及条件
        for cells in rows[1:]:
            basis = cells[-1] if cells else ""
            if not STEP_BASIS_OK.search(basis):
                report.error(
                    "公理链",
                    f"{where} 有一步依据是「{basis[:24]}」：预备段每步依据只取 A 编号 / 代数 / 量纲 / 近似及条件",
                )
                problems += 1
                break

        # C4-3 推导里至少出现一次 A 编号
        if axioms and not any(re.search(r"\bA\d+\b", " ".join(cells)) for cells in rows):
            report.error("公理链", f"{where} 的推导里没有出现任何 A 编号：这条链的起点不在公理清单里")
            problems += 1

        # C4-4 禁解释符号（跳步词已在全文层面拦过）
        for cells in rows:
            basis = cells[-1] if cells else ""
            if "量纲" in basis:
                continue
            gloss = SYMBOL_GLOSS_RE.search(" ".join(cells))
            if gloss:
                report.error(
                    "预备段",
                    f"{where} 的推导在解释符号：「{gloss.group(0)}」。符号含义写在 <var data-sym> 与单位行里",
                )
                problems += 1
                break

        # 一.3 五问：能代入本页的数 + 什么时候不能用
        substituted = any(
            re.search(r"=\s*[−-]?\d", cell) and UNIT_TOKEN_RE.search(cell)
            for cells in rows
            for cell in cells
        )
        if not substituted:
            report.error(
                "预备段",
                f"{where} 的推导没有数值代入行：用贯穿算例的数代进去（形如「120 mV ÷ 0.905 dec = 132.6 mV/dec」）",
            )
            problems += 1
        if not re.search(r"误差|失效|偏差|不成立|边界|忽略", text):
            report.error(
                "预备段",
                f"{where} 的推导没写失效/近似条件：一句话 + 数值阈值（如「Δlog₁₀j < 0.5 dec 时偏差 > 20%」）",
            )
            problems += 1

    # ---- C2 预备式「被用到」与冗余 ----
    for formula in prep:
        if not formula.used_in.isdigit():
            continue
        target_index = int(formula.used_in)
        target = slides[target_index - 1] if 1 <= target_index <= len(slides) else None
        if target is None:
            report.error(
                "预备段",
                f"{formula.eq_id} 的 data-used-in=\"{formula.used_in}\" 指向不存在的页（共 {len(slides)} 页）",
            )
            problems += 1
            continue
        if target.kind != "calc":
            report.error(
                "预备段",
                f"{formula.eq_id} 声明用于第 {target_index} 页，但该页 data-kind=\"{target.kind}\"："
                "「被用到」必须指向一个存在的 calc 页",
            )
            problems += 1
            continue
        declared = {item.strip() for item in (target.open_attrs.get("data-uses", "") or "").split(",")}
        referenced = formula.eq_id in declared or re.search(
            rf"(?<![\w]){re.escape(formula.eq_id)}(?!\d)", target.plain_text()
        )
        if not referenced:
            report.error(
                "预备段",
                f"{formula.eq_id} 声明用于第 {target_index} 页，但第 {target_index} 页未引用它（预备段冗余）",
            )
            problems += 1

    # ---- C5-3 公理冗余：data-used-in 必须指向真实引用它的页 ----
    for aid, axiom in axioms.items():
        raw_pages = [item for item in re.split(r"[,，\s]+", axiom.used_in) if item]
        if not raw_pages:
            report.error(
                "公理清单",
                f"{aid} 缺 data-used-in（它被哪些页用到，如 data-used-in=\"5,7\"）：未被任何页用到的公理是冗余",
            )
            problems += 1
            continue
        bad_pages = [item for item in raw_pages if not item.isdigit() or not (1 <= int(item) <= len(slides))]
        if bad_pages:
            report.error(
                "公理清单",
                f"{aid} 的 data-used-in 里有不存在的页 {bad_pages}（共 {len(slides)} 页）：删页后要整体重排",
            )
            problems += 1
            continue
        referenced = False
        for item in raw_pages:
            page = slides[int(item) - 1]
            declared = {token.strip() for token in (page.open_attrs.get("data-uses", "") or "").split(",")}
            if aid in declared or re.search(rf"(?<![\w]){re.escape(aid)}(?!\d)", page.plain_text()):
                referenced = True
                break
        if not referenced:
            report.error(
                "公理清单",
                f"{aid} 声明用于第 {'、'.join(raw_pages)} 页，但这些页都没引用它（冗余公理）：删掉，或补 data-uses=\"{aid}\"",
            )
            problems += 1

    # ---- C1 孤儿符号闭包 ----
    defined: set[str] = set()
    for formula in prep:
        defined |= {sym_key(sym) for sym in formula.syms}
    for axiom in axioms.values():
        defined |= {sym_key(tok) for tok in SYM_TOKEN_RE.findall(axiom.eq)}
    origin_reads: set[str] = set()
    outline = html_path.parent / "outline.json"
    if outline.is_file():
        try:
            raw = json.loads(outline.read_text(encoding="utf-8"))
            origin_reads |= {str(item).strip() for item in (raw.get("origin_reads") or []) if str(item).strip()}
        except (OSError, ValueError):
            report.warn("孤儿符号", f"读不出 {outline} 的 origin_reads，只用页面上的 data-reads")
    for slide in slides:
        if slide.kind == "origin":
            raw = slide.open_attrs.get("data-reads", "")
            origin_reads |= {item for item in re.split(r"[,，\s]+", raw) if item}
    reported: set[str] = set()
    for slide in slides:
        if slide.kind != "calc":
            continue
        for sym in VAR_SYM_RE.findall(slide.body):
            sym = sym.strip()
            key = sym_key(sym)
            if not sym or key in defined or key in {sym_key(x) for x in origin_reads} or key in reported:
                continue
            reported.add(sym)
            report.error(
                "孤儿符号",
                f"孤儿符号 {sym} 首次出现于第 {slide.index} 页，预备段无定义式："
                "正文每个符号都必须能追到某条 P 式的 LHS/RHS，或起点图上的读数",
            )
            problems += 1

    # ---- S3：结构摘要与 calc 占比 ----
    if body_pages and len(calc_pages) * 2 < len(body_pages):
        report.error(
            "预备段",
            f"calc 只占正文 {stats['ratio']}%（{len(calc_pages)}/{len(body_pages)} 页）：讲解页应以算例为主，至少一半",
        )
        problems += 1
    if not problems:
        report.ok("公式预备段")
    return stats


def check_recalc(html: str, report: Report) -> None:
    """D2：全篇必须有「数值复算」折叠表；幻灯片上的数要能在表里找到出处。"""
    block = ""
    raw_block = ""
    recalc_attrs: dict[str, str] = {}
    for attrs, inner in find_tags(html, "details"):
        if has_class(attrs, "recalc"):
            recalc_attrs = attrs
            raw_block = inner
            block = text_of(inner)
            break
    if not block:
        report.error(
            "数值复算",
            "缺 <details class=\"recalc\">：把原 docx 的复算表搬进来（输入 | 计算 | 结果 | 对应页）",
        )
        return
    recalc_tag = re.search(r'<details[^>]*class="[^"]*recalc[^"]*"[^>]*>', html)
    if recalc_tag and not re.search(r"\bopen\b", recalc_tag.group(0)):
        report.warn(
            "数值复算",
            "recalc 默认折叠：如果这页只有复算表，屏幕上就是一张空白页。改成 <details class=\"recalc\" open>",
        )
    rows = len(re.findall(r"<tr\b", raw_block)) or len(re.findall(r"<li\b", raw_block))
    if "数值复算" not in block:
        report.error("数值复算", "复算块里要有「数值复算」四个字作为标题，便于核对")
    if rows < 3:
        report.error("数值复算", f"复算表只有 {rows} 行：幻灯片上每个带单位的数都要有一行出处")

    body = re.sub(r"<[^>]+>", " ", html)
    lost = sorted({m.group(0).strip() for m in UNIT_NUM_RE.finditer(body) if m.group(1) not in block})
    if lost:
        report.warn("数值复算", f"这些数在复算表里找不到出处：{lost[:5]}")
    if "数值复算" in block and rows >= 3:
        report.ok("数值复算")


# ---- 呈现层：页码必须看得见 -----------------------------------------------


def check_viewport(html: str, report: Report) -> None:
    """R0：1600×900 固定画布必须缩放到视口，否则右下角页码会跑出屏幕。"""
    problems = 0
    scales = re.search(r"transform\s*:\s*scale|zoom\s*:|--k\b", html, re.I)
    listens = re.search(r"addEventListener\(\s*[\"']resize|@media\s*\(max-width", html, re.I)
    if not scales:
        report.error(
            "视口适配",
            "没有缩放到视口的机制（transform: scale / zoom / --k）：1600×900 画布在小窗口下会被裁掉，"
            "右下角页码直接看不见",
        )
        problems += 1
    if not listens:
        report.error(
            "视口适配",
            "没有 resize 监听（或等价媒体查询）：窗口大小一变就错位，页码又跑出去",
        )
        problems += 1
    if re.search(r"\.pg\s*\{[^}]*display\s*:\s*none", html, re.I):
        report.error("视口适配", ".pg 被 display:none 藏掉了：页码必须始终可见")
        problems += 1
    if not re.search(r"\.pg\s*\{[^}]*position\s*:\s*(absolute|fixed)", html, re.I):
        report.warn("视口适配", ".pg 没有定位：确认页码真的落在每页可见区域")
    if not problems:
        report.ok("视口适配")


def check_size(html: str, report: Report) -> None:
    """体积与逐点内联：曲线应当「数据 + 渲染函数」，不要把上千个坐标写死。"""
    problems = 0
    kb = len(html.encode("utf-8")) / 1024
    if kb > MAX_HTML_KB:
        report.warn(
            "体积",
            f"HTML {kb:.0f}KB > {MAX_HTML_KB}KB：曲线改成「数据数组 + 一个渲染函数」，别逐点内联坐标",
        )
    long_points = [
        value for value in re.findall(r"points=\"([^\"]+)\"", html) if len(value) > MAX_INLINE_POINTS
    ]
    if long_points:
        report.warn(
            "体积",
            f"有 {len(long_points)} 条 polyline 的坐标串超过 {MAX_INLINE_POINTS} 字符："
            "把点存成 <script type=\"application/json\" class=\"deck-data\">，由 JS 生成路径",
        )
        problems += 1
    if not problems:
        report.ok("体积")


# ---- 截图（抽查） ---------------------------------------------------------


def check_shots(html_path: Path, pages: list[int], report: Report) -> None:
    """验收改成「整份 PDF + 抽查 3 页」，不再要求逐页 PNG。"""
    folder = html_path.parent / "shots"
    pdf = folder / "deck-print.pdf" if folder.is_dir() else None
    images = []
    if folder.is_dir():
        images = [p for p in folder.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    if pdf and pdf.is_file() and len(images) >= 3:
        report.ok("截图")
        return
    if not folder.is_dir():
        report.warn("截图", "缺 shots/：至少给 deck-print.pdf + 3 张抽查截图")
    elif not (pdf and pdf.is_file()):
        report.warn("截图", f"shots/ 里没有 deck-print.pdf（现有 {len(images)} 张图）")
    elif len(images) < 3:
        report.warn("截图", f"抽查截图不足 3 张（现有 {len(images)} 张）")


# ---- 公式渲染：手写体 + 下标 + 展开态 ------------------------------------


HAND_HINT = "公式必须用内嵌手写体（scaffold.CSS 的 --hand）；公式里不许用下划线当下标"

# var(--hand) 允许出现的选择器（纯数学，不含中文）
HAND_SELECTORS = {".formula .expr", "ol.axioms .eq"}
# 允许倾斜的选择器（行内公式；块级倾斜会把表格/图注一起转）
TILT_ALLOWED = {".formula .expr"}


def css_rules(html: str) -> list[tuple[str, str]]:
    """把 <style> 里的扁平规则拆成 (selector, declarations)。@media 里的内层规则也能取到。"""
    styles = re.findall(r"<style\b[^>]*>(.*?)</style>", html, re.S | re.I)
    rules: list[tuple[str, str]] = []
    for css in styles:
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            selector = m.group(1).strip()
            if selector.startswith("@"):
                continue
            rules.append((selector, m.group(2)))
    return rules


def hand_cmap(html: str):
    """从 HTML 内嵌的 woff2 里读出 cmap；读不到返回 None。"""
    m = re.search(r"url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)", html)
    if not m:
        return None
    try:
        import base64
        import io

        from fontTools.ttLib import TTFont

        font = TTFont(io.BytesIO(base64.b64decode(m.group(1))))
        coverage: set[int] = set()
        for table in font["cmap"].tables:
            coverage |= set(table.cmap.keys())
        return coverage
    except Exception:  # noqa: BLE001 - 字体解析失败只降级成 warn
        return None


def hand_fragments(body: str) -> list[tuple[str, str]]:
    """取出会被手写体渲染的片段：.formula .expr 与 ol.axioms .eq。"""
    out: list[tuple[str, str]] = []
    for m in re.finditer(r'<span class="expr">(.*?)</span>', body, re.S):
        out.append((".formula .expr", m.group(1)))
    for m in re.finditer(r'<span class="eq">(.*?)</span>', body, re.S):
        out.append(("ol.axioms .eq", m.group(1)))
    return out


def check_handwriting(html: str, slides: list[SlideInfo], report: Report) -> None:
    """R：公式渲染成手写体；下标用 <sub>；折叠块展开后仍在一页内。

    三条都来自真实翻车：公式排在系统字体里像代码、E_eq 这种编程写法留在页面上、
    复算表一展开下半截就被 overflow:hidden 裁掉。
    """
    problems = 0

    # 1) 手写体必须内嵌（离线单文件），且只挂在纯数学元素上
    face = re.search(r"@font-face\s*\{[^}]*font-family\s*:\s*([\"']?)DeckHand", html, re.I)
    if not face:
        report.error(
            "手写体",
            "@font-face 里没有 DeckHand：公式必须用手写体（scripts/make_handfont.py 生成内嵌子集）",
        )
        problems += 1
    elif not re.search(r"@font-face\s*\{[^}]*url\(data:font/woff2;base64,", html, re.I):
        report.error(
            "手写体",
            "@font-face 没用 data:font/woff2 内嵌：换台机器字体就掉档，离线单文件要求自带字形",
        )
        problems += 1
    if not re.search(r"\.formula\s+\.expr\s*\{[^}]*font-family\s*:\s*var\(--hand\)", html, re.I):
        report.error("手写体", f".formula .expr 没有 font-family: var(--hand)：{HAND_HINT}")
        problems += 1

    # 1b) var(--hand) 只能出现在纯数学选择器上：子集字体没有 CJK 字形，
    #     挂到会含中文的元素（推导表、正文）上就会回退到本机系统字体，换机器字形就变。
    for selector, decls in css_rules(html):
        if "var(--hand)" not in decls:
            continue
        key = re.sub(r"\s+", " ", selector.strip())
        if key in HAND_SELECTORS:
            continue
        report.error(
            "手写体",
            f"手写体挂在了「{key}」上：只许挂 {sorted(HAND_SELECTORS)}。"
            "这些元素里一旦出现中文（推导表的式子/依据列），就会回退到系统字体",
        )
        problems += 1

    # 1c) 字形覆盖：公式元素里每个字符都必须在内嵌子集里
    coverage = hand_cmap(html)
    if coverage is None:
        report.warn("手写体", "读不出内嵌字体（fontTools 缺失或 base64 损坏），跳过字形覆盖检查")
    else:
        for slide in slides:
            for label, frag in hand_fragments(slide.body):
                text = html_mod.unescape(TAG_RE.sub("", frag))
                missing = sorted({ch for ch in text if not ch.isspace() and ord(ch) not in coverage})
                if missing:
                    report.error(
                        "手写体",
                        f"第 {slide.index} 页 {label} 有 {len(missing)} 个字符不在内嵌子集里："
                        f"{''.join(missing)[:20]!r}——换台机器这些字会回退成系统字体",
                    )
                    problems += 1

    # 1d) 倾斜只许给行内公式：块级元素带 rotate/skew 会把表格/图注一起转斜
    for selector, decls in css_rules(html):
        if not re.search(r"transform\s*:[^;]*(rotate|skew)", decls, re.I):
            continue
        key = re.sub(r"\s+", " ", selector.strip())
        if key in HAND_SELECTORS or key in TILT_ALLOWED:
            continue
        if re.search(r"\b(formula|details|table|td|th|figure|figcaption|h1|p|ul|ol|section)\b", key):
            report.error(
                "倾斜",
                f"「{key}」上有 rotate/skew：块级元素一转，里面的表格横线两端就出现高差"
                "（1428px 宽的表在 0.3° 下差 7.5px）。倾斜只许挂在 .formula .expr 这种行内元素上",
            )
            problems += 1

    # 2) 下标写法：公式区里出现 X_y 就是没排成 <sub>
    bad_sub = []
    for slide in slides:
        for m in re.finditer(
            r'class="formula"[\s\S]*?</div>|<ol class="axioms">[\s\S]*?</ol>', slide.body
        ):
            chunk = TAG_RE.sub(" ", m.group(0))
            for hit in re.finditer(r"[A-Za-zΑ-Ωα-ω]\(?_[A-Za-z0-9]{1,6}", chunk):
                bad_sub.append((slide.index, hit.group(0)))
    if bad_sub:
        page, sample = bad_sub[0]
        report.warn(
            "下标写法",
            f"第 {page} 页公式里出现 {sample} 这类下划线写法（共 {len(bad_sub)} 处）：手写数学该用 <sub>，"
            "scaffold.subs() 会自动换",
        )

    # 3) 折叠块展开后是否还装得下：静态可判的一半——复算表同页有图且行数多，必然裁掉
    for slide in slides:
        recalc = [attrs for attrs, inner in find_tags(slide.body, "details") if has_class(attrs, "recalc")]
        if not recalc:
            continue
        rows = len(re.findall(r"<tr\b", slide.body))
        has_fig = bool(re.search(r"<figure\b", slide.body))
        if has_fig and rows > 8:
            report.error(
                "展开态",
                f"第 {slide.index} 页复算表 {rows} 行 + 图：details 一展开就超出 900px 被 overflow:hidden 裁掉。"
                "复算表单独成页（无图），或拆成两个 data-part",
            )
            problems += 1
        elif not has_fig and rows > 14:
            report.warn(
                "展开态",
                f"第 {slide.index} 页复算表 {rows} 行：展开后接近页高上限，跑 tools/shoot_deck.py 确认",
            )
    if not problems:
        report.ok("手写体与展开态")


# ---- 主流程 ---------------------------------------------------------------


COLOR = sys.stdout.isatty() and sys.platform != "win32"


def paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def main() -> int:
    parser = argparse.ArgumentParser(description="校验知识点讲解 HTML 幻灯片")
    parser.add_argument("html", help="幻灯片 HTML 路径")
    parser.add_argument("--min-pages", type=int, default=MIN_PAGES, help="页数下限（默认 1 = 不设下限）")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES, help="页数上限（默认 999 = 不设上限）")
    parser.add_argument("--max-eq", type=int, default=MAX_EQ, help="正文核心式上限（0 = 不设上限，默认）")
    parser.add_argument("--max-anim", type=int, default=MAX_ANIM, help="动画页上限")
    parser.add_argument("--skip-shots", action="store_true", help="不检查截图")
    args = parser.parse_args()

    html_path = Path(args.html)
    if not html_path.is_file():
        print(f"找不到文件: {html_path}")
        return 1

    html = html_path.read_text(encoding="utf-8", errors="replace")
    raw_slides = [(m.group(1), m.group(2)) for m in SLIDE_RE.finditer(html)]
    slides = [SlideInfo(index, open_tag, body) for index, (open_tag, body) in enumerate(raw_slides, start=1)]
    report = Report()

    pages = check_structure(raw_slides, report, args.min_pages, args.max_pages)
    check_page_numbers(raw_slides, report)
    check_banned(html, report)
    check_pitfalls(html, report)
    body_formulas, prep_formulas = collect_formulas(slides, report, args.max_eq)
    check_no_quiz(html, raw_slides, report)
    check_offline(html, report)
    check_css(html, report)
    check_nav(html, report)

    # 语义层
    check_axes(slides, report)
    check_recast(slides, report)
    check_dims(slides, report)
    check_phenomenon(slides, report)
    check_formula_binding(slides, body_formulas + prep_formulas, report)
    check_derivation(slides, body_formulas, report)
    check_formula_section_stats = check_formula_section(slides, prep_formulas, html, html_path, report)
    check_meta_discourse(slides, report)
    axiom_page = next((slide for slide in slides if slide.kind == "axioms"), slides[0] if slides else None)
    axioms = parse_axioms(axiom_page.body) if axiom_page else {}
    goal = (axiom_page.open_attrs.get("data-goal", "") if axiom_page else "").strip()
    prep_blocks = prep_deriv_blocks(slides)
    check_prep_admission(prep_formulas, axioms, prep_blocks, report)
    check_axiom_scope(axioms, goal, slides, report)
    check_recalc(html, report)
    check_handwriting(html, slides, report)
    check_viewport(html, report)
    check_size(html, report)
    check_kinds(slides, report)
    check_animations(slides, report, args.max_anim)
    check_duplicate_figures(slides, report)

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
    if check_formula_section_stats:
        stats = check_formula_section_stats
        print(
            f"公理 {stats['axioms']} 条 / 预备段 {stats['prep']} 页 / 正文 {stats['body']} 页 / "
            f"calc 占比 {stats['ratio']}%"
        )
    summary = f"{len(pages)} 页，{report.errors} 个错误，{report.warnings} 个警告"
    if report.errors == 0:
        print(paint(f"通过：{summary}", "32"))
        return 0
    print(paint(f"未通过：{summary}", "31"))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
