#!/usr/bin/env python3
"""给公式做一套数学衬线字体（Latin Modern Math 子集），内嵌成 base64。

参考图是 Computer Modern 的排版观感：衬线、变量斜体、常数 e 正体、真上下标。
Latin Modern Math 就是 Computer Modern 的 OpenType 后继，字形同一族。

用法:
    python3 scripts/make_mathfont.py                 # 需要源字体（见下）
    DECK_MATH_FONT=/path/to/latinmodern-math.otf python3 scripts/make_mathfont.py
    python3 scripts/make_mathfont.py --check

源字体探测顺序：
    $DECK_MATH_FONT → scripts/assets/latinmodern-math.otf → ~/.local/share/fonts/latinmodern-math.otf
下载：https://mirrors.ctan.org/fonts/lm-math/opentype/latinmodern-math.otf

产物（提交进仓库，构建 deck 时不再需要源字体）：
    scripts/assets/mathfont.woff2   子集（约 72KB）
    scripts/assets/mathfont.b64     base64（约 96KB）
    scripts/assets/mathfont.css     scaffold.py 直接读它

子集内部 name 改成 DeckMath：不改的话 pdffonts / CSS.getPlatformFontsForNode
报的是 LatinModernMath-Regular，和系统字体混在一起，「公式到底用了哪个字体」判不出来。
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
OUT_WOFF2 = ASSETS / "mathfont.woff2"
OUT_B64 = ASSETS / "mathfont.b64"
OUT_CSS = ASSETS / "mathfont.css"

# 公式字符集：ASCII + 希腊（正体大写、斜体小写）+ 数学斜体拉丁 + 运算符/括号/标点
CHARS = set(chr(c) for c in range(0x20, 0x7F))
CHARS |= set("αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ")
CHARS |= set(chr(c) for c in range(0x1D434, 0x1D468))    # 𝐴…𝑧（数学斜体拉丁）
CHARS |= set(chr(c) for c in range(0x1D6FC, 0x1D71C))    # 𝛼…𝜔（数学斜体希腊小写）
CHARS |= set("−–—×÷·⋅±∓≤≥≠≈≡≃≅∝∞∂∆∑∏∫√°µΩ′″…∈∉⊂⊃∪∩∖∀∃∅→←↔⇒⇔")
CHARS |= set("()[]{}|/\\,.;:'\"!?@#%&*+-<=>^_~")
CHARSET = "".join(sorted(CHARS))


def find_source() -> str | None:
    env = os.environ.get("DECK_MATH_FONT", "")
    if env and Path(env).is_file():
        return env
    for cand in (ASSETS / "latinmodern-math.otf",
                 Path.home() / ".local/share/fonts/latinmodern-math.otf"):
        if cand.is_file():
            return str(cand)
    return None


def build(source: str) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    txt = ASSETS / ".math-charset.txt"
    txt.write_text(CHARSET, encoding="utf-8")
    cmd = [sys.executable, "-m", "fontTools.subset", source,
           f"--text-file={txt}", "--flavor=woff2", f"--output-file={OUT_WOFF2}",
           "--layout-features=*", "--no-hinting"]
    subprocess.run(cmd, check=True, capture_output=True)

    from fontTools.ttLib import TTFont

    font = TTFont(OUT_WOFF2)
    for name_id, value in ((1, "DeckMath"), (3, "DeckMath-Regular"), (4, "DeckMath"),
                           (6, "DeckMath-Regular"), (16, "DeckMath"), (17, "Regular")):
        font["name"].setName(value, name_id, 3, 1, 0x409)
        font["name"].setName(value, name_id, 1, 0, 0)
    font.flavor = "woff2"
    font.save(OUT_WOFF2)

    b64 = base64.b64encode(OUT_WOFF2.read_bytes()).decode("ascii")
    OUT_B64.write_text(b64, encoding="utf-8")
    OUT_CSS.write_text(
        '@font-face { font-family: "DeckMath"; font-display: block; font-weight: 100 900;\n'
        f'  src: url(data:font/woff2;base64,{b64}) format("woff2"); }}\n',
        encoding="utf-8")
    txt.unlink(missing_ok=True)
    print(f"源字体: {source}")
    print(f"字形数: {len(CHARSET)}")
    print(f"mathfont.woff2: {OUT_WOFF2.stat().st_size / 1024:.1f}KB")
    print(f"mathfont.b64:   {OUT_B64.stat().st_size / 1024:.1f}KB（内嵌用）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    source = find_source()
    if not source:
        print("warn: 没找到 latinmodern-math.otf（设 DECK_MATH_FONT 或放到 scripts/assets/）。")
        print("      deck 仍可用，但公式会退化成系统 serif；check_deck 会 error。")
        return 0 if args.check else 1
    if args.check:
        print(f"源字体: {source}\n字形数: {len(CHARSET)}")
        return 0
    build(source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
