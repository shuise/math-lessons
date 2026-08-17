// 本地答疑服务器：静态课件（math/ 根）+ /api/qa 答疑 API
// 用法：node scripts/qa-server.mjs  →  http://localhost:8644/lessons/
// 端口可用环境变量 PORT 覆盖
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { existsSync, statSync, readFileSync } from 'node:fs';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import qaHandler from '../api/qa.mjs';

// 加载根目录 .env（若存在，不覆盖已有环境变量）
try {
  const envPath = fileURLToPath(new URL('../.env', import.meta.url));
  for (const line of readFileSync(envPath, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
} catch (e) { /* 无 .env 时忽略 */ }

const root = fileURLToPath(new URL('../', import.meta.url));
const port = Number(process.env.PORT || 8644);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.png': 'image/png',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.json': 'application/json',
  '.md': 'text/plain; charset=utf-8',
  '.xhtml': 'text/html; charset=utf-8'
};

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');

  if (url.pathname === '/api/qa' && req.method === 'POST') {
    const chunks = [];
    for await (const c of req) chunks.push(c);
    req.body = Buffer.concat(chunks).toString('utf8');
    res.json = (obj) => {
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify(obj));
    };
    res.status = (code) => {
      res.statusCode = code;
      return res;
    };
    qaHandler(req, res);
    return;
  }

  let p = decodeURIComponent(url.pathname);
  if (p.endsWith('/')) p += 'index.html';
  const file = join(root, p);
  if (!file.startsWith(root) || !existsSync(file) || statSync(file).isDirectory()) {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('not found');
    return;
  }
  const data = await readFile(file);
  res.writeHead(200, { 'Content-Type': MIME[extname(file)] || 'application/octet-stream' });
  res.end(data);
});

server.listen(port, () => {
  console.log(`答疑站点：http://localhost:${port}/lessons/`);
  console.log(`答疑 API：POST http://localhost:${port}/api/qa`);
});
