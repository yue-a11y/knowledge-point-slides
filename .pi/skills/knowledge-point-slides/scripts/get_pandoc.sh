#!/usr/bin/env bash
# 在「使用该技能的那个项目」里安装 pandoc 静态二进制（不碰系统、不需要 sudo）。
#
# 安装位置：从技能目录逐级上溯，第一个含 .pi/ 或 .git/ 的目录视为项目根，
# 装到 <项目根>/tools/pandoc/。找不到项目根时退化为「技能目录旁」的 tools/。
#
#   bash scripts/get_pandoc.sh              # 默认 3.5
#   PANDOC_VERSION=3.6 bash scripts/get_pandoc.sh
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${PANDOC_VERSION:-3.5}"

find_root() {
  local dir="$SKILL_DIR"
  while [[ "$dir" != "/" ]]; do
    if [[ -d "$dir/.pi" || -d "$dir/.git" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  echo "$SKILL_DIR"
}

ROOT="$(find_root)"
TARGET="$ROOT/tools/pandoc"

case "$(uname -m)" in
  x86_64 | amd64) ARCH="linux-amd64" ;;
  aarch64 | arm64) ARCH="linux-arm64" ;;
  *) echo "不支持的架构: $(uname -m)" >&2; exit 1 ;;
esac

if [[ -x "$TARGET/bin/pandoc" ]]; then
  echo "已存在: $("$TARGET/bin/pandoc" --version | head -1)"
  echo "位置: $TARGET"
  exit 0
fi

url="https://github.com/jgm/pandoc/releases/download/${VERSION}/pandoc-${VERSION}-${ARCH}.tar.gz"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "项目根: $ROOT"
echo "下载 $url"
curl -fsSL --max-time 300 -o "$tmp/pandoc.tar.gz" "$url"

tar -xzf "$tmp/pandoc.tar.gz" -C "$tmp"
mkdir -p "$TARGET"
cp -R "$tmp/pandoc-${VERSION}/." "$TARGET/"

echo "已安装: $("$TARGET/bin/pandoc" --version | head -1)"
echo "位置: $TARGET"
echo
echo "提示：该目录较大（~140MB），建议加进该项目的 .gitignore"
