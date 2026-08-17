#!/usr/bin/env bash
# 把自助答疑脚本注入到 lessons/ 下所有 HTML（幂等，重复执行安全）
# 注入方式：在 </body> 前追加 <script src="/lessons/qa.js" defer>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/lessons"
MARK="/lessons/qa.js"

[ -f "$DIR/qa.js" ] || { echo "缺少 $DIR/qa.js" >&2; exit 1; }

INJECTED=0
NOBODY=0
while IFS= read -r -d '' f; do
  if grep -q "$MARK" "$f"; then
    continue  # 已注入，跳过（幂等）
  fi
  if grep -qi '</body>' "$f"; then
    sed -i.bak 's#</body>#<script src="/lessons/qa.js" defer></script></body>#' "$f" 2>/dev/null \
      && rm -f "$f.bak" && INJECTED=$((INJECTED + 1))
  else
    printf '\n<script src="%s" defer></script>\n' "$MARK" >> "$f"
    NOBODY=$((NOBODY + 1))
  fi
done < <(find "$DIR" -name '*.html' -print0)

echo "注入完成：新增 $INJECTED 个页面；追加到末尾（无 </body>）$NOBODY 个；已跳过（此前注入）$(( $(find "$DIR" -name '*.html' | wc -l | tr -d ' ') - INJECTED - NOBODY )) 个"
