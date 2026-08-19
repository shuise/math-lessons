// 自助答疑后端：接收划词 + 课件上下文，调 DeepSeek API 返回解释
// Vercel Serverless Function（Node 运行时）
export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method Not Allowed' });
    return;
  }

  let body = {};
  try {
    body = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
  } catch (e) {
    body = {};
  }

  // API Key：优先用用户在前端配置的（feature.md），回退到服务端 env
  const key = ((body.apiKey || '').toString().trim()) || process.env.DEEPSEEK_API_KEY;
  if (!key) {
    res.status(500).json({ error: '未配置 API Key：请点击页面右上角 ⚙ 输入 DeepSeek API Key' });
    return;
  }

  const text = (body.text || '').replace(/\s+/g, ' ').trim();
  if (!text || text.length < 2 || text.length > 2000) {
    res.status(400).json({ error: '问题文本无效或过长' });
    return;
  }

  const ctx = body.context || {};
  const near = (ctx.nearText || '').slice(0, 1500);
  const chapter = (ctx.chapter || '').slice(0, 120);
  const pageTitle = (ctx.pageTitle || '').slice(0, 120);
  const history = Array.isArray(body.history) ? body.history.slice(-4) : [];
  // 年级：继承用户配置，未配置默认初三（feature.md）
  const grade = (body.grade || '').toString().trim() || '初三';

  const system =
    '你是一位面向' + grade + '（及以下年级）学生/零基础读者的高中数学讲解老师，必须用最生活化、最简单的语言讲解数学知识。' +
    '回答格式（必须严格遵守，三段式）：' +
    '第一段【真正的问题】用一句话（不超过30字）提炼读者问题描述背后真正想问的核心；问题本身已很明确时，直接用一句话确认它。' +
    '第二段【解答】控制在120~180字，只写3句话：第一句定义、第二句逻辑分析、第三句生活化示例。' +
    '第三段【深度引导】换行写"【深度引导】"，下面用无序列表给出 3 个继续深入的方向，' +
    '每项以"- "开头，写成一个可以直接追问的引导语（如"想知道……，可以问……"），让读者选择后继续提问。' +
    '其他规则：' +
    '1) 除以上三个标记外，不得使用其他小标题、序号、分点；不要客套话，不要复述题目。' +
    '2) 先结合读者提供的课件上下文；上下文与问题无关时，明确说一句后给通用解释。' +
    '3) 讲解深度必须符合读者年级：读者是' + grade + '，只允许使用该年级及以下能理解的概念和方法；' +
    '不得超纲（禁用切线放缩、空间向量坐标、概率全概率/条件概率、柯西不等式、极限与导数等超出该年级的内容）。' +
    '4) 输出简体中文；公式用 $...$ 内联表示。' +
    '5) 输出必须严格按以下结构：' +
    '【真正的问题】……' +
    '【解答】……' +
    '【深度引导】' +
    '- ……' +
    '- ……' +
    '- ……';

  const historyBlock = history.length
    ? history.map((h) => `[追问历史] 问：${h.q}\n答：${h.a}`).join('\n')
    : '';

  const user = [
    `页面：《${pageTitle}》（章节：${chapter}）`,
    `页面地址：${body.pageUrl || ''}`,
    ``,
    `课件上下文（就近段落）：`,
    near || '（未获取到，请给出通用解释）',
    ``,
    historyBlock ? `历史问答：\n${historyBlock}` : '',
    `读者划词提问：${text}`,
    ``,
    `请结合课件上下文给出通俗、逐步的解释，若涉及公式请用 Markdown 行内代码或公式写法表示。`
  ].join('\n');

  try {
    const r = await fetch('https://api.deepseek.com/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${key}`
      },
      body: JSON.stringify({
        model: 'deepseek-chat',
        messages: [
          { role: 'system', content: system },
          { role: 'user', content: user }
        ],
        stream: false,
        max_tokens: 320
      })
    });

    const data = await r.json();
    if (!r.ok) {
      res.status(502).json({ error: `AI 服务调用失败：${(data.error && data.error.message) || r.status}` });
      return;
    }
    const answer = (data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || '（无返回内容）';
    res.setHeader('Cache-Control', 'no-store');
    res.status(200).json({ answer });
  } catch (err) {
    res.status(500).json({ error: `AI 服务异常：${err.message}` });
  }
}
