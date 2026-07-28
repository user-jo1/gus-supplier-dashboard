/**
 * GUS 劳务供应商管理看板 - 生产服务器
 * 
 * 安全特性：
 * 1. Helmet 安全头（隐藏技术栈、防XSS、防点击劫持）
 * 2. IP 频率限制（防暴力破解、防爬虫）
 * 3. 反爬虫检测（User-Agent检查、请求频率分析）
 * 4. 静态资源只读服务（不暴露源码目录结构）
 * 5. HPP 参数污染防护
 */

const express = require('express');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const hpp = require('hpp');
const compression = require('compression');
const morgan = require('morgan');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// ==================== 1. 基础安全中间件 ====================

// Helmet：设置各种 HTTP 安全头
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", "data:", "blob:"],
      connectSrc: ["'self'"],
      fontSrc: ["'self'"],
      objectSrc: ["'none'"],
      mediaSrc: ["'self'"],
      frameSrc: ["'none'"],
    },
  },
  // 禁止搜索引擎索引
  crossOriginEmbedderPolicy: false,
  // 隐藏 Express/X-Powered-By
  hidePoweredBy: true,
  // 防止点击劫持
  frameguard: { action: 'deny' },
  // 强制 HTTPS（如果使用反向代理）
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true,
    preload: true,
  },
  // 禁止 MIME 类型嗅探
  noSniff: true,
  // 启用 XSS 过滤器
  xssFilter: true,
}));

// HPP：防止 HTTP 参数污染
app.use(hpp());

// Compression：压缩响应
app.use(compression());

// ==================== 2. 日志记录（仅记录必要信息） ====================

// 自定义日志格式（不记录敏感数据）
morgan.token('custom', (req) => {
  return req.headers['x-forwarded-for'] || req.socket.remoteAddress || '-';
});
app.use(morgan(':custom - :method :url :status :response-time[0]ms - :date[iso]', {
  skip: (req) => req.url.startsWith('/static/'),
}));

// ==================== 3. 反爬虫 / 访问频率限制 ====================

// 全局基础限制：每IP每分钟最多 200 个请求
const globalLimiter = rateLimit({
  windowMs: 1 * 60 * 1000, // 1 分钟
  max: 200,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: '请求过于频繁，请稍后再试', code: 429 },
  skip: (req) => req.ip === '127.0.0.1' || req.ip === '::1' || req.ip === 'localhost',
});
app.use(globalLimiter);

// 登录接口限制：每IP每分钟最多 10 次尝试（防暴力破解）
const loginLimiter = rateLimit({
  windowMs: 1 * 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: '登录尝试次数过多，请1分钟后再试', code: 429 },
});
app.use('/api/login', loginLimiter);

// 爬虫检测中间件
const botPatterns = [
  // 已知爬虫UA
  /bot/i, /crawler/i, /spider/i, /scraper/i, /headless/i,
  // 异常UA
  /curl/i, /wget/i, /python/i, /java/i, /go-http/i,
  /axios/i, /node-fetch/i, /okhttp/i,
];

const botRequestCounts = new Map();
const BOT_CLEANUP_INTERVAL = 5 * 60 * 1000; // 5分钟清理一次

// 定期清理计数
setInterval(() => {
  const now = Date.now();
  for (const [key, data] of botRequestCounts.entries()) {
    if (now - data.lastTime > BOT_CLEANUP_INTERVAL) {
      botRequestCounts.delete(key);
    }
  }
}, BOT_CLEANUP_INTERVAL);

app.use((req, res, next) => {
  const ua = (req.headers['user-agent'] || '').toLowerCase();
  const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'unknown';
  const now = Date.now();

  // 检查是否为已知爬虫UA
  const isBot = botPatterns.some(pattern => pattern.test(ua));

  if (isBot) {
    // 追踪爬虫请求频率
    const key = `${ip}:${ua.substring(0, 50)}`;
    if (!botRequestCounts.has(key)) {
      botRequestCounts.set(key, { count: 1, firstTime: now, lastTime: now });
    } else {
      const data = botRequestCounts.get(key);
      data.count++;
      data.lastTime = now;
    }

    // 如果短时间内请求过多，直接拒绝
    const data = botRequestCounts.get(key);
    const timeSpan = (now - data.firstTime) / 1000; // 秒
    const rate = data.count / Math.max(timeSpan, 1);

    if (data.count > 20 && rate > 5) {
      console.warn(`[ANTI-BOT] 检测到爬虫行为: IP=${ip}, UA=${ua.substring(0, 60)}`);
      return res.status(403).send('Access Denied');
    }
  }

  // 检查异常高的请求频率（可能为自动化工具）
  const freqKey = `freq:${ip}`;
  if (!botRequestCounts.has(freqKey)) {
    botRequestCounts.set(freqKey, { count: 1, firstTime: now, lastTime: now });
  } else {
    const freqData = botRequestCounts.get(freqKey);
    freqData.count++;
    freqData.lastTime = now;

    const timeSpan = (now - freqData.firstTime) / 1000;
    const rate = freqData.count / Math.max(timeSpan, 1);

    // 超过30请求/秒，视为异常
    if (freqData.count > 30 && rate > 30) {
      console.warn(`[ANTI-BOT] 异常高频请求: IP=${ip}, rate=${rate.toFixed(1)}/s`);
      return res.status(403).send('Access Denied');
    }
  }

  next();
});

// ==================== 4. 静态文件服务（源码不暴露） ====================

// 从构建目录（或源码目录）提供静态文件
// Docker 构建时会将 HTML/JSON 等文件复制到 public/ 目录
const publicDir = path.join(__dirname, 'public');

// 检查 public 目录是否存在（Docker构建产物），否则回退到父目录
const staticDir = fs.existsSync(publicDir) ? publicDir : path.join(__dirname, '..');

console.log(`[INFO] 静态文件目录: ${staticDir}`);

// 只允许访问特定文件类型
const ALLOWED_EXTENSIONS = new Set([
  '.html', '.json', '.css', '.js', '.png', '.jpg', '.jpeg',
  '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot',
  '.txt', '.xml', '.webmanifest',
]);

// 自定义静态文件中间件（白名单扩展名 + 禁止访问非公开文件）
app.use(express.static(staticDir, {
  index: false,         // 不自动显示 index.html（手动控制路由）
  dotfiles: 'deny',     // 禁止访问点文件
  setHeaders: (res, filePath) => {
    const ext = path.extname(filePath).toLowerCase();
    if (!ALLOWED_EXTENSIONS.has(ext)) {
      // 不应该到达这里，但以防万一
      return;
    }
    // 设置缓存策略
    if (ext === '.json') {
      res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
      res.set('Pragma', 'no-cache');
      res.set('Expires', '0');
    } else if (ext === '.html') {
      res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
      res.set('Pragma', 'no-cache');
      res.set('Expires', '0');
    } else {
      res.set('Cache-Control', 'public, max-age=86400'); // 1天
    }
    // 设置正确的内容类型
    if (ext === '.json') {
      res.set('Content-Type', 'application/json; charset=utf-8');
    }
  },
  fallthrough: true,
}));

// 禁止直接访问原始数据文件和服务器文件
const forbiddenPaths = [
  /\/\.git/i,
  /\/server\.js/i,
  /\/package\.json/i,
  /\/Dockerfile/i,
  /\/docker-compose/i,
  /\/node_modules/i,
  /\/build_data\.py/i,
  /\/build_dashboard\.py/i,
  /\/deploy\.sh/i,
  /\/check\.sh/i,
  /\/\.env/i,
  /\/README/i,
];

app.use((req, res, next) => {
  const url = req.url.toLowerCase();
  for (const pattern of forbiddenPaths) {
    if (pattern.test(url)) {
      return res.status(404).send('Not Found');
    }
  }
  next();
});

// ==================== 5. 路由定义 ====================

// 首页重定向到登录页
app.get('/', (req, res) => {
  res.redirect('/login.html');
});

// 登录页
app.get('/login.html', (req, res) => {
  res.sendFile('login.html', { root: staticDir }, (err) => {
    if (err) res.status(404).send('Not Found');
  });
});

// 管理后台
app.get('/admin.html', (req, res) => {
  res.sendFile('admin.html', { root: staticDir }, (err) => {
    if (err) res.status(404).send('Not Found');
  });
});

// 主看板
app.get('/dashboard.html', (req, res) => {
  res.sendFile('dashboard.html', { root: staticDir }, (err) => {
    if (err) res.status(404).send('Not Found');
  });
});

// 分享版看板
app.get('/dashboard_share.html', (req, res) => {
  res.sendFile('dashboard_share.html', { root: staticDir }, (err) => {
    if (err) res.status(404).send('Not Found');
  });
});

// 数据文件
app.get('/dashboard_data.json', (req, res) => {
  res.sendFile('dashboard_data.json', { root: staticDir }, (err) => {
    if (err) res.status(404).send('Not Found');
  });
});

// robots.txt（禁止所有爬虫）
app.get('/robots.txt', (req, res) => {
  res.type('text/plain');
  res.send('User-agent: *\nDisallow: /\n');
});

// API 路由：健康检查（不暴露任何内部信息）
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

// ==================== 6. 404 处理 ====================

// 对任何未匹配的路由返回 404
app.use((req, res) => {
  res.status(404).send('Not Found');
});

// ==================== 7. 错误处理 ====================

app.use((err, req, res, next) => {
  console.error(`[ERROR] ${err.message}`);
  res.status(500).send('Internal Server Error');
});

// ==================== 8. 启动服务器 ====================

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[GUS Dashboard] 服务器已启动: http://0.0.0.0:${PORT}`);
  console.log(`[GUS Dashboard] 静态文件目录: ${staticDir}`);
  console.log(`[GUS Dashboard] 环境: ${process.env.NODE_ENV || 'development'}`);
});
