/* question-bank.js — 我的题库
 * 功能：
 *   1. 给每个题目注入「⭐ 加入题库」按钮
 *   2. 答错的题目自动收入题库（MutationObserver 监听 wrong-fb）
 *   3. index.html 的「我的题库」tab 渲染全部题目，可答题/看提示/看答案/移除
 * 存储：localStorage，纯前端，无依赖
 */
(function () {
  'use strict';

  var STORE_KEY = 'sl_question_bank_v1';

  /* ---------------- 存取 ---------------- */
  function loadAll() {
    try {
      var arr = JSON.parse(localStorage.getItem(STORE_KEY) || '[]');
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }
  function saveAll(list) {
    localStorage.setItem(STORE_KEY, JSON.stringify(list));
  }
  function findRecord(key) {
    var list = loadAll();
    for (var i = 0; i < list.length; i++) {
      if (list[i].key === key) return list[i];
    }
    return null;
  }
  function upsertRecord(rec) {
    var list = loadAll();
    for (var i = 0; i < list.length; i++) {
      if (list[i].key === rec.key) {
        list[i].wrong = list[i].wrong || rec.wrong; // 错题标记一旦有就保留
        return;
      }
    }
    list.push(rec);
    saveAll(list);
  }
  function removeRecord(key) {
    saveAll(loadAll().filter(function (r) { return r.key !== key; }));
  }

  /* ---------------- 工具 ---------------- */
  function currentSourcePath() {
    // /self-learning/exams/exam-stage1.html → exams/exam-stage1.html
    var p = location.pathname;
    var idx = p.indexOf('/self-learning/');
    if (idx >= 0) p = p.slice(idx + '/self-learning/'.length);
    return p.replace(/^\/+/, '');
  }
  function argFromOnclick(attr, fnName) {
    // 取出 onclick="fn('a','b')" 的字符串参数
    var m = attr.match(new RegExp(fnName + "\\s*\\(([^)]*)\\)"));
    if (!m) return [];
    var out = [];
    var re = /'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|([^,]+)/g;
    var x;
    while ((x = re.exec(m[1])) !== null) {
      out.push(x[1] !== undefined ? x[1] : (x[2] !== undefined ? x[2] : x[3].trim()));
    }
    return out;
  }
  function esc(s) {
    return String(s == null ? '' : s);
  }

  /* ---------------- 题目采集 ---------------- */

  // 在 scope 内找到「思路提示」「查看答案」两个按钮及其 box id
  function findHintAns(root) {
    var hBtn = root.querySelector('button[onclick*="toggleHint"]');
    var aBtn = root.querySelector('button[onclick*="toggleAns"]');
    if (!hBtn || !aBtn) return null;
    var hId = argFromOnclick(hBtn.getAttribute('onclick'), 'toggleHint')[0];
    var aId = argFromOnclick(aBtn.getAttribute('onclick'), 'toggleAns')[0];
    return { hBtn: hBtn, aBtn: aBtn, hId: hId, aId: aId,
             hBox: document.getElementById(hId), aBox: document.getElementById(aId) };
  }

  // 从题目容器解析结构化数据；返回 null 表示不是有效题目
  function parseQuestion(scope, stemEl) {
    var ha = findHintAns(scope);
    if (!ha) return null;
    var source = currentSourcePath();
    var key = source + '|' + ha.hId;

    var rec = {
      key: key,
      source: source,
      sourceTitle: document.title.replace(/\s*[—–-]\s*自学课件.*$/, ''),
      type: 'plain',
      stem: stemEl ? stemEl.innerHTML : '',
      options: null,
      answer: '',
      hint: ha.hBox ? ha.hBox.innerHTML : '',
      ans: ha.aBox ? ha.aBox.innerHTML : '',
      wrong: false,
      addedAt: Date.now()
    };

    // 题型识别（只在题目自身范围内找交互区）
    var tfZone = scope.querySelector('[id^="tf-"]');
    var optZone = scope.querySelector('[id^="opt-"]');
    var fillZone = scope.querySelector('[id^="fill-"]');
    var olyZone = scope.querySelector('.fill-row [onclick*="checkOlympiad"]') ?
                  scope.querySelector('.fill-row') : null;

    if (tfZone) {
      rec.type = 'tf';
      rec.options = [];
      tfZone.querySelectorAll('.tf-btn').forEach(function (b) {
        var args = argFromOnclick(b.getAttribute('onclick'), 'checkTF');
        rec.options.push({ label: b.textContent.trim(), correct: args[1] === 'true' });
      });
    } else if (optZone) {
      var isMulti = !!optZone.querySelector('.check-btn[onclick*="checkMulti"]');
      rec.type = isMulti ? 'multi' : 'single';
      rec.options = [];
      optZone.querySelectorAll('.opt-btn').forEach(function (b) {
        rec.options.push({
          label: b.textContent.trim(),
          correct: b.getAttribute('data-correct') === 'true'
        });
      });
    } else if (fillZone) {
      rec.type = 'fill';
      var cb = fillZone.querySelector('.check-btn[onclick*="checkFill"]');
      if (cb) rec.answer = argFromOnclick(cb.getAttribute('onclick'), 'checkFill')[1] || '';
    } else if (olyZone) {
      rec.type = 'fill';
      var ob = olyZone.querySelector('[onclick*="checkOlympiad"]');
      if (ob) rec.answer = argFromOnclick(ob.getAttribute('onclick'), 'checkOlympiad')[1] || '';
    }
    return { rec: rec, ha: ha };
  }

  // 收集页面上的所有题目 {rec, ha, root}
  function collectAll() {
    var out = [];
    var seen = {};

    function pushParsed(scope, stemEl) {
      try {
        var parsed = parseQuestion(scope, stemEl);
        if (parsed && !seen[parsed.rec.key]) {
          seen[parsed.rec.key] = 1;
          out.push({ rec: parsed.rec, ha: parsed.ha, root: scope });
        }
      } catch (e) { /* 单题失败不影响整体 */ }
    }

    // 1) 标准题目容器
    document.querySelectorAll('.q-item, .problem, .exercise').forEach(function (box) {
      pushParsed(box, box.querySelector('p'));
    });

    // 2) .challenge 内一个块含多道题：以「思路提示」按钮为锚点分组
    document.querySelectorAll('.challenge').forEach(function (ch) {
      ch.querySelectorAll('button[onclick*="toggleHint"]').forEach(function (hBtn) {
        var info = findHintAns(ch);
        if (!info) return;
        // 题干 = hint 按钮往前最近的 <p>
        var stem = hBtn.previousElementSibling;
        while (stem && stem.tagName !== 'P') stem = stem.previousElementSibling;
        // 用临时包裹限定 parseQuestion 的交互区搜索（challenge 题为纯问答）
        var parsed = parseQuestion(ch, stem);
        if (parsed && !seen[parsed.rec.key]) {
          seen[parsed.rec.key] = 1;
          // 覆盖 hint/ans 按钮对（challenge 有多组）
          var aBtn = hBtn.nextElementSibling;
          while (aBtn && !(aBtn.tagName === 'BUTTON' && /toggleAns/.test(aBtn.getAttribute('onclick') || ''))) {
            aBtn = aBtn.nextElementSibling;
          }
          if (!aBtn) return;
          var aId = argFromOnclick(aBtn.getAttribute('onclick'), 'toggleAns')[0];
          parsed.rec.key = currentSourcePath() + '|' +
                           argFromOnclick(hBtn.getAttribute('onclick'), 'toggleHint')[0];
          parsed.rec.hint = (document.getElementById(
            argFromOnclick(hBtn.getAttribute('onclick'), 'toggleHint')[0]) || {}).innerHTML || '';
          parsed.rec.ans = (document.getElementById(aId) || {}).innerHTML || '';
          out.push({ rec: parsed.rec, ha: { hBtn: hBtn, aBtn: aBtn }, root: ch });
        }
      });
    });

    return out;
  }

  /* ---------------- 注入「加入题库」按钮 ---------------- */
  function injectButtons() {
    var items = collectAll();
    items.forEach(function (item) {
      var rec = item.rec;
      var aBtn = item.ha.aBtn;
      if (aBtn && aBtn.getAttribute('data-qb-injected') === '1') return;

      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'qb-add-btn btn-sm';
      syncAddBtn(btn, rec.key);
      btn.addEventListener('click', function () {
        if (findRecord(rec.key)) return; // 已在题库
        upsertRecord(rec);
        syncAddBtn(btn, rec.key);
      });
      // 插在「查看答案」按钮后面
      if (aBtn.parentNode) aBtn.parentNode.insertBefore(btn, aBtn.nextSibling);
      if (aBtn) aBtn.setAttribute('data-qb-injected', '1');
    });
  }

  function syncAddBtn(btn, key) {
    if (findRecord(key)) {
      btn.textContent = '✓ 已加入题库';
      btn.classList.add('in-bank');
    } else {
      btn.textContent = '⭐ 加入题库';
      btn.classList.remove('in-bank');
    }
  }

  /* ---------------- 答错自动收录 ---------------- */
  function watchWrongAnswers() {
    var observer = new MutationObserver(function (muts) {
      muts.forEach(function (m) {
        if (m.type !== 'attributes' || m.attributeName !== 'class') return;
        var el = m.target;
        if (!el.classList || !el.classList.contains('wrong-fb')) return;
        var t = el.textContent || '';
        // 空答案提示不算答错（如「请输入答案」）
        if (!/✗|错误|不对/.test(t)) return;
        var root = el.closest('.q-item, .problem, .exercise');
        if (!root) return;
        var parsed = parseQuestion(root, root.querySelector('p'));
        if (!parsed) return;
        parsed.rec.wrong = true;
        if (!findRecord(parsed.rec.key)) upsertRecord(parsed.rec);
        // 同步该题的星标按钮
        var star = root.querySelector('.qb-add-btn');
        if (star) syncAddBtn(star, parsed.rec.key);
      });
    });
    observer.observe(document.body, {
      subtree: true, attributes: true, attributeFilter: ['class']
    });
  }

  /* ---------------- 题库页渲染（index.html 的 tab） ---------------- */
  function normalizeAns(s) {
    return String(s || '').replace(/\s+/g, '').toLowerCase();
  }
  function answerCorrect(user, correct) {
    var u = normalizeAns(user), c = normalizeAns(correct);
    if (!u) return null; // 未作答
    if (u === c) return true;
    var un = parseFloat(u), cn = parseFloat(c);
    if (!isNaN(un) && !isNaN(cn) && Math.abs(un - cn) < 0.0001) return true;
    // 分数比较 a/b
    function frac(s) {
      var p = s.split('/');
      if (p.length === 2) {
        var n = parseFloat(p[0]), d = parseFloat(p[1]);
        if (!isNaN(n) && !isNaN(d) && d !== 0) return n / d;
      }
      return NaN;
    }
    var fu = frac(u), fc = frac(c);
    if (!isNaN(fu) && !isNaN(fc) && Math.abs(fu - fc) < 0.0001) return true;
    if (!isNaN(fu) && !isNaN(cn) && Math.abs(fu - cn) < 0.0001) return true;
    if (!isNaN(un) && !isNaN(fc) && Math.abs(un - fc) < 0.0001) return true;
    return false;
  }

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  function renderBank() {
    var listEl = document.getElementById('qb-list');
    var countEl = document.getElementById('qb-count');
    if (!listEl) return;
    var list = loadAll().sort(function (a, b) { return b.addedAt - a.addedAt; });
    if (countEl) countEl.textContent = list.length;
    listEl.innerHTML = '';

    if (!list.length) {
      listEl.appendChild(el('div', 'qb-empty',
        '题库还是空的。<br>做题时点击「⭐ 加入题库」，或者答错的题目会自动收进来，方便以后复习。'));
      return;
    }

    list.forEach(function (rec, idx) {
      var card = el('div', 'q-item qb-card');
      // 来源 + 错题标记 + 移除
      var meta = el('div', 'qb-meta');
      meta.appendChild(el('a', 'qb-source', esc(rec.sourceTitle) || esc(rec.source)));
      var last = meta.lastChild;
      last.href = rec.source;
      if (rec.wrong) meta.appendChild(el('span', 'qb-badge-wrong', '🔁 错题'));
      var rmBtn = el('button', 'qb-remove-btn', '🗑 移出题库');
      rmBtn.type = 'button';
      rmBtn.addEventListener('click', function () {
        removeRecord(rec.key);
        renderBank();
      });
      meta.appendChild(rmBtn);
      card.appendChild(meta);

      // 题干
      card.appendChild(el('p', 'qb-stem', rec.stem));

      var uid = 'qb' + idx + '-' + Math.random().toString(36).slice(2, 7);

      if (rec.type === 'tf' || rec.type === 'single') {
        var zone = el('div', 'qb-zone');
        rec.options.forEach(function (op) {
          var b = el('button', rec.type === 'tf' ? 'tf-btn' : 'opt-btn', esc(op.label));
          b.type = 'button';
          b.addEventListener('click', function () {
            if (zone.dataset.done) return;
            zone.dataset.done = '1';
            zone.querySelectorAll('button').forEach(function (x) { x.disabled = true; });
            if (op.correct) {
              b.classList.add('correct');
              fb.textContent = '✓ 正确'; fb.className = 'feedback show correct-fb';
            } else {
              b.classList.add('wrong');
              fb.textContent = '✗ 错误'; fb.className = 'feedback show wrong-fb';
            }
          });
          zone.appendChild(b);
        });
        var fb = el('span', 'feedback');
        zone.appendChild(fb);
        card.appendChild(zone);
      } else if (rec.type === 'multi') {
        var zone2 = el('div', 'qb-zone');
        rec.options.forEach(function (op) {
          var b = el('button', 'opt-btn', esc(op.label));
          b.type = 'button';
          b.addEventListener('click', function () {
            if (zone2.dataset.done) return;
            b.classList.toggle('selected');
          });
          zone2.appendChild(b);
        });
        zone2.appendChild(el('br'));
        var submit = el('button', 'check-btn', '提交');
        submit.type = 'button';
        var fb2 = el('span', 'feedback');
        submit.addEventListener('click', function () {
          if (zone2.dataset.done) return;
          zone2.dataset.done = '1';
          var allRight = true;
          zone2.querySelectorAll('.opt-btn').forEach(function (b, i) {
            b.disabled = true;
            var picked = b.classList.contains('selected');
            var right = rec.options[i].correct;
            if (picked && right) b.classList.add('correct');
            else if (picked && !right) { b.classList.add('wrong'); allRight = false; }
            else if (!picked && right) allRight = false;
          });
          submit.disabled = true;
          fb2.textContent = allRight ? '✓ 正确' : '✗ 错误';
          fb2.className = 'feedback show ' + (allRight ? 'correct-fb' : 'wrong-fb');
        });
        zone2.appendChild(submit);
        zone2.appendChild(fb2);
        card.appendChild(zone2);
      } else if (rec.type === 'fill') {
        var row = el('div', 'qb-fill-row');
        var input = el('input', 'fill-input');
        input.type = 'text';
        input.placeholder = '输入答案';
        var btnC = el('button', 'check-btn', '提交');
        btnC.type = 'button';
        var fb3 = el('span', 'feedback');
        function doCheck() {
          if (row.dataset.done) return;
          var r = answerCorrect(input.value, rec.answer);
          if (r === null) { input.focus(); return; }
          row.dataset.done = '1';
          input.disabled = true;
          btnC.disabled = true;
          if (r) {
            input.style.borderColor = '#4caf50';
            fb3.textContent = '✓ 正确'; fb3.className = 'feedback show correct-fb';
          } else {
            input.style.borderColor = '#f44336';
            fb3.textContent = '✗ 错误'; fb3.className = 'feedback show wrong-fb';
          }
        }
        btnC.addEventListener('click', doCheck);
        input.addEventListener('keydown', function (e) { if (e.key === 'Enter') doCheck(); });
        row.appendChild(input);
        row.appendChild(btnC);
        row.appendChild(fb3);
        card.appendChild(row);
      }

      // 提示 / 答案（题库页不再放「加入题库」按钮）
      var btnRow = el('div', 'qb-btn-row');
      var hBox = el('div', 'hint-box qb-hint-' + uid, rec.hint);
      var aBox = el('div', 'ans-box qb-ans-' + uid, rec.ans);
      var bHint = el('button', 'qb-mini-btn qb-hint-btn', '💡 思路提示');
      bHint.type = 'button';
      bHint.addEventListener('click', function () { hBox.classList.toggle('show'); });
      var bAns = el('button', 'qb-mini-btn qb-ans-btn', '✅ 查看答案');
      bAns.type = 'button';
      bAns.addEventListener('click', function () { aBox.classList.toggle('show'); });
      btnRow.appendChild(bHint);
      btnRow.appendChild(bAns);
      card.appendChild(btnRow);
      card.appendChild(hBox);
      card.appendChild(aBox);

      listEl.appendChild(card);
    });
  }

  /* ---------------- 启动 ---------------- */
  function init() {
    if (document.getElementById('qb-list')) {
      renderBank();
      var clr = document.getElementById('qb-clear');
      if (clr) clr.addEventListener('click', function () {
        if (confirm('确定清空整个题库吗？此操作不能撤销。')) {
          saveAll([]);
          renderBank();
        }
      });
      return; // 题库页不注入星标
    }
    injectButtons();
    watchWrongAnswers();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
