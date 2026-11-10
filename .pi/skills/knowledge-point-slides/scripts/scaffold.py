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

分式不用手写 `\\frac`：DSL 里写 `a/b`，mathrender 按契约自动切项——
分子 = 斜杠前那一项（`2.303RT/α_aF` 的分子是 `2.303RT`），
分母 = 斜杠后到加减/关系符/括号/中文注释为止的整组（`Δη/Δlog₁₀ j` 的分母是整个 `Δlog₁₀ j`），
真分式一律出 `<mfrac>`；只有斜杠两侧都是单位词时（`mA/cm²`、`mV/dec`）才保留斜杠。
所以上面 outline 里 `η = b · log₁₀( j / j₀ )` 生成的骨架就是二维，不靠人事后补。

生成完还需要人做的：把 fig 里的 <svg> 换成真图（数据 + 渲染函数）、补刻度值。
"""

from __future__ import annotations

import html
import html as html_mod
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mathrender  # noqa: E402

ASSETS = Path(__file__).resolve().parent / "assets"

# 公式用数学衬线字体（Latin Modern Math 子集，scripts/make_mathfont.py 生成）；
# 正文用「手写体」（LXGW WenKai 子集，按 deck 的字符集现场生成，见 embed_text_font）。
MATH_LOCAL = '"Latin Modern Math", "CMU Serif", "STIX Two Math", serif'
TEXT_LOCAL = '"LXGW WenKai", "霞鹜文楷", "KaiTi", "STKaiti", serif'


def math_face() -> str:
    css_file = ASSETS / "mathfont.css"
    if css_file.is_file():
        return css_file.read_text(encoding="utf-8")
    return f'@font-face {{ font-family: "DeckMath"; src: local("Latin Modern Math"); }}\n'


TEXT_FONT_CANDIDATES = [
    os.environ.get("DECK_TEXT_FONT", ""),
    str(Path.home() / ".local/share/fonts/LXGWWenKai-Regular.ttf"),
    "/usr/share/fonts/truetype/lxgw-wenkai/LXGWWenKai-Regular.ttf",
]


def find_text_font() -> str | None:
    for cand in TEXT_FONT_CANDIDATES:
        if cand and Path(cand).is_file():
            return cand
    return None


_TEXT_CACHE: dict[str, str] = {}


def text_face(charset: str) -> str:
    """把 deck 用到的字符子集化成 DeckText（woff2 + base64），返回 @font-face 规则。

    每个 deck 的字符集不同，所以文本字体是「按 deck 现场生成」而不是仓库里的固定资产：
    300 个汉字约 86KB woff2，固定全量 CJK 子集会撑爆 320KB。
    源字体缺失时返回空串，check_deck 会报「缺 DeckText」。
    """
    key = str(abs(hash(charset)))
    if key in _TEXT_CACHE:
        return _TEXT_CACHE[key]
    source = find_text_font()
    if not source or not charset:
        return ""
    import base64
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        txt = Path(tmp) / "chars.txt"
        out = Path(tmp) / "text.woff2"
        txt.write_text(charset, encoding="utf-8")
        subprocess.run(
            [sys.executable, "-m", "fontTools.subset", source, f"--text-file={txt}",
             "--flavor=woff2", f"--output-file={out}", "--layout-features=*", "--no-hinting"],
            check=True, capture_output=True)
        from fontTools.ttLib import TTFont

        # recalcTimestamp 是 TTFont 的构造参数（默认 True）：开着它每次 save 都把
        # head.modified 刷成当前秒，重建同一份 deck 会得到逐字节不同的 woff2。
        # 关掉后 head.modified 沿用源字体的值，构建可复现。
        font = TTFont(out, recalcTimestamp=False)
        for name_id, value in ((1, "DeckText"), (3, "DeckText-Regular"), (4, "DeckText"),
                               (6, "DeckText-Regular"), (16, "DeckText"), (17, "Regular")):
            font["name"].setName(value, name_id, 3, 1, 0x409)
            font["name"].setName(value, name_id, 1, 0, 0)
        font.flavor = "woff2"
        font.save(out)
        b64 = base64.b64encode(out.read_bytes()).decode("ascii")
    css = ('@font-face { font-family: "DeckText"; font-display: block; font-weight: 100 900;\n'
           f'  src: url(data:font/woff2;base64,{b64}) format("woff2"); }}\n')
    _TEXT_CACHE[key] = css
    return css


def visible_text(html: str) -> str:
    """deck 里所有会被渲染的字符：正文文本 + CSS 伪元素 content 字符串。"""
    body = re.sub(r"<style\b.*?</style>|<script\b.*?</script>", "", html, flags=re.S | re.I)
    text = html_mod.unescape(re.sub(r"</?[A-Za-z][^>]*>", "", body))
    css = "".join(re.findall(r"<style\b[^>]*>(.*?)</style>", html, re.S | re.I))
    text += "".join(re.findall(r"content\s*:\s*\"([^\"]*)\"", css))
    # 空格必须进子集：缺 U+0020 时渲染引擎会拿系统字体画空格（实测 Chrome PDF 里 737 个空格回退到 LXGW）
    return "".join(sorted({" "} | {ch for ch in text if not ch.isspace()}))


def embed_text_font(html: str) -> str:
    """把按 deck 字符集生成的 DeckText 塞进 /*__TEXT_FACE__*/ 占位处。"""
    return html.replace("/*__TEXT_FACE__*/", text_face(visible_text(html)))


CSS = (
    math_face()
    + ':root { --text: "DeckText", ' + TEXT_LOCAL + ';\n'
    + '         --math: "DeckMath", ' + MATH_LOCAL + '; }\n'
    + """  /*__TEXT_FACE__*/
  html, body { margin: 0; height: 100%; overflow: hidden; background: #fbfaf8; color: #1b1b1b;
    font-family: var(--text); font-size: 21px; }
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
  /* 公式：数学衬线排版（参考图口径）。无旋转、无下划线、无底色、无边框；
     手写观感只留给正文文字（var(--text)），公式一律 var(--math)。 */
  /* 参考图口径：白底、1px 深色方框内一行式子；无旋转、无下划线、无底色。
     方框只框式子本身（.expr），单位行与推导表留在框外。 */
  .formula { font-size: 30px; margin: 12px 0 0; color: #0f1115; line-height: 1.4; }
  .formula .expr { display: inline-block; border: 1px solid #0f1115; background: #fff;
    padding: 9px 10px; line-height: 1; font-family: var(--math); white-space: nowrap; }
  .formula .eqno { font-size: 20px; color: #2c7fb8; font-weight: 650; margin-right: 12px;
    font-family: var(--text); }
  .formula .units { display: block; font-size: 19px; color: #4a5260; margin-top: 4px;
    font-family: var(--text); }
  .formula var, ol.axioms var { font-style: normal; }
  /* 推导表的「式子」列是表格文字：跟正文一样用文字字体（含中文注释） */
  details.deriv td:nth-child(2) { font-size: 19px; }
  .io { font-size: 20px; color: #4a5260; margin: 6px 0 2px; }
  ol.axioms { margin: 10px 0 0; padding-left: 30px; font-size: 22px; line-height: 1.7; }
  ol.axioms li { margin-bottom: 4px; }
  ol.axioms b { color: #2c7fb8; font-weight: 650; }
  ol.axioms .eq { font-weight: 400; font-family: var(--math); font-size: 25px; }
  ol.axioms .note { margin-left: 12px; color: #5d6470; }
  ol.axioms .note::before { content: "—— "; }
  .lead { font-size: 21px; line-height: 1.45; margin: 10px 0 0; }
  .pg { position: absolute; right: 44px; bottom: 20px; font-size: 18px; color: #8b929b; }
  ul.pit { margin: 10px 0 0; padding-left: 0; list-style: none; font-size: 20px; line-height: 1.45; }
  ul.pit li { margin: 0 0 10px; padding-left: 14px; border-left: 4px solid #7f8c8d; }
  ul.pit b { color: #c0392b; }
  ul.items { margin: 10px 0 0; padding-left: 0; list-style: none; font-size: 21px; line-height: 1.5; }
  /* 项目符号用 CSS 生成，字符会进子集；默认的 disc 是引擎自带字形，不在子集里会回退系统字体 */
  ul.items li::before { content: "•"; color: #2c7fb8; margin-right: .5em; }
  details { border: 1px solid #dcd8d0; border-radius: 8px; background: #fff; padding: 5px 14px; margin-top: 8px; font-size: 19px; }
  summary { font-size: 20px; font-weight: 550; cursor: pointer; list-style: none; }
  summary::-webkit-details-marker { display: none; }
  /* 折叠三角用 border 画，不用字形：默认 marker 的 ▶ 不在子集里，会回退系统字体 */
  summary::before { content: ""; display: inline-block; width: 0; height: 0;
    border-left: 7px solid #666; border-top: 5px solid transparent; border-bottom: 5px solid transparent;
    margin-right: 8px; vertical-align: middle; }
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
) + mathrender.MATH_CSS

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


def _unescape(fragment: str) -> str:
    for entity, char in (("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&"),
                         ("&quot;", '"'), ("&#39;", "'")):
        fragment = fragment.replace(entity, char)
    return fragment


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
MATH_SPAN_RE = re.compile(r"\$([^$]+)\$")
# 散文里的「公式词」：含 Unicode 上下标或 _ / ^ 的一整个词（log₁₀、j₀、10⁻³、E_eq）
TOKEN_RE = re.compile(r"[^\s，。、；：（）【】《》「」\[\]]+")
UNICODE_SCRIPT_RE = re.compile("[\u2070-\u207f\u2080-\u209c\u00b9\u00b2\u00b3]")
SCRIPT_TOKEN_RE = re.compile("[\u2070-\u207f\u2080-\u209c\u00b9\u00b2\u00b3_^]")


def prose(fragment: str) -> str:
    """散文 → HTML：含 Unicode 上下标 / _ / ^ 的词自动排成行内 <math>，其余原样转义。

    这样作者在标题、正文、图注、单位行里照旧写 log₁₀、j₀、10⁻³，
    产出的 HTML 里它们已经是 <math><msub>…</msub></math>（C11 查的就是这一点）。
    """
    out: list[str] = []
    pos = 0
    for match in TOKEN_RE.finditer(fragment):
        out.append(esc(fragment[pos:match.start()]))
        token = match.group(0)
        if SCRIPT_TOKEN_RE.search(token):
            out.append(mathrender.math(token, mark_syms=False))
        else:
            out.append(esc(token))
        pos = match.end()
    out.append(esc(fragment[pos:]))
    return "".join(out)


def subs(fragment: str, auto: bool = False) -> str:
    """散文里的公式 → 行内 <math>；其余文字照常转义。

    三条规则（写进 SKILL.md 与 check_deck.py 的 C9/C12）：
      · `$…$` 里的内容按公式 DSL 排成行内 MathML（标题/正文/图注/单位行/推导表都能用）；
      · auto=True（推导表的「式子」列、复算表的数值格）：整格就是一个 <math>，
        中文注释进 <mtext>（仍用正文手写体），所以「失效：$Δlog$ …」不必手写 $…$；
      · 「依据」列与正文是散文（auto=False），只认 `$…$`（否则「A2」会被排成 A 2）。
    分式按 C12 自动二维：`a/b` 两侧各是一个完整式子 → <mfrac>；两侧都是单位词（mA/cm²）→ 留斜杠。
    不允许再出现 <sub>/<sup>、E_eq 这种一行拼接、以及 Unicode 上下标（x²、η⁻¹、log₁₀）——
    它们在 check_deck.py 里直接 error。
    """
    raw = _unescape(str(fragment))
    if not raw.strip():
        return ""
    if auto:
        # 整格公式：MathML 不会在行内折行，长句子会把表格撑出格。所以按中文标点切成
        # 几个 <math>（标点留在外面），表格就能在标点处换行，而每个公式片段仍是 <math>。
        chunks = re.split(r"([，；：。])", raw.replace("$", ""))
        formulaChar = re.compile(r"[^\s\u3400-\u4dbf\u4e00-\u9fff，；：。、（）【】《》「」—…“”‘’]")
        return "".join(
            esc(chunk) if chunk in "，；：。" or not formulaChar.search(chunk) else
            mathrender.math(chunk, mark_syms=False)
            for chunk in chunks if chunk
        )
    parts: list[str] = []
    pos = 0
    for match in MATH_SPAN_RE.finditer(raw):
        parts.append(prose(raw[pos:match.start()]))
        parts.append(mathrender.math(match.group(1), mark_syms=False))
        pos = match.end()
    parts.append(prose(raw[pos:]))
    return "".join(parts)


def expr_span(expr: str, syms: list[str] | None = None) -> str:
    """把公式主体排成 Presentation MathML（mathrender），再包成 .expr（1px 方框由 CSS 给）。

    真分式（`j/j_0`、`Δη/Δlog_{10} j`、`RT/α_aF`）由 mathrender 自动出 <mfrac>，
    量纲写法（`mA/cm²`、`mV/dec`）自动保留斜杠——C12 的口径落在默认路径上。
    """
    return f'<span class="expr">{mathrender.math(expr, syms)}</span>'


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


def figure(spec: dict, caption: str, anim: str = "", compact: bool = False) -> str:
    sym_x, sym_y = spec.get("xsym", spec["x"]), spec.get("ysym", spec["y"])
    anim_attr = f' data-anim="{anim}"' if anim else ""
    cls = "fig compact" if compact else "fig"
    return f"""  <figure class="{cls}" data-x="{esc(spec['x'])}" data-y="{esc(spec['y'])}" data-xscale="{spec.get('xscale', 'linear')}" data-yscale="{spec.get('yscale', 'log')}"{anim_attr}>
    <svg viewBox="0 0 1120 520">
      <!-- TODO 真图：曲线用「数据数组 + 渲染函数」生成，不要逐点写死坐标 -->
      <text class="ax" data-axis="x" data-sym="{esc(sym_x)}">{esc(axis_label(spec, 'x'))}</text>
      <text class="ax" data-axis="y" data-sym="{esc(sym_y)}">{esc(axis_label(spec, 'y'))}</text>
      {ticks(spec, 'x')}
      {ticks(spec, 'y')}
    </svg>
    <figcaption>{subs(caption)}</figcaption>
  </figure>"""


def formula_block(spec: dict) -> str:
    rows = "".join(
        f"<tr><td>{esc(step)}</td><td>{subs(body, auto=True)}</td><td>{subs(basis)}</td></tr>"
        for step, body, basis in spec.get("deriv", [])
    )
    return f"""  <div class="formula" data-eq="{spec['eq']}">
    <span class="eqno">式 ({spec['eq']})</span>{expr_span(spec["expr"], spec.get("syms"))}
    <span class="units">{subs(spec.get('units', 'TODO 符号与单位'))}</span>
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
        f"<tr><td>{esc(step)}</td><td>{subs(body, auto=True)}</td><td>{subs(basis)}</td></tr>"
        for step, body, basis in spec.get("deriv", [])
    )
    return f"""  <details class="deriv" data-eq="{spec['eq']}" data-part="{spec['part']}">
    <summary>推导（第 {spec['part']} 段）：式 ({spec['eq']})</summary>
    <table>
      <tr><th>步骤</th><th>式子</th><th>依据</th></tr>{rows}
    </table>
  </details>"""


def recalc_block(rows: list[list[str]], open_block: bool = False) -> str:
    body = "".join(
        "<tr>" + "".join(
            f"<td>{subs(cell, auto=not CJK_RE.search(cell))}</td>" for cell in row
        ) + "</tr>" for row in rows
    )
    return f"""  <details class="recalc" open>
    <summary>数值复算</summary>
    <table>
      <tr><th>输入</th><th>计算</th><th>结果</th><th>对应</th></tr>{body}
    </table>
  </details>"""


def p_formula_block(spec: dict) -> str:
    """预备段的一条 P 式：数据属性（used-in / stop / axiom）和正文式一样都挂在 .formula 上。"""
    rows = "".join(
        f"<tr><td>{esc(step)}</td><td>{subs(body, auto=True)}</td><td>{subs(basis)}</td></tr>"
        for step, body, basis in spec.get("deriv", [])
    )
    return f"""  <div class="formula" data-eq="{spec['eq']}" data-used-in="{spec['used_in']}" data-axiom="{spec['axiom']}" data-stop="{esc(spec.get('stop', ''))}">
    <span class="eqno">{spec['eq']}</span>{expr_span(spec["expr"], spec.get("syms"))}
    <span class="units">{subs(spec.get('units', 'TODO 符号与单位'))}</span>
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
            f'<span class="eq">{mathrender.math(eq, [])}</span>'
            f'<span class="note">{subs(note)}</span></li>'
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
        f"  <h1>{subs(slide['h1'])}</h1>",
    ]
    if slide.get("axioms_html"):
        parts.append(slide["axioms_html"])
    if slide.get("io"):
        parts.append('  <p class="io">' + subs(slide["io"]) + "</p>")
    if slide.get("recast"):
        parts.append(f'  <p class="recast">{subs(slide["recast"])}</p>')
    if slide.get("fig"):
        # 同页还有公式/复算表时图必须让出高度，否则 details 一展开就超出 900px
        compact = bool(slide.get("formula") or slide.get("recalc")) or slide.get("compact", False)
        parts.append(figure(slide["fig"], slide.get("caption", ""), slide.get("anim", ""), compact))
    if slide.get("pformula"):
        parts.append(p_formula_block(slide["pformula"]))
    if slide.get("formula"):
        parts.append(formula_block(slide["formula"]))
    if slide.get("deriv_part"):
        parts.append(deriv_part_block(slide["deriv_part"]))
    if slide.get("pitfalls"):
        items = "".join(
            f'<li><b>错误做法：</b>{subs(bad)}<b>现象：</b>{subs(seen)}<b>正确做法：</b>{subs(good)}</li>'
            for bad, seen, good in slide["pitfalls"]
        )
        parts.append(f'  <ul class="pit">{items}</ul>')
    if slide.get("items"):
        items = "".join(f"<li>{subs(item)}</li>" for item in slide["items"])
        parts.append(f'  <ul class="items">{items}</ul>')
    if slide.get("lead"):
        parts.append(f'  <p class="lead">{subs(slide["lead"])}</p>')
    if slide.get("recalc"):
        parts.append(recalc_block(slide["recalc"], slide.get("open_recalc", False)))
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
        # 复算表单独成页：塞进末页会和图/推导抢 900px，展开即溢出（实测）
        slides.append({"kind": "calc", "h1": "数值复算：每个带单位的数都能在这里查到出处",
                       "recalc": recalc, "open_recalc": True})
        total = len(slides)
        body = "\n\n".join(slide_html(slide, i, total) for i, slide in enumerate(slides, start=1))
    return embed_text_font(f"""<!doctype html>
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
""")


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
