#!/bin/bash
#
# parse_epub.sh - 解析 EPUB 文件，提取文本内容并输出为 Markdown
#
# 用法: ./parse_epub.sh <input.epub> [选项]
#
# 选项:
#   -o <dir>     输出目录（默认: epub-output/<书名>）
#   -f <format>  输出格式: markdown（默认）, text
#   -h           显示帮助
#

set -euo pipefail

# ============================================================
# 依赖检查
# ============================================================
for cmd in unzip xmlstarlet sed awk basename; do
  if ! command -v "$cmd" &>/dev/null 2>&1; then
    echo "错误: 未找到 '$cmd' 命令，请先安装。" >&2
    exit 1
  fi
done

# ============================================================
# 函数定义
# ============================================================

usage() {
  sed -n '3,11p' "$0" | sed 's/^# //; s/^#$//'
  exit 0
}

# 从 OPF 文件中获取元数据
get_metadata() {
  local opf="$1"
  local xpath="$2"
  xmlstarlet sel -N dc="http://purl.org/dc/elements/1.1/" \
    -t -v "$xpath" "$opf" 2>/dev/null | sed '/^$/d' | head -1
}

# 清理 HTML 标签，提取纯文本
html_to_text() {
  sed -E '
    s/<[^>]*>//g
    s/&amp;/\&/g
    s/&lt;/</g
    s/&gt;/>/g
    s/&quot;/"/g
    s/&#39;/'\''/g
    s/&nbsp;/ /g
    s/&#160;/ /g
    s/^[[:space:]]+//
    s/[[:space:]]+$//
    /^$/d
  '
}

# 将 HTML 转为 Markdown（基础版）
html_to_markdown() {
  local file="$1"
  sed -E '
    # 标题
    s|<h1[^>]*>(.*)</h1>|# \1|g
    s|<h2[^>]*>(.*)</h2>|## \1|g
    s|<h3[^>]*>(.*)</h3>|### \1|g
    s|<h4[^>]*>(.*)</h4>|#### \1|g
    s|<h5[^>]*>(.*)</h5>|##### \1|g
    s|<h6[^>]*>(.*)</h6>|###### \1|g

    # 粗体和斜体
    s|<b>(.*)</b>|**\1**|g
    s|<strong>(.*)</strong>|**\1**|g
    s|<i>(.*)</i>|*\1*|g
    s|<em>(.*)</em>|*\1*|g

    # 段落: 空行前后
    s|<p[^>]*>(.*)</p>|\1\n|g

    # 换行
    s|<br\s*/?>|\n|g
    s|<br>|\n|g

    # 列表
    s|<li[^>]*>(.*)</li>|- \1|g

    # 图片
    s|<img[^>]*src="([^"]*)"[^>]*>|![](\1)|g

    # 链接
    s|<a[^>]*href="([^"]*)"[^>]*>(.*)</a>|[\2](\1)|g

    # 水平线
    s|<hr\s*/?>|---|g

    # 表格基本处理
    s|<tr[^>]*>(.*)</tr>|\1|g
    s|<td[^>]*>(.*)</td>|\1|g
    s|<th[^>]*>(.*)</th>|\1|g
  ' "$file" | sed -E '
    # 移除剩余 HTML 标签
    s/<[^>]*>//g

    # HTML 实体
    s/&amp;/\&/g
    s/&lt;/</g
    s/&gt;/>/g
    s/&quot;/"/g
    s/&#39;/\x27/g
    s/&nbsp;/ /g
    s/&#160;/ /g
    s/&mdash;/—/g
    s/&ndash;/–/g

    # 合并多行空白
    /^$/{
      N
      /^\n$/d
    }
  ' | sed -E '/^[[:space:]]*$/d'
}

# ============================================================
# 主流程
# ============================================================

INPUT_FILE=""
OUTPUT_DIR=""
OUTPUT_FORMAT="markdown"

# 解析参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage ;;
    -o) shift; OUTPUT_DIR="$1" ;;
    -f) shift; OUTPUT_FORMAT="$1" ;;
    -*)
      echo "错误: 未知选项 $1" >&2
      usage
      ;;
    *)
      [[ -z "$INPUT_FILE" ]] && INPUT_FILE="$1" || {
        echo "错误: 多余的参数: $1" >&2
        usage
      }
      ;;
  esac
  shift
done

# 检查输入文件
if [[ -z "$INPUT_FILE" ]]; then
  echo "错误: 请指定 EPUB 文件" >&2
  usage
fi

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "错误: 文件不存在: $INPUT_FILE" >&2
  exit 1
fi

INPUT_FILE="$(cd "$(dirname "$INPUT_FILE")" && pwd)/$(basename "$INPUT_FILE")"

# ============================================================
# 1. 解压 EPUB
# ============================================================
TMP_DIR="$(mktemp -d /tmp/epub-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "正在解压: $INPUT_FILE"
unzip -qo "$INPUT_FILE" -d "$TMP_DIR"

# ============================================================
# 2. 定位 OPF 文件
# ============================================================
CONTAINER="$TMP_DIR/META-INF/container.xml"
if [[ ! -f "$CONTAINER" ]]; then
  echo "错误: 无法找到 META-INF/container.xml" >&2
  exit 1
fi

OPF_REL=$(xmlstarlet sel -N ns="urn:oasis:names:tc:opendocument:xmlns:container" \
  -t -v "//ns:rootfile/@full-path" "$CONTAINER" 2>/dev/null | head -1)

if [[ -z "$OPF_REL" ]]; then
  echo "错误: 无法从 container.xml 解析 OPF 路径" >&2
  exit 1
fi

OPF_FILE="$TMP_DIR/$OPF_REL"
if [[ ! -f "$OPF_FILE" ]]; then
  echo "错误: OPF 文件不存在: $OPF_FILE" >&2
  exit 1
fi

OPF_DIR="$(dirname "$OPF_FILE")"
echo "发现 OPF: $OPF_REL"

# ============================================================
# 3. 读取元数据
# ============================================================
TITLE=$(get_metadata "$OPF_FILE" "//dc:title" || echo "未知标题")
CREATOR=$(get_metadata "$OPF_FILE" "//dc:creator" || echo "未知作者")
LANGUAGE=$(get_metadata "$OPF_FILE" "//dc:language" || echo "未知语言")

echo "书名: $TITLE"
echo "作者: $CREATOR"

# ============================================================
# 4. 确定输出目录
# ============================================================
if [[ -z "$OUTPUT_DIR" ]]; then
  SAFE_TITLE=$(echo "$TITLE" | sed 's/[^a-zA-Z0-9_\u4e00-\u9fa5-]/-/g; s/-\+/-/g; s/^-\|-$//g')
  OUTPUT_DIR="epub-output/${SAFE_TITLE:-epub-unknown}"
fi

mkdir -p "$OUTPUT_DIR"

# ============================================================
# 5. 按 spine 顺序读取内容
# ============================================================
echo "正在提取内容..."

# 收集 manifest 中的 id->href 映射
declare -A MANIFEST
while IFS='|' read -r id href; do
  MANIFEST["$id"]="$href"
done < <(xmlstarlet sel -N dc="http://purl.org/dc/elements/1.1/" \
  -t -m "//*[local-name()='manifest']/*[local-name()='item']" \
  -v "concat(@id, '|', @href)" -n "$OPF_FILE" 2>/dev/null)

# 输出文件
OUTPUT_FILE="$OUTPUT_DIR/$(basename "$INPUT_FILE" .epub).md"
[[ "$OUTPUT_FORMAT" == "text" ]] && OUTPUT_FILE="$OUTPUT_DIR/$(basename "$INPUT_FILE" .epub).txt"

{
  echo "---"
  echo "title: \"$TITLE\""
  echo "creator: \"$CREATOR\""
  [[ -n "$LANGUAGE" ]] && echo "language: \"$LANGUAGE\""
  echo "source: \"$(basename "$INPUT_FILE")\""
  echo "---"
  echo ""
  echo "# $TITLE"
  echo ""
  echo "**作者:** $CREATOR"
  echo ""
  echo "---"
  echo ""
} > "$OUTPUT_FILE"

# 按 spine 顺序处理
SPINE_ITEMS=$(xmlstarlet sel -N dc="http://purl.org/dc/elements/1.1/" \
  -t -m "//*[local()='spine']/*[local()='itemref']" \
  -v "@idref" -n "$OPF_FILE" 2>/dev/null)

CHAPTER_NUM=0
while IFS= read -r idref; do
  [[ -z "$idref" ]] && continue

  HREF="${MANIFEST[$idref]:-}"
  [[ -z "$HREF" ]] && continue

  CONTENT_FILE="$OPF_DIR/$HREF"
  CONTENT_FILE="$(cd "$(dirname "$CONTENT_FILE")" && pwd)/$(basename "$CONTENT_FILE")"

  if [[ ! -f "$CONTENT_FILE" ]]; then
    echo "  警告: 文件不存在: $HREF" >&2
    continue
  fi

  # 只处理 HTML/XHTML
  case "$CONTENT_FILE" in
    *.htm|*.html|*.xhtml|*.xml)
      CHAPTER_NUM=$((CHAPTER_NUM + 1))
      printf "  [%d] %s\n" "$CHAPTER_NUM" "$HREF"

      if [[ "$OUTPUT_FORMAT" == "markdown" ]]; then
        html_to_markdown "$CONTENT_FILE" >> "$OUTPUT_FILE"
      else
        html_to_text < "$CONTENT_FILE" >> "$OUTPUT_FILE"
      fi
      echo "" >> "$OUTPUT_FILE"
      echo "---" >> "$OUTPUT_FILE"
      echo "" >> "$OUTPUT_FILE"
      ;;
    *)
      # 非 HTML 文件（图片、CSS 等）跳过
      ;;
  esac
done <<< "$SPINE_ITEMS"

echo ""
echo "完成! 共处理 $CHAPTER_NUM 个章节"
echo "输出文件: $(cd "$(dirname "$OUTPUT_FILE")" && pwd)/$(basename "$OUTPUT_FILE")"
