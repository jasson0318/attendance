const CACHE = "attendance-v10";

/** 由 sw.js 路徑推算 BASE_PATH（"" 或 "/attendance"） */
function swBasePath() {
  try {
    const path = self.location.pathname || "";
    const idx = path.lastIndexOf("/sw.js");
    if (idx >= 0) {
      return path.slice(0, idx) || "";
    }
  } catch (_e) {}
  return "";
}

const BASE_PATH = swBasePath();

function withBase(p) {
  if (!p.startsWith("/")) p = "/" + p;
  return BASE_PATH + p;
}

const ASSETS = [
  withBase("/"),
  withBase("/index.html"),
  withBase("/admin.html"),
  withBase("/static/css/app.css?v=10"),
  withBase("/static/css/admin.css?v=7"),
  withBase("/static/js/config.js?v=3"),
  withBase("/static/js/boot_assets.js?v=1"),
  withBase("/static/js/auth_session.js?v=9"),
  withBase("/static/js/app.js?v=12"),
  withBase("/static/js/admin.js?v=9"),
  withBase("/static/icons/icon-192.png"),
  withBase("/static/icons/icon-512.png"),
  withBase("/manifest.webmanifest"),
];

function isApiRequest(url) {
  // 同源 /api 或任何路徑含 /api/（防誤 cache）
  if (url.pathname.includes("/api/")) return true;
  // 跨域 Cloud API：不同 origin 通常不進此 SW；雙重保險
  if (url.pathname.endsWith("/api") || url.pathname.startsWith("/api")) return true;
  return false;
}

function isStaticAsset(url) {
  const p = url.pathname;
  return (
    p.endsWith(".css") ||
    p.endsWith(".js") ||
    p.endsWith(".png") ||
    p.endsWith(".jpg") ||
    p.endsWith(".jpeg") ||
    p.endsWith(".webp") ||
    p.endsWith(".svg") ||
    p.endsWith(".ico") ||
    p.endsWith(".webmanifest") ||
    p.endsWith(".html") ||
    p === BASE_PATH + "/" ||
    p === BASE_PATH ||
    p.endsWith("/")
  );
}

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(CACHE)
      .then(async (c) => {
        for (const asset of ASSETS) {
          try {
            await c.add(asset);
          } catch (_err) {
            // 個別資源失敗不阻擋 SW 安裝（例如本機無 admin.html 路由差異）
          }
        }
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // API：network-only，绝不写入 cache
  if (isApiRequest(url)) {
    return;
  }

  // 僅處理靜態資源；其餘交由瀏覽器預設
  if (!isStaticAsset(url)) {
    return;
  }

  // HTML / JS / CSS / manifest：network-first，失敗才用 cache（仍可不經 API）
  const networkFirst =
    url.pathname.endsWith(".html") ||
    url.pathname.endsWith(".js") ||
    url.pathname.endsWith(".css") ||
    url.pathname.endsWith(".webmanifest") ||
    url.pathname === BASE_PATH + "/" ||
    url.pathname === BASE_PATH ||
    url.pathname.endsWith("/");

  if (networkFirst) {
    e.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // 圖片等：cache-first
  e.respondWith(
    caches.match(req).then((cached) => cached || fetch(req).then((res) => {
      if (res && res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
      }
      return res;
    }))
  );
});
