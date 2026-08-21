# 项目记忆 — /Users/shuise/math 数学课件系统

## 项目结构
- 根目录 `lessons/`：各科课件（逻辑 `logic/`、数学方法 `math-methods-unit/` 等），每个课件目录下 index.html 为入口
- `lessons/index.html`：课程列表页
- `lessons/style.css`：共享样式
- `课堂讨论.md`：课堂讨论记录文档（含「学生/讨论问题/分析过程/一句话总结」格式）
- 本地服务器：`python3 -m http.server 8643`，cwd `/Users/shuise/math`，预览 URL http://localhost:8643/

## 关键课件文件
- `lessons/logic/index.html`：逻辑课（命题/联结词/量词），16 道 quiz（q1–q16，answers 见文件底部脚本，题 12–16 权重 2 分，满分 21）
- `lessons/logic/comprehensive/index.html`：逻辑综合题推导，45 题（q1–q45），分节：综合/侦探推理/题型拓展/挑战题，挑战题（q35–q45）为较难；题目标题行首有 `.q-no` 序号 span（1.–45.，样式 #e65100 加粗）
- `lessons/logic/handle-problem/index.html`：如何处理难题（六步解题法），12 个例题（原 15 题，删 11、14 后 13，再删第 4 题后 12），每题 `.example` + `.toggle-btn` 切换 `.ex-steps/.ex-result`，含 `.why`/`.why-ans` 教学高亮，脚本用 querySelectorAll+classList
- `lessons/math-methods-unit/methods/index.html`：18 题计分（逻辑推理 8 + 代数变形 10，segmentRanges=[[0,7],[8,17]]），含"问题空间"引导块（L320-337）
- `lessons/math-methods-unit/thinking/index.html`：22 题 7 段计分（data-idx 0–21）
- `lessons/logic/science-thinking/index.html`：思维训练课（科学与批判性思维，7 节，含 topbar 导航与时间进度）
- `lessons/complex-numbers/index.html`：复数课（数系扩展/复数概念/几何意义/四则运算/共轭/三角形式/综合练习，14 单选 + 5 综合题）。3.1 复平面图带**绕原点旋转交互（任意角度）**：角度输入框 `#rotAngle`（默认 90、step=any）+ 逆时针/顺时针/复位三按钮（onclick rotateZ(dir)/resetZ），rotateZ 用三角函数 a'=a·cosθ−b·sinθ、b'=a·sinθ+b·cosθ 累计叠加；SVG 元素 id = zPoint/zLabel/zProjX/zProjY，映射 (ox=200, oy=190, scale=45)；fmtComplex 保留 1 位小数、整数倍 90° 用 = 其余用 ≈、负数统一 Unicode 减号 −；标签 text-anchor 按点所在左右动态切换防溢出

## 用户硬性约定（重要）
1. 通信与 UI 均为简体中文；交互式课件参数变化需实时渲染
2. **不得超纲**：禁用切线放缩、空间向量坐标、概率（全概率/条件概率）、柯西不等式等超纲内容，需用朴素方法替代（均值不等式、平移法+余弦定理、三角换元+几何等）
3. 课件完成必须自检：GetDiagnostics 无错误 + 浏览器实测 + 提供简洁执行日志
4. 题目默认隐藏分析过程，按钮点击 toggle
5. **判题规则（所有习题/交互题，2026-08 确立）**：提交答案时只判断对错（正确绿/错误红，仅标记所选选项），**不直接给出正确答案**（正确选项不加 correct-opt、解析不自动展开）；每题必配「思路提示」「查看答案」双按钮，点击才显示对应内容。参考实现：logic-set-quiz 的 HINTS 对象 + initControls 自动注入按钮/hint 区 + toggleHint/toggleAns（查看答案时才标出正确选项）
6. **UI 规则（所有习题集/课件页面，2026-08 确立）**：整体白底（body/article 均 #fff，无阴影无圆角）；题卡去四周边框与内间距、只留底部 1px 边框（padding: 0 0 24px）；对错状态无背景色、仅用底部边框变色（correct 绿 #4caf50 / wrong 红 #f44336）；mobile（≤720px）article 左右留白约 12px、内容尽量显示完整；导航折行显示完整（flex-wrap: wrap、无 overflow-x: auto）。**已抽象到共享 style.css 的 `body.quizset` 块（选择器前缀 body.quizset）**，18 个习题集页只需 `<body class="quizset">` 即启用（已全部迁移，页面内不再有重复覆盖块）；讲解/讨论课不带 quizset 保持灰底白卡或新版式

## 技术要点与陷阱
- **style.css 四段结构（2026-08 微重构完成）**：① 基础骨架（body 920px 灰底 / article 白卡 / h1/h2/table/.example/.hint/.back/.tip/.keyword/.definition/.qa）；② 习题集模式 `body.quizset`（白底、题卡去四周边框只留底部 1px 边框、对错仅底部边框变色、@media 720px article padding 8px 12px）；③ 标准组件库 3.1–3.10（h4/.formula/.formula-box/.key-point/.note/.two-col/.compare-table/.quiz-question+question-card 全套/.q-tag 色板/.calc-card/.fill-input/.btn-check/评分组件 3.8=score-panel+quiz-footer+#scoreDisplay+.reset-btn/.diff-tag 四色/.comp-question）；④ 讨论课模板（course-meta/.topbar/section.sec c-1..c-7/.sec-head/.quote-box/.kw-card/.case-card/.interact/.end-box，强调色用 var(--accent, #3949ab)，页面 :root 覆盖）
- **style.css 冗余检查（2026-08-06）**：用 class 属性/classList/className 严格提取比对，已删 2 个未使用类——`.exercises`（仅注释提及）、`.three-col`（仅 part1/part4 media query 覆盖但页面无该元素），新增页面勿使用这两类（用则需自带定义）
- **内联 CSS 抽象规范（微重构判定标准）**：与共享逐字节等价的规则删除；页面特有/同名异义/异色覆盖（含带边框 vs 无边框的 diff-* 差异、margin/font-size/padding 数值差异）保留在页面内联 `<style>`，并在注释中注明「主样式由共享 style.css 提供，此处仅保留差异规则」。已清理页（均保留 `<link rel="stylesheet">` 指向 ../style.css 或 ../../style.css）：functions 系 / olympiad-exam / gaokao-exam / set-exam / set-func-exam / verify / math-methods-unit 系（thinking/exam/quiz-basic/methods/summary）/ logic 系（index/comprehensive/handle-problem/logic-set-quiz）。真实差异保留示例：thinking 的 .quiz-footer（margin 30px 0、score-box font-size 1.2em、btn-reset padding 8px 28px 均异于共享）；logic/index 的 .diff-tag 基（padding 1px 10px radius 10px）与 .diff-olym；set-func-exam 的 .diff-easy/.diff-medium（带边框版）与 .diff-olym（#e0f7fa 青）；mmu-exam 的 .diff-olym（渐变版）；comprehensive 的 .diff-hard（无边框版）
- **禁止触碰页面（含 20+ 处元素级 style 属性，无法抽象）**：3d-geometry(30)/probability(37)/statistics(29)/set-theory(85)/lessons-index(59)/part5(106)
- **遗留发现项（已解决）**：set-quiz/index.html 曾缺 stylesheet 引用，已于 2026-08-06 补 `<link rel="stylesheet" href="../style.css">`，quizset 风格（白底、题卡仅底部边框）已生效，实测通过
- **全站 UI 标准（2026-08 统一）**：920px 宽、灰底 #f5f7fa、白卡 article（radius 12 + padding 32px 40px + 阴影）、line-height 1.9、font-size 16px。已写入共享 style.css（body 原 1100px 白底 → 920px 灰底；`article1` 笔误已修正为 `article`）；12 个内联 body 页面 max-width 已同步 900/880→920px（verify/set-quiz/set-func-exam/set-exam/methods-exam/func-concept-quiz/triangle-function/all-function/olympiad-exam/gaokao-exam/func-types-quiz/functions-exam），methods/summary/handle-problem 依赖全局或已符合
- **习题集 UI 统一（2026-08，已迁移共享）**：统一规则已抽象到共享 style.css 的 `body.quizset` 块（含 6 类题卡选择器 .quiz-question/.question-card/.calc-card/.solve-card/.fill-card/.example + 无背景的对错状态 + mobile media）。18 个习题集页 body 均加 class="quizset"：logic-set-quiz / logic/comprehensive / logic/index.html / logic/handle-problem（.example）/ set-quiz / set-exam / set-func-exam / functions 系 7 页 / math-methods-unit 系（methods / thinking / quiz-basic / math-methods-unit/exam 含 .fill-card）/ verify（.calc-card）。新习题集页只需 `<body class="quizset">` 即可获得统一风格；方法讲解小卡 .example-card 保留原样式
- **导航折行规范**：所有讨论课 topbar 必须 `flex-wrap: wrap` + 无 `overflow-x: auto` + 无滚动居中 JS（science-thinking/decision/economics 已清理滚动居中块；proverbs/misconceptions 已是折行版）。science-thinking 本人是特例：body 无 padding + article 透明 + section.sec 白卡（新版式），其余页保持「灰底 + article 白卡」式样
- B 类交互课件（thinking/methods/comprehensive）：`.quiz-question` + `.opt[data-val]`（或 onclick checkChoice(id, idx)），`answers` 对象在脚本中定义；解析文本填入 .explain
- textContent 陷阱：数学比较符号必须用字面 `<`/`>`；题干 HTML 可解析 `&lt;` 实体
- comprehensive 页 checkChoice 用 onclick 属性（checkChoice(N, idx)），N 必须等于题块 id 数字；题目块 id 为 qN，explain id 为 explainN
- logic/index.html 2.4 节真值表为 .two-col 双表格并排（真/假 vs 1/0 四则运算：¬p=1−p、p∧q=p×q、p∨q=p+q−p×q），窄屏响应式降级单列
- 数学公式：logic 系用 MathJax（`\(...\)` 包裹），methods/thinking 系可能不同，遵循各文件现有惯例
- 浏览器验证：browser_use 子代理；browser_evaluate 返回值不可用，需 console.log + console_messages，或写 document.title 经 snapshot 读取；脚本用 IIFE/function 表达式（避免裸函数表达式语法错误）

## 已知外部干扰
- lessons/logic/index.html 的 L343 区域曾被外部（IDE 手动编辑）反复覆盖（two-col → two-col2 → 裸 div），需在改动后立即 grep/curl 复核持久性；curl 走 --noproxy '*' 避免代理缓存，带 ?t=时间戳 绕缓存

## 会话习惯
- 用户会用"检查修复""改进""删除 X 题"等指令迭代课件；改题量/重编号后必须 grep 验证编号连续唯一、answers 键数与题数一致
