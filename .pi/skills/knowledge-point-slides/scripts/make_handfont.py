#!/usr/bin/env python3
"""给公式做一套「手写体」子集字体，内嵌成 base64，供 scaffold.CSS 直接引用。

为什么要子集：LXGW WenKai 全字重约 20MB，直接内嵌会撑爆单文件 HTML；
公式只用 ASCII + 希腊字母 + 数学符号 + 上下标，约 200 个字形，woff2 后 ~30KB。

用法:
    python3 scripts/make_handfont.py            # 写到 scripts/assets/handfont.b64
    python3 scripts/make_handfont.py --check    # 只报告源字体与体积，不写文件

源字体探测顺序：
    $DECK_HAND_FONT → ~/.local/share/fonts/LXGWWenKai-Regular.ttf
    → fc-match "LXGW WenKai" → fc-match "KaiTi"
找不到源字体时不报错退出，只打印一条 warn：scaffold 会退化成
local() 引用链（本机有效、换机器可能失效），check_deck 会因此给 warning。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
OUT_WOFF2 = ASSETS / "handfont.woff2"
OUT_B64 = ASSETS / "handfont.b64"
OUT_CSS = ASSETS / "handfont.css"   # scaffold.py 直接读它，省得每次拼字符串

# 公式字符集：空格必须有（缺 U+0020 时 weasyprint 会报 .notdef）
CHARS = set(" " + "".join(chr(c) for c in range(0x21, 0x7F)))
CHARS |= set("αβγδεζηθικλμνξοπρστυφχψω")
CHARS |= set("ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ")
CHARS |= set("₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺⁼")
CHARS |= set("≡≈≫≪≤≥≠±×÷·⋅→←↔∝∞∂∆∑√∫°μΩ⁻¹²³½¼¾—–…‘’“”、。，：；（）【】「」")
# 数学减号 U+2212 与常见集合/关系符号：公式里写「E − E_eq」用的是这个减号，
# 不是 ASCII 的 -。漏了它，公式会回退到系统字体（本轮实测踩到）。
CHARS |= set("−∈∉∼≃≅∥∀∃′″")
CHARSET = "".join(sorted(CHARS))


def find_source() -> str | None:
    env = os.environ.get("DECK_HAND_FONT", "")
    if env and Path(env).is_file():
        return env
    cands = [
        Path.home() / ".local/share/fonts/LXGWWenKai-Regular.ttf",
        Path("/usr/share/fonts/truetype/lxgw-wenkai/LXGWWenKai-Regular.ttf"),
    ]
    for c in cands:
        if c.is_file():
            return str(c)
    if shutil.which("fc-match"):
        for family in ("LXGW WenKai", "KaiTi", "STKaiti"):
            try:
                hit = subprocess.run(
                    ["fc-match", "-f", "%{file}", family], capture_output=True, text=True, check=True
                ).stdout.strip()
            except subprocess.CalledProcessError:
                continue
            if hit and Path(hit).is_file() and "wenkai" in hit.lower():
                return hit
    return None


def build(source: str) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    txt = ASSETS / ".charset.txt"
    txt.write_text(CHARSET, encoding="utf-8")
    cmd = [
        sys.executable, "-m", "fontTools.subset", source,
        f"--text-file={txt}",
        "--flavor=woff2",
        f"--output-file={OUT_WOFF2}",
        "--layout-features=*",
        "--no-hinting",
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    # 把子集字体的内部名字改成 DeckHand。
    # 不改的话 name 表还是「LXGW WenKai」：Chromium 的 CSS.getPlatformFontsForNode、
    # 以及 pdffonts 都会把它和系统里的 LXGW WenKai 混成同一个名字，
    # 于是「公式到底用的是内嵌字形还是系统回退」无法判定（本轮实测踩到）。
    from fontTools.ttLib import TTFont

    font = TTFont(OUT_WOFF2)
    for name_id, value in ((1, "DeckHand"), (3, "DeckHand-Regular"), (4, "DeckHand"),
                           (6, "DeckHand-Regular"), (16, "DeckHand"), (17, "Regular")):
        font["name"].setName(value, name_id, 3, 1, 0x409)
        font["name"].setName(value, name_id, 1, 0, 0)
    font.flavor = "woff2"
    font.save(OUT_WOFF2)

    import base64

    b64 = base64.b64encode(OUT_WOFF2.read_bytes()).decode("ascii")
    OUT_B64.write_text(b64, encoding="utf-8")
    OUT_CSS.write_text(
        '@font-face { font-family: "DeckHand"; font-display: block;\n'
        f'  src: url(data:font/woff2;base64,{b64}) format("woff2"); }}\n',
        encoding="utf-8",
    )
    txt.unlink(missing_ok=True)
    print(f"源字体: {source}")
    print(f"字形数: {len(CHARSET)}")
    print(f"{OUT_WOFF2.relative_to(ASSETS.parent)}: {OUT_WOFF2.stat().st_size / 1024:.1f}KB")
    print(f"{OUT_B64.relative_to(ASSETS.parent)}: {OUT_B64.stat().st_size / 1024:.1f}KB（内嵌用）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只探测，不写文件")
    args = ap.parse_args()

    source = find_source()
    if not source:
        print("warn: 没找到手写体源字体（LXGW WenKai / KaiTi）。")
        print("      deck 仍可用，但 @font-face 会退化成 local() 引用链，换机器可能失效。")
        print("      装字体：https://github.com/lxgw/LxgwWenKai/releases → ~/.local/share/fonts/")
        return 1 if not args.check else 0
    if args.check:
        print(f"源字体: {source}")
        print(f"字形数: {len(CHARSET)}")
        return 0
    build(source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
