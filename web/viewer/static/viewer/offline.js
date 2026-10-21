/* 오프라인 묶음 — 박스 하나의 타일을 파일 하나로 들여 망·키 없이 본다 (wetherilli P13·382).
 *
 * 묶음(`.gsmpack`)은 굽는 쪽(패키지 `gsmpack`, wetherilli 381·P16)이 짓는다. 꼴은 패키지의 README(`tools/gsmpack/`)가 정한다.
 * **묶음 하나를 읽는 것(머리·타일·지층 면)은 `gsmpack-reader.js`(`GSMPack`)의 일이다**(wetherilli P16) — 여기는 그 위에 저장소·
 * 여러 묶음·지도 소스 감싸기·화면의 말을 얹는다.
 *
 * 고른 파일(Blob)을 **IndexedDB 에 통째로** 둔다 — 개인 레이어처럼 그 브라우저에만 있다. 타일은 `Blob.slice` 로 그때그때 잘라
 * `URL.createObjectURL` 로 그린다. 200 MB 를 메모리로 읽지 않는다. 서비스 워커(wetherilli 380)는 손대지 않는다.
 *
 * 화면(map.js)은 소스를 지을 때 `wrap(source, 이름)` 만 부른다 — 묶음에 그 타일이 있으면 묶음에서, 묶음의 마지막 줌보다 깊으면 그 줌을 늘려(wetherilli 405), 없으면 원래 손(망)으로.
 * 배경지도 고르개는 IndexedDB 가 열리기 전에 서므로, 덮는 레이어 이름을 localStorage 에도 적어 두고(`coversSync`) 거기서 본다.
 */
(function (root) {
  "use strict";

  var reader = root.GSMPack;
  var DB_NAME = "gsm-offline";
  var STORE = "packs";
  var SYNC_SLOT = "gsm.offline.layers";

  var tr = function (text, vars) {
    return vars ? text.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; }) : text;
  };
  function T(text, vars) { return tr(text, vars); }
  function setTranslator(fn) { if (fn) tr = fn; }

  // ── 머리 ───────────────────────────────────────────────────────

  //: 읽는 쪽의 오류 → 화면의 말
  var READ_ERRORS = {
    "not-pack": function () { return T("오프라인 묶음(.gsmpack)이 아니다"); },
    "truncated": function () { return T("묶음의 머리가 잘렸다"); },
    "bad-header": function () { return T("묶음의 머리를 읽지 못했다"); },
  };

  /** 묶음의 머리 → `{head, base}`. 꼴이 아니면 화면의 말로 거절한다 */
  function readHeader(blob) {
    return reader.readHeader(blob).catch(function (e) {
      throw READ_ERRORS[e && e.code] ? new Error(READ_ERRORS[e.code]()) : e;
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
    for (var i = 0; i < packs.length; i++) {
      var blob = reader.tile(packs[i], name, z, x, y, tileSize);
      if (blob) return blob;
    }
    return null;
  }

  // ── 누른 자리의 속성 — 지층 면 (wetherilli 384) ──
  //
  // 묶음 머리의 `units.<레이어>` — 굽는 쪽이 박스 범위의 지층 면을 넣었다. 처음 누를 때 읽어 두고(`GSMPack.readUnits`) 누른 자리를
  // 품은 면의 속성을 낸다. 새로 구운 묶음이 앞이다

  var shapes = {};                     // 묶음/레이어 → Promise<[{box, polys, props, props_en}]>

  function unitsFor(name) {
    for (var i = 0; i < packs.length; i++) if (reader.hasUnits(packs[i], name)) return packs[i];
    return null;
  }

  function hasUnits(name) { return !!unitsFor(name); }

  /** 레이어의 누른 자리 속성 — `[props…]`(없으면 빈 목록). 묶음에 그 레이어의 지층 면이 없으면 null */
  function unitsAt(name, lon, lat, lang) {
    var pack = unitsFor(name);
    if (!pack) return null;
    var key = pack.id + "/" + name;
    if (!shapes[key]) shapes[key] = reader.readUnits(pack, name);
    return shapes[key].then(function (rows) { return reader.unitsAt(rows, lon, lat, lang); }, function () { return []; });
  }

  /** 경위도 한 자리를 덮는 묶음들 — 화면의 "오프라인: 장성 · 10-10" 표 */
  function at(lon, lat) {
    return packs.filter(function (p) { return reader.contains(p, lon, lat); }).map(summary);
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
      var now = packs.length ? found(name, c[0], c[1], c[2], size) : null;
      if (now || !coversSync(name)) { draw(tile, src, now, original); return; }
      ready.then(function () { draw(tile, src, found(name, c[0], c[1], c[2], size), original); });
    });
    wrapped.push(source);
    return source;
  }

  /** 그 자리에 그릴 것 — 묶음에 그 타일이 있으면 그것(`{blob}`), 없으면 묶음의 마지막 줌 타일에서 이 자리의 칸을 늘려
   *  (`{blob, dz, col, row}`, wetherilli 405). 줌을 다 담은 묶음이 늘린 것보다 앞선다. 없으면 null */
  function found(name, z, x, y, tileSize) {
    var blob = tileBlob(name, z, x, y, tileSize);
    if (blob) return { blob: blob };
    for (var i = 0; i < packs.length; i++) {
      var over = reader.deeper(packs[i], name, z, x, y, tileSize);
      if (over) return over;
    }
    return null;
  }

  /** 마지막 줌 타일의 한 칸을 타일 한 장 크기로 늘린다 → PNG Blob */
  function enlarge(over) {
    var open = root.createImageBitmap ? root.createImageBitmap(over.blob) : new Promise(function (resolve, reject) {
      var im = new Image(), url = URL.createObjectURL(over.blob);
      im.onload = function () { URL.revokeObjectURL(url); resolve(im); };
      im.onerror = function () { URL.revokeObjectURL(url); reject(new Error("tile")); };
      im.src = url;
    });
    return open.then(function (image) {
      var w = image.width, part = w / Math.pow(2, over.dz);
      var canvas = document.createElement("canvas");
      canvas.width = canvas.height = w;
      var ctx = canvas.getContext("2d");
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(image, over.col * part, over.row * part, part, part, 0, 0, w, w);
      if (image.close) image.close();
      return new Promise(function (resolve, reject) {
        canvas.toBlob(function (b) { if (b) resolve(b); else reject(new Error("canvas")); }, "image/png");
      });
    });
  }

  function draw(tile, src, got, original) {
    if (!got) { original(tile, src); return; }
    if (got.dz) {
      enlarge(got).then(function (blob) { show(tile, blob); }, function () { original(tile, src); });
      return;
    }
    show(tile, got.blob);
  }

  function show(tile, blob) {
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
    MAGIC: reader.MAGIC,
    ready: ready,
    readHeader: readHeader,
    add: add,
    remove: remove,
    list: list,
    onChange: onChange,
    coversSync: coversSync,
    held: held,
    tileBlob: tileBlob,
    hasUnits: hasUnits,
    unitsAt: unitsAt,
    at: at,
    wrap: wrap,
    size: size,
    setTranslator: setTranslator,
  };
  root.GSMOffline = api;
})(typeof self !== "undefined" ? self : this);
