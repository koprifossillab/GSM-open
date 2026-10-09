/* 오프라인 묶음 — 박스 하나의 타일을 파일 하나로 들여 망·키 없이 본다 (wetherilli P13·382).
 *
 * 묶음(`.gsmpack`)은 굽는 쪽(`viewer/offlinepack.py`, wetherilli 381)이 짓는다. 꼴은 P13 그대로다.
 *
 *     0      8 B   "GSMPACK1"
 *     8      4 B   머리 길이 N (uint32, little-endian)
 *     12     N B   머리 JSON (UTF-8)
 *     12+N   …     타일 바이트를 잇달아 — 머리의 `tiles` 가 `{"<레이어>/<z>/<x>/<y>": [시작, 길이]}`
 *
 * 고른 파일(Blob)을 **IndexedDB 에 통째로** 둔다 — 개인 레이어처럼 그 브라우저에만 있다. 타일은 `Blob.slice` 로 그때그때 잘라
 * `URL.createObjectURL` 로 그린다. 200 MB 를 메모리로 읽지 않는다. 서비스 워커(wetherilli 380)는 손대지 않는다.
 *
 * 화면(map.js)은 소스를 지을 때 `wrap(source, 이름)` 만 부른다 — 묶음에 그 타일이 있으면 묶음에서, 없으면 원래 손(망)으로.
 * 배경지도 고르개는 IndexedDB 가 열리기 전에 서므로, 덮는 레이어 이름을 localStorage 에도 적어 두고(`coversSync`) 거기서 본다.
 */
(function (root) {
  "use strict";

  var MAGIC = "GSMPACK1";
  var DB_NAME = "gsm-offline";
  var STORE = "packs";
  var SYNC_SLOT = "gsm.offline.layers";

  var tr = function (text, vars) {
    return vars ? text.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; }) : text;
  };
  function T(text, vars) { return tr(text, vars); }
  function setTranslator(fn) { if (fn) tr = fn; }

  // ── 머리 ───────────────────────────────────────────────────────

  function readSlice(blob, start, end) {
    var part = blob.slice(start, end);
    if (part.arrayBuffer) return part.arrayBuffer();
    return new Promise(function (resolve, reject) {       // 옛 사파리
      var r = new FileReader();
      r.onload = function () { resolve(r.result); };
      r.onerror = function () { reject(r.error); };
      r.readAsArrayBuffer(part);
    });
  }

  /** 묶음의 머리 → `{head, base}`. `base` 는 타일 바이트가 시작하는 자리(12+N). 꼴이 아니면 거절한다 */
  function readHeader(blob) {
    return readSlice(blob, 0, 12).then(function (buf) {
      var bytes = new Uint8Array(buf);
      var magic = String.fromCharCode.apply(null, Array.prototype.slice.call(bytes, 0, 8));
      if (bytes.length < 12 || magic !== MAGIC) throw new Error(T("오프라인 묶음(.gsmpack)이 아니다"));
      var n = new DataView(buf).getUint32(8, true);
      if (12 + n > blob.size) throw new Error(T("묶음의 머리가 잘렸다"));
      return readSlice(blob, 12, 12 + n).then(function (raw) {
        var head = JSON.parse(new TextDecoder("utf-8").decode(raw));
        if (!head || typeof head.tiles !== "object" || typeof head.layers !== "object") {
          throw new Error(T("묶음의 머리를 읽지 못했다"));
        }
        return { head: head, base: 12 + n };
      });
    });
  }

  // ── 브라우저 저장소 ─────────────────────────────────────────────

  function openDB() {
    return new Promise(function (resolve, reject) {
      if (!root.indexedDB) { reject(new Error(T("이 브라우저는 저장소(IndexedDB)를 쓰지 못한다"))); return; }
      var req = root.indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function () {
        if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE, { keyPath: "id" });
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function tx(mode, work) {
    return openDB().then(function (db) {
      return new Promise(function (resolve, reject) {
        var t = db.transaction(STORE, mode);
        var result;
        work(t.objectStore(STORE), function (r) { result = r; });
        t.oncomplete = function () { db.close(); resolve(result); };
        t.onerror = function () { db.close(); reject(t.error); };
        t.onabort = function () { db.close(); reject(t.error || new Error(T("저장하지 못했다 — 저장소가 찼을 수 있다"))); };
      });
    });
  }

  // ── 들인 묶음 ───────────────────────────────────────────────────

  //: 읽어 둔 묶음 — `{id, name, size, added, blob, head, base}`. 새로 구운 것이 앞이다(같은 타일이면 그것이 이긴다)
  var packs = [];
  var listeners = [];
  var wrapped = [];

  function sortPacks() {
    packs.sort(function (a, b) { return String(b.head.built || "").localeCompare(String(a.head.built || "")); });
  }

  //: 덮는 레이어 이름 — 지난번에 적어 둔 것으로 시작해 묶음을 읽으면 고친다. 타일마다 묻는 것이라 메모리에 둔다
  var covered = (function () {
    try { return JSON.parse(localStorage.getItem(SYNC_SLOT) || "[]") || []; } catch (e) { return []; }
  })();

  function writeSync() {
    var names = {};
    packs.forEach(function (p) { Object.keys(p.head.layers || {}).forEach(function (n) { names[n] = true; }); });
    covered = Object.keys(names);
    try { localStorage.setItem(SYNC_SLOT, JSON.stringify(covered)); } catch (e) { /* 사생활 모드 */ }
  }

  function load() {
    return tx("readonly", function (store, done) {
      var req = store.getAll();
      req.onsuccess = function () { done(req.result || []); };
    }).then(function (rows) {
      return Promise.all(rows.map(function (row) {
        return readHeader(row.blob).then(function (got) {
          return { id: row.id, name: row.name, size: row.size, added: row.added, blob: row.blob,
                   head: got.head, base: got.base };
        }, function () { return null; });                  // 읽지 못하는 것은 목록에서 뺀다 — 지우기는 남긴다
      }));
    }).then(function (rows) {
      packs = rows.filter(Boolean);
      sortPacks();
      writeSync();
      return packs;
    }, function () { packs = []; return packs; });     // 저장소가 막혔다 — 적어 둔 이름은 그대로 두고 망으로 간다
  }

  var ready = load();

  function changed() {
    sortPacks();
    writeSync();
    wrapped.forEach(function (s) { if (s.refresh) s.refresh(); });
    listeners.forEach(function (fn) { try { fn(list()); } catch (e) { /* 듣는 쪽의 잘못 */ } });
  }

  /** 고른 파일을 들인다 — 머리를 먼저 읽어 꼴을 보고, 맞으면 통째로 저장소에 둔다 */
  function add(file) {
    return readHeader(file).then(function (got) {
      var row = { id: (got.head.box || "pack") + "-" + (got.head.built || "") + "-" + Date.now().toString(36),
                  name: file.name || "", size: file.size, added: new Date().toISOString(), blob: file };
      return tx("readwrite", function (store) { store.put(row); }).then(function () {
        return ready.then(function () {
          var pack = Object.assign({ head: got.head, base: got.base }, row);
          packs.push(pack);
          changed();
          return summary(pack);
        });
      });
    });
  }

  function remove(id) {
    return tx("readwrite", function (store) { store.delete(id); }).then(function () {
      packs = packs.filter(function (p) { return p.id !== id; });
      changed();
    });
  }

  function summary(p) {
    var h = p.head;
    return { id: p.id, name: p.name, size: p.size, added: p.added, box: h.box || "", title: h.title || h.box || p.name,
             built: h.built || "", bbox: h.bbox || null, region: h.region || "", note: h.note || "",
             layers: Object.keys(h.layers || {}), tiles: Object.keys(h.tiles || {}).length,
             attribution: attributionOf(p) };
  }

  function attributionOf(p) {
    var seen = [];
    Object.keys(p.head.layers || {}).forEach(function (n) {
      var a = (p.head.layers[n] || {}).attribution;
      if (a && seen.indexOf(a) < 0) seen.push(a);
    });
    return seen;
  }

  function list() { return packs.map(summary); }

  function onChange(fn) { listeners.push(fn); }

  /** 이 레이어를 덮는 묶음이 있나 — 저장소가 열리기 전에도 답한다(지난번에 적어 둔 것) */
  function coversSync(name) { return covered.indexOf(name) >= 0; }

  /** 들인 묶음이 하나라도 있나 — 저장소가 열리기 전에도 답한다 */
  function held() { return packs.length > 0 || covered.length > 0; }

  /** 레이어·타일 자리의 Blob 하나, 없으면 null. 열쇠는 소스의 tileCoord 그대로다 — KIGAM 은 512 px 격자라 격자 줌이 화면 줌보다
   *  하나 낮고 VWorld 는 256 px 그대로다(wetherilli 381). `tileSize` 를 주면 머리의 `tile_size` 가 다른 묶음은 건너뛴다 — 격자가
   *  어긋난 묶음이 엉뚱한 자리에 그리지 않게 */
  function tileBlob(name, z, x, y, tileSize) {
    var key = name + "/" + z + "/" + x + "/" + y;
    for (var i = 0; i < packs.length; i++) {
      var p = packs[i];
      var at = p.head.tiles[key];
      if (!at) continue;
      var meta = p.head.layers[name] || {};
      if (tileSize && meta.tile_size && meta.tile_size !== tileSize) continue;
      var type = meta.type || "image/png";
      return p.blob.slice(p.base + at[0], p.base + at[0] + at[1], type);
    }
    return null;
  }

  /** 경위도 한 자리를 덮는 묶음들 — 화면의 "오프라인: 장성 · 10-10" 표 */
  function at(lon, lat) {
    return packs.filter(function (p) {
      var b = p.head.bbox;
      return b && lon >= b[0] && lon <= b[2] && lat >= b[1] && lat <= b[3];
    }).map(summary);
  }

  /** 소스의 타일 손을 감싼다 — 묶음에 그 타일이 있으면 묶음에서, 없으면 원래 손으로(망·키). 묶음이 덮지 않는 레이어도 감싸
   *  둔다 — 나중에 묶음을 들이면 `refresh` 로 다시 그린다 */
  function wrap(source, name) {
    if (!source || !source.getTileLoadFunction || !source.setTileLoadFunction) return source;
    var original = source.getTileLoadFunction();
    var grid = source.getTileGrid && source.getTileGrid();
    var size = grid ? grid.getTileSize(0) : 0;
    size = Array.isArray(size) ? size[0] : size;
    source.setTileLoadFunction(function (tile, src) {
      var c = tile.getTileCoord();
      var now = packs.length ? tileBlob(name, c[0], c[1], c[2], size) : null;
      if (now || !coversSync(name)) { draw(tile, src, now, original); return; }
      ready.then(function () { draw(tile, src, tileBlob(name, c[0], c[1], c[2], size), original); });
    });
    wrapped.push(source);
    return source;
  }

  function draw(tile, src, blob, original) {
    if (!blob) { original(tile, src); return; }
    var img = tile.getImage();
    var url = URL.createObjectURL(blob);
    var free = function () { URL.revokeObjectURL(url); img.removeEventListener("load", free); img.removeEventListener("error", free); };
    img.addEventListener("load", free);
    img.addEventListener("error", free);
    img.src = url;
  }

  /** 정리된 크기 — 목록에 */
  function size(bytes) {
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(bytes >= 104857600 ? 0 : 1) + " MB";
    return Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  var api = {
    MAGIC: MAGIC,
    ready: ready,
    readHeader: readHeader,
    add: add,
    remove: remove,
    list: list,
    onChange: onChange,
    coversSync: coversSync,
    held: held,
    tileBlob: tileBlob,
    at: at,
    wrap: wrap,
    size: size,
    setTranslator: setTranslator,
  };
  root.GSMOffline = api;
})(typeof self !== "undefined" ? self : this);
