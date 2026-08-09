#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
split_epub_books.py - 按 ncx 顶层书目把合集 md 拆分为每本一个文件

用法:
  python3 tools/split_epub_books.py <epub> <合集md> [输出目录]

说明:
  - 书目顺序取自 epub 的 toc.ncx 顶层 navPoint（与总目录一致）
  - 在 md 中按顺序定位每本书的起点标题（容忍 "标题 (N)" 序号后缀；
    某书顶层文件内容过短被跳过时，回退到该书第一个有内容的子标题）
  - 输出到 <输出目录>/<书名>.md，另输出 00_总目录.md 保存开头版权页与总目录列表
"""

import sys
import os
import re
import zipfile
import xml.etree.ElementTree as ET

NS = '{http://www.daisy.org/z3986/2005/ncx/}'
FN_CLEAN = re.compile(r'[\\/:*?"<>|]')


def parse_ncx_books(epub_path):
    """返回 [(书名, [该书的全部 ncx 标题])]，按顶层 navPoint 顺序
    支持 .epub 文件或已解压的 EPUB 目录"""
    ncx_path = None
    if os.path.isdir(epub_path):
        for root_dir, _, files in os.walk(epub_path):
            for f in files:
                if f.lower().endswith('.ncx'):
                    ncx_path = os.path.join(root_dir, f)
                    break
            if ncx_path:
                break
        if not ncx_path:
            return []
        root = ET.parse(ncx_path).getroot()
    else:
        with zipfile.ZipFile(epub_path) as zf:
            ncx_name = None
            for n in zf.namelist():
                if n.lower().endswith('.ncx'):
                    ncx_name = n
                    break
            if not ncx_name:
                return []
            root = ET.fromstring(zf.read(ncx_name))
    books = []
    navmap = root.find(NS + 'navMap')
    if navmap is None:
        return []
    for np in list(navmap):
        label_el = np.find(NS + 'navLabel/' + NS + 'text')
        title = label_el.text.strip() if (label_el is not None and label_el.text) else ''
        if not title:
            continue
        labels = [title]
        for sub in np.findall(NS + 'navPoint'):
            sl = sub.find(NS + 'navLabel/' + NS + 'text')
            if sl is not None and sl.text and sl.text.strip():
                labels.append(sl.text.strip())
        books.append((title, labels))
    return books


def norm_title(t):
    """去 (N) 序号后缀，去空白，用于匹配"""
    t = re.sub(r'\s*\(\d+\)\s*$', '', t).strip()
    return re.sub(r'\s+', ' ', t)


def clean_filename(t):
    t = FN_CLEAN.sub('_', t).strip()
    t = re.sub(r'\s+', ' ', t)
    return t[:80]


def split_md(md_path):
    """把 md 按 ^## 标题切成 [(标题行号, 规范化标题, 原始标题, 块内容)]"""
    with open(md_path, encoding='utf-8') as f:
        lines = f.read().split('\n')
    blocks = []  # (start_line, norm_title, raw_title, body_lines)
    cur = None
    for i, ln in enumerate(lines):
        if ln.startswith('## '):
            if cur is not None:
                blocks.append(cur)
            raw = ln[3:].strip()
            cur = (i + 1, norm_title(raw), raw, [])
        else:
            if cur is not None:
                cur[3].append(ln)
    if cur is not None:
        blocks.append(cur)
    return blocks, lines


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    epub_path, md_path = sys.argv[1], sys.argv[2]
    out_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        os.path.dirname(md_path), 'split')

    books = parse_ncx_books(epub_path)
    if not books:
        print('错误: 未在 epub 中找到 toc.ncx 顶层书目')
        sys.exit(1)
    # 过滤掉 ncx 顶层的导航项（版权信息/总目录 等非书籍条目）
    SKIP_TOP = {'版权信息', '总目录', '目录', 'CONTENTS', 'Contents'}
    books = [b for b in books if b[0] not in SKIP_TOP]
    print(f'ncx 顶层书目: {len(books)} 本')

    blocks, lines = split_md(md_path)

    # 逐本定位起点：
    #   顶层标题（书名）精确匹配优先；仅当该书顶层标题在 md 中
    #   实际不存在时（顶层文件内容过短被解析器跳过），回退匹配其子标题
    md_titles = {nt for _, nt, _, _ in blocks}
    starts = {}  # book_index -> block index
    bi = 0
    for idx, (ln, ntitle, raw, _) in enumerate(blocks):
        if bi >= len(books):
            break
        title, labels = books[bi]
        if ntitle == norm_title(title):
            starts[bi] = idx
            bi += 1
        elif norm_title(title) not in md_titles:
            # 该书顶层标题缺失，尝试用子标题定位（仅一次）
            if any(ntitle == norm_title(l) for l in labels[1:]):
                starts[bi] = idx
                bi += 1
    if len(starts) < len(books):
        missing = [i for i in range(len(books)) if i not in starts]
        print(f'警告: {len(books) - len(starts)} 本未能定位: '
              + '、'.join(books[i][0] for i in missing))

    os.makedirs(out_dir, exist_ok=True)
    written = []
    for i in range(len(books)):
        title, _ = books[i]
        start = starts.get(i)
        end = starts.get(i + 1, len(blocks))
        body_lines = []
        if start is not None:
            for bi in range(start, end):
                _, _, raw, body = blocks[bi]
                body_lines.append(f'## {raw}')
                body_lines.extend(body)
        fname = clean_filename(title)
        path = os.path.join(out_dir, f'{fname}.md')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'# {title}\n\n')
            f.write('\n'.join(body_lines).rstrip() + '\n')
        written.append((fname, os.path.getsize(path)))

    # 总目录与开头版权页单独保存
    first_start = starts.get(0, 0)
    front_start = None
    for idx, (ln, ntitle, raw, _) in enumerate(blocks[:first_start]):
        if ntitle == '总目录':
            front_start = idx
            break
    front_lines = []
    for idx in range(0, first_start):
        _, _, raw, body = blocks[idx]
        front_lines.append(f'## {raw}')
        front_lines.extend(body)
    front_path = os.path.join(out_dir, '00_总目录.md')
    with open(front_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(front_lines).rstrip() + '\n')

    print(f'输出目录: {out_dir}')
    for fname, size in written:
        print(f'  {fname}.md  ({size // 1024} KB)')


if __name__ == '__main__':
    main()
