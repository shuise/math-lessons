#!/usr/bin/env python3
"""
parse_epub.py - 解析 EPUB 文件，提取文本内容输出为 Markdown

用法: python3 parse_epub.py <input.epub> [-o <output_dir>]

章节标题生成优先级：
1. 章节顺序取 OPF spine（manifest itemref 顺序）
2. 章节标题取 toc.ncx 目录树（navPoint > navLabel/text），按 src 关联
3. 无 toc 标题时，取章节 HTML 中的首个 <h1>/<h2>，其次 <title>
4. 仍无则用文件名（清理数字/下划线）；重名自动追加序号
"""

import sys
import os
import zipfile
import tempfile
import argparse
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


class TextExtractor(HTMLParser):
    """提取 HTML 中的纯文本"""
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tag = False
        self.skip_tags = {'script', 'style', 'meta', 'link'}

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip_tag = True

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip_tag = False

    def handle_data(self, data):
        if not self.skip_tag:
            text = data.strip()
            if text:
                self.text_parts.append(text)

    def get_text(self):
        return '\n'.join(self.text_parts)


def local(tag):
    """去掉 XML 命名空间前缀，返回本地标签名"""
    return tag.rsplit('}', 1)[-1]


def parse_opf(opf_content):
    """解析 OPF：返回 (manifest id->(href, media-type), spine idref 有序列表, toc.ncx 的 href 或 None)"""
    manifest = {}
    spine = []
    toc_href = None
    root = ET.fromstring(opf_content)
    for el in root.iter():
        name = local(el.tag)
        if name == 'item':
            iid = el.get('id')
            href = el.get('href')
            media = el.get('media-type')
            if iid and href:
                manifest[iid] = (href, media or '')
        elif name == 'itemref':
            idref = el.get('idref')
            if idref:
                spine.append(idref)
        elif name == 'spine':
            toc_id = el.get('toc')
            if toc_id:
                toc_href = manifest.get(toc_id, (None, None))[0]
    return manifest, spine, toc_href


def parse_ncx(ncx_path, opf_dir):
    """解析 toc.ncx：返回 (标题映射, 顶层书起点文件集合)
    标题映射: {规范化章节 HTML 绝对路径: 标题}
    书起点集合: ncx 顶层 navPoint 指向的文件（每本书的起始页），
               即使内容过短也应输出书名标题，保证拆分锚点齐全
    """
    titles = {}
    book_starts = set()
    try:
        root = ET.parse(ncx_path).getroot()
    except Exception:
        return titles, book_starts
    for nav in root.iter():
        if local(nav.tag) != 'navPoint':
            continue
        label = None
        src = None
        for child in nav:
            cname = local(child.tag)
            if cname == 'navLabel':
                for t in child.iter():
                    if local(t.tag) == 'text' and t.text:
                        label = t.text.strip()
                        break
            elif cname == 'content':
                src = child.get('src')
        if label and src:
            clean = src.split('#')[0]
            if clean:
                abs_path = os.path.normpath(os.path.join(opf_dir, clean))
                if abs_path not in titles:
                    titles[abs_path] = label
                # 顶层 navPoint（navMap 的直接子元素）视为书起点
                parent = None
                for p in root.iter():
                    if local(p.tag) == 'navPoint' and nav in list(p):
                        parent = p
                        break
                if parent is None or local(parent.tag) != 'navPoint':
                    book_starts.add(abs_path)
    return titles, book_starts


# 无意义标题词表：这类词（或 text00006/cover1 等 字母+数字）不是真正的章节名
STOP_WORDS = {'text', 'part', 'chapter', 'cover', 'page', 'img', 'image',
              'ch', 'sec', 'section', 'toc', 'oebps', 'preface', 'appendix', 'title'}


def is_meaningless(t):
    """标题是否为无意义（纯文件名式、纯数字、通用词）"""
    if not t:
        return True
    if re.fullmatch(r'[A-Za-z]*\d+', t):
        return True
    if re.fullmatch(r'[A-Za-z]+[-_.]?\d+', t):
        return True
    if re.fullmatch(r'[\d_]+', t):
        return True
    if re.search(r'-\d+$', t):
        return True
    if t.lower().strip() in STOP_WORDS:
        return True
    return False


def extract_title_from_html(content):
    """从章节 HTML 中提取第一个 <h1>/<h2>，其次 <title>"""
    for pattern in (r'<h[12][^>]*>(.*?)</h[12]>', r'<title[^>]*>(.*?)</title>'):
        m = re.search(pattern, content, re.S | re.I)
        if m:
            text = TextExtractor()
            try:
                text.feed(m.group(1))
            except Exception:
                continue
            t = ' '.join(text.text_parts).strip()
            if t and not is_meaningless(t):
                return t
    return ''


def extract_epub(epub_path, output_dir):
    """解析 EPUB 文件（或已解压的 EPUB 目录），提取文本并输出为 Markdown"""
    basename = os.path.splitext(os.path.basename(epub_path))[0]
    # 清理文件名
    clean_name = re.sub(r'\s*\(.*?\)\s*', '', basename).strip()
    clean_name = re.sub(r'[\\/:*?"<>|]', '_', clean_name)

    if os.path.isdir(epub_path):
        # 输入已是解压后的 EPUB 目录，直接使用
        extract_root = epub_path
    else:
        extract_root = tempfile.mkdtemp(prefix='epub-')
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                zf.extractall(extract_root)
        except Exception:
            pass
    try:
        return _extract_from_dir(extract_root, epub_path, output_dir, clean_name)
    finally:
        if epub_path != extract_root:
            import shutil
            shutil.rmtree(extract_root, ignore_errors=True)


def _extract_from_dir(extract_root, epub_path, output_dir, clean_name):
    """从解压目录中提取内容，写入 Markdown"""
    # 找 OPF 文件
    opf_path = None
    for root, _, files in os.walk(extract_root):
        for f in files:
            if f.endswith('.opf'):
                opf_path = os.path.join(root, f)
                break
        if opf_path:
            break

    if not opf_path:
        print("错误: 未找到 OPF 文件")
        return

    # 读取 OPF 获取元数据和文件列表
    with open(opf_path, 'r', encoding='utf-8', errors='replace') as f:
        opf_content = f.read()
    opf_dir = os.path.dirname(opf_path)

    # 提取书名
    title_match = re.search(r'<dc:title[^>]*>(.*?)</dc:title>', opf_content)
    title = title_match.group(1) if title_match else clean_name

    # 提取作者
    author_match = re.search(r'<dc:creator[^>]*>(.*?)</dc:creator>', opf_content)
    author = author_match.group(1) if author_match else ''

    # 解析 manifest / spine / toc
    try:
        manifest, spine, toc_href = parse_opf(opf_content)
    except ET.ParseError:
        manifest, spine, toc_href = {}, [], None

    # 章节顺序：优先 spine；spine 无效时回退到文件名排序
    chapters = []  # (abs_path, None)
    if spine:
        for idref in spine:
            href = manifest.get(idref, (None, None))[0]
            if not href:
                continue
            abs_path = os.path.normpath(os.path.join(opf_dir, href))
            if os.path.isfile(abs_path) and abs_path.endswith(('.html', '.xhtml', '.htm')):
                chapters.append((abs_path, None))
        if not chapters:
            spine = []

    # toc.ncx 标题映射 + 顶层书起点集合
    ncx_titles = {}
    book_starts = set()
    if toc_href:
        ncx_path = os.path.normpath(os.path.join(opf_dir, toc_href))
        if os.path.isfile(ncx_path):
            ncx_titles, book_starts = parse_ncx(ncx_path, opf_dir)

    if not spine:
        for root, _, files in os.walk(extract_root):
            for f in sorted(files):
                if f.endswith(('.html', '.xhtml', '.htm')):
                    chapters.append((os.path.join(root, f), None))

    # 提取文本
    out_items = []  # (title, text)
    used_titles = {}
    fallback_no = 0
    for abs_path, _ in chapters:
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            continue

        extractor = TextExtractor()
        try:
            extractor.feed(content)
        except Exception:
            continue
        text = extractor.get_text().strip()
        is_book_start = abs_path in book_starts
        if len(text) < 20 and not is_book_start:  # 跳过太短的内容（导航页等），但书起点强制保留
            continue

        # 章节标题：ncx 标题 > html h1/h2/title > 文件名清理 > 第 N 节
        # （ncx 标题若只是文件名式（text00006 等）视为无效，继续回退）
        ch_title = ncx_titles.get(abs_path, '')
        if is_meaningless(ch_title):
            ch_title = ''
        if not ch_title:
            ch_title = extract_title_from_html(content)
        if not ch_title:
            fn = os.path.splitext(os.path.basename(abs_path))[0]
            fn = re.sub(r'[0-9_]+', '', fn).strip()
            ch_title = fn if (fn and not is_meaningless(fn)) else None
        if not ch_title:
            fallback_no += 1
            ch_title = f'第 {fallback_no} 节'

        # 重名自动追加序号，避免重复标题
        base = ch_title
        n = 2
        while ch_title in used_titles:
            ch_title = f'{base} ({n})'
            n += 1
        used_titles[ch_title] = True

        out_items.append((ch_title, text))

    # 输出 Markdown
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f'{clean_name}.md')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f'# {title}\n\n')
        if author:
            f.write(f'**作者**: {author}\n\n')
        f.write(f'**源文件**: {os.path.basename(epub_path)}\n\n')
        f.write('---\n\n')

        for ch_title, text in out_items:
            f.write(f'## {ch_title}\n\n')
            f.write(text)
            f.write('\n\n')

    print(f'输出: {out_path}')
    return out_path


def main():
    parser = argparse.ArgumentParser(description='解析 EPUB 文件')
    parser.add_argument('input', help='输入的 EPUB 文件')
    parser.add_argument('-o', '--output', default='sources', help='输出目录')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f'错误: 文件不存在 {args.input}')
        sys.exit(1)

    extract_epub(args.input, args.output)


if __name__ == '__main__':
    main()
