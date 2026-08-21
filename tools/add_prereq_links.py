#!/usr/bin/env python3
"""
add_prereq_links.py - 为 self-learning 课件批量添加前置知识链接
用法:
  python3 tools/add_prereq_links.py          # 执行添加
  python3 tools/add_prereq_links.py --check   # 仅检查不修改
"""
import re, os, sys

# 支持从项目根目录运行
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
CHECK_ONLY = '--check' in sys.argv

courses = {
    1: "natural-numbers.html", 2: "fractions.html", 3: "negative-numbers.html",
    4: "algebraic-expressions.html", 5: "polynomials.html", 6: "factoring-rational.html",
    7: "linear-equations.html", 8: "fractional-equations.html", 9: "quadratic-equations.html",
    10: "geometry-basics.html", 11: "lines-rays-segments.html", 12: "angles.html",
    13: "parallel-lines.html", 14: "triangle.html", 15: "congruent-triangles.html",
    16: "real-numbers.html", 17: "quadratic-radicals.html",
    18: "linear-systems.html", 19: "inequalities.html",
    20: "symmetry.html", 21: "pythagorean.html", 22: "parallelogram.html",
    23: "coordinate-system.html", 24: "linear-function.html",
    25: "quadratic-function.html", 26: "inverse-function.html",
    27: "rotation.html", 28: "circle.html", 29: "similarity.html",
    30: "trigonometry.html", 31: "projection-views.html",
    32: "data-collection.html", 33: "data-analysis.html", 34: "probability.html",
}

dirpath = os.path.join(_project_root, "self-learning")
count = 0

for fname in os.listdir(dirpath):
    if not fname.endswith('.html') or fname == 'index.html':
        continue
    fpath = os.path.join(dirpath, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    if '<a href=' in content and '前置知识' in content:
        # Check if the 前置知识 line already has links
        m = re.search(r'<p style="color:#999;font-size:13px;margin-bottom:8px;">前置知识：[^<]*</p>', content)
        if m and '<a href=' in m.group(0):
            continue  # already has links

    def replace_prereq(match):
        line = match.group(0)
        if '<a href=' in line:
            return line

        # 课件 N（title）→ link
        def linkify(m):
            num = int(m.group(1))
            desc = m.group(2) if m.group(2) else ''
            if num in courses:
                href = courses[num]
                return f'<a href="./{href}">课件 {num}{desc}</a>'
            return m.group(0)

        # 课件 N-M（title）→ links
        def linkify_range(m):
            a = int(m.group(1))
            b = int(m.group(2))
            desc = m.group(3) if m.group(3) else ''
            links = []
            for n in range(a, b+1):
                if n in courses:
                    links.append(f'<a href="./{courses[n]}">课件 {n}</a>')
            return '、'.join(links) + desc

        line = re.sub(r'课件 (\d+)-(\d+)(（[^）]*）)?', linkify_range, line)
        line = re.sub(r'课件 (\d+)(（[^）]*）)', linkify, line)
        return line

    new_content = re.sub(
        r'<p style="color:#999;font-size:13px;margin-bottom:8px;">前置知识：[^<]*</p>',
        replace_prereq,
        content
    )

    if new_content != content:
        if CHECK_ONLY:
            print(f"NEEDS UPDATE: {fname}")
            count += 1
        else:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated: {fname}")
            count += 1

if CHECK_ONLY:
    print(f"\n{count} files need update (check mode)")
else:
    print(f"\nTotal updated: {count} files")