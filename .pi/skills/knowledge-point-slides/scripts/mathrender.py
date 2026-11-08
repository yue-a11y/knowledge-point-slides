#!/usr/bin/env python3
"""把一行数学式子排成「参考图」那种排版：衬线斜体变量、正体常数与数字、真上下标、指数内斜杠分式。

为什么自己写一个小排版器，而不是 MathML / KaTeX：
  · KaTeX 要几十个字体文件 + 200KB JS，单文件 320KB 装不下；
  · MathML 在 weasyprint 里不支持，打印与屏幕会不一致；
  · 本仓库的式子只有「变量 / 数字 / 运算符 / 上下标 / 括号」这几种成分，
    用 HTML 的定位 span 就能排准，而且两个渲染引擎（Chromium / weasyprint）都一致。

用法（生成器里）:
    from mathrender import math
    math("j = j_0 e^{η/b_a}")      →  <span class="mth">…</span>

语法（LaTeX 的一小撮）:
    x_0 / x_{eq}        下标（单个字符或 {…} 组）
    x^2 / x^{η/b_a}     上标；上标里可以再带下标（b_a）
    \\text{…}            正体文字（函数名、单位、中文注释）
    其余字符按「变量斜体 / 数字正体 / 运算符正体」自动分类

排版规则（与参考图对齐）:
    · 变量：拉丁/希腊小写单字母 → 数学斜体字形（U+1D434… / U+1D6FC…，真正的 CM 斜体，
      不是 CSS 合成斜体）；大写希腊与数字、运算符、括号一律正体。
    · e（自然常数）正体；exp / ln / log / sin / cos / tan / max / min 等函数名正体。
    · 上下标字号 0.7em，嵌套再乘 0.72；上标抬到 x-height 之上（-.42em），
      下标压到基线下（+.2em）；全部 line-height:0，不改变整行基线节奏。
    · = ≡ ≈ ≤ ≥ 两侧 .28em，+ − × · / 两侧 .16em；逗号后 .12em。
"""
from __future__ import annotations

import html
import re

# 数学斜体区块（Unicode Mathematical Alphanumeric Symbols）
_IT_A, _IT_a = 0x1D434, 0x1D44E          # 𝐴…𝑍 / 𝑎…𝑧
_IT_GREEK_a = 0x1D6FC                    # 𝛼…𝜔（小写）
GREEK_LOWER = "αβγδεζηθικλμνξοπρστυφχψω"
GREEK_UPPER = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"

FUNCS = ("exp", "ln", "log", "sin", "cos", "tan", "cot", "sec", "csc",
         "max", "min", "lim", "det", "arg", "Re", "Im")
UPRIGHT_LETTERS = {"e", "i", "d"}        # 常数 / 微分算子：参考图里 e 是正体

RELATIONS = set("=≡≈≅≃≠≤≥∼∝")
BINARIES = set("+−-±∓×÷·⋅")
PUNCT = set(",;:")

TAG_RE = re.compile(r"<[^>]+>")


def _italic(ch: str) -> str | None:
    if "a" <= ch <= "z":
        return chr(_IT_a + ord(ch) - ord("a"))
    if "A" <= ch <= "Z":
        return chr(_IT_A + ord(ch) - ord("A"))
    if ch in GREEK_LOWER:
        return chr(_IT_GREEK_a + GREEK_LOWER.index(ch))
    return None


def _span(cls: str, inner: str) -> str:
    return f'<span class="{cls}">{inner}</span>' if cls else inner


def _plain(html_fragment: str) -> str:
    """把渲染片段还原成可读符号名：去掉标签、把数学斜体映射回 ASCII/希腊。"""
    import html as _html

    text = _html.unescape(TAG_RE.sub("", html_fragment))
    out = []
    for ch in text:
        code = ord(ch)
        if 0x1D434 <= code <= 0x1D44D:
            out.append(chr(ord("A") + code - 0x1D434))
        elif 0x1D44E <= code <= 0x1D467:
            out.append(chr(ord("a") + code - 0x1D44E))
        elif 0x1D6FC <= code <= 0x1D71B:
            out.append(GREEK_LOWER[code - 0x1D6FC])
        else:
            out.append(ch)
    return "".join(out)


def _script(kind: str, body: str, depth: int) -> str:
    # 多字母下标是「标签」（eq / ref / app），按正体排；单字母下标才是变量（a / c / i）
    if re.fullmatch(r"[A-Za-z]{2,}", body):
        inner = html.escape(body)
    else:
        inner = _render_tokens(_tokenize(body), depth + 1, wrap=False)
    return f'<span class="scr {kind}">{inner}</span>'


def _var(name: str, inner: str) -> str:
    return f'<var data-sym="{name}">{inner}</var>'


def _render_letter_run(run: str, depth: int, _wrap: bool = True) -> str:
    """一段连续字母：函数名整体正体；变量逐字斜体并包成 <var data-sym>。"""
    out = []
    i = 0
    while i < len(run):
        for fn in FUNCS:
            if run.startswith(fn, i):
                out.append(f'<span class="fn">{fn}</span>')
                i += len(fn)
                break
        else:
            ch = run[i]
            italic = _italic(ch)
            if italic and ch not in UPRIGHT_LETTERS:
                out.append(_var(ch, italic) if _wrap else italic)
            else:
                out.append(html.escape(ch))
            i += 1
    return "".join(out)


def _tokenize(expr: str) -> list[tuple[str, str]]:
    """切成 (类型, 内容)：text / group / sub / sup / letters / other。"""
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(expr)
    while i < n:
        ch = expr[i]
        if ch == "\\" and expr.startswith("\\text{", i):
            depth, j = 1, i + 6
            while j < n and depth:
                if expr[j] == "{":
                    depth += 1
                elif expr[j] == "}":
                    depth -= 1
                j += 1
            tokens.append(("text", expr[i + 6:j - 1]))
            i = j
            continue
        if ch in "_^":
            kind = "sub" if ch == "_" else "sup"
            i += 1
            if i < n and expr[i] == "{":
                depth, j = 1, i + 1
                while j < n and depth:
                    if expr[j] == "{":
                        depth += 1
                    elif expr[j] == "}":
                        depth -= 1
                    j += 1
                tokens.append((kind, expr[i + 1:j - 1]))
                i = j
            elif i < n:
                tokens.append((kind, expr[i]))
                i += 1
            continue
        if ch == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if expr[j] == "{":
                    depth += 1
                elif expr[j] == "}":
                    depth -= 1
                j += 1
            tokens.append(("group", expr[i + 1:j - 1]))
            i = j
            continue
        if ch.isspace():
            i += 1
            continue
        if ch.isalpha():
            j = i
            while j < n and expr[j].isalpha():
                j += 1
            tokens.append(("letters", expr[i:j]))
            i = j
            continue
        j = i + 1
        while j < n and not (expr[j].isalpha() or expr[j] in "_^{} \\") and not expr[j].isspace():
            j += 1
        tokens.append(("other", expr[i:j]))
        i = j
    return tokens


def _render_tokens(tokens: list[tuple[str, str]], depth: int, wrap: bool = True) -> str:
    out: list[str] = []
    i = 0
    while i < len(tokens):
        kind, body = tokens[i]
        # 变量 + 紧随的上下标 → 合成一个 <var data-sym="base_script">
        if kind == "letters":
            rendered = _render_letter_run(body, depth, wrap)
            scripts = ""
            j = i + 1
            while j < len(tokens) and tokens[j][0] in ("sub", "sup"):
                scripts += _script(tokens[j][0], tokens[j][1], depth)
                j += 1
            base = body if len(body) == 1 else ""
            if body in FUNCS and scripts:
                out.append(f'<span class="fn">{body}{scripts}</span>')
                i = j
                continue
            if wrap and scripts and base and _italic(base) and base not in UPRIGHT_LETTERS:
                # 变量 + 上下标合成一个 var；base 不再单独包 var（避免 var 套 var）
                name = _plain(_italic(base)) + "_" + _plain(scripts)
                out.append(_var(name, _italic(base) + scripts))
            else:
                out.append(rendered + scripts)
            i = j
            continue
        if kind == "text":
            out.append(_span("fn", html.escape(body)))
        elif kind in ("sub", "sup"):
            out.append(_script(kind, body, depth))
        elif kind == "group":
            out.append(_render_tokens(_tokenize(body), depth))
        else:
            for ch in body:
                if ch in RELATIONS:
                    out.append(f'<span class="rel">{html.escape(ch)}</span>')
                elif ch in BINARIES:
                    out.append(f'<span class="op">{html.escape(ch)}</span>')
                elif ch == "/":
                    out.append('<span class="slash">/</span>')
                elif ch in PUNCT:
                    out.append(f'<span class="punct">{html.escape(ch)}</span>')
                else:
                    out.append(html.escape(ch))
        i += 1
    return "".join(out)


_SUB_DIGITS = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
               "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9"}
_SUP_DIGITS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
               "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"}


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


def math(expr: str, syms: list[str] | None = None) -> str:
    """把一行式子排成 HTML。变量自动包 <var data-sym="j_0">（式图绑定要用）。"""
    return f'<span class="mth">{_render_tokens(_tokenize(normalize(expr)), 0)}</span>'


MATH_CSS = """  .mth { font-family: var(--math); white-space: nowrap; }
  .mth .scr { font-size: .7em; line-height: 0; position: relative; display: inline-block; }
  .mth .scr.sub { top: .2em; }
  .mth .scr.sup { top: -.42em; }
  .mth .scr .scr { font-size: .72em; }
  .mth .scr .scr.sup { top: -.3em; }
  .mth .scr .scr.sub { top: .16em; }
  .mth .rel { margin: 0 .22em; }
  .mth .op { margin: 0 .16em; }
  .mth .punct { margin-right: .12em; }
  .mth .slash { margin: 0 .03em; }
  .mth .fn { font-style: normal; margin-right: .12em; }
  .mth var { font-style: normal; }
"""


if __name__ == "__main__":
    import sys

    for line in sys.argv[1:] or ["j = j_0 e^{η/b_a}"]:
        print(math(line))
