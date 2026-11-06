# Knowledge Point Slides

把一个知识点讲成 **HTML 版幻灯片**（单文件 HTML + 公式推导 docx）。
听完的人要能做到「能取 / 能算 / 能判 / 能反推」，而不是知道一个名词。

## 使用

放在 `.pi/skills/knowledge-point-slides/`，Pi 自动发现；改完 `/reload`，或 `/skill:knowledge-point-slides` 强制触发。

```text
/skill:knowledge-point-slides 讲清「怎么从 LSV 曲线取 Tafel 斜率」，听众是研一学生，
手上有 0.1 M KOH、1 mV/s 的一条 LSV（E: 0–0.4 V vs RHE，j: 0–50 mA/cm²），
要能自己算出 60 mV/dec 这个数。
```

## 四道闸门

| 闸门 | 只允许输出 | 为什么要卡 |
|---|---|---|
| 1 | 5 行：起点 / 终点 / 听众缺 / 贯穿算例 / 最易错一步 | 这五项任一错，后面 12 页全废 |
| 2 | outline 表（8–12 行，四列固定） | 逼出「每页一个视觉增量」，拦住凑页 |
| 3 | 视觉与动画计划 + 公式清单 | 动画只准四类；公式先编号，防止铺推导 |
| 4 | HTML + docx + 交付说明，`check_deck.py` 全绿 | 把验收从「人眼看」变成可执行 |

## 交付物

```text
work/<slug>/
├── <slug>.html                # 单文件，无外网依赖
├── <slug>-公式推导.docx       # 与幻灯片同批，式号一一对应
├── shots/p01.png …            # 每页缩略截图
└── <slug>-交付说明.md         # A–I 勾选 + 没做到的事
```

## 脚本

```bash
# 交付自检（页数/标题/禁用词/公式编号/离线/字号/翻页/易错点/自测/docx/截图）
python3 scripts/check_deck.py work/<slug>/<slug>.html

# markdown + LaTeX → Word（自动用项目内 pandoc）
python3 scripts/md2docx.py work/<slug>/<slug>-公式推导.md work/<slug>/<slug>-公式推导.docx

# 重装 pandoc（项目内 tools/pandoc/，不碰系统）
bash scripts/get_pandoc.sh
```

## 依赖

| 依赖 | 用途 | 获取方式 |
|---|---|---|
| pandoc | LaTeX → Word 原生公式 | `bash scripts/get_pandoc.sh`（装到所在项目的 `tools/pandoc/`） |
| python-docx | pandoc 缺失时的降级后端 | `pip install python-docx`（已装则跳过） |

本技能不依赖 PyYAML 等工坊内部工具，拷贝到任何项目的 `.pi/skills/` 即可用。

## 与其他技能的分工

- `paper-to-cn-slides`：英文论文 → 中文汇报 slides（读 PDF、抽 Figure）
- 本技能：一个知识点 → 讲解 slides（自造算例、手写 SVG、必须产推导 docx）

## 参考

- `references/deck-contract.md`：HTML 骨架与 `check_deck.py` 的检查项
- `references/checklist.md`：验收 A–I 细则与打勾模板

## 变更记录

- 初始版本：四道闸门 + 白名单动画 + 公式/推导分离 + 可执行自检
- 由一份单段式 prompt 模板转化；保留原模板的验收 A–I 条款
