# HTML 契约

`scripts/check_deck.py` 按本文件逐条检查。**class 名与 data-* 属性不可改名**，改了自检直接失败。

规则分两层：

- **形式层**：页数、页码、字号、翻页、离线、docx。
- **语义层**：坐标系、标注方向、公式最小集、式图绑定、页预算、动画配额、重复图。
  语义层全部是**声明式**的：脚本不认识具体学科的量，只比对页面自己的声明
  （`data-x` / `data-y` / `data-xscale` / `data-yscale` / `data-kind` / `var[data-sym]` /
  `g.dim[data-span]`）与正文说法是否自洽。

## 骨架

```html
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>LSV → Tafel 斜率 — 讲解</title>
<style>
  html, body { margin: 0; height: 100%; overflow: hidden; font-size: 21px; }
  /* 固定版式必须缩放到视口，否则右下角页码会跑出屏幕 */
  #deck { width: 1600px; height: 900px; transform: scale(var(--k, 1)); transform-origin: top left; }
  .slide { width: 1600px; height: 900px; box-sizing: border-box; position: absolute; overflow: hidden; }
  .slide:not(.active) { display: none; }
  .pg { position: absolute; right: 44px; bottom: 20px; font-size: 18px; }
  @page { size: 1600px 900px; margin: 0; }
  @media print { #deck { transform: none; } .slide { position: relative; page-break-after: always; } }
</style>
</head>
<body>
<main id="deck">

  <!-- 预备段：第 1 页公理清单（axioms），随后每条 P 一页；起点原图页顺延到第 3 页 -->
  <section class="slide active" data-page="1" data-kind="axioms" data-goal="b">
    <h1>三条定义、一条约定、一条定律</h1>
    <ol class="axioms">
      <li data-axiom="A1" data-used-in="3,5"><b>[定义]</b> <span class="eq">η ≡ E − E_eq</span><span class="note">过电位</span></li>
      <li data-axiom="A2" data-used-in="5"><b>[定律]</b> <span class="eq">j = j₀[exp(α_aFη/RT) − exp(−α_cFη/RT)]</span><span class="note">Butler–Volmer</span></li>
      <li data-axiom="A3" data-used-in="2,5"><b>[定义]</b> <span class="eq">k = Δy / Δx</span><span class="note">直线 y = kx + c 的斜率</span></li>
    </ol>
    <span class="pg">1 / 8</span>
  </section>

  <section class="slide" data-page="2" data-kind="formula" data-eq="P1">
    <h1>P1：过电位 = 实测电位 − 平衡电位</h1>
    <p class="io">吃进：E [mV]（第 3 页读得到）→ 吐出：η [mV]</p>
    <div class="formula" data-eq="P1" data-used-in="5" data-axiom="A1"
         data-stop="正文最后一次代入 η 在第 5 页取窗口两端；再往下推 α 的来源不属于本文档">
      <span class="eqno">P1</span><var data-sym="η">η</var> = <var data-sym="E">E</var> − <var data-sym="E_eq">E_eq</var>
      <span class="units">η [mV]，E、E_eq [mV vs RHE]</span>
      <details class="deriv" data-eq="P1">
        <summary>推导：P1</summary>
        <table>
          <tr><th>步骤</th><th>式子</th><th>依据</th></tr>
          <tr><td>(1.1)</td><td>η ≡ E − E_eq</td><td>A1</td></tr>
          <tr><td>(1.2)</td><td>E = 0.150 V → η = 150 mV</td><td>代数：代入本例读数</td></tr>
          <tr><td>(1.3)</td><td>失效：η &lt; 10 mV 时 ±2 mV 读数误差 &gt; 20%</td><td>误差与边界</td></tr>
        </table>
      </details>
    </div>
    <span class="pg">2 / 8</span>
  </section>

  <section class="slide" data-page="3" data-kind="origin" data-reads="E,j">
    <h1>从一条 LSV 曲线能取出两个数</h1>
    <figure class="fig" data-x="E" data-y="j" data-xscale="linear" data-yscale="linear">
      <svg viewBox="0 0 1120 520">
        <text class="ax" data-axis="x" data-sym="E">E [V vs RHE]</text>
        <text class="ax" data-axis="y" data-sym="j">j [mA/cm²]</text>
        <text data-axis="x" x="200" y="470">0.2</text>
        <text data-axis="y" x="84" y="400">25</text>
        <polyline id="p1" fill="none" stroke="#1b1b1b" stroke-width="3"/>
      </svg>
      <figcaption>起点：0.1 M KOH，1 mV/s（示例数据）</figcaption>
    </figure>
    <span class="pg">3 / 8</span>
  </section>

  <section class="slide" data-page="4" data-kind="theory">
    <h1>取数之前先定三条：动力学控制、无背景、无欧姆降</h1>
    <ul class="items"><li>每条写成「条件 → 违反后图长什么样 → 判据」</li></ul>
    <span class="pg">4 / 8</span>
  </section>

  <section class="slide" data-page="5" data-kind="calc">
    <h1>纵轴取对数后，指数关系变成一条直线</h1>
    <p class="recast">E vs RHE → η = E − E_eq；纵轴 j → log₁₀ j（刻度换成 10ⁿ）</p>
    <figure class="fig" data-x="η" data-y="j" data-xscale="linear" data-yscale="log" data-anim="dim">
      <svg viewBox="0 0 1120 520">
        <text class="ax" data-axis="x" data-sym="η">η [mV]</text>
        <text class="ax" data-axis="y" data-sym="j">log₁₀ j [mA/cm²]</text>
        <text data-axis="x" x="200" y="470">200</text>
        <text data-axis="y" x="84" y="400">10⁻¹</text>
        <g class="dim" data-span="x" data-sym="η"><text>Δη = 100 mV</text></g>
        <g class="dim" data-span="y" data-sym="j"><text>Δlog₁₀ j = 1.667 dec</text></g>
      </svg>
    </figure>
    <div class="formula" data-eq="1">
      <span class="eqno">式 (1)</span>
      <var data-sym="η">η</var> = <var data-sym="b">b</var> · log₁₀( <var data-sym="j">j</var> / <var data-sym="j0">j₀</var> )
      <span class="units">η [mV]，b [mV/dec]，j、j₀ [mA/cm²]；动力学控制（A1）</span>
      <details class="deriv" data-eq="1">
        <summary>推导：式 (1)</summary>
        <table>
          <tr><th>步骤</th><th>式子</th><th>依据</th></tr>
          <tr><td>(1.1)</td><td>j = j₀[exp(α_aFη/RT) − exp(−(1−α_a)Fη/RT)]</td><td>定义：BV 方程（起点；不引用别式编号）</td></tr>
          <tr><td>(1.2)</td><td>j ≈ j₀ exp(α_aFη/RT)</td><td>近似（写在依据列，不进 A 节）：舍掉还原项，η=150 mV 时它占 2.9×10⁻³；为什么能舍写在这里</td></tr>
          <tr><td>(1.3)</td><td>η = (RT/αF)ln(j/j₀) → η = b·log₁₀(j/j₀)</td><td>代数：取对数再换底；量纲：mV/dec</td></tr>
          <tr><td>(1.4)</td><td>log₁₀(j/j₀) = 300 mV ÷ 60 mV/dec = 5.0</td><td>代数：代入本页数（η=300 mV、b=60 mV/dec）</td></tr>
          <tr><td>(1.5)</td><td>适用：η ≫ 60 mV 且动力学控制；η &lt; 60 mV 时还原项不可忽略</td><td>误差与边界：低过电位段偏差可达 10%</td></tr>
        </table>
      </details>
    </div>
    <span class="pg">5 / 8</span>
  </section>

  <section class="slide" data-page="7" data-kind="pitfall">
    <h1>三个最容易错的地方</h1>
    <ul class="pit">
      <li><b>错误做法：</b>… <b>现象：</b>… <b>正确做法：</b>…</li>
    </ul>
    <span class="pg">7 / 8</span>
  </section>

  <section class="slide" data-page="8" data-kind="calc">
    <h1>把 b 代回同一条直线：300 mV 对应 5.0 dec</h1>
    <details class="recalc">
      <summary>数值复算</summary>
      <table>
        <tr><th>输入</th><th>计算</th><th>结果</th><th>对应</th></tr>
        <tr><td>j 0.50 → 23.2 mA/cm²</td><td>log₁₀(23.2/0.50)</td><td>1.667 dec</td><td>第 3 页</td></tr>
        <tr><td>100 ÷ 1.667</td><td>除法</td><td>60.0 mV/dec</td><td>式 (1)</td></tr>
      </table>
    </details>
    <span class="pg">8 / 8</span>
  </section>

</main>
<script>
  /* 曲线：数据数组 + 渲染函数，不要逐点内联 */
  const D = [[0, 0.5], [1, 0.63], [2, 0.79]];
  const toPoints = (data, x0, x1, y0, y1) => data.map(([x, y]) => `${x0 + x * (x1 - x0)},${y1 - y * (y1 - y0)}`).join(' ');
  document.getElementById('p1').setAttribute('points', toPoints(D, 96, 1064, 446, 58));

  const slides = [...document.querySelectorAll('.slide')];
  let current = 0;
  function show(i) { /* 见「翻页」 */ }
  addEventListener('keydown', e => {
    if (e.key === 'ArrowRight' || e.key === 'PageDown') show(current + 1);
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') show(current - 1);
  });
  addEventListener('wheel', e => show(e.deltaY > 0 ? current + 1 : current - 1), { passive: true });

  /* 视口缩放：没有它，1600×900 画布在小窗口下会把右下角页码裁掉 */
  function fit() {
    const k = Math.min(window.innerWidth / 1600, window.innerHeight / 900);
    document.documentElement.style.setProperty('--k', String(k));
  }
  addEventListener('resize', fit);
  fit();
</script>
</body>
</html>
```

## 必需结构

| 元素 | 要求 |
|---|---|
| `<section class="slide" data-page="N">` | 每页一个，N 从 1 连续递增；**页数不设上下限**（预备段长度 = 链长，正文长度 = 算例走完所需页数） |
| `data-kind` | 每页必填：`axioms`（第 1 页公理清单，仅此一页）/ `formula`（P 段）/ `origin` / `theory` / `calc` / `pitfall`（≤1 页）/ 末页为 `calc` 或 `pitfall`（**没有 summary 结论页**） |
| `<h1>` | 每页一个，非空，写结论句 |
| `<span class="pg">N / M</span>` | 每页一个，N = `data-page`，M = 总页数；画布必须缩放到视口，保证屏幕上可见 |
| `<figure class="fig" data-x data-y data-xscale data-yscale>` | 有图的页必填四个声明；`data-anim` 可选。**预备段页可以不带图** |
| `<text class="ax" data-axis="x|y" data-sym="…">量 [单位]</text>` | 每张图两个，一个 x 一个 y |
| `<text data-axis="x|y">刻度</text>` | 每个刻度标归属轴；log 轴刻度写 `10⁻¹`，不许出现 `0` |
| `<g class="dim" data-span="x|y" data-sym="…">` | 几何标注：横边只能量横轴的量；**预备段页禁用** |
| `<p class="recast">` | 换坐标（量或刻度）的那一页必须有一行，说明「旧 → 新 = 关系」 |
| `<div class="formula" data-eq="N">` | 每页 **≤1** 个；正文式号 `1…n` 连续；全篇条数**默认不设上限**（`--max-eq` 可收紧） |
| `<div class="formula" data-eq="P1" data-used-in="N" data-stop="…" data-axiom="A3">` | 预备段：`P1…Pn` 连号；`data-used-in` 指向存在的 `calc` 页；`data-stop` 写停点理由；`data-axiom` 写起点 A 号（必须是已声明的 A，且不能是自己） |
| `<p class="io">吃进：… → 吐出：…</p>` | **每个 P 页必有**：输入量 + 从第几页读、输出量 + 单位 |
| `<section data-kind="axioms" data-goal="b">` | 第 1 页公理清单页：不挂 `data-eq`、不挂推导；`data-goal` 声明本文档的终点量（A 节不许出现它） |
| `<li data-axiom="A1" data-used-in="5,7"><b>[定义]</b> <span class="eq">…</span><span class="note">…</span></li>` | 每条公理：标签只许 `[定义]/[约定]/[定律]/[经验事实]`；`data-used-in` 可多值（逗号分隔），未被任何页用到 = 冗余 |
| `<var data-sym="…">` | 公式里每个符号都要标；每式 ≥2 个 |
| `<details class="deriv" data-eq="N">` | **每条公式同页必有**：≥3 步；依据落到「定义/公理 A1/代数/量纲/误差」；必须有一行数值代入；必须写误差/失效边界；首末查量纲 |
| `<details class="recalc">` | 全篇 1 个：≥3 行「输入 / 计算 / 结果 / 对应」，覆盖幻灯片上所有带单位数字 |
| 曲线 | 数据数组 + 渲染函数；单条 `points` ≤2400 字符，整份 HTML ≤320KB |

**没有** docx、没有例题页、没有自测题。

## 公式预备段契约（八条）

预备段是全篇最前面的一段：第 1 页公理清单，随后每条 P 一页。下面八条是契约正文，不是注释。

1. **`data-kind` 允许集**：`axioms` / `formula` / `origin` / `theory` / `calc` / `pitfall`。
   第 1 页必须是 `axioms`（公理清单，不挂 `data-eq`、不挂 deriv）；`formula` 从第 2 页起连续到起点原图页之前；
   `origin` 只剩一页，且必须紧跟在预备段之后。预备段页数 = 1（`axioms`）+ P 条数（+ 各自的续页）。
2. **`data-eq="P*"`**：预备段式号写 `P1`、`P2`…（`<section data-eq="P1">` 与
   `<div class="formula" data-eq="P1">` 同号）；正文式号仍是 `1`、`2`…。**两套号永不复用**：
   正文引用预备式只写「P2」，不许写「式 (P2)」。P 号从 1 连号；一条 P 一页，续页用
   `<details class="deriv" data-eq="P1" data-part="2">`（同号 + 递增分片号），不许重开公式。
3. **`data-used-in="N"`**：这条 P 在正文第几页被用。N 必须是存在的 `calc` 页，且该页真的引用它
   （页面 `data-uses="P3"`，或正文出现 `P3`）。查不到 → 预备段冗余。
4. **`data-stop="…"`**：停点理由——为什么推到这一式就不再往下（正文最后一次代入它在哪一页）。
   空着视为没写。
5. **`data-axiom="A3"`**：这条链的起点 A 号，必须在第 1 页公理清单里存在；该 A 编号还要在推导里
   至少出现一次。答不出起点 → 不许进预备段。
6. **`.io` 行**：每个 P 页必须有 `<p class="io">吃进：E [mV]（第 3 页读得到）→ 吐出：η [mV]</p>`。
   预备段可以不带图；不带图时，「进/出」就靠这一行交代。「式里的量必须在图上指得到」只管正文页。
7. **公理清单节 + 预备段禁动画**：第 1 页用
   `<section data-kind="axioms" data-goal="b"><ol class="axioms"><li data-axiom="A1" data-used-in="5,7"><b>[定义]</b>
   <span class="eq">…</span><span class="note">…</span></li></ol></section>`；
   标签只许 `[定义]` / `[约定]` / `[定律]` / `[经验事实]`；近似写进引用它的那一步的「依据」列，不进 A 节；
   终点量（`data-goal`）不许出现在 A 节任何一条的 LHS；A 的 RHS 不许以另一条 A 的 LHS 开头。
   预备段**禁动画、禁高亮带（`g.dim`）、禁滑块**；第 1 页连强调色块都不加。
8. **定义不推导**：定义 / 约定 / 纯换算式不占 P 号。P 的式子归一化后等于某条 A → error；
   `deriv` <3 步、或真实变换（取对数 / 近似 / 相减 / 与 A 对照定系数）<2 步 → error。
   预备段允许只有 1 条 P。

## 语义层规则（脚本逐条查）

| 编号 | 规则 | 触发错误的样子 |
|---|---|---|
| R0 | 1600×900 画布必须缩放到视口（`transform: scale` / `zoom` + resize 监听），`.pg` 不许被隐藏 | 页码元素在，但小窗口下右下角被裁掉，屏幕上根本看不见 |
| R1 | 页码齐，且 `pg` 的 N/M 与页序、总页数一致 | 忘了放页码；页码写死成 `4 / 12` |
| R2 | 每图两轴声明齐全；log 轴标签必须含 `log₁₀`，线性轴标签不许含 log；轴标签的「量」必须等于 `data-x`/`data-y` | 横轴已换成 η，标签却还是 `E vs RHE [V]` |
| R2′ | log 轴的刻度必须写成 10ⁿ 且不含 0；线性轴不许出现 10ⁿ | 换了对数刻度，刻度还是 `0,10,20` |
| R3 | 换坐标（量或刻度）的那页必须有 `recast`，且图内不许残留旧量名 | 图注还写着 `E 0–0.4 V vs RHE` |
| R4 | `data-span="x"` 的标注量名 = `data-x`；`y` 同理 | x 轴是 η、y 轴是 log j，却把 Δlog j 画成横边 |
| R5 | 正文式号 `1…n` 连续（默认不设条数上限）；两条正文式的 LHS 不许相同；P 号另成一套、从 P1 连号 | `log₁₀ j₀ = log₁₀ j − η/b` 给单独式号；正文与预备段混号 |
| R6 | 出现「变平 / 弯曲 / 偏离直线 / 拐点 / 线性区」的页，纵轴必须是 log | 线性 LSV 图上写「0.26 V 之后变平」 |
| R7 | 式里 ≥2 个 `data-sym`；**正文页**至少一个出现在本页图上（预备段页不要求）；讲「补偿/外推/换算/校正」的页必须有式 | 讲 iR 补偿却只写字、不给 `E_meas = η_kin + R_u·j` |
| R8 | 起点页不许有 `data-anim`、`.dim` 标注；预备段**所有**页都不许（见 C3） | 首页就叠高亮带和拟合线 |
| R9 | 动画页 ≤3、同种动画只用一次、错例页不许有动画 | 第 6 页 slider 与第 8 页又是同一段滑动 |
| R10 | 两页的图不许几乎相同（去掉公共骨架后相似度 <0.9） | 用同一张拟合图解释另一件事 |
| R11 | 页角色合规（S1/S2/S3）：第 1 页是 `axioms`、P 段从第 2 页起连续、`origin` 紧跟其后且只有一页、`theory` 排在第一个 `calc` 之前、`calc` ≥ 正文页一半、`pitfall` ≤1 页、末页是 calc/pitfall；错例文字不许出现在推导页 | 先算 4 页，最后才补一条「其实要满足三个条件」；把原图页留在第 1 页 |
| D1 | 每条 `data-eq` 同页必须有 `details.deriv`：≥3 步；每行依据落到具体来源；非基线式写「由式 (N)」；有一行数值代入；有一行误差/失效边界；引用假设编号；首末两式查量纲 | 推导只写「定义 / 代数 / 量纲」三行，读者不知道这式怎么来的、怎么落到本页的数 |
| D2 | 全篇必须有 `details.recalc`：≥3 行，幻灯片上带单位的数字都能找到出处 | 近似式写的和数值算的对不上（如还原项比值写了错的量级） |
| D3 | 不许出现「自测 / 例题 / 习题」；末页必须是 `calc` / `pitfall` | 末页挂一道小结 |
| C1 | 孤儿符号闭包：`calc` 页每个 `<var data-sym="X">` 必须属于某条 P 式的 LHS/RHS，或 `origin_reads`（`outline.json` 的 `origin_reads` ∪ `origin` 页的 `data-reads`） | 第 5 页冒出 `E₀`，预备段里从没定义过 |
| C2 | 每条 P 的 `data-used-in="N"`：N 存在、`data-kind="calc"`、且该页真的引用它 | 声明用于第 7 页，第 7 页只写「按斜率算」 |
| C3 | 第 1 页 `data-kind="formula"`；预备段每页 ≤1 式；P 号连号；预备段无动画/高亮带/滑块；每条 P 有非空 `data-stop` 与 `.io`；禁「式 (P2)」写法 | 第 1 页还是原图；P 页放了一个高亮带 |
| C4 | 每条 P 的 deriv 首步依据命中文首 A 编号或「定义」；之后每步只取 A 编号/代数/量纲/近似及条件；推导里至少一次 A 编号；全文无「由式/由上可知/显然/易得/已知结论」 | P3 首步依据写「Tafel 方程」——推论当公理 |
| C5 | 每条 A 带 `[定义]/[约定]/[定律]/[经验事实]` 之一；无 `[教科书结论]/[已知结论]`；A 节内无近似；`data-used-in` 页真的引用它 | A4 写「η 较大时可略还原项」；A5 谁都没引用 |
| C6 | 标题 / lead / 正文 / 列表出现元话语黑名单词 | 首页标题「开讲前先钉死五条」 |
| C7 | P 段准入：P 是某条 A 的重述；推导照抄公理 ≥2 行；<3 步或真实变换 <2 步 | 把 η ≡ E − E_eq 立成 P1 |
| C8 | A 节收进终点量；A 之间互推；`[约定]` 里写「实测」 | A5 写成 `b ≡ 直线斜率` |
| C12 | 分式一律二维：`<mo>/</mo>` 只许夹在两侧都是量纲文本之间（`<mtext>mA</mtext>`、`<msup><mtext>cm</mtext><mn>2</mn></msup>`）；`<mfrac>` 的分子分母不许都是量纲词；`<mfrac>` 后面不许紧跟操作数（分母只框一个 token） | `mA/cm²` 写成 `<mfrac>`；`RT/α_aF` 写成 `\frac{RT}{α}_aF`（分母只框了 α） |

## CSS 硬要求

- `html, body { height: 100%; overflow: hidden; }`，`main#deck { height: 100vh; }`
- 单页单屏：`.slide { height: 100vh; display: flex; … }`，任何 `.slide` 内不出现滚动
- 正文 `font-size ≥ 20px`（1600×900 基准），其它文字不得 `< 18px`（页码也一样）
- `@media print { … }`：每页一屏、`page-break-after: always`
- 层级 ≤3（h1 / 正文 / 注释）

## 翻页

```js
addEventListener('keydown', e => {
  if (e.key === 'ArrowRight' || e.key === 'PageDown') go(+1);
  if (e.key === 'ArrowLeft'  || e.key === 'PageUp')   go(-1);
});
addEventListener('wheel', e => go(e.deltaY > 0 ? +1 : -1), { passive: true });
```

## 自检脚本查什么

| 检查 | 级别 |
|---|---|
| `data-page` 连续（页数不设上下限） | error |
| 没有视口缩放 / 没有 resize 监听 / `.pg` 被 display:none | error |
| 出现「自测 / 例题 / 习题」；末页不是 `calc` / `pitfall` | error |
| 公式缺同页 `details.deriv`；推导少于 3 步 / 缺依据列 / 依据空泛（只写「代数」） | error |
| 推导没有数值代入行；推导没写误差或失效边界 | error |
| 首末两式的推导里没有量纲检查 | error |
| 缺 `details.recalc`；复算表 <3 行 | error |
| 每页有非空 `<h1>`、有 `.pg` 且页码对 | error |
| 标题含「介绍/概述/小结/总结/谢谢/欢迎提问/目录」 | error |
| 全文出现「谢谢观看 / 欢迎提问 / 你学到了什么 / Q&A」 | error |
| 推导链「两边取对数 / 代入整理得 / 移项得」 | error |
| 正文 `data-eq` 不连续，或某页 >1 条；P 号不连号；一条 P 拆成两页 | error |
| 公式 LHS 重复（移项另编号） | error |
| C12 分式不是 `<mfrac>`（真分式写成斜杠）；`<mo>/</mo>` 两侧不是量纲词；量纲词（mA/cm²、mV/dec）被排成 `<mfrac>`；`<mfrac>` 后面紧跟操作数（分母只框一个 token） | error |
| 公式符号与图无交集 / 式内符号少于 2 个 | error |
| 讲补偿/外推/换算却没给式 | error |
| 图缺 `data-x`/`data-y`，轴标签缺失或与声明不符 | error |
| log 轴标签缺 `log₁₀`、含「（对数）」；线性轴标签含 log | error |
| 刻度未标 `data-axis`；log 轴出现 0 或非 10ⁿ 刻度 | error |
| 换坐标没写 `recast`，或图内残留旧量名 | error |
| Δ 标注方向与轴不符 / 缺 `data-span` | error |
| 现象词出现在非 log 纵轴的页 | error |
| 起点页带 `data-anim` 或 `.dim`；预备段任意页带动画/高亮带/滑块 | error |
| 动画页 >3、同种动画重复、错例页带 `data-anim` | error |
| 两页的图几乎相同 | error |
| 页角色缺失、`origin` 不在预备段之后、条件页不在计算之前、`calc` 占正文不足一半 | error |
| 错例页 >1，或推导页里出现「错误做法」 | error |
| 外部资源（`http(s)://` 的 src/href/@import、CDN） | error |
| 缺 `overflow: hidden` / `100vh` / 翻页监听 | error |
| 正文 `font-size < 20px`，其它 `< 18px` | error / warn |
| 易错点三段式不足 3 组 | error |
| 末页 `<details>` < 3 | error |
| 单条 `points` 超 2400 字符 / HTML 超 320KB | warn |
| 幻灯片上的数字在复算表里找不到 | warn |
| 某页图没有专属视觉元素 | warn |
| C1 孤儿符号：`calc` 页出现预备段没定义的 `<var data-sym>` | error |
| C2 每条 P 的 `data-used-in` 指向的页不存在 / 不是 calc / 没引用它 | error |
| C3 第 1 页不是 formula；预备段 >1 式；缺 `data-stop`；缺 `.io`；出现「式 (P2)」 | error |
| C4 P 推导首步依据不是 A 编号/定义；每步依据超出允许集；推导无 A 编号；全文出现「由式/由上可知/显然/易得/已知结论」 | error |
| C5 公理缺标签 / 用了禁用标签 / A 节内有近似 / `data-used-in` 的页没引用它 | error |
| C6 标题 / lead / 正文出现元话语（开讲前、本文档、为了讲清楚、本节只、后面会…） | error |
| C7 P 是 A 的重述 / 推导照抄公理 ≥2 行 / 步数 <3 / 真实变换 <2 | error |
| C8 A 的 LHS 是终点量 / A 的 RHS 以另一条 A 的 LHS 开头 / [约定] 里写「实测」 | error / warn |
| C9 缺 `DeckMath` / `DeckText` 的 `@font-face`、没内嵌 `url(data:font/woff2;base64,…)`、`.formula .expr` 没用 `var(--math)`、`body` 没用 `var(--text)` | error |
| C10 `var(--math)` 出现在纯数学选择器之外；公式/正文字符不在子集 cmap；块级元素带 rotate/skew；公式里用 `<sub>/<sup>` | error |
| C9 公式区里出现 `E_eq` 这类下划线写法（没排成 `<sub>`） | warn |
| C10 复算表与图同页且行数 > 8（展开必溢出）/ 无图页 > 14 行 | error / warn |
| `shots/` 缺 `deck-print.pdf` 或抽查截图 <3 张 | warn |

`data:image/...` 内联图片是**允许且推荐**的（单文件要求）；外链图片不允许。

## 常见失败

- 用 CDN 的 MathJax / Chart.js → 断网就白屏，直接 error
- 每页 `min-height: 100vh` + `overflow: auto` → 出滚动条
- 公式用 `<img src="https://…">` → 外链
- 把推导写进 `<div class="note">` 小字 → 内容检查抓不到，但验收 H 人工会抓
- 复制上一页的 SVG 只改文字 → 视觉增量检查（R10）会抓到
- 页码写了但没做缩放 → R0 抓到（这是实测踩过的坑：`.pg` 在，屏幕上看不见）
- 曲线逐点内联 → 体积告警，改数要重写整块 SVG
- 换了坐标只改曲线 → 轴标签、刻度、图注、正文量名要一起改（R2/R2′/R3）
- 公式排在系统字体里、`E_eq` 当下标 → 看起来像代码不像式子（C9）
- 复算表和图挤一页 → 屏幕上点开「数值复算」，下半截被 `overflow:hidden` 裁掉（C10 +
  `shoot_deck.py` 展开态测量）

## 公式渲染契约（Presentation MathML + 文字手写）

```css
@font-face { font-family: "DeckMath"; src: url(data:font/woff2;base64,…) format("woff2"); }
@font-face { font-family: "DeckText"; src: url(data:font/woff2;base64,…) format("woff2"); }
:root { --math: "DeckMath", "Latin Modern Math", serif; --text: "DeckText", "LXGW WenKai", serif; }
body { font-family: var(--text); }                    /* 正文：手写体 */
.formula .expr { border: 1px solid #0f1115; padding: 9px 10px;
                 font-family: var(--math); white-space: nowrap; }   /* 公式：数学衬线 + 1px 方框 */
math { font-family: var(--math); font-size: 1em; line-height: 1.25; }  /* 公式主体是 <math> */
math mtext { font-family: var(--text); font-size: .92em; }            /* 中文注释/单位词走手写体 */
```

- **公式**：一行 DSL → `scripts/mathrender.py` → `<math>`（Presentation MathML）；变量进 `<mi>`
  （数学斜体由 Latin Modern Math 的 MATH 表挑字形）、数字进 `<mn>`、运算符/关系符进 `<mo>`、
  上下标进 `<msub>/<msup>/<msubsup>`、分式 `<mfrac>`、根式 `<msqrt>`、中文注释与单位词进 `<mtext>`。
  **不许用 `<sub>/<sup>`、`_` 拼接或 `.mth`/`.scr` 定位 span**（C9/C10，脚本 error）。
- **分式一律二维（C12，脚本 error）**：斜杠两侧**各是一个完整式子**（变量/数字/乘积链/括号整组/
  函数作用/幂或根式）时，必须写成 `<mfrac>`；斜杠**只留给量纲写法**——两侧都是单位词
  （`<mtext>mA</mtext>` / `<msup><mtext>cm</mtext><mn>2</mn></msup>`），可带数字前缀（`59.2 mV/dec`）。
  DSL 里写 `a/b` 就自动排成 `<mfrac>`（`\frac{分子}{分母}` 也认），不需要人事后补。
  **分母是整组**：`Δη/Δlog₁₀ j` 的分母是整个 `Δlog₁₀ j`（`j` 不能掉在外面），`RT/α_aF` 的分母是
  `α_aF` 整体；解析器按「斜杠后到加减/关系符/括号/中文注释为止」切项，所以不必额外加 `{}`。
  反例：`mA/cm²` 排成 `<mfrac>`、`j/j₀` 用 `<mo>/</mo>`、`\frac{RT}{α}_aF`（分母只框一个 token）。
  量纲词表只有一份（`mathrender.UNITS` / `SINGLE_UNITS`），`check_deck.py` 直接引用。
- **一个公式实例 = 一个 `<math>`**：`.expr`、公理 `.eq`、推导表式子列每格都只有一个 `<math>`，
  `<math>` 之外只剩式号与单位行。散文里含 Unicode 上下标的词由 `scaffold.subs()` 自动转成行内 `<math>`。
- **方框**：白底、1px `#0f1115`、内边距 9–10px、无旋转、无下划线、无底色（参考图口径）。
- **文字**：`body` 必须 `var(--text)`（手写体），标题/正文/图注/表格文字全部继承，不许退回无衬线。
- **两套字体都必须内嵌**：`DeckMath`（`scripts/assets/mathfont.css`，Latin Modern Math 子集）
  与 `DeckText`（按 deck 字符集现场子集化，`scaffold.embed_text_font`）。
  子集内部 name 分别是 `DeckMath` / `DeckText`，否则 `pdffonts` 与平台字体 API 分不清内嵌与回退。
- **字符集必须含空格 U+0020** 与 CSS 伪元素 `content` 里的字符（`•`、`——`）：缺了会回退系统字体。
- **字形覆盖**：`<math>` 里除 `<mtext>` 外的字符 ⊆ DeckMath 的 cmap；`<mtext>` 与每页可见文字
  ⊆ DeckText 的 cmap（脚本逐字核对）。
- **打印**：`tools/shoot_deck.py` 用浏览器打印生成 `deck-print.pdf`（屏幕态与 PDF 同引擎）。
  **weasyprint 不支持 MathML**（实测 70.0：上下标拍平、分式塌成一行），所以它既不是打印源，
  也不能用作观感对照——只剩页数交叉验证。它的 SVG text 同样不走 `@font-face`。
- 验收：`python3 tools/measure_deck.py <html> --fonts`（公式只报 DeckMath、正文只报 DeckText）、
  `pdffonts shots/deck-print.pdf`（只有 DeckText / DeckMath）。

## 展开态契约（折叠块的空间预算）

屏幕态 `details` 折叠，`overflow: hidden` 于 `.slide`——**一展开就顶出 900px，直接被裁掉**。
契约要求：

- 任一页把全部 `details` 打开后，`scrollHeight - clientHeight ≤ 1px`；
- 复算表单独成页（无图），>14 行拆 `data-part`；单独成页时加 `open`（默认展开），否则末页是空白页；
  推导块同页有图时步数 ≤6，否则续页；
- 验收：`python3 tools/shoot_deck.py <html>` 会逐页开 `details` 再量一次，
  并核对 `pdfinfo` 的页数 == 幻灯片页数。

真实翻车案例（含错误片段与改法）见 `references/anti-patterns.md`。
