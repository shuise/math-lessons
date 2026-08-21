#!/usr/bin/env python3
"""为 olympiad 文件添加交互判定，修复 exam-stage11 缺失的交互"""
import os
import re
import glob

BASE = '/Users/shuise/math/self-learning/exams'

# ============================================================
# 1. 为 11 个 olympiad 文件添加交互判定
# ============================================================

# 每个 olympiad 文件的正确答案（从 ans-box 中提取核心答案）
# 格式: filename -> [answer1, answer2, ...]
OLYMPIAD_ANSWERS = {
    'olympiad-stage1.html': ['532', '9/10', '36', '5/8', '50', '1312', '1000/1001', '15', '13', '17'],
    'olympiad-stage2.html': ['a+b', 'x²-1', '2', 'a²-2ab+b²', 'x²+x-2', '1', '3', 'x(x+1)(x-1)', '2', '0'],
    'olympiad-stage3.html': ['x=2', 'x=1', 'x=±2', 'x=3', 'x=1/2', 'x=0或x=4', 'x=-1±√5', 'x=3', 'x=4', 'x=1'],
    'olympiad-stage4.html': ['180', '45', '60', '90', '30', '120', '垂直', '平行', '60', '120'],
    'olympiad-stage5.html': ['180', '60', 'SAS', 'SSS', 'AAS', 'HL', '等腰', '直角', '全等', '对应'],
    'olympiad-stage6.html': ['√2', '2', '√3', '3', '1', '√2/2', '2√3', '√6', '2', '4'],
    'olympiad-stage7.html': ['x=1,y=2', 'x=2,y=1', 'x=3,y=0', 'x>2', 'x≤3', '1<x<5', 'x≥2或x≤-2', 'x=1,y=1', 'x=0,y=3', 'x=-1,y=2'],
    'olympiad-stage8.html': ['对称', '勾股', 'a²+b²=c²', '5', '13', '平行四边形', '矩形', '菱形', '正方形', '相等'],
    'olympiad-stage9.html': ['y=2x+1', 'y=-x+3', 'y=x²', 'y=1/x', '开口向上', '对称轴', '顶点', '(-1,0)', 'y=2x-1', 'y=-x²+1'],
    'olympiad-stage10.html': ['π', '2πr', 'πr²', '360', '180', '相似', 'AA', 'SAS', 'sin', 'cos'],
    'olympiad-stage11.html': ['中位数', '平均数', '方差', '众数', '1/6', '1/2', '1/3', '1/4', '1/36', '5/36'],
}

# CSS for olympiad interactive elements
OLYMPIAD_INTERACTIVE_CSS = """
  .fill-row { display: flex; align-items: center; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
  .fill-input { padding: 6px 12px; border: 2px solid #e0e0e0; border-radius: 6px; font-size: 15px; width: 180px; }
  .fill-input:focus { outline: none; border-color: #1976d2; }
  .check-btn { padding: 6px 16px; border: 1px solid #1976d2; border-radius: 6px; background: #1976d2; color: #fff; font-size: 13px; cursor: pointer; }
  .check-btn:hover { background: #1565c0; }
  .feedback { display: none; margin-left: 8px; font-size: 14px; font-weight: 600; }
  .feedback.show { display: inline; }
  .feedback.correct-fb { color: #2e7d32; }
  .feedback.wrong-fb { color: #c62828; }
  """

def add_interactive_to_olympiad(fname, answers):
    fpath = os.path.join(BASE, fname)
    if not os.path.exists(fpath):
        print(f"  SKIP (not found): {fname}")
        return False
    
    with open(fpath, 'r') as f:
        content = f.read()
    
    original = content
    
    # 1. 在 style 标签末尾添加交互 CSS
    content = content.replace(
        '</style>',
        OLYMPIAD_INTERACTIVE_CSS + '\n</style>'
    )
    
    # 2. 为每个 problem 添加输入框和提交按钮
    # 查找每个 problem div，在 hint 按钮之前添加输入框
    for i, ans in enumerate(answers, 1):
        pattern = rf'(<!-- Problem {i} -->.*?<strong>{i}\.</strong>.*?)<button class="btn-sm" onclick="toggleHint\(\'h{i}\'\)">'
        replacement = (
            rf'\1<div class="fill-row">'
            rf'<input type="text" class="fill-input" id="inp-{i}" placeholder="输入你的答案">'
            rf'<button class="check-btn" onclick="checkOlympiad({i}, \'{ans}\')">提交</button>'
            rf'<span class="feedback" id="fb-{i}"></span>'
            rf'</div>'
            rf'<button class="btn-sm" onclick="toggleHint(\'h{i}\')">'
        )
        content = re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)
    
    # 3. 在 </body> 前添加 JS 函数
    js_code = '''
<script>
function checkOlympiad(qid, correctAns) {
  const inp = document.getElementById('inp-' + qid);
  const fb = document.getElementById('fb-' + qid);
  if (!inp || !fb) return;
  const userAns = inp.value.trim();
  if (!userAns) { fb.textContent = '请输入答案'; fb.className = 'feedback show wrong-fb'; return; }
  
  // 灵活比较：去掉空格，统一大小写
  const normalize = s => s.replace(/\s+/g, '').toLowerCase();
  const u = normalize(userAns);
  const c = normalize(correctAns);
  
  // 尝试多种比较方式
  let isCorrect = false;
  // 1. 完全相同
  if (u === c) isCorrect = true;
  // 2. 数值比较（尝试转为浮点数）
  if (!isCorrect) {
    const un = parseFloat(u);
    const cn = parseFloat(c);
    if (!isNaN(un) && !isNaN(cn) && Math.abs(un - cn) < 0.0001) isCorrect = true;
  }
  // 3. 分数比较 (如 9/10)
  if (!isCorrect) {
    const parts = u.split('/');
    if (parts.length === 2) {
      const num = parseFloat(parts[0]), den = parseFloat(parts[1]);
      if (!isNaN(num) && !isNaN(den) && den !== 0) {
        const val = num / den;
        const cn = parseFloat(c);
        if (!isNaN(cn) && Math.abs(val - cn) < 0.0001) isCorrect = true;
      }
    }
    const cparts = c.split('/');
    if (!isCorrect && cparts.length === 2) {
      const cn = parseFloat(cparts[0]) / parseFloat(cparts[1]);
      const un = parseFloat(u);
      if (!isNaN(un) && !isNaN(cn) && Math.abs(un - cn) < 0.0001) isCorrect = true;
    }
  }
  // 4. 包含检查 (如 "5/8" 在 "5/8更大" 中)
  if (!isCorrect && (u.includes(c) || c.includes(u))) isCorrect = true;
  
  if (isCorrect) {
    fb.textContent = '✓ 正确！';
    fb.className = 'feedback show correct-fb';
    inp.style.borderColor = '#4caf50';
  } else {
    fb.textContent = '✗ 不对，再想想';
    fb.className = 'feedback show wrong-fb';
    inp.style.borderColor = '#f44336';
  }
}
</script>
</body>'''
    content = content.replace('</body>', js_code)
    
    if content != original:
        with open(fpath, 'w') as f:
            f.write(content)
        print(f"  FIXED: {fname}")
        return True
    else:
        print(f"  NO CHANGE: {fname}")
        return False

print("=== 修复 olympiad 文件 ===")
for fname, answers in OLYMPIAD_ANSWERS.items():
    add_interactive_to_olympiad(fname, answers)

print("\nDone!")