/* 정적 판(GitHub Pages)의 극지 상류 — 서버 없이 브라우저가 곧장 부른다 (wetherilli 161).
 *
 * 서버 판에서는 타일·속성·범례가 다 `/GSM/wms/`·`/GSM/featureinfo/`·`/GSM/legend/` 를 거치고, 서버의 문(npolar.py·geus.py …)이
 * 상류의 꼴로 옮겨 부른다. 정적 판에는 서버가 없으므로 그 옮기는 일을 여기서 한다. 표(주소·레이어 번호·팝업 이름·지질시대
 * 낱말)는 이 파일에 적지 않는다 — 빌드가 서버의 문에서 떠 싣는 `window.GSM_STATIC_TABLES`(`viewer/static_tables.py`)를 읽는다.
 *
 * 꼴 — map.js 의 `LAYER_KINDS` 와 같은 자리에 선다(고리는 map.js 정적 모드가 둔다):
 *   window.GSM_STATIC_KINDS = {
 *     <upstream>: {
 *       source(name, row)                 → ol 소스(타일). 레이어 이름을 `gsmName` 으로 붙여 둔다
 *       info(source, coordinate, view)    → Promise<{features: [{id, props}]}> — 서버의 /featureinfo/ 와 같은 꼴. 없으면 null
 *       legend(name, row)                 → Promise<{img: 주소} | {rows: [{label, src}]} | {link: 주소}>
 *       points(name, row)                 → Promise<FeatureCollection> — 서버의 /points/ 와 같은 꼴(labels·links·style·legend)
 *     }
 *   }
 *
 * 실측과 까닭은 docs/정적_밖_경로.md §2·§4·§5.
 *   - GEUS — 정사각 그림을 403 으로 돌려보낸다("this is not a WMTS … singleTile=true"). 512×511 타일로 받는다.
 *     부르는 이를 밝히는 `whoami` 는 각자의 이메일을 그 브라우저에만(`gsm.key.geus`). 속성은 text/plain 을 풀고, 범례는 HTML 쪽이라 링크로
 *   - NPI·PGC — WMS 가 아니라 ArcGIS `export`·`exportImage`·`identify`. 서버의 `npolar.export_params`·`identify_params`·
 *     `elevation.get_map` 을 TileArcGISRest 와 손으로 지은 identify 로 옮긴다
 *   - EMODnet·KPDC — 여느 WMS(3413·3031). CORS 가 열려 있다. KPDC 는 이 서버에서 이름이 안 풀리지만(사내 DNS) 밖에서는 풀린다
 *   - 그린란드 포털·NPI 점 — ArcGIS 의 GeoJSON 을 장을 넘겨 받고, 서버의 `arcpoints.compact`·`grportal.class_of` 를 따라 줄인다
 */
(function () {
  "use strict";
  // 표는 지도 화면이 `<script id="static-tables">` 로 싣는다(`views.map_view`). 시험은 `window.GSM_STATIC_TABLES` 로 넣는다
  var T = window.GSM_STATIC_TABLES || (function () {
    try { return JSON.parse((document.getElementById("static-tables") || {}).textContent || "{}"); } catch (e) { return {}; }
  })();

  // ── 거들개 ──────────────────────────────────────────────────────────

  function lang() { return (document.documentElement.lang || "ko").slice(0, 2) === "en" ? "en" : "ko"; }

  /** 사람이 그 브라우저에 넣은 값(GEUS 이메일 따위). 저장이 막힌 브라우저면 빈칸 — 늘 try 로 */
  function stored(key) {
    try { return localStorage.getItem(key) || sessionStorage.getItem(key) || ""; } catch (e) { return ""; }
  }

  function query(url, params) {
    var parts = [];
    Object.keys(params).forEach(function (k) {
      if (params[k] != null) parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(params[k]));
    });
    return url + (url.indexOf("?") >= 0 ? "&" : "?") + parts.join("&");
  }

  function getJson(url) {
    return fetch(url, { credentials: "omit" }).then(function (r) {
      if (!r.ok) throw new Error("status " + r.status);
      return r.json();
    }).then(function (data) {
      if (data && data.error) throw new Error(data.error.message || "error");   // ArcGIS 는 200 에 {error} 를 싣는다
      return data;
    });
  }

  function empty(value) {
    return value == null || (typeof value === "string" && ["", " ", "Null", "null", "<Null>"].indexOf(value.trim()) >= 0);
  }

  /** 영어판이면 팝업 이름을 `PROP_EN` 으로 — 서버의 `i18n.props_en` 가운데 극지가 쓰는 몫(값은 상류가 준 영어 그대로) */
  function forLang(props) {
    if (lang() !== "en") return props;
    var out = {}, names = T.propEn || {}, links = T.linkEn || {};
    Object.keys(props).forEach(function (k) {
      var v = props[k];
      if (v && typeof v === "object" && v.links) {
        v = { text: v.text, links: v.links.map(function (l) { return { url: l.url, label: links[l.label] || l.label }; }) };
      }
      out[names[k] || k] = v;
    });
    return out;
  }

  /** 서버의 `feature_info` 가 모든 상류에 하는 거름 — 빈 덩이는 빼고, 속성이 같은 것은 하나로(겹친 면을 몇 픽셀 둘레로 물으면
   *  같은 것이 여러 번 온다), `maxFeatures` 개까지 */
  function tidy(features) {
    var seen = {}, out = [];
    features.forEach(function (f) {
      var keys = Object.keys(f.props);
      if (!keys.length || out.length >= (T.maxFeatures || 3)) return;
      var mark = JSON.stringify(keys.sort().map(function (k) { return [k, f.props[k]]; }));
      if (seen[mark]) return;
      seen[mark] = true;
      out.push(f);
    });
    return { features: out };
  }

  // ── 지질시대 — `i18n.age_ko` 를 그대로 옮긴 것 ─────────────────────────
  //
  // 영문 ICS 값 하나를 한국어로. 모르는 낱말이 하나라도 있으면 원문 그대로 — 반만 옮긴 것은 틀린 것보다 나쁘다.
  //   late Paleocene → 팔레오세 후기, Early - Middle Triassic → 트라이아스기 전기~중기, Neoproterozoic (?) → 신원생대(?)
  var AGE_TOKEN = /and\/or|[A-Za-z]+|\?|[-–,;]/g;

  function ageKo(value) {
    var age = T.age || {}, words = age.words || {}, mods = age.modifiers || {}, joins = age.joiners || {};
    var text = String(value == null ? "" : value).trim();
    if (!text) return value;
    var flat = text.replace(/\(\?\)/g, "?");
    if (flat.replace(AGE_TOKEN, "").replace(/[()]/g, "").trim()) return value;
    var tokens = flat.match(AGE_TOKEN) || [];
    var segments = [], joiners = [], cur = { mods: [], noun: null, doubt: false };
    for (var i = 0; i < tokens.length; i++) {
      var token = tokens[i], low = token.toLowerCase();
      if (Object.prototype.hasOwnProperty.call(joins, low)) {
        if (!(cur.mods.length || cur.noun)) return value;
        segments.push(cur);
        joiners.push(joins[low]);
        cur = { mods: [], noun: null, doubt: false };
      } else if (token === "?") {
        cur.doubt = true;
      } else if (Object.prototype.hasOwnProperty.call(mods, low) && !cur.noun) {
        cur.mods.push(mods[low]);
      } else if (Object.prototype.hasOwnProperty.call(words, low) && !cur.noun) {
        cur.noun = words[low];
      } else {
        return value;
      }
    }
    if (!(cur.mods.length || cur.noun)) return value;
    segments.push(cur);
    var out = [], shown = null;
    for (var s = 0; s < segments.length; s++) {
      var seg = segments[s], noun = seg.noun;
      if (noun == null) {
        for (var k = s + 1; k < segments.length && noun == null; k++) noun = segments[k].noun;
        if (noun == null || !seg.mods.length) return value;
      }
      var m = seg.mods.join(" ");
      var piece = noun === shown && m ? m : (noun + " " + m).trim();
      shown = noun;
      out.push(piece + (seg.doubt ? "(?)" : ""));
    }
    return out.map(function (p, n) { return p + (n < joiners.length ? joiners[n] : ""); }).join("");
  }

  /** `i18n.age_local` 을 옮긴 것 — 독일어·네덜란드어·폴란드어·프랑스어 시대(`Perm - frühe Kreide`·`jura górna`) → ICS 영어.
   *  낱말 하나라도 모르면 빈 글 — 부르는 쪽이 원문을 보인다 (wetherilli 257) */
  function ageLocal(value) {
    var t = T.ageLocal || {}, words = t.words || {}, mods = t.modifiers || {}, glued = t.glued || [];
    var has = function (o, k) { return Object.prototype.hasOwnProperty.call(o, k); };
    var text = String(value == null ? "" : value).trim();
    if (!text || text.toLowerCase() === "null") return "";
    var parts = [], pieces = text.split(/\s+(?:-|–|bis|tot|do|à)\s+|\s*–\s*|\s*,\s*/);
    for (var i = 0; i < pieces.length; i++) {
      var ws = pieces[i].trim().toLowerCase().split(/[\s\-]+/).filter(Boolean);
      if (!ws.length) continue;
      var noun = "", mod = "";
      for (var j = 0; j < ws.length; j++) {
        var w = ws[j];
        if (has(words, w) && !noun) noun = words[w];
        else if (has(mods, w) && !mod) mod = mods[w];
        else {
          // 독일어는 꾸밈말을 붙여 쓴다 — `Obertrias`·`Unterkreide`
          var g = null;
          for (var k = 0; k < glued.length && !g; k++) {
            if (w.indexOf(glued[k]) === 0 && has(words, w.slice(glued[k].length))) g = [glued[k], w.slice(glued[k].length)];
          }
          if (!g || noun || mod) return "";
          mod = mods[g[0]]; noun = words[g[1]];
        }
      }
      if (!noun) return "";
      parts.push(mod ? mod + " " + noun : noun);
    }
    if (!parts.length) return "";
    return parts.every(function (p) { return p === parts[0]; }) ? parts[0] : parts[0] + " – " + parts[parts.length - 1];
  }

  /** 시대 원문 → 화면 말. 옮기면 한국어판은 한국어·영어판은 ICS 영어, 못 옮기면 원문 (서버 문들의 같은 세 줄) */
  function localAge(raw) {
    var ics = ageLocal(raw);
    return ics ? (lang() === "ko" ? ageKo(ics) : ics) : String(raw == null ? "" : raw).trim();
  }

  /** 누른 자리 둘레 — 지금 화면의 해상도로. identify 의 mapExtent·imageDisplay 로 쓴다(101 칸, 가운데가 누른 자리) */
  function around(coordinate, view, code) {
    var viewCode = view.getProjection().getCode();
    var xy = viewCode === code ? coordinate : ol.proj.transform(coordinate, viewCode, code);
    var res = view.getResolution();
    if (viewCode !== code) {
      var other = ol.proj.transform([coordinate[0] + res, coordinate[1]], viewCode, code);
      res = Math.sqrt(Math.pow(other[0] - xy[0], 2) + Math.pow(other[1] - xy[1], 2));
    }
    var half = 50.5 * res;
    return { x: xy[0], y: xy[1], extent: [xy[0] - half, xy[1] - half, xy[0] + half, xy[1] + half] };
  }

  function srid(code) { return Number(String(code).split(":")[1]); }

  function tileGrid(code) {
    return ol.tilegrid.createXYZ({ extent: ol.proj.get(code).getExtent(), tileSize: 512 });
  }

  // ── GEUS (그린란드 지질도) ─────────────────────────────────────────

  var geus = T.geus || {};

  /** MapServer 의 text/plain → feature 목록 (`geus.parse_plain`) */
  function parsePlain(text) {
    var features = [], layer = "", current = null;
    String(text || "").split(/\r?\n/).forEach(function (line) {
      var m = /^Layer '([^']+)'/.exec(line);
      if (m) { layer = m[1]; return; }
      m = /^\s*Feature\s+(\S+):\s*$/.exec(line);
      if (m) { current = { id: layer + "." + m[1], properties: {} }; features.push(current); return; }
      m = /^\s{2,}(\w+)\s*=\s*'(.*)'\s*$/.exec(line);
      if (m && current) current.properties[m[1]] = m[2];
    });
    return features;
  }

  /** GEUS 는 **정사각 그림을 막는다** — 403 "this is not a WMTS"(2026-10-02, `whoami` 와 상관없다: 600×600·512×512 는 403,
   *  601×600 은 200). 그래서 타일을 512×511 로 받는다 — 해상도는 여느 3857 격자와 같고 세로만 한 줄 짧다. 화면 한 장(ImageWMS)으로
   *  받는 길도 있지만, 타일이면 브라우저 캐시가 맞고 map.js 의 타일 레이어에 그대로 얹힌다 */
  var geusGridMemo = null;
  function geusGrid() {       // 처음 쓸 때 짓는다 — 이 파일은 ol 보다 먼저 읽혀도 돌아야 한다
    if (!geusGridMemo) {
      var half = 20037508.342789244, resolutions = [];
      for (var z = 0; z <= 19; z++) resolutions.push(2 * half / 512 / Math.pow(2, z));
      geusGridMemo = new ol.tilegrid.TileGrid({ extent: [-half, -half, half, half], origin: [-half, half],
                                                resolutions: resolutions, tileSize: [512, 511] });
    }
    return geusGridMemo;
  }

  function geusFriendly(props) {
    var out = {}, names = geus.friendly || {}, hidden = geus.hidden || [];
    Object.keys(props).forEach(function (key) {
      if (hidden.indexOf(key.toLowerCase()) >= 0) return;
      var value = props[key];
      if (typeof value === "string" && /^-?\d+\.0+$/.test(value)) value = value.split(".")[0];   // 1600.000000 → 1600
      out[names[key] || key] = value;
    });
    return out;
  }

  // ── NPI (스발바르·드로닝모드랜드 지도 서버) ──────────────────────────

  var npi = T.npolar || {};

  function npiFriendly(props) {
    var out = {}, links = npi.linkProps || [], ages = npi.ageProps || [];
    (npi.friendly || []).forEach(function (pair) {
      var key = pair[0], label = pair[1], value = props[key];
      if (typeof value === "string") value = value.trim();
      if (empty(value) || Object.prototype.hasOwnProperty.call(out, label)) return;
      if (links.indexOf(key) >= 0) {
        if (!/^https?:\/\//i.test(String(value))) return;
        value = { text: "", links: [{ url: String(value), label: "열기" }] };
      } else if (ages.indexOf(label) >= 0 && lang() === "ko") {
        value = ageKo(value);
      } else if (key === "Date" && /^\d{8}$/.test(String(value))) {
        var d = String(value);
        value = d.slice(0, 4) + "-" + d.slice(4, 6) + "-" + d.slice(6);   // 빙하 전면의 20230910
      } else if (key === "Length_km") {
        var n = parseFloat(String(value).replace(",", "."));             // 노르웨이 꼴의 소수 쉼표("3,595676")
        if (!isNaN(n)) value = n.toFixed(2);
      }
      out[label] = value;
    });
    return out;
  }

  function npiSpec(name) { return (npi.tiles || {})[String(name).split("@")[0]]; }

  // ── EMODnet (해저 지질) ────────────────────────────────────────────

  var emod = T.emodnet || {};

  function emodName(name) {
    var p = emod.prefix || "emodnet:";
    return String(name).indexOf(p) === 0 ? String(name).slice(p.length) : String(name);
  }

  function emodFriendly(props) {
    var out = {};
    (emod.friendly || []).forEach(function (pair) {
      var key = pair[0], label = pair[1], value = props[key];
      if (value == null || value === "" || ["n/a", "-", "none"].indexOf(String(value).trim().toLowerCase()) >= 0) return;
      if (key === "label_age" && lang() === "ko") value = ageKo(value);
      else if (key === "reference") value = String(value).replace(/^Reference: /, "");
      else if (key === "scale" && /^\d+(\.\d+)?$/.test(String(value))) {
        value = "1:" + Math.round(Number(value)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
      }
      out[label] = value;
    });
    return out;
  }

  // ── 점 — 그린란드 포털·NPI 의 ArcGIS (arcpoints) ─────────────────────

  function round5(v) { return Math.round(Number(v) * 1e5) / 1e5; }

  function roundCoords(c) {
    return typeof c[0] === "number" ? [round5(c[0]), round5(c[1])] : c.map(roundCoords);
  }

  /** 값 하나 (`arcpoints.clean`) — 고치지 않는다. 빈 값은 뺀다 */
  function clean(value, kind) {
    if (value == null) return null;
    if (kind === "number" || kind === "measure") {
      var n = Math.round(Number(value) * 1000) / 1000;
      if (isNaN(n)) return null;
      return kind === "measure" && n <= -999 ? null : n;
    }
    var text = String(value).split(/\s+/).join(" ").trim();
    if (!text) return null;
    if (kind === "link") return /^https?:\/\//i.test(text) ? text : null;
    if (kind === "rgb") {
      var p = text.split(" ").slice(0, 3).map(Number);
      if (p.length < 3 || p.some(isNaN)) return null;
      return "#" + p.map(function (x) { return ("0" + x.toString(16)).slice(-2); }).join("");
    }
    return text;
  }

  /** 상류 feature 하나 → 우리 것 (`arcpoints.compact`). 점이 아니면 null — `areal` 이면 면도 */
  function compact(feature, spec) {
    var geom = feature.geometry || {}, coords = geom.coordinates, geometry;
    if (spec.areal && ["Polygon", "MultiPolygon", "LineString", "MultiLineString"].indexOf(geom.type) >= 0 && coords) {
      geometry = { type: geom.type, coordinates: roundCoords(coords) };
    } else if (geom.type !== "Point" || !coords || coords.length < 2) {
      return null;
    } else {
      geometry = { type: "Point", coordinates: [round5(coords[0]), round5(coords[1])] };
    }
    var src = feature.properties || {}, props = {};
    Object.keys(spec.fields).forEach(function (key) {
      var f = spec.fields[key], v = clean(src[f.from], f.kind);
      if (v != null) props[key] = v;
    });
    var fid = feature.id != null ? feature.id : (src[spec.oid] != null ? src[spec.oid] : (src.FID != null ? src.FID : src.OBJECTID));
    return { type: "Feature", id: fid, geometry: geometry, properties: props };
  }

  /** 갈래 (`grportal.class_of`) — 위에서부터 먼저 맞는 것. 머리는 셋 가운데 하나다:
   *  `{gt0: 열}`(그 열의 값이 0 보다 크다, 석류석)·`{top: 열, of: [열…]}`(그 열이 가장 크다), 구간 `[이상, 미만]`(`numeric`, 미만이 null 이면 끝이 없다), 머리말 묶음 */
  function classOf(classes, props) {
    var raw = classes.by ? props[classes.by] : null;
    var value = String(raw == null ? "" : raw);
    for (var i = 0; i < classes.table.length; i++) {
      var row = classes.table[i], heads = row[4], hit;
      if (heads && !Array.isArray(heads) && heads.top) {
        // 그 열이 `of` 가운데 가장 크고 0 보다 크다 — 지시광물 화학 갈래 (wetherilli 178)
        var top = Number(props[heads.top]) || 0;
        hit = top > 0 && heads.of.every(function (k) { return top >= (Number(props[k]) || 0); });
      } else if (heads && !Array.isArray(heads)) hit = (Number(props[heads.gt0]) || 0) > 0;
      else if (classes.numeric) hit = typeof raw === "number" && raw >= heads[0] && (heads[1] == null || raw < heads[1]);
      else hit = heads.some(function (head) { return value.indexOf(head) === 0; });
      if (hit) return row.slice(0, 4);
    }
    return classes["else"];
  }

  /** 레이어 하나를 장을 넘겨 다 받는다 (`arcpoints.collect`). 장 사이에 0.5 초 쉰다 — 서버 판과 같은 빠르기 */
  function collect(spec) {
    var wanted = {};
    Object.keys(spec.fields).forEach(function (k) { wanted[spec.fields[k].from] = true; });
    wanted[spec.oid] = true;
    var out = [];
    function page(offset, index) {
      var params = { where: "1=1", outFields: Object.keys(wanted).sort().join(","), returnGeometry: "true",
                     outSR: "4326", f: "geojson" };
      if (spec.generalize) params.maxAllowableOffset = spec.generalize;
      if (spec.paged) {
        params.orderByFields = spec.oid + " ASC";
        params.resultOffset = offset;
        params.resultRecordCount = spec.page;
      }
      return getJson(query(spec.url, params)).then(function (data) {
        var got = data.features || [];
        got.forEach(function (f) { var row = compact(f, spec); if (row) out.push(row); });
        var more = data.exceededTransferLimit || (data.properties || {}).exceededTransferLimit;
        if (!spec.paged || !got.length || (got.length < spec.page && !more) || index + 1 >= spec.maxPages) return out;
        return new Promise(function (ok) { setTimeout(ok, 500); }).then(function () {
          return page(offset + got.length, index + 1);
        });
      });
    }
    return page(0, 0);
  }

  /** 서버의 `/points/` 와 같은 덩이 (`arcpoints.body`·`grportal.body`·`grportal._value_body`) */
  function pointBody(spec) {
    // 원소마다 잘라 받는 연속값(전암 화학 3 만 점)은 통째로 받기에 무겁다 — 굽는 쪽이 싣는다
    if (spec.slice) return Promise.reject(new Error("sliced value layer — baked only"));
    return collect(spec).then(function (features) {
      var body = { type: "FeatureCollection", labels: spec.labels, links: spec.links, style: spec.style };
      if (spec.style === "value") {
        // 연속값(지화학) — 이 레이어에서 값이 하나라도 있는 원소만, 측정값 수(`n`)와 검출 한계 밑의 수(`below`)를 센다
        var counts = {};
        features.forEach(function (f) {
          spec.values.forEach(function (v) {
            var x = f.properties[v[0]];
            if (typeof x !== "number") return;
            var c = counts[v[0]] || (counts[v[0]] = [0, 0]);
            if (x > 0) c[0] += 1;
            if (x < 0) c[1] += 1;
          });
        });
        body.values = spec.values.filter(function (v) { return counts[v[0]] && counts[v[0]][0]; }).map(function (v) {
          return { key: v[0], label: v[1], unit: v[2], n: counts[v[0]][0], below: counts[v[0]][1] };
        });
        body["default"] = spec["default"];
        body.features = features;
        return body;
      }
      if (spec.classes) {
        var counts = {}, table = {};
        features.forEach(function (f) {
          var c = classOf(spec.classes, f.properties);
          f.properties.code = c[0];
          counts[c[0]] = (counts[c[0]] || 0) + 1;
          table[c[0]] = c;
        });
        var order = spec.classes.table.map(function (r) { return r[0]; }).concat([spec.classes["else"][0]]);
        body.style = "class";
        body.legend = order.filter(function (c) { return counts[c]; }).map(function (c) {
          return { code: c, label: table[c][1], color: table[c][2], shape: table[c][3], count: counts[c] };
        });
      }
      body.features = features;
      return body;
    });
  }

  // ── 상류마다 ──────────────────────────────────────────────────────

  var KINDS = {};

  /** 소스에 레이어 이름을 붙여 둔다 — 속성을 물을 때(`info`) 소스만 받으므로. map.js 의 `layerSource` 와 같은 표식이다 */
  function named(name, source) { source.set("gsmName", name); return source; }

  KINDS.geus = {
    source: function (name) {
      return named(name, new ol.source.TileWMS({
        url: geus.url,
        // 서버 판(`geus._get`)과 같은 변수 — 1.1.1·SRS. `whoami` 는 그 사람이 넣은 이메일(없으면 비운다)
        params: { LAYERS: name, FORMAT: "image/png", TRANSPARENT: true, VERSION: "1.1.1", TILED: true,
                  mapname: geus.mapname, whoami: stored("gsm.key.geus"), nocache: "nocache" },
        projection: "EPSG:3857", tileGrid: geusGrid(), crossOrigin: "anonymous", transition: 0,
        attributions: "© GEUS",
      }));
    },
    info: function (source, coordinate, view) {
      var url = source.getFeatureInfoUrl(coordinate, view.getResolution(), view.getProjection(),
                                         { INFO_FORMAT: "text/plain" });
      if (!url) return null;
      return fetch(url, { credentials: "omit" }).then(function (r) { return r.ok ? r.text() : ""; })
        .then(function (text) {
          return tidy(parsePlain(text).map(function (f) { return { id: f.id, props: forLang(geusFriendly(f.properties)) }; }));
        });
    },
    // GEUS 의 GetLegendGraphic 은 HTML 범례 쪽으로 넘긴다 — 그림이 아니라 링크로 연다
    legend: function (name) {
      return Promise.resolve({ link: query(geus.url, { service: "WMS", version: "1.1.1", request: "GetLegendGraphic",
                                                         format: "image/png", layer: name, mapname: geus.mapname }) });
    },
  };

  KINDS.npolar = {
    source: function (name) {
      var spec = npiSpec(name);
      return named(name, new ol.source.TileArcGISRest({
        url: npi.url + "/" + spec.service + "/MapServer",
        params: { LAYERS: "show:" + spec.show.join(","), FORMAT: spec.format, TRANSPARENT: true, DPI: 96 },
        projection: spec.projection, tileGrid: tileGrid(spec.projection), crossOrigin: "anonymous",
        transition: 0, attributions: npi.attribution,
      }));
    },
    info: function (source, coordinate, view) {
      var name = source.get("gsmName"), spec = npiSpec(name);
      if (!spec || !spec.info) return null;
      var at = around(coordinate, view, spec.projection), sr = srid(spec.projection);
      // 서버의 `npolar.identify_params` — 둘레 3 픽셀, 그 축척에서 보이는 것(`visible:`)
      var url = query(npi.url + "/" + spec.service + "/MapServer/identify", {
        geometry: at.x + "," + at.y, geometryType: "esriGeometryPoint", sr: sr,
        layers: "visible:" + spec.info.join(","), tolerance: 3, mapExtent: at.extent.join(","),
        imageDisplay: "101,101,96", returnGeometry: "false", f: "json",
      });
      return getJson(url).then(function (data) {
        return tidy((data.results || []).map(function (res) {
          var a = res.attributes || {};
          return { id: res.layerId + "." + (a.OBJECTID != null ? a.OBJECTID : a.FID), props: forLang(npiFriendly(a)) };
        }));
      });
    },
    // `legend?f=json` 은 칸마다 작은 그림(base64)과 이름을 준다 — 서버는 이어 붙여 한 장으로 줬고, 여기서는 줄로 준다
    legend: function (name) {
      var spec = npiSpec(name);
      if (!spec || !spec.legend) return Promise.resolve(null);
      return getJson(npi.url + "/" + spec.service + "/MapServer/legend?f=json").then(function (data) {
        var rows = [];
        (data.layers || []).forEach(function (layer) {
          if (spec.legend.indexOf(layer.layerId) < 0) return;
          (layer.legend || []).forEach(function (item) {
            rows.push({ label: item.label || layer.layerName, src: "data:" + item.contentType + ";base64," + item.imageData });
          });
        });
        return { rows: rows };
      });
    },
    points: function (name) {
      var spec = (npi.points || {})[name];
      return spec ? pointBody(spec) : Promise.reject(new Error("no such point layer"));
    },
  };

  KINDS.grportal = {
    source: null, info: null,
    points: function (name) {
      var spec = ((T.grportal || {}).points || {})[name];
      return spec ? pointBody(spec) : Promise.reject(new Error("no such point layer"));
    },
  };

  var pgc = T.pgc || {};
  KINDS.pgc = {
    source: function (name) {
      var spec = pgc.layers[name];
      return named(name, new ol.source.TileArcGISRest({
        url: pgc["export"].replace("{service}", spec.service).replace(/\/exportImage$/, ""),
        params: { FORMAT: spec.format, TRANSPARENT: true, renderingRule: JSON.stringify({ rasterFunction: spec.draw }) },
        projection: spec.srs, tileGrid: tileGrid(spec.srs), crossOrigin: "anonymous", transition: 0,
        attributions: pgc.attribution,
      }));
    },
    // 누른 픽셀 한 점의 값 — 경사 몇 도·해발 몇 m (`elevation.get_feature_info`)
    info: function (source, coordinate, view) {
      var name = source.get("gsmName"), spec = pgc.layers[name];
      var at = around(coordinate, view, spec.srs);
      var url = query(pgc.identify.replace("{service}", spec.service), {
        geometry: JSON.stringify({ x: at.x, y: at.y, spatialReference: { wkid: srid(spec.srs) } }),
        geometryType: "esriGeometryPoint", renderingRule: JSON.stringify({ rasterFunction: spec.read[0] }),
        returnGeometry: "false", returnCatalogItems: "false", f: "json",
      });
      return getJson(url).then(function (data) {
        var value = parseFloat(data.value);
        if (isNaN(value)) return { features: [] };                // "NoData" — 모자이크 밖
        var props = {};
        props[spec.read[1]] = value.toFixed(1);
        return { features: [{ id: "pgc", props: forLang(props) }] };
      });
    },
  };

  /** 여느 WMS(EMODnet 3413·KPDC 3031/3413) — 타일·속성(JSON)·범례(그림) */
  /** WMS 상류 하나. `url` 은 글자이거나 레이어 이름 → 주소의 함수다. `infoFormat` 은 속성의 꼴 — 기본 `application/json`,
   *  ArcGIS 는 `application/geo+json` 이다(콜롬비아 SGC, wetherilli 201) */
  function wmsKind(url, layerOf, projectionOf, friendly, attribution, infoFormat) {
    var urlOf = typeof url === "function" ? url : function () { return url; };
    return {
      source: function (name) {
        var code = projectionOf(name);
        return named(name, new ol.source.TileWMS({
          url: urlOf(name), params: { LAYERS: layerOf(name), TILED: true, FORMAT: "image/png", TRANSPARENT: true },
          projection: code, tileGrid: tileGrid(code), crossOrigin: "anonymous", transition: 0, attributions: attribution,
        }));
      },
      info: function (source, coordinate, view) {
        var u = source.getFeatureInfoUrl(coordinate, view.getResolution(), view.getProjection(),
                                         { INFO_FORMAT: infoFormat || "application/json", FEATURE_COUNT: 5 });
        if (!u) return null;
        return getJson(u).then(function (data) {
          return tidy((data.features || []).map(function (f) {
            return { id: f.id, props: forLang(friendly(f.properties || {})) };
          }));
        });
      },
      legend: function (name) {
        return Promise.resolve({ img: query(urlOf(name), { service: "WMS", version: "1.1.1", request: "GetLegendGraphic",
                                                   format: "image/png", layer: layerOf(name) }) });
      },
    };
  }

  KINDS.emodnet = wmsKind(emod.url, emodName, function () { return "EPSG:3413"; }, emodFriendly, emod.attribution);

  var kpdc = T.kopri || {};
  KINDS.kopri = wmsKind(kpdc.url, function (name) { return "kpdc:" + (kpdc.wms || {})[name]; },
                        function (name) { return (kpdc.projection || {})[name] || "EPSG:3031"; },
                        // KPDC 속성은 서버도 손질하지 않고 넘긴다 — 빈 값만 뺀다
                        function (props) {
                          var out = {};
                          Object.keys(props).forEach(function (k) { if (!empty(props[k])) out[k] = props[k]; });
                          return out;
                        }, kpdc.attribution);
  // 모아 둔 파일에서 그리는 KOPRI 점(시료·운석·KPDC 목록)은 여기 없다 — 굽는 쪽(bake_static)이 싣는다
  KINDS.kopri.points = null;

  // ── 콜롬비아 1:50만 — SGC ArcGIS WMS (wetherilli 201) ──
  // 조건이 열린 판(CC BY 4.0)만 표(`T.sgc.sheets`)에 실려 온다. SGC 는 Origin 을 되돌려 주어 곧장 부른다. 이름은 `sgc:<판>:<번호>`
  var sgcT = T.sgc || {};
  function sgcSheet(name) { return String(name).split(":")[1]; }
  function sgcUrl(name) { return sgcT.url + "/" + (sgcT.sheets || {})[sgcSheet(name)] + "/MapServer/WMSServer"; }
  /** `sgc.friendly` 의 콜롬비아 판 갈래 — 값은 에스파냐어 그대로다. 남미 판(영문 시대를 옮기는 것)은 정적 판에 없다 */
  function sgcFriendly(props) {
    var out = {};
    (sgcT.friendly || []).forEach(function (pair) {
      var value = props[pair[0]];
      if (value == null) return;
      value = String(value).trim();
      if (!value || value.toLowerCase() === "null" || out[pair[1]] != null) return;
      out[pair[1]] = value;
    });
    return out;
  }
  KINDS.sgc = wmsKind(sgcUrl, function (name) { return String(name).split(":")[2]; }, function () { return "EPSG:3857"; },
                      sgcFriendly, sgcT.attribution, "application/geo+json");

  // ── 스웨덴 — SGU GeoServer (wetherilli 213) ──
  // CC0, CORS `*`. 서버 판(`sgu.py`)처럼 레이어 하나가 1:100만·5만 판을 함께 부르고, 3413 으로 곧장 받는다.
  // 누르면 자세한 판부터 묻고(둘레 1 픽셀) 판마다 첫 하나만 남긴다. 범례는 1:100만 판의 것
  var sguT = T.sgu || {};
  function sguParts(name) { return (sguT.layers || {})[name] || []; }
  /** `sgu.clean` — `;` 로 이은 값에서 `Null:…` 칸을 뺀다 */
  function sguClean(value) {
    return String(value == null ? "" : value).split(";").map(function (p) { return p.trim(); })
      .filter(function (p) { return p && p.toLowerCase().indexOf("null") !== 0; }).join("; ");
  }
  /** `sgu.friendly` — 표(`sguT.friendly`)의 차례로, 같은 이름은 앞의 것이 이긴다 */
  function sguFriendly(props) {
    var out = {};
    (sguT.friendly || []).forEach(function (pair) {
      var value = sguClean(props[pair[0]]);
      if (value && out[pair[1]] == null) out[pair[1]] = value;
    });
    return out;
  }
  KINDS.sgu = wmsKind(sguT.url, function (name) { return sguParts(name).join(","); }, function () { return "EPSG:3413"; },
                      sguFriendly, sguT.attribution);
  KINDS.sgu.info = function (source, coordinate, view) {
    var name = source.get("gsmName"), names = sguParts(name).slice().reverse().join(",");
    if ((sguT.queryable || []).indexOf(name) < 0) return null;
    var u = source.getFeatureInfoUrl(coordinate, view.getResolution(), view.getProjection(),
                                     { INFO_FORMAT: "application/json", FEATURE_COUNT: 5, BUFFER: 1, QUERY_LAYERS: names, LAYERS: names });
    if (!u) return null;
    return getJson(u).then(function (data) {
      var seen = {};
      return tidy((data.features || []).filter(function (f) {
        var layer = String(f.id || "").split(".fid")[0];
        if (seen[layer]) return false;
        seen[layer] = true;
        return true;
      }).map(function (f) { return { id: f.id, props: forLang(sguFriendly(f.properties || {})) }; }));
    });
  };
  KINDS.sgu.legend = function (name) {
    var layer = (sguT.legend || {})[name];
    return Promise.resolve(layer ? { img: query(sguT.url, { service: "WMS", version: "1.1.1", request: "GetLegendGraphic",
                                                            format: "image/png", layer: layer }) } : null);
  };

  // ── 미국 — USGS mrdata 의 SGMC·알래스카 (wetherilli 205) ──
  // 공공 도메인, CORS `*`. 그림은 WMS 그대로. 본토(SGMC)의 WMS 는 GetFeatureInfo 가 막혀 있어 서버 판(`mrdata.get_feature_info`)처럼
  // WFS 1.0 에 작은 경위도 네모로 묻고 GML 을 읽는다. 알래스카는 WMS 의 `text/plain`(GEUS 와 같은 MapServer 꼴)
  var usgsT = T.mrdata || {};
  function usgsParts(name) { return (usgsT.layers || {})[name] || []; }
  function usgsLink(url) {
    url = String(url || "").trim();
    return /^https?:\/\//.test(url) ? { text: "", links: [{ url: url, label: "열기" }] } : null;
  }
  /** `mrdata._island_age` — upper·lower 를 ICS 의 late·early 로, `?` 는 뒤에. 못 옮기면 원문 */
  function islandAge(age) {
    if (lang() !== "ko" || !age) return age;
    var doubt = age.indexOf("?") >= 0;
    var map = { upper: "Late", lower: "Early", middle: "Middle" };
    var ics = age.replace(/\?/g, " ").split(/\s+/).filter(Boolean)
      .map(function (w) { return map[w.toLowerCase()] || w; }).join(" ") + (doubt ? " (?)" : "");
    var ko = ageKo(ics);
    return ko !== ics ? ko : age;
  }
  /** `mrdata.friendly` 와 같다 — 값은 영어 그대로, 알래스카·섬의 시대만 옮긴다. 광물 자원·광산 기호·연대 기록(wetherilli 247)과
   *  하와이·푸에르토리코(238)도 같은 갈래로 */
  function usgsFriendly(props) {
    var v = function (k) { return String(props[k] == null ? "" : props[k]).trim(); }, rows;
    var join = function (xs, sep) { return xs.filter(Boolean).join(sep); };
    if ("dep_id" in props) {
      rows = [["이름", v("site_name")], ["광종", v("code_list")], ["개발 단계", v("dev_stat")], ["보고서", usgsLink(v("url"))]];
    } else if ("ftr_type" in props) {
      var scale = v("topo_scale");
      var topo = join([v("topo_name"), /^\d+$/.test(scale) ? "(" + v("topo_date") + ", 1:" + Number(scale).toLocaleString("en-US") + ")" : ""], " ");
      rows = [["갈래", v("ftr_type")], ["이름", v("ftr_name")], ["주", join([v("county"), v("state")], " · ")],
              ["지형도", topo], ["비고", v("remarks")]];
    } else if ("recno" in props) {
      rows = [["기록 번호", v("recno")], ["상세", usgsLink(v("url"))]];
    } else if ("volcano" in props) {
      rows = [["이름", v("name") || v("unit")], ["기호", v("symbol")], ["지질시대", islandAge(v("age_range"))],
              ["암석", join([v("rock_type"), v("lithology")], " · ")], ["조성", v("compositio")], ["섬", v("island")],
              ["화산 성장 단계", v("volc_stage")], ["원도", v("source")], ["단위 설명", usgsLink(v("url"))]];
    } else if ("fmatn" in props) {
      rows = [["이름", v("name")], ["기호", v("fmatn")], ["지질시대", islandAge(v("age"))], ["암상", v("lith62name")],
              ["설명", v("descript")], ["참고 문헌", v("refs")], ["단위 설명", usgsLink(v("url"))]];
    } else if ("state_unit" in props || "age_range" in props) {
      var age = v("age_range");
      rows = [["이름", v("state_unit")], ["기호", v("label")], ["지질시대", age && lang() === "ko" ? ageKo(age) : age],
              ["단위 설명", usgsLink(v("url"))]];
    } else {
      rows = [["주", v("state")], ["기호", v("orig_label")], ["암상", v("generalize")], ["단위 설명", usgsLink(v("url"))],
              ["원도", usgsLink(v("src_url"))]];
    }
    var out = {};
    rows.forEach(function (r) { if (r[1]) out[r[0]] = r[1]; });
    return out;
  }
  function unescapeXml(t) {
    return t.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&");
  }
  /** `mrdata.parse_gml` 와 같다 — `<ms:열>값</ms:열>` 만 */
  function usgsGml(text, kind) {
    var out = [], re = new RegExp("<ms:" + kind + "[^>]*>([\\s\\S]*?)</ms:" + kind + ">", "g"), m, n = 0;
    while ((m = re.exec(String(text || "")))) {
      var props = {}, f, fr = /<ms:([A-Za-z_]+)>([\s\S]*?)<\/ms:\1>/g;
      while ((f = fr.exec(m[1]))) props[f[1]] = unescapeXml(f[2].trim());
      out.push({ id: kind + "." + (n++), properties: props });
    }
    return out;
  }
  KINDS.mrdata = {
    source: function (name) {
      var p = usgsParts(name);
      return named(name, new ol.source.TileWMS({
        url: usgsT.url + "/" + p[0], params: { LAYERS: p[1], TILED: true, FORMAT: "image/png", TRANSPARENT: true },
        projection: "EPSG:3857", tileGrid: tileGrid("EPSG:3857"), crossOrigin: "anonymous", transition: 0,
        attributions: usgsT.attribution,
      }));
    },
    info: function (source, coordinate, view) {
      var name = source.get("gsmName"), p = usgsParts(name);
      if ((usgsT.queryable || []).indexOf(name) < 0) return null;
      if (p[0] === "sgmc2") {
        var ll = ol.proj.transform(coordinate, view.getProjection(), "EPSG:4326");
        var d = Math.max(ol.proj.getPointResolution(view.getProjection(), view.getResolution(), coordinate) / 111320 * 2, 1e-5);
        var url = query(usgsT.url + "/wfs/sgmc2", { service: "WFS", version: "1.0.0", request: "GetFeature", typeName: "Lithology",
                                                    maxFeatures: 3, propertyName: (usgsT.sgmcFields || []).join(","),
                                                    bbox: [ll[0] - d, ll[1] - d, ll[0] + d, ll[1] + d].map(function (x) { return x.toFixed(6); }).join(",") });
        return fetch(url, { credentials: "omit" }).then(function (r) { return r.ok ? r.text() : ""; }).then(function (text) {
          return tidy(usgsGml(text, "Lithology").map(function (f) { return { id: f.id, props: forLang(usgsFriendly(f.properties)) }; }));
        });
      }
      var u = source.getFeatureInfoUrl(coordinate, view.getResolution(), view.getProjection(), { INFO_FORMAT: "text/plain" });
      if (!u) return null;
      return fetch(u, { credentials: "omit" }).then(function (r) { return r.ok ? r.text() : ""; }).then(function (text) {
        return tidy(parsePlain(text).map(function (f) { return { id: f.id, props: forLang(usgsFriendly(f.properties)) }; }));
      });
    },
    // 범례는 없다 — 단위가 주마다 수천이다. 팝업의 단위 설명 링크가 갈음한다
    legend: function () { return Promise.resolve(null); },
  };

  // ── 호주 — Geoscience Australia (wetherilli 212) ──
  // CC BY 4.0, Origin 을 되비춘다. 레이어 하나가 1:250만·1:100만 두 판을 함께 부르고 상류가 축척에 맞는 판을 그린다(서버의 `ga._wms`)
  var gaT = T.ga || {};
  /** `ga.friendly` 와 같다 — 이름·설명·암상은 영어 그대로, 시대만 옮긴다. 지질구·핵심 광물(`ga.other_friendly`, wetherilli 241)도 */
  function gaFriendly(props) {
    var v = function (k) {
      var s = String(props[k] == null ? "" : props[k]).trim();
      return ["null", "none"].indexOf(s.toLowerCase()) >= 0 ? "" : s;
    };
    var other = null;
    if ("provinceName" in props) {
      var older = v("olderNameAge"), younger = v("youngerNamedAge");
      var span = [older, younger !== older ? younger : ""].filter(Boolean).join(" - ") || v("geologicHistory");
      other = [["이름", v("provinceName")], ["갈래", [v("type"), v("subtype"), v("rank")].filter(Boolean).join(" · ")],
               ["상위 단위", v("parentName")], ["지질시대", span && lang() === "ko" ? ageKo(span) : span],
               ["설명", v("description")], ["주", v("state")], ["참고 문헌", v("source")]];
    } else if ("Commodities" in props || "ProjectName" in props) {
      other = [["이름", v("ProjectName")], ["광종", v("Commodities")], ["운영", v("Status")], ["주", v("STATE")]];
    }
    if (other) {
      var o = {};
      other.forEach(function (r) { if (r[1]) o[r[0]] = r[1]; });
      return o;
    }
    var hist = v("geologicHistory").split(" to ").map(function (p) { return p.trim(); }).filter(Boolean).join(" - ");
    var scale = v("resolutionScale");
    var rows = [["기호", v("mapSymbol") || v("plotSymbol")], ["이름", v("name")], ["설명", v("description")],
                ["지질시대", hist && lang() === "ko" ? ageKo(hist) : hist], ["암석", v("lithology")],
                ["축척", /^\d+(\.\d+)?$/.test(scale) ? "1:" + Math.floor(Number(scale)).toLocaleString("en-US") : ""]];
    var out = {};
    rows.forEach(function (r) { if (r[1]) out[r[0]] = r[1]; });
    return out;
  }
  // 지질구·핵심 광물·지구물리 격자(wetherilli 241)는 다른 서비스다 — 주소·레이어를 `gaT.other` 에서
  function gaOther(name) { return (gaT.other || {})[name]; }
  KINDS.ga = wmsKind(function (name) { return gaOther(name) ? gaOther(name)[0] : gaT.url; },
                     function (name) { return gaOther(name) ? gaOther(name)[1] : (gaT.layers || {})[name]; },
                     function () { return "EPSG:3857"; }, gaFriendly, gaT.attribution, "application/geo+json");
  var gaInfo = KINDS.ga.info;
  KINDS.ga.info = function (source, coordinate, view) {
    var name = source.get("gsmName"), other = gaOther(name);
    if (other ? !other[2] : (gaT.queryable || []).indexOf(name) < 0) return null;     // 서버의 `ga.queryable`
    return gaInfo(source, coordinate, view);
  };
  // 지표 지질도의 범례 그림은 198×4096 이라 싣지 않는다 — 서버 판은 보는 범위의 범례를 뜨지만 정적 판에는 그 길이 없다.
  // 지질구·핵심 광물은 서버처럼 상류의 그림(첫 레이어), 격자는 범례가 없다
  KINDS.ga.legend = function (name) {
    var other = gaOther(name);
    if (!other || !other[2]) return Promise.resolve(null);
    return Promise.resolve({ img: query(other[0], { service: "WMS", version: "1.3.0", request: "GetLegendGraphic", format: "image/png",
                                                    layer: other[1].split(",")[0] }) });
  };

  // ── 유럽 넷 — `arcwms.Door` 를 쓰는 상류 (wetherilli 257) ──
  // 네덜란드 TNO(CC0)·벨기에 DOV(무료 재사용)·SPW(CC BY 4.0)·오스트리아 GeoSphere(CC BY 4.0)·폴란드 PIG-PIB(조건 없음).
  // 모두 CORS 가 열려 있다(`*` 이거나 Origin 을 되비춘다, 2026-10-05). 서버의 `arcwms.Door` 처럼 1.1.1 로 묻고, 속성 꼴·더 붙일 변수
  // (`propertyName` 따위)는 표가 문에서 떠 온다. 손질만 상류마다 여기 둔다
  function arcKind(upstream, friendly) {
    var t = T[upstream] || {};
    function door(name) {
      var ds = t.doors || [];
      for (var i = 0; i < ds.length; i++) if (Object.prototype.hasOwnProperty.call(ds[i].layers, name)) return ds[i];
      return null;
    }
    return {
      source: function (name) {
        var d = door(name) || { url: "", layers: {} };
        return named(name, new ol.source.TileWMS({
          url: d.url, params: { LAYERS: d.layers[name], VERSION: "1.1.1", TILED: true, FORMAT: "image/png", TRANSPARENT: true },
          projection: "EPSG:3857", tileGrid: tileGrid("EPSG:3857"), crossOrigin: "anonymous", transition: 0, attributions: t.attribution,
        }));
      },
      info: function (source, coordinate, view) {
        var name = source.get("gsmName"), d = door(name);
        if (!d || d.queryable.indexOf(name) < 0) return null;
        var extra = { INFO_FORMAT: d.infoFormat, FEATURE_COUNT: 5 };
        var more = (d.infoParams || {})[name] || {};
        Object.keys(more).forEach(function (k) { extra[k.toLowerCase() === "feature_count" ? "FEATURE_COUNT" : k] = more[k]; });
        var u = source.getFeatureInfoUrl(coordinate, view.getResolution(), view.getProjection(), extra);
        if (!u) return null;
        return getJson(u).then(function (data) {
          return tidy((data.features || []).map(function (f) { return { id: f.id, props: forLang(friendly(f.properties || {})) }; }));
        });
      },
      legend: function (name) {
        var layer = (t.legend || {})[name], d = door(name);
        if (!layer || !d) return Promise.resolve(null);
        return Promise.resolve({ img: query(d.url, { service: "WMS", version: "1.1.1", request: "GetLegendGraphic",
                                                     format: "image/png", layer: layer }) });
      },
    };
  }
  /** 서버 문들의 `_value` — 빈칸·"null" 은 빈 글 */
  function val(props, key) {
    var s = String(props[key] == null ? "" : props[key]).trim();
    return s.toLowerCase() === "null" ? "" : s;
  }
  function rowsOut(rows) {
    var out = {};
    rows.forEach(function (r) { if (r[1]) out[r[0]] = r[1]; });
    return out;
  }
  /** `tno.friendly` — 값은 네덜란드어 그대로, 시대만 옮긴다 */
  function tnoFriendly(props) {
    var s = function (x) { return String(x == null ? "" : x).trim(); };
    return rowsOut([["기호", s(props.CODE)], ["이름", s(props.NAAM1 || props.LITHOSTRAT)], ["설명", s(props.OMSCHRIJVI)],
                    ["지질시대", localAge(s(props.OUDERDOM))], ["층서 명명집", s(props.VERWIJZING)]]);
  }
  /** `dov.friendly` — 값은 네덜란드어 그대로, 시대 열이 없다 */
  function dovFriendly(props) {
    return rowsOut([["기호", val(props, "code")], ["이름", val(props, "formatie")], ["부층", val(props, "lid")],
                    ["설명", val(props, "beschrijving")], ["단면", val(props, "profiel")]]);
  }
  /** `spw.friendly` — 값은 프랑스어 그대로, 시대는 가장 잘게 가른 것(절 > 통 > 계) */
  function spwFriendly(props) {
    var raw = val(props, "Etage") || val(props, "Série") || val(props, "Système");
    var sheet = [val(props, "Numéro de planche"), val(props, "Nom de planche")].filter(Boolean).join(" ");
    return rowsOut([["기호", val(props, "Sigle")], ["이름", val(props, "Nom de la formation")],
                    ["설명", val(props, "Description générale")], ["지질시대", localAge(raw)], ["도폭", sheet],
                    ["편집", val(props, "Auteurs")], ["층 설명", val(props, "Description de la notice")]]);
  }
  /** `pig.friendly` — 값은 폴란드어 그대로, 시대만 옮긴다. 1:5만(`Wydzielenia`)과 1:50만의 열이 다르다 */
  function pigFriendly(props) {
    var age = localAge(val(props, "Stratygrafia"));
    if ("Wydzielenia" in props) {
      return rowsOut([["설명", val(props, "Wydzielenia")], ["성인", val(props, "Geneza")], ["지질시대", age],
                      ["도폭", val(props, "Nr arkusza")]]);
    }
    return rowsOut([["기호", val(props, "Symbol wydzielenia")], ["설명", val(props, "Opis wydzielenia")],
                    ["암석", val(props, "Litologia")], ["지질시대", age], ["성인", val(props, "Geneza")],
                    ["빙하 층서", val(props, "Klimatostratygrafia")]]);
  }
  /** `geosphere.friendly` 의 1:100만 갈래 — `Beschreibung` 의 "암상; 시대" 를 뗀다(1:5만은 REST 라 정적 판에 없다) */
  function geosphereFriendly(props) {
    var text = String(props.Beschreibung == null ? "" : props.Beschreibung).trim();
    var cut = text.lastIndexOf(";"), rock = cut >= 0 ? text.slice(0, cut) : text, age = cut >= 0 ? text.slice(cut + 1) : "";
    return rowsOut([["암석", rock.trim()], ["지질시대", localAge(age)],
                    ["지구조 구역", String(props.Tektonik == null ? "" : props.Tektonik).trim()]]);
  }
  KINDS.tno = arcKind("tno", tnoFriendly);
  KINDS.dov = arcKind("dov", dovFriendly);
  KINDS.spw = arcKind("spw", spwFriendly);
  KINDS.pig = arcKind("pig", pigFriendly);
  KINDS.geosphere = arcKind("geosphere", geosphereFriendly);

  window.GSM_STATIC_KINDS = KINDS;
  // 시험·다른 화면이 같은 손질을 쓰게 — 정적 판의 다른 파일(개인 레이어 따위)도 지질시대를 옮길 수 있다
  window.GSM_STATIC_HELPERS = { ageKo: ageKo, parsePlain: parsePlain, compact: compact, classOf: classOf, pointBody: pointBody,
                                npiFriendly: npiFriendly, emodFriendly: emodFriendly, geusFriendly: geusFriendly, sgcFriendly: sgcFriendly,
                                sguFriendly: sguFriendly,
                                usgsFriendly: usgsFriendly, usgsGml: usgsGml, gaFriendly: gaFriendly,
                                ageLocal: ageLocal, tnoFriendly: tnoFriendly, dovFriendly: dovFriendly, spwFriendly: spwFriendly,
                                pigFriendly: pigFriendly, geosphereFriendly: geosphereFriendly,
                                tidy: tidy };
})();
