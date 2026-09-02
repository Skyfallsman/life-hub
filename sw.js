/* Service Worker — Gary 日程 App
   策略（v4 起）：
   - HTML 文档 → **network-first**，并绕过 HTTP 缓存（cache:'reload'）
     => 只要联网，打开永远是最新版；断网时才回退到缓存（离线可用）。
   - 静态资源（图标/manifest）→ stale-while-revalidate，秒开。
   - activate 时 skipWaiting + clients.claim；页面侧监听 controllerchange 自动 reload 一次。
   => 以后更新内容：重新部署即可，用户无需手动刷新/清缓存。 */
const CACHE = 'gary-schedule-v27';
const ASSETS = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png'];

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).catch(() => {}));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;

  const accept = req.headers.get('accept') || '';
  const isDoc = req.mode === 'navigate' || accept.indexOf('text/html') > -1;
  const isNews = req.url.indexOf('news.json') > -1;   /* 热搜数据：必须拿最新 */

  if (isDoc || isNews) {
    // 网络优先 + 绕过 HTTP 缓存 → 永远拿最新
    e.respondWith(
      fetch(req, { cache: 'reload' })
        .then(res => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put('./index.html', copy)).catch(() => {});
          }
          return res;
        })
        .catch(() =>
          caches.match('./index.html').then(c => c || caches.match('./'))
        )
    );
    return;
  }

  // 静态资源：先给缓存，后台更新
  e.respondWith(
    caches.match(req).then(cached => {
      const net = fetch(req)
        .then(res => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => cached);
      return cached || net;
    })
  );
});
