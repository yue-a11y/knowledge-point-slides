#!/usr/bin/env python3
"""把 tests/fixtures/tafel-deck.html 公式区升级到「Presentation MathML」这一版。

fixture 是手写的静态样本，历史上公式是 <var> + 定位 span（.mth/.scr）平铺的；这个脚本：
  1) 用 scaffold.CSS 替换 <style>（保留 fixture 自己的版式微调）；
  2) 把每个 .formula 的式子主体换成 mathrender 的 <math>（包 .expr，1px 方框由 CSS 给）；
  3) 把 A 节的 .eq 也换成 mathrender；
  4) 推导表 / 复算表逐格重排：式子列整格一个 <math>（中文注释进 <mtext>），
     依据列 / 对应列走散文（含 Unicode 上下标的词自动变行内 <math>）；
  5) 调 scaffold.embed_text_font 内嵌 DeckText。

跑一次即可；改完的 HTML 是静态的（smoke 不依赖这个脚本）。
    python3 tests/fixtures/rebuild.py
"""
from __future__ import annotations

import html as html_mod
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".pi/skills/knowledge-point-slides/scripts"))
import scaffold  # noqa: E402
from check_deck import _math_inner_text  # noqa: E402  拍平 MathML → DSL 文本（只一份实现）

MATH = scaffold.mathrender.math
S = scaffold.subs
FIX = Path(__file__).resolve().parent / "tafel-deck.html"

# fixture 里公式的 DSL 写法（与页面上的观感一一对应）
FORMULAS = {
    "P1": "j = j_0 e^{η/b_a}",
    "P2": "b = Δη / Δlog_{10} j",
    "1": "η = E − E_{eq}",
    "2": "b = Δη / Δlog_{10} j",
}
AXIOMS = {
    "A1": "η ≡ E − E_{eq}",
    "A2": "j = I / A",
    "A3": "j = j_0[exp(α_aFη/RT) − exp(−α_cFη/RT)]",
    "A4": "E_{eq} = 0.00 V",
    "A5": "k = Δy / Δx",
}

EXTRA_CSS = """  .slide { display: flex; flex-direction: column; justify-content: center; padding: 48px; }
  h1 { font-size: 40px; margin: 0 0 24px; }
  .formula { margin-top: 16px; }
  ol.axioms { font-size: 24px; }
  details.deriv { font-size: 19px; }
"""

TD_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S)
TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
MATH_RE = re.compile(r"<math\b[^>]*>(.*?)</math>", re.S | re.I)
# 上下标闭合后打一个占位符：Δlog₁₀ j 拍成 Δlog_10j 时，重排会把 10 和 j 一起吞进下标。
# 占位符只在后面紧跟字母/数字时换成空格（Δlog_10 j），其余位置删掉（(j/j_ref) 不许多空格）。
SCRIPT_CLOSE_RE = re.compile(r"</(msub|msup|msubsup)>")
SCRIPT_MARK = "\x00"


def flatten(fragment: str) -> str:
    """把 <math> 子树拍回 DSL 文本（mfrac → a/b、msub → a_b），让本脚本可以反复跑。

    否则第二次跑时 cell_text() 会把 <msub>j</msub><mn>0</mn> 拍成 j0，
    分母结构也丢了（mfrac 拍成 numden），改完的 HTML 就不可重现。
    """
    def repl(match: re.Match) -> str:
        inner = SCRIPT_CLOSE_RE.sub(r"</\1>" + SCRIPT_MARK, match.group(1))
        text = _math_inner_text(inner)
        text = re.sub(SCRIPT_MARK + r"(?=[A-Za-z0-9])", " ", text)
        return " " + text.replace(SCRIPT_MARK, "") + " "

    return MATH_RE.sub(repl, fragment)


def cell_text(cell: str) -> str:
    text = html_mod.unescape(TAG_RE.sub("", flatten(cell)))
    return re.sub(r"\s+", " ", text).strip()


def rebuild_table(table: str, name: str) -> str:
    """推导表：col 0 步骤（原文）、col 1 式子（整格 math）、col 2 依据（散文）。"""
    rows = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S):
        cells = TD_RE.findall(row)
        if not cells or "步骤" in cell_text(cells[0]) or "输入" in cell_text(cells[0]):
            rows.append(
                "<tr><th>步骤</th><th>式子</th><th>依据</th></tr>"
                if name == "deriv"
                else "<tr><th>输入</th><th>计算</th><th>结果</th><th>对应</th></tr>"
            )
            continue
        out = []
        for index, cell in enumerate(cells):
            text = cell_text(cell)
            if name == "deriv":
                out.append(f"<td>{scaffold.esc(text) if index == 0 else S(text, auto=index == 1)}</td>")
            else:
                out.append(f"<td>{S(text, auto=index < 3 and not scaffold.CJK_RE.search(text))}</td>")
        rows.append("<tr>" + "".join(out) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def main() -> int:
    html = FIX.read_text(encoding="utf-8")

    # 1) CSS
    html = re.sub(
        r"<style>.*?</style>",
        "<style>\n" + scaffold.CSS + EXTRA_CSS + "</style>",
        html, count=1, flags=re.S)

    # 2) 公式主体
    for eq, dsl in FORMULAS.items():
        pattern = re.compile(
            rf'(<div class="formula" data-eq="{eq}"[^>]*>\s*<span class="eqno">[^<]*</span>)'
            rf"(.*?)(\s*<span class=\"units\">)", re.S)
        html, n = pattern.subn(
            lambda m: m.group(1) + f'<span class="expr">{MATH(dsl)}</span>' + m.group(3), html, count=1)
        print(f"formula {eq}: {n}")

    # 3) 公理式子
    for aid, dsl in AXIOMS.items():
        pattern = re.compile(
            rf'(<li data-axiom="{aid}"[^>]*><b>\[[^\]]*\]</b> )<span class="eq">.*?</span>(?=<span class="note">)', re.S)
        html, n = pattern.subn(lambda m: m.group(1) + f'<span class="eq">{MATH(dsl)}</span>', html, count=1)
        print(f"axiom {aid}: {n}")

    # 4) 推导表 / 复算表
    def table_sub(match: re.Match) -> str:
        head, inner = match.group(1), match.group(2)
        table = re.search(r"<table>.*?</table>", inner, re.S)
        if not table:
            return match.group(0)
        name = "deriv" if "deriv" in head else "recalc"
        return head + inner[:table.start()] + rebuild_table(table.group(0), name) + inner[table.end():] + "</details>"

    html = re.sub(r'(<details class="(?:deriv|recalc)"[^>]*>)(.*?)(</details>)', table_sub, html, flags=re.S)

    # 4b) 散文容器：只剩文字的那些（.note / .units / h1 / p / li / figcaption）重排一遍，
    #     含 Unicode 上下标的词自动变行内 <math>（已经是 <math> 的容器跳过）
    prose_pattern = re.compile(
        r'<(span|p)\b[^>]*class="([^"]*\b(?:note|units|lead|io|recast)\b[^"]*)"[^>]*>'
        r'(.*?)</\1>', re.S)

    def prose_sub(match: re.Match) -> str:
        inner = match.group(3)
        if "<details" in inner or "<b>" in inner:
            return match.group(0)
        head = match.group(0)[: match.start(3) - match.start(0)]
        return head + S(cell_text(inner)) + match.group(0)[match.end(3) - match.start(0):]

    html = prose_pattern.sub(prose_sub, html)
    for tag in ("h1", "figcaption"):
        html = re.sub(
            rf"(<{tag}[^>]*>)(.*?)(</{tag}>)",
            lambda m: m.group(1) + S(cell_text(m.group(2))) + m.group(3),
            html, flags=re.S)
    html = re.sub(
        r'(<ul class="pit">.*?</ul>)',
        lambda m: re.sub(r">([^<>]+)<", lambda t: ">" + S(html_mod.unescape(t.group(1))) + "<", m.group(1)),
        html, flags=re.S)

    # 5) 内嵌 DeckText
    html = scaffold.embed_text_font(html)
    FIX.write_text(html, encoding="utf-8")
    print(f"已写回 {FIX}（{FIX.stat().st_size / 1024:.0f}KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
