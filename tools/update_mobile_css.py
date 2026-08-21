#!/usr/bin/env python3
"""
update_mobile_css.py - 批量更新 self-learning 课件的移动端 CSS
用法: python3 tools/update_mobile_css.py
"""
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
dirpath = os.path.join(_project_root, "self-learning")
count = 0

for fname in os.listdir(dirpath):
    if not fname.endswith('.html') or fname == 'index.html':
        continue
    fpath = os.path.join(dirpath, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Update mobile article padding + add body padding 0
    content = content.replace(
        'article { padding: 20px 12px !important; }',
        'article { padding: 20px 0 100px 0 !important; border-radius: 0 !important; }\n    body { padding: 0; }'
    )

    if content != original:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {fname}")
        count += 1

print(f"\nTotal updated: {count} files")