#!/usr/bin/env python3
"""将卡片 HTML 渲染为 750px 宽的 PNG（移动端模式）"""
import sys
import os
from playwright.sync_api import sync_playwright

def render_card(html_path, output_path, mobile=True):
    abs_path = os.path.abspath(html_path)
    url = f"file://{abs_path}"

    W = 750

    with sync_playwright() as p:
        browser = p.chromium.launch()
        if mobile:
            iphone = p.devices["iPhone 14 Pro"]
            ctx = browser.new_context(
                viewport={"width": W, "height": 2000},
                device_scale_factor=1,
                has_touch=True,
                user_agent=iphone["user_agent"],
            )
        else:
            ctx = browser.new_context(
                viewport={"width": W, "height": 2000},
                device_scale_factor=1,
            )

        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")
        content_height = page.evaluate("document.body.scrollHeight")
        page.set_viewport_size({"width": W, "height": content_height + 10})
        page.screenshot(path=output_path, full_page=True)
        ctx.close()
        browser.close()
        mode = "mobile" if mobile else "desktop"
        print(f"Rendered [{mode}]: {output_path} ({W}x{content_height})")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 render_card.py <input.html> <output.png>")
        sys.exit(1)
    render_card(sys.argv[1], sys.argv[2])