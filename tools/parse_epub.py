#!/usr/bin/env python3
"""
parse_epub.py - 解析 EPUB 文件，提取文本内容输出为 Markdown

用法: python3 parse_epub.py <input.epub> [-o <output_dir>]
"""

import sys
import os
import zipfile
import tempfile
import argparse
import re
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


def extract_epub(epub_path, output_dir):
    """解析 EPUB 文件，提取文本并输出为 Markdown"""
    basename = os.path.splitext(os.path.basename(epub_path))[0]
    # 清理文件名
    clean_name = re.sub(r'\s*\(.*?\)\s*', '', basename).strip()
    clean_name = re.sub(r'[\\/:*?"<>|]', '_', clean_name)

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(epub_path, 'r') as zf:
            zf.extractall(tmpdir)

        # 找 OPF 文件
        opf_path = None
        for root, _, files in os.walk(tmpdir):
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

        # 提取书名
        title_match = re.search(r'<dc:title[^>]*>(.*?)</dc:title>', opf_content)
        title = title_match.group(1) if title_match else clean_name

        # 提取作者
        author_match = re.search(r'<dc:creator[^>]*>(.*?)</dc:creator>', opf_content)
        author = author_match.group(1) if author_match else ''

        # 找所有 HTML/XHTML 文件
        html_files = []
        for root, _, files in os.walk(tmpdir):
            for f in files:
                if f.endswith(('.html', '.xhtml', '.htm')):
                    html_files.append(os.path.join(root, f))

        # 按文件名排序
        html_files.sort()

        # 提取文本
        chapters = []
        for html_path in html_files:
            rel_path = os.path.relpath(html_path, tmpdir)
            try:
                with open(html_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception:
                continue

            extractor = TextExtractor()
            try:
                extractor.feed(content)
            except Exception:
                continue

            text = extractor.get_text().strip()
            if len(text) < 20:  # 跳过太短的内容（可能是导航页等）
                continue

            chapters.append((rel_path, text))

        # 输出 Markdown
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, f'{clean_name}.md')

        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(f'# {title}\n\n')
            if author:
                f.write(f'**作者**: {author}\n\n')
            f.write(f'**源文件**: {os.path.basename(epub_path)}\n\n')
            f.write('---\n\n')

            for i, (rel_path, text) in enumerate(chapters):
                # 用文件名做章节标题
                chapter_title = os.path.splitext(os.path.basename(rel_path))[0]
                chapter_title = re.sub(r'[0-9_]+', '', chapter_title).strip()
                if not chapter_title:
                    chapter_title = f'第 {i+1} 节'

                f.write(f'## {chapter_title}\n\n')
                f.write(text)
                f.write('\n\n')

        print(f'输出: {out_path}')
        return out_path


def main():
    parser = argparse.ArgumentParser(description='解析 EPUB 文件')
    parser.add_argument('input', help='输入的 EPUB 文件')
    parser.add_argument('-o', '--output', default='epub-output', help='输出目录')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f'错误: 文件不存在 {args.input}')
        sys.exit(1)

    extract_epub(args.input, args.output)


if __name__ == '__main__':
    main()
