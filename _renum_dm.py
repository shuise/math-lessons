# -*- coding: utf-8 -*-
import re

path = '/Users/shuise/math/lessons/logic/comprehensive/index.html'
with open(path, encoding='utf-8') as f:
    c = f.read()

# 1) 先把 5 个「德摩根」新题块内的编号换成临时值（+500），避免与旧题冲突
dm_pattern = re.compile(r'(<!-- ========== 德摩根 (\d) ========== -->)(.*?)(?=<!-- ========== |</article>)', re.S)

def temp_block(m):
    n = int(m.group(2))
    temp = n + 500
    b = m.group(3)
    b = re.sub(r'id="q' + str(n) + r'"', 'id="q' + str(temp) + '"', b)
    b = re.sub(r'id="explain' + str(n) + r'"', 'id="explain' + str(temp) + '"', b)
    b = re.sub(r'checkChoice\(' + str(n) + r',', 'checkChoice(' + str(temp) + ',', b)
    return m.group(1) + b

c = dm_pattern.sub(temp_block, c)

# 2) 重编号旧题（原 6-40 -> 新），按目标值降序，避免连锁替换
mapping = [
    (40,45),(39,44),(38,43),(37,42),(36,41),
    (35,39),(34,38),(33,37),(32,36),(31,35),
    (30,34),(29,33),(28,32),
    (27,30),(26,29),(25,28),(24,27),(23,26),(22,25),(21,24),(20,23),(19,22),
    (18,20),(17,19),(16,18),(15,17),(14,16),(13,15),
    (12,13),(11,12),(10,11),(9,10),(8,9),(7,8),(6,7)
]
for old, new in sorted(mapping, key=lambda x: -x[1]):
    c = re.sub(r'id="q' + str(old) + r'"', 'id="q' + str(new) + '"', c)
    c = re.sub(r'id="explain' + str(old) + r'"', 'id="explain' + str(new) + '"', c)
    c = re.sub(r'checkChoice\(' + str(old) + r',', 'checkChoice(' + str(new) + ',', c)

# 3) 德摩根块临时值还原为最终编号
def restore_block(m):
    n = int(m.group(2))
    temp = n + 500
    b = m.group(3)
    b = re.sub(r'id="q' + str(temp) + r'"', 'id="q' + str(n) + '"', b)
    b = re.sub(r'id="explain' + str(temp) + r'"', 'id="explain' + str(n) + '"', b)
    b = re.sub(r'checkChoice\(' + str(temp) + r',', 'checkChoice(' + str(n) + ',', b)
    return m.group(1) + b

c = dm_pattern.sub(restore_block, c)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)
print('renumber done')
