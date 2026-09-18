#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
epub_to_textbooks.py - 把 books1 中的 EPUB 拆解到 textbooks，每本书一个目录，
                       目录内生成 index.html 索引章节，textbooks 根目录生成
                       index.html 索引所有书籍。

用法:
  python3 tools/epub_to_textbooks.py                  # 默认: books1 -> textbooks
  python3 tools/epub_to_textbooks.py --force          # 强制重新拆解（覆盖已存在目录）
  python3 tools/epub_to_textbooks.py --books-dir books1 --out-dir textbooks

说明:
  - 每本 epub 解压后作为一个目录放入 textbooks/，目录名取自 epub 文件名，
    去掉开头的日期、书名号《》以及其它特殊字符
  - 目录内所有 .xhtml 重命名为 .html，并修正内部 href/src 引用
  - 目录内 index.html 按 toc.ncx 章节树生成嵌套章节列表
  - textbooks/index.html 列出所有书籍（含已存在的目录，如 张景中）
  - 增量模式：若 textbooks/<书名>/index.html 已存在则跳过拆解，只重建根索引
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

HTML_EXTS = ('.html', '.htm', '.xhtml')
SKIP_TOP = {'版权信息', '总目录', '目录', 'CONTENTS', 'Contents'}
MANIFEST_NAME = '.manifest.json'


def local(tag):
    return tag.rsplit('}', 1)[-1]


# ---------------------------------------------------------------------------
# 命名清理
# ---------------------------------------------------------------------------
def _strip_parens(s):
    """迭代删除成对括号及其内容（含嵌套），处理 () 与 （）"""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r'\s*[（(][^（）()]*[）)]\s*', '', s)
    return s


def clean_dirname(name):
    """去掉开头日期、书名号《》、括号内噪声及其它特殊字符，用于目录名"""
    name = name.replace('《', '').replace('》', '')
    name = name.replace('〈', '').replace('〉', '')
    name = _strip_parens(name)  # 去除 (z-library…) 等括号噪声
    # 开头日期：2019-08 / 2018.02 / 2017-06- / 2019 08
    name = re.sub(r'^\s*\d{4}[-.\s/]\d{1,2}[-.\s/]*', '', name)
    name = re.sub(r'^\s*\d{4}\s+', '', name)
    # 只保留：汉字、字母、数字、下划线、连字符、间隔号
    name = re.sub(r'[^\u4e00-\u9fff\u3400-\u4dbfA-Za-z0-9_\-·]', '', name)
    # 截断（避免文件名过长，UTF-8 下 60 汉字 ≈ 180 字节，安全）
    if len(name) > 60:
        name = name[:60]
    return name.strip() or '未命名'


def find_free_dirname(d, manifest, out_dir):
    """返回不与 manifest 冲突、不在磁盘上的目录名"""
    if d not in manifest and not os.path.exists(os.path.join(out_dir, d)):
        return d
    n = 2
    while True:
        cand = f'{d}_{n}'
        if cand not in manifest and not os.path.exists(os.path.join(out_dir, cand)):
            return cand
        n += 1


def load_manifest(out_dir):
    p = os.path.join(out_dir, MANIFEST_NAME)
    if os.path.isfile(p):
        try:
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_manifest(out_dir, manifest):
    p = os.path.join(out_dir, MANIFEST_NAME)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# OPF / NCX 解析
# ---------------------------------------------------------------------------
def find_opf(book_root):
    """通过 META-INF/container.xml 定位 OPF，回退到文件查找"""
    container = os.path.join(book_root, 'META-INF', 'container.xml')
    if os.path.isfile(container):
        try:
            root = ET.parse(container).getroot()
            for el in root.iter():
                if local(el.tag) == 'rootfile':
                    p = el.get('full-path')
                    if p:
                        full = os.path.join(book_root, p)
                        if os.path.isfile(full):
                            return full
        except ET.ParseError:
            pass
    for r, _, files in os.walk(book_root):
        for f in files:
            if f.endswith('.opf'):
                return os.path.join(r, f)
    return None


def read_opf_metadata(opf_path):
    """返回 (title, author)"""
    title = author = ''
    try:
        root = ET.parse(opf_path).getroot()
    except ET.ParseError:
        return title, author
    for el in root.iter():
        n = local(el.tag)
        if n == 'title' and not title and el.text:
            title = el.text.strip()
        elif n == 'creator' and not author and el.text:
            author = el.text.strip()
    return title, author


def find_ncx(opf_path):
    """从 OPF spine toc 属性定位 ncx，回退到同目录 .ncx 文件"""
    opf_dir = os.path.dirname(opf_path)
    try:
        root = ET.parse(opf_path).getroot()
    except ET.ParseError:
        root = None
    toc_id = None
    if root is not None:
        for el in root.iter():
            if local(el.tag) == 'spine':
                toc_id = el.get('toc')
                break
    if root is not None and toc_id:
        for el in root.iter():
            if local(el.tag) == 'item' and el.get('id') == toc_id:
                href = el.get('href')
                if href:
                    p = os.path.normpath(os.path.join(opf_dir, href))
                    if os.path.isfile(p):
                        return p
    for r, _, files in os.walk(opf_dir):
        for f in files:
            if f.lower().endswith('.ncx'):
                return os.path.join(r, f)
    return None


def parse_ncx_tree(ncx_path):
    """解析 toc.ncx 返回嵌套节点 [(title, src, children)]"""
    try:
        root = ET.parse(ncx_path).getroot()
    except ET.ParseError:
        return []

    def build_node(np):
        title = ''
        src = ''
        for child in np:
            cn = local(child.tag)
            if cn == 'navLabel':
                for t in child.iter():
                    if local(t.tag) == 'text' and t.text:
                        title = t.text.strip()
                        break
            elif cn == 'content':
                src = child.get('src', '') or ''
        children = [build_node(c) for c in np if local(c.tag) == 'navPoint']
        return (title, src, children)

    for el in root.iter():
        if local(el.tag) == 'navMap':
            return [build_node(np) for np in el if local(np.tag) == 'navPoint']
    return []


def src_to_link(src, opf_dir, book_root):
    """把 ncx 中的 src（相对 opf_dir）转为相对 book_root 的链接，.xhtml→.html"""
    if not src:
        return ''
    file_part, sep, anchor = src.partition('#')
    file_part = file_part.replace('.xhtml', '.html')
    abs_file = os.path.normpath(os.path.join(opf_dir, file_part))
    rel = os.path.relpath(abs_file, book_root)
    return rel + (sep + anchor if sep else '')


# ---------------------------------------------------------------------------
# .xhtml -> .html 重命名 + 引用修正
# ---------------------------------------------------------------------------
def rename_xhtml(book_root):
    """把目录内所有 .xhtml 重命名为 .html"""
    for r, _, files in os.walk(book_root):
        for f in files:
            if f.lower().endswith('.xhtml'):
                src = os.path.join(r, f)
                dst = os.path.splitext(src)[0] + '.html'
                if src != dst:
                    os.replace(src, dst)


REF_RE = re.compile(r'((?:href|src)\s*=\s*")([^"]*?)\.xhtml', re.I)
REF_RE_SQ = re.compile(r"((?:href|src)\s*=\s*')([^']*?)\.xhtml", re.I)


def fix_xhtml_refs(book_root):
    """修正 html/css/opf/ncx 中对 .xhtml 的引用为 .html"""
    text_exts = ('.html', '.htm', '.xhtml', '.css', '.opf', '.ncx', '.xml')
    for r, _, files in os.walk(book_root):
        for f in files:
            if not f.lower().endswith(text_exts):
                continue
            p = os.path.join(r, f)
            try:
                with open(p, 'r', encoding='utf-8', errors='replace') as fh:
                    content = fh.read()
            except Exception:
                continue
            new = REF_RE.sub(lambda m: m.group(1) + m.group(2) + '.html', content)
            new = REF_RE_SQ.sub(lambda m: m.group(1) + m.group(2) + '.html', new)
            if new != content:
                with open(p, 'w', encoding='utf-8') as fh:
                    fh.write(new)


VIEWPORT_TAG = ('<meta name="viewport" content="'
                'width=device-width, initial-scale=1.0" />')


def _prefix_for(file_path, book_root):
    """计算从 file 所在目录到 textbooks 根（book_root 的上一级）的相对前缀"""
    rel = os.path.relpath(file_path, book_root)
    d = os.path.dirname(rel)
    depth = 0 if d == '' else len([c for c in d.split(os.sep) if c])
    return '../' * (depth + 1)


def inject_assets(book_root):
    """给书目录内所有 html 页面注入共享 style.css（head 最早）与 math.js（页尾最迟）。
    同时补 viewport meta 以支持移动端。"""
    for r, _, files in os.walk(book_root):
        for f in files:
            if not f.lower().endswith(HTML_EXTS):
                continue
            p = os.path.join(r, f)
            try:
                with open(p, 'r', encoding='utf-8', errors='replace') as fh:
                    content = fh.read()
            except Exception:
                continue
            prefix = _prefix_for(p, book_root)
            link = f'<link rel="stylesheet" href="{prefix}style.css">'
            script = f'<script src="{prefix}math.js"></script>'
            changed = False
            # 已注入则跳过
            if link not in content:
                # viewport meta（缺失则补，确保移动端可用）
                if re.search(r'name=["\']viewport["\']', content, re.I) is None:
                    content, n = re.subn(r'(<head[^>]*>)', r'\1' + VIEWPORT_TAG,
                                          content, count=1, flags=re.I)
                    if n == 0:
                        content, n = re.subn(r'(<html[^>]*>)', r'\1' + VIEWPORT_TAG,
                                            content, count=1, flags=re.I)
                # style.css 注入到 <head> 之后（最早）
                content, n = re.subn(r'(<head[^>]*>)', r'\1' + link,
                                     content, count=1, flags=re.I)
                if n == 0:
                    content = link + content
                changed = True
            if script not in content:
                # math.js 注入到 </body> 之前（最迟）
                content, n = re.subn(r'(</body>)', script + r'\1',
                                     content, count=1, flags=re.I)
                if n == 0:
                    content, n = re.subn(r'(</html>)', script + r'\1',
                                        content, count=1, flags=re.I)
                if n == 0:
                    content = content + script
                changed = True
            if changed:
                try:
                    with open(p, 'w', encoding='utf-8') as fh:
                        fh.write(content)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# 章节回退：无 NCX 时扫描 html 文件
# ---------------------------------------------------------------------------
TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)


def fallback_chapters(book_root):
    """无 NCX 时，扫描目录内 html 文件作为章节列表"""
    items = []
    for r, _, files in os.walk(book_root):
        for f in files:
            if f.lower().endswith(HTML_EXTS) and f.lower() != 'index.html':
                items.append(os.path.join(r, f))
    items.sort()
    chapters = []
    for p in items:
        title = os.path.splitext(os.path.basename(p))[0]
        try:
            with open(p, 'r', encoding='utf-8', errors='replace') as fh:
                content = fh.read()
            m = TITLE_RE.search(content)
            if m:
                t = re.sub(r'<[^>]*>', '', m.group(1)).strip()
                if t:
                    title = t
        except Exception:
            pass
        rel = os.path.relpath(p, book_root)
        chapters.append((title, rel, []))
    return chapters


# ---------------------------------------------------------------------------
# index.html 生成
# ---------------------------------------------------------------------------
def render_chapters(nodes, opf_dir, book_root):
    """递归渲染嵌套 <ul>"""
    if not nodes:
        return ''
    parts = ['<ul>']
    for title, src, children in nodes:
        link = src_to_link(src, opf_dir, book_root) if src else ''
        label = html_escape(title or '(无标题)')
        if link:
            parts.append(f'<li><a href="{html_escape(link)}">{label}</a>')
        else:
            parts.append(f'<li>{label}')
        if children:
            parts.append(render_chapters(children, opf_dir, book_root))
        parts.append('</li>')
    parts.append('</ul>')
    return '\n'.join(parts)


def html_escape(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;'))


def write_book_index(book_root, title, author, source_name, chapters, opf_dir):
    """生成 books/<书名>/index.html"""
    head = title or os.path.basename(book_root)
    author_line = f'<p class="meta">作者：{html_escape(author)}</p>' if author else ''
    source_line = (f'<p class="meta">来源：{html_escape(source_name)}</p>'
                   if source_name else '')
    body = render_chapters(chapters, opf_dir, book_root) or '<p class="empty">（未找到章节）</p>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<link rel="stylesheet" href="../style.css" />
<title>{html_escape(head)}</title>
</head>
<body>
<div class="wrap">
  <a class="back" href="../index.html">← 返回书库</a>
  <h1>{html_escape(head)}</h1>
  {author_line}
  {source_line}
  <div class="toc">
  {body}
  </div>
</div>
<script src="../math.js"></script>
</body>
</html>
"""
    with open(os.path.join(book_root, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def process_book_dir(book_root, source_name=''):
    """处理一个已存在的书目录：读元数据、解析章节、生成 index.html
    返回 (title, author)"""
    opf_path = find_opf(book_root)
    title = author = ''
    opf_dir = book_root
    chapters = []
    if opf_path:
        opf_dir = os.path.dirname(opf_path)
        title, author = read_opf_metadata(opf_path)
        ncx = find_ncx(opf_path)
        if ncx:
            chapters = parse_ncx_tree(ncx)
    if not chapters:
        chapters = fallback_chapters(book_root)
    if not title:
        title = os.path.basename(book_root)
    write_book_index(book_root, title, author, source_name, chapters, opf_dir)
    return title, author


# ---------------------------------------------------------------------------
# 单本 epub 处理
# ---------------------------------------------------------------------------
def process_epub(epub_path, out_dir, manifest, source_to_dir):
    """解压一本 epub 到 out_dir/<书名>/，重命名 xhtml，生成 index.html。
    manifest / source_to_dir 在函数内同步更新。
    返回 (dirname, title) 或 None（跳过/失败）"""
    source = os.path.basename(epub_path)
    base = os.path.splitext(source)[0]
    d = clean_dirname(base)

    # 增量：同一来源 epub 已处理过则跳过
    existing = source_to_dir.get(source)
    if existing and os.path.isfile(os.path.join(out_dir, existing, 'index.html')):
        print(f'  跳过(已存在): {existing}')
        return None

    # 重复书名直接覆盖：使用清理后的目录名，已存在则覆盖
    target = d
    target_full = os.path.join(out_dir, target)
    old = manifest.get(target)
    if old and not old.get('source'):
        # 预存目录（非 epub 生成，如 张景中），不覆盖
        print(f'  !! 目录已存在(预存)，跳过: {target}')
        return None
    # 若该目录原属其它来源，清掉旧来源的反向映射，避免下次误跳过
    if old and old.get('source') and old['source'] != source:
        source_to_dir.pop(old['source'], None)

    tmp = tempfile.mkdtemp(prefix='epub-tb-')
    try:
        with zipfile.ZipFile(epub_path, 'r') as zf:
            zf.extractall(tmp)
    except zipfile.BadZipFile:
        print(f'  !! 损坏的 epub，跳过: {epub_path}')
        shutil.rmtree(tmp, ignore_errors=True)
        return None

    rename_xhtml(tmp)
    fix_xhtml_refs(tmp)
    # 给所有章节页注入共享 style.css / math.js + viewport
    inject_assets(tmp)

    # 生成 index.html（在 tmp 中完成，相对链接随目录一起移动仍然有效）
    title, _ = process_book_dir(tmp, source_name=source)

    if os.path.exists(target_full):
        shutil.rmtree(target_full)
    shutil.move(tmp, target_full)

    manifest[target] = {'source': source, 'title': title}
    source_to_dir[source] = target
    print(f'  拆解完成: {target}  ({title})')
    return target, title


# ---------------------------------------------------------------------------
# 根索引
# ---------------------------------------------------------------------------
def write_root_index(out_dir, books):
    """books: [(dirname, title, source)]  生成 textbooks/index.html"""
    books_sorted = sorted(books, key=lambda b: b[1])
    items = []
    for dirname, title, source in books_sorted:
        src_line = (f'<span class="src">{html_escape(source)}</span>'
                    if source else '')
        items.append(
            f'<li><a href="{html_escape(dirname)}/index.html">{html_escape(title)}</a>'
            f'{src_line}</li>'
        )
    list_html = '\n  '.join(items) if items else '<li class="empty">（暂无书籍）</li>'
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<link rel="stylesheet" href="style.css" />
<title>教材书库</title>
</head>
<body>
<div class="wrap">
  <h1>教材书库</h1>
  <p class="sub">共 {len(books)} 本 · 点击书名进入阅读</p>
  <ul class="booklist">
  {list_html}
  </ul>
</div>
<script src="math.js"></script>
</body>
</html>
"""
    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def dir_size_bytes(path):
    """递归统计目录总字节数"""
    total = 0
    for r, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(r, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def prune_oversized(out_dir, manifest, max_mb):
    """删除超过 max_mb 的书目录，并在 manifest 标记 deleted（永久排除）。
    预存目录（source 为空）同样按大小删除。"""
    limit = max_mb * 1024 * 1024
    removed = []
    for name in sorted(os.listdir(out_dir)):
        full = os.path.join(out_dir, name)
        if not os.path.isdir(full) or name.startswith('.'):
            continue
        size = dir_size_bytes(full)
        if size > limit:
            size_mb = size / 1024 / 1024
            info = manifest.get(name, {'source': '', 'title': name})
            shutil.rmtree(full)
            info['deleted'] = True
            manifest[name] = info
            removed.append((name, size_mb))
            print(f'删除(超过 {max_mb:g}MB): {name}  ({size_mb:.1f} MB)')
    return removed


def main():
    parser = argparse.ArgumentParser(
        description='把 books1 中的 EPUB 拆解到 textbooks，生成索引页')
    parser.add_argument('--books-dir', default='books1', help='EPUB 所在目录（默认 books1）')
    parser.add_argument('--out-dir', default='textbooks', help='输出目录（默认 textbooks）')
    parser.add_argument('--force', action='store_true', help='强制重新拆解（覆盖已存在目录）')
    parser.add_argument('--max-size', type=float, default=None, metavar='MB',
                        help='删除超过该大小（MB）的书目录并永久排除（重跑不再生成）')
    parser.add_argument('--exclude', action='append', default=[], metavar='DIRNAME',
                        help='按书目录名永久排除并删除（可重复使用）')
    args = parser.parse_args()

    books_dir = args.books_dir
    out_dir = args.out_dir

    if not os.path.isdir(books_dir):
        print(f'错误: EPUB 目录不存在: {books_dir}')
        sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)

    # 加载 manifest：保留 deleted 标记条目（目录虽不存在但需永久排除），
    # 剔除其余目录已不存在的陈旧条目
    manifest = {}
    for k, v in load_manifest(out_dir).items():
        if v.get('deleted') or os.path.isdir(os.path.join(out_dir, k)):
            manifest[k] = v

    # 0) 按目录名永久排除：删除目录并在 manifest 标记 deleted
    for name in args.exclude:
        full = os.path.join(out_dir, name)
        if os.path.isdir(full):
            size_mb = dir_size_bytes(full) / 1024 / 1024
            shutil.rmtree(full)
            print(f'删除(手动排除): {name}  ({size_mb:.1f} MB)')
        info = manifest.get(name, {'source': '', 'title': name})
        info['deleted'] = True
        manifest[name] = info

    deleted_sources = {v['source'] for v in manifest.values()
                       if v.get('deleted') and v.get('source')}
    # 反向映射 source epub -> dirname，用于增量跳过
    source_to_dir = {}
    for d, info in manifest.items():
        s = info.get('source', '')
        if s and not info.get('deleted') and s not in source_to_dir:
            source_to_dir[s] = d

    if args.force:
        # 强制重新拆解：删除所有由 epub 生成的目录（source 非空），
        # 保留预存目录和已标记 deleted 的永久排除项
        for d in list(manifest):
            if manifest[d].get('source') and not manifest[d].get('deleted'):
                full = os.path.join(out_dir, d)
                if os.path.exists(full):
                    shutil.rmtree(full)
                del manifest[d]
        source_to_dir = {}

    # 1) 拆解 books1 中的 epub（仅处理文件，跳过同名目录）
    epubs = sorted(f for f in os.listdir(books_dir)
                   if f.lower().endswith('.epub')
                   and os.path.isfile(os.path.join(books_dir, f)))
    print(f'发现 {len(epubs)} 个 EPUB')
    # 同名书（清理后目录名相同）只保留排序最后的来源作为胜出者，其余跳过，
    # 体现「重复书名直接覆盖」（后覆盖前）且保证幂等：重复运行不会反复重拆。
    clean_map = {}
    for name in epubs:
        clean_map.setdefault(clean_dirname(os.path.splitext(name)[0]), []).append(name)
    winners = {srcs[-1] for srcs in clean_map.values()}

    for i, name in enumerate(epubs, 1):
        if name in deleted_sources:
            print(f'[{i}/{len(epubs)}] {name}  跳过(超大小已删除)')
            continue
        if name not in winners:
            print(f'[{i}/{len(epubs)}] {name}  跳过(同名被覆盖)')
            continue
        print(f'[{i}/{len(epubs)}] {name}')
        try:
            process_epub(os.path.join(books_dir, name), out_dir,
                         manifest, source_to_dir)
        except Exception as e:
            print(f'  !! 处理失败: {e}')
            continue

    # 2) 处理预存目录（manifest 中 source 为空，或不在 manifest）：
    #    确保所有章节页注入 style.css / math.js，并补建 index.html。
    #    inject_assets 幂等，重复运行安全。
    for name in sorted(os.listdir(out_dir)):
        full = os.path.join(out_dir, name)
        if not os.path.isdir(full) or name.startswith('.'):
            continue
        info = manifest.get(name)
        if info and info.get('source'):
            continue  # epub 生成目录，step 1 已注入
        inject_assets(full)
        idx = os.path.join(full, 'index.html')
        if not os.path.isfile(idx):
            print(f'补建索引: {name}')
            try:
                title, _ = process_book_dir(full)
                manifest[name] = {'source': '', 'title': title}
            except Exception as e:
                print(f'  !! 补建失败 {name}: {e}')
        else:
            title = read_title_from_index(idx) or name
            manifest[name] = {'source': '', 'title': title}

    # 2.5) 删除超过大小上限的书目录（仅在 --max-size 指定时执行）
    if args.max_size is not None:
        prune_oversized(out_dir, manifest, args.max_size)

    save_manifest(out_dir, manifest)

    # 3) 生成根索引（排除已删除条目）
    books = [(d, info.get('title', d), info.get('source', ''))
             for d, info in manifest.items() if not info.get('deleted')]
    write_root_index(out_dir, books)
    print(f'\n完成: 共 {len(books)} 本书已索引')
    print(f'根索引: {os.path.join(out_dir, "index.html")}')


def read_title_from_index(idx_path):
    try:
        with open(idx_path, 'r', encoding='utf-8') as f:
            content = f.read()
        m = TITLE_RE.search(content)
        if m:
            return re.sub(r'<[^>]*>', '', m.group(1)).strip()
    except Exception:
        pass
    return ''


if __name__ == '__main__':
    main()
