#!/usr/bin/env python3
"""从 outline.json 生成符合契约的 HTML 骨架。

为什么有它：契约（data-x / data-yscale / ax 标签 / 刻度 data-axis / g.dim /
details.deriv / details.recalc / 页码 / 视口缩放）靠手写必然漏，漏了就反复
『改一页 → 跑校验 → 再改』。这个脚本把这些一次性生成好，写作者只填内容。

用法:
    python3 scripts/scaffold.py outline.json work/<slug>/<slug>.html

outline.json 结构（只列必需项，可省略的用默认值）:

{
  "title": "LSV → Tafel 斜率",
  "origin_reads": ["E", "j"],          # 起点原图上读得到的量（C1 孤儿符号闭包的第二来源）

  # 公理清单（文首单列一页，编号 A1…An；标签只许 定义/定律/经验事实）
  "axioms": [
    {"id": "A1", "tag": "定义", "eq": "η ≡ E − E_eq"},
    {"id": "A2", "tag": "定义", "eq": "j = I / A"},
    {"id": "A3", "tag": "定律", "eq": "j = j₀[exp(α_aFη/RT) − exp(−α_cFη/RT)]（Butler–Volmer）"}
  ],

  # 公式预备段：一条链一页，按链序排（生成器会把它们放在全篇最前）
  "formula": [
    {"eq": "P1", "h1": "P1：过电位就是把实测电位减去平衡电位",
     "expr": "η = E − E_eq", "syms": ["η", "E", "E_eq"],
     "units": "η [mV]，E [mV vs RHE]，E_eq [mV vs RHE]",
     "io": "吃进：E [mV]（第 5 页读得到）→ 吐出：η [mV]",
     "axiom": "A1", "used_in": 7,
     "stop": "正文最后一次代入 η 在第 7 页；再往下是 α 的物理来源，不属于本文档",
     "deriv": [["(1.1)", "η ≡ E − E_eq", "A1"], ["(1.2)", "…", "代数"]]}
  ],

  "slides": [
    {"kind": "origin", "h1": "起点：一条 LSV 曲线",
     "fig": {"x": "E", "y": "j", "xscale": "linear", "yscale": "linear"},
     "lead": "图上只有一条曲线。"},

    {"kind": "theory", "h1": "取数前先定三条",
     "items": ["动力学控制：…", "无背景电流：…", "无欧姆降：…"]},

    {"kind": "calc", "h1": "横轴换成 η", "uses": ["P1"],
     "recast": "E → η = E − E_eq（刻度值不变，标签必须改）",
     "fig": {"x": "η", "y": "j", "xscale": "linear", "yscale": "log"},
     "formula": {"eq": 1, "expr": "η = b · log₁₀( j / j₀ )",
                 "syms": ["η", "b", "j", "j0"],
                 "units": "η [mV]，b [mV/dec]，j、j₀ [mA/cm²]",
                 "deriv": [["(1.1)", "j = …", "定义"], ["(1.2)", "j ≈ …", "近似 A1"]]},
     "lead": "…"},

    {"kind": "pitfall", "h1": "三个最容易错的地方",
     "pitfalls": [["错误做法", "现象", "正确做法"], …]},

    {"kind": "calc", "h1": "…（末页就停在这里，不再另起结论页）", "items": ["…"]}

  页角色只有 formula / origin / theory / calc / pitfall：结论页已取消。
  formula 页由 axioms / formula 两块自动生成，不要写进 slides。
  一条式子的推导一页写不下时，把余下的步骤放下一页，并给同号分片：
    {"kind": "calc", "h1": "…（式 2 的推导续）",
     "deriv_part": {"eq": 2, "part": 2, "deriv": [[…]]}}
  ],
  "recalc": [["输入", "计算", "结果", "对应"], ["j 0.50 → 23.2", "log₁₀", "1.667 dec", "第 5 页"]]
}

生成完还需要人做的：把 fig 里的 <svg> 换成真图（数据 + 渲染函数）、补刻度值。
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"

# 公式用手写体：子集 woff2（scripts/make_handfont.py 生成）。
# 取不到子集时退化成 local() 引用链，本机有效、换机器可能失效，check_deck 会 warn。
HAND_LOCAL = '"LXGW WenKai", "霞鹜文楷", "KaiTi", "STKaiti", cursive'


def hand_face() -> str:
    css_file = ASSETS / "handfont.css"
    if css_file.is_file():
        return css_file.read_text(encoding="utf-8")
    return f'@font-face {{ font-family: "DeckHand"; src: local("LXGW WenKai"); }}\n'


HAND_STROKE = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='600' height='8' viewBox='0 0 600 8'"
    " preserveAspectRatio='none'><path d='M3,5.2 C90,3.0 170,6.6 250,4.8 330,3.0 410,6.4 490,4.4"
    " 545,3.1 578,5.4 597,4.6' fill='none' stroke='%232c7fb8' stroke-width='2.4'"
    " stroke-linecap='round'/></svg>"
)

CSS = (
    hand_face()
    + ':root { --hand: "DeckHand", ' + HAND_LOCAL + '; }\n'
    + """  html, body { margin: 0; height: 100%; overflow: hidden; background: #fbfaf8; color: #1b1b1b;
    font-family: system-ui, -apple-system, "Noto Sans SC", sans-serif; font-size: 21px; }
  #deck { width: 1600px; height: 900px; transform: scale(var(--k, 1)); transform-origin: top left; }
  .slide { width: 1600px; height: 900px; box-sizing: border-box; padding: 34px 56px 26px;
    position: absolute; top: 0; left: 0; overflow: hidden; background: #fbfaf8; }
  .slide:not(.active) { display: none; }
  h1 { font-size: 31px; line-height: 1.3; margin: 0 0 10px; font-weight: 650; }
  .recast { font-size: 20px; color: #2c7fb8; margin: 0 0 8px; }
  .fig { margin: 0; text-align: center; }
  .fig svg { display: block; width: 1240px; height: 574px; margin: 0 auto; }
  /* 同页还有公式/推导时用 class="fig compact"：图让出高度，文字等比放大保持可读 */
  .fig.compact svg { width: 767px; height: 356px; }
  .fig.compact svg text { font-size: 30px; }
  .fig.compact svg text.ax { font-size: 30px; }
  .fig.compact svg g.dim text { font-size: 28px; }
  figcaption { font-size: 19px; color: #5d6470; margin-top: 2px; }
  /* 公式一律手写体：手写体 + 变量斜体 + 整行 −0.3° + 手绘笔迹下划线。
     倾斜只能挂在 .expr（行内）上：挂到 .formula 会把里面的推导表格一起转，
     1428px 宽的表会被 tan(0.3°) 拉出 7.5px 高差（实测）。表格/单位行/正文必须水平。
     手写体也只能挂在纯数学元素上：子集字体没有 CJK 字形，中文会回退到系统字体。 */
  .formula { font-size: 27px; padding: 8px 16px 10px; background: #f3f7fb; margin: 10px 0 0;
    position: relative; color: #17222e; line-height: 1.5; }
  .formula .expr { position: relative; display: inline-block; padding-bottom: 3px;
    transform: rotate(-0.3deg); font-family: var(--hand); }
  .formula .expr::after { content: ""; position: absolute; left: -2px; right: -2px; bottom: -2px;
    height: 7px; background-image: url("__STROKE__"); background-repeat: no-repeat;
    background-position: left bottom; background-size: 100% 7px; }
  .formula .eqno { font-size: 20px; color: #2c7fb8; font-weight: 650; margin-right: 10px;
    font-family: system-ui, -apple-system, "Noto Sans SC", sans-serif; }
  .formula .units { display: block; font-size: 19px; color: #4a5260; margin-top: 2px;
    font-family: system-ui, -apple-system, "Noto Sans SC", sans-serif; }
  /* 上下标：缩小并压掉行高，否则每加一个下标就把整行撑高几像素 */
  sub, sup { font-size: 0.72em; line-height: 0; }
  sub { vertical-align: -0.22em; }
  sup { vertical-align: 0.42em; }
  .formula var, ol.axioms var, details.deriv td:nth-child(2) var { font-style: italic; }
  /* 推导表的「式子」列不许用手写体：单元格里夹着中文（「与 A5 的 y = kx + c 对照」「记 b ≡ k」），
     子集字体没有 CJK 字形，会回退到本机系统字体 —— 同一份 deck 在两台机器上字形不一致。 */
  details.deriv td:nth-child(2) { font-size: 20px; }
  .io { font-size: 20px; color: #4a5260; margin: 6px 0 2px; }
  ol.axioms { margin: 10px 0 0; padding-left: 30px; font-size: 22px; line-height: 1.7; }
  ol.axioms li { margin-bottom: 4px; }
  ol.axioms b { color: #2c7fb8; font-weight: 650; }
  ol.axioms .eq { font-weight: 550; font-family: var(--hand); font-size: 24px; }
  ol.axioms .note { margin-left: 12px; color: #5d6470; }
  ol.axioms .note::before { content: "—— "; }
  .lead { font-size: 21px; line-height: 1.45; margin: 10px 0 0; }
  .pg { position: absolute; right: 44px; bottom: 20px; font-size: 18px; color: #8b929b; }
  ul.pit { margin: 10px 0 0; padding-left: 0; list-style: none; font-size: 20px; line-height: 1.45; }
  ul.pit li { margin: 0 0 10px; padding-left: 14px; border-left: 4px solid #7f8c8d; }
  ul.pit b { color: #c0392b; }
  ul.items { margin: 10px 0 0; padding-left: 26px; font-size: 21px; line-height: 1.5; }
  details { border: 1px solid #dcd8d0; border-radius: 8px; background: #fff; padding: 5px 14px; margin-top: 8px; font-size: 19px; }
  summary { font-size: 20px; font-weight: 550; cursor: pointer; }
  details table { border-collapse: collapse; width: 100%; margin-top: 6px; }
  details th, details td { border-bottom: 1px solid #e2ded6; padding: 3px 8px;
    text-align: left; line-height: 1.3; vertical-align: top; }
  @page { size: 1600px 900px; margin: 0; }
  @media print {
    html, body { height: auto; overflow: visible; }
    #deck { transform: none; height: auto; }
    .slide, .slide:not(.active) { display: block; position: relative; page-break-after: always; break-after: page; }
    details { display: block; padding: 3px 10px; margin-top: 4px; }
    details > summary { display: list-item; }
    details:not([open]) > *:not(summary) { display: block; }
    /* 打印时 details 全展开：图与表格内边距要让出高度，否则一页会溢出成两张纸 */
    .fig svg { width: 860px; height: 399px; }
    details th, details td { padding: 2px 6px; }
  }"""
).replace("__STROKE__", HAND_STROKE)

JS = """  const slides = [...document.querySelectorAll('.slide')];
  let current = 0;
  slides[0].classList.add('active');
  function show(i) {
    const next = Math.max(0, Math.min(slides.length - 1, i));
    slides[current].classList.remove('active');
    current = next;
    slides[current].classList.add('active');
  }
  addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' || e.key === 'PageDown') { e.preventDefault(); show(current + 1); }
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); show(current - 1); }
  });
  let lock = 0;
  addEventListener('wheel', (e) => {
    if (Math.abs(e.deltaY) < 4) return;
    const now = Date.now(); if (now - lock < 380) return; lock = now;
    show(e.deltaY > 0 ? current + 1 : current - 1);
  }, { passive: true });
  function fit() {
    const k = Math.min(window.innerWidth / 1600, window.innerHeight / 900);
    document.documentElement.style.setProperty('--k', String(k));
  }
  addEventListener('resize', fit);
  fit();"""


def esc(value: str) -> str:
    return html.escape(str(value), quote=False)


TAG = re.compile(r"<[^>]+>")
SUB = re.compile(r"(?<=[A-Za-zΑ-Ωα-ω0-9\)])_\{?([A-Za-z0-9]+)\}?")
SUP = re.compile(r"(?<=[A-Za-zΑ-Ωα-ω0-9\)])\^\{?([A-Za-z0-9+\-]+)\}?")


def subs(fragment: str) -> str:
    """下划线/尖号写法换成真正的 <sub>/<sup>。

    公式里写 E_eq 是编程写法，手写数学该是 E 下标 eq；只处理文本节点，
    data-sym="E_eq" 这类属性保持原样（绑定检查靠它）。
    """
    parts = TAG.split(fragment)
    tags = TAG.findall(fragment)
    out = []
    for i, chunk in enumerate(parts):
        if "<script" in chunk or chunk.strip() == "":
            out.append(chunk)
        else:
            chunk = SUB.sub(r"<sub>\1</sub>", chunk)
            chunk = SUP.sub(r"<sup>\1</sup>", chunk)
            out.append(chunk)
        if i < len(tags):
            out.append(tags[i])
    return "".join(out)


def expr_span(expr: str) -> str:
    """把公式主体包成 .expr：手绘笔迹只压在式子上，不压到下面的推导块。"""
    return f'<span class="expr">{expr}</span>'


def axis_label(spec: dict, axis: str) -> str:
    quantity = spec[axis]
    unit = spec.get(f"{axis}unit", "")
    scale = spec.get(f"{axis}scale", "linear")
    label = f"log₁₀ {quantity}" if scale == "log" else quantity
    return f"{label} [{unit}]" if unit else label


def ticks(spec: dict, axis: str) -> str:
    """按刻度类型给出占位刻度：log 必须写 10ⁿ，线性写数值。"""
    if spec.get(f"{axis}scale", "linear") == "log":
        return "".join(
            f'<text data-axis="{axis}" x="{x}" y="{y}">{label}</text>'
            for x, y, label in ((200, 470, "10⁰"), (600, 470, "10¹"))
            if axis == "x"
        ) or "".join(
            f'<text data-axis="y" x="84" y="{y}">{label}</text>'
            for y, label in ((400, "10⁰"), (120, "10¹"))
        )
    if axis == "x":
        return '<text data-axis="x" x="200" y="470">TODO 刻度</text>'
    return '<text data-axis="y" x="84" y="400">TODO 刻度</text>'


def figure(spec: dict, caption: str, anim: str = "") -> str:
    sym_x, sym_y = spec.get("xsym", spec["x"]), spec.get("ysym", spec["y"])
    anim_attr = f' data-anim="{anim}"' if anim else ""
    return f"""  <figure class="fig" data-x="{esc(spec['x'])}" data-y="{esc(spec['y'])}" data-xscale="{spec.get('xscale', 'linear')}" data-yscale="{spec.get('yscale', 'log')}"{anim_attr}>
    <svg viewBox="0 0 1120 520">
      <!-- TODO 真图：曲线用「数据数组 + 渲染函数」生成，不要逐点写死坐标 -->
      <text class="ax" data-axis="x" data-sym="{esc(sym_x)}">{esc(axis_label(spec, 'x'))}</text>
      <text class="ax" data-axis="y" data-sym="{esc(sym_y)}">{esc(axis_label(spec, 'y'))}</text>
      {ticks(spec, 'x')}
      {ticks(spec, 'y')}
    </svg>
    <figcaption>{esc(caption)}</figcaption>
  </figure>"""


def formula_block(spec: dict) -> str:
    expr = esc(spec["expr"])
    for sym in spec.get("syms", []):
        expr = re.sub(
            rf"(?<![\w₀₁]){re.escape(sym)}(?![\w₀₁])",
            f'<var data-sym="{sym}">{sym}</var>',
            expr,
            count=1,
        )
    rows = "".join(
        f"<tr><td>{esc(step)}</td><td>{subs(esc(body))}</td><td>{subs(esc(basis))}</td></tr>"
        for step, body, basis in spec.get("deriv", [])
    )
    return f"""  <div class="formula" data-eq="{spec['eq']}">
    <span class="eqno">式 ({spec['eq']})</span>{expr_span(subs(expr))}
    <span class="units">{esc(spec.get('units', 'TODO 符号与单位'))}</span>
    <details class="deriv" data-eq="{spec['eq']}">
      <summary>推导：式 ({spec['eq']})</summary>
      <table>
        <tr><th>步骤</th><th>式子</th><th>依据</th></tr>{rows}
      </table>
    </details>
  </div>"""


def deriv_part_block(spec: dict) -> str:
    """一条式子的推导跨页时，第 2 片起单独成一页：data-eq 同号 + data-part 递增。"""
    rows = "".join(
        f"<tr><td>{esc(step)}</td><td>{esc(body)}</td><td>{esc(basis)}</td></tr>"
        for step, body, basis in spec.get("deriv", [])
    )
    return f"""  <details class="deriv" data-eq="{spec['eq']}" data-part="{spec['part']}">
    <summary>推导（第 {spec['part']} 段）：式 ({spec['eq']})</summary>
    <table>
      <tr><th>步骤</th><th>式子</th><th>依据</th></tr>{rows}
    </table>
  </details>"""


def recalc_block(rows: list[list[str]]) -> str:
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"""  <details class="recalc" open>
    <summary>数值复算</summary>
    <table>
      <tr><th>输入</th><th>计算</th><th>结果</th><th>对应</th></tr>{body}
    </table>
  </details>"""


def p_formula_block(spec: dict) -> str:
    """预备段的一条 P 式：数据属性（used-in / stop / axiom）和正文式一样都挂在 .formula 上。"""
    expr = esc(spec["expr"])
    for sym in spec.get("syms", []):
        expr = re.sub(
            rf"(?<![\w₀₁]){re.escape(sym)}(?![\w₀₁])",
            f'<var data-sym="{sym}">{sym}</var>',
            expr,
            count=1,
        )
    rows = "".join(
        f"<tr><td>{esc(step)}</td><td>{subs(esc(body))}</td><td>{subs(esc(basis))}</td></tr>"
        for step, body, basis in spec.get("deriv", [])
    )
    return f"""  <div class="formula" data-eq="{spec['eq']}" data-used-in="{spec['used_in']}" data-axiom="{spec['axiom']}" data-stop="{esc(spec.get('stop', ''))}">
    <span class="eqno">{spec['eq']}</span>{expr_span(subs(expr))}
    <span class="units">{esc(spec.get('units', 'TODO 符号与单位'))}</span>
    <details class="deriv" data-eq="{spec['eq']}" open>
      <summary>推导：{spec['eq']}</summary>
      <table>
        <tr><th>步骤</th><th>式子</th><th>依据</th></tr>{rows}
      </table>
    </details>
  </div>"""


def axiom_block(outline: dict) -> str:
    items = ""
    for item in outline.get("axioms") or []:
        aid = esc(item["id"])
        tag = esc(item["tag"])
        eq = esc(item["eq"])
        used_in = esc(item.get("used_in", ""))
        note = esc(item.get("note", ""))
        items += (
            f'<li data-axiom="{aid}" data-used-in="{used_in}"><b>[{tag}]</b> '
            f'<span class="eq">{eq}</span><span class="note">{note}</span></li>'
        )
    return f'  <ol class="axioms">{items}</ol>'


def prep_slides(outline: dict) -> list[dict]:
    """预备段排在全篇最前：第 1 页公理清单，随后每条 P 一页。"""
    pages: list[dict] = []
    if outline.get("axioms"):
        pages.append(
            {
                "kind": "axioms",
                "h1": outline.get("axiom_h1") or "公理清单：定义、约定与定律",
                "goal": outline.get("goal", ""),
                "axioms_html": axiom_block(outline),
            }
        )
    for spec in outline.get("formula") or []:
        pages.append(
            {
                "kind": "formula",
                "h1": spec.get("h1") or f"{spec['eq']}：{spec['expr']}",
                "io": spec.get("io", "TODO 吃进：… → 吐出：…"),
                "pformula": spec,
                "eq_id": spec["eq"],
            }
        )
    return pages


def slide_html(slide: dict, page: int, total: int) -> str:
    kind = slide["kind"]
    attrs = f'class="slide" data-page="{page}" data-kind="{kind}"'
    if slide.get("eq_id"):
        attrs += ' data-eq="' + esc(slide["eq_id"]) + '"'
    if slide.get("uses"):
        attrs += ' data-uses="' + esc(",".join(slide["uses"])) + '"'
    if slide.get("goal"):
        attrs += ' data-goal="' + esc(slide["goal"]) + '"'
    if slide.get("reads"):
        attrs += ' data-reads="' + esc(slide["reads"]) + '"'
    parts = [
        f"<section {attrs}>",
        f"  <h1>{esc(slide['h1'])}</h1>",
    ]
    if slide.get("axioms_html"):
        parts.append(slide["axioms_html"])
    if slide.get("io"):
        parts.append('  <p class="io">' + esc(slide["io"]) + "</p>")
    if slide.get("recast"):
        parts.append(f'  <p class="recast">{esc(slide["recast"])}</p>')
    if slide.get("fig"):
        parts.append(figure(slide["fig"], slide.get("caption", ""), slide.get("anim", "")))
    if slide.get("pformula"):
        parts.append(p_formula_block(slide["pformula"]))
    if slide.get("formula"):
        parts.append(formula_block(slide["formula"]))
    if slide.get("deriv_part"):
        parts.append(deriv_part_block(slide["deriv_part"]))
    if slide.get("pitfalls"):
        items = "".join(
            f'<li><b>错误做法：</b>{esc(bad)}<b>现象：</b>{esc(seen)}<b>正确做法：</b>{esc(good)}</li>'
            for bad, seen, good in slide["pitfalls"]
        )
        parts.append(f'  <ul class="pit">{items}</ul>')
    if slide.get("items"):
        items = "".join(f"<li>{esc(item)}</li>" for item in slide["items"])
        parts.append(f'  <ul class="items">{items}</ul>')
    if slide.get("lead"):
        parts.append(f'  <p class="lead">{esc(slide["lead"])}</p>')
    if slide.get("recalc"):
        parts.append(recalc_block(slide["recalc"]))
    parts.append(f'  <span class="pg">{page} / {total}</span>')
    parts.append("</section>")
    return "\n".join(parts)


def build(outline: dict) -> str:
    # 预备段永远在最前：第 1 页公理清单，随后 P1、P2…；起点原图页顺延
    slides = prep_slides(outline) + list(outline["slides"])
    reads = [str(item) for item in (outline.get("origin_reads") or [])]
    if reads:
        for slide in slides:
            if slide["kind"] == "origin":
                slide.setdefault("reads", ",".join(reads))
                break
    total = len(slides)
    body = "\n\n".join(slide_html(slide, index, total) for index, slide in enumerate(slides, start=1))
    recalc = outline.get("recalc")
    if recalc and not any(slide.get("recalc") for slide in slides):
        body = body.replace(
            f'  <span class="pg">{total} / {total}</span>',
            recalc_block(recalc) + f'\n  <span class="pg">{total} / {total}</span>',
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{esc(outline.get('title', '知识点讲解'))}</title>
<style>
{CSS}
</style>
</head>
<body>
<main id="deck">

{body}

</main>
<script>
{JS}
</script>
</body>
</html>
"""


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    outline = json.loads(src.read_text(encoding="utf-8"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(build(outline), encoding="utf-8")
    prep = len(outline.get("formula") or []) + (1 if outline.get("axioms") else 0)
    print(f"已生成骨架: {dst}（预备段 {prep} 页 + 正文 {len(outline['slides'])} 页）")

    # 推导五件事预检：缺什么先说出来，省一轮 check_deck 往返
    eqs = [slide["formula"]["eq"] for slide in outline["slides"] if slide.get("formula")]
    base = min(eqs) if eqs else None
    warnings = []
    for slide in outline["slides"]:
        spec = slide.get("formula")
        if not spec:
            continue
        rows = spec.get("deriv", [])
        where = f"式 ({spec['eq']})"
        text = " ".join(" ".join(row) for row in rows)
        if len(rows) < 3:
            warnings.append(f"{where} 推导只有 {len(rows)} 行：至少 3 行（起点 → 消掉什么 → 代入本页的数）")
        if spec["eq"] != base and not re.search(r"P\d|式\s*[（(]?\s*\d", text):
            warnings.append(f"{where} 没写它由哪条式/哪条 P 变来：读者不知道它从哪来")
        if not any(
            re.search(r"=\s*[−-]?\d", cell) and re.search(r"\d\s*(mV|dec|mA|V)", cell)
            for row in rows
            for cell in row
        ):
            warnings.append(f"{where} 没有代入本页的数的那一行（形如 120 mV ÷ 0.905 dec = 132.6 mV/dec）")
        if not re.search(r"误差|偏差|适用|失效|忽略", text):
            warnings.append(f"{where} 没写误差或失效边界")

    axiom_ids = {item["id"] for item in outline.get("axioms") or []}
    for spec in outline.get("formula") or []:
        rows = spec.get("deriv", [])
        where = f"{spec.get('eq', 'P?')}"
        text = " ".join(" ".join(row) for row in rows)
        for key in ("used_in", "stop", "axiom"):
            if not spec.get(key):
                warnings.append(f"{where} 缺 {key}：预备段每条 P 都必须写")
        if spec.get("axiom") and axiom_ids and spec["axiom"] not in axiom_ids:
            warnings.append(f"{where} 的 axiom={spec['axiom']} 不在公理清单里")
        if rows:
            first = rows[0][-1]
            if not (re.search(r"A\d", first) or "定义" in first):
                warnings.append(f"{where} 推导首步依据是「{first}」：只能写 A 编号或「定义」（推论当公理）")
        if len(rows) < 3:
            warnings.append(f"{where} 推导只有 {len(rows)} 行：至少 3 行")
        if not re.search(r"误差|偏差|失效|不成立|边界|忽略", text):
            warnings.append(f"{where} 没写失效/近似条件（要带数值阈值）")
    if warnings:
        print("")
        print("推导预检未通过（check_deck.py 会报 error）：")
        for item in warnings:
            print(f"  ⚠ {item}")
    print("下一步：填真图（数据 + 渲染函数）、补刻度值、把 TODO 全部删掉，再跑 check_deck.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
