#!/usr/bin/env python3
"""扫描所有 exam/olympiad 文件，检查每道题的交互状态"""
import os
import re
import glob

BASE = '/Users/shuise/math/self-learning/exams'

def scan_file(fpath):
    fname = os.path.basename(fpath)
    with open(fpath, 'r') as f:
        content = f.read()
    
    issues = []
    
    # 检查 JS 函数是否存在
    has_checkTF = 'function checkTF' in content
    has_checkSingle = 'function checkSingle' in content
    has_checkMulti = 'function checkMulti' in content
    has_checkFill = 'function checkFill' in content
    has_toggleHint = 'function toggleHint' in content
    has_toggleAns = 'function toggleAns' in content
    
    missing_funcs = []
    if not has_checkTF: missing_funcs.append('checkTF')
    if not has_checkSingle: missing_funcs.append('checkSingle')
    if not has_checkMulti: missing_funcs.append('checkMulti')
    if not has_checkFill: missing_funcs.append('checkFill')
    if not has_toggleHint: missing_funcs.append('toggleHint')
    if not has_toggleAns: missing_funcs.append('toggleAns')
    
    if missing_funcs:
        issues.append(f'JS 函数缺失: {", ".join(missing_funcs)}')
    
    # 检查题型数量
    # 判断题：找 tf-btn 和 onclick="checkTF"
    tf_questions = len(re.findall(r'onclick="checkTF\(', content))
    tf_buttons = content.count('class="tf-btn"')
    
    # 单选题：找 opt-btn 和 onclick="checkSingle"
    single_questions = len(re.findall(r'onclick="checkSingle\(', content))
    single_opts = content.count('class="opt-btn"')
    
    # 多选题：找 checkMulti
    multi_questions = len(re.findall(r'onclick="checkMulti\(', content))
    multi_opts = len(re.findall(r'onclick="toggleMultiOpt\(', content))
    
    # 填空题：找 checkFill
    fill_questions = len(re.findall(r'onclick="checkFill\(', content))
    fill_inputs = content.count('class="fill-input"')
    
    # 查找没有交互的题目（只有纯文本，没有按钮）
    # 找所有题目编号
    q_items = re.findall(r'<div class="q-item">(.*?)</div>\s*<!--\s*(?:判|单|多|填|其)', content, re.DOTALL)
    total_q = len(re.findall(r'<div class="q-item">', content))
    
    # 检查 hint/ans 按钮
    hint_buttons = len(re.findall(r'onclick="toggleHint\(', content))
    ans_buttons = len(re.findall(r'onclick="toggleAns\(', content))
    
    # 汇总
    total_interactive = tf_questions + single_questions + multi_questions + fill_questions
    total_buttons = tf_buttons + single_opts + multi_opts + fill_inputs
    
    result = {
        'file': fname,
        'tf_q': tf_questions,
        'single_q': single_questions, 
        'multi_q': multi_questions,
        'fill_q': fill_questions,
        'total_interactive': total_interactive,
        'total_q_items': total_q,
        'hint_btns': hint_buttons,
        'ans_btns': ans_buttons,
        'issues': issues,
        'has_all_funcs': len(missing_funcs) == 0,
    }
    
    # 检查是否有题目没有交互元素
    if total_interactive == 0:
        issues.append('⚠ 没有任何交互题目！')
    elif total_interactive < total_q:
        issues.append(f'⚠ 交互题数({total_interactive}) < 题块数({total_q})，可能有题目缺少交互')
    
    return result

# 扫描所有文件
files = sorted(glob.glob(os.path.join(BASE, '*.html')))
results = []

for fpath in files:
    r = scan_file(fpath)
    results.append(r)

# 打印报告
print(f"{'文件':<28} {'JS函数':<6} {'判断':<4} {'单选':<4} {'多选':<4} {'填空':<4} {'题块':<4} {'提示':<4} {'答案':<4} {'问题'}")
print("-" * 120)

total_issues = 0
for r in results:
    func_ok = '✓' if r['has_all_funcs'] else '✗'
    issues_str = '; '.join(r['issues']) if r['issues'] else ''
    if issues_str:
        total_issues += 1
        issues_str = '⚠ ' + issues_str
    
    print(f"{r['file']:<28} {func_ok:<6} {r['tf_q']:<4} {r['single_q']:<4} {r['multi_q']:<4} {r['fill_q']:<4} {r['total_q_items']:<4} {r['hint_btns']:<4} {r['ans_btns']:<4} {issues_str}")

print(f"\n共 {len(results)} 个文件，{total_issues} 个有问题")

# 详细列出有问题的文件
print("\n" + "=" * 60)
print("详细问题列表：")
for r in results:
    if r['issues']:
        print(f"\n📄 {r['file']}:")
        for issue in r['issues']:
            print(f"  {issue}")