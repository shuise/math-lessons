#!/usr/bin/env python3
"""
通用课件检查工具 — 检查 self-learning/exams 目录下所有 exam/olympiad 文件的交互状态
用法: python3 check_exams.py

检查项:
1. JS 函数是否齐全
2. onclick 中是否有转义引号 \'
3. 交互调用数 vs 题数是否匹配
4. checkSingle 的容器 id 前缀是否与 HTML 一致（single- vs opt-）
5. checkMulti 的容器 id 前缀是否与 HTML 一致（multi- vs opt-）
6. 单选题是否缺少 feedback span
7. 判断题/多选题/填空题是否缺少 feedback span
8. CSS 中是否有 correct/wrong 样式定义
"""
import os, re, glob, sys

BASE = os.path.dirname(os.path.abspath(__file__))

def scan_file(fpath):
    with open(fpath, 'r') as f:
        content = f.read()

    fname = os.path.basename(fpath)
    issues = []
    is_olympiad = 'olympiad' in fname

    # 1. 检查 JS 函数
    if is_olympiad:
        funcs = ['checkOlympiad', 'toggleHint', 'toggleAns']
    else:
        funcs = ['checkTF', 'checkSingle', 'checkMulti', 'checkFill', 'toggleHint', 'toggleAns']
    missing = [fn for fn in funcs if f'function {fn}' not in content]
    if missing:
        issues.append(f'JS函数缺失: {", ".join(missing)}')

    # 2. 检查转义引号（onclick 属性中的 \' 应为 '）
    escaped = re.findall(r"onclick=\"[^\"]*\\'", content)
    if escaped:
        issues.append(f'转义引号 {len(escaped)} 处')

    # 3. 统计交互调用 & 题数
    if is_olympiad:
        fill_count = len(re.findall(r'onclick="checkOlympiad\(', content))
        hint_count = len(re.findall(r'onclick="toggleHint\(', content))
        ans_count = len(re.findall(r'onclick="toggleAns\(', content))
        total_interactive = fill_count
        total_q = len(re.findall(r'<strong>\d+\.</strong>', content))
        tf_count = single_count = multi_count = 0
    else:
        tf_count = len(re.findall(r'onclick="checkTF\(', content))
        single_count = len(re.findall(r'onclick="checkSingle\(', content))
        multi_count = len(re.findall(r'onclick="checkMulti\(', content))
        fill_count = len(re.findall(r'onclick="checkFill\(', content))
        hint_count = len(re.findall(r'onclick="toggleHint\(', content))
        ans_count = len(re.findall(r'onclick="toggleAns\(', content))
        total_interactive = tf_count + single_count + multi_count + fill_count
        total_q = len(re.findall(r'<strong>\d+\.</strong>', content))

    # 4. checkSingle 容器 id 前缀一致性
    if not is_olympiad and single_count > 0:
        # 提取 checkSingle 调用中的 qid
        single_qids = re.findall(r"onclick=\"checkSingle\(this,\s*(?:true|false),\s*'([^']+)'\)\"", content)
        # 检查函数中用的前缀
        func_match = re.search(r'function checkSingle\(.*?\)\s*\{[^}]*?getElementById\(\'([a-z]+)-\'\s*\+\s*qid\)', content, re.DOTALL)
        if func_match:
            func_prefix = func_match.group(1)
            # 检查 HTML 中是否有对应 id 的 div
            for qid in single_qids:
                if f'id="{func_prefix}-{qid}"' not in content:
                    issues.append(f'checkSingle 容器 id 不匹配: 函数用 {func_prefix}-{qid} 但 HTML 无此 id')
                    break
        # 也检查反方向：HTML 中 single- div 但函数用 opt-
        single_divs = re.findall(r'id="(single-\d+-\d+)"', content)
        if single_divs and func_match and func_prefix != 'single':
            issues.append(f'checkSingle 函数前缀={func_prefix}- 但 HTML 用 single-')

    # 5. checkMulti 容器 id 前缀一致性
    if not is_olympiad and multi_count > 0:
        multi_qids = re.findall(r"onclick=\"checkMulti\('([^']+)'", content)
        func_match = re.search(r'function checkMulti\(.*?\)\s*\{[^}]*?getElementById\(\'([a-z]+)-\'\s*\+\s*qid\)', content, re.DOTALL)
        if func_match:
            func_prefix = func_match.group(1)
            for qid in multi_qids:
                if f'id="{func_prefix}-{qid}"' not in content:
                    issues.append(f'checkMulti 容器 id 不匹配: 函数用 {func_prefix}-{qid} 但 HTML 无此 id')
                    break
        multi_divs = re.findall(r'id="(multi-\d+-\d+)"', content)
        if multi_divs and func_match and func_prefix != 'multi':
            issues.append(f'checkMulti 函数前缀={func_prefix}- 但 HTML 用 multi-')

    # 6. 单选题缺少 feedback span
    if not is_olympiad and single_count > 0:
        single_qids = re.findall(r"onclick=\"checkSingle\(this,\s*(?:true|false),\s*'([^']+)'\)\"", content)
        missing_fb = [qid for qid in single_qids if f'id="fb-{qid}"' not in content]
        if missing_fb:
            issues.append(f'单选题缺 feedback span: {",".join(missing_fb[:5])}')

    # 7. 判断题缺少 feedback span
    if not is_olympiad and tf_count > 0:
        tf_qids = re.findall(r"onclick=\"checkTF\(this,\s*(?:true|false),\s*'([^']+)'\)\"", content)
        missing_fb = [qid for qid in tf_qids if f'id="fb-{qid}"' not in content]
        if missing_fb:
            issues.append(f'判断题缺 feedback span: {",".join(missing_fb[:5])}')

    # 8. 多选题缺少 feedback span
    if not is_olympiad and multi_count > 0:
        multi_qids = re.findall(r"onclick=\"checkMulti\('([^']+)'", content)
        missing_fb = [qid for qid in multi_qids if f'id="fb-{qid}"' not in content]
        if missing_fb:
            issues.append(f'多选题缺 feedback span: {",".join(missing_fb[:5])}')

    # 9. 填空题缺少 feedback span
    if not is_olympiad and fill_count > 0:
        fill_qids = re.findall(r"onclick=\"checkFill\('([^']+)'", content)
        missing_fb = [qid for qid in fill_qids if f'id="fb-{qid}"' not in content]
        if missing_fb:
            issues.append(f'填空题缺 feedback span: {",".join(missing_fb[:5])}')

    # 10. CSS correct/wrong 样式检查
    if not is_olympiad:
        if '.correct' not in content:
            issues.append('CSS 缺少 .correct 样式')
        if '.wrong' not in content:
            issues.append('CSS 缺少 .wrong 样式')

    has_all_funcs = len(missing) == 0

    return {
        'file': fname,
        'tf': tf_count,
        'single': single_count,
        'multi': multi_count,
        'fill': fill_count,
        'interactive': total_interactive,
        'questions': total_q,
        'hints': hint_count,
        'answers': ans_count,
        'has_all_funcs': has_all_funcs,
        'issues': issues,
    }

files = sorted(glob.glob(os.path.join(BASE, '*.html')))
if not files:
    print("未找到 HTML 文件")
    sys.exit(0)

print(f"{'文件':<28} {'JS':<4} {'TF':<4} {'单选':<5} {'多选':<5} {'填空':<5} {'交互':<6} {'题数':<6} {'提示':<5} {'答案':<5} {'问题'}")
print("-" * 130)

total_issues = 0
for fpath in files:
    r = scan_file(fpath)
    js = '✓' if r['has_all_funcs'] else '✗'
    issues_str = '; '.join(r['issues']) if r['issues'] else ''
    if issues_str:
        total_issues += 1
        issues_str = '⚠ ' + issues_str
    print(f"{r['file']:<28} {js:<4} {r['tf']:<4} {r['single']:<5} {r['multi']:<5} {r['fill']:<5} {r['interactive']:<6} {r['questions']:<6} {r['hints']:<5} {r['answers']:<5} {issues_str}")

print(f"\n共 {len(files)} 个文件，{total_issues} 个有问题")
