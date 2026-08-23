#!/usr/bin/env python3
"""
几何课件 SVG 图形检查工具 — 检查 self-learning 目录下几何课件的 SVG 图形质量
用法: python3 tools/check_geometry.py [--fix]

检查项:
1. SVG viewBox 是否存在且合理
2. SVG 内 text 元素是否有 text-anchor
3. SVG 内坐标是否超出 viewBox 范围
4. 红色/橙色检查（#f44336, #e65100, #ff5722, #ff9800, red, orange）
5. SVG 内 circle/rect/line/path 元素是否有必要属性
6. 前置知识链接检查
7. 中国古代典故检查
8. 挑战题提示按钮检查
"""
import os, re, glob, sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF_LEARNING = os.path.join(PROJECT_ROOT, 'self-learning')

# 几何课件文件列表
GEOMETRY_FILES = [
    'geometry-basics.html',
    'lines-rays-segments.html',
    'angles.html',
    'parallel-lines.html',
    'triangle.html',
    'congruent-triangles.html',
    'symmetry.html',
    'pythagorean.html',
    'parallelogram.html',
    'rotation.html',
    'circle.html',
    'similarity.html',
    'trigonometry.html',
    'projection-views.html',
]

# 红色/橙色系颜色（显示错误才用的颜色）
BAD_COLORS = [
    '#f44336', '#e65100', '#ff5722', '#ff9800', '#ff6f00',
    '#d84315', '#bf360c', '#ff5722', '#ff8a65', '#ffab91',
    'red', 'orange', '#f00', '#e53',
    '#ef5350', '#e53935', '#c62828', '#b71c1c',
    '#ff7043', '#f4511e',
]

def scan_file(fpath):
    with open(fpath, 'r') as f:
        content = f.read()

    fname = os.path.basename(fpath)
    issues = []

    # 1. SVG viewBox 检查
    svgs = re.findall(r'<svg[^>]*>', content)
    for i, svg_tag in enumerate(svgs):
        if 'viewBox' not in svg_tag:
            issues.append(f'SVG #{i+1}: 缺少 viewBox')

    # 2. SVG text 元素 text-anchor 检查（跳过 favicon SVG）
    body_content = re.split(r'</head>', content, maxsplit=1)[-1] if '</head>' in content else content
    # 去掉 head 中的 favicon SVG
    body_svgs = re.findall(r'<svg[^>]*>.*?</svg>', body_content, re.DOTALL)
    # 也提取 CSS 中的 text-anchor 定义
    css_text_anchors = re.findall(r'\.(?:tlabel|lbl|desc|tsmall|tnote|label|place-label)\s*\{[^}]*text-anchor\s*:\s*(\w+)', content)
    for svg_block in body_svgs:
        for text_tag in re.finditer(r'<text([^>]*)>', svg_block):
            attrs = text_tag.group(1)
            if 'text-anchor' not in attrs:
                # 检查是否有 CSS class 定义了 text-anchor
                has_class = re.search(r'class="([^"]+)"', attrs)
                if has_class:
                    cls = has_class.group(1)
                    # 检查 CSS 中是否有 text-anchor（匹配 .cls 或 text.cls）
                    if re.search(r'(?:text\.)?\.' + cls + r'\s*\{[^}]*text-anchor', content):
                        continue
                issues.append(f'SVG text 缺少 text-anchor: "{text_tag.group(0)[:60]}..."')

    # 3. 坐标超出 viewBox 检查
    for svg_match in re.finditer(r'<svg[^>]*viewBox="([\d.\s]+)"[^>]*>(.*?)</svg>', content, re.DOTALL):
        viewBox = svg_match.group(1).split()
        if len(viewBox) == 4:
            vb_x, vb_y, vb_w, vb_h = [float(v) for v in viewBox]
            svg_inner = svg_match.group(2)
            # 检查 circle cx/cy 是否超出
            for circle in re.finditer(r'<circle[^>]*cx="([\d.]+)"[^>]*cy="([\d.]+)"[^>]*r="([\d.]+)"', svg_inner):
                cx, cy, r = float(circle.group(1)), float(circle.group(2)), float(circle.group(3))
                if cx + r > vb_x + vb_w + 1 or cx - r < vb_x - 1:
                    issues.append(f'SVG circle 超出 viewBox: cx={cx}, r={r}, viewBox宽={vb_w}')
                if cy + r > vb_y + vb_h + 1 or cy - r < vb_y - 1:
                    issues.append(f'SVG circle 超出 viewBox: cy={cy}, r={r}, viewBox高={vb_h}')
            # 检查 line x1/y1/x2/y2
            for line in re.finditer(r'<line[^>]*x1="([\d.]+)"[^>]*y1="([\d.]+)"[^>]*x2="([\d.]+)"[^>]*y2="([\d.]+)"', svg_inner):
                x1, y1, x2, y2 = [float(v) for v in line.groups()]
                if max(x1, x2) > vb_x + vb_w + 1 or min(x1, x2) < vb_x - 1:
                    issues.append(f'SVG line 超出 viewBox: x1={x1}, x2={x2}, viewBox宽={vb_w}')
                if max(y1, y2) > vb_y + vb_h + 1 or min(y1, y2) < vb_y - 1:
                    issues.append(f'SVG line 超出 viewBox: y1={y1}, y2={y2}, viewBox高={vb_h}')

    # 4. 红色/橙色检查
    for color in BAD_COLORS:
        if color.lower() in content.lower():
            # 排除 CSS 中的 .correct 等对错标记
            matches = re.findall(re.escape(color), content, re.IGNORECASE)
            if matches:
                # 检查是否在 SVG style 或 inline style 中
                for m in re.finditer(re.escape(color), content, re.IGNORECASE):
                    start = max(0, m.start() - 40)
                    context = content[start:m.end()+20]
                    if '.correct' in context or '.wrong' in context or 'correct' in context.lower():
                        continue
                    issues.append(f'使用红/橙色: {color} (位置: ...{context[:60]}...)')
                    break

    # 5. 前置知识链接检查
    if '前置知识' not in content:
        issues.append('缺少前置知识声明')

    # 6. 中国古代典故检查
    ancient_keywords = ['古代', '中国', '九章算术', '周髀', '赵爽', '刘徽', '祖冲之', '秦九韶', '算经', '勾股', '田亩', '方田']
    has_ancient = any(kw in content for kw in ancient_keywords)
    if not has_ancient:
        issues.append('缺少中国古代相关知识/典故')

    # 7. 挑战题提示按钮检查
    if '挑战' in content or '习题' in content:
        # 检查是否有提示按钮
        if 'toggleHint' not in content and '思路提示' not in content and 'hint' not in content.lower():
            issues.append('挑战题/习题缺少提示按钮')

    # 8. 下一课链接检查
    next_links = re.findall(r'下一课[：:]\s*<a[^>]*href="([^"]+)"', content)
    for link in next_links:
        if link.startswith('http') or link.startswith('../lessons/'):
            issues.append(f'下一课链接可能错误: {link}')

    return {
        'file': fname,
        'issues': issues,
    }

# 主程序
print("=" * 100)
print("几何课件 SVG 图形检查")
print("=" * 100)
print(f"{'文件':<35} {'问题数':<8} {'问题详情'}")
print("-" * 100)

total_issues = 0
files_with_issues = 0

for fname in GEOMETRY_FILES:
    fpath = os.path.join(SELF_LEARNING, fname)
    if not os.path.exists(fpath):
        print(f"{fname:<35} {'文件不存在':<8}")
        continue
    r = scan_file(fpath)
    n = len(r['issues'])
    if n > 0:
        files_with_issues += 1
        total_issues += n
        for issue in r['issues'][:5]:
            print(f"{fname:<35} {n:<8} ⚠ {issue}")
        if n > 5:
            print(f"{'':<35} {'':<8}   ... 还有 {n-5} 个问题")
    else:
        print(f"{fname:<35} {'0':<8} ✓")

print("-" * 100)
print(f"共 {len(GEOMETRY_FILES)} 个文件，{files_with_issues} 个有问题，共 {total_issues} 个问题")
