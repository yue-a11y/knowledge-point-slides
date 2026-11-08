# knowledge-point-slides — 应用项目

用 `knowledge-point-slides` 技能做**知识点讲解 HTML 幻灯片**（单文件，推导折叠在公式旁边，无 docx）。

技能本体就在 `.pi/skills/knowledge-point-slides/`，**直接在这里改、在这里用**（改完 `/reload`）。
工坊已删除，没有 export / rsync 同步链，也不要再引入第二份副本。

## 启动

```bash
cd ~/pi-workspaces/knowledge-point-slides
pi            # 首次会问 project trust，必须批准，否则技能不加载
```

## 触发

```text
/skill:knowledge-point-slides 讲清「怎么从 LSV 曲线取 Tafel 斜率」，听众研一，
手上有 0.1 M KOH、1 mV/s 的 LSV（E 0–0.4 V vs RHE，j 0–50 mA/cm²），要能自己算出 60 mV/dec。
```

或者直接用自然语言（`description` 能被路由到才算写对）：

```text
帮我做个讲解 PPT，讲清 Tafel 斜率怎么取，听众是研一学生……
```

技能会先只回 5 行（起点（含预备段 P 条数）/ 终点 / 听众缺 / 贯穿算例 / 最易错一步），
确认后一次给五张表（outline + 坐标 + 公理 + 公式预备 + 正文公式），最后才产出文件。
**别催它跳阶段**，闸门是这个技能的核心。

## 产物

```text
work/<slug>/
├── <slug>.html                # 单文件，断网可用，Ctrl+P 导 PDF
├── <slug>.py                  # 构建脚本：数字与曲线都由它算，不手写
├── outline.json               # 闸门 2 的五张表（goal / axioms / formula / origin_reads）
├── shots/deck-print.pdf       # 整份打印件（页数必须 = 幻灯片页数）
├── shots/p-01.png …           # 抽查截图
└── <slug>-交付说明.md         # 验收 A–S 勾选 + 没做到的事
```

交付前自检：

```bash
python3 .pi/skills/knowledge-point-slides/scripts/check_deck.py work/<slug>/<slug>.html   # 退出码必须 0
bash .pi/skills/knowledge-point-slides/tests/smoke.sh                                    # 通过 77 / 失败 0
```

## 环境

| 项 | 状态 |
|---|---|
| chrome-headless-shell | `~/.local/bin/chrome-headless-shell` → `~/.cache/pi-chrome/…`，`tools/shoot_deck.py` 用它出 PNG/PDF |
| weasyprint | 交叉验证打印态页数（`weasyprint -p <deck>.html shots/deck-print.pdf`） |
| pandoc 3.5 | `tools/pandoc/`（gitignore，144MB），只在需要可选 docx 时用 |

## 改技能

技能是普通文件，改完直接生效：

```bash
$EDITOR .pi/skills/knowledge-point-slides/SKILL.md          # 规则
$EDITOR .pi/skills/knowledge-point-slides/references/*.md   # 契约 / 验收 / 反例
$EDITOR .pi/skills/knowledge-point-slides/scripts/*.py      # 机器校验
bash .pi/skills/knowledge-point-slides/tests/smoke.sh       # 好样本必须过、坏样本必须挂
```

改契约时四件套一起动：`SKILL.md` + `references/deck-contract.md` + `references/checklist.md` +
`scripts/check_deck.py`（必要时加 `references/anti-patterns.md` 与 `tests/` 用例），别只改文字。
