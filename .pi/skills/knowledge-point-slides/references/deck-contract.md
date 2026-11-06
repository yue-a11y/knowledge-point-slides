# HTML 契约

`scripts/check_deck.py` 按本文件逐条检查。**class 名与 data-* 属性不可改名**，改了自检直接失败。

## 骨架

```html
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>LSV → Tafel 斜率 — 讲解</title>
<style>
  /* 见「CSS 硬要求」 */
</style>
</head>
<body>
<main id="deck">

  <section class="slide" data-page="1">
    <h1>从一条 LSV 曲线能取出几个数</h1>
    <figure class="fig">
      <svg viewBox="0 0 800 450">…</svg>
      <figcaption>起点：0.1 M KOH，1 mV/s，η 0–400 mV</figcaption>
    </figure>
    <div class="formula" data-eq="1">
      η = E − E<sub>eq</sub>  <span class="units">[mV]</span>
    </div>
  </section>

  <section class="slide" data-page="2">…</section>
  …

  <section class="slide" data-page="12">
    <h1>自测</h1>
    <details><summary>1. 计算：η = 300 mV 时 j 是多少？</summary><p>…</p></details>
    <details><summary>2. 判断：下面两张图哪张取错了区间？</summary><p>…</p></details>
    <details><summary>3. 解释：斜率从 60 变 40 意味着什么？</summary><p>…</p></details>
  </section>

</main>
<script>
  /* 见「翻页」 */
</script>
</body>
</html>
```

## 必需结构

| 元素 | 要求 |
|---|---|
| `<section class="slide" data-page="N">` | 每页一个，N 从 1 连续递增，共 **8–12** 页 |
| `<h1>` | 每页一个，非空，写结论句 |
| `<div class="formula" data-eq="N">` | 每页 **≤1** 个，N 全篇从 1 连续递增 |
| `<details>` | 末页 ≥3 个，用于折叠答案 |
| 易错点 | 正文出现「错误做法」「现象」「正确做法」各 ≥3 次 |

## CSS 硬要求

- `html, body { height: 100%; overflow: hidden; }`，`main#deck { height: 100vh; }`
- 单页单屏：`.slide { height: 100vh; display: flex; … }`，任何 `.slide` 内不出现滚动
- 正文 `font-size ≥ 20px`（1600×900 基准），其它文字不得 `< 18px`
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
| 页数 8–12、`data-page` 连续 | error |
| 每页有非空 `<h1>` | error |
| 标题含「介绍/概述/小结/总结/谢谢/欢迎提问/目录」 | error |
| 全文出现「谢谢观看 / 欢迎提问 / 你学到了什么 / Q&A」 | error |
| 推导链「两边取对数 / 代入整理得 / 移项得」 | error |
| `data-eq` 不连续，或某页 >1 条公式 | error |
| 外部资源（`http(s)://` 的 src/href/@import、CDN） | error |
| 缺 `overflow: hidden` / `100vh` / 翻页监听 | error |
| 正文 `font-size < 20px`，其它 `< 18px` | error / warn |
| 易错点三段式不足 3 组 | error |
| 末页 `<details>` < 3 | error |
| 同级目录缺 `<slug>-公式推导.docx` | error |
| docx 里式号与 HTML `data-eq` 不一致 | error |
| `shots/` 缺页或数量与页数不符 | warn |

`data:image/...` 内联图片是**允许且推荐**的（单文件要求）；外链图片不允许。

## 常见失败

- 用 CDN 的 MathJax / Chart.js → 断网就白屏，直接 error
- 每页 `min-height: 100vh` + `overflow: auto` → 出滚动条
- 公式用 `<img src="https://…">` → 外链
- 把推导写进 `<div class="note">` 小字 → 内容检查抓不到，但验收 H 人工会抓
