// 정적 판의 서비스 워커 (wetherilli 380) — `static_site.py` 가 판마다 `__VERSION__` 을 채워 Pages 뿌리(와 `en/`)에 둔다.
//
// 하는 일은 둘뿐이다.
//  - 화면 파일(같은 곳의 `static/` — 주소에 `?v=판` 이 든다)은 처음 받은 것을 기기에 두고 다음부터 거기서 낸다. 판이 오르면 주소가 바뀌고
//    옛 판의 상자는 새 워커가 뜰 때 지운다
//  - 페이지(지도·소개)는 늘 망에서 먼저 받고, 망이 없을 때만 담아 둔 것을 낸다 — 새 판이 늦게 뜨지 않게
// 다른 곳(KIGAM·VWorld·극지 상류·배경)으로 가는 요청은 손대지 않는다 — 키가 든 주소를 기기에 담지 않는다. 지도 타일을 기기에 두는 것
// (오프라인 지도)은 아직 하지 않는다(TODOs)
var CACHE = "gsm-__VERSION__";

self.addEventListener("install", function () { self.skipWaiting(); });

self.addEventListener("activate", function (event) {
  event.waitUntil(caches.keys().then(function (names) {
    return Promise.all(names.filter(function (n) { return n.indexOf("gsm-") === 0 && n !== CACHE; })
                            .map(function (n) { return caches.delete(n); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).then(function (res) {
      if (res.ok) { var copy = res.clone(); caches.open(CACHE).then(function (c) { c.put(req, copy); }); }
      return res;
    }).catch(function () {
      return caches.match(req).then(function (hit) { return hit || Response.error(); });
    }));
    return;
  }
  if (url.pathname.indexOf("/static/") >= 0) {
    event.respondWith(caches.open(CACHE).then(function (c) {
      return c.match(req).then(function (hit) {
        return hit || fetch(req).then(function (res) {
          if (res.ok) c.put(req, res.clone());
          return res;
        });
      });
    }));
  }
});
