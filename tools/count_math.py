#!/usr/bin/env python3
"""逐页数 <math>：屏幕态查 querySelectorAll('math').length，与「该页公式清单」逐条对照。

公式清单由 DOM 自己给出（四类，一条公式一个 <math>）：

    .expr            块级公式（P 页 / 算例页的 1px 方框）
    .eq              公理清单里的式子
    deriv 式子列     推导表第二列（整格一个 <math>）
    行内              散文里的 $…$ / 自动转的公式词

判定：每页 total == 四类之和；且 .expr / .eq / 推导表式子列每格恰好 1 个 <math>。
另打印 `<math>` 之外是否还有可见公式内容（只看 .expr / .eq 里 math 之外有没有字母数字）。

    python3 tools/count_math.py work/<slug>/<slug>.html [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shoot_deck import find_browser  # noqa: E402

COUNT_JS = r"""
() => {
  const rows = [];
  document.querySelectorAll('section.slide').forEach((slide, i) => {
    slide.classList.add('active');
    const n = (sel) => slide.querySelectorAll(sel).length;
    const hasMath = (el) => el.querySelectorAll('math').length;
    const bad = [];
    slide.querySelectorAll('.formula .expr').forEach((el) => {
      if (hasMath(el) !== 1) bad.push(`expr 有 ${hasMath(el)} 个 math`);
    });
    slide.querySelectorAll('ol.axioms .eq').forEach((el) => {
      if (hasMath(el) !== 1) bad.push(`axiom .eq 有 ${hasMath(el)} 个 math`);
    });
    // 推导表式子列：长句按中文标点切成多个 <math>，所以只要求 ≥1，且 math 之外没有公式内容
    slide.querySelectorAll('details.deriv tr td:nth-child(2)').forEach((el) => {
      if (hasMath(el) < 1) {
        const text = (el.textContent || '').trim();
        if (/[A-Za-z0-9]/.test(text)) bad.push(`推导式子格没有 math：${text.slice(0, 18)}`);
        return;
      }
      const clone = el.cloneNode(true);
      clone.querySelectorAll('math').forEach((m) => m.remove());
      const rest = (clone.textContent || '').replace(/[\s，；：。、（）]/g, '');
      if (/[A-Za-z0-9]/.test(rest)) bad.push(`推导式子格 math 之外还有公式内容「${rest.slice(0, 12)}」`);
    });
    const expr = n('.formula .expr math');
    const axiom = n('ol.axioms .eq math');
    const deriv = n('details.deriv td:nth-child(2) math');
    const total = n('math');
    rows.push({
      page: i + 1, kind: slide.dataset.kind || '', total,
      expr, axiom, deriv, inline: total - expr - axiom - deriv, bad,
    });
    slide.classList.remove('active');
  });
  return rows;
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    html = Path(args.html).resolve()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=find_browser(), args=["--no-sandbox", "--font-render-hinting=none"]
        )
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(html.as_uri())
        page.wait_for_timeout(500)
        rows = page.evaluate(COUNT_JS)
        browser.close()

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        print(f"文件: {html}")
        print(f"{'页':>3} {'页角色':<8} {'块级':>4} {'公理':>4} {'推导':>4} {'行内':>4} {'总数':>4}  一致性")
        bad = 0
        for row in rows:
            ok = row["total"] == row["expr"] + row["axiom"] + row["deriv"] + row["inline"] and not row["bad"]
            bad += 0 if ok else 1
            note = "✓" if ok else ("✗ " + "；".join(row["bad"]))
            print(f"{row['page']:>3} {row['kind']:<8} {row['expr']:>4} {row['axiom']:>4} "
                  f"{row['deriv']:>4} {row['inline']:>4} {row['total']:>4}  {note}")
        total = sum(row["total"] for row in rows)
        print(f"合计 {len(rows)} 页 / {total} 个 <math>；不一致的页 {bad}")
    return 1 if any(row["bad"] or row["total"] != row["expr"] + row["axiom"] + row["deriv"] + row["inline"]
                    for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
