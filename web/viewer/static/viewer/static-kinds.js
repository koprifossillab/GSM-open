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
  function wmsKind(url, layerOf, projectionOf, friendly, attribution) {
    return {
      source: function (name) {
        var code = projectionOf(name);
        return named(name, new ol.source.TileWMS({
          url: url, params: { LAYERS: layerOf(name), TILED: true, FORMAT: "image/png", TRANSPARENT: true },
          projection: code, tileGrid: tileGrid(code), crossOrigin: "anonymous", transition: 0, attributions: attribution,
        }));
      },
      info: function (source, coordinate, view) {
        var u = source.getFeatureInfoUrl(coordinate, view.getResolution(), view.getProjection(),
                                         { INFO_FORMAT: "application/json", FEATURE_COUNT: 5 });
        if (!u) return null;
        return getJson(u).then(function (data) {
          return tidy((data.features || []).map(function (f) {
            return { id: f.id, props: forLang(friendly(f.properties || {})) };
          }));
        });
      },
      legend: function (name) {
        return Promise.resolve({ img: query(url, { service: "WMS", version: "1.1.1", request: "GetLegendGraphic",
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

  window.GSM_STATIC_KINDS = KINDS;
  // 시험·다른 화면이 같은 손질을 쓰게 — 정적 판의 다른 파일(개인 레이어 따위)도 지질시대를 옮길 수 있다
  window.GSM_STATIC_HELPERS = { ageKo: ageKo, parsePlain: parsePlain, compact: compact, classOf: classOf, pointBody: pointBody,
                                npiFriendly: npiFriendly, emodFriendly: emodFriendly, geusFriendly: geusFriendly, tidy: tidy };
})();
