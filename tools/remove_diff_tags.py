import re, os

dirpath = "self-learning"
count = 0

for fname in os.listdir(dirpath):
    if not fname.endswith('.html') or fname == 'index.html':
        continue
    fpath = os.path.join(dirpath, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Remove diff-tag CSS blocks (the 4 lines: .diff-tag, .diff-easy, .diff-medium, .diff-hard)
    content = re.sub(
        r'\s*\.diff-tag \{ display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 12px; color: #fff; margin-left: 8px; \}\n'
        r'\s*\.diff-easy \{ background: #66bb6a; \}\n'
        r'\s*\.diff-medium \{ background: #ff9800; \}\n'
        r'\s*\.diff-hard \{ background: #f44336; \}\n',
        '\n',
        content
    )

    # Remove diff-tag spans from HTML body
    content = re.sub(r'\s*<span class="diff-tag diff-(?:easy|medium|hard)">[^<]*</span>', '', content)

    if content != original:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {fname}")
        count += 1

print(f"\nTotal updated: {count} files")