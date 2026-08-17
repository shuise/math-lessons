/* 自助答疑：划词 → 「答疑」→ 内嵌解释框（多轮追问，不弹层）
 * 历史存 localStorage（按页面路径），右下角气泡带角标可随时回看
 * 由 scripts/build.sh 注入到 public/ 下所有 HTML，源课件（math/）零改动 */
(function () {
  'use strict';
  if (window.__QA_INIT__) return;
  window.__QA_INIT__ = true;

  var API = '/api/qa';
  var MAX_SEL = 800;       // 划词长度上限
  var MAX_CONTEXT = 1500;  // 上下文截取长度
  var MAX_HISTORY = 10;    // 每页保留的问答条数

  /* ---- 设置（API Key + 年级）---- */
  var CONFIG_KEY = 'qa:config';
  var GRADES = ['初一', '初二', '初三', '高一', '高二', '高三'];
  var DEFAULT_GRADE = '初三';
  var settingsBtn = null;  // 右上角设置入口（跳过后收缩于此）
  var overlay = null;      // 设置层
  var cfg = loadConfig();

  function loadConfig() {
    try {
      var c = JSON.parse(localStorage.getItem(CONFIG_KEY) || 'null');
      if (c && c.apiKey) {
        return {
          apiKey: String(c.apiKey),
          grade: GRADES.indexOf(c.grade) >= 0 ? c.grade : DEFAULT_GRADE
        };
      }
    } catch (e) { /* ignore */ }
    return null;
  }
  function saveConfig(apiKey, grade) {
    cfg = { apiKey: apiKey, grade: grade };
    try { localStorage.setItem(CONFIG_KEY, JSON.stringify(cfg)); } catch (e) { /* ignore */ }
    // 同一会话内立即刷新右上角按钮外观（若已创建）
    if (settingsBtn) {
      settingsBtn.style.background = 'linear-gradient(135deg,#1a73e8,#0f5fd1)';
      settingsBtn.style.color = '#fff';
      settingsBtn.title = '答疑设置（' + maskKey(cfg.apiKey) + '）';
    }
  }
  function maskKey(k) {
    return k.length > 8 ? k.slice(0, 4) + '…' + k.slice(-4) : '已保存';
  }

  /* ---------- 设置层（模态） ---------- */
  function buildSettings() {
    if (overlay) return;
    overlay = document.createElement('div');
    css(overlay, {
      position: 'fixed', inset: '0', zIndex: 2147483200,
      background: 'rgba(20,28,40,.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center'
    });
    overlay.innerHTML =
      '<div style="background:#fff;border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.3);padding:26px 30px;width:min(440px,calc(100vw - 40px));box-sizing:border-box;font:14px/1.7 system-ui,\'PingFang SC\',sans-serif;color:#222;">' +
        '<h2 style="margin:0 0 4px;font-size:18px;">⚙️ 自助答疑设置</h2>' +
        '<p style="margin:0 0 14px;color:#888;font-size:13px;">输入 DeepSeek API Key（仅支持 DeepSeek），并选择你目前的年级，答疑将按对应水平讲解。</p>' +
        '<label style="display:block;margin-bottom:6px;color:#555;">API Key</label>' +
        '<input class="qa-key" type="password" placeholder="sk-…（DeepSeek）" autocomplete="off" style="width:100%;box-sizing:border-box;border:1px solid #ccd4e0;border-radius:8px;padding:8px 10px;font:14px inherit;margin-bottom:12px;">' +
        '<label style="display:block;margin-bottom:6px;color:#555;">目前年级</label>' +
        '<select class="qa-grade" style="width:100%;box-sizing:border-box;border:1px solid #ccd4e0;border-radius:8px;padding:8px 10px;font:14px inherit;margin-bottom:18px;">' +
          GRADES.map(function (g) { return '<option value="' + g + '">' + g + '</option>'; }).join('') +
        '</select>' +
        '<div style="display:flex;gap:10px;justify-content:flex-end;">' +
          '<button class="qa-skip" style="background:#f2f4f7;color:#555;border:none;border-radius:8px;padding:8px 16px;font-size:14px;cursor:pointer;">跳过</button>' +
          '<button class="qa-save" style="background:#1a73e8;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:14px;cursor:pointer;">保存</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    var inp = overlay.querySelector('.qa-key');
    var sel = overlay.querySelector('.qa-grade');
    if (cfg) { inp.value = cfg.apiKey; sel.value = cfg.grade; }
    overlay.querySelector('.qa-save').addEventListener('click', function () {
      var k = inp.value.replace(/\s+/g, '').trim();
      if (!k) { showToast('请输入 DeepSeek API Key'); inp.focus(); return; }
      saveConfig(k, sel.value);
      closeSettings();
      showToast('配置已保存：' + sel.value + ' · ' + maskKey(k));
    });
    overlay.querySelector('.qa-skip').addEventListener('click', closeSettings);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closeSettings(); });
  }
  function closeSettings() {
    if (!overlay) return;
    overlay.remove();
    overlay = null;
    ensureSettingsBtn();
  }

  /* ---------- 右上角设置入口 ---------- */
  function ensureSettingsBtn() {
    if (settingsBtn) return;
    settingsBtn = document.createElement('div');
    settingsBtn.textContent = '⚙';
    css(settingsBtn, {
      position: 'fixed', top: '12px', right: '12px', zIndex: 2147483000,
      width: '34px', height: '34px', borderRadius: '50%', cursor: 'pointer',
      background: cfg ? 'linear-gradient(135deg,#1a73e8,#0f5fd1)' : '#f2f4f7',
      color: cfg ? '#fff' : '#666', fontSize: '16px', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
      boxShadow: '0 2px 8px rgba(0,0,0,.18)',
      fontFamily: 'system-ui,"PingFang SC",sans-serif', userSelect: 'none',
      border: '1px solid #e0e4ea'
    });
    settingsBtn.title = cfg ? '答疑设置（' + maskKey(cfg.apiKey) + '）' : '答疑设置（未配置，点击配置）';
    document.body.appendChild(settingsBtn);
    settingsBtn.addEventListener('click', buildSettings);
  }

  var askBtn = null;   // 划词后的浮动「答疑」按钮
  var bubble = null;   // 右下角气泡（历史角标）
  var panel = null;    // 内嵌解释框
  var toast = null;    // 气泡提示
  var inflight = false;
  var inflightQ = '';
  var curHistory = loadHistory();

  function css(el, obj) { for (var k in obj) el.style[k] = obj[k]; }
  function keyOf() { return 'qa:' + location.pathname; }
  function loadHistory() {
    try { return JSON.parse(localStorage.getItem(keyOf()) || '[]'); } catch (e) { return []; }
  }
  function saveHistory() {
    try { localStorage.setItem(keyOf(), JSON.stringify(curHistory.slice(-MAX_HISTORY))); } catch (e) { /* ignore */ }
  }

  /* ---------- 右下角气泡 ---------- */
  function buildBubble() {
    bubble = document.createElement('div');
    bubble.textContent = '答疑';
    css(bubble, {
      position: 'fixed', right: '18px', bottom: '18px', zIndex: 2147483000,
      width: '56px', height: '56px', borderRadius: '50%',
      background: 'linear-gradient(135deg,#1a73e8,#0f5fd1)', color: '#fff',
      fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center',
      cursor: 'pointer', boxShadow: '0 4px 14px rgba(0,0,0,.3)',
      fontFamily: 'system-ui,"PingFang SC",sans-serif', userSelect: 'none'
    });
    var badge = document.createElement('span');
    css(badge, {
      position: 'absolute', top: '-3px', right: '-3px', minWidth: '18px', height: '18px',
      borderRadius: '9px', background: '#e53935', color: '#fff', fontSize: '11px',
      lineHeight: '18px', textAlign: 'center', padding: '0 4px', display: 'none',
      boxSizing: 'border-box'
    });
    bubble.appendChild(badge);
    document.body.appendChild(bubble);
    bubble.addEventListener('click', togglePanel);
    updateBadge();
  }
  function updateBadge() {
    if (!bubble) return;
    var badge = bubble.querySelector('span');
    var n = curHistory.length;
    badge.style.display = n > 0 ? 'block' : 'none';
    badge.textContent = n > 99 ? '99+' : String(n);
  }

  /* ---------- 划词按钮 ---------- */
  function makeAskBtn() {
    askBtn = document.createElement('div');
    askBtn.textContent = '答疑';
    css(askBtn, {
      position: 'fixed', zIndex: 2147483000, display: 'none',
      background: '#1a73e8', color: '#fff', border: 'none',
      borderRadius: '18px', padding: '6px 14px', fontSize: '14px',
      cursor: 'pointer', boxShadow: '0 2px 10px rgba(0,0,0,.28)',
      fontFamily: 'system-ui, "PingFang SC", sans-serif', userSelect: 'none'
    });
    document.body.appendChild(askBtn);
    askBtn.addEventListener('mousedown', function (e) { e.preventDefault(); e.stopPropagation(); });
    askBtn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      hideAskBtn();
      ask(lastText);
    });
  }
  var lastText = '';
  function onMouseUp() {
    var sel = window.getSelection();
    var text = sel ? sel.toString().replace(/\s+/g, ' ').trim() : '';
    if (!text || text.length < 2 || text.length > MAX_SEL) { hideAskBtn(); return; }
    lastText = text;
    var r = sel.getRangeAt(0).getBoundingClientRect();
    var left = Math.min(r.left + r.width / 2 - 30, window.innerWidth - 96);
    var top = r.top < 44 ? r.bottom + 8 : r.top - 42;
    css(askBtn, { display: 'block', left: Math.max(6, left) + 'px', top: top + 'px' });
  }
  function hideAskBtn() { if (askBtn) askBtn.style.display = 'none'; }

  /* ---------- 上下文收集 ---------- */
  function gatherContext() {
    var h1 = document.querySelector('h1');
    var h2 = document.querySelector('h2');
    var sel = window.getSelection();
    var near = '';
    if (sel && sel.rangeCount) {
      var node = sel.getRangeAt(0).commonAncestorContainer;
      var el = node.nodeType === 3 ? node.parentElement : node;
      while (el && el !== document.body && !/^(P|LI|TD|DIV|SECTION|ARTICLE)$/.test(el.tagName)) {
        el = el.parentElement;
      }
      if (el) near = el.textContent.replace(/\s+/g, ' ').trim().slice(0, MAX_CONTEXT);
    }
    return {
      pageTitle: document.title,
      pageUrl: location.href,
      chapter: h2 ? h2.textContent.trim() : (h1 ? h1.textContent.trim() : ''),
      nearText: near
    };
  }

  /* ---------- 内嵌解释框 ---------- */
  function positionPanel() {
    // 宽度：手机端 90% 居中，PC 600px 右下角
    var mobile = window.matchMedia('(max-width: 767px)').matches;
    if (mobile) {
      css(panel, { left: '5%', right: '5%', width: '90%' });
    } else {
      css(panel, { left: 'auto', right: '14px', width: '600px' });
    }
  }
  function buildPanel() {
    panel = document.createElement('div');
    css(panel, {
      position: 'fixed', bottom: '84px', zIndex: 2147483000,
      maxHeight: '70vh',
      background: '#fff', borderRadius: '12px', boxShadow: '0 8px 32px rgba(0,0,0,.25)',
      display: 'none', flexDirection: 'column', overflow: 'hidden',
      font: '14px/1.7 system-ui,"PingFang SC",sans-serif', color: '#222',
      border: '1px solid #e3e8f0'
    });
    positionPanel();
    panel.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:#f4f7fb;border-bottom:1px solid #e8edf5;">' +
        '<strong style="font-size:15px;">📖 自助答疑</strong>' +
        '<span class="qa-min" title="收起" style="cursor:pointer;font-size:20px;color:#888;line-height:1;">&minus;</span>' +
      '</div>' +
      '<div class="qa-list" style="flex:1;overflow:auto;padding:12px 14px;min-height:120px;"></div>' +
      '<div style="padding:10px 12px;border-top:1px solid #e8edf5;display:flex;gap:8px;">' +
        '<textarea class="qa-input" rows="1" placeholder="继续提问，回车发送…" style="flex:1;box-sizing:border-box;border:1px solid #ccd4e0;border-radius:8px;padding:7px 10px;font:14px/1.5 inherit;resize:none;"></textarea>' +
        '<button class="qa-send" style="background:#1a73e8;color:#fff;border:none;border-radius:8px;padding:0 16px;font-size:14px;cursor:pointer;white-space:nowrap;">发送</button>' +
      '</div>';
    document.body.appendChild(panel);
    panel.querySelector('.qa-min').addEventListener('click', function (e) {
      e.stopPropagation();
      togglePanel();
    });
    var input = panel.querySelector('.qa-input');
    function send() {
      var q = input.value.replace(/\s+/g, ' ').trim();
      if (!q) return;
      input.value = '';
      ask(q);
    }
    panel.querySelector('.qa-send').addEventListener('click', send);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });
  }
  function togglePanel() {
    if (!panel) buildPanel();
    var show = panel.style.display === 'none';
    panel.style.display = show ? 'flex' : 'none';
    if (show) renderList();
  }
  function renderList() {
    var list = panel.querySelector('.qa-list');
    list.innerHTML = '';
    if (!curHistory.length && !inflight) {
      list.innerHTML = '<p style="color:#999;text-align:center;margin:28px 12px;line-height:2;">划选课件内容，点「答疑」提问；<br>回答会保存在本地，可随时回看。</p>';
      return;
    }
    curHistory.forEach(function (it, i) {
      list.appendChild(itemNode(it, i === curHistory.length - 1));
    });
    if (inflight) list.appendChild(loadingNode(inflightQ));
    list.scrollTop = list.scrollHeight;
  }
  function itemNode(it, isLast) {
    var wrap = document.createElement('div');
    wrap.style.marginBottom = '12px';
    var q = document.createElement('div');
    q.textContent = '问：' + it.q;
    q.style.cssText = 'background:#eef4fe;border-radius:8px;padding:6px 10px;margin-bottom:6px;color:#1a3d6e;';
    wrap.appendChild(q);
    var a = document.createElement('div');
    a.innerHTML = mdToHtml(it.a);
    wrap.appendChild(a);
    if (MATH_RE.test(it.a)) {
      ensureMathJax(function () {
        try { MathJax.typesetPromise([a]); } catch (e) { /* ignore */ }
      });
    }
    return wrap;
  }
  function loadingNode(q) {
    var item = document.createElement('div');
    item.style.marginBottom = '12px';
    item.innerHTML = '<div style="background:#eef4fe;border-radius:8px;padding:6px 10px;margin-bottom:6px;color:#1a3d6e;">问：' + escapeHtml(q) + '</div>' +
      '<div class="qa-loading" style="color:#888;">AI 正在用「定义 → 逻辑分析 → 示例」讲解…</div>';
    return item;
  }

  /* ---------- 提问 ---------- */
  // 直连 DeepSeek（纯静态服务器下 /api/qa 不可用时的兜底）
  function buildSystemPrompt(grade) {
    return '你是一位面向' + grade + '（及以下年级）学生/零基础读者的高中数学讲解老师，必须用最生活化、最简单的语言讲解数学知识。' +
      '回答规则（必须严格遵守）：' +
      '1) 全部内容控制在 120~180 字以内，只写 3 句话，结构固定为：' +
      '第一句【定义】用一句话说清概念是什么；第二句【逻辑分析】用一句话讲为什么这样、关键逻辑；第三句【示例】给一个生活化的例子。' +
      '2) 禁止使用小标题、序号、分点列表、多段落；不要客套话，不要复述题目，直接输出这 3 句话。' +
      '3) 先结合读者提供的课件上下文；上下文与问题无关时，明确说一句后给通用解释。' +
      '4) 讲解深度必须符合读者年级：读者是' + grade + '，只允许使用该年级及以下能理解的概念和方法；不得超纲。' +
      '5) 输出简体中文；公式用 $...$ 内联表示。';
  }
  function askDirect(text, ctx, history) {
    if (!cfg || !cfg.apiKey) {
      return Promise.reject(new Error('未配置 API Key：请点击页面右上角 ⚙ 输入 DeepSeek API Key'));
    }
    var grade = cfg.grade || DEFAULT_GRADE;
    var user = [
      '页面：《' + document.title + '》（章节：' + (ctx.chapter || '') + '）',
      '页面地址：' + location.href,
      '',
      '课件上下文（就近段落）：',
      ctx.nearText || '（未获取到，请给出通用解释）',
      '',
      history.length ? '历史问答：\n' + history.map(function (h) {
        return '[追问历史] 问：' + h.q + '\n答：' + h.a;
      }).join('\n') : '',
      '读者划词提问：' + text,
      '',
      '请结合课件上下文给出通俗、逐步的解释，若涉及公式请用 Markdown 行内代码或公式写法表示。'
    ].join('\n');
    return fetch('https://api.deepseek.com/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + cfg.apiKey },
      body: JSON.stringify({
        model: 'deepseek-chat',
        messages: [
          { role: 'system', content: buildSystemPrompt(grade) },
          { role: 'user', content: user }
        ],
        stream: false,
        max_tokens: 320
      })
    })
      .then(function (res) {
        return res.text().then(function (txt) {
          var d = null;
          try { d = JSON.parse(txt); } catch (e) { /* 非 JSON */ }
          if (!res.ok || !d || d.error) {
            throw new Error('HTTP ' + res.status +
              ((d && d.error && d.error.message) ? '：' + d.error.message : ''));
          }
          return (d.choices && d.choices[0] && d.choices[0].message && d.choices[0].message.content) || '（无返回内容）';
        });
      });
  }

  function ask(text) {
    if (!panel) buildPanel();
    panel.style.display = 'flex';
    var list = panel.querySelector('.qa-list');
    // 有历史时先渲染历史，再在末尾追加本次问题
    if (!list.children.length) renderList();
    var item = loadingNode(text);
    list.appendChild(item);
    list.scrollTop = list.scrollHeight;
    inflight = true;
    inflightQ = text;
    var ctx = gatherContext();

    function renderAnswer(answer, direct) {
      inflight = false;
      curHistory.push({ q: text, a: answer, t: Date.now() });
      saveHistory();
      updateBadge();
      var el = item.querySelector('.qa-loading');
      if (el) {
        el.className = '';
        el.innerHTML = mdToHtml(answer);
        if (MATH_RE.test(answer)) {
          ensureMathJax(function () {
            try { MathJax.typesetPromise([el]); } catch (e) { /* ignore */ }
          });
        }
      }
      list.scrollTop = list.scrollHeight;
      showToast(direct ? '回答已保存（直连 DeepSeek）' : '回答已保存，点右下角气泡可随时回看');
    }
    function renderError(err) {
      inflight = false;
      var el = item.querySelector('.qa-loading');
      if (el) el.innerHTML = '<p style="color:#d32f2f;margin:0;">答疑失败：' + escapeHtml(err.message) + '</p>';
    }

    var req = { text: text, context: ctx, pageUrl: location.href, history: curHistory.slice(-4) };
    if (cfg) { req.apiKey = cfg.apiKey; req.grade = cfg.grade; }
    // 先走后端 /api/qa；失败（纯静态服务/后端异常）时兜底直连 DeepSeek
    fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    })
      .then(function (res) {
        // 容错：响应可能不是 JSON（如 404/501 文本），先取文本再尝试解析
        return res.text().then(function (txt) {
          var d = null;
          try { d = JSON.parse(txt); } catch (e) { /* 非 JSON */ }
          return { ok: res.ok, status: res.status, d: d, raw: txt };
        });
      })
      .then(function (r) {
        if (!r.ok || !r.d || r.d.error) {
          var isHtml = r.raw && r.raw.charAt(0) === '<';
          var reason = (r.d && r.d.error) ||
            ('HTTP ' + r.status + (r.raw && !isHtml ? '：' + r.raw.slice(0, 80) : ''));
          throw new Error(reason);
        }
        return r.d.answer;
      })
      .catch(function () { return askDirect(text, ctx, curHistory.slice(-4)).then(function (a) { return { a: a, d: true }; }); })
      .then(function (ans) {
        renderAnswer(ans.a, ans.d);
      })
      .catch(function (err) { renderError(err); });
  }

  /* ---------- 气泡提示 ---------- */
  function showToast(msg) {
    if (!toast) {
      toast = document.createElement('div');
      css(toast, {
        position: 'fixed', left: '50%', transform: 'translateX(-50%)', bottom: '90px',
        zIndex: 2147483100, background: 'rgba(0,0,0,.78)', color: '#fff',
        borderRadius: '8px', padding: '8px 16px', fontSize: '13px', maxWidth: '80vw',
        textAlign: 'center', fontFamily: 'system-ui,"PingFang SC",sans-serif',
        opacity: '0', transition: 'opacity .25s', pointerEvents: 'none'
      });
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = '1';
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { toast.style.opacity = '0'; }, 2600);
  }

  /* ---------- 轻量 Markdown 渲染 ---------- */
  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function inline(s) {
    s = s.replace(/`([^`]+)`/g, '<code style="background:#f0f0f0;padding:1px 5px;border-radius:4px;font-size:.92em;">$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, '$1<em>$2</em>');
    return s;
  }
  // 是否含数学公式（\( \) / \[ \] / $ $ / $$ $$ / \begin）
  var MATH_RE = /(?:\\\(|\\\[|\$\$?|\\begin\{)/;
  function ensureMathJax(cb) {
    if (window.MathJax && window.MathJax.typesetPromise) { cb(); return; }
    if (!window.MathJax) {
      window.MathJax = {
        tex: {
          inlineMath: [['\\(' , '\\)'], ['$', '$']],
          displayMath: [['\\[', '\\]'], ['$$', '$$']]
        }
      };
    }
    var s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js';
    s.async = true;
    s.onload = cb;
    s.onerror = function () { /* 加载失败时保持纯文本 */ };
    document.head.appendChild(s);
  }
  function mdToHtml(md) {
    md = escapeHtml(md).replace(/\r\n/g, '\n');
    var lines = md.split('\n');
    var html = '';
    var inCode = false, codeBuf = [], paraBuf = [], quoteBuf = [], tableBuf = [];
    var listOpen = false, olOpen = false;
    function splitRow(l) {
      return l.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(function (c) { return c.trim(); });
    }
    function isTableSep(l) {
      var cells = splitRow(l);
      return cells.length > 0 && cells.every(function (c) { return /^:?-+:?$/.test(c); });
    }
    function flushTable() {
      if (!tableBuf.length) return;
      var rows = tableBuf;
      var htmlT = '<table style="border-collapse:collapse;margin:10px 0;width:100%;font-size:14px;">';
      var startIdx = 0;
      if (rows.length >= 2 && isTableSep(rows[1])) {
        htmlT += '<thead><tr>' + splitRow(rows[0]).map(function (c) {
          return '<th style="border:1px solid #d0d7e2;padding:6px 10px;background:#f4f7fb;text-align:left;">' + inline(c) + '</th>';
        }).join('') + '</tr></thead>';
        startIdx = 2;
      }
      htmlT += '<tbody>';
      for (var i = startIdx; i < rows.length; i++) {
        htmlT += '<tr>' + splitRow(rows[i]).map(function (c) {
          return '<td style="border:1px solid #e0e5ee;padding:6px 10px;">' + inline(c) + '</td>';
        }).join('') + '</tr>';
      }
      htmlT += '</tbody></table>';
      html += htmlT;
      tableBuf = [];
    }
    function flushList() {
      if (listOpen) { html += '</ul>'; listOpen = false; }
      if (olOpen) { html += '</ol>'; olOpen = false; }
    }
    function flushQuote() {
      if (!quoteBuf.length) return;
      html += '<blockquote style="margin:8px 0;padding:6px 14px;border-left:3px solid #1a73e8;background:#f7fafd;color:#555;">'
        + quoteBuf.map(function (l) { return inline(l.replace(/^\s*&gt;\s?/, '').replace(/\s{2,}$/, '')); }).join('<br>')
        + '</blockquote>';
      quoteBuf = [];
    }
    function flushPara() {
      if (!paraBuf.length) return;
      html += '<p style="margin:8px 0;">'
        + paraBuf.map(function (l) { return inline(l.replace(/\s{2,}$/, '')); }).join('<br>')
        + '</p>';
      paraBuf = [];
    }
    function flushBlock() { flushList(); flushQuote(); flushPara(); flushTable(); }
    function headingLevel(level) { return Math.min(level + 2, 6); }
    for (var i = 0; i < lines.length; i++) {
      var l = lines[i];
      if (tableBuf.length && !/^\s*\|/.test(l)) flushTable();
      if (/^```/.test(l)) {
        flushBlock();
        if (!inCode) { inCode = true; codeBuf = []; }
        else { html += '<pre style="background:#f6f8fa;border-radius:8px;padding:10px 14px;overflow:auto;font-size:.9em;"><code>' + codeBuf.join('\n') + '</code></pre>'; inCode = false; }
        continue;
      }
      if (inCode) { codeBuf.push(l); continue; }
      if (/^\s*\|/.test(l)) {
        flushList(); flushQuote(); flushPara();
        tableBuf.push(l);
        continue;
      }
      if (/^\s*(---|\*\*\*|___)\s*$/.test(l)) {
        flushBlock();
        html += '<hr style="border:none;border-top:1px solid #ddd;margin:12px 0;">';
        continue;
      }
      if (/^\s*&gt;\s?/.test(l)) {
        flushList(); flushPara();
        quoteBuf.push(l);
        continue;
      }
      if (/^#{1,4}\s/.test(l)) {
        flushBlock();
        var lv = headingLevel(l.match(/^#+/)[0].length);
        html += '<h' + lv + ' style="margin:14px 0 6px;">' + inline(l.replace(/^#+\s/, '')) + '</h' + lv + '>';
        continue;
      }
      if (/^\s*[-*]\s+/.test(l)) {
        flushQuote(); flushPara();
        if (!listOpen) { html += '<ul style="padding-left:22px;margin:6px 0;">'; listOpen = true; }
        html += '<li>' + inline(l.replace(/^\s*[-*]\s+/, '')) + '</li>';
        continue;
      }
      if (/^\s*\d+[.)]\s+/.test(l)) {
        flushQuote(); flushPara();
        if (!olOpen) { html += '<ol style="padding-left:22px;margin:6px 0;">'; olOpen = true; }
        html += '<li>' + inline(l.replace(/^\s*\d+[.)]\s+/, '')) + '</li>';
        continue;
      }
      if (l.trim() === '') { flushBlock(); continue; }
      flushList(); flushQuote();
      paraBuf.push(l);
    }
    if (inCode) html += '<pre style="background:#f6f8fa;border-radius:8px;padding:10px 14px;overflow:auto;"><code>' + codeBuf.join('\n') + '</code></pre>';
    flushBlock();
    return html;
  }

  /* ---------- 启动 ---------- */
  if (!cfg) buildSettings();  // 首次访问自动弹出设置层（可跳过）
  ensureSettingsBtn();
  buildBubble();
  makeAskBtn();
  document.addEventListener('mouseup', onMouseUp);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panel) panel.style.display = 'none';
  });
  window.addEventListener('resize', function () { if (panel) positionPanel(); });
  document.addEventListener('scroll', hideAskBtn, true);
})();
