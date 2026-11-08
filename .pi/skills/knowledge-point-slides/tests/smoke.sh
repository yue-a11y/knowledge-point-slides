#!/usr/bin/env bash
# check_deck.py 自测：好样本必须过，每类硬规则各造一个坏样本必须挂。
# 覆盖：形式层 / 坐标 / 推导 / 页预算 + 公式预备段 C1–C5 + 元话语 C6 + 定义不推导 C7 + 公理范围 C8。
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"
CHECK="$SKILL_DIR/scripts/check_deck.py"
SCAFFOLD="$SKILL_DIR/scripts/scaffold.py"
FIX="$SKILL_DIR/tests/fixtures"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

pass=0
fail=0
ok()  { echo "  ok   $1"; pass=$((pass + 1)); }
bad() { echo "  FAIL $1"; sed 's/^/       /' "$tmp/out.txt" 2>/dev/null; fail=$((fail + 1)); }

fresh() { # fresh <dir>
  local dir="$tmp/$1"
  rm -rf "$dir"
  mkdir -p "$dir/shots"
  cp "$FIX/tafel-deck.html" "$dir/"
  : >"$dir/shots/deck-print.pdf"
  for n in 01 02 03; do : >"$dir/shots/p-$n.png"; done
  echo "$dir"
}

expect() { # expect <期望码> <用例名> <html> [额外参数…]
  local want="$1" label="$2" html="$3"
  shift 3
  "$PY" "$CHECK" "$html" "$@" >"$tmp/out.txt" 2>&1
  local got=$?
  if [[ $got -eq $want ]]; then
    ok "$label"
  else
    bad "$label（期望 $want，实际 $got）"
  fi
}

echo "== check_deck.py 自测 =="

good="$(fresh good)"
expect 0 "好样本通过（axioms 页 + P1/P2 + 正文）" "$good/tafel-deck.html"

# ---- 形式层 ---------------------------------------------------------------
d="$(fresh cdn)"; sed -i 's|<main id="deck">|<script src="https://cdn.jsdelivr.net/npm/chart.js"></script><main id="deck">|' "$d/tafel-deck.html"
expect 1 "外链 CDN 被抓出" "$d/tafel-deck.html"

d="$(fresh eq)"; sed -i 's/data-eq="2"/data-eq="1"/' "$d/tafel-deck.html"
expect 1 "式号重复/不连续被抓出" "$d/tafel-deck.html"

d="$(fresh banned)"; sed -i 's|<h1>把 60 mV/dec 代回同一条直线：η = 300 mV 时 j/j₀ = 10⁵</h1>|<h1>谢谢观看</h1>|' "$d/tafel-deck.html"
expect 1 "「谢谢观看」被抓出" "$d/tafel-deck.html"

d="$(fresh font)"; sed -i 's/font-size: 20px; font-family/font-size: 16px; font-family/' "$d/tafel-deck.html"
expect 1 "body 字号 <20px 被抓出" "$d/tafel-deck.html"

d="$(fresh overflow)"; sed -i 's/overflow: hidden; //g' "$d/tafel-deck.html"
expect 1 "缺 overflow:hidden 被抓出" "$d/tafel-deck.html"

d="$(fresh page)"; sed -i 's/data-page="5"/data-page="9"/' "$d/tafel-deck.html"
expect 1 "data-page 不连续被抓出" "$d/tafel-deck.html"

d="$(fresh pitfall)"; sed -i 's/错误做法/做法错误/g' "$d/tafel-deck.html"
expect 1 "易错点三段式缺失被抓出" "$d/tafel-deck.html"

d="$(fresh pages)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r'<section class="slide" data-page="5".*?</section>', "", text, flags=re.S)
path.write_text(text, encoding="utf-8")
PY
expect 1 "删掉中间一页后 data-page 不连续被抓出（页数已不设上下限）" "$d/tafel-deck.html"

# ---- 呈现层：页码与视口 ---------------------------------------------------
d="$(fresh pageno)"; sed -i 's|<span class="pg">4 / 11</span>||' "$d/tafel-deck.html"
expect 1 "缺页码被抓出" "$d/tafel-deck.html"

d="$(fresh pageno2)"; sed -i 's|<span class="pg">5 / 11</span>|<span class="pg">5 / 14</span>|' "$d/tafel-deck.html"
expect 1 "页码与总页数不符被抓出" "$d/tafel-deck.html"

d="$(fresh noscale)"; sed -i 's|transform: scale(var(--k, 1))|transform: none|; s|--k|--kk|g' "$d/tafel-deck.html"
expect 1 "没有视口缩放（页码会跑出屏幕）被抓出" "$d/tafel-deck.html"

d="$(fresh noresize)"; sed -i "s|addEventListener('resize', fit);||" "$d/tafel-deck.html"
expect 1 "没有 resize 监听被抓出" "$d/tafel-deck.html"

d="$(fresh pghidden)"; sed -i 's|\.pg { position: absolute;|.pg { display: none; position: absolute;|' "$d/tafel-deck.html"
expect 1 "页码被 display:none 藏掉被抓出" "$d/tafel-deck.html"

# ---- 去自测 ---------------------------------------------------------------
d="$(fresh quiz)"; sed -i 's|<h1>把 60 mV/dec 代回同一条直线：η = 300 mV 时 j/j₀ = 10⁵</h1>|<h1>自测：三道题</h1>|' "$d/tafel-deck.html"
expect 1 "出现「自测」被抓出" "$d/tafel-deck.html"

d="$(fresh summary)"; sed -i 's|data-page="11" data-kind="calc"|data-page="11" data-kind="summary"|' "$d/tafel-deck.html"
expect 1 "末页另起结论页（summary 已取消）被抓出" "$d/tafel-deck.html"

d="$(fresh lasttitle)"; sed -i 's|<h1>把 60 mV/dec 代回同一条直线：η = 300 mV 时 j/j₀ = 10⁵</h1>|<h1>结论：斜率就是线性段的两条边</h1>|' "$d/tafel-deck.html"
expect 1 "末页标题写成「结论：…」被抓出" "$d/tafel-deck.html"

d="$(fresh lastkind)"; sed -i 's|data-page="11" data-kind="calc"|data-page="11" data-kind="theory"|' "$d/tafel-deck.html"
expect 1 "末页不在最后一个算例上被抓出" "$d/tafel-deck.html"

# ---- 坐标系 ---------------------------------------------------------------
d="$(fresh staleaxis)"; sed -i 's|>η \[mV\]</text>|>E vs RHE [V]</text>|' "$d/tafel-deck.html"
expect 1 "换坐标后轴标签没换被抓出" "$d/tafel-deck.html"

d="$(fresh loglabel)"; sed -i 's|>log₁₀ j \[mA/cm²\]</text>|>j [mA/cm²]（对数）</text>|' "$d/tafel-deck.html"
expect 1 "纵轴写成「j（对数）」被抓出" "$d/tafel-deck.html"

d="$(fresh logtick)"; sed -i 's|>10⁻²</text>|>0</text>|' "$d/tafel-deck.html"
expect 1 "log 轴刻度出现 0 被抓出" "$d/tafel-deck.html"

d="$(fresh lineartick100)"; sed -i 's|<text x="420" y="430" font-size="20" text-anchor="middle" data-axis="x">200</text>|<text x="420" y="430" font-size="20" text-anchor="middle" data-axis="x">100</text>|' "$d/tafel-deck.html"
expect 0 "线性轴刻度写 100 不再被误判成 10ⁿ（LOG_TICK_RE 回归）" "$d/tafel-deck.html"

d="$(fresh noaxis)"; sed -i 's| data-x="η" data-y="j" data-xscale="linear" data-yscale="log" data-anim="dim"| data-anim="dim"|' "$d/tafel-deck.html"
expect 1 "图缺 data-x/data-y 声明被抓出" "$d/tafel-deck.html"

d="$(fresh recast)"; sed -i 's|<p class="recast">横轴由 E 换成 η = E − E_eq（本例 E_eq = 0，刻度值不变，标签必须改）</p>||' "$d/tafel-deck.html"
expect 1 "换坐标却没写 recast 被抓出" "$d/tafel-deck.html"

d="$(fresh residual)"; sed -i 's|<figcaption>同一组数据，横轴换成过电位（示例数据）</figcaption>|<figcaption>E 0–0.4 V vs RHE（示例数据）</figcaption>|' "$d/tafel-deck.html"
expect 1 "换轴后图注残留旧量名被抓出" "$d/tafel-deck.html"

d="$(fresh dimspan)"; sed -i 's|<g class="dim" data-span="x" data-sym="η">|<g class="dim" data-span="y" data-sym="η">|' "$d/tafel-deck.html"
expect 1 "Δη 画在竖边被抓出" "$d/tafel-deck.html"

d="$(fresh dimq)"; sed -i 's|>Δη = 100 mV</text>|>Δlog₁₀ j = 1.667 dec</text>|' "$d/tafel-deck.html"
expect 1 "标注量与轴不符被抓出" "$d/tafel-deck.html"

d="$(fresh phenom)"; sed -i 's|<h1>横轴换成过电位 η，不同样品的曲线才能并排比</h1>|<h1>0.26 V 之后曲线变平，横轴换成 η 也一样</h1>|' "$d/tafel-deck.html"
expect 1 "线性纵轴上说「变平」被抓出" "$d/tafel-deck.html"

# ---- 公式 / 推导（正文） --------------------------------------------------
d="$(fresh lhsdup)"; sed -i 's|<var data-sym="b">b</var> = Δ<var data-sym="η">η</var>|<var data-sym="η">η</var> = Δ<var data-sym="η">η</var>|' "$d/tafel-deck.html"
expect 1 "公式 LHS 重复（移项另编号）被抓出" "$d/tafel-deck.html"

d="$(fresh maxeq)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace(
    '<p>斜率只由速率决定步骤定，与电流绝对值无关。</p>',
    '<div class="formula" data-eq="3"><span class="eqno">式 (3)</span>'
    'log₁₀ <var data-sym="j">j₀</var> = log₁₀ <var data-sym="j">j</var> − <var data-sym="η">η</var> / <var data-sym="b">b</var>'
    ' <span class="units">j [mA/cm²]</span></div>',
    1,
)
path.write_text(text, encoding="utf-8")
PY
expect 1 "显式设 --max-eq 2 时超上限被抓出" "$d/tafel-deck.html" --max-eq 2

d="$(fresh ops)"; sed -i 's|<p>斜率只由速率决定步骤定，与电流绝对值无关。</p>|<p>这里还没做 iR 补偿，所以要把读数往回推。</p>|' "$d/tafel-deck.html"
expect 1 "讲补偿却没给定义式被抓出" "$d/tafel-deck.html"

d="$(fresh sym)"; sed -i 's|<var data-sym="η">η</var> = <var data-sym="b">b</var> · log₁₀( <var data-sym="j">j</var> / <var data-sym="j0">j₀</var> )|<var data-sym="eta">η</var> = <var data-sym="beta">b</var> · log₁₀( <var data-sym="cur">j</var> / <var data-sym="cur0">j₀</var> )|' "$d/tafel-deck.html"
expect 1 "式里的符号图上都没有被抓出" "$d/tafel-deck.html"

d="$(fresh noderiv)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r'<details class="deriv" data-eq="2">.*?</details>', "", text, flags=re.S)
path.write_text(text, encoding="utf-8")
PY
expect 1 "式 (2) 缺同页推导块被抓出" "$d/tafel-deck.html"

d="$(fresh nobasis)"; sed -i 's|>依据</th>|>备注</th>|g' "$d/tafel-deck.html"
expect 1 "推导缺「依据」列被抓出" "$d/tafel-deck.html"

d="$(fresh noassume)"; sed -i 's|A2 在窗口内成立|上述条件成立|' "$d/tafel-deck.html"
expect 1 "推导没引用假设编号被抓出" "$d/tafel-deck.html"

d="$(fresh norecalc)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r'<details class="recalc">.*?</details>', "", text, flags=re.S)
path.write_text(text, encoding="utf-8")
PY
expect 1 "缺数值复算表被抓出" "$d/tafel-deck.html"

d="$(fresh deriv2)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r'<details class="deriv" data-eq="2" data-part="2">.*?</details>', "", text, flags=re.S)
rows = ('<table><tr><th>步骤</th><th>式子</th><th>依据</th></tr>'
        '<tr><td>(2.1)</td><td>b = Δη / Δlog₁₀ j</td><td>定义：A5 就是斜率定义</td></tr>'
        '<tr><td>(2.5)</td><td>失效：Δlog₁₀ j &lt; 0.5 dec 时端点 ±2 mV 使 b 偏差 &gt; 20%</td><td>误差与边界</td></tr>'
        '</table>')
text = re.sub(r'(<details class="deriv" data-eq="2">)(.*?)(</details>)',
              lambda m: m.group(1) + rows + m.group(3), text, count=1, flags=re.S)
path.write_text(text, encoding="utf-8")
PY
expect 1 "推导只剩 2 步（没讲怎么来的）被抓出" "$d/tafel-deck.html"

d="$(fresh derivsrc)"; sed -i 's|代数：两点差；量纲：dec 无量纲|代数：由式 (1) 得|' "$d/tafel-deck.html"
expect 1 "推导用「由式 (N) 得」代替推理被抓出" "$d/tafel-deck.html"

d="$(fresh gloss)"; sed -i 's|代数：读本页窗口两端|代数：读本页窗口两端，其中 j 为电流密度|' "$d/tafel-deck.html"
expect 1 "推导里解释符号含义被抓出" "$d/tafel-deck.html"

d="$(fresh partgap)"; sed -i 's|data-eq="2" data-part="2"|data-eq="2" data-part="3"|' "$d/tafel-deck.html"
expect 1 "推导分片号不连续被抓出" "$d/tafel-deck.html"

d="$(fresh partpage)"; sed -i 's|data-page="11" data-kind="calc"|data-page="11" data-kind="pitfall"|' "$d/tafel-deck.html"
expect 1 "推导续页不是 calc 被抓出" "$d/tafel-deck.html"

d="$(fresh derivnum)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
rows = ('<table><tr><th>步骤</th><th>式子</th><th>依据</th></tr>'
        '<tr><td>(1.1)</td><td>η = b·log₁₀(j/j₀)</td><td>定义：P1 已从 BV 推完这条形式</td></tr>'
        '<tr><td>(1.2)</td><td>log₁₀(j/j₀) 随 η 增大</td><td>代数：整理</td></tr>'
        '<tr><td>(1.3)</td><td>高过电位段才成直线</td><td>误差与边界</td></tr>'
        '</table>')
text = re.sub(r'(<details class="deriv" data-eq="1">)(.*?)(</details>)',
              lambda m: m.group(1) + rows + m.group(3), text, count=1, flags=re.S)
path.write_text(text, encoding="utf-8")
PY
expect 1 "推导没有代入本页的数被抓出" "$d/tafel-deck.html"

d="$(fresh deriverr)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
rows = ('<table><tr><th>步骤</th><th>式子</th><th>依据</th></tr>'
        '<tr><td>(1.1)</td><td>η = b·log₁₀(j/j₀)</td><td>定义：P1 已从 BV 推完这条形式</td></tr>'
        '<tr><td>(1.2)</td><td>log₁₀(j/j₀) = 300 mV ÷ 60 mV/dec = 5.0 dec</td><td>代数：代入本页的数；量纲：dec</td></tr>'
        '<tr><td>(1.3)</td><td>高过电位段才成直线</td><td>代数：整理</td></tr>'
        '</table>')
text = re.sub(r'(<details class="deriv" data-eq="1">)(.*?)(</details>)',
              lambda m: m.group(1) + rows + m.group(3), text, count=1, flags=re.S)
path.write_text(text, encoding="utf-8")
PY
expect 1 "推导没写误差/失效边界被抓出" "$d/tafel-deck.html"

# ---- 页预算 / 动画 / 重复图 ----------------------------------------------
d="$(fresh kind)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace('<section class="slide" data-page="5" data-kind="theory">',
                    '<section class="slide" data-page="5" data-kind="calc">', 1)
path.write_text(text, encoding="utf-8")
PY
expect 1 "没有条件页（理论在计算之后）被抓出" "$d/tafel-deck.html"

d="$(fresh pitfall2)"; sed -i 's|<p>斜率只由速率决定步骤定，与电流绝对值无关。</p>|<p>错误做法：把 j 直接取平均。现象：斜率被抹平。正确做法：按式 (2) 取两端。</p>|' "$d/tafel-deck.html"
expect 1 "错例页超过 1 页被抓出" "$d/tafel-deck.html"

d="$(fresh animdup)"; sed -i 's|data-xscale="linear" data-yscale="log">|data-xscale="linear" data-yscale="log" data-anim="scale">|' "$d/tafel-deck.html"
expect 1 "同一种动画用两次被抓出" "$d/tafel-deck.html"

d="$(fresh pageone)"; sed -i 's|  <span class="pg">1 / 11</span>|  <g class="dim" data-span="x"><text data-axis="x">Δ</text></g><span class="pg">1 / 11</span>|' "$d/tafel-deck.html"
expect 1 "公理清单页（第 1 页）叠高亮带被抓出" "$d/tafel-deck.html"

d="$(fresh dupfig)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace('<polyline points="80,399 180,372 300,318 420,258 540,196 660,132 760,72"',
                    '<polyline points="80,398 200,380 320,330 420,270 520,210 620,150 760,90"', 1)
text = text.replace('<path d="M 260,380 L 700,98" fill="none" stroke="#c33" stroke-width="3"/>',
                    '<path d="M 300,345 L 700,93" fill="none" stroke="#c33" stroke-width="3" stroke-dasharray="8 5"/>', 1)
path.write_text(text, encoding="utf-8")
PY
expect 1 "两页用同一张图被抓出" "$d/tafel-deck.html"

# ---- C1 孤儿符号闭包 ------------------------------------------------------
d="$(fresh c1)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace('<p>刻度值一样，但刻度上的量变了',
                    '<p><var data-sym="E₀">E₀</var> 是表观起始电位；刻度值一样，但刻度上的量变了', 1)
path.write_text(text, encoding="utf-8")
PY
expect 1 "C1：calc 页出现预备段没定义的符号被抓出" "$d/tafel-deck.html"

# ---- C2 被用到与冗余 ------------------------------------------------------
d="$(fresh c2a)"; sed -i 's| data-used-in="7"||' "$d/tafel-deck.html"
expect 1 "C2：P1 缺 data-used-in 被抓出" "$d/tafel-deck.html"

d="$(fresh c2b)"; sed -i 's|data-eq="P2" data-used-in="8"|data-eq="P2" data-used-in="9"|' "$d/tafel-deck.html"
expect 1 "C2：P2 声明用于第 9 页但该页没引用它被抓出" "$d/tafel-deck.html"

d="$(fresh c2c)"; sed -i 's|data-eq="P2" data-used-in="8"|data-eq="P2" data-used-in="5"|' "$d/tafel-deck.html"
expect 1 "C2：data-used-in 指向非 calc 页被抓出" "$d/tafel-deck.html"

# ---- C3 版式 --------------------------------------------------------------
d="$(fresh c3a)"; sed -i '0,/data-kind="axioms"/s//data-kind="origin"/' "$d/tafel-deck.html"
expect 1 "C3：第 1 页不是 axioms 被抓出" "$d/tafel-deck.html"

d="$(fresh c3b)"; sed -i 's|data-page="2" data-kind="formula" data-eq="P1"|data-page="2" data-kind="formula" data-eq="P1" data-anim="dim"|' "$d/tafel-deck.html"
expect 1 "C3：预备段页带动画被抓出" "$d/tafel-deck.html"

d="$(fresh c3c)"; sed -i 's|<p class="io">吃进：j \[mA/cm²\]（第 4 页读得到）→ 吐出：η \[mV\]</p>||' "$d/tafel-deck.html"
expect 1 "C3：P 页缺 .io 行（吃进/吐出）被抓出" "$d/tafel-deck.html"

d="$(fresh c3d)"; sed -i 's|data-stop="正文最后一次代入这条式在第 7 页取纵轴；再往下是 α 的物理来源，不推"||' "$d/tafel-deck.html"
expect 1 "C3：P 缺 data-stop（停点理由）被抓出" "$d/tafel-deck.html"

d="$(fresh c3e)"; sed -i 's|P1 已从 BV 推完这条形式|式 (P1) 已推完这条形式|' "$d/tafel-deck.html"
expect 1 "C3：用「式 (P1)」混写被抓出" "$d/tafel-deck.html"

d="$(fresh c3f)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace('"P2"', '"P3"')
path.write_text(text, encoding="utf-8")
PY
expect 1 "C3：P 号不连号被抓出" "$d/tafel-deck.html"

# ---- C4 公理链 -------------------------------------------------------------
d="$(fresh c4a)"; sed -i 's|<tr><td>(1.1)</td><td>j = j₀\[exp(α_aFη/RT) − exp(−α_cFη/RT)\]</td><td>A3</td></tr>|<tr><td>(1.1)</td><td>j = j₀[exp(α_aFη/RT) − exp(−α_cFη/RT)]</td><td>Tafel 方程</td></tr>|' "$d/tafel-deck.html"
expect 1 "C4：P1 首步依据写成「Tafel 方程」（推论当公理）被抓出" "$d/tafel-deck.html"

d="$(fresh c4b)"; sed -i 's|data-axiom="A3" data-stop|data-axiom="A9" data-stop|' "$d/tafel-deck.html"
expect 1 "C4：data-axiom 指向 A 节里不存在的编号被抓出" "$d/tafel-deck.html"

d="$(fresh c4c)"; sed -i 's|<p>斜率只由速率决定步骤定，与电流绝对值无关。</p>|<p>显然斜率只由速率决定步骤定。</p>|' "$d/tafel-deck.html"
expect 1 "C4：全文出现「显然」跳步被抓出" "$d/tafel-deck.html"

d="$(fresh c4d)"; sed -i 's|<td>定义：P1 已从 BV 推完这条形式</td>|<td>由 P1 得</td>|' "$d/tafel-deck.html"
expect 1 "C4：预备段内部用「由 P1 得」代替推理被抓出" "$d/tafel-deck.html"

# ---- C5 公理清单 -----------------------------------------------------------
d="$(fresh c5a)"; sed -i 's|<span class="eq">E_eq = 0.00 V</span>|<span class="eq">η 较大时可略还原项，E_eq = 0.00 V</span>|' "$d/tafel-deck.html"
expect 1 "C5：A 节里写近似被抓出" "$d/tafel-deck.html"

d="$(fresh c5b)"; sed -i 's|<b>\[约定\]</b>|<b>[教科书结论]</b>|' "$d/tafel-deck.html"
expect 1 "C5：公理用了禁止标签 [教科书结论] 被抓出" "$d/tafel-deck.html"

d="$(fresh c5c)"; sed -i 's|data-uses="A1,A4"|data-uses="A1"|' "$d/tafel-deck.html"
expect 1 "C5：A4 声明用于第 6 页但该页没引用它（冗余公理）被抓出" "$d/tafel-deck.html"

d="$(fresh c5d)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r'\s*<li data-axiom="A5".*?</li>', "", text, count=1, flags=re.S)
path.write_text(text, encoding="utf-8")
PY
expect 1 "C5：P 的 data-axiom 指向被删掉的公理被抓出" "$d/tafel-deck.html"

# ---- C6 元话语 -------------------------------------------------------------
d="$(fresh c6)"; sed -i 's|<h1>横轴换成过电位 η，不同样品的曲线才能并排比</h1>|<h1>开讲前先钉死五条：A1–A5 之外不再假设任何东西</h1>|' "$d/tafel-deck.html"
expect 1 "C6：标题里出现「开讲前 / 不再假设」被抓出" "$d/tafel-deck.html"

d="$(fresh c6b)"; sed -i 's|<p>刻度值一样，但刻度上的量变了，图上每个数都要跟着换名字。</p>|<p>为了讲清楚，本节只讲换轴这一件事。</p>|' "$d/tafel-deck.html"
expect 1 "C6：正文里出现「为了讲清楚 / 本节只」被抓出" "$d/tafel-deck.html"

# ---- C7 定义不推导 ---------------------------------------------------------
d="$(fresh c7a)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace(
    '<var data-sym="η">η</var> = <var data-sym="b">b</var> · log₁₀( <var data-sym="j">j</var> / <var data-sym="j0">j₀</var> )',
    '<var data-sym="η">η</var> = <var data-sym="E">E</var> − <var data-sym="E_eq">E_eq</var>', 1)
path.write_text(text, encoding="utf-8")
PY
expect 1 "C7a：把 η ≡ E − E_eq 重新立成 P1（定义当推导）被抓出" "$d/tafel-deck.html"

d="$(fresh c7b)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
rows = ('<table><tr><th>步骤</th><th>式子</th><th>依据</th></tr>'
        '<tr><td>(2.1)</td><td>j = j₀[exp(α_aFη/RT) − exp(−α_cFη/RT)]</td><td>A3</td></tr>'
        '<tr><td>(2.2)</td><td>j = j₀[exp(α_aFη/RT) − exp(−α_cFη/RT)]</td><td>A3</td></tr>'
        '<tr><td>(2.3)</td><td>b = Δη / Δlog₁₀ j</td><td>代数：整理</td></tr>'
        '<tr><td>(2.4)</td><td>100 mV ÷ 1.667 dec = 60.0 mV/dec</td><td>数值：代入本例的数</td></tr>'
        '</table>')
text = re.sub(r'(<details class="deriv" data-eq="2">)(.*?)(</details>)',
              lambda m: m.group(1) + rows + m.group(3), text, count=1, flags=re.S)
path.write_text(text, encoding="utf-8")
PY
expect 1 "C7b：推导里两行照抄公理式子被抓出" "$d/tafel-deck.html"

d="$(fresh c7c)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
rows = ('<table><tr><th>步骤</th><th>式子</th><th>依据</th></tr>'
        '<tr><td>(2.1)</td><td>η = b·log₁₀(j/j₀)</td><td>定义：P1 已从 BV 推完这条形式</td></tr>'
        '<tr><td>(2.2)</td><td>b = 100 mV ÷ 1.667 dec = 60.0 mV/dec</td><td>代数：代入本页的数</td></tr>'
        '<tr><td>(2.3)</td><td>失效：Δlog₁₀ j &lt; 0.5 dec 时偏差 &gt; 20%</td><td>误差与边界</td></tr>'
        '</table>')
text = re.sub(r'(<details class="deriv" data-eq="2">)(.*?)(</details>)',
              lambda m: m.group(1) + rows + m.group(3), text, count=1, flags=re.S)
path.write_text(text, encoding="utf-8")
PY
expect 1 "C7c：三步空转（照抄 → 代常数 → 换单位）被抓出" "$d/tafel-deck.html"

# ---- C8 公理范围 -----------------------------------------------------------
d="$(fresh c8a)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace('<li data-axiom="A5" data-used-in="2,3"><b>[定义]</b> <span class="eq">k = Δy / Δx</span>',
                    '<li data-axiom="A6" data-used-in="2"><b>[定义]</b> <span class="eq">b = Δη / Δlog₁₀ j</span><span class="note">斜率</span></li>'
                    '<li data-axiom="A5" data-used-in="2,3"><b>[定义]</b> <span class="eq">k = Δy / Δx</span>', 1)
path.write_text(text, encoding="utf-8")
PY
expect 1 "C8a：终点量 b 被写成 A 条目被抓出" "$d/tafel-deck.html"

d="$(fresh c8b)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace('<li data-axiom="A4" data-used-in="6"><b>[约定]</b> <span class="eq">E_eq = 0.00 V</span>',
                    '<li data-axiom="A4" data-used-in="6"><b>[约定]</b> <span class="eq">E_eq = η</span>', 1)
path.write_text(text, encoding="utf-8")
PY
expect 1 "C8b：A 的 RHS 以另一条 A 的 LHS 开头（公理互推）被抓出" "$d/tafel-deck.html"

d="$(fresh c8c)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace('<span class="note">RHE 刻度、本例 pH 0</span>',
                    '<span class="note">RHE 刻度、本例 pH 0；实测得到</span>', 1)
path.write_text(text, encoding="utf-8")
PY
"$PY" "$CHECK" "$d/tafel-deck.html" >"$tmp/out.txt" 2>&1
if grep -q "标了 \[约定\] 却写了" "$tmp/out.txt"; then ok "C8c：[约定] 里写「实测得到」被提示复核"; else bad "C8c 未提示"; fi

# ---- 体积 / 截图 -----------------------------------------------------------
d="$(fresh big)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
points = " ".join(f"{i}.0,{i % 400}.0" for i in range(900))
text = text.replace(
    '<polyline points="80,399 180,372 300,318 420,258 540,196 660,132 760,72"',
    f'<polyline points="{points}"',
    1,
)
path.write_text(text, encoding="utf-8")
PY
"$PY" "$CHECK" "$d/tafel-deck.html" >"$tmp/out.txt" 2>&1
if grep -q "坐标串超过" "$tmp/out.txt"; then ok "逐点内联大坐标串被提示"; else bad "逐点内联大坐标串未被提示"; fi

# 手写体：去掉 @font-face 必须报错（公式不许排在系统字体里）
d="$(fresh noshots)"
"$PY" - "$d/tafel-deck.html" <<'PYEOF'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r'@font-face\s*\{[^}]*\}\s*', '', text, count=1)
path.write_text(text, encoding="utf-8")
PYEOF
"$PY" "$CHECK" "$d/tafel-deck.html" >"$tmp/out.txt" 2>&1
if grep -q "没有 DeckHand" "$tmp/out.txt"; then ok "缺 @font-face 手写体被拦"; else bad "缺 @font-face 手写体未被拦"; fi

# 手写体：.formula 不用 var(--hand) 必须报错
d="$(fresh noshots)"
"$PY" - "$d/tafel-deck.html" <<'PYEOF'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace("font-family: var(--hand);", "", 1)
path.write_text(text, encoding="utf-8")
PYEOF
"$PY" "$CHECK" "$d/tafel-deck.html" >"$tmp/out.txt" 2>&1
if grep -q "没有 font-family: var(--hand)" "$tmp/out.txt"; then ok "公式未用手写体被拦"; else bad "公式未用手写体未被拦"; fi

# 手写体：挂到块级 .formula 上必须报错（中文会回退系统字体）
d="$(fresh noshots)"
"$PY" - "$d/tafel-deck.html" <<'PYEOF'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace(".formula .expr { display: inline-block; font-family: var(--hand);",
                    ".formula { display: inline-block; font-family: var(--hand);", 1)
path.write_text(text, encoding="utf-8")
PYEOF
"$PY" "$CHECK" "$d/tafel-deck.html" >"$tmp/out.txt" 2>&1
if grep -q "手写体挂在了" "$tmp/out.txt"; then ok "手写体挂到块级元素被拦"; else bad "手写体挂到块级元素未被拦"; fi

# 手写体：公式里放中文（子集没有 CJK 字形）必须报错
d="$(fresh noshots)"
"$PY" - "$d/tafel-deck.html" <<'PYEOF'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace('<var data-sym="b">b</var> = Δ<var data-sym="η">η</var> / Δlog₁₀ <var data-sym="j">j</var></span>',
                    '<var data-sym="b">b</var> = Δ<var data-sym="η">η</var> / 对数</span>', 1)
path.write_text(text, encoding="utf-8")
PYEOF
"$PY" "$CHECK" "$d/tafel-deck.html" >"$tmp/out.txt" 2>&1
if grep -q "不在内嵌子集里" "$tmp/out.txt"; then ok "公式里放中文（字形回退）被拦"; else bad "公式里放中文未被拦"; fi

# 倾斜：块级 .formula 上加 rotate 必须报错（表格会跟着斜）
d="$(fresh noshots)"
"$PY" - "$d/tafel-deck.html" <<'PYEOF'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace(".formula { font-size: 26px; margin-top: 16px; }",
                    ".formula { font-size: 26px; margin-top: 16px; transform: rotate(-0.3deg); }", 1)
path.write_text(text, encoding="utf-8")
PYEOF
"$PY" "$CHECK" "$d/tafel-deck.html" >"$tmp/out.txt" 2>&1
if grep -q "上有 rotate/skew" "$tmp/out.txt"; then ok "块级倾斜（会把表格转斜）被拦"; else bad "块级倾斜未被拦"; fi

d="$(fresh noshots)"; rm -f "$d/shots/deck-print.pdf"
"$PY" "$CHECK" "$d/tafel-deck.html" >"$tmp/out.txt" 2>&1
if grep -q "deck-print.pdf" "$tmp/out.txt"; then ok "缺 deck-print.pdf 被提示"; else bad "缺 deck-print.pdf 未被提示"; fi

d="$(fresh skipshots)"; rm -f "$d/shots/deck-print.pdf"
"$PY" "$CHECK" "$d/tafel-deck.html" --skip-shots >"$tmp/out.txt" 2>&1
if [[ $? -eq 0 ]]; then ok "--skip-shots 生效"; else bad "--skip-shots 未生效"; fi

# ---- 脚手架 ---------------------------------------------------------------
if [[ -f "$SCAFFOLD" ]]; then
  cat >"$tmp/outline.json" <<'JSON'
{"title":"脚手架样例","origin_reads":["E","j"],"goal":"b",
 "axioms":[{"id":"A1","tag":"定义","eq":"η ≡ E − E_eq","note":"过电位","used_in":"6,8"},
           {"id":"A2","tag":"定律","eq":"j = j₀[exp(α_aFη/RT) − exp(−α_cFη/RT)]","note":"Butler–Volmer","used_in":"7"},
           {"id":"A3","tag":"定义","eq":"k = Δy / Δx","note":"直线斜率","used_in":"7"}],
 "formula":[
  {"eq":"P1","h1":"P1：BV → Tafel 形式","expr":"η = b · log₁₀( j / j₀ )","syms":["η","b","j","j0"],
   "units":"η [mV]，b [mV/dec]，j、j₀ [mA/cm²]","io":"吃进：j [mA/cm²]（第 5 页读得到）→ 吐出：η [mV]",
   "axiom":"A2","used_in":7,"stop":"正文最后一次代入这条式在第 7 页取纵轴；再往下不推",
   "deriv":[["(1.1)","j = j₀[exp(α_aFη/RT) − exp(−α_cFη/RT)]","A2"],
            ["(1.2)","j ≈ j₀ exp(α_aFη/RT)","近似：η ≫ RT/F = 25.7 mV；η = 150 mV 时还原项占 2.9×10⁻³"],
            ["(1.3)","η = (2.303RT/α_aF) log₁₀(j/j₀)","代数：取自然对数再换底"],
            ["(1.4)","η = 300 mV、b = 60 mV/dec → log₁₀(j/j₀) = 300 mV ÷ 60 mV/dec = 5.0 dec","数值：代入本例的数"],
            ["(1.5)","失效：η < 60 mV 时还原项不可忽略，偏差 10%","误差与边界"]]},
  {"eq":"P2","h1":"P2：两点差商就是 b","expr":"b = Δη / Δlog₁₀ j","syms":["b","η","j"],
   "units":"b [mV/dec]，η [mV]，j [mA/cm²]","io":"吃进：η [mV]、j [mA/cm²]（第 7 页读得到）→ 吐出：b [mV/dec]",
   "axiom":"A3","used_in":7,"stop":"正文最后一次代入这条式在第 7 页取窗口两端；再往下不推",
   "deriv":[["(2.1)","η = b·log₁₀(j/j₀)","定义：P1 已推完这条形式"],
            ["(2.2)","k = (η₂ − η₁)/(log₁₀j₂ − log₁₀j₁)","A3：直线斜率定义，两点相减"],
            ["(2.3)","b = Δη / Δlog₁₀ j","代数：b ≡ k，两点差商；量纲：mV/dec"],
            ["(2.4)","100 mV ÷ 1.667 dec = 60.0 mV/dec","数值：代本例的数"],
            ["(2.5)","失效：Δlog₁₀ j < 0.5 dec 时偏差 > 20%","误差与边界"]]}],
 "slides":[
 {"kind":"origin","h1":"起点","fig":{"x":"E","y":"j","xscale":"linear","yscale":"linear","xunit":"V","yunit":"mA/cm²"},"caption":"示例数据"},
 {"kind":"theory","h1":"先定三条","items":["a","b","c"]},
 {"kind":"calc","h1":"换横轴","uses":["A1"],"recast":"E → η = E − E_eq",
  "fig":{"x":"η","y":"j","xscale":"linear","yscale":"linear","xunit":"mV","yunit":"mA/cm²"},
  "formula":{"eq":1,"expr":"η = E − E_eq","syms":["η","E","E_eq"],"units":"η [mV]",
   "deriv":[["(1.1)","η ≡ E − E_eq","定义：A1（P1 已推完）"],["(1.2)","E = 0.150 V → η = 150 mV","代数：代入本页读数；量纲：V 换 mV"],
            ["(1.3)","失效：η < 10 mV 时 ±2 mV 读数误差 > 20%","误差与边界"]]}},
 {"kind":"calc","h1":"换纵轴","uses":["P1","A2","P2","A3"],"recast":"j → log₁₀ j：刻度改 10ⁿ",
  "fig":{"x":"η","y":"j","xscale":"linear","yscale":"log","xunit":"mV","yunit":"mA/cm²"},
  "formula":{"eq":2,"expr":"b = Δη / Δlog₁₀ j","syms":["b","η","j"],"units":"b [mV/dec]",
   "deriv":[["(2.1)","b = Δη / Δlog₁₀ j","定义：A3（P2 已推完）"],["(2.2)","Δlog₁₀ j = log₁₀(23.2/0.50) = 1.667 dec","代数：两点差；量纲：dec"],
            ["(2.3)","b = 100 mV ÷ 1.667 dec = 60.0 mV/dec","代数：代入本页的数；量纲：mV/dec"],
            ["(2.4)","失效：Δlog₁₀ j < 0.5 dec 时偏差 > 20%","误差与边界"]]}},
 {"kind":"calc","h1":"斜率含义","fig":{"x":"η","y":"j","xscale":"linear","yscale":"log","xunit":"mV","yunit":"mA/cm²"}},
 {"kind":"pitfall","h1":"三个错处","pitfalls":[["a","b","c"],["d","e","f"],["g","h","i"]]},
 {"kind":"calc","h1":"把 b 代回去验算","fig":{"x":"η","y":"j","xscale":"linear","yscale":"log","xunit":"mV","yunit":"mA/cm²"},
  "deriv_part":{"eq":2,"part":2,"deriv":[["(2.5)","α = 59.2 mV/dec ÷ 60.0 mV/dec = 0.99","代数：代入本页的 b；量纲：mV/dec 相除无量纲"],
                                          ["(2.6)","误差：读数 ±2 mV → b 偏 ±1.2 mV/dec","误差与边界"]]}}],
 "recalc":[["j 0.50 → 23.2","log₁₀","1.667 dec","第 7 页"],["η 150 → 250","250−150","100 mV","第 7 页"],["100 ÷ 1.667","除法","60.0 mV/dec","式 (2)"]]}
JSON
  "$PY" "$SCAFFOLD" "$tmp/outline.json" "$tmp/scaffold/deck.html" >/dev/null 2>&1
  mkdir -p "$tmp/scaffold/shots"; : >"$tmp/scaffold/shots/deck-print.pdf"
  for n in 01 02 03; do : >"$tmp/scaffold/shots/p-$n.png"; done
  expect 0 "脚手架生成的骨架（axioms 页 + P1/P2 + 正文）直接过校验" "$tmp/scaffold/deck.html"
else
  bad "缺 scripts/scaffold.py"
fi

echo
echo "通过 $pass / 失败 $fail"
[[ $fail -eq 0 ]]
