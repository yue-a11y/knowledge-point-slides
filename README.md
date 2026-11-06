# knowledge-point-slides — 应用项目

用 `knowledge-point-slides` 技能做**知识点讲解 HTML 幻灯片**（+ 公式推导 docx）。

技能本体在 `.pi/skills/knowledge-point-slides/`，由 `/home/llh/pi-workspaces/skill`（技能工坊）导出，**不要在这里改技能**——改动请提回工坊再重新导出。

## 启动

```bash
cd ~/pi-workspaces/knowledge-point-slides
pi            # 首次会问 project trust，必须批准，否则技能不加载
```

改过技能后 `/reload`。

## 触发

```text
/skill:knowledge-point-slides 讲清「怎么从 LSV 曲线取 Tafel 斜率」，听众研一，
手上有 0.1 M KOH、1 mV/s 的 LSV（E 0–0.4 V vs RHE，j 0–50 mA/cm²），要能自己算出 60 mV/dec。
```

或者直接用自然语言（`description` 能被路由到才算写对）：

```text
帮我做个讲解 PPT，讲清 Tafel 斜率怎么取，听众是研一学生……
```

技能会先只回 5 行（起点/终点/听众缺/贯穿算例/最易错一步），确认后才给 outline 表，再给视觉动画计划，最后才产出文件。**别催它跳阶段**，闸门是这个技能的核心。

## 产物

```text
work/<slug>/
├── <slug>.html                # 单文件，断网可用，Ctrl+P 导 PDF
├── <slug>-公式推导.docx       # 与幻灯片同批产出
├── shots/p01.png …            # 每页缩略截图
└── <slug>-交付说明.md         # 验收 A–I 勾选 + 没做到的事
```

交付前自检：

```bash
python3 .pi/skills/knowledge-point-slides/scripts/check_deck.py work/<slug>/<slug>.html
```

## 环境

| 项 | 状态 |
|---|---|
| pandoc 3.5 | 已装在 `tools/pandoc/`（gitignore，144MB） |
| python-docx | 系统已装（pandoc 缺失时的降级后端） |
| 技能自测 | `bash .pi/skills/knowledge-point-slides/tests/smoke.sh` → 通过 12 / 失败 0 |

## 更新技能

```bash
# 工坊里
cd ~/pi-workspaces/skill && make export NAME=knowledge-point-slides

# 这里
rsync -a --delete ~/pi-workspaces/skill/dist/knowledge-point-slides/ .pi/skills/knowledge-point-slides/
```

不要两边手改，会分叉。
