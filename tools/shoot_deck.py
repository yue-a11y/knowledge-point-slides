#!/usr/bin/env python3
"""用真浏览器（chrome-headless-shell）给 HTML 幻灯片逐页截图 + 导 PDF + 交互自检。

本机浏览器不在 PATH 里，历史上因为「只在 PATH 里找」被误判成「没有浏览器」。
所以这里显式按已知位置探测，探测失败给安装命令，不再静默降级到 weasyprint。

用法:
    python3 tools/shoot_deck.py work/<slug>/<slug>.html
    python3 tools/shoot_deck.py work/<slug>/<slug>.html --no-pdf

产出:
    <slug>/shots/p-01.png …（1600×900，屏幕态：details 折叠）
    <slug>/shots/deck-browser.pdf（page.pdf()，每页一张）
    <slug>/shots/check.txt（交互自检结果）
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 先看 PATH（~/.local/bin/chrome-headless-shell 是这个仓库装好的入口），
# 再看历史安装位置：本机浏览器长期不在 PATH 里，只用 command -v 判定会误判成「没有」。
PATH_NAMES = ["chrome-headless-shell", "chromium", "chromium-browser", "google-chrome", "google-chrome-stable"]

CANDIDATES = [
    os.environ.get("CHROME_PATH", ""),
    str(Path.home() / ".cache/pi-chrome/chrome-headless-shell-linux64/chrome-headless-shell"),
    str(Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux/chrome"),
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/snap/bin/chromium",
]

INSTALL = """没找到可用浏览器。装一个（约 110MB，国内镜像，十几秒）：
  curl -sL -o /tmp/chs.zip https://cdn.npmmirror.com/binaries/chrome-for-testing/131.0.6778.85/linux64/chrome-headless-shell-linux64.zip
  mkdir -p ~/.cache/pi-chrome && python3 -c "import zipfile;zipfile.ZipFile('/tmp/chs.zip').extractall('$HOME/.cache/pi-chrome')"
  chmod +x ~/.cache/pi-chrome/chrome-headless-shell-linux64/chrome-headless-shell
然后用 CHROME_PATH=… 或默认路径重跑本脚本。"""


def find_browser() -> str:
    import glob
    import shutil

    for name in PATH_NAMES + [os.environ.get("CHROME_PATH", "")]:
        if name:
            hit = shutil.which(name)
            if hit:
                return hit

    for cand in CANDIDATES:
        if not cand:
            continue
        for hit in glob.glob(cand):
            if Path(hit).is_file() and os.access(hit, os.X_OK):
                return hit
    print(INSTALL)
    raise SystemExit(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--view", default="1600x900", help="截图视口，默认 1600x900（版式 1:1）")
    ap.add_argument("--compact-view", default="900x600", help="页码可见性检查用的窗口")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    html = Path(args.html).resolve()
    shots = html.parent / "shots"
    shots.mkdir(exist_ok=True)
    exe = find_browser()
    w, h = (int(v) for v in args.view.split("x"))
    log: list[str] = [f"browser: {exe}"]

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe, args=["--no-sandbox", "--font-render-hinting=none"])

        page = browser.new_page(viewport={"width": w, "height": h})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.goto(html.as_uri())
        page.wait_for_timeout(400)

        total = page.locator("section.slide").count()
        log.append(f"slides: {total}")

        for i in range(1, total + 1):
            page.evaluate(
                """(i) => {
                    const s = [...document.querySelectorAll('.slide')];
                    s.forEach((el, k) => el.classList.toggle('active', k === i - 1));
                }""",
                i,
            )
            page.wait_for_timeout(120)
            pg_no = page.locator("section.slide.active .pg").inner_text().strip()
            expect = f"{i} / {total}"
            if pg_no != expect:
                log.append(f"✗ 第 {i} 页页码显示「{pg_no}」，应为「{expect}」")
            else:
                log.append(f"✓ 第 {i} 页页码 {pg_no}")
            page.screenshot(path=str(shots / f"p-{i:02d}.png"))
            # 内容不得溢出（滚动高度 > 版式高度即溢出）
            overflow = page.evaluate(
                """() => { const s = document.querySelector('.slide.active');
                          return s.scrollHeight - s.clientHeight; }"""
            )
            if overflow > 1:
                log.append(f"✗ 第 {i} 页内容溢出 {overflow}px（折叠态）")
            # 折叠态看不出来、展开就溢出的情形：把本页所有 details 打开再量一次。
            # 这是「数值复算 / 推导展开后下半截看不见」的唯一可靠判据。
            opened = page.evaluate(
                """() => {
                    const s = document.querySelector('.slide.active');
                    const ds = [...s.querySelectorAll('details')];
                    ds.forEach(d => { d.dataset._was = d.open ? '1' : '0'; d.open = true; });
                    return ds.length;
                }"""
            )
            if opened:
                page.wait_for_timeout(60)
                overflow_open = page.evaluate(
                    """() => { const s = document.querySelector('.slide.active');
                              return s.scrollHeight - s.clientHeight; }"""
                )
                if overflow_open > 1:
                    log.append(f"✗ 第 {i} 页展开 {opened} 个折叠块后溢出 {overflow_open}px"
                               f"（展开态被 overflow:hidden 裁掉，屏幕上直接看不见）")
                page.screenshot(path=str(shots / f"p-{i:02d}-open.png"))
                page.evaluate(
                    """() => { const s = document.querySelector('.slide.active');
                              [...s.querySelectorAll('details')]
                                .forEach(d => { d.open = d.dataset._was === '1'; }); }"""
                )

        # 翻页：键盘右移两页 / 滚轮回一页
        page.evaluate("""() => { const s=[...document.querySelectorAll('.slide')];
                                 s.forEach((el,k)=>el.classList.toggle('active', k===0)); }""")
        page.keyboard.press("ArrowRight")
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(200)
        log.append(f"{'✓' if page.locator('section.slide.active').get_attribute('data-page') == '3' else '✗'} 键盘 → → 到第 3 页")
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(500)
        log.append(f"{'✓' if page.locator('section.slide.active').get_attribute('data-page') == '4' else '✗'} 滚轮下翻到第 4 页")

        # 小窗口下页码是否还在屏幕内
        cw, ch = (int(v) for v in args.compact_view.split("x"))
        page.set_viewport_size({"width": cw, "height": ch})
        page.wait_for_timeout(300)
        box = page.locator("section.slide.active .pg").bounding_box()
        inside = box is not None and box["x"] + box["width"] <= cw and box["y"] + box["height"] <= ch
        log.append(f"{'✓' if inside else '✗'} {cw}×{ch} 窗口下页码在屏幕内 {box}")

        if not args.no_pdf:
            page.set_viewport_size({"width": w, "height": h})
            # 与 Ctrl+P 一致：导 PDF 前把 details 展开（否则推导块不进 PDF）
            page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
            page.wait_for_timeout(200)
            page.pdf(path=str(shots / "deck-browser.pdf"), width="1600px", height="900px",
                     print_background=True, page_ranges="1-" + str(total))
            # deck-print.pdf 就是浏览器打印件（Ctrl+P 同一条路径）：只有它用得上内嵌字体；
            # weasyprint 的 SVG text 不走 @font-face，会在 PDF 里带进系统字体（实测）。
            (shots / "deck-print.pdf").write_bytes((shots / "deck-browser.pdf").read_bytes())
            log.append(f"pdf: {shots / 'deck-browser.pdf'}（另存为 deck-print.pdf）")
            try:
                import subprocess

                out = subprocess.run(
                    ["pdfinfo", str(shots / "deck-browser.pdf")],
                    capture_output=True, text=True, check=False,
                ).stdout
                pages = int(next(l.split()[-1] for l in out.splitlines() if l.startswith("Pages:")))
                log.append(f"{'✓' if pages == total else '✗'} 打印页数 {pages} == 幻灯片 {total}")
            except Exception as exc:  # pdfinfo 缺失只降级成提示，不阻断
                log.append(f"? 没能核对 PDF 页数（{exc}）")

        log.append("console errors: " + ("无" if not errors else "; ".join(errors[:5])))
        browser.close()

    (shots / "check.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return 0 if not any(line.startswith("✗") for line in log) else 1


if __name__ == "__main__":
    sys.exit(main())
