#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""math-story-card 生成脚本

将「书名 / 章节 / 标题 / 故事摘录 / 金句 / 知识点标签」排版为竖版分享卡片（PNG）。

原理：
  1. 用标准库将内容排版为 ASS 字幕文件（libass 格式，含背景矩形、圆角标签、
     装饰线等全部图形元素；文字自动按近似宽度换行）。
  2. 调用 ffmpeg 的 ass filter（libass）渲染单帧为 PNG。
     （本机 ffmpeg 无 librsvg/drawtext，但 libass 可用——已验证。）
  3. 可选 --to-photos：渲染后经 osascript 导入 macOS 系统相册。

默认风格：白底黑字（light 主题），1080×1920（9:16，手机屏幕比例）。

用法：
  python3 generate_card.py --config card.json
  python3 generate_card.py --book "尖叫的数学" --chapter "第三章 发现无理数" \\
      --title "一桩逻辑上的丑闻" --story "……" --quote "……" --tag 无理数 --tag 逻辑

--config JSON 字段：
  book/chapter/title/story/quote/tags(数组)/theme/out/size/to_photos/figure
  figure：配图类型 "parabola"/"sqrt2"/"circle"/"numberline" 或 {"type": "parabola"}
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from math import cos, sin

# 字体必须能被 fontconfig 解析（fc-match 可查）；"PingFang SC" 未被 fontconfig
# 索引，libass 会回退到 Verdana 导致中文全部渲染为空心方框（乱码）。
FONT = "Heiti SC"

# 基准画布 1080×1920（9:16 手机屏幕）；布局按此基准设计，--size 自定义时按比例缩放
BASE_W, BASE_H = 1080, 1920

# 主题：bg 背景色 / accent 强调色（装饰线、金句文字）。
# 深底主题自动用白字；light（默认）白底黑字。bg 亮度自动决定正文用色。
THEMES = {
    "light":  dict(bg=(0xFF, 0xFF, 0xFF), accent=(0x39, 0x49, 0xAB)),
    "indigo": dict(bg=(0x39, 0x49, 0xAB), accent=(0xFF, 0xD5, 0x4F)),
    "deep":   dict(bg=(0x26, 0x32, 0x38), accent=(0x80, 0xDE, 0xEA)),
    "teal":   dict(bg=(0x00, 0x69, 0x6B), accent=(0xFF, 0xCC, 0x80)),
    "wine":   dict(bg=(0x8E, 0x24, 0x3A), accent=(0xEF, 0xBE, 0x8F)),
}
DEFAULT_THEME = "light"

# ---------------------------------------------------------------- 工具

def ass_ovr(rgb):
    """RGB 元组 → ASS override 颜色 &HBBGGRR（6 位、BGR、无 alpha；\1c 只接受 6 位）"""
    r, g, b = rgb
    return "&H%02X%02X%02X" % (b, g, r)


def ovr(rgb, alpha=None):
    """override 颜色前缀：{\\1c&HBBGGRR}；alpha 非空时追加 {\\1a&HAA&}。
    注意：ASS alpha 与常见约定相反（0x00 完全不透明，0xFF 完全透明）；
    drawing(\\p1) 下 \\alpha 会失效（图形不渲染），必须用 \\1a。"""
    s = "{\\1c%s}" % ass_ovr(rgb)
    if alpha is not None:
        s += "{\\1a&H%02X&}" % alpha
    return s


def esc(s):
    """转义 ASS 特殊字符（{} 与 \\）"""
    return s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def text_w(s, fs):
    """近似文本宽度：CJK=1em，ASCII≈0.55em"""
    w = 0.0
    for ch in s:
        w += 0.55 if ord(ch) < 128 else 1.0
    return w * fs


def wrap(s, max_px, fs):
    """按近似宽度换行，返回行列表（不切单词、不断 CJK）"""
    lines, cur = [], ""
    for ch in s:
        if text_w(cur + ch, fs) <= max_px:
            cur += ch
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def round_rect(x, y, w, h, r):
    """ASS Drawing 圆角矩形路径（三次贝塞尔近似）"""
    k = r * 0.5523
    return (
        f"m {x+r:.1f} {y:.1f}"
        f" l {x+w-r:.1f} {y:.1f}"
        f" b {x+w-r+k:.1f} {y:.1f} {x+w:.1f} {y+r-k:.1f} {x+w:.1f} {y+r:.1f}"
        f" l {x+w:.1f} {y+h-r:.1f}"
        f" b {x+w:.1f} {y+h-r+k:.1f} {x+w-r+k:.1f} {y+h:.1f} {x+w-r:.1f} {y+h:.1f}"
        f" l {x+r:.1f} {y+h:.1f}"
        f" b {x+r-k:.1f} {y+h:.1f} {x:.1f} {y+h-r+k:.1f} {x:.1f} {y+h-r:.1f}"
        f" l {x:.1f} {y+r:.1f}"
        f" b {x:.1f} {y+r-k:.1f} {x+r-k:.1f} {y:.1f} {x+r:.1f} {y:.1f}"
    )


def _ass_time(cs):
    """centiseconds → ASS 时间 h:mm:ss.cc（纯数字会被 libass 判为 Bad timestamp）"""
    h, rem = divmod(int(cs), 360000)
    m, rem = divmod(rem, 6000)
    s, cc = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cc:02d}"


def dialog(text, start=0, end=60000, layer=0):
    return f"Dialogue: {layer},{_ass_time(start)},{_ass_time(end)},Def,,0,0,0,,{text}"


# ---------------------------------------------------------------- ASS 排版

def build_ass(cfg, W, H):
    """返回完整 ASS 字符串。布局以 1080×1920 为基准，按实际画布比例缩放。
    注意：{\\pos(...)} 必须放在其作用的文本之前。"""
    theme = THEMES.get(cfg.get("theme", DEFAULT_THEME), THEMES[DEFAULT_THEME])
    bg, accent = theme["bg"], theme["accent"]
    # 深浅底自动适配文字色：深底→白字，浅底（light）→黑字
    is_dark = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2] < 150
    text = (0, 0, 0) if not is_dark else (0xFF, 0xFF, 0xFF)

    sx, sy = W / BASE_W, H / BASE_H   # 横向 / 纵向缩放
    ss = min(sx, sy)                  # 字号缩放（保比例，防变形）
    margin = 72 * sx
    maxw = W - 2 * margin

    lines = []
    add = lines.append

    # 全屏背景（layer=0）。注意：libass 中无 \\pos 的 drawing 事件会按"同 layer 内
    # 前序 drawing 的高度"累积下移，因此每个 drawing 事件必须独占一个 layer！
    # 图形 layer：背景0 / 装饰线1 / 标签2+i / 金句块10；文字 layer：正文50 / 标签金句51
    add(dialog(f"{{\\p1}}{ovr(bg)}"
               f"m 0 0 l {W} 0 l {W} {H} l 0 {H} l 0 0{{\\p0}}", layer=0))

    book = cfg.get("book", "").strip()
    chapter = cfg.get("chapter", "").strip()
    title = cfg.get("title", "").strip()
    story = cfg.get("story", "").strip()
    quote = cfg.get("quote", "").strip()
    tags = [t.strip() for t in cfg.get("tags", []) if t.strip()]

    # 1) 书名 + 章节（弱化色，左上角）
    if book:
        add(dialog(f"{{\\fs{28 * ss:.0f}}}{ovr(text, 0x4D)}{{\\b0}}"
                   f"{{\\pos({margin},{56 * sy})}}{esc(book)}", layer=50))
    if chapter:
        add(dialog(f"{{\\fs{22 * ss:.0f}}}{ovr(text, 0x66)}{{\\b0}}"
                   f"{{\\pos({margin},{100 * sy})}}{esc(chapter)}", layer=50))

    # 2) 大标题（主色粗体，自动换行 ≤2 行；超宽时缩小字号）
    ty = 170 * sy
    title_fs = 48 * ss
    title_lines = wrap(title, maxw, title_fs)
    while len(title_lines) > 2 and title_fs > 30 * ss:
        title_fs -= 2 * ss
        title_lines = wrap(title, maxw, title_fs)
    lh = title_fs * 1.4
    for i, ln in enumerate(title_lines):
        add(dialog(f"{{\\fs{title_fs:.0f}}}{ovr(text)}{{\\b1}}"
                   f"{{\\pos({margin},{ty + i * lh})}}{esc(ln)}", layer=50))
    title_bottom = ty + len(title_lines) * lh

    # 3) 装饰线（accent 色）
    add(dialog(f"{{\\p1}}{ovr(accent)}"
               f"{round_rect(margin, title_bottom + 30 * sy, 110 * sx, 5 * sy, 2 * ss)}{{\\p0}}",
               layer=1))

    # 4) 故事摘录（正文，自动换行，90% 主色）
    story_fs = 32 * ss
    story_top = title_bottom + 72 * sy
    bottom_reserve = 380 * sy  # 底部预留：标签 + 金句 + 下边距
    max_story_lines = int((H - bottom_reserve - story_top) / (story_fs * 1.5))
    story_lines = wrap(story, maxw, story_fs)
    if len(story_lines) > max_story_lines:
        story_fs = 28 * ss
        story_top = title_bottom + 68 * sy
        max_story_lines = int((H - bottom_reserve - story_top) / (story_fs * 1.5))
        story_lines = wrap(story, maxw, story_fs)
    if len(story_lines) > max_story_lines:
        print("警告：故事过长，建议压缩至约 %d 字，否则会与金句区重叠。"
              % max_story_lines, file=sys.stderr)
        story_lines = story_lines[:max_story_lines]
    lh_s = story_fs * 1.5
    for i, ln in enumerate(story_lines):
        add(dialog(f"{{\\fs{story_fs:.0f}}}{ovr(text, 0x1A)}{{\\b0}}"
                   f"{{\\pos({margin},{story_top + i * lh_s})}}{esc(ln)}", layer=50))
    story_bottom = story_top + len(story_lines) * lh_s

    # 4.5) 配图（可选）：位于故事下方、金句上方
    fig_top = story_bottom + 40 * sy
    fig_evs, fig_h = build_figure(cfg, W, sy, margin, fig_top, text, accent)
    for ev in fig_evs:
        add(ev)

    # 5) 底部：标签（贴底圆角矩形）+ 金句块（图/故事与标签之间垂直居中）
    tag_h, tag_fs = 52 * sy, 24 * ss
    pad_x, gap = 28 * sx, 18 * sx
    tag_bottom = H - 56 * sy
    tag_top = tag_bottom - tag_h
    tag_alpha = 0xB3 if is_dark else 0xE6      # 深底=白30% / 浅底=黑10%
    tag_text = bg if is_dark else (0, 0, 0)    # 标签文字：深底=主题深色 / 浅底=黑
    if tags:
        widths = [text_w(t, tag_fs) + 2 * pad_x for t in tags]
        total = sum(widths) + gap * (len(tags) - 1)
        cx = margin + (maxw - total) / 2
        for i, (t, tw) in enumerate(zip(tags, widths)):
            add(dialog(f"{{\\p1}}{ovr(text, tag_alpha)}"
                       f"{round_rect(cx, tag_top, tw, tag_h, tag_h / 2)}{{\\p0}}",
                       layer=2 + i))  # 每个标签独立 layer，避免 drawing 累积位移
            add(dialog(f"{{\\fs{tag_fs:.0f}}}{ovr(tag_text)}{{\\b1}}{{\\an5}}"
                       f"{{\\pos({cx + tw / 2},{tag_top + tag_h / 2})}}{esc(t)}",
                       layer=51))
            cx += tw + gap

    if quote:
        q_fs, q_pad = 34 * ss, 28 * sx
        q_maxw = maxw - 2 * q_pad
        q_lines = wrap(quote, q_maxw, q_fs)
        if len(q_lines) > 3:
            q_fs = 30 * ss
            q_lines = wrap(quote, q_maxw, q_fs)
        q_lh = q_fs * 1.45
        q_h = len(q_lines) * q_lh + 2 * q_pad
        # 金句区垂直范围：图/故事底部以下，到标签上方 ~56px；区域内垂直居中
        area_top = (fig_top + fig_h + 40 * sy) if fig_h else (story_bottom + 80 * sy)
        area_bottom = tag_top - 56 * sy
        avail = area_bottom - area_top
        if avail >= q_h:
            q_top = area_top + (avail - q_h) / 2
        else:
            q_top = area_bottom - q_h
            if q_top < story_bottom:
                print("警告：故事过长，金句区与故事区间距不足。", file=sys.stderr)
                q_top = max(q_top, story_bottom + 10 * sy)
        q_x, q_w = margin, maxw
        q_block_alpha = 0xD9 if is_dark else 0xF2  # 深底=白 15% / 浅底=黑 5%
        add(dialog(f"{{\\p1}}{ovr(text, q_block_alpha)}"
                   f"{round_rect(q_x, q_top, q_w, q_h, 16 * ss)}{{\\p0}}", layer=10))
        for i, ln in enumerate(q_lines):
            add(dialog(f"{{\\fs{q_fs:.0f}}}{ovr(accent)}{{\\b1}}{{\\an8}}"
                       f"{{\\pos({W / 2},{q_top + q_pad + i * q_lh + q_fs * 0.55})}}{esc(ln)}",
                       layer=51))

    return lines


# ---------------------------------------------------------------- 配图（figure）

# 图中 drawing 事件从 layer 20 起递增（每个 drawing 独占 layer 防累积位移）；
# 标注文字用 layer 51（与金句/标签文字同层，保证在图之上）
FIG_LAYER0 = 20


def _fig_line(pts, color, lw=3, layer=FIG_LAYER0):
    """折线 → 填充多边形模拟线宽（沿法向偏移 lw/2 生成带状闭合路径）。

    不用 \\bord 轮廓方案：开放折线会被 libass 自动闭合，闭合边被描边产生
    多余横线（如抛物线两端点间的顶部直线伪影）。"""
    hw = lw / 2.0
    n = len(pts)
    if n < 2:
        return None
    left, right = [], []
    for i in range(n):
        if i == 0:
            dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
        elif i == n - 1:
            dx, dy = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        L = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / L * hw, dx / L * hw
        left.append((pts[i][0] + nx, pts[i][1] + ny))
        right.append((pts[i][0] - nx, pts[i][1] - ny))
    p = f"m {left[0][0]:.1f} {left[0][1]:.1f}" + "".join(
        f" l {x:.1f} {y:.1f}" for x, y in left[1:])
    p += "".join(f" l {x:.1f} {y:.1f}" for x, y in reversed(right))
    return dialog(f"{{\\p1}}{ovr(color)}{p}{{\\p0}}", layer=layer)


def _fig_label(text, x, y, fs, color, layer=51, anchor=None):
    """图内文字标注（\\pos 文本，不受 drawing 位移影响）"""
    an = f"{{\\an{anchor}}}" if anchor else ""
    return dialog(f"{{\\fs{fs}}}{ovr(color)}{an}{{\\pos({x},{y})}}{esc(text)}",
                  layer=layer)


def _fig_parabola(fx, fy, fw, fh, text_col, accent):
    """抛物线 y = ax²：坐标轴 + 曲线 + 顶点标注。逻辑 x∈[-3,3], y∈[0,9]。"""
    evs = []
    layer = FIG_LAYER0
    a = 1.0
    axis_c = (0x9E, 0x9E, 0x9E) if text_col == (0, 0, 0) else (0xB0, 0xB0, 0xB0)

    def px(lx):
        return fx + (lx + 3) / 6.0 * fw

    def py(ly):
        return fy + fh - ly / 9.0 * fh

    # 横轴（y=0 底部）与纵轴（x=0 中线）
    y0, x0 = py(0), px(0)
    evs.append(_fig_line([(fx, y0), (fx + fw, y0)], axis_c, 2, layer)); layer += 1
    evs.append(_fig_line([(x0, fy), (x0, fy + fh)], axis_c, 2, layer)); layer += 1
    # 曲线 y = x²（采样 40 点）
    pts = [(px(lx), py(a * lx * lx)) for lx in
           (i * 6.0 / 39 - 3 for i in range(40))]
    evs.append(_fig_line(pts, accent, 4, layer)); layer += 1
    # 标注
    evs.append(_fig_label("y = x²", px(2.1), py(4.6), 18, accent, anchor=5))
    evs.append(_fig_label("顶点 (0,0)", x0 + 8, y0 + 8, 16, text_col, anchor=7))
    evs.append(_fig_label("开口向上", px(2.6), py(1.4), 16, text_col, anchor=5))
    return evs


def _fig_sqrt2(fx, fy, fw, fh, text_col, accent):
    """单位正方形 + 对角线（勾股/√2）。"""
    evs = []
    layer = FIG_LAYER0
    s = min(fw, fh) * 0.5
    cx, cy = fx + fw / 2, fy + fh / 2
    x0, y0 = cx - s / 2, cy - s / 2
    x1, y1 = cx + s / 2, cy + s / 2
    axis_c = (0x9E, 0x9E, 0x9E) if text_col == (0, 0, 0) else (0xB0, 0xB0, 0xB0)
    sq = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    evs.append(_fig_line(sq, text_col, 3, layer)); layer += 1
    evs.append(_fig_line([(x0, y0), (x1, y1)], accent, 3, layer)); layer += 1
    evs.append(_fig_label("1", cx, y0 - 6, 16, axis_c, anchor=8))
    evs.append(_fig_label("1", x1 + 6, cy, 16, axis_c, anchor=4))
    evs.append(_fig_label("√2", x0 + 6, y1 + 8, 17, accent, anchor=7))
    return evs


def _fig_circle(fx, fy, fw, fh, text_col, accent):
    """圆 + 半径（π 相关）。"""
    evs = []
    layer = FIG_LAYER0
    cx, cy = fx + fw / 2, fy + fh / 2
    r = min(fw, fh) * 0.32
    axis_c = (0x9E, 0x9E, 0x9E) if text_col == (0, 0, 0) else (0xB0, 0xB0, 0xB0)
    pts = [(cx + r * cos(t), cy - r * sin(t)) for t in
           (i * 6.28318 / 63 for i in range(64))]
    evs.append(_fig_line(pts, accent, 3, layer)); layer += 1
    evs.append(_fig_line([(cx, cy), (cx + r, cy)], text_col, 2, layer)); layer += 1
    evs.append(_fig_label("r", cx + r / 2, cy - 8, 16, axis_c, anchor=8))
    evs.append(_fig_label("周长 C = 2πr", cx, cy - r - 14, 16, text_col, anchor=8))
    return evs


def _fig_numberline(fx, fy, fw, fh, text_col, accent):
    """数轴：自然数 ⊂ 整数 ⊂ 有理数 ⊂ 实数 ⊂ 复数（数系扩展示意）。"""
    evs = []
    layer = FIG_LAYER0
    cy = fy + fh * 0.55
    axis_c = (0x9E, 0x9E, 0x9E) if text_col == (0, 0, 0) else (0xB0, 0xB0, 0xB0)
    evs.append(_fig_line([(fx, cy), (fx + fw, cy)], axis_c, 3, layer)); layer += 1
    names = ["自然数", "整数", "有理数", "实数", "复数"]
    n = len(names)
    step = fw / n
    for i, nm in enumerate(names):
        xc = fx + step * (i + 0.5)
        evs.append(_fig_line([(xc, cy - 12), (xc, cy + 12)], axis_c, 2, layer)); layer += 1
        col = accent if i == n - 1 else text_col
        evs.append(_fig_label(nm, xc, cy + 26, 17, col, anchor=8))
    evs.append(_fig_label("数系不断扩展", fx + fw / 2, fy + 8, 16, accent, anchor=8))
    return evs


def _fig_permutation(fx, fy, fw, fh, text_col, accent):
    """根置换示意（伽罗瓦）：三个根 x1 x2 x3 的循环置换 → 对称结构 = 群。"""
    evs = []
    layer = FIG_LAYER0
    ys = fy + fh * 0.62
    n = 3
    gap = fw / (n + 1)
    xs = [fx + gap * (i + 1) for i in range(n)]

    def circ(x, y, r):
        return [(x + r * cos(t), y + r * sin(t))
                for t in (i * 6.28318 / 23 for i in range(24))]

    def arc(p1, p2, h):
        xa, ya = p1
        xb, yb = p2
        mx, my = (xa + xb) / 2, min(ya, yb) - h
        return [( (1 - t) ** 2 * xa + 2 * (1 - t) * t * mx + t ** 2 * xb,
                  (1 - t) ** 2 * ya + 2 * (1 - t) * t * my + t ** 2 * yb)
                for t in (i / 12 for i in range(13))]

    def arrow_tip(p, prev, size=11):
        dx, dy = p[0] - prev[0], p[1] - prev[1]
        L = (dx * dx + dy * dy) ** 0.5 or 1.0
        ux, uy = dx / L, dy / L
        px_, py_ = -uy, ux
        tip = (p[0] + ux * size * 1.4, p[1] + uy * size * 1.4)
        b1 = (p[0] - ux * size * 0.4 + px_ * size * 0.7,
              p[1] - uy * size * 0.4 + py_ * size * 0.7)
        b2 = (p[0] - ux * size * 0.4 - px_ * size * 0.7,
              p[1] - uy * size * 0.4 - py_ * size * 0.7)
        return _fig_line([tip, b1, b2, tip], accent, 2, layer)

    # 三个根（圆点 + 标签）
    for i, x in enumerate(xs):
        evs.append(_fig_line(circ(x, ys, 9), text_col, 2, layer)); layer += 1
        evs.append(_fig_label(f"x{i + 1}", x, ys + 26, 17, text_col, anchor=8))
    # 循环置换：x1→x2→x3（上拱），x3→x1（高拱跨越）
    p1, p2, p3 = (xs[0], ys), (xs[1], ys), (xs[2], ys)
    for a_, b_, h_ in [(p1, p2, 42), (p2, p3, 42), (p3, p1, 120)]:
        arc_pts = arc(a_, b_, h_)
        evs.append(_fig_line(arc_pts, accent, 3, layer)); layer += 1
        evs.append(arrow_tip(arc_pts[-1], arc_pts[-2]))
        layer += 1
    evs.append(_fig_label("根的置换构成「群」", fx + fw / 2, fy + 8, 17, accent, anchor=8))
    return evs


def _fig_jitu(fx, fy, fw, fh, text_col, accent):
    """鸡兔同笼·画图法：7 头先画 2 脚（黑）=14 脚，后 2 头添 2 脚（靛蓝）=18 脚。"""
    evs = []
    layer = FIG_LAYER0
    n = 7
    gap = fw / (n + 1)
    hy = fy + fh * 0.40

    def circ(x, y, r):
        return [(x + r * cos(t), y + r * sin(t))
                for t in (i * 6.28318 / 23 for i in range(24))]

    for i in range(n):
        x = fx + gap * (i + 1)
        evs.append(_fig_line(circ(x, hy, 10), text_col, 2, layer)); layer += 1
        # 每头先画 2 条脚（黑）
        for dx in (-5, 5):
            evs.append(_fig_line([(x + dx, hy + 10), (x + dx, hy + 36)],
                                 text_col, 2, layer)); layer += 1
        # 后 2 头（第 6、7 只）各添 2 条脚（靛蓝，表示"鸡变兔"）
        if i >= 5:
            for dx in (-12, 12):
                evs.append(_fig_line([(x + dx, hy + 10), (x + dx, hy + 36)],
                                     accent, 3, layer)); layer += 1
    evs.append(_fig_label("7 个头，先各画 2 只脚 = 14 只，还差 4 只",
                          fx + fw / 2, hy + 52, 16, text_col, anchor=8))
    evs.append(_fig_label("后 2 头各添 2 只（靛蓝）→ 18 只脚，即 5 鸡 2 兔",
                          fx + fw / 2, fy + fh - 12, 16, accent, anchor=8))
    return evs


def build_figure(cfg, W, sy, margin, fig_top, text_col, accent):
    """按 cfg.figure 生成配图事件。返回 (事件列表, 图高)。无图返回 ([], 0)。"""
    fig = cfg.get("figure")
    if not fig:
        return [], 0
    ftype = fig.get("type") if isinstance(fig, dict) else str(fig)
    fh = 300 * sy
    fx, fy, fw = margin, fig_top, W - 2 * margin
    makers = {
        "parabola": _fig_parabola,
        "sqrt2": _fig_sqrt2,
        "circle": _fig_circle,
        "numberline": _fig_numberline,
        "permutation": _fig_permutation,
        "jitu": _fig_jitu,
    }
    maker = makers.get(ftype)
    if maker is None:
        print(f"警告：未知 figure 类型 {ftype!r}（支持 {sorted(makers)}）", file=sys.stderr)
        return [], 0
    return maker(fx, fy, fw, fh, text_col, accent), fh


def ass_header(W, H):
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {W}\n"
        f"PlayResY: {H}\n"
        "WrapStyle: 0\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Def,{FONT},30,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        "0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )


def import_to_photos(path):
    """经 osascript 把图片导入 macOS「照片」App。首次会请求自动化权限。"""
    script = f'tell application "Photos" to import POSIX file "{path}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        print(f"已写入系统相册: {path}")
        return True
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", "replace").strip()
        print("写入相册失败:", err or e, file=sys.stderr)
        return False


# ---------------------------------------------------------------- 主流程

def render(cfg):
    size = cfg.get("size")
    if size:
        W, H = int(size[0]), int(size[1])
    else:
        W, H = BASE_W, BASE_H

    book = cfg.get("book", "未命名")
    title = cfg.get("title", "无标题")
    out = cfg.get("out") or os.path.join(
        cfg.get("out_dir", "cards"), f"{book}-{title}.png")
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)

    ass = ass_header(W, H) + "\n".join(build_ass(cfg, W, H)) + "\n"
    fd, ass_path = tempfile.mkstemp(suffix=".ass")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(ass)

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "lavfi", "-i", f"color=white:s={W}x{H}",
           "-vf", f"ass={ass_path}",
           "-frames:v", "1", "-update", "1", out]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("ffmpeg 渲染失败:", e, file=sys.stderr)
        sys.exit(1)
    finally:
        os.unlink(ass_path)
    print(f"已生成: {out} ({W}x{H})")

    if cfg.get("to_photos"):
        import_to_photos(os.path.abspath(out))


def main():
    ap = argparse.ArgumentParser(description="生成数学故事分享卡片 PNG")
    ap.add_argument("--config", help="JSON 配置文件路径")
    ap.add_argument("--book")
    ap.add_argument("--chapter")
    ap.add_argument("--title")
    ap.add_argument("--story")
    ap.add_argument("--quote")
    ap.add_argument("--tag", action="append", default=[])
    ap.add_argument("--theme", choices=list(THEMES), default=DEFAULT_THEME)
    ap.add_argument("--size", nargs=2, type=int, metavar=("W", "H"))
    ap.add_argument("--out", help="输出 PNG 路径")
    ap.add_argument("--out-dir", default="cards")
    ap.add_argument("--to-photos", action="store_true",
                    help="生成后导入 macOS 系统相册")
    ap.add_argument("--figure", help="配图类型：parabola / sqrt2 / circle / numberline，"
                                     "或 JSON 对象如 '{\"type\":\"parabola\"}'")
    args = ap.parse_args()

    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        cfg = {}
        for k in ("book", "chapter", "title", "story", "quote"):
            v = getattr(args, k)
            if v:
                cfg[k] = v
        cfg["tags"] = args.tag
        cfg["theme"] = args.theme
        if args.size:
            cfg["size"] = args.size
        if args.out:
            cfg["out"] = args.out
        else:
            cfg["out_dir"] = args.out_dir
        cfg["to_photos"] = args.to_photos
        if args.figure:
            try:
                cfg["figure"] = json.loads(args.figure)
            except json.JSONDecodeError:
                cfg["figure"] = args.figure
    render(cfg)


if __name__ == "__main__":
    main()
