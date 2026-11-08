#!/usr/bin/env python3
"""量 deck 的版面几何与公式字形来源（问题 1 / 问题 2 的验收工具）。

两个模式：

    python3 tools/measure_deck.py work/<slug>/<slug>.html --tilt
        逐页量每个推导表格的**实际倾斜角**与「横线两端高差 Δy」。
        角度来自 transform 链的矩阵分解（parent 的 rotate 会传到子元素），
        Δy = 表宽 × tan(角度)。验收线：|Δy| ≤ 1px。
        同时检查标题 / 正文 / 图注 / 表格单元格是否被倾斜。

    python3 tools/measure_deck.py work/<slug>/<slug>.html --fonts
        用 CDP 的 CSS.getPlatformFontsForNode 量公式元素**实际用了哪些字体**。
        公式区应当只有 DeckHand；出现别的字体就说明字形回退到了系统字体。

退出码：有超阈值项 → 1，否则 0（可直接进 CI / 验收）。
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shoot_deck import find_browser  # noqa: E402


TILT_JS = """
() => {
  const eff = (el) => {
    let m = new DOMMatrix();
    for (let n = el; n; n = n.parentElement) {
      const t = getComputedStyle(n).transform;
      if (t && t !== 'none') m = new DOMMatrix(t).multiply(m);
    }
    return m;
  };
  const angleOf = (el) => {
    const m = eff(el);
    return Math.atan2(m.b, m.a) * 180 / Math.PI;
  };
  const out = { tables: [], others: [] };
  document.querySelectorAll('section.slide').forEach((slide, i) => {
    slide.classList.add('active');
    slide.querySelectorAll('details.deriv table').forEach((tb) => {
      const r = tb.getBoundingClientRect();
      out.tables.push({ page: i + 1, width: Math.round(r.width), angle: angleOf(tb),
                        dy: r.width * Math.tan(angleOf(tb) * Math.PI / 180) });
    });
    slide.querySelectorAll('h1, p, figcaption, details.deriv td').forEach((el) => {
      const a = angleOf(el);
      if (Math.abs(a) > 0.01) {
        out.others.push({ page: i + 1, tag: el.tagName.toLowerCase(), angle: a,
                          text: (el.textContent || '').slice(0, 24) });
      }
    });
    slide.classList.remove('active');
  });
  return out;
}
"""

FONT_JS = """
() => {
  const pick = [];
  document.querySelectorAll('section.slide').forEach((slide, i) => {
    slide.classList.add('active');
    const add = (el, label) => {
      if (el) pick.push({ page: i + 1, label, node: el, text: (el.textContent || '').slice(0, 40) });
    };
    slide.querySelectorAll('.formula .expr').forEach((el, k) => add(el, `式 ${k + 1}`));
    slide.querySelectorAll('ol.axioms .eq').forEach((el, k) => add(el, `A${k + 1}`));
    const td = slide.querySelector('details.deriv td:nth-child(2)');
    if (td) add(td, '推导式子列(正文体)');
    slide.classList.remove('active');
  });
  // 注意：CDP 量字体需要节点有 layout box，查询前要先把对应页激活（见 measure_fonts）
  // 把 node 引用换成临时 id，方便 CDP 查询
  window.__pick = pick.map((p, i) => {
    p.node.setAttribute('data-measure-id', String(i));
    return { page: p.page, label: p.label, text: p.text, id: i };
  });
  return window.__pick;
}
"""


def measure_tilt(page) -> int:
    data = page.evaluate(TILT_JS)
    worst = 0.0
    print(f"{'页':>3} {'表宽px':>7} {'角度°':>7} {'Δy px':>7}")
    for t in data["tables"]:
        print(f"{t['page']:>3} {t['width']:>7} {t['angle']:>7.3f} {t['dy']:>7.2f}")
        worst = max(worst, abs(t["dy"]))
    print(f"表格数 {len(data['tables'])}；最大 |Δy| = {worst:.2f}px（验收 ≤1px）")
    if data["others"]:
        print("被倾斜的非公式元素：")
        for o in data["others"]:
            print(f"  第 {o['page']} 页 <{o['tag']}> {o['angle']:+.2f}°  {o['text']!r}")
    else:
        print("标题 / 正文 / 图注 / 表格单元格：全部 0.00°（无倾斜）")
    return 0 if worst <= 1 and not data["others"] else 1


def measure_fonts(page, cdp) -> int:
    items = page.evaluate(FONT_JS)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    root = cdp.send("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
    bad = 0
    current = None
    for it in items:
        if it["page"] != current:
            current = it["page"]
            page.evaluate(
                """(i) => {
                    document.querySelectorAll('.slide').forEach((el, k) =>
                        el.classList.toggle('active', k === i - 1));
                }""",
                current,
            )
            page.wait_for_timeout(60)
        node = cdp.send(
            "DOM.querySelector", {"nodeId": root, "selector": f'[data-measure-id="{it["id"]}"]'}
        )["nodeId"]
        fonts = cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
        names = ", ".join(f"{f['familyName']}×{f['glyphCount']}" for f in fonts)
        print(f"第 {it['page']:>2} 页 {it['label']:<12} {names}")
        if "正文体" in it["label"]:
            continue  # 推导表的式子列是正文体（不要求内嵌字形），只作对照
        if any("DeckHand" not in f["familyName"] for f in fonts):
            bad += 1
    print(f"公式元素 {len(items)} 个（其中推导表式子列只作对照）；用非 DeckHand 字体的 {bad} 个（验收 0）")
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--tilt", action="store_true")
    ap.add_argument("--fonts", action="store_true")
    args = ap.parse_args()
    if not (args.tilt or args.fonts):
        ap.error("至少给一个 --tilt / --fonts")

    from playwright.sync_api import sync_playwright

    html = Path(args.html).resolve()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=find_browser(), args=["--no-sandbox", "--font-render-hinting=none"]
        )
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(html.as_uri())
        page.wait_for_timeout(500)
        code = 0
        if args.tilt:
            code |= measure_tilt(page)
        if args.fonts:
            code |= measure_fonts(page, page.context.new_cdp_session(page))
        browser.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
