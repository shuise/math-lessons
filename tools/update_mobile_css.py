import os

dirpath = "self-learning"
count = 0

for fname in os.listdir(dirpath):
    if not fname.endswith('.html') or fname == 'index.html':
        continue
    fpath = os.path.join(dirpath, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Update mobile article padding + add body padding 0
    content = content.replace(
        'article { padding: 20px 12px !important; }',
        'article { padding: 20px 0 100px 0 !important; border-radius: 0 !important; }\n    body { padding: 0; }'
    )

    if content != original:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {fname}")
        count += 1

print(f"\nTotal updated: {count} files")