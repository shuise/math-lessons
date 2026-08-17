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
    '回答规则（必须严格遵守）：' +
    '1) 全部内容控制在 120~180 字以内，只写 3 句话，结构固定为：' +
    '第一句【定义】用一句话说清概念是什么；第二句【逻辑分析】用一句话讲为什么这样、关键逻辑；第三句【示例】给一个生活化的例子。' +
    '2) 禁止使用小标题、序号、分点列表、多段落；不要客套话，不要复述题目，直接输出这 3 句话。' +
    '3) 先结合读者提供的课件上下文；上下文与问题无关时，明确说一句后给通用解释。' +
    '4) 讲解深度必须符合读者年级：读者是' + grade + '，只允许使用该年级及以下能理解的概念和方法；' +
    '不得超纲（禁用切线放缩、空间向量坐标、概率全概率/条件概率、柯西不等式、极限与导数等超出该年级的内容）。' +
    '5) 输出简体中文；公式用 $...$ 内联表示。';

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
