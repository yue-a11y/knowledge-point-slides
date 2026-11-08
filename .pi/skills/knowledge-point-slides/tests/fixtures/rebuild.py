#!/usr/bin/env python3
"""把 tests/fixtures/tafel-deck.html 的公式/CSS 升级到「数学衬线 + 文字手写」这一版。

fixture 是手写的静态样本，公式里还是旧的 <var> + 平铺文本；这个脚本：
  1) 用 scaffold.CSS 替换 <style>（保留 fixture 自己的版式微调）；
  2) 把每个 .formula 的式子主体换成 mathrender 的输出（包 .expr，1px 方框由 CSS 给）；
  3) 把 A 节的 .eq 也换成 mathrender；
  4) 调 scaffold.embed_text_font 内嵌 DeckText。

跑一次即可；改完的 HTML 是静态的（smoke 不依赖这个脚本）。
    python3 tests/fixtures/rebuild.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".pi/skills/knowledge-point-slides/scripts"))
import scaffold  # noqa: E402

MATH = scaffold.mathrender.math
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
        html, n = pattern.subn(lambda m: m.group(1) + f'<span class="expr">{MATH(dsl)}</span>' + m.group(3), html, count=1)
        print(f"formula {eq}: {n}")

    # 3) 公理式子
    for aid, dsl in AXIOMS.items():
        pattern = re.compile(
            rf'(<li data-axiom="{aid}"[^>]*><b>\[[^\]]*\]</b> )<span class="eq">.*?</span>(?=<span class="note">)', re.S)
        html, n = pattern.subn(lambda m: m.group(1) + f'<span class="eq">{MATH(dsl)}</span>', html, count=1)
        print(f"axiom {aid}: {n}")

    # 4) 内嵌 DeckText
    html = scaffold.embed_text_font(html)
    FIX.write_text(html, encoding="utf-8")
    print(f"已写回 {FIX}（{FIX.stat().st_size / 1024:.0f}KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
