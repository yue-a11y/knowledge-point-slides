#!/usr/bin/env python3
"""把一行式子排成 Presentation MathML（<math> 元素），屏幕与打印走同一个排版。

为什么是 MathML，而不是自带定位 span：
  · 「公式必须是结构化的 MathML」是硬约束：变量 <mi>、数字 <mn>、运算符 <mo>、
    上下标 <msub>/<msup>/<msubsup>、分式 <mfrac>、根式 <msqrt> 各归其位，
    纯文本/定位 span 平铺一律算没做（check_deck.py C9 起全部 error）。
  · 不用 MathJax / KaTeX / polyfill / CDN：Chromium 109+ 原生支持 MathML Core，
    单文件离线、断网打开仍成立；字体仍是内嵌的 DeckMath（Latin Modern Math 子集），
    变量的数学斜体来自该字体的 MATH 表，不是 CSS 合成斜体。
  · weasyprint **不支持 MathML**（实测 70.0：<math> 被当未知行内元素，上下标拍平、
    分式塌成一行、斜体丢失）。所以 weasyprint 不再是打印源：打印走
    tools/shoot_deck.py 的 Chromium page.pdf()，屏幕态与 deck-print.pdf 同引擎同观感；
    weasyprint 只留作「页数交叉验证」（页数由 @page + 每页一屏决定，与公式排版无关）。

用法（生成器里）:
    from mathrender import math
    math("j = j_0 e^{η/b_a}")
        → <math xmlns="http://www.w3.org/1998/Math/MathML"><mi data-sym="j">j</mi>…

分式一律二维（契约「分式与量纲斜杠」，check_deck.py C12 硬校验）:
    真分式 = 分子、分母各是一个完整式子 → 排成 <mfrac>。DSL 里写 `a/b` 就自动二维，
    不必手写 \\frac；\\frac{分子}{分母} 仍然可用（指数里也能嵌套）。
    量纲斜杠 = 斜杠两侧都是单位词（mA/cm²、mV/dec、mol/L）→ 保留 <mo>/</mo>，不许二维。
    「分母整组」：Δη/Δlog₁₀ j 的分母是整个 Δlog₁₀ j，RT/α_aF 的分母是 α_aF 整体；
    解析时分子取「斜杠前的那一项」、分母取「斜杠后到加减/关系符为止的整项」，
    所以 `Δη/Δlog_{10} j` 与 `RT/α_aF` 自动就是整组分母，不需要额外加 {}。

语法（LaTeX 的一小撮）:
    x_0 / x_{eq}          下标（单字符或 {…} 组）
    x^2 / x^{η/b_a}       上标；上标里可以再带下标（b_a）
    x_1^2                 上下标同时出现 → <msubsup>
    a/b                   真分式 → <mfrac>；两侧都是单位词时保留斜杠（mA/cm²）
    \\frac{分子}{分母}      显式真分式 → <mfrac>（指数里也能嵌套）
    \\sqrt{x}              根式 → <msqrt>
    \\text{…}              正体文字 → <mtext>（用正文手写体 DeckText 排，可放中文/单位）
    其余字符自动分类：
        变量 → <mi>（拉丁/希腊小写单字母，数学斜体；e、i、d 与希腊大写走正体）
        数字 → <mn>；运算符/关系符/括号 → <mo>
        单位词（mV、dec、cm、mol…，只在「字母连写且命中单位表」时）→ <mtext>
        ×10ⁿ 这类 Unicode 上下标先由 normalize() 换成 _{} / ^{} 再解析

MathML 的排版细节交给浏览器：运算符间距、上下标缩放/位移、分式与根式的高度
都按 MATH 表算（Latin Modern Math 的 scriptPercentScaleDown = 70%），
所以本文件不再手写 top/line-height 之类的定位。
"""
from __future__ import annotations

import html
import re

# 数学斜体区块（Unicode Mathematical Alphanumeric Symbols）—— 只在 plain() 里用来还原
_IT_A, _IT_a = 0x1D434, 0x1D44E
_IT_GREEK_a = 0x1D6FC
GREEK_LOWER = "αβγδεζηθικλμνξοπρστυφχψω"
GREEK_UPPER = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
GREEK = GREEK_LOWER + GREEK_UPPER

FUNCS = ("exp", "ln", "log", "sin", "cos", "tan", "cot", "sec", "csc",
         "max", "min", "lim", "det", "arg", "Re", "Im")
UPRIGHT_LETTERS = {"e", "i", "d"}        # 常数 / 微分算子：参考图里 e 是正体

# 单位词：字母连写命中这张表 → <mtext>（正文手写体），不当作变量斜体。
# 只收不会与变量名冲突的多字母单位；单字母 V / A / K 有歧义（A 是面积、V 是电位），
# 所以公式里要写单位请用 \\text{V}。
# 多字母但整段正体的记号（不是几个变量相乘）：pH、pKa、RHE… 命中就整段一个 <mi>
LABELS = ("pKa", "pH", "RHE", "SHE", "OCV", "EIS", "LSV", "HER", "OER", "ORR", "RDE", "RRDE")
# 量纲位置上的非单位记号：mV/pH、mV/pKa 的分母是「每 pH 单位」，按量纲词对待
UNIT_LABELS = {"pH", "pKa"}

UNITS = {
    "mV", "mA", "MV", "uA", "µA", "nA", "pA", "dec", "mol", "mmol", "min",
    "sec", "cm", "mm", "nm", "µm", "um", "km", "dm", "ms", "us", "µs", "ns",
    "Hz", "kHz", "MHz", "eV", "keV", "meV", "kJ", "cal", "atm", "bar",
    "ppm", "ppb", "rpm",
}

# 单字母单位：只在「紧跟在数字后面、后面不再接字母」时才算单位（0.100 V、300 K）。
# 这样 j = I / A 里的 A 仍是面积变量，2.303RT 里的 R、T 仍是变量。
SINGLE_UNITS = {"V", "A", "K", "J", "W", "s", "m", "g", "L", "C", "N", "h"}

RELATIONS = set("=≡≈≅≃≠≤≥∼∝<>")
BINARIES = set("+−-±∓×÷·⋅∗")
PUNCT = set(",;:")
FENCES = set("()[]{}|")
# 中文标点：整段是散文的一部分（推导表的注释），用 mtext 走正文手写体
CJK_PUNCT = set("，。；：、（）【】《》「」『』—…“”‘’")

# ---- 「分式还是量纲斜杠」的判定 ---------------------------------------------
# 「项」的边界：加减、关系符、逗号、右括号、中文标点。遇到这些就停，
# 于是 Δη/Δlog₁₀ j 的分母是整组 Δlog₁₀ j（不是只有 Δ），RT/α_aF 的分母是 α_aF 整组。
TERM_STOP = (RELATIONS
             | {"+", "−", "-", "±", "∓", "÷", "→", "←", "↔", "⇒", "⇔"}
             | set(",;:)]}") | CJK_PUNCT)
# 显式乘号：算在同一个「项」里（2.303RT/F 的分子是 2.303RT 整组）
MULT_JOIN = set("·×∗⋅")
# 能当操作数/分母节点的 MathML 种类
OPERAND_KINDS = {"mi", "mn", "mtext", "msub", "msup", "msubsup", "mfrac", "msqrt"}
# 成对的括号：整组当一个操作数（(η₂−η₁)/(…) 的分子就是整组括号）
FENCE_PAIRS = {"(": ")", "[": "]"}


def _unit_word(text: str) -> bool:
    """单位词：命中单位表，或是 ≤6 个纯字母的短词（mol、mg、mL、dec…）。"""
    word = text.strip()
    return (word in UNITS or word in SINGLE_UNITS
            or re.fullmatch(r"[A-Za-zµμ°Ω‰]{1,6}", word) is not None)


def _numeric(node: tuple) -> bool:
    """指数是不是「一个数」（2 / −1 / −3）。"""
    if node[0] == "mn":
        return True
    if node[0] == "mo":
        return node[1] in ("−", "-", "+")
    if node[0] == "mrow":
        return bool(node[1]) and all(_numeric(child) for child in node[1])
    return False


def _unit_text(node: tuple) -> bool:
    """节点是不是纯量纲文本：<mtext>mA</mtext>、<msup><mtext>cm</mtext><mn>2</mn></msup>、pH。"""
    if node[0] == "mtext":
        return _unit_word(node[1])
    if node[0] == "mi" and isinstance(node[1], str) and node[1] in UNIT_LABELS:
        return True
    if node[0] == "msup" and node[1][0] == "mtext":
        return _unit_word(node[1][1]) and _numeric(node[2])
    if node[0] == "mrow":
        return bool(node[1]) and all(_unit_text(child) for child in node[1])
    return False


def _is_unit_expr(run: list[tuple]) -> bool:
    """整段是不是「量纲写法」：单位词，或「一个数 + 单位词」（59.2 mV）。

    是 → 斜杠保留（mA/cm²、mV/dec）；不是 → 真分式，排成 <mfrac>。
    """
    core = [n for n in run if not (n[0] == "mo" and n[1] in MULT_JOIN)]
    if not core:
        return False
    lead = 1 if core[0][0] == "mn" else 0
    return len(core) > lead and all(_unit_text(n) for n in core[lead:])


def _has_cjk(text: str) -> bool:
    return any("\u3400" <= ch <= "\u4dbf" or "\u4e00" <= ch <= "\u9fff" for ch in text)


def _is_operand(node: tuple) -> bool:
    """能当分子/分母一部分的节点；中文注释（mtext）不算，免得分母吞掉后面的散文。"""
    if node[0] == "mtext" and _has_cjk(node[1]):
        return False
    return node[0] in OPERAND_KINDS or node[0] == "mrow"


def _as_node(run: list[tuple]) -> tuple:
    if len(run) == 1:
        return run[0]
    return ("mrow", run)


TAG_RE = re.compile(r"<[^>]+>")

_SUB_DIGITS = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
               "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
               "₊": "+", "₋": "−", "₌": "=", "₍": "(", "₎": ")",
               "ₐ": "a", "ₑ": "e", "ₕ": "h", "ᵢ": "i", "ⱼ": "j", "ₖ": "k",
               "ₗ": "l", "ₘ": "m", "ₙ": "n", "ₒ": "o", "ₚ": "p", "ᵣ": "r",
               "ₛ": "s", "ₜ": "t", "ᵤ": "u", "ᵥ": "v", "ₓ": "x"}
_SUP_DIGITS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
               "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
               "⁺": "+", "⁻": "−", "⁼": "=", "⁽": "(", "⁾": ")",
               "ⁿ": "n", "ⁱ": "i"}

UNICODE_SCRIPTS = set(_SUB_DIGITS) | set(_SUP_DIGITS)

# 内嵌数学字体（Latin Modern Math 子集）覆盖的字符：不在里面的常见关系符（≫ ≪ ≦ ≧ …）
# 走 <mtext>（正文手写体 DeckText 有这些字形），否则会回退到系统字体。
# 子集由 scripts/make_mathfont.py 的 CHARS 决定，这里直接复用，避免两份清单漂移。
try:  # pragma: no cover - 只是取常量
    from make_mathfont import CHARS as _MATH_SUBSET
except Exception:  # noqa: BLE001 - 取不到就退回保守集合（ASCII + 希腊 + 常用运算符）
    _MATH_SUBSET = set(chr(c) for c in range(0x20, 0x7F)) | set(GREEK) | set(
        "−–—×÷·⋅±∓≤≥≠≈≡≃≅∝∞∂∆∑∏∫√°µΩ′″…∈∉⊂⊃∪∩∖∀∃∅→←↔⇒⇔")
MATH_SUBSET = set(_MATH_SUBSET)

_ESC_MAP = {"&lt;": "<", "&gt;": ">", "&amp;": "&", "&quot;": '"', "&#39;": "'"}


def _unescape(text: str) -> str:
    for entity, char in _ESC_MAP.items():
        text = text.replace(entity, char)
    return text


def normalize(expr: str) -> str:
    """把 Unicode 上下标（j₀ / log₁₀ / mV²）换成 _{} / ^{} 写法，连续数字并成一组。"""
    out = []
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch in _SUB_DIGITS:
            j = i
            while j < len(expr) and expr[j] in _SUB_DIGITS:
                j += 1
            out.append("_{" + "".join(_SUB_DIGITS[c] for c in expr[i:j]) + "}")
            i = j
        elif ch in _SUP_DIGITS:
            j = i
            while j < len(expr) and expr[j] in _SUP_DIGITS:
                j += 1
            out.append("^{" + "".join(_SUP_DIGITS[c] for c in expr[i:j]) + "}")
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


# ---- 解析：字符串 → 节点树 ------------------------------------------------

# 节点是 (kind, payload)：
#   ("mi", 文本) / ("mn", 文本) / ("mo", 文本) / ("mtext", 文本)
#   ("mrow", [子节点]) / ("mfrac", 分子节点, 分母节点) / ("msqrt", 参数节点)
#   ("msub", 底, 下标) / ("msup", 底, 上标) / ("msubsup", 底, 下标, 上标)


class _Parser:
    def __init__(self, expr: str) -> None:
        self.src = expr
        self.i = 0

    def parse(self) -> list[tuple]:
        return self._seq(stop="")

    # -- 基础 --
    def _peek(self) -> str:
        return self.src[self.i] if self.i < len(self.src) else ""

    def _skip_space(self) -> None:
        while self.i < len(self.src) and self.src[self.i].isspace():
            self.i += 1

    def _braced(self) -> str:
        """吃掉一个 {…}（或单字符），返回里面的原文。"""
        self._skip_space()
        if self._peek() == "{":
            depth, j = 1, self.i + 1
            while j < len(self.src) and depth:
                if self.src[j] == "{":
                    depth += 1
                elif self.src[j] == "}":
                    depth -= 1
                j += 1
            inner = self.src[self.i + 1:j - 1]
            self.i = j
            return inner
        if self.i < len(self.src):
            ch = self.src[self.i]
            self.i += 1
            return ch
        return ""

    def _script_arg(self, kind: str) -> str:
        """上下标的实参：{…} 整组；否则下标吃字母数字连写（E_eq、b_app），上标吃一个数字。"""
        self._skip_space()
        if self._peek() == "{":
            return self._braced()
        j = self.i
        if kind == "_":
            while j < len(self.src) and re.match(r"[A-Za-z0-9]", self.src[j]):
                j += 1
        else:
            while j < len(self.src) and (self.src[j].isdigit() or
                                         (j == self.i and self.src[j] in "+−-⁺⁻")):
                j += 1
            if j == self.i:
                j = self.i + 1
        arg = self.src[self.i:j]
        self.i = j
        return arg

    def _group(self, text: str) -> tuple:
        nodes = _Parser(text).parse()
        if len(nodes) == 1:
            return nodes[0]
        return ("mrow", nodes)

    def _script_group(self, text: str) -> tuple:
        """上下标实参：多字母是「标签」（eq / ref / app）→ 一个正体 <mi>；否则照常解析。"""
        if re.fullmatch(r"[A-Za-z]{2,}", text):
            return ("mi", text)
        return self._group(text)

    # -- 主循环 --
    def _seq(self, stop: str) -> list[tuple]:
        nodes: list[tuple] = []
        while self._step(nodes, stop):
            pass
        return nodes

    def _step(self, nodes: list[tuple], stop: str) -> bool:
        """吃一个 token 追加到 nodes；遇到 stop / 结尾返回 False。"""
        self._skip_space()
        ch = self._peek()
        if not ch or (stop and ch == stop):
            return False
        if ch == "{":
            nodes.append(self._group(self._braced()))
            return True
        if ch == "\\":
            nodes.append(self._command())
            return True
        if ch in "_^":
            self.i += 1
            script = self._script_group(self._script_arg(ch))
            nodes[:] = self._attach(nodes, ch, script)
            return True
        if ch in FENCE_PAIRS:
            close = FENCE_PAIRS[ch]
            self.i += 1
            inner = self._seq(stop=close)
            if self._peek() == close:
                self.i += 1
            nodes.append(("mrow", [("mo", ch)] + inner + [("mo", close)]))
            return True
        if ch == "/":
            self.i += 1
            self._fraction(nodes)
            return True
        if ch in CJK_PUNCT or ("\u4e00" <= ch <= "\u9fff"):
            j = self.i
            while j < len(self.src) and (self.src[j] in CJK_PUNCT or
                                         "\u4e00" <= self.src[j] <= "\u9fff"):
                j += 1
            nodes.append(("mtext", self.src[self.i:j]))
            self.i = j
            return True
        if ch.isdigit():
            j = self.i
            while j < len(self.src) and (self.src[j].isdigit() or
                                         (self.src[j] == "." and j + 1 < len(self.src)
                                          and self.src[j + 1].isdigit())):
                j += 1
            nodes.append(("mn", self.src[self.i:j]))
            self.i = j
            return True
        if (ch.isalpha() or ch in GREEK) and not ("\u4e00" <= ch <= "\u9fff"):
            j = self.i
            while j < len(self.src) and (self.src[j].isalpha() or self.src[j] in GREEK) \
                    and not ("\u4e00" <= self.src[j] <= "\u9fff"):
                j += 1
            run = self.src[self.i:j]
            prev = nodes[-1] if nodes else None
            nodes.extend(self._letters(run, prev))
            self.i = j
            # E° / E°′：度数符号贴在符号上，不当独立算符（否则 MathML 会在中间加空格）
            while self.i < len(self.src) and self.src[self.i] == "°" and len(run) == 1:
                nodes[-1] = ("msup", nodes[-1], ("mo", "°"))
                self.i += 1
            return True
        nodes.append(self._symbol(ch))
        self.i += 1
        return True

    # -- 斜杠：真分式 → mfrac；量纲写法 → 保留 / --
    def _fraction(self, nodes: list[tuple]) -> None:
        """`a/b` 的两条路：两侧都是单位词则留斜杠，否则排成二维 <mfrac>。

        分子 = 斜杠前那一项（含 2.303RT 这种隐式/显式乘法链）；
        分母 = 斜杠后到加减/关系符为止的整项（Δlog₁₀ j、α_aF 都是整组）。
        """
        numerator = self._pop_operand_run(nodes)
        denominator = self._term()
        if _is_unit_expr(numerator) and _is_unit_expr([denominator]):
            nodes.extend(numerator)
            nodes.append(("mo", "/"))
            nodes.append(denominator)
            return
        nodes.append(("mfrac", _as_node(numerator), denominator))

    @staticmethod
    def _pop_operand_run(nodes: list[tuple]) -> list[tuple]:
        """从已解析的节点尾部取出一个「项」当分子（会从 nodes 里删除）。"""
        run: list[tuple] = []
        while nodes and (_is_operand(nodes[-1])
                         or (nodes[-1][0] == "mo" and nodes[-1][1] in MULT_JOIN)):
            run.insert(0, nodes.pop())
        return run

    def _term(self) -> tuple:
        """往前读一个「项」当分母：遇到加减/关系符/右括号/中文标点/结尾就停。"""
        nodes: list[tuple] = []
        while True:
            self._skip_space()
            ch = self._peek()
            # 中文注释是散文，不能当分母的一部分（否则 j/j_0 偏 0.4 个 dec 会被吞进分母）
            if not ch or ch in TERM_STOP or _has_cjk(ch):
                break
            if not self._step(nodes, stop=""):
                break
        return _as_node(nodes)

    def _command(self) -> tuple:
        for name, handler in (("\\text{", self._text), ("\\frac{", self._frac),
                              ("\\sqrt{", self._sqrt)):
            if self.src.startswith(name, self.i):
                return handler()
        # 未知命令：原样当运算符
        j = self.i + 1
        while j < len(self.src) and self.src[j].isalpha():
            j += 1
        raw = self.src[self.i:j]
        self.i = j
        return ("mo", raw)

    def _text(self) -> tuple:
        body = self._braced()
        return ("mtext", body)

    def _frac(self) -> tuple:
        self.i += len("\\frac")          # 跳过命令本身，留下 {
        numerator = self._braced()
        denominator = self._braced()
        return ("mfrac", self._group(numerator), self._group(denominator))

    def _sqrt(self) -> tuple:
        self.i += len("\\sqrt")
        body = self._braced()
        return ("msqrt", self._group(body))

    # -- 上下标：挂到前一个节点上 --
    def _attach(self, nodes: list[tuple], kind: str, script: tuple) -> list[tuple]:
        if not nodes:
            base: tuple = ("mrow", [])
        else:
            base = nodes.pop()
        if base[0] == "msub" and kind == "^":
            return nodes + [("msubsup", base[1], base[2], script)]
        if base[0] == "msup" and kind == "_":
            return nodes + [("msubsup", base[1], script, base[2])]
        return nodes + [("msub" if kind == "_" else "msup", base, script)]

    # -- 字母连写：函数名整段正体，单位词走 mtext，其余逐字母 <mi> --
    def _letters(self, run: str, prev: tuple | None = None) -> list[tuple]:
        out: list[tuple] = []
        i = 0
        for label in LABELS:
            if run == label:
                return [("mi", label)]
        # 单字母单位：跟在数字后面、且后面不再接字母（0.100 V / 300 K）
        if (len(run) == 1 and run in SINGLE_UNITS
                and prev is not None and prev[0] in ("mn", "mtext")):
            return [("mtext", run)]
        while i < len(run):
            label = next((lb for lb in LABELS if run.startswith(lb, i)), None)
            if label:
                out.append(("mi", label))
                i += len(label)
                continue
            for fn in FUNCS:
                if run.startswith(fn, i):
                    out.append(("mi", ("fn", fn)))
                    i += len(fn)
                    break
            else:
                if run[i:i + 4] in UNITS:
                    out.append(("mtext", run[i:i + 4]))
                    i += 4
                    continue
                if run[i:i + 3] in UNITS:
                    out.append(("mtext", run[i:i + 3]))
                    i += 3
                    continue
                if run[i:i + 2] in UNITS:
                    out.append(("mtext", run[i:i + 2]))
                    i += 2
                    continue
                out.append(("mi", run[i]))
                i += 1
        return out

    def _symbol(self, ch: str) -> tuple:
        if ch not in MATH_SUBSET:
            return ("mtext", ch)
        if ch in RELATIONS or ch in BINARIES or ch in PUNCT or ch in FENCES or ch in "/%":
            return ("mo", ch)
        if ch in CJK_PUNCT or ("\u4e00" <= ch <= "\u9fff"):
            return ("mtext", ch)
        return ("mo", ch)


def _mi_attrs(char: str) -> str:
    """单字母变量的属性：正体字母（e/i/d、希腊大写）不加 data-sym（它们不是量）。"""
    upright = char in UPRIGHT_LETTERS or char in GREEK_UPPER
    attrs = ""
    if not upright and _EMIT_SYM.get("on", True):
        attrs += f' data-sym="{html.escape(char, quote=True)}"'
    if upright:
        attrs += ' mathvariant="normal"'
    return attrs


def _emit(node: tuple) -> str:
    kind = node[0]
    if kind == "mi":
        payload = node[1]
        if isinstance(payload, tuple):  # 函数名
            return f"<mi>{html.escape(payload[1])}</mi>"
        if len(payload) > 1:            # 多字母标识（标签）
            return f"<mi>{html.escape(payload)}</mi>"
        return f"<mi{_mi_attrs(payload)}>{html.escape(payload)}</mi>"
    if kind in ("mn", "mo", "mtext"):
        return f"<{kind}>{html.escape(node[1])}</{kind}>"
    if kind == "mrow":
        children = node[1]
        if not children:
            return "<mrow></mrow>"
        out: list[str] = []
        prev: tuple | None = None
        for child in children:
            # 「数 + 单位」之间补一个细空格：MathML 把 <mn>60.0</mn><mtext>mV</mtext>
            # 当两个相邻原子直接拼，会渲染成 60.0mV（实测）
            if (prev is not None and prev[0] == "mn" and child[0] == "mtext"
                    and (child[1] in UNITS or child[1] in SINGLE_UNITS)):
                out.append('<mspace width="0.17em"/>')
            out.append(_emit(child))
            prev = child
        return "<mrow>" + "".join(out) + "</mrow>"
    if kind == "mfrac":
        return f"<mfrac>{_emit(node[1])}{_emit(node[2])}</mfrac>"
    if kind == "msqrt":
        return f"<msqrt>{_emit(node[1])}</msqrt>"
    if kind == "msub":
        return f"<msub>{_emit(node[1])}{_emit(node[2])}</msub>"
    if kind == "msup":
        return f"<msup>{_emit(node[1])}{_emit(node[2])}</msup>"
    if kind == "msubsup":
        return f"<msubsup>{_emit(node[1])}{_emit(node[2])}{_emit(node[3])}</msubsup>"
    raise ValueError(f"未知节点类型 {kind}")


_EMIT_SYM = {"on": True}


def math(expr: str, syms=None, mark_syms: bool = True) -> str:
    """把一行式子排成 Presentation MathML；mark_syms=True 时每个变量标 data-sym（式图绑定用）。

    散文里的行内 <math>（标题、图注、推导表注释）不参与「符号 ↔ 图」绑定，
    传 mark_syms=False，避免把 Faraday 常数这类只在注释里出现的字母算成孤儿符号。
    """
    _EMIT_SYM["on"] = bool(mark_syms)
    try:
        body = _emit(("mrow", _Parser(normalize(_unescape(expr))).parse()))
    finally:
        _EMIT_SYM["on"] = True
    return ('<math xmlns="http://www.w3.org/1998/Math/MathML" display="inline">'
            f"{body}</math>")


# ---- 反解析：MathML → 可读文本（校验脚本比对用） -------------------------

def _node_text(node: tuple) -> str:
    kind = node[0]
    if kind == "mi":
        payload = node[1]
        return payload[1] if isinstance(payload, tuple) else payload
    if kind in ("mn", "mo", "mtext"):
        return node[1]
    if kind == "mrow":
        return "".join(_node_text(child) for child in node[1])
    if kind == "mfrac":
        return f"{_node_text(node[1])}/{_node_text(node[2])}"
    if kind == "msqrt":
        return f"√{_node_text(node[1])}"
    if kind == "msub":
        return f"{_node_text(node[1])}_{_node_text(node[2])}"
    if kind == "msup":
        return f"{_node_text(node[1])}^{_node_text(node[2])}"
    if kind == "msubsup":
        return f"{_node_text(node[1])}_{_node_text(node[2])}^{_node_text(node[3])}"
    return ""


def plain(expr: str) -> str:
    """DSL → 纯文本（把数据读回来核对时用）。"""
    return _node_text(("mrow", _Parser(normalize(_unescape(expr))).parse()))


# 公式元素自己的样式：字体只挂 math 元素；mtext（中文/单位）走正文手写体。
# 运算符间距、上下标缩放与位移、分式与根式的高度全部交给 MathML 布局，
# 这里不再出现 top / line-height 之类的定位（那是旧 span 方案的事）。
MATH_CSS = """  math { font-family: var(--math); font-size: 1em; line-height: 1.25; }
  math mtext { font-family: var(--text); font-size: .92em; }
  math mi, math mn, math mo { white-space: nowrap; }
"""


if __name__ == "__main__":
    import sys

    for line in sys.argv[1:] or ["j = j_0 e^{η/b_a}"]:
        print(math(line))
        print(plain(line))
