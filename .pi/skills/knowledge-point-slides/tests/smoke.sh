#!/usr/bin/env bash
# check_deck.py 自测：好样本必须过，每类硬规则各造一个坏样本必须挂。
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"
CHECK="$SKILL_DIR/scripts/check_deck.py"
CONV="$SKILL_DIR/scripts/md2docx.py"
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
  mkdir -p "$dir"
  cp "$FIX/tafel-deck.html" "$FIX/tafel-deck-公式推导.md" "$dir/"
  "$PY" "$CONV" "$dir/tafel-deck-公式推导.md" "$dir/tafel-deck-公式推导.docx" >/dev/null 2>&1
  echo "$dir"
}

expect() { # expect <期望码> <用例名> <html>
  local want="$1" label="$2" html="$3"
  "$PY" "$CHECK" "$html" >"$tmp/out.txt" 2>&1
  local got=$?
  if [[ $got -eq $want ]]; then
    ok "$label"
  else
    bad "$label（期望 $want，实际 $got）"
  fi
}

echo "== check_deck.py 自测 =="

# 0. 好样本
good="$(fresh good)"
expect 0 "好样本通过" "$good/tafel-deck.html"

# 1. 缺 docx
d="$(fresh nodocx)"; rm -f "$d/tafel-deck-公式推导.docx"
expect 1 "缺推导 docx 被抓出" "$d/tafel-deck.html"

# 2. 外链 CDN
d="$(fresh cdn)"; sed -i 's|<main id="deck">|<script src="https://cdn.jsdelivr.net/npm/chart.js"></script><main id="deck">|' "$d/tafel-deck.html"
expect 1 "外链 CDN 被抓出" "$d/tafel-deck.html"

# 3. 式号不连续
d="$(fresh eq)"; sed -i 's/data-eq="3"/data-eq="2"/' "$d/tafel-deck.html"
expect 1 "式号重复/不连续被抓出" "$d/tafel-deck.html"

# 4. 禁用词
d="$(fresh banned)"; sed -i 's|<h1>自测：三道题，答完再翻回去核对</h1>|<h1>谢谢观看</h1>|' "$d/tafel-deck.html"
expect 1 "「谢谢观看」被抓出" "$d/tafel-deck.html"

# 5. 正文字号过小
d="$(fresh font)"; sed -i 's/font-size: 20px; font-family/font-size: 16px; font-family/' "$d/tafel-deck.html"
expect 1 "body 字号 <20px 被抓出" "$d/tafel-deck.html"

# 6. 缺 overflow: hidden
d="$(fresh overflow)"; sed -i 's/overflow: hidden; //' "$d/tafel-deck.html"
expect 1 "缺 overflow:hidden 被抓出" "$d/tafel-deck.html"

# 7. data-page 不连续
d="$(fresh page)"; sed -i 's/data-page="5"/data-page="9"/' "$d/tafel-deck.html"
expect 1 "data-page 不连续被抓出" "$d/tafel-deck.html"

# 8. 末页答案没折叠
d="$(fresh details)"; sed -i 's/<details>/<div>/g' "$d/tafel-deck.html"
expect 1 "末页缺折叠答案被抓出" "$d/tafel-deck.html"

# 9. 易错点不是三段式
d="$(fresh pitfall)"; sed -i 's/错误做法/做法错误/g' "$d/tafel-deck.html"
expect 1 "易错点三段式缺失被抓出" "$d/tafel-deck.html"

# 10. 页数不足
d="$(fresh pages)"
"$PY" - "$d/tafel-deck.html" <<'PY'
import pathlib, re, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r'<section class="slide" data-page="7">.*?</section>', "", text, flags=re.S)
path.write_text(text, encoding="utf-8")
PY
expect 1 "页数不足 8 页被抓出" "$d/tafel-deck.html"

# 11. --skip-docx 可跳过 docx 检查
d="$(fresh skipdocx)"; rm -f "$d/tafel-deck-公式推导.docx"
"$PY" "$CHECK" "$d/tafel-deck.html" --skip-docx >"$tmp/out.txt" 2>&1
if [[ $? -eq 0 ]]; then ok "--skip-docx 生效"; else bad "--skip-docx 未生效"; fi

echo
echo "通过 $pass / 失败 $fail"
[[ $fail -eq 0 ]]
