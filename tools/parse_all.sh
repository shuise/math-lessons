#!/bin/bash
#
# parse_all.sh - 一键批量解析 books1 目录下所有 EPUB 到 sources/
#
# 用法:
#   ./tools/parse_all.sh              增量模式：只解析 sources/ 中还没有的
#   ./tools/parse_all.sh -a           全量模式：重新解析所有 epub（覆盖同名 .md）
#   ./tools/parse_all.sh --dir books2 指定 EPUB 所在目录（默认 books1）
#
# 说明:
#   - 支持 .epub 文件与已解压的 EPUB 目录（目录名以 .epub 结尾）
#   - 内部调用 python3 tools/parse_epub.py，文件名清理规则与其一致
#

set -euo pipefail

DIR="books1"
ALL=false

# 解析参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    -a|--all) ALL=true ;;
    --dir) shift; DIR="${1:-books1}" ;;
    -h|--help)
      sed -n '3,10p' "$0" | sed 's/^# //; s/^#$//'
      exit 0
      ;;
    *)
      echo "错误: 未知选项 $1" >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -d "$DIR" ]]; then
  echo "错误: 目录不存在: $DIR" >&2
  exit 1
fi

# 与 parse_epub.py 一致的输出文件名清理规则
clean_name() {
  python3 -c "
import sys, re
b = sys.argv[1]
n = re.sub(r'\s*\(.*?\)\s*', '', b).strip()
print(re.sub(r'[\\\\/:*?\"<>|]', '_', n))
" "$1"
}

cd "$(dirname "$0")/.."   # 切换到项目根目录

mkdir -p sources

found=0
parsed=0
skipped=0

for f in "$DIR"/*; do
  [[ -e "$f" ]] || continue
  [[ "$(basename "$f")" != *.epub ]] && continue
  found=$((found + 1))

  base="$(basename "$f" .epub)"
  name="$(clean_name "$base")"
  out="sources/${name}.md"

  if [[ -f "$out" ]] && [[ "$ALL" == false ]]; then
    echo "跳过(已存在): $name"
    skipped=$((skipped + 1))
    continue
  fi

  echo "解析: $name"
  python3 tools/parse_epub.py "$f" -o sources || {
    echo "  !! 解析失败: $f" >&2
    continue
  }
  parsed=$((parsed + 1))
done

echo ""
echo "完成: 共发现 $found 个 EPUB，新解析 $parsed 个，跳过 $skipped 个"
