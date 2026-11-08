# Knowledge Point Slides

把一个知识点讲成 **单文件 HTML 幻灯片**（开讲前先把要用的公式从公理一步一次变换推一遍，推导折叠在公式旁边、可续页，无结论页）。
听完的人要能做到「能取 / 能算 / 能判 / 能反推」，而不是知道一个名词。
**不产 docx，不出例题/自测页；页数不设上下限（预备段长度 = 链长）。**

## 使用

放在 `.pi/skills/knowledge-point-slides/`，Pi 自动发现；改完 `/reload`，或 `/skill:knowledge-point-slides` 强制触发。

```text
/skill:knowledge-point-slides 讲清「怎么从 LSV 曲线取 Tafel 斜率」，听众是研一学生，
手上有 0.1 M KOH、1 mV/s 的一条 LSV（E: 0–0.4 V vs RHE，j: 0–50 mA/cm²），
要能自己算出 60 mV/dec 这个数。
```

## 三道闸门

| 闸门 | 只允许输出 | 为什么要卡 |
|---|---|---|
| 1 | 5 行：起点（含预备段 P 条数）/ 终点 / 听众缺 / 贯穿算例 / 最易错一步 | 这五项任一错，后面每页全废 |
| 2 | outline 表（含页角色）+ 坐标表 + **公理表** + **公式预备表** + 正文公式表，**一次给全** | 逼出「每页一个视觉增量」；公理与坐标先声明，漏改标签、推论当公理都会被抓；合并是为了少一轮等待 |
| 3 | HTML + 截图 + 交付说明，`check_deck.py` 全绿 | 把验收从「人眼看」变成可执行 |

## 交付物

```text
work/<slug>/
├── <slug>.html                # 单文件，推导折叠在 details.deriv 里
├── shots/deck-print.pdf       # 整份打印件
├── shots/p-0N.png             # 抽查 ≥3 页
└── <slug>-交付说明.md         # A–M 勾选 + 没做到的事
```

## 脚本

```bash
# ① 先生成契约合规的骨架（页码、视口缩放、坐标声明、推导块、翻页全生成好）
python3 scripts/scaffold.py work/<slug>/outline.json work/<slug>/<slug>.html

# ② 填完内容后自检：形式层 + 语义层 + 公式预备段 C1–C5 + 推导/复算/页码可见性
python3 scripts/check_deck.py work/<slug>/<slug>.html
# 公式手写体子集（只需跑一次；换字体或缺字形时重跑）
python3 scripts/make_handfont.py
# 展开态 + 打印页数（屏幕折叠看不出溢出的那块，只能真浏览器量）
python3 tools/shoot_deck.py work/<slug>/<slug>.html

# 自测：好样本 + 脚手架产物必须过，每类硬规则各造一个坏样本必须挂
bash tests/smoke.sh

# 可选：确实还需要 Word 版推导时（默认不产 docx）
python3 scripts/md2docx.py 推导.md 推导.docx
bash scripts/get_pandoc.sh
```

## 依赖

| 依赖 | 用途 | 获取方式 |
|---|---|---|
| pandoc | LaTeX → Word 原生公式 | `bash scripts/get_pandoc.sh`（装到所在项目的 `tools/pandoc/`） |
| python-docx | pandoc 缺失时的降级后端 | `pip install python-docx`（已装则跳过） |

本技能不依赖 PyYAML 等外部工具，拷贝到任何项目的 `.pi/skills/` 即可用（本仓库里它就是唯一维护地，直接改）。

## 与其他技能的分工

- `paper-to-cn-slides`：英文论文 → 中文汇报 slides（读 PDF、抽 Figure）
- 本技能：一个知识点 → 讲解 slides（自造算例、手写 SVG、必须产推导 docx）

## 参考

- `references/deck-contract.md`：HTML 骨架、`data-*` 契约与 `check_deck.py` 的检查项
- `references/checklist.md`：验收 A–M 细则与打勾模板
- `references/anti-patterns.md`：实测踩过的 11 个坑（错 → 错在哪 → 哪条规则拦 → 怎么改）

## 变更记录

- 初始版本：四道闸门 + 白名单动画 + 公式/推导分离 + 可执行自检
- 由一份单段式 prompt 模板转化；保留原模板的验收 A–I 条款
- 第三次收紧（公式讲解太简略的反馈）：
  - 推导块从「≥2 步 + 依据列」升级为**五件事**：由哪条式变来 / 这一步做什么 /
    为什么可以这么做 / 代入本页的数 / 误差与失效边界
  - `check_deck.py`：≥3 步、必须有数值代入行、必须写误差/失效边界，全部 error
    （第三次修订把「必须写由式 (N)」反过来禁掉了，见下）
  - 新增反例 #14（推导只写定义/代数）、#15（引用的关系没编号）
- 第二次收紧（用户实测反馈）：
  - **取消 docx**：推导改成公式旁的 `details.deriv`，数值复算改成 `details.recalc`
  - **取消末页例题/自测**：末页固定 `data-kind="summary"` 结论页（**第三次修订又取消了 summary，见下**）
  - **页码必须看得见**：固定 1600×900 画布必须 `transform: scale` + resize 监听（只查元素存在不够）
  - **闸门 2+3 合并**成一次「outline + 坐标表 + 公式表」，少一轮等待
  - 新增 `scripts/scaffold.py`：从 outline.json 生成契约合规骨架
  - 图改用「数据数组 + 渲染函数」，超 320KB 或单条 points >2400 字符告警
  - 截图从「逐页 PNG」改成「整份 PDF + ≥3 张抽查」
- 第三次修订（用户要求）：
  - **推导不许解释符号**：「其中 … 为 …」「… 分别表示 …」「符号说明」一律 error；
    符号含义只写在公式的 `var[data-sym]` 与单位行里
  - **推导不许用「由式 (N) 得」**：必须从定义 / 物理前提 / 实验事实重新写这一步的因果链；
    脚本把「由式」「由 (N.k)」列为 error
  - **一页写不下就续页**：`details.deriv[data-eq=N][data-part=2]`，第 1 片与公式同页，
    续页必须是 `calc`，分片号连续；页数上限 10 → 14
  - **取消结论页**：`summary` 从 `KINDS` 移除，末页必须是 `calc` / `pitfall`，
    末页标题含「结论 / 小结 / 总结 / 综上 / 回顾」即 error
  - `tests/smoke.sh`：新增 6 个用例（由式、符号释义、分片不连续、续页不是 calc、末页结论、末页 kind），并反转旧的两条
- 第一次实测后收紧（见 `references/anti-patterns.md`）：
  - 图升级为「声明式坐标系契约」：`data-x/data-y/data-xscale/data-yscale`、`text.ax`、
    刻度 `data-axis`、Δ 标注 `data-span`、换坐标必须写 `recast`
  - 公式升级为「最小集 + 式图绑定」：全篇 ≤3 条、LHS 不重复、每个符号 `var[data-sym]`
    且图上指得到、讲补偿/外推/换算的页必须有定义式
  - 新增页预算：`data-kind` + 条件页在计算之前 + 错例 ≤1 页 + 动画 ≤3 且不重复
  - 新增可见页码、重复图检测；页数收到 8–10（第三次修订放宽到 8–14）
  - docx 强制「数值复算」表 + 单参数贯穿
  - `check_deck.py` 新增 11 类语义检查（全部 error）；`tests/smoke.sh` 扩到 34 个用例
