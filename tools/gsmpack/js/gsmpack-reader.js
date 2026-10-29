/* 오프라인 묶음(`.gsmpack`) 읽기 — 묶음 하나의 머리·타일·지층 면 (wetherilli P16, `offline.js` 에서 뗐다).
 *
 * 꼴은 패키지의 README 와 `gsmpack/format.py` 가 정한다. 라이브러리 없이 `Blob.slice` 로만 읽는다 — 200 MB 를 메모리로 읽지 않는다.
 * 저장(IndexedDB 따위)·지도(OpenLayers 따위)·화면의 말은 모른다. 그것은 부르는 쪽(GSM 의 `offline.js`)의 일이다.
 *
 * 묶음 하나는 `{blob, head, base}` — `readHeader(blob)` 가 `{head, base}` 를 준다. 아래 함수는 모두 그것을 받는다.
 * 오류에는 `code` 가 붙는다 — `not-pack`(꼴이 아니다)·`truncated`(머리가 잘렸다)·`bad-header`(머리를 읽지 못했다).
 * 화면의 말은 부르는 쪽이 `code` 로 고른다.
 */
(function (root) {
  "use strict";

  var MAGIC = "GSMPACK1";

  function fail(code, message) {
    var e = new Error(message);
    e.code = code;
    return e;
  }

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
      if (bytes.length < 12 || magic !== MAGIC) throw fail("not-pack", "not a .gsmpack");
      var n = new DataView(buf).getUint32(8, true);
      if (12 + n > blob.size) throw fail("truncated", "header is truncated");
      return readSlice(blob, 12, 12 + n).then(function (raw) {
        var head;
        try { head = JSON.parse(new TextDecoder("utf-8").decode(raw)); } catch (e) { head = null; }
        if (!head || typeof head.tiles !== "object" || typeof head.layers !== "object") {
          throw fail("bad-header", "cannot read the header");
        }
        return { head: head, base: 12 + n };
      });
    });
  }

  /** 레이어·타일 자리의 Blob 하나, 없으면 null. 열쇠는 화면의 tileCoord 그대로다 — 격자는 머리의 `layers.<이름>.tile_size`.
   *  `want` 를 주면 격자가 다른 묶음은 null 이다 — 격자가 어긋난 묶음이 엉뚱한 자리에 그리지 않게. `want` 는 타일 크기(수) 또는
   *  `{size, grid}` — 남극 탭에는 256 px 격자가 셋이라(3031·Esri 극 격자·옮겨 그리는 3857) 크기만으로는 못 가른다(wetherilli 410) */
  function tile(pack, name, z, x, y, want) {
    var at = pack.head.tiles[name + "/" + z + "/" + x + "/" + y];
    if (!at) return null;
    var meta = pack.head.layers[name] || {};
    if (!fits(meta, want)) return null;
    return pack.blob.slice(pack.base + at[0], pack.base + at[0] + at[1], meta.type || "image/png");
  }

  /** 머리의 레이어(`tile_size`·`grid`)가 화면 소스의 격자와 맞나. `grid` 를 적지 않은 옛 묶음은 3857 이다 */
  function fits(meta, want) {
    if (!want) return true;
    var size = typeof want === "number" ? want : want.size;
    if (size && meta.tile_size && meta.tile_size !== size) return false;
    return typeof want === "number" || !want.grid || (meta.grid || "EPSG:3857") === want.grid;
  }

  //: 늘려 그리는 한도 — 마지막 줌에서 이만큼 깊은 줌까지(2^4 = 16 배). 그보다 깊으면 그릴 것이 없다고 본다
  var MAX_OVERZOOM = 4;

  /** 굽다가 받지 못한 자리인가 — 머리의 `missing`(열쇠 목록, wetherilli 409). 없는 열쇠라도 이것이 아니면 "그릴 것이 없는 자리" 다 */
  function missing(pack, name, z, x, y) {
    var list = pack.head.missing;
    return !!list && list.indexOf(name + "/" + z + "/" + x + "/" + y) >= 0;
  }

  /** 묶음에 없는 자리를 얕은 줌의 타일로 메운다 — 묶음의 마지막 줌보다 깊은 자리(wetherilli 405)와, 굽다가 받지 못한 자리(`missing`,
   *  wetherilli 409). 이 자리를 품은 가장 깊은 타일과 그 안에서 이 자리가 차지하는 칸 — `{blob, dz, col, row}` 는 타일 한 변을 2^dz 로
   *  나눈 칸 가운데 왼쪽에서 col, 위에서 row 번째다. 묶음이 그 자리를 담았거나(그때는 `tile` 이 답한다) 그 자리에 그릴 것이 없으면
   *  (바다 따위) null. 받지 못한 타일 위로는 한 줌씩 더 올라간다 */
  function deeper(pack, name, z, x, y, want) {
    var meta = pack.head.layers[name];
    if (!meta || !meta.zooms) return null;
    var first = meta.zooms[0], last = meta.zooms[1];
    if (z <= last && !missing(pack, name, z, x, y)) return null;
    for (var p = Math.min(last, z - 1); p >= first && z - p <= MAX_OVERZOOM; p--) {
      var dz = z - p, px = x >> dz, py = y >> dz;
      var blob = tile(pack, name, p, px, py, want);
      if (blob) return { blob: blob, dz: dz, col: x - (px << dz), row: y - (py << dz) };
      if (!missing(pack, name, p, px, py)) return null;
    }
    return null;
  }

  /** 경위도 한 자리가 묶음의 범위(`bbox`) 안인가 */
  function contains(pack, lon, lat) {
    var b = pack.head.bbox;
    return !!b && lon >= b[0] && lon <= b[2] && lat >= b[1] && lat <= b[3];
  }

  // ── 누른 자리의 속성 — 지층 면 (wetherilli 384) ──
  //
  // 머리의 `units.<레이어>` 는 `{key: "@units/<레이어>", …}` — 박스 범위의 지층 면 GeoJSON 한 덩이다. 면마다 네모를 셈해 두고
  // 누른 자리를 품은 면의 속성을 낸다. 범례 색으로 찾지 않는다 — 한 도폭 안에서도 단위 둘이 한 색이다

  /** 그 레이어의 지층 면이 묶음에 있나 */
  function hasUnits(pack, name) {
    var u = (pack.head.units || {})[name];
    return !!(u && u.key && pack.head.tiles[u.key]);
  }

  /** 지층 면 → `[{box, polys, props, props_en}]`. 없으면 빈 목록 */
  function readUnits(pack, name) {
    if (!hasUnits(pack, name)) return Promise.resolve([]);
    var at = pack.head.tiles[pack.head.units[name].key];
    var part = pack.blob.slice(pack.base + at[0], pack.base + at[0] + at[1]);
    return (part.text ? part.text() : new Response(part).text()).then(function (text) {
      return (JSON.parse(text).features || []).map(function (f) {
        var g = f.geometry || {};
        var polys = g.type === "MultiPolygon" ? g.coordinates : [g.coordinates];
        var box = [Infinity, Infinity, -Infinity, -Infinity];
        polys.forEach(function (poly) {
          (poly[0] || []).forEach(function (c) {
            box[0] = Math.min(box[0], c[0]); box[1] = Math.min(box[1], c[1]);
            box[2] = Math.max(box[2], c[0]); box[3] = Math.max(box[3], c[1]);
          });
        });
        return { box: box, polys: polys, props: f.properties.props, props_en: f.properties.props_en };
      });
    });
  }

  /** 고리 하나 안인가 — 반직선이 변을 몇 번 건너나 */
  function inRing(ring, x, y) {
    var inside = false;
    for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      var a = ring[i], b = ring[j];
      if ((a[1] > y) !== (b[1] > y) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
    }
    return inside;
  }

  /** 면 하나(바깥 고리와 구멍들) 안인가 */
  function inPolygon(poly, x, y) {
    if (!poly.length || !inRing(poly[0], x, y)) return false;
    for (var k = 1; k < poly.length; k++) if (inRing(poly[k], x, y)) return false;
    return true;
  }

  /** `readUnits` 가 준 면들에서 경위도 한 자리를 품은 것의 속성 — `[props…]`, 같은 것은 한 번. `lang` 이 "en" 이면 영어판 */
  function unitsAt(rows, lon, lat, lang) {
    var seen = {}, out = [];
    rows.forEach(function (r) {
      if (lon < r.box[0] || lon > r.box[2] || lat < r.box[1] || lat > r.box[3]) return;
      if (!r.polys.some(function (poly) { return inPolygon(poly, lon, lat); })) return;
      var props = lang === "en" && r.props_en ? r.props_en : r.props;
      var mark = JSON.stringify(props);
      if (!seen[mark]) { seen[mark] = true; out.push(props); }
    });
    return out;
  }

  // ── 점·모양 덩이 (wetherilli 434) ──
  //
  // 머리의 `vectors.<레이어>` 는 `{key: "@vectors/<레이어>", …}` — 서버의 `points/?layer=` 가 주는 덩이 그대로에서 박스에 닿는 모양만 남긴 것

  /** 그 레이어의 점·모양 덩이가 묶음에 있나 */
  function hasVector(pack, name) {
    var v = (pack.head.vectors || {})[name];
    return !!(v && v.key && pack.head.tiles[v.key]);
  }

  /** 점·모양 덩이 → GeoJSON 객체(`legend`·`labels` 칸까지). 없으면 null */
  function readVector(pack, name) {
    if (!hasVector(pack, name)) return Promise.resolve(null);
    var at = pack.head.tiles[pack.head.vectors[name].key];
    var part = pack.blob.slice(pack.base + at[0], pack.base + at[0] + at[1]);
    return (part.text ? part.text() : new Response(part).text()).then(JSON.parse);
  }

  root.GSMPack = {
    MAGIC: MAGIC,
    readHeader: readHeader,
    tile: tile,
    deeper: deeper,
    missing: missing,
    contains: contains,
    hasUnits: hasUnits,
    readUnits: readUnits,
    unitsAt: unitsAt,
    hasVector: hasVector,
    readVector: readVector,
  };
})(typeof self !== "undefined" ? self : this);
