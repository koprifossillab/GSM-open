/* 개인 레이어 — 이 브라우저에만 두는 내 자료 (wetherilli P08·118).
 *
 * 양식은 docs/개인레이어_양식.md 하나다. 여기는 그 양식을 읽고(`parse`),
 * 다시 쓰고(`toGeoJSON`·`toCSV`), 브라우저 저장소(IndexedDB)에 넣고 빼는 일만 한다.
 * 서버로 보내지 않는다 — 점묶음(`PointSet`)과 다른 자리다.
 *
 * **점·선·면은 좌표 값의 꼴이 정한다.** JSON 은 geometry 의 type,
 * CSV 는 lon·lat 두 칸(점)이냐 geometry 칸의 WKT(점·선·면)냐. 한 레이어에는 한 가지 —
 * **섞여 오면 모양별로 갈라 여러 레이어로 만든다**(`split`, wetherilli 126).
 *
 * 관리 화면(manage.js)과 지도(map.js)가 함께 쓰고, node 로도 읽힌다(시험).
 * 화면 문장은 부르는 쪽의 `T` 로 옮긴다 — 여기 문장도 `T("…")` 로 감싸 시험이 긁는다.
 */
(function (root) {
  "use strict";

  var FORMAT = "gsm-personal-layer";
  var VERSION = 1;
  var TYPES = ["string", "integer", "number"];
  var RESERVED = ["id", "lon", "lat", "geometry"];
  var LON_ALIASES = ["lon", "lng", "long", "longitude", "경도", "x"];
  var LAT_ALIASES = ["lat", "latitude", "위도", "y"];
  var DEFAULT_COLOR = "#e15759";
  //: 새 레이어의 색 — 머리에 색이 없으면 여기서 고른다(wetherilli 131). 위성·지질도 위에서 서로 갈리는 열둘
  var PALETTE = ["#e15759", "#f28e2b", "#edc948", "#59a14f", "#76b7b2", "#4e79a7",
                 "#b07aa1", "#ff9da7", "#9c755f", "#17becf", "#bcbd22", "#ffffff"];
  //: 점의 모양
  var SHAPES = ["circle", "square", "diamond", "triangle", "star", "hexagon"];

  // 옮기개는 부르는 쪽이 건다(`setTranslator`). 없으면 원문 그대로 자리표만 채운다
  var tr = function (text, vars) {
    return String(text).replace(/\{(\w+)\}/g, function (m, k) {
      return vars && vars[k] !== undefined ? vars[k] : m;
    });
  };
  function T(text, vars) { return tr(text, vars); }
  function setTranslator(fn) { if (fn) tr = fn; }

  function ParseError(message) { this.message = message; }
  ParseError.prototype = Object.create(Error.prototype);
  ParseError.prototype.name = "ParseError";

  // ── 바이트 -> 글자 ─────────────────────────────────────────────

  /** UTF-8 이 아니면 EUC-KR(CP949)로 읽는다 — 한국어 엑셀이 CSV 를 그렇게 저장한다. */
  function decode(buffer) {
    var bytes = new Uint8Array(buffer);
    try {
      return { text: new TextDecoder("utf-8", { fatal: true }).decode(bytes).replace(/^﻿/, ""), encoding: "utf-8" };
    } catch (e) {
      return { text: new TextDecoder("euc-kr").decode(bytes), encoding: "euc-kr" };
    }
  }

  // ── CSV ────────────────────────────────────────────────────────

  /** RFC 4180 — 따옴표 안의 쉼표·줄바꿈·"" 를 안다. 줄마다 [칸…, 원래 줄 번호]. */
  function csvRows(text) {
    var rows = [], row = [], cell = "", quoted = false, line = 1, start = 1;
    for (var i = 0; i < text.length; i++) {
      var c = text[i];
      if (quoted) {
        if (c === '"') {
          if (text[i + 1] === '"') { cell += '"'; i++; } else quoted = false;
        } else {
          if (c === "\n") line++;
          cell += c;
        }
        continue;
      }
      if (c === '"' && cell === "") { quoted = true; continue; }
      if (c === ",") { row.push(cell); cell = ""; continue; }
      if (c === "\r") continue;
      if (c === "\n") {
        row.push(cell);
        rows.push({ cells: row, line: start });
        row = []; cell = ""; line++; start = line;
        continue;
      }
      cell += c;
    }
    if (cell !== "" || row.length) { row.push(cell); rows.push({ cells: row, line: start }); }
    return rows;
  }

  function csvCell(value) {
    if (value === null || value === undefined) return "";
    var s = String(value);
    return /[",\r\n]/.test(s) || /^\s|\s$/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  /** 머리말 `#열쇠: 값` 들. `#column:` 은 여럿이다. */
  function readHeaderLines(rows) {
    var meta = {}, columns = [], body = [];
    rows.forEach(function (r) {
      var first = r.cells[0] || "";
      if (!body.length && first.charAt(0) === "#") {
        var whole = r.cells.join(",");     // 값 안의 쉼표를 되살린다
        var m = /^#\s*([\w.-]+)\s*:\s*(.*)$/.exec(whole);
        if (!m) return;
        var key = m[1].toLowerCase(), value = m[2].trim();
        if (key === "column") {
          var parts = value.split("|").map(function (s) { return s.trim(); });
          columns.push({ key: parts[0], label: parts[1] || parts[0], type: parts[2] || "string", note: parts.slice(3).join(" | ") });
        } else {
          meta[key] = value;
        }
        return;
      }
      if (!body.length && r.cells.length === 1 && r.cells[0].trim() === "") return;
      body.push(r);
    });
    return { meta: meta, columns: columns, body: body };
  }

  function typed(raw, type) {
    if (raw === "" || raw === null || raw === undefined) return null;
    if (type === "integer" || type === "number") {
      var n = Number(String(raw).trim());
      if (!isFinite(n)) return raw;            // 잃지 않는다 — 글자 그대로 둔다
      if (type === "integer" && Math.floor(n) !== n) return raw;
      return n;
    }
    return raw;
  }

  function findColumn(header, aliases) {
    var low = header.map(function (h) { return h.trim().toLowerCase(); });
    for (var i = 0; i < aliases.length; i++) {
      var at = low.indexOf(aliases[i]);
      if (at >= 0) return at;
    }
    return -1;
  }

  function parseCSV(text) {
    var head = readHeaderLines(csvRows(String(text).replace(/^\uFEFF/, "")));
    if (!head.body.length) throw new ParseError(T("머리줄이 없다"));
    var header = head.body[0].cells.map(function (h) { return h.trim(); });
    var rows = head.body.slice(1).filter(function (r) {
      return r.cells.some(function (c) { return c.trim() !== ""; });
    });

    var geomAt = findColumn(header, ["geometry", "wkt"]);
    var lonAt = findColumn(header, LON_ALIASES);
    var latAt = findColumn(header, LAT_ALIASES);
    var idAt = findColumn(header, ["id"]);
    if (geomAt < 0 && (lonAt < 0 || latAt < 0)) {
      throw new ParseError(T("좌표 칸이 없다 — 점은 lon·lat, 면은 geometry(WKT)"));
    }
    var warnings = [];
    if (geomAt < 0 && (header[lonAt].toLowerCase() !== "lon" || header[latAt].toLowerCase() !== "lat")) {
      warnings.push(T("좌표 칸 이름이 양식과 다르다 ({lon}·{lat}) — lon·lat 으로 읽었다", { lon: header[lonAt], lat: header[latAt] }));
    }

    var declared = {};
    head.columns.forEach(function (c) { declared[c.key] = c; });
    var skip = [geomAt, lonAt, latAt, idAt];
    var columns = [];
    header.forEach(function (h, i) {
      if (skip.indexOf(i) >= 0 && !(geomAt >= 0 && (i === lonAt || i === latAt))) return;
      var d = declared[h] || { key: h, label: h, type: "string", note: "" };
      columns.push({ key: h, label: d.label || h, type: TYPES.indexOf(d.type) >= 0 ? d.type : "string", note: d.note || "", at: i });
    });

    var features = [], problems = [];
    rows.forEach(function (r) {
      var cells = r.cells;
      if (cells.length !== header.length) {
        problems.push(T("{line}째 줄 — 칸 수가 머리줄과 다르다 ({n}/{m})", { line: r.line, n: cells.length, m: header.length }));
      }
      var geometry = null;
      try {
        if (geomAt >= 0) {
          geometry = (cells[geomAt] || "").trim() ? parseWKT(cells[geomAt]) : null;
        } else {
          var lonRaw = (cells[lonAt] || "").trim(), latRaw = (cells[latAt] || "").trim();
          if (lonRaw || latRaw) geometry = pointGeometry(lonRaw, latRaw);
        }
      } catch (e) {
        problems.push(T("{line}째 줄 — {why}", { line: r.line, why: e.message }));
        geometry = null;
      }
      var props = {};
      columns.forEach(function (c) { props[c.key] = typed(cells[c.at] === undefined ? "" : cells[c.at], c.type); });
      var f = { type: "Feature", geometry: geometry, properties: props };
      if (idAt >= 0 && (cells[idAt] || "") !== "") f.id = cells[idAt];
      features.push(f);
    });
    columns.forEach(function (c) { delete c.at; });
    // 머리는 글자로 읽힌다. 판 번호만은 JSON 과 같게 숫자로 둔다
    if (head.meta.version !== undefined && isFinite(Number(head.meta.version))) head.meta.version = Number(head.meta.version);

    return finish({
      meta: head.meta,
      columns: columns,
      features: features,
      problems: problems,
      warnings: warnings,
      format: "csv",
    });
  }

  function pointGeometry(lonRaw, latRaw) {
    var lon = Number(lonRaw), lat = Number(latRaw);
    if (lonRaw === "" || latRaw === "" || !isFinite(lon) || !isFinite(lat)) {
      throw new ParseError(T("좌표를 읽지 못했다 ({lon}, {lat})", { lon: lonRaw, lat: latRaw }));
    }
    checkLonLat(lon, lat);
    return { type: "Point", coordinates: [lon, lat] };
  }

  function checkLonLat(lon, lat) {
    if (Math.abs(lat) > 90 || Math.abs(lon) > 180) {
      throw new ParseError(T("위경도 범위 밖이다 ({lon}, {lat}) — 십진도 WGS84 만 받는다", { lon: lon, lat: lat }));
    }
  }

  // ── WKT (점·면만) ───────────────────────────────────────────────

  function parseWKT(text) {
    var s = String(text).trim();
    var m = /^(MULTIPOINT|POINT|MULTILINESTRING|LINESTRING|MULTIPOLYGON|POLYGON)\s*(Z|M|ZM)?\s*(\(.*\))\s*$/i.exec(s);
    if (!m) throw new ParseError(T("WKT 를 읽지 못했다 — POINT·LINESTRING·POLYGON 과 그 MULTI 만 받는다"));
    var type = m[1].toUpperCase();
    var nested = nest(m[3]);
    function pos(str) {
      var n = str.trim().split(/\s+/).map(Number);
      if (n.length < 2 || !isFinite(n[0]) || !isFinite(n[1])) throw new ParseError(T("WKT 좌표를 읽지 못했다"));
      checkLonLat(n[0], n[1]);
      return [n[0], n[1]];
    }
    function ring(node) {
      if (!Array.isArray(node)) throw new ParseError(T("WKT 괄호가 맞지 않는다"));
      return node.map(function (n) { return pos(leaf(n)); });
    }
    if (type === "POINT") return { type: "Point", coordinates: pos(leaf(nested)) };
    if (type === "MULTIPOINT") {
      return { type: "MultiPoint", coordinates: nested.map(function (n) { return pos(leaf(n)); }) };
    }
    if (type === "LINESTRING") return { type: "LineString", coordinates: ring(nested) };
    if (type === "MULTILINESTRING") return { type: "MultiLineString", coordinates: nested.map(ring) };
    if (type === "POLYGON") return { type: "Polygon", coordinates: nested.map(ring) };
    return { type: "MultiPolygon", coordinates: nested.map(function (p) {
      if (!Array.isArray(p)) throw new ParseError(T("WKT 괄호가 맞지 않는다"));
      return p.map(ring);
    }) };
  }

  /** "((1 2, 3 4), (5 6))" -> [["1 2", "3 4"], ["5 6"]]. 잎은 괄호 없는 좌표 글자. */
  function nest(str) {
    var i = 0;
    function list() {
      if (str[i] !== "(") throw new ParseError(T("WKT 괄호가 맞지 않는다"));
      i++;
      var items = [];
      for (;;) {
        while (/\s/.test(str[i] || "")) i++;
        if (str[i] === "(") items.push(list());
        else {
          var j = i;
          while (i < str.length && str[i] !== "," && str[i] !== ")") i++;
          items.push(str.slice(j, i).trim());
        }
        while (/\s/.test(str[i] || "")) i++;
        if (str[i] === ",") { i++; continue; }
        if (str[i] === ")") { i++; return items; }
        throw new ParseError(T("WKT 괄호가 맞지 않는다"));
      }
    }
    var out = list();
    if (str.slice(i).trim()) throw new ParseError(T("WKT 괄호가 맞지 않는다"));
    return out;
  }

  /** 잎 하나 — MULTIPOINT 는 (1 2) 와 1 2 를 다 받는다. */
  function leaf(node) {
    if (typeof node === "string") return node;
    if (node.length === 1 && typeof node[0] === "string") return node[0];
    throw new ParseError(T("WKT 괄호가 맞지 않는다"));
  }

  function wkt(geometry) {
    if (!geometry) return "";
    function pos(p) { return p[0] + " " + p[1]; }
    function ring(r) { return "(" + r.map(pos).join(", ") + ")"; }
    var c = geometry.coordinates;
    switch (geometry.type) {
      case "Point": return "POINT (" + pos(c) + ")";
      case "MultiPoint": return "MULTIPOINT (" + c.map(function (p) { return "(" + pos(p) + ")"; }).join(", ") + ")";
      case "LineString": return "LINESTRING " + ring(c);
      case "MultiLineString": return "MULTILINESTRING (" + c.map(ring).join(", ") + ")";
      case "Polygon": return "POLYGON (" + c.map(ring).join(", ") + ")";
      case "MultiPolygon": return "MULTIPOLYGON (" + c.map(function (p) { return "(" + p.map(ring).join(", ") + ")"; }).join(", ") + ")";
    }
    return "";
  }

  // ── JSON (GeoJSON + gsm 머리) ───────────────────────────────────

  function parseJSON(text) {
    var doc;
    try { doc = JSON.parse(String(text).replace(/^\uFEFF/, "")); } catch (e) { throw new ParseError(T("JSON 을 읽지 못했다 — {why}", { why: e.message })); }
    // 피처 하나(API 의 상세 주소 따위)면 하나짜리 묶음으로 본다
    if (doc && doc.type === "Feature") doc = { type: "FeatureCollection", features: [doc] };
    if (!doc || doc.type !== "FeatureCollection" || !Array.isArray(doc.features)) {
      throw new ParseError(T("GeoJSON FeatureCollection 이 아니다"));
    }
    var head = doc.gsm || {};
    var warnings = [];
    if (!doc.gsm) warnings.push(T("gsm 머리가 없다 — 이름·열 설명 없이 읽었다"));
    var meta = {};
    Object.keys(head).forEach(function (k) { if (k !== "columns") meta[k] = head[k]; });

    var columns = (head.columns || []).map(function (c) {
      return { key: c.key, label: c.label || c.key, type: TYPES.indexOf(c.type) >= 0 ? c.type : "string", note: c.note || "" };
    });
    var known = {};
    columns.forEach(function (c) { known[c.key] = true; });

    var problems = [];
    var features = doc.features.map(function (f, i) {
      var geometry = f && f.geometry ? f.geometry : null;
      if (geometry) {
        try { checkGeometry(geometry); } catch (e) {
          problems.push(T("{n}째 피처 — {why}", { n: i + 1, why: e.message }));
          geometry = null;
        }
      }
      var props = (f && f.properties) || {};
      Object.keys(props).forEach(function (k) {
        if (!known[k]) { known[k] = true; columns.push({ key: k, label: k, type: guessType(props[k]), note: "" }); }
      });
      var out = { type: "Feature", geometry: geometry, properties: props };
      if (f && f.id !== undefined) out.id = f.id;
      return out;
    });

    return finish({ meta: meta, columns: columns, features: features, problems: problems, warnings: warnings, format: "json" });
  }

  function guessType(v) {
    if (typeof v === "number") return Number.isInteger(v) ? "integer" : "number";
    return "string";
  }

  function checkGeometry(g) {
    var depth = { Point: 0, MultiPoint: 1, LineString: 1, MultiLineString: 2, Polygon: 2, MultiPolygon: 3 };
    if (!(g.type in depth)) throw new ParseError(T("{type} 은 받지 않는다 — 점·선·면만", { type: g.type }));
    (function walk(c, depth) {
      if (depth === 0) {
        if (!Array.isArray(c) || c.length < 2 || !isFinite(c[0]) || !isFinite(c[1])) throw new ParseError(T("좌표를 읽지 못했다"));
        checkLonLat(c[0], c[1]);
        return;
      }
      if (!Array.isArray(c)) throw new ParseError(T("좌표를 읽지 못했다"));
      c.forEach(function (x) { walk(x, depth - 1); });
    })(g.coordinates, depth[g.type]);
  }

  // ── 마무리 — 점·선·면 가르기 ───────────────────────────────────

  var KINDS = ["point", "line", "polygon"];

  function kindOf(geometry) {
    if (!geometry) return null;
    if (/Point$/.test(geometry.type)) return "point";
    return /LineString$/.test(geometry.type) ? "line" : "polygon";
  }

  function finish(r) {
    var kinds = {};
    r.features.forEach(function (f) { var k = kindOf(f.geometry); if (k) kinds[k] = (kinds[k] || 0) + 1; });
    var names = KINDS.filter(function (k) { return kinds[k]; });
    if (!names.length) throw new ParseError(T("그릴 좌표가 하나도 없다"));
    var meta = r.meta;
    if (meta.format && meta.format !== FORMAT) r.warnings.push(T("양식 이름이 다르다 ({name})", { name: meta.format }));
    if (meta.version && Number(meta.version) > VERSION) r.warnings.push(T("더 새 판의 양식이다 (v{v}) — 아는 것만 읽었다", { v: meta.version }));
    var drawn = names.reduce(function (n, k) { return n + kinds[k]; }, 0);
    return {
      // 섞였으면 "mixed" — 저장할 때 `split` 으로 모양마다 한 레이어가 된다
      kind: names.length > 1 ? "mixed" : names[0],
      kinds: kinds,
      name: meta.name || "",
      meta: meta,
      columns: r.columns,
      features: r.features,
      count: r.features.length,
      drawn: drawn,
      undrawn: r.features.length - drawn,
      problems: r.problems,
      warnings: r.warnings,
      format: r.format,
    };
  }

  /** 읽은 것을 모양마다 하나로 가른다 → [읽은 것…]. 한 가지면 그대로 하나.
   *  좌표가 없는 행은 맨 앞 갈래에 둔다 — 버리지 않는다(되쓰면 원본의 행이 다 나온다). */
  function split(parsed) {
    if (parsed.kind !== "mixed") return [parsed];
    var names = KINDS.filter(function (k) { return parsed.kinds[k]; });
    return names.map(function (kind, i) {
      var features = parsed.features.filter(function (f) {
        var k = kindOf(f.geometry);
        return k === kind || (!k && i === 0);
      });
      var out = {};
      Object.keys(parsed).forEach(function (key) { out[key] = parsed[key]; });
      out.kind = kind;
      out.kinds = {};
      out.kinds[kind] = parsed.kinds[kind];
      out.features = features;
      out.count = features.length;
      out.drawn = parsed.kinds[kind];
      out.undrawn = features.length - out.drawn;
      return out;
    });
  }

  /** 파일 이름과 글자로 읽는다. 끝이 .csv·.tsv 가 아니면 JSON 으로 본다. */
  function parse(text, filename) {
    var csv = /\.csv$/i.test(filename || "") || (!/^\uFEFF?\s*[\[{]/.test(text));
    return csv ? parseCSV(text) : parseJSON(text);
  }

  // ── 다시 쓰기 ──────────────────────────────────────────────────

  function headOf(layer) {
    var head = { format: FORMAT, version: VERSION };
    Object.keys(layer.meta || {}).forEach(function (k) {
      if (k !== "format" && k !== "version" && k !== "columns") head[k] = layer.meta[k];
    });
    if (layer.name) head.name = layer.name;
    if (layer.color) head.color = layer.color;
    head.columns = layer.columns.map(function (c) {
      var out = { key: c.key, label: c.label, type: c.type };
      if (c.note) out.note = c.note;
      return out;
    });
    return head;
  }

  function toGeoJSON(layer) {
    return {
      type: "FeatureCollection",
      gsm: headOf(layer),
      features: layer.features.map(function (f) {
        var out = { type: "Feature" };
        if (f.id !== undefined) out.id = f.id;
        out.geometry = f.geometry;
        out.properties = f.properties;
        return out;
      }),
    };
  }

  function toCSV(layer) {
    var head = headOf(layer);
    var lines = [];
    Object.keys(head).forEach(function (k) {
      if (k === "columns") return;
      var v = head[k];
      lines.push("#" + k + ": " + (typeof v === "object" ? JSON.stringify(v) : String(v).replace(/[\r\n]+/g, " ")));
    });
    head.columns.forEach(function (c) {
      lines.push("#column: " + [c.key, c.label, c.type].concat(c.note ? [c.note] : []).join(" | ").replace(/[\r\n]+/g, " "));
    });
    var hasId = layer.features.some(function (f) { return f.id !== undefined; });
    var point = layer.kind === "point" && layer.features.every(function (f) { return !f.geometry || f.geometry.type === "Point"; });
    var cols = (hasId ? ["id"] : []).concat(point ? ["lon", "lat"] : ["geometry"]).concat(head.columns.map(function (c) { return c.key; }));
    lines.push(cols.map(csvCell).join(","));
    layer.features.forEach(function (f) {
      var row = hasId ? [f.id === undefined ? "" : f.id] : [];
      if (point) row.push(f.geometry ? f.geometry.coordinates[0] : "", f.geometry ? f.geometry.coordinates[1] : "");
      else row.push(wkt(f.geometry));
      head.columns.forEach(function (c) { row.push(f.properties[c.key]); });
      lines.push(row.map(csvCell).join(","));
    });
    return "﻿" + lines.join("\r\n") + "\r\n";
  }

  // ── 브라우저 저장소 ─────────────────────────────────────────────
  //
  // IndexedDB 에 둔다 — localStorage 는 5 MB 남짓이고 글자만 받는다.
  // 같은 주소(오리진)의 지도와 관리 화면이 같은 것을 본다.

  var DB_NAME = "gsm-personal";
  var STORE = "layers";
  var CHANNEL = "gsm-personal";

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
        var store = t.objectStore(STORE);
        var result;
        Promise.resolve(work(store, function (r) { result = r; })).catch(reject);
        t.oncomplete = function () { db.close(); resolve(result); };
        t.onerror = function () { db.close(); reject(t.error); };
        t.onabort = function () { db.close(); reject(t.error || new Error(T("저장하지 못했다 — 저장소가 찼을 수 있다"))); };
      });
    });
  }

  function list() {
    return tx("readonly", function (store, done) {
      var req = store.getAll();
      req.onsuccess = function () {
        done(req.result.sort(function (a, b) { return (b.imported || "").localeCompare(a.imported || ""); }));
      };
    });
  }

  function get(id) {
    return tx("readonly", function (store, done) {
      var req = store.get(id);
      req.onsuccess = function () { done(req.result); };
    });
  }

  function put(record) {
    return tx("readwrite", function (store) { store.put(record); }).then(function () { announce(); return record; });
  }

  function remove(id) {
    return tx("readwrite", function (store) { store.delete(id); }).then(announce);
  }

  function clear() {
    return tx("readwrite", function (store) { store.clear(); }).then(announce);
  }

  /** 읽은 것(`parse` 의 결과)을 저장할 꼴로. */
  function record(parsed, file) {
    var now = new Date();
    return {
      id: "pl-" + now.getTime().toString(36) + "-" + Math.random().toString(36).slice(2, 7),
      name: parsed.name || (file && file.name ? file.name.replace(/\.[^.]+$/, "") : T("이름 없는 레이어")),
      kind: parsed.kind,
      color: /^#[0-9a-f]{6}$/i.test(parsed.meta.color || "") ? parsed.meta.color
        : PALETTE[Math.floor(Math.random() * (PALETTE.length - 1))],
      label: parsed.meta.label || "",
      visible: true,
      meta: parsed.meta,
      columns: parsed.columns,
      features: parsed.features,
      count: parsed.count,
      drawn: parsed.drawn,
      file: file ? { name: file.name, size: file.size, format: parsed.format } : null,
      imported: now.toISOString(),
    };
  }

  /** 대략의 크기 — 저장한 JSON 의 글자 수. */
  function sizeOf(rec) {
    var text;
    try { text = JSON.stringify(rec); } catch (e) { return 0; }
    try { return new Blob([text]).size; } catch (e) { return text.length; }   // UTF-8 바이트
  }

  // ── 용량 (wetherilli 131) ──────────────────────────────────────
  //
  // 브라우저 저장소는 한도가 있고(브라우저·디스크마다 다르다), 차면 저장이 실패하거나 브라우저가 통째로 지운다.
  // 레이어 하나가 크면 지도가 느려진다. 그래서 재어 보고 넘으면 알린다 — 막지는 않는다(자리가 정말 없을 때만 빼고).

  var LIMITS = {
    layer: 10 * 1024 * 1024,      // 레이어 하나 — 이보다 크면 지도가 느려질 수 있다
    total: 100 * 1024 * 1024,     // 개인 레이어 전체
    quotaWarn: 0.8,               // 이 사이트의 저장소가 한도의 이만큼을 넘으면
    quotaFull: 0.95,
  };

  function formatBytes(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    if (n < 1024 * 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
    return (n / 1024 / 1024 / 1024).toFixed(2) + " GB";
  }

  function estimate() {
    if (!root.navigator || !navigator.storage || !navigator.storage.estimate) return Promise.resolve({});
    return navigator.storage.estimate().catch(function () { return {}; });
  }

  /** 기록들을 잰다 → { layers: [{id, name, bytes, big}], total, usage, quota, warnings: [{level: warn|bad, text}] } */
  function measure(recs) {
    var layers = (recs || []).map(function (r) {
      var b = sizeOf(r);
      return { id: r.id, name: r.name, bytes: b, big: b > LIMITS.layer };
    });
    var total = layers.reduce(function (n, l) { return n + l.bytes; }, 0);
    return estimate().then(function (e) {
      var out = { layers: layers, total: total, usage: e.usage || 0, quota: e.quota || 0, warnings: [] };
      layers.filter(function (l) { return l.big; }).forEach(function (l) {
        out.warnings.push({ level: "warn", text: T("'{name}' 이 {size} 다 — 지도가 느려질 수 있다", { name: l.name, size: formatBytes(l.bytes) }) });
      });
      if (total > LIMITS.total) {
        out.warnings.push({ level: "warn", text: T("개인 레이어가 모두 {size} 다 — 쓰지 않는 것은 지우는 편이 낫다", { size: formatBytes(total) }) });
      }
      if (out.quota) {
        var ratio = out.usage / out.quota;
        if (ratio >= LIMITS.quotaFull) {
          out.warnings.push({ level: "bad", text: T("이 브라우저의 저장소가 거의 찼다 ({used} / {quota}) — 새로 저장하지 못하거나 브라우저가 지울 수 있다",
            { used: formatBytes(out.usage), quota: formatBytes(out.quota) }) });
        } else if (ratio >= LIMITS.quotaWarn) {
          out.warnings.push({ level: "warn", text: T("이 브라우저의 저장소를 {pct}% 썼다 ({used} / {quota})",
            { pct: Math.round(ratio * 100), used: formatBytes(out.usage), quota: formatBytes(out.quota) }) });
        }
      }
      return out;
    });
  }

  /** 저장하기 전에 — 이 기록(들)이 얼마나 크고, 자리가 있는지. → { bytes, warnings, room: false 면 자리가 없다 } */
  function checkBeforeSave(newRecs) {
    var bytes = newRecs.reduce(function (n, r) { return n + sizeOf(r); }, 0);
    return estimate().then(function (e) {
      var out = { bytes: bytes, warnings: [], room: true };
      newRecs.forEach(function (r) {
        var b = sizeOf(r);
        if (b > LIMITS.layer) out.warnings.push({ level: "warn", text: T("'{name}' 이 {size} 다 — 지도가 느려질 수 있다", { name: r.name, size: formatBytes(b) }) });
      });
      if (e.quota) {
        var after = (e.usage || 0) + bytes;
        if (after > e.quota) {
          out.room = false;
          out.warnings.push({ level: "bad", text: T("자리가 모자라다 — {need} 가 더 들어야 하는데 남은 것은 {left} 다",
            { need: formatBytes(bytes), left: formatBytes(Math.max(0, e.quota - (e.usage || 0))) }) });
        } else if (after / e.quota >= LIMITS.quotaWarn) {
          out.warnings.push({ level: "warn", text: T("저장하면 이 브라우저의 저장소를 {pct}% 쓴다", { pct: Math.round(after / e.quota * 100) }) });
        }
      }
      return out;
    });
  }

  // ── 연결 레이어 (wetherilli P09·122) ─────────────────────────────
  //
  // 남의 사이트가 우리 양식으로 내주는 주소와 인증키를 기록(`rec.link`)에 둔다. 받을 때마다 **브라우저가 먼저
  // 곧장 부르고**, 막히면(상대가 CORS 를 열지 않으면) 우리 서버(`linked/fetch/`)를 거친다. 받지 못하면 마지막으로
  // 받은 것을 그대로 두고 까닭을 `rec.status` 에 적는다. 키는 이 브라우저에만 있다 — 내려받기(JSON·CSV)에도 안 실린다.

  var AUTH_MODES = ["none", "bearer", "header", "query"];
  var config = { proxy: "", csrf: function () { return ""; } };
  function configure(opts) { Object.keys(opts || {}).forEach(function (k) { config[k] = opts[k]; }); }

  function withQuery(url, name, key) {
    var u = new URL(url);
    u.searchParams.set(name, key);
    return u.toString();
  }

  function checkLink(link) {
    var url;
    try { url = new URL(String(link && link.url || "").trim()); } catch (e) { throw new ParseError(T("주소를 읽지 못했다")); }
    if (!/^https?:$/.test(url.protocol)) throw new ParseError(T("http·https 주소만 부른다"));
    var auth = link.auth || { mode: "none" };
    if (AUTH_MODES.indexOf(auth.mode) < 0) throw new ParseError(T("인증 방식을 모른다"));
    if ((auth.mode === "header" || auth.mode === "query") && !String(auth.name || "").trim()) {
      throw new ParseError(T("인증키를 싣는 이름이 없다"));
    }
    if (auth.mode !== "none" && !auth.key) throw new ParseError(T("인증키가 비었다"));
    return { url: url.toString(), auth: { mode: auth.mode, name: String(auth.name || "").trim(), key: auth.key || "" } };
  }

  /** 곧장 받는다. CORS·망으로 막히면 TypeError 가 난다 — 그것만 서버로 돌린다. */
  function fetchDirect(link) {
    var headers = { Accept: "application/geo+json, application/json, text/csv;q=0.9, */*;q=0.5" };
    var url = link.url;
    if (link.auth.mode === "bearer") headers.Authorization = "Bearer " + link.auth.key;
    else if (link.auth.mode === "header") headers[link.auth.name] = link.auth.key;
    else if (link.auth.mode === "query") url = withQuery(url, link.auth.name, link.auth.key);
    return fetch(url, { headers: headers, credentials: "omit", cache: "no-store", redirect: "follow" }).then(function (r) {
      if (r.status === 401 || r.status === 403) throw new ParseError(T("상대 서버가 거절했다 ({status}) — 인증키를 본다", { status: r.status }));
      if (!r.ok) throw new ParseError(T("상대 서버가 주지 않았다 ({status})", { status: r.status }));
      return r.arrayBuffer();
    });
  }

  function fetchViaServer(link) {
    if (!config.proxy) throw new ParseError(T("곧장 받지 못했다 — 상대 서버가 CORS 를 열어야 한다"));
    return fetch(config.proxy, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": config.csrf() },
      body: JSON.stringify({ url: link.url, auth: link.auth }),
      credentials: "same-origin",
      cache: "no-store",
    }).then(function (r) {
      if (r.ok) return r.arrayBuffer();
      return r.json().catch(function () { return {}; }).then(function (d) {
        throw new ParseError(d.error || T("우리 서버가 받지 못했다 ({status})", { status: r.status }));
      });
    });
  }

  /** 받기만 한다 — 곧장, 막히면 서버. → { buf, via } */
  function fetchBytes(checked) {
    return fetchDirect(checked).then(function (buf) { return { buf: buf, via: "direct" }; }, function (e) {
      if (e instanceof ParseError) throw e;                  // 상대가 답은 했다 — 서버로 가도 같다
      return Promise.resolve().then(function () { return fetchViaServer(checked); })
        .then(function (buf) { return { buf: buf, via: "server" }; });
    });
  }

  /** API 의 목차(`{"endpoints": {"sites": {"url": …}}}` 따위)에서 자료 주소를 고른다 (wetherilli 129).
   *  같은 호스트의, 자리표(`{id}`)가 없는 `url` 만 — 키를 다른 호스트로 싣지 않는다. */
  function endpointsOf(text, base) {
    var doc;
    try { doc = JSON.parse(String(text).replace(/^\uFEFF/, "")); } catch (e) { return []; }
    var out = [];
    (function walk(node, depth) {
      if (!node || typeof node !== "object" || depth > 3) return;
      Object.keys(node).forEach(function (k) {
        var v = node[k];
        if (k === "url" && typeof v === "string" && v.indexOf("{") < 0) {
          try {
            var u = new URL(v, base);
            if (u.host === new URL(base).host && u.href !== base && out.indexOf(u.href) < 0) out.push(u.href);
          } catch (e) { /* 주소가 아니다 */ }
        } else if (typeof v === "object") walk(v, depth + 1);
      });
    })(doc && (doc.endpoints || doc.links || doc), 0);
    return out;
  }

  /** 연결을 따라 받아 읽는다 → { parsed, via: "direct"|"server", url }. 받은 것이 자료가 아니라 API 의 목차면
   *  거기 적힌 자료 주소를 차례로 받아 본다(셋까지). 찾으면 `url` 이 그 주소다 — 부르는 쪽이 연결에 적어 다음부터 곧장 간다. */
  function fetchLinked(link) {
    var checked = checkLink(link);
    function read(got, url) {
      var d = decode(got.buf);
      var name = url.split("?")[0];
      var parsed = parse(d.text, /\.csv$/i.test(name) ? name : "");
      parsed.encoding = d.encoding;
      return { parsed: parsed, via: got.via, url: url };
    }
    return fetchBytes(checked).then(function (got) {
      try { return read(got, checked.url); } catch (e) {
        if (!(e instanceof ParseError)) throw e;
        var tries = endpointsOf(decode(got.buf).text, checked.url).slice(0, 3);
        if (!tries.length) throw e;
        return tries.reduce(function (chain, url) {
          return chain.catch(function () {
            var next = { url: url, auth: checked.auth };
            return fetchBytes(next).then(function (g) { return read(g, url); });
          });
        }, Promise.reject(e)).catch(function () {
          throw new ParseError(T("API 의 목차다 — 자료 주소를 찾지 못했다 ({urls})", { urls: tries.join(", ") }));
        });
      }
    });
  }

  /** 받은 것을 기록에 덮는다. 사람이 고친 이름·색·이름표는 둔다. */
  function applyFetched(rec, got) {
    var parts = split(got.parsed);
    // 섞인 연결이면 이 기록이 맡은 모양(`linkPart`)의 갈래만. 그 모양이 사라졌으면 빈 레이어로 남긴다
    var p = parts.filter(function (x) { return !rec.linkPart || x.kind === rec.linkPart; })[0] ||
      { kind: rec.linkPart, meta: got.parsed.meta, columns: got.parsed.columns, features: [], count: 0, drawn: 0, problems: [] };
    rec.kind = p.kind;
    rec.meta = p.meta;
    rec.columns = p.columns;
    rec.features = p.features;
    rec.count = p.count;
    rec.drawn = p.drawn;
    rec.fetched = new Date().toISOString();
    rec.status = { ok: true, via: got.via, at: rec.fetched, problems: p.problems.length };
    return rec;
  }

  /** 한 연결에서 나온 기록들(같은 `linkGroup`)을 한 번 받아 함께 덮는다. 실패해도 저장한다 — 옛것은
   *  그대로, 까닭만 적는다. 기록 하나를 넘기면 그 하나만. */
  function refresh(recs) {
    recs = (Array.isArray(recs) ? recs : [recs]).filter(function (r) { return r && r.link; });
    if (!recs.length) return Promise.resolve([]);
    return fetchLinked(recs[0].link).then(function (got) {
      return Promise.all(recs.map(function (rec) {
        if (got.url) rec.link.url = got.url;                 // 목차에서 찾은 자료 주소로 바로잡는다
        return put(applyFetched(rec, got));
      }));
    }, function (e) {
      var status = { ok: false, error: (e && e.message) || String(e), at: new Date().toISOString() };
      return Promise.all(recs.map(function (rec) { rec.status = status; return put(rec); }));
    });
  }

  /** 기록들을 연결마다 묶는다 → [[기록…]…]. 연결이 아닌 것은 뺀다. */
  function linkGroups(recs) {
    var groups = {}, order = [];
    recs.forEach(function (rec) {
      if (!rec.link) return;
      var key = rec.linkGroup || rec.id;
      if (!groups[key]) { groups[key] = []; order.push(key); }
      groups[key].push(rec);
    });
    return order.map(function (k) { return groups[k]; });
  }

  // 다른 창(지도·관리 화면)에 바뀐 것을 알린다
  var channel = root.BroadcastChannel ? new root.BroadcastChannel(CHANNEL) : null;
  function announce() { if (channel) channel.postMessage({ changed: Date.now() }); }
  function onChange(fn) { if (channel) channel.addEventListener("message", fn); }

  var api = {
    FORMAT: FORMAT,
    VERSION: VERSION,
    DEFAULT_COLOR: DEFAULT_COLOR,
    PALETTE: PALETTE,
    SHAPES: SHAPES,
    RESERVED: RESERVED,
    ParseError: ParseError,
    setTranslator: setTranslator,
    decode: decode,
    parse: parse,
    parseCSV: parseCSV,
    parseJSON: parseJSON,
    parseWKT: parseWKT,
    wkt: wkt,
    toGeoJSON: toGeoJSON,
    toCSV: toCSV,
    record: record,
    sizeOf: sizeOf,
    LIMITS: LIMITS,
    formatBytes: formatBytes,
    measure: measure,
    checkBeforeSave: checkBeforeSave,
    list: list,
    get: get,
    put: put,
    remove: remove,
    clear: clear,
    onChange: onChange,
    AUTH_MODES: AUTH_MODES,
    configure: configure,
    checkLink: checkLink,
    fetchLinked: fetchLinked,
    applyFetched: applyFetched,
    refresh: refresh,
    linkGroups: linkGroups,
    split: split,
    endpointsOf: endpointsOf,
    kindOf: kindOf,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.GSMPersonal = api;
})(typeof self !== "undefined" ? self : this);
