---
name: "math-story-card"
description: "基于 /Users/shuise/math/sources 中的数学故事或方法，生成可分享的竖版图形卡片（PNG）。当用户要求『生成/制作一张数学卡片』『把某段故事做成卡片』『做一个分享图』且素材来自 sources 书库时触发。"
---

# math-story-card：数学故事分享卡片生成

把 `/Users/shuise/math/sources` 书库中的故事/方法提炼为**四要素**，排版为竖版 PNG 卡片（默认 1080×1920，9:16，白底黑字，适合手机屏幕），输出到 `/Users/shuise/math/cards/`，可选写入 macOS 系统相册。

## 触发时机

- 用户给出书名/章节/故事的文字描述，要求生成分享卡片
- 用户引用 sources 中的某个故事或方法，想做成一图分享
- 用户说"把这段做成卡片""做一张 XX 的图"

## 工作流

1. **确认素材**：若用户只给了书名+话题而未给文本，从 sources 书库检索原文摘录。书库映射见下文。若用户直接给出文字描述，直接进入第 2 步。
2. **识别内容类型**（决定提炼方式）：
   - **故事型**（数学史/人物/事件）：按**叙事弧**提炼——背景（何时·何人·何问题）→ 冲突/转折 → 结果 → 意义。story 必须有头有尾，不能只截取一段。
   - **方法型**（解题/思想方法）：按**思路链**提炼——要解决的问题 → 核心思路（一句话）→ 关键步骤（2–4 步）→ 结论/应用。story 要让人能照着思路走通。
3. **提炼四要素**：
   - `book` 来源书名（如"尖叫的数学"）
   - `chapter` 章节名（可选）
   - `title` 本卡标题（≤ 20 字，太长会自动缩字号）
   - `story` 按第 2 步类型组织（**建议 ≤ 120 字**，超过会截断并警告）：
     - 故事型：背景 → 转折 → 结局 → 意义
     - 方法型：问题 → 思路 → 关键步骤 → 结论
   - `quote` 一句话总结或金句（≤ 60 字，最多 3 行），提炼要点而非复述
   - `tags` 2–5 个知识点标签（如"无理数、勾股定理"）
4. **决定是否配图**（`figure` 字段）：
   - **内容涉及图形/函数/几何/数系/结构/流程时优先配图**，图与正文互补、不重复表达同一信息
   - 图类型与内容映射：
     - `parabola`：二次函数/抛物线 → 坐标轴 + y=x² 曲线 + 顶点/开口标注
     - `sqrt2`：勾股定理/无理数 → 单位正方形 + 对角线 + 1/√2 标注
     - `circle`：圆/π → 圆 + 半径 + C=2πr 标注
     - `numberline`：数系扩展 → 数轴 + 自然数⊂整数⊂有理数⊂实数⊂复数
   - 纯叙述/论证类内容可不配图
5. **生成**：调用 `scripts/generate_card.py`（JSON 配置或命令行参数均可，见下）。
6. **验收**：确认 PNG 生成、尺寸正确；有图时核对图形与标注到位（`--figure` 类型 × 内容匹配）；如需快速核对渲染，可用
   `ffmpeg -i out.png -vf "crop=W:H:x:y,signalstats,metadata=print" -f null -` 检查各区域亮度，
   或转 PPM 后按亮度打字符画目检布局。

## 素材库映射（/Users/shuise/math/sources）

| 书库 | 格式 | 说明 |
|---|---|---|
| `尖叫的数学/text/` | HTML | 数学史故事（0、无理数、π、虚数…），按 partXXXX 分节 |
| `烧掉数学书/text/` | HTML | 数学方法（导数、指数、极限…的直觉化讲解） |
| `简单逻辑学/text/` | HTML | 逻辑学方法与案例 |
| `数学的逻辑/xhtml/` | XHTML | 按 chapterXX 分章 |
| `魔鬼数学/textXXXXX.html` | HTML | 概率与决策 |
| `牛津通识读本/*.md` | Markdown | 含《数学（中文版）》等通识读物 |
| `用通俗方式解释复杂概念全14册/*.md` | Markdown | 通俗科普（哲学小史、物质的秘密等） |

HTML 书每个 part 开头有章节标题（`<h1 class="contents-title">` 目录、正文 `<h1>` 标题），抓取时先看目录页定位章节再取正文段落。

## 脚本用法

```bash
# 方式一：JSON 配置（推荐，便于多元素）
python3 .trae/skills/math-story-card/scripts/generate_card.py \
  --config card.json --out-dir cards

# card.json 字段：
# {"book":"尖叫的数学","chapter":"第三章 发现无理数","title":"一桩逻辑上的丑闻",
#  "story":"……","quote":"……","tags":["无理数","勾股定理"],
#  "theme":"light","size":[1080,1920],"to_photos":false,
#  "figure":"sqrt2","out":"cards/xxx.png"}
#   figure 可为类型名（"parabola"/"sqrt2"/"circle"/"numberline"）或
#   {"type":"parabola","a":1} 形式

# 方式二：命令行参数（--figure 配图可选；--to-photos 可选：写入系统相册）
python3 .trae/skills/math-story-card/scripts/generate_card.py \
  --book "尖叫的数学" --chapter "第三章" --title "标题" \
  --story "故事……" --quote "金句……" --tag 无理数 --tag 逻辑 \
  --theme light --figure sqrt2 --out-dir cards --to-photos
```

- 默认输出名：`{书名}-{标题}.png`；`--out` 可指定完整路径
- `--theme`：`light`（默认，白底黑字）/ `indigo`（深蓝）/ `deep`（墨黑）/ `teal`（青绿）/ `wine`（酒红）
- `--size W H`：自定义画布尺寸（布局按 1080×1920 基准比例缩放，改尺寸后需人工复核）
- `--figure`：配图类型 `parabola` / `sqrt2` / `circle` / `numberline`（也可传 JSON，如 `'{"type":"parabola"}'`）
- `--to-photos`：渲染后经 osascript 导入 macOS「照片」App（首次会请求自动化权限）

## 设计规范

- 尺寸 1080×1920（9:16 手机屏，可配置）；布局自上而下：书名+章节 → 大标题 → 强调色装饰线 → 故事正文 → **配图（可选，位于故事下方）** → 金句块（浅灰底圆角矩形，强调色字，在图/故事与标签间垂直居中）→ 底部圆角标签（贴底）
- 配色：`bg` 主题背景；**背景亮度自动决定用色**——light（默认）白底黑字：标题黑粗体、正文 90% 黑、书名 70% 黑、章节 60% 黑、装饰线/金句靛蓝 #3949ab、标签黑 10% 底 + 黑字；深色主题（indigo 等）自动白字：正文 90% 白、标签白 30% 底 + 主题深色字、金句块白 15% 底 + accent 金句
- 字体：Heiti SC（fontconfig 解析，`fc-match "Heiti SC"` 可查）。注意 **"PingFang SC" 不在 fontconfig 索引内**，用它 libass 会回退到 Verdana（纯拉丁字体），中文全部渲染成空心方框。可选字体：Heiti SC（黑体，默认）、Hiragino Sans GB、Songti SC、STSong

## 技术要点与坑（改脚本前必读）

生成链路：**Python 标准库排版 → ASS 字幕文件 → `ffmpeg` libass 渲染 PNG**。
本机 ffmpeg 无 librsvg（不能 SVG→PNG）、无 drawtext（只能 libass）。libass 可用（已实测）。

1. **ASS 时间**：Event 时间必须是 `h:mm:ss.cc`（如 `0:00:00.00`）；纯数字 `0,60000` 会被 libass 判为 "Bad timestamp"，事件整体跳过（表现为整图空白）。
2. **override 颜色 `\1c` 只接受 6 位 `&HBBGGRR`**（无 alpha、BGR 顺序）；Style 行里的颜色才是 8 位 `&HAABBGGRR`。混用会导致颜色解析失败回退为白（整图被白矩形覆盖）。
3. **alpha 语义相反**：ASS 中 alpha 越大越透明（0x00 不透明，0xFF 全透明）。
4. **drawing 上用 `\1a` 而非 `\alpha`**：`\p1` 绘图状态下 `\alpha` 会令图形整体不渲染；`\1a&HAA&`（主色 alpha）正常。
5. **`\pos(...)` 必须放在其作用的文本之前**（override 只作用于其后的文本）；否则文本按默认对齐堆在画布左上角。
6. **layer 层级**：layer 值大的在上层；**同 layer 内先出现的事件渲染在上层**（libass 行为），所以全屏背景矩形必须独占最低 layer（脚本用 0），装饰图形 layer=1，文字 layer=2/3，否则背景会盖住其它图形。
7. **drawing 累积位移（关键坑，踩过）**：无 `\pos` 的 drawing 事件，其绘制原点会按**同 layer 内前序 drawing 事件的路径高度**累积下移（第 i 个事件偏移 = Σ 前 i-1 个事件高度）；带 `\pos` 的 drawing 事件则**完全不渲染**（libass 0.17 行为）。因此**每个 drawing 事件必须独占一个独立 layer**（背景0/装饰线1/标签2+i/金句块10；文字统一 layer 50/51）。文字事件用 \pos 无此问题。
8. 换行是脚本预计算的（CJK=1em、ASCII≈0.55em 近似），libass 不做自动换行；story/quote 过长会按区域上限截断并打印警告。
9. 验证命令速查：`sips -g pixelWidth -g pixelHeight <png>` 查尺寸；
   signalstats 分区域看 YMIN/YAVG/YMAX 判断元素是否在位。参考：light 主题白底 YAVG≈235、黑字 YMIN≈16、靛蓝金句≈83；深色主题背景≈83、标题白≈235。
10. **字体必须是 fontconfig 可解析的中文字体**（`fc-match <名字>` 验证）；否则中文显示为方框。
   signalstats/字符画只能验证"有内容"，**验证不了字形是否正确**——改完必须用浏览器打开 PNG 目检，
   或对标题区域放大做像素字符画比对（notdef 方框的特征是每个字形都是相同的空心矩形）。
11. **验证字形**：生成后应打开 PNG 目检一次中文渲染；可用 browser 打开 `file:///...` 查看。
12. **light 主题 alpha**：浅底上用黑 alpha 时方向与直觉相反——"黑 5%/10%"= 不透明 5%/10% = 透明 95%/90% = `\1a&HF2&`/`\1a&HE6&`（0x00 不透明，0xFF 全透明）。
13. **配图绘制（figure）**：图内折线用**填充多边形模拟线宽**（沿法向偏移生成闭合带状路径），不要用 `\bord` 轮廓方案——开放折线会被 libass 自动闭合，闭合边被描边产生多余横线（抛物线两端点间伪影）。每个图内 drawing 事件也要独占 layer（脚本从 20 起递增）；图标注文字用 layer 51。新增图类型：在 `build_figure` 的 makers 注册一个 `_fig_xxx(fx,fy,fw,fh,text_col,accent)` 函数即可（fx/fy/fw/fh 为图区像素范围，逻辑坐标自行映射）。

## 验收清单

- [ ] PNG 已生成且尺寸正确
- [ ] 四要素齐全、无重叠截断（story 超长时脚本已警告）
- [ ] 可选：字符画目检布局（缩小转 PPM 按亮度映射）
