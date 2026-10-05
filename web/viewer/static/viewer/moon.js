/* 대돌여지도 · 달 (devlog 036·037·038, P05).
 *
 * **둥근 달로 들어가서, 가까이 가면 평면에서 본다.** 한 화면에 둘이 있다.
 *
 * - 구 — CesiumJS. 달 타원체를 알아 극까지 온전하다. LOLA 지형을 세우고 기울여 본다
 * - 평면 — OpenLayers. 2D 화면과 같은 손맛이고 축척 막대가 붙는다. 투영은 달의 등거리 원통
 *   (IAU_2015:30110, 미터)이다 — Trek 의 경위도 격자가 그대로 맞는다. 위도 65° 너머는 달 극 평사도법
 *   (IAU_2015:30130·30135)이고 Trek 의 극지 판을 곧장 받는다 (052)
 *
 * 곧장 내려다보며 가까이 가면 평면으로, 평면에서 멀어지면 구로 넘어간다. 기울여 보는 동안은 구에
 * 머문다.
 *
 * 영상 배경(LRO WAC·LOLA 음영)은 브라우저가 Trek 을 곧장 부르고, 지질도·표고·속성·범례·지명은
 * 서버의 문(`trek.py`)을 거친다.
 */
(function () {
  "use strict";

  var BASE = location.pathname.replace(/moon\/?$/, "");
  var LANG = document.documentElement.lang === "en" ? "en" : "ko";
  var I18N = JSON.parse((document.getElementById("i18n-data") || {}).textContent || "{}");
  // 화면이 주소를 짓는 우리 타일의 판 (wetherilli 183) — `?v=` 를 붙이면 서버가 길게(immutable) 캐시하게 한다. 판이 바뀌면 주소가 바뀐다
  var TILE_V = JSON.parse((document.getElementById("tile-versions") || {}).textContent || "{}");
  function vq(kind) { return TILE_V[kind] ? "?v=" + TILE_V[kind] : ""; }
  function T(text, vars) {
    var out = (LANG === "en" && I18N[text]) || text;
    if (vars) out = out.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; });
    return out;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  // ── 공유 링크 (wetherilli 189) ──
  // 주소의 해시(`share.js`)로 들어오면 그 카메라·켠 레이어·배경을 덧층에 깔고 연다. 기억은 모두 `saved`·`save` 를 거치므로,
  // 링크로 연 동안에는 덧층에만 쓰고 그 사람의 localStorage 는 건드리지 않는다. 모르는 레이어·배경은 늘 하던 대로 건너뛴다
  var SHARED = window.GSMShare ? GSMShare.read() : null;
  var STATE = SHARED ? GSMShare.store(sharedSeed(SHARED)) : null;
  function sharedSeed(q) {
    var seed = { "gsm.moon.layers": JSON.stringify(GSMShare.layers(q.l)), "gsm.moon.mode": q.m === "flat" ? "flat" : "globe" };
    var c = (q.c || "").split(",").map(Number), ok = c.length === 2 && isFinite(c[0]) && isFinite(c[1]);
    if (ok && isFinite(+q.h)) {
      seed["gsm.moon.view"] = JSON.stringify({ lon: c[0], lat: c[1], h: +q.h, heading: isFinite(+q.hd) ? +q.hd : 0,
                                              pitch: isFinite(+q.pt) ? +q.pt : -Math.PI / 2 });
    }
    if (ok && isFinite(+q.res)) seed["gsm.moon.flat"] = JSON.stringify({ lon: c[0], lat: c[1], res: +q.res });
    if (q.b) seed["gsm.moon.base"] = q.b;
    return seed;
  }
  function saved(key, fallback) {
    var v;
    if (STATE) v = STATE.get(key);
    else try { v = localStorage.getItem(key); } catch (e) { return fallback; }
    return v == null ? fallback : v;
  }
  function save(key, value) {
    if (STATE) { STATE.set(key, value); return; }
    try { localStorage.setItem(key, String(value)); } catch (e) { /* 사생활 모드 */ }
  }
  function $(id) { return document.getElementById(id); }

  // ══ 달과 격자 ═════════════════════════════════════════════════════
  var R = 1737400;                                   // 달 반지름 (IAU 2015, 구)
  var M_PER_DEG = Math.PI * R / 180;
  var TREK = "https://trek.nasa.gov/tiles/Moon/EQ/";
  // 줌 끝은 2026-09-29 에 한 장씩 받아 보았다 — WAC 는 8, LOLA 음영은 6 (7 은 404), Kaguya 는 10 (11 은 404)
  //
  // 고해상(`kaguya`)은 **WAC 위에 Kaguya 지형 카메라 정사 모자이크를 얹은 것**이다 (043). Kaguya 는 줌 10
  // (한 픽셀 약 21 m)까지라 WAC(약 100 m)보다 다섯 배 촘촘하지만 틈이 있다 — 위도 75° 안쪽도 곳곳이 비고
  // (0–2 %), 극 둘레는 40 % 넘게 빈다. 넓게 볼 때는 해가 낮은 WAC 쪽이 지형이 산다. 그래서 `under` 로 WAC 를
  // 늘 밑에 깔고 Kaguya 는 줌 `min`(8, WAC 가 원자료를 다 쓰는 줌)부터 얹는다 — 틈에는 WAC 가 비친다
  // USGS Astrogeology 의 WMS(wetherilli 229) — 옛 탐사선의 모자이크. 열쇠가 없고 CORS `*`, 미국 정부 자료(공공 도메인).
  // 칸의 경위도 범위로 묻는다(`{westDegrees}` …, Cesium 과 `tileSource` 가 채운다). 한 칸 1 초 남짓(2026-10-04)
  function usgsWms(map, layer) {
    return "https://planetarymaps.usgs.gov/cgi-bin/mapserv?map=/maps/" + map + "&service=WMS&version=1.1.1&request=GetMap" +
      "&styles=&srs=EPSG:4326&width=256&height=256&format=image/png&layers=" + layer +
      "&bbox={westDegrees},{southDegrees},{eastDegrees},{northDegrees}";
  }
  var BASES = {
    kaguya: { url: TREK + "Kaguya_TCortho_Mosaic_Global_4096ppd/1.0.0/default/default028mm/{z}/{y}/{x}.png",
              max: 10, min: 8, under: "wac", credit: "SELENE (Kaguya) TC · JAXA" },
    wac: { url: TREK + "LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{z}/{y}/{x}.jpg",
           max: 8, credit: "LRO LROC WAC · NASA/GSFC/Arizona State University" },
    lola: { url: TREK + "LRO_LOLA_Shade_Global_256ppd_v06/1.0.0/default/default028mm/{z}/{y}/{x}.png",
            max: 6, credit: "LRO LOLA · NASA/GSFC" },
    // 옛 탐사선 (wetherilli 229) — 루나 오비터(1966–67)는 해가 낮아 지형이 서고 띠가 남았다. 클레멘타인(1994) 750 nm 는
    // 해가 높아 바다·고지의 밝기(조성)가 선다. 극 평면에서는 USGS 의 극 판이 우리 극 격자와 맞지 않아(축척·방향) WAC 를 쓴다
    lo: { url: usgsWms("earth/moon_simp_cyl.map", "LO"), max: 9,
          credit: "Lunar Orbiter global mosaic · NASA/USGS Astrogeology" },
    clementine: { url: usgsWms("earth/moon_simp_cyl.map", "uv_v2"), max: 8,
                  credit: "Clementine UVVIS 750 nm mosaic v2 · NRL/NASA/USGS Astrogeology" },
  };
  // 지질 레이어 목록 — 2D 의 카탈로그처럼 골라 켜면 "켠 지질 레이어" 로 올라온다(오버레이).
  // 레이어군을 더하면(원소·광물 …) 목록에 저절로 선다. 이름은 서버 `trek.LAYERS` 의 열쇠다
  //   info    누르면 읽는 갈래 (`moon/info/?layer=`)   legend  범례 칸의 갈래   src  카드 밑의 출처
  var CATALOG = [
    { group: "달 지질 (USGS 1:500만, 2020)", layers: [
      { name: "units", title: "지질 단위", info: "units", legend: "units", src: "USGS · NASA Moon Trek" },
      { name: "contacts", title: "지질 경계", src: "USGS · NASA Moon Trek" },
      { name: "linear", title: "선 구조 (능선·열구·단층)", src: "USGS · NASA Moon Trek" },
    ] },
    // 원도 6 장 — 통합 지질도가 다듬기 전의 원래 단위(195 가지). 우리가 파일을 굽는다 (`moonmap.py`, 039)
    { group: "달 지질 원도 (USGS 1:500만, 1971–1979)", layers: [
      { name: "orig-units", title: "원도 지질 단위", info: "orig", legend: "orig",
        src: "USGS I-703·948·1034·1047·1062·1162 · colors E. Lutz" },
      { name: "orig-lines", title: "원도 구조선", legend: "orig-lines", src: "USGS 1971–1979" },
    ] },
    // 착륙지 — 지점·동선은 벡터(`kind: "vector"`), 착륙지 사진은 여러 장 모자이크(`kind: "nac"`) (046)
    { group: "착륙지", layers: [
      { name: "landings", title: "착륙·충돌 지점", kind: "vector", url: "moon/landings/", legend: "landings",
        src: "NASA Moon Trek · NSSDC" },
      { name: "eva", title: "아폴로 EVA 동선", kind: "vector", url: "moon/eva/", src: "Esri UK" },
      { name: "nac", title: "착륙지 고해상 사진 (LRO NAC)", kind: "nac", src: "NASA/GSFC/Arizona State University" },
    ] },
  ];
  var LAYER = {};
  CATALOG.forEach(function (g) { g.layers.forEach(function (l) { LAYER[l.name] = l; }); });
  // NASA Trek 판 (060) — 서버가 씨앗(`data/moon_trek_layers.json`)에서 추린 것을 페이지에 싣는다. 브라우저가 Trek 을
  // 곧장 부른다(영상 배경과 같다). 수백 장이라 켤 때 레이어를 짓는다(`ensureTrek`). 이름은 `trek:<판>`
  var TREK_DATA = JSON.parse(($("trek-data") || {}).textContent || "{}");
  var TREK_ROOT = TREK_DATA.root || "https://trek.nasa.gov/tiles/Moon/EQ";
  var TREK_GROUPS = (TREK_DATA.groups || []).map(function (g) {
    return { group: LANG === "en" ? g.en : g.ko, layers: g.layers.map(function (l) {
      // `map` 은 WMTS 가 없어 우리 문이 굽는 판 — 누르면 속성을 읽는다. `same` 은 우리 레이어와 같은 자료를 다르게
      // 그린 판(Kaguya TC 지질도 = 통합 지질도) — 속성·범례를 그 레이어의 것으로 낸다
      return { name: "trek:" + l.id, kind: "trek", id: l.id, ms: l.kind === "map", ext: l.ext, max: l.max, z0: l.z0,
               bbox: l.bbox, polar: l.polar || {}, legend: l.same || (l.legend ? "trek:" + l.id : undefined),
               // 값을 칠한 판은 누른 자리의 값을 ImageServer 에서 읽는다 (wetherilli 103). 색·회색 판이 같은 갈래다
               // 값이 있으면 값이 먼저다 — 우리 문이 굽는 ImageServer 판(북극 FeO·얼음 깊이, wetherilli 150)도 값으로 읽는다
               info: l.same || (l.value ? "value:" + l.value : l.kind === "map" ? "trek" : undefined),
               title: LANG === "en" ? l.title : (l.ko || l.title), en: l.title,
               src: (l.src ? l.src + " · " : "") + "NASA Moon Trek" };
    }) };
  });
  TREK_GROUPS.forEach(function (g) { g.layers.forEach(function (l) { LAYER[l.name] = l; }); });
  var ALL_NAMES = Object.keys(LAYER);
  //: 타일 레이어(지질) — 벡터·모자이크는 아래 "착륙지" 절이 따로 짓는다
  var GEO_NAMES = ALL_NAMES.filter(function (n) { return !LAYER[n].kind; });
  var GEO_MAX = 12;
  function geoUrl(name) { return BASE + "moon/tiles/" + name + "/{z}/{x}/{y}.png" + (/^orig-/.test(name) ? vq("orig") : ""); }
  var GEO_CREDIT = "Unified Geologic Map of the Moon 1:5M (Fortezzo et al., 2020, USGS) via NASA Moon Trek";
  var ORIG_CREDIT = "USGS 1:5M lunar geologic maps 1971–1979 (renovated by Fortezzo & Hare, 2013); colors after E. Lutz";
  function creditOf(name) { return name === "units" ? GEO_CREDIT : name === "orig-units" ? ORIG_CREDIT : undefined; }

  // ── 켠 것 — 구와 평면이 함께 쓴다. 이 브라우저에 기억한다 ──
  var look = {
    base: saved("gsm.moon.base", "kaguya"),
    terrain: saved("gsm.moon.terrain", "on") !== "off",
    exag: +saved("gsm.moon.exag", "20"),
  };
  if (!BASES[look.base]) look.base = "kaguya";
  // 켠 지질 레이어 — 맨 앞이 위다. `[{name, opacity}]`. 처음이면 지질 단위 하나를 반쯤 비치게
  var active = (function () {
    try {
      var list = JSON.parse(saved("gsm.moon.layers", "null"));
      if (Array.isArray(list)) {
        return list.filter(function (e) { return e && LAYER[e.name]; })
                   .map(function (e) { return { name: e.name, opacity: isFinite(e.opacity) ? +e.opacity : 1 }; });
      }
    } catch (e) { /* 깨진 값 */ }
    return [{ name: "units", opacity: 0.6 }];
  })();
  function entryOf(name) { return active.filter(function (e) { return e.name === name; })[0]; }
  function isOn(name) { return !!entryOf(name); }
  function saveLayers() { save("gsm.moon.layers", JSON.stringify(active)); }

  // ══ 구 — Cesium ═══════════════════════════════════════════════════
  var MOON = Cesium.Ellipsoid.MOON;
  // 타원체를 넘기지 않는 곳(카메라 기본 범위·좌표 풀이)이 지구로 여기지 않게 기본값부터 바꾼다
  Cesium.Ellipsoid.default = MOON;
  function scheme() { return new Cesium.GeographicTilingScheme({ ellipsoid: MOON }); }
  // `min` 은 제공자의 minimumLevel 이 아니라 레이어의 minimumTerrainLevel 로 건다 — minimumLevel 은 그 줌의
  // 타일이 네 장을 넘으면 그리기가 흐트러진다(Cesium 문서). 구의 격자와 영상 격자가 같아 줌이 맞는다
  function cesiumBase(key) {
    var b = BASES[key];
    return new Cesium.ImageryLayer(new Cesium.UrlTemplateImageryProvider({
      url: b.url, tilingScheme: scheme(), maximumLevel: b.max, credit: b.credit,
    }), b.min ? { minimumTerrainLevel: b.min } : {});
  }

  // 지형 — LOLA 표고, 서버가 65×65 Terrarium 으로 옮겨 준다 (036)
  var DEM_SIZE = 65;
  var DEM_MAX = 9;             // 서버의 `trek.DEM_MAX_ZOOM`. 그 너머는 고운 판이 걸친 자리만, 나머지는 부모 격자를 늘려 쓴다
  var demMemo = {};
  function demGrid(x, y, level) {
    var id = level + "/" + x + "/" + y;
    if (!demMemo[id]) {
      demMemo[id] = fetch(BASE + "moon/dem/" + id + ".png").then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.blob();
      }).then(function (blob) {
        return createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
      }).then(function (bitmap) {
        var canvas = document.createElement("canvas");
        canvas.width = canvas.height = DEM_SIZE;
        var ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(bitmap, 0, 0);
        var px = ctx.getImageData(0, 0, DEM_SIZE, DEM_SIZE).data;
        var out = new Float32Array(DEM_SIZE * DEM_SIZE);
        for (var i = 0; i < out.length; i++) {
          out[i] = px[i * 4] * 256 + px[i * 4 + 1] + px[i * 4 + 2] / 256 - 32768;
        }
        return out;
      }).catch(function () {
        delete demMemo[id];                    // 다음에 다시 묻는다. 이번에는 평평하게
        return new Float32Array(DEM_SIZE * DEM_SIZE);
      });
    }
    return demMemo[id];
  }
  // 가까이서 쓰는 고운 표고 판(극 5 m·NAC, wetherilli 107) — [서, 남, 동, 북, 줌 끝]. 서버의 `trek.DEM_PARTS`
  var DEM_PARTS = JSON.parse(($("dem-parts") || {}).textContent || "[]");
  /** 그 장(또는 조상)을 서버가 줄 수 있는 가장 깊은 줌. 고운 판이 걸친 자리만 `DEM_MAX` 너머로 간다 */
  function demLevel(x, y, level) {
    for (var L = level; L > DEM_MAX; L--) {
      var k = Math.pow(2, level - L), step = 180 / Math.pow(2, L);
      var w = -180 + Math.floor(x / k) * step, n = 90 - Math.floor(y / k) * step;
      for (var i = 0; i < DEM_PARTS.length; i++) {
        var p = DEM_PARTS[i];
        if (p[4] >= L && p[0] < w + step && p[2] > w && p[1] < n && p[3] > n - step) return L;
      }
    }
    return Math.min(level, DEM_MAX);
  }
  function heights(x, y, level) {
    var top = demLevel(x, y, level);
    if (level === top) return demGrid(x, y, level);
    // 조상(서버가 주는 가장 깊은 줌) 격자의 한 조각을 겹선형으로 늘린다
    var k = Math.pow(2, level - top);
    var ax = Math.floor(x / k), ay = Math.floor(y / k);
    var ox = (x - ax * k) / k, oy = (y - ay * k) / k, span = 1 / k, n = DEM_SIZE - 1;
    return demGrid(ax, ay, top).then(function (src) {
      var out = new Float32Array(DEM_SIZE * DEM_SIZE);
      for (var j = 0; j < DEM_SIZE; j++) {
        var fy = (oy + span * j / n) * n, y0 = Math.min(n - 1, Math.floor(fy)), ty = fy - y0;
        for (var i = 0; i < DEM_SIZE; i++) {
          var fx = (ox + span * i / n) * n, x0 = Math.min(n - 1, Math.floor(fx)), tx = fx - x0;
          var a = src[y0 * DEM_SIZE + x0], b = src[y0 * DEM_SIZE + x0 + 1];
          var c = src[(y0 + 1) * DEM_SIZE + x0], d = src[(y0 + 1) * DEM_SIZE + x0 + 1];
          out[j * DEM_SIZE + i] = (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
        }
      }
      return out;
    });
  }
  var lolaTerrain = new Cesium.CustomHeightmapTerrainProvider({
    width: DEM_SIZE, height: DEM_SIZE, tilingScheme: scheme(), callback: heights,
    credit: "LRO LOLA DEM (NASA/GSFC)",
  });
  var flatTerrain = new Cesium.EllipsoidTerrainProvider({ ellipsoid: MOON });

  // 배경은 두 겹이다 — 맨 밑의 WAC(`cUnder`, 고해상일 때만 보인다)와 고른 배경(`cBase`). 영상 보정·배경 바꾸기는
  // 차례(`get(0)`)가 아니라 이 둘을 잡고 한다
  var cUnder = cesiumBase("wac");
  cUnder.show = !!BASES[look.base].under;
  var cBase = cesiumBase(look.base);
  var viewer = new Cesium.Viewer("globe", {
    globe: new Cesium.Globe(MOON),
    baseLayer: cUnder,
    terrainProvider: look.terrain ? lolaTerrain : flatTerrain,
    // 달에는 대기가 없다. 지구 전용 단추(주소 찾기·지도 고르개·시간 막대)도 뺀다
    skyAtmosphere: false,
    baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
    navigationHelpButton: false, animation: false, timeline: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false,
    // 그리기가 멈추면 Cesium 은 영어 오류 창을 띄우고 멈춘다 — 우리 안내로 바꾼다(아래 `renderFailed`, wetherilli 110·186)
    showRenderLoopErrors: false,
  });
  viewer.imageryLayers.add(cBase, 1);
  var scene = viewer.scene;
  scene.globe.showGroundAtmosphere = false;
  scene.globe.enableLighting = false;
  // 지형 뒤의 것은 가린다 — 끄면 자전축처럼 달 속을 지나는 선이 가까이서 땅 위로 비친다 (045).
  // 땅에 붙인 점·이름표는 `disableDepthTestDistance` 로 따로 가리지 않는다
  scene.globe.depthTestAgainstTerrain = true;
  scene.globe.baseColor = Cesium.Color.fromCssColorString("#1a1a1a");
  // 타일을 조금 덜 촘촘하게 — 표고·지질도가 서버를 거치므로 한 화면의 요청을 줄인다
  scene.globe.maximumScreenSpaceError = 3;
  scene.fog.enabled = false;
  if (scene.moon) scene.moon.show = false;       // 하늘에 뜨는 지구의 달 — 달 위에서는 우습다
  if (scene.sun) scene.sun.show = false;
  scene.backgroundColor = Cesium.Color.BLACK;
  scene.verticalExaggeration = look.exag / 10;
  window.__gsmMoon = viewer;

  // ── 그리기가 멈추면 (온 지구의 것을 옮겼다, wetherilli 110·186) ──
  //
  // WebGL 문맥을 잃으면 Cesium 은 되살리지 못한다. 멈춘 자리에 까닭과 나갈 길 셋을 띄운다 — 새로고침, 가볍게 다시(지형 세우기를
  // 끄고), 평면으로(평면은 OpenLayers 라 구와 따로 돈다). 가볍게 다시 연 것은 이 브라우저에 남는다
  var failed = false;
  function renderFailed(reason) {
    if (failed) return;
    failed = true;
    viewer.useDefaultRenderLoop = false;
    $("render-failed-why").textContent = reason ? String(reason).split("\n")[0].slice(0, 160) : "";
    $("render-failed").hidden = false;
  }
  scene.renderError.addEventListener(function (s, err) {
    renderFailed(err && (err.message || err));
  });
  scene.canvas.addEventListener("webglcontextlost", function (e) {
    e.preventDefault();
    renderFailed(T("WebGL 문맥을 잃었다"));
  });
  $("render-failed-reload").addEventListener("click", function () { location.reload(); });
  $("render-failed-light").addEventListener("click", function () {
    save("gsm.moon.terrain", "off");
    location.reload();
  });
  $("render-failed-flat").addEventListener("click", function () {
    $("render-failed").hidden = true;
    var c = cameraLL();                                  // 평면으로 열 자리 — 보던 가운데를 그대로
    save("gsm.moon.flat", JSON.stringify({ lon: c ? +c.lon.toFixed(4) : 0, lat: c ? +c.lat.toFixed(4) : 0, res: 2000 }));
    save("gsm.moon.mode", "flat");
    location.reload();                                   // 멈춘 구를 두고 평면만 새로 연다
  });

  var cGeo = {};
  GEO_NAMES.forEach(function (name) {
    var layer = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: geoUrl(name), tilingScheme: scheme(), maximumLevel: GEO_MAX, hasAlphaChannel: true,
      credit: creditOf(name),
    }));
    layer.show = false;
    cGeo[name] = layer;
  });

  // ══ 평면 — OpenLayers ═════════════════════════════════════════════
  //
  // 투영은 둘이다. `IAU_2015:30100` 은 달의 경위도(도) — 자료가 그 꼴로 온다. `IAU_2015:30110` 은
  // 등거리 원통(미터)이고 화면이 쓴다. 둘 사이는 곱셈 하나다. 지구의 EPSG:4326 을 빌리지 않는다 —
  // OpenLayers 가 지구 반지름으로 거리·축척을 재 3.67 배 틀어진다 (P05 §3)
  var LL = new ol.proj.Projection({ code: "IAU_2015:30100", units: "degrees",
                                    extent: [-180, -90, 180, 90], global: true });
  var EQC = new ol.proj.Projection({
    code: "IAU_2015:30110", units: "m", global: true,
    extent: [-180 * M_PER_DEG, -90 * M_PER_DEG, 180 * M_PER_DEG, 90 * M_PER_DEG],
    // 등거리 원통은 남북이 참이고 동서가 위도만큼 늘어난다. 축척 막대는 동서로 잰다 — 가운데 위도의
    // cos 를 곱해 땅의 미터로 바꾼다
    getPointResolution: function (resolution, point) {
      return resolution * Math.cos(Math.max(-89.9, Math.min(89.9, point[1] / M_PER_DEG)) * Math.PI / 180);
    },
  });
  ol.proj.addProjection(LL);
  ol.proj.addProjection(EQC);
  ol.proj.addCoordinateTransforms(LL, EQC,
    function (c) { return [c[0] * M_PER_DEG, c[1] * M_PER_DEG]; },
    function (c) { return [c[0] / M_PER_DEG, c[1] / M_PER_DEG]; });

  // ── 극 평면 (052) ──
  //
  // 위도 65° 너머는 **달 극 평사도법**으로 편다 — PSDI 가 극에 권하는 투영이고(`IAU_2015:30130` 북·`30135` 남,
  // 구·극에서 축척 1·가짜 동거 0), Trek 이 극지 영상·지질도를 이 투영으로 그려 둔다. PSDI 의 경계는 55° 지만
  // Trek 의 극지 판이 60° 까지(격자는 축 위에서 55° 까지)라 그 언저리는 비어 있다 — 경계를 65° 로 올려 극 평면이
  // 늘 자료 안에 있게 했다. 등거리 원통은 65° 에서 가로가 2.4 배라 아직 읽힌다. 등거리 원통은 극으로
  // 갈수록 가로가 늘어나(위도 80° 에서 5.8 배) 극에서는 쓸 수 없다. 경위도 타일을 극 평면으로 옮겨 그리는
  // 길도 있지만, 극점을 품은 한 장을 채우려면 경도 한 바퀴의 타일을 다 받아야 한다(줌 8 이면 수백 장).
  // 그래서 극에서는 **극 타일을 곧장** 받는다 — 격자는 Trek 극 WMTS 의 것 하나다(`trek.polar_tile_bbox`)
  var POLAR_HALF = 1095930;                // 서버의 `trek.POLAR_HALF`
  var POLAR_LAT = 65;                      // 이 위도 너머는 극 평면. 넘나드는 문턱은 ±2° 되돌이
  function psForward(pole) {
    return function (c) {
      // 반대쪽 반구는 멀리 떨어진다 — 반대 극에서 무한으로 가지 않게 80° 에서 멈춘다
      var lat = pole === "n" ? Math.max(-80, c[1]) : Math.min(80, c[1]);
      var phi = lat * Math.PI / 180, lam = c[0] * Math.PI / 180;
      var rho = 2 * R * Math.tan(Math.PI / 4 - (pole === "n" ? phi : -phi) / 2);
      return [rho * Math.sin(lam), pole === "n" ? -rho * Math.cos(lam) : rho * Math.cos(lam)];
    };
  }
  function psInverse(pole) {
    return function (c) {
      var rho = Math.hypot(c[0], c[1]), lat = 90 - 2 * Math.atan2(rho, 2 * R) * 180 / Math.PI;
      var lon = Math.atan2(c[0], pole === "n" ? -c[1] : c[1]) * 180 / Math.PI;
      return [lon, pole === "n" ? lat : -lat];
    };
  }
  function polarProj(pole) {
    var inv = psInverse(pole);
    var p = new ol.proj.Projection({
      code: pole === "n" ? "IAU_2015:30130" : "IAU_2015:30135", units: "m",
      extent: [-POLAR_HALF, -POLAR_HALF, POLAR_HALF, POLAR_HALF],
      // 극에서 축척 1 — 위도 φ 에서 한 단위가 땅의 (1 + sin|φ|) / 2 미터
      getPointResolution: function (resolution, point) {
        return resolution * (1 + Math.sin(Math.abs(inv(point)[1]) * Math.PI / 180)) / 2;
      },
    });
    ol.proj.addProjection(p);
    ol.proj.addCoordinateTransforms(LL, p, psForward(pole), inv);
    ol.proj.addCoordinateTransforms(EQC, p,
      function (c) { return psForward(pole)([c[0] / M_PER_DEG, c[1] / M_PER_DEG]); },
      function (c) { var ll = inv(c); return [ll[0] * M_PER_DEG, ll[1] * M_PER_DEG]; });
    p.pole = pole;
    return p;
  }
  var NPS = polarProj("n"), SPS = polarProj("s");
  var proj = EQC;                          // 평면이 지금 쓰는 투영
  function toLL(xy) { return ol.proj.transform(xy, proj, LL); }
  function fromLL(ll) { return ol.proj.transform(ll, LL, proj); }
  /** 그 위도에 맞는 투영. 지금 투영(`cur`)을 주면 되돌이를 둔다 — 문턱에서 오락가락하지 않게 */
  function projFor(lat, cur) {
    var a = Math.abs(lat), edge = !cur ? POLAR_LAT : cur === EQC ? POLAR_LAT + 2 : POLAR_LAT - 2;
    return a < edge ? EQC : lat > 0 ? NPS : SPS;
  }
  /** 평면의 해상도(투영 단위) ↔ 땅의 미터. 등거리 원통은 남북이 참이라 그대로다(038) */
  function groundScale(p, lat) {
    return p === EQC ? 1 : (1 + Math.sin(Math.abs(lat) * Math.PI / 180)) / 2;
  }
  function groundRes() {
    var v = flat.getView();
    return v.getResolution() * groundScale(proj, toLL(v.getCenter())[1]);
  }

  // Trek·우리 문의 격자 — 줌 0 이 가로 2·세로 1 장, y 는 북쪽부터
  function grid(maxZoom) {
    var res = [];
    for (var z = 0; z <= maxZoom; z++) res.push(180 * M_PER_DEG / Math.pow(2, z) / 256);
    return new ol.tilegrid.TileGrid({ extent: EQC.getExtent(), origin: [-180 * M_PER_DEG, 90 * M_PER_DEG],
                                      resolutions: res, tileSize: 256 });
  }
  // `box`(경위도 [서, 남, 동, 북])를 주면 그 밖의 타일은 묻지 않는다 — 착륙지 사진처럼 좁은 판은 밖이 404 인데
  // Trek 이 404 에는 CORS 를 달지 않아 콘솔이 붉어진다. 극 평면에서 옮겨 그릴 때(052) 둘레 타일을 더 묻는다
  // `z0` 은 상류가 우리 줌 0 을 몇 번으로 적는지다 — Trek 판 몇은 1 부터 센다 (060)
  function tileSource(template, maxZoom, attribution, crossOrigin, box, z0) {
    return new ol.source.TileImage({
      projection: EQC, tileGrid: grid(maxZoom), attributions: attribution, wrapX: true, crossOrigin: crossOrigin,
      tileUrlFunction: function (coord) {
        var z = coord[0], x = coord[1], y = coord[2], n = Math.pow(2, z + 1);
        if (y < 0 || y >= n / 2) return undefined;
        x = ((x % n) + n) % n;
        if (box) {
          var step = 180 / Math.pow(2, z), w = -180 + x * step, north = 90 - y * step;
          if (w > box[2] || w + step < box[0] || north < box[1] || north - step > box[3]) return undefined;
        }
        // WMS 배경(USGS Astrogeology, wetherilli 229)은 칸의 경위도 범위로 묻는다 — Cesium 의 자리표(`{westDegrees}` …)와 같은 이름
        var deg = 180 / Math.pow(2, z), west = -180 + x * deg, top = 90 - y * deg;
        return template.replace("{z}", z + (z0 || 0)).replace("{x}", x).replace("{y}", y)
          .replace("{westDegrees}", west).replace("{southDegrees}", top - deg)
          .replace("{eastDegrees}", west + deg).replace("{northDegrees}", top);
      },
    });
  }
  // 배경은 WebGL 타일이다 — 영상 보정(밝기·대비·감마·채도)을 GPU 셰이더로 건다(042). 셰이더가 영상을 읽으려면
  // CORS 로 받아야 한다(Trek 은 `*`)
  // 극 격자 — Trek 극 WMTS 의 것. 줌 0 이 한 장(±1 095 930 m), 한 장이 줌마다 반씩
  function polarGrid(maxZoom) {
    var res = [];
    for (var z = 0; z <= maxZoom; z++) res.push(2 * POLAR_HALF / 256 / Math.pow(2, z));
    return new ol.tilegrid.TileGrid({ extent: [-POLAR_HALF, -POLAR_HALF, POLAR_HALF, POLAR_HALF],
                                      origin: [-POLAR_HALF, POLAR_HALF], resolutions: res, tileSize: 256 });
  }
  // Trek 의 극지 판 — 이름의 `{P}` 가 N·S 다. 줌 끝은 2026-09-29 에 한 장씩 받아 보았다. `half` 는 판이
  // 덮는 네모의 반(m, 없으면 격자 전체). 음영은 셋을 잇는다 — 87.5° 안쪽은 5 m 판(줌 9), 75° 안쪽은 30 m(6),
  // 그 밖은 100 m(4)
  var POLAR = {
    wac: { credit: BASES.wac.credit, parts: [{ name: "LRO_WAC_Mosaic_{P}Pole60_100m_v02", max: 5 }] },
    ce2: { credit: "Chang'e-2 CCD · CNSA/CLEP (via Moon Trek)",
           parts: [{ name: "CE2_OrthoMosaic_7m_{P}P", max: 9, half: 931070 }] },
    lola: { credit: BASES.lola.credit, parts: [
      { name: "LRO_LOLA_Shade_{P}Pole875_5mp_v04", max: 9, half: 75840 },
      { name: "LRO_LOLA_Shade_{P}Pole75_30mp_v04", max: 6, half: 457440 },
      { name: "LRO_LOLA_Shade_{P}Pole45_100mp_v04", max: 4 }] },
  };
  // 극에서 고른 배경 — 고해상은 가구야가 극에 없어(40 % 넘게 빈다, 043) 창어 2 호 정사 모자이크(7 m)를 쓴다
  var POLAR_BASE = { kaguya: "ce2", wac: "wac", lola: "lola", lo: "wac", clementine: "wac" };
  /** 여러 판을 한 격자로 잇는 극 타일. 한 장마다 **그 타일을 다 덮는 가장 촘촘한 판**을 고르고, 판의 줌 끝을
   *  넘으면 조상 타일을 잘라 늘린다(`#crop=`) — OpenLayers 는 한 소스 안에서 판마다 줌 끝이 다른 것을 모른다 */
  function polarSource(pole, key) {
    var def = POLAR[key], P = pole === "n" ? "N" : "S", dir = pole === "n" ? "NP/" : "SP/";
    var parts = def.parts.map(function (part) {
      return { url: "https://trek.nasa.gov/tiles/Moon/" + dir + part.name.replace("{P}", P) +
                    "/1.0.0/default/default028mm/{z}/{y}/{x}.png", max: part.max, half: part.half };
    });
    var top = Math.max.apply(null, parts.map(function (part) { return part.max; }));
    var tileGrid = polarGrid(top);
    return new ol.source.TileImage({
      projection: pole === "n" ? NPS : SPS, tileGrid: tileGrid, attributions: def.credit, crossOrigin: "anonymous",
      tileUrlFunction: function (coord) {
        var z = coord[0], x = coord[1], y = coord[2], n = Math.pow(2, z);
        if (x < 0 || y < 0 || x >= n || y >= n) return undefined;
        var ext = tileGrid.getTileCoordExtent(coord);
        var far = Math.max(Math.abs(ext[0]), Math.abs(ext[1]), Math.abs(ext[2]), Math.abs(ext[3]));
        var part = parts.filter(function (q) { return !q.half || far <= q.half; })[0];
        if (!part) return undefined;
        if (z <= part.max) return part.url.replace("{z}", z).replace("{x}", x).replace("{y}", y);
        var dz = z - part.max, ax = x >> dz, ay = y >> dz;
        return part.url.replace("{z}", part.max).replace("{x}", ax).replace("{y}", ay) +
               "#crop=" + dz + "," + (x - (ax << dz)) + "," + (y - (ay << dz));
      },
      tileLoadFunction: function (tile, src) {
        var img = tile.getImage(), m = /#crop=(\d+),(\d+),(\d+)$/.exec(src);
        if (!m) { img.src = src; return; }
        var whole = new Image();
        whole.crossOrigin = "anonymous";
        whole.onload = function () {
          var k = Math.pow(2, +m[1]), w = 256 / k, c = document.createElement("canvas");
          c.width = c.height = 256;
          c.getContext("2d").drawImage(whole, +m[2] * w, +m[3] * w, w, w, 0, 0, 256, 256);
          img.src = c.toDataURL();
        };
        whole.onerror = function () { img.src = src.replace(/#.*$/, ""); };   // 없는 것 — 타일이 빈 채 끝난다
        whole.src = src.replace(/#.*$/, "");
      },
    });
  }
  function polarGeoSource(pole, name) {
    return new ol.source.TileImage({
      projection: pole === "n" ? NPS : SPS, tileGrid: polarGrid(GEO_MAX), attributions: creditOf(name),
      url: BASE + "moon/ptiles/" + pole + "/" + name + "/{z}/{x}/{y}.png" + (/^orig-/.test(name) ? vq("orig") : ""),
    });
  }
  function baseSource(key) {
    if (proj !== EQC) return polarSource(proj.pole, POLAR_BASE[key]);
    var b = BASES[key];
    return tileSource(b.url, b.max, b.credit, "anonymous");
  }
  /** 지금 배경의 출처 — 극이면 극지 판의 것 */
  function baseCredit(key) { return proj !== EQC ? POLAR[POLAR_BASE[key]].credit : BASES[key].credit; }
  function baseLayer(className, key) {
    return new ol.layer.WebGLTile({
      className: className, source: baseSource(key),
      style: { variables: { exposure: 0, contrast: 0, gamma: 1, saturation: 0 },
               exposure: ["var", "exposure"], contrast: ["var", "contrast"],
               gamma: ["var", "gamma"], saturation: ["var", "saturation"] },
    });
  }
  // 구처럼 두 겹 — 밑의 WAC 는 고해상일 때만, 고른 배경은 `min` 줌부터 (평면의 줌은 타일 줌과 같다)
  var oUnder = baseLayer("moon-base-under", "wac");
  var oBase = baseLayer("moon-base", look.base);
  function placeBase() {
    var b = BASES[look.base];
    oUnder.setVisible(!!b.under);
    oBase.setMinZoom(b.min && proj === EQC ? b.min - 0.5 : -Infinity);
  }
  placeBase();
  var SHADE = BASES.lola;
  var oShade = new ol.layer.Tile({ className: "moon-shade", visible: false, opacity: 0.7,
                                   source: tileSource(SHADE.url, SHADE.max, SHADE.credit, "anonymous") });   // CORS — 그림으로 뽑으려면 (048)
  var oGeo = {};
  GEO_NAMES.forEach(function (name) {
    oGeo[name] = new ol.layer.Tile({ source: tileSource(geoUrl(name), GEO_MAX, creditOf(name)),
                                     visible: false });
  });
  var oPoints = new ol.layer.Group({ layers: [] });
  // 착륙지 레이어(벡터·모자이크)가 들어갈 묶음 — 레이어는 "착륙지" 절이 짓는다 (046)
  var oExtra = new ol.layer.Group({ layers: [] });
  var flat = new ol.Map({
    target: "map",
    layers: [oUnder, oBase, oShade].concat(GEO_NAMES.map(function (n) { return oGeo[n]; }), [oExtra, oPoints]),
    view: new ol.View({ projection: EQC, center: [0, 0], resolution: 500, maxResolution: 180 * M_PER_DEG / 256,
                        constrainResolution: false }),
    controls: ol.control.defaults.defaults({ attributionOptions: { collapsible: true } }).extend([
      new ol.control.ScaleLine({ target: $("scalebar"), bar: true, steps: 4, text: true, minWidth: 110 }),
    ]),
  });
  window.__gsmMoonFlat = flat;

  // ══ 착륙지 (046) ═════════════════════════════════════════════════
  //
  // 셋이다. 착륙·충돌 지점(Trek, 서버가 캐시)·아폴로 EVA 동선(Esri UK, 저장소의 씨앗)은 벡터로 우리가 그리고,
  // 착륙지 고해상 사진(LRO NAC)은 Trek 의 모자이크 여러 장을 브라우저가 곧장 받는다(영상 배경과 같다).
  // 지질 레이어와 같은 손잡이(보이기·투명도·차례)를 갖게 `cGeo`·`oGeo` 에 넣는다 — 구의 벡터는 영상 위에
  // 따로 그려지므로 차례(`cRaise`)가 없다.
  var LANDING_ORDER = ["crewed", "soft", "rover", "impact"];
  var LANDING_STYLE = {
    crewed: { color: "#ffffff", size: 10, label: "유인 착륙" },
    soft: { color: "#4ea5d9", size: 8, label: "연착륙" },
    rover: { color: "#7bc47f", size: 8, label: "로버" },
    impact: { color: "#ff8f3d", size: 6, label: "충돌" },
  };
  var EVA_COLOR = "#ffe14d";
  // Trek 의 착륙지 모자이크 — 줌 끝은 2026-09-29 에 한 장씩 받아 보았다. 11·14 는 26–28 cm 판(대비를 높였다)
  var NAC = [
    { layer: "apollo11_26cm_mosaic_byte_geo_1_2_highContrast", max: 15, bbox: [23.4485, 0.1465, 23.5397, 1.1149] },
    { layer: "LRO_NAC_Apollo12_Mosaic_p", max: 16, bbox: [-23.4442, -3.4713, -23.3572, -2.5019] },
    { layer: "apollo14_28cm_mosaic_byte_geo_1_2_highContrast", max: 15, bbox: [-17.4901, -4.1921, -17.3908, -3.2254] },
    { layer: "LRO_NAC_Apollo15_Mosaic_p", max: 16, bbox: [3.5811, 25.7965, 3.6899, 26.7636] },
    { layer: "LRO_NAC_Apollo16_Mosaic_p", max: 14, bbox: [15.3788, -9.6061, 15.5545, -8.6617] },
    { layer: "NAC_DTM_APOLLO17_MOSAIC_120CM", max: 14, bbox: [29.9059, 19.3905, 31.658, 21.3035] },
    { layer: "LRO_NAC_Post_Landing_OrthoMosaic_1mpp_IM_1_LandingSite", max: 13, bbox: [0.9387, -80.2164, 1.9392, -80.0428] },
  ];
  var NAC_CREDIT = "LRO NAC · NASA/GSFC/Arizona State University (via Moon Trek)";
  var cRaise = {};
  GEO_NAMES.forEach(function (n) { cRaise[n] = [cGeo[n]]; });
  function proxy(onShow, onAlpha) {
    var h = {};
    Object.defineProperty(h, "show", { set: onShow });
    Object.defineProperty(h, "alpha", { set: onAlpha });
    return h;
  }
  // ── 착륙지 사진 ──
  (function nac() {
    var cl = NAC.map(function (m) {
      var layer = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
        url: TREK + m.layer + "/1.0.0/default/default028mm/{z}/{y}/{x}.png", tilingScheme: scheme(),
        maximumLevel: m.max, rectangle: Cesium.Rectangle.fromDegrees(m.bbox[0], m.bbox[1], m.bbox[2], m.bbox[3]),
        credit: NAC_CREDIT,
      }));
      layer.show = false;
      return layer;
    });
    cRaise.nac = cl;
    cGeo.nac = proxy(function (v) { cl.forEach(function (l) { l.show = v; }); },
                     function (a) { cl.forEach(function (l) { l.alpha = a; }); });
    oGeo.nac = new ol.layer.Group({ visible: false, layers: NAC.map(function (m) {
      return new ol.layer.Tile({
        gsmBox: m.bbox,                                                    // 투영을 바꾸면 범위를 다시 잰다 (052)
        extent: [m.bbox[0] * M_PER_DEG, m.bbox[1] * M_PER_DEG, m.bbox[2] * M_PER_DEG, m.bbox[3] * M_PER_DEG],
        source: tileSource(TREK + m.layer + "/1.0.0/default/default028mm/{z}/{y}/{x}.png", m.max, NAC_CREDIT,
                           "anonymous", m.bbox),                           // CORS — 그림으로 뽑으려면 (048)
      });
    }) });
    oExtra.getLayers().push(oGeo.nac);
  })();
  // ── NASA Trek 판 (060) — 켤 때 짓는다. 구는 영상 레이어, 평면은 `oExtra` 의 타일 ──
  var TREK_CREDIT = "NASA Moon Trek";
  function ensureTrek(name) {
    var l = LAYER[name];
    if (!l || l.kind !== "trek" || cGeo[name]) return;
    var url = l.ms ? BASE + "trek/moon/map/" + l.id + "/{zz}/{x}/{y}.png"
                   : TREK_ROOT + "/" + l.id + "/1.0.0/default/default028mm/{zz}/{y}/{x}." + l.ext;
    var z0 = l.z0 || 0;
    var layer = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: url, tilingScheme: scheme(), maximumLevel: l.ms ? GEO_MAX : l.max, hasAlphaChannel: l.ms || l.ext === "png",
      customTags: { zz: function (provider, x, y, level) { return level + z0; } },
      rectangle: l.bbox ? Cesium.Rectangle.fromDegrees(l.bbox[0], l.bbox[1], l.bbox[2], l.bbox[3]) : undefined,
      credit: TREK_CREDIT,
    }));
    layer.show = false;
    cGeo[name] = layer;
    cRaise[name] = [layer];
    var tile = new ol.layer.Tile({
      visible: false,
      source: tileSource(url.replace("{zz}", "{z}"), l.ms ? GEO_MAX : l.max, TREK_CREDIT, "anonymous", l.bbox, z0),
    });
    if (l.bbox) {
      tile.set("gsmBox", l.bbox);                                          // 투영을 바꾸면 범위를 다시 잰다 (052)
      tile.setExtent(ol.proj.transformExtent(l.bbox, LL, proj, 16));
    }
    tile.set("gsmTrekUrl", url.replace("{zz}", "{z}"));
    oGeo[name] = tile;
    oExtra.getLayers().push(tile);
    if (proj !== EQC) trekFlat(name);
  }
  /** 평면의 Trek 판을 지금 투영에 맞춘다. 극이고 Trek 이 극지 짝(`<판>_SP`·`_NP`)을 구워 두었으면 그것을 곧장 받고
   *  — 적도 판을 옮겨 그리면 극 가까이가 성기다 — 없으면 적도 판을 옮겨 그린다 (wetherilli 085) */
  function trekFlat(name) {
    var l = LAYER[name], tile = oGeo[name], p = proj !== EQC && l.polar[proj.pole];
    if (!p) {
      tile.setSource(tileSource(tile.get("gsmTrekUrl"), l.ms ? GEO_MAX : l.max, TREK_CREDIT, "anonymous", l.bbox,
                                l.z0 || 0));
      if (l.bbox) tile.setExtent(ol.proj.transformExtent(l.bbox, LL, proj, 16));
      return;
    }
    var pole = proj.pole, projection = pole === "n" ? NPS : SPS;
    if (p.kind === "map") {                                              // 우리 문이 극 좌표로 굽는다
      tile.setSource(new ol.source.TileImage({
        projection: projection, tileGrid: polarGrid(GEO_MAX), attributions: TREK_CREDIT,
        url: BASE + "trek/moon/map/" + l.id + "/p/" + pole + "/{z}/{x}/{y}.png",
      }));
      tile.setExtent(undefined);
      return;
    }
    // 판이 덮는 네모(m) 밖은 묻지 않는다 — Trek 이 404 에 CORS 를 달지 않아 콘솔이 붉어진다
    var root = TREK_ROOT.replace(/\/EQ$/, pole === "n" ? "/NP" : "/SP"), tg = polarGrid(p.max), box = p.box;
    tile.setSource(new ol.source.TileImage({
      projection: projection, tileGrid: tg, attributions: TREK_CREDIT, crossOrigin: "anonymous",
      tileUrlFunction: function (coord) {
        var z = coord[0], x = coord[1], y = coord[2], n = Math.pow(2, z);
        if (x < 0 || y < 0 || x >= n || y >= n) return undefined;
        var e = tg.getTileCoordExtent(coord);
        if (box && (e[0] > box[2] || e[2] < box[0] || e[1] > box[3] || e[3] < box[1])) return undefined;
        return root + "/" + p.name + "/1.0.0/default/default028mm/" + z + "/" + y + "/" + x + "." + p.ext;
      },
    }));
    tile.setExtent(box || undefined);
  }
  // ── 벡터 — 착륙·충돌 지점, EVA 동선. 처음 켤 때 받는다 ──
  function vectorLayer(name, draw) {
    var ds = new Cesium.CustomDataSource(name);
    ds.show = false;
    viewer.dataSources.add(ds);
    var src = new ol.source.Vector();
    var ol_ = new ol.layer.Vector({ source: src, visible: false, declutter: name === "landings",
                                    style: draw.olStyle });
    ol_.set("gsmSet", { name: T(LAYER[name].title), color: draw.chip });
    oExtra.getLayers().push(ol_);
    var loaded = false;
    function load() {
      if (loaded) return;
      loaded = true;
      fetch(BASE + LAYER[name].url).then(function (r) { return r.json(); }).then(function (data) {
        (data.features || []).forEach(function (f) { draw.cesium(ds, f); });
        src.addFeatures(new ol.format.GeoJSON().readFeatures(
          { type: "FeatureCollection", features: (data.features || []).map(draw.olFeature) },
          { dataProjection: LL, featureProjection: proj }));
      }).catch(function () { loaded = false; });
    }
    cRaise[name] = [];
    cGeo[name] = proxy(function (v) { ds.show = v; if (v) load(); }, function () { /* 벡터는 늘 또렷이 */ });
    oGeo[name] = ol_;
  }
  function landingProps(p) {
    var out = { "이름표": p["이름표"] };
    out[T("종류")] = T((LANDING_STYLE[p.kind] || {}).label || p.kind);
    if (p.date) out[T("날짜")] = p.date;
    if (p.link) out["NSSDC"] = p.link;
    return out;
  }
  vectorLayer("landings", {
    chip: "#ffffff",
    cesium: function (ds, f) {
      var st = LANDING_STYLE[f.properties.kind] || LANDING_STYLE.impact;
      var e = ds.entities.add({
        position: Cesium.Cartesian3.fromDegrees(f.geometry.coordinates[0], f.geometry.coordinates[1], 0, MOON),
        point: { pixelSize: st.size, color: Cesium.Color.fromCssColorString(st.color), outlineColor: Cesium.Color.BLACK,
                 outlineWidth: 1.5, heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                 disableDepthTestDistance: 1500000 },
        label: { text: f.properties["이름표"], font: "12px system-ui, sans-serif", fillColor: Cesium.Color.WHITE,
                 outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                 pixelOffset: new Cesium.Cartesian2(0, -14), heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                 distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 900000),
                 disableDepthTestDistance: 1500000 },
      });
      e.gsmProps = landingProps(f.properties);
      e.gsmSet = { name: T(LAYER.landings.title), color: st.color };
    },
    olFeature: function (f) { return { type: "Feature", geometry: f.geometry,
                                        properties: Object.assign({ _kind: f.properties.kind }, landingProps(f.properties)) }; },
    olStyle: function (feature, resolution) {
      var st = LANDING_STYLE[feature.get("_kind")] || LANDING_STYLE.impact;
      return new ol.style.Style({
        image: new ol.style.Circle({ radius: st.size / 2 + 1, fill: new ol.style.Fill({ color: st.color }),
                                     stroke: new ol.style.Stroke({ color: "#000", width: 1.5 }) }),
        text: resolution < 3000 ? new ol.style.Text({ text: feature.get("이름표"), offsetY: -14,
          font: "12px system-ui, sans-serif", fill: new ol.style.Fill({ color: "#fff" }),
          stroke: new ol.style.Stroke({ color: "#000", width: 3 }) }) : undefined,
      });
    },
  });
  function evaProps(p) {
    var out = { "이름표": p.mission + " EVA" };
    out[T("임무")] = p.mission;
    if (p.who) out[T("사람")] = p.who;
    return out;
  }
  vectorLayer("eva", {
    chip: EVA_COLOR,
    cesium: function (ds, f) {
      var lines = f.geometry.type === "LineString" ? [f.geometry.coordinates] : f.geometry.coordinates;
      lines.forEach(function (line) {
        var flatArr = [];
        line.forEach(function (c) { flatArr.push(c[0], c[1]); });
        var e = ds.entities.add({ polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(flatArr, MOON), width: 2, clampToGround: true,
          material: Cesium.Color.fromCssColorString(EVA_COLOR),
          // 동선은 착륙지 둘레 수 km 다 — 멀리서는 점 하나로도 안 보인다
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 120000) } });
        e.gsmProps = evaProps(f.properties);
        e.gsmSet = { name: T(LAYER.eva.title), color: EVA_COLOR };
      });
    },
    olFeature: function (f) { return { type: "Feature", geometry: f.geometry, properties: evaProps(f.properties) }; },
    olStyle: new ol.style.Style({ stroke: new ol.style.Stroke({ color: EVA_COLOR, width: 2 }) }),
  });

  // ══ 구 ⇄ 평면 ═════════════════════════════════════════════════════
  //
  // 넘는 높이를 둘로 둔다(되돌이). 구에서 250 km 밑으로 곧장 내려다보면 평면으로, 평면에서 400 km
  // 높이만큼 멀어지면 구로. 둘이 같으면 문턱에서 오락가락한다
  var TO_FLAT_H = 250000, TO_GLOBE_H = 400000;
  var mode = "globe";
  var autoFlat = true;                    // 손으로 구로 돌아오면, 한 번 멀어질 때까지 저절로 넘지 않는다
  var wrap = $("map-wrap");

  function fovy() {
    var f = viewer.camera.frustum;
    return f.fovy || f.fov || Math.PI / 3;
  }
  function heightToRes(h) { return 2 * h * Math.tan(fovy() / 2) / Math.max(1, scene.canvas.clientHeight); }
  function resToHeight(res) { return res * Math.max(1, scene.canvas.clientHeight) / (2 * Math.tan(fovy() / 2)); }
  function cameraLL() {
    var c = MOON.cartesianToCartographic(viewer.camera.positionWC);
    return c ? { lon: Cesium.Math.toDegrees(c.longitude), lat: Cesium.Math.toDegrees(c.latitude), h: c.height } : null;
  }
  function flyGlobe(lon, lat, h, duration) {
    var dest = Cesium.Cartesian3.fromDegrees(lon, lat, h, MOON);
    var orient = { heading: 0, pitch: -Math.PI / 2, roll: 0 };
    if (duration) viewer.camera.flyTo({ destination: dest, orientation: orient, duration: duration });
    else viewer.camera.setView({ destination: dest, orientation: orient });
  }

  function setMode(next, at) {
    if (next === mode) return;
    closePopup();
    cancelSketch();                         // 끝내지 않은 선은 넘어가지 않는다. 끝낸 것은 둘 다 그린다
    if (next === "flat") {
      var c = at || cameraLL();
      if (!c) return;
      // 위도가 투영을 고른다 — 65° 너머는 극 평사도법 (052)
      var ground = Math.min(heightToRes(c.h), heightToRes(TO_GLOBE_H) * 0.9);
      useProj(projFor(c.lat), [c.lon, c.lat], ground);
      var view = flat.getView();
      view.setCenter(fromLL([c.lon, c.lat]));
      view.setResolution(ground / groundScale(proj, c.lat));
      view.setRotation(0);
      mode = "flat";
      wrap.className = "moon-flat";
      // 숨은 구는 그리기를 멈춘다 — 안 보이는데 GPU 를 먹고, 평면의 WebGL 배경과 다툰다 (042)
      viewer.useDefaultRenderLoop = false;
      flat.updateSize();
    } else {
      var v = flat.getView(), ll = toLL(v.getCenter());
      flyGlobe(ll[0], ll[1], (at && at.h) || resToHeight(groundRes()));
      mode = "globe";
      viewer.useDefaultRenderLoop = true;
      wrap.className = "moon-globe";
    }
    save("gsm.moon.mode", mode);
  }

  /** 평면의 투영을 바꾼다 (052). 타일 소스를 갈아 끼우고, 벡터는 모양을 옮기고, 찍고 잰 것은 경위도에서
   *  다시 그린다. 새 뷰는 `ll` 을 가운데에, 땅의 해상도 `ground` 로 연다. 바뀌었으면 true */
  function useProj(p, ll, ground) {
    if (p === proj) return false;
    var from = proj;
    proj = p;
    cancelSketch();
    function each(layer) {
      if (layer instanceof ol.layer.Group) { layer.getLayers().forEach(each); return; }
      if (layer.get("gsmBox")) layer.setExtent(ol.proj.transformExtent(layer.get("gsmBox"), LL, p, 16));
      if (layer instanceof ol.layer.Vector && layer.getSource() !== drawSource) {
        layer.getSource().getFeatures().forEach(function (f) {
          if (f.getGeometry()) f.getGeometry().transform(from, p);
        });
      }
    }
    flat.getLayers().forEach(each);
    oUnder.setSource(baseSource("wac"));
    oBase.setSource(baseSource(look.base));
    oShade.setSource(p === EQC ? tileSource(SHADE.url, SHADE.max, SHADE.credit, "anonymous") : polarSource(p.pole, "lola"));
    GEO_NAMES.forEach(function (name) {
      oGeo[name].setSource(p === EQC ? tileSource(geoUrl(name), GEO_MAX, creditOf(name)) : polarGeoSource(p.pole, name));
    });
    Object.keys(oGeo).forEach(function (name) {
      if (LAYER[name] && LAYER[name].kind === "trek") trekFlat(name);
    });
    placeBase();
    var polar = p !== EQC;
    flat.setView(new ol.View({
      projection: p, center: fromLL(ll), resolution: ground / groundScale(p, ll[1]), constrainResolution: false,
      maxResolution: polar ? 2 * POLAR_HALF / 256 : 180 * M_PER_DEG / 256,
      // 가운데만 격자 안에 묶는다 — 화면 전체를 묶으면 멀리서 볼 때 가운데가 극에서 떠나지 못한다
      extent: polar ? [-POLAR_HALF, -POLAR_HALF, POLAR_HALF, POLAR_HALF] : undefined, constrainOnlyCenter: polar,
    }));
    installFlat();
    renderDrawn();
    applyTune();
    return true;
  }

  viewer.camera.moveEnd.addEventListener(function () {
    var c = cameraLL();
    if (!c) return;
    save("gsm.moon.view", JSON.stringify({
      lon: +c.lon.toFixed(5), lat: +c.lat.toFixed(5), h: Math.round(c.h),
      heading: +viewer.camera.heading.toFixed(4), pitch: +viewer.camera.pitch.toFixed(4),
    }));
    if (mode !== "globe") return;
    if (c.h > TO_FLAT_H) { autoFlat = true; return; }
    var straight = viewer.camera.pitch < Cesium.Math.toRadians(-80);
    if (autoFlat && straight && !drawing() && !tilting) setMode("flat", c);
  });
  flat.on("moveend", function () {
    if (mode !== "flat") return;
    var v = flat.getView(), ll = toLL(v.getCenter()), ground = groundRes();
    // 해상도는 땅의 미터로 적는다 — 투영마다 단위의 뜻이 달라서다 (052)
    save("gsm.moon.flat", JSON.stringify({ lon: +ll[0].toFixed(5), lat: +ll[1].toFixed(5), res: Math.round(ground) }));
    if (drawing()) return;                // 그리던 선이 끊기지 않게 (041)
    if (ground > heightToRes(TO_GLOBE_H)) { setMode("globe"); return; }
    // 극으로 가면 극 평사도법으로, 돌아오면 등거리 원통으로 — 문턱 둘레 2° 는 되돌이다 (052)
    useProj(projFor(ll[1], proj), ll, ground);
  });

  $("tool-mode").addEventListener("click", function () {
    if (mode === "globe") {
      var c = cameraLL();
      if (!c) return;
      // 멀리서 누르면 문턱 높이까지 내려와 평면으로. 극이면 극 평사도법이다 (052)
      setMode("flat", { lon: c.lon, lat: c.lat, h: Math.min(c.h, TO_FLAT_H) });
    } else {
      autoFlat = false;
      setMode("globe", { h: Math.max(resToHeight(groundRes()), TO_FLAT_H * 1.4) });
    }
  });
  $("tool-home").addEventListener("click", function () {
    if (mode === "flat") setMode("globe", { h: 5200000 });
    flyGlobe(0, 0, 5200000, 1.5);
  });
  // 북쪽 위 — 가운데 점 위로 올라가 곧장 내려다본다. 가까우면 다 내려다본 뒤 평면으로 넘어간다
  $("tool-top").addEventListener("click", function () {
    var p = pivot(true);
    if (p) { orbit(p, 0, -90, 0.8); return; }
    var c = cameraLL();
    if (c) flyGlobe(c.lon, c.lat, c.h, 0.8);
  });

  // ══ 자세 — 가운데 점 · 거리 · 방위 · 기울기 (045) ═══════════════════
  //
  // 지구 3D(MapLibre)와 같은 네 값으로 본다. **돌고 기울이는 중심은 화면 한가운데 아래의 지형 점**이다 —
  // 보던 크레이터가 가운데에 머문다.
  //
  // - 방위는 **달의 북극**(자전축을 그 점의 수평면에 내린 쪽)이 0°, 시계 방향. IAU 달 좌표계·지명이 다
  //   이 북쪽이다. 극점 위에서는 북쪽이 없으므로 **위도 89.5° 너머는 지구 쪽(경도 0°, +X 축)이 0°** 다 —
  //   달은 늘 같은 면을 지구로 향하므로 극에서 가장 자연스러운 기준이다
  // - 기울기는 그 점에서 **달 구면에 접하는 수평면**으로 잰다. 지형의 경사로 재면 크레이터 벽에서 값이
  //   춤춘다. 보이는 값은 지구 3D 처럼 곧장 내려다봄이 0°, 수평이 90° 다
  //
  // 손 — 오른쪽 단추(또는 Ctrl)로 끌면 기울이고 돈다. 휠은 당기고 민다. 평면에서 그렇게 끌면 같은
  // 가운데·같은 넓이로 구로 넘어가며 기울기가 붙는다. 평면은 지도 읽기, 기울이는 순간부터는 3D 다
  var cam = scene.screenSpaceCameraController;
  cam.tiltEventTypes = [Cesium.CameraEventType.MIDDLE_DRAG, Cesium.CameraEventType.PINCH,
                        Cesium.CameraEventType.RIGHT_DRAG,
                        { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL }];
  cam.zoomEventTypes = [Cesium.CameraEventType.WHEEL, Cesium.CameraEventType.PINCH];
  var tilting = false;                     // 평면에서 넘어와 끄는 중 — 그동안은 평면으로 되넘지 않는다
  var X_AXIS = new Cesium.Cartesian3(1, 0, 0), Z_AXIS = new Cesium.Cartesian3(0, 0, 1);

  /** 화면 한가운데 아래의 점과 거기까지의 거리. `terrain` 이면 지형을, 아니면 타원체를 짚는다(가볍다). */
  function pivot(terrain) {
    var cv = scene.canvas, mid = new Cesium.Cartesian2(cv.clientWidth / 2, cv.clientHeight / 2);
    var pos = null;
    if (terrain) {
      var ray = viewer.camera.getPickRay(mid);
      pos = ray && scene.globe.pick(ray, scene);
    }
    if (!pos) pos = viewer.camera.pickEllipsoid(mid, MOON);
    return pos ? { pos: pos, range: Cesium.Cartesian3.distance(viewer.camera.positionWC, pos) } : null;
  }
  /** 점 `pos` 의 수평면에서 본 카메라의 방위·기울기(도). `cesium` 이면 Cesium 의 동-북-위를 쓴다 —
   *  `lookAt` 에 넘길 값이다. 아니면 위의 기준(극 가까이는 지구 쪽)이다. */
  function anglesAt(pos, cesium) {
    var up = MOON.geodeticSurfaceNormal(pos, new Cesium.Cartesian3());
    var north, east;
    if (cesium) {
      var m = Cesium.Transforms.eastNorthUpToFixedFrame(pos, MOON);
      east = Cesium.Matrix4.getColumn(m, 0, new Cesium.Cartesian4());
      north = Cesium.Matrix4.getColumn(m, 1, new Cesium.Cartesian4());
      east = new Cesium.Cartesian3(east.x, east.y, east.z);
      north = new Cesium.Cartesian3(north.x, north.y, north.z);
    } else {
      var lat = Cesium.Math.toDegrees(MOON.cartesianToCartographic(pos).latitude);
      var ref = Math.abs(lat) > 89.5 ? X_AXIS : Z_AXIS;
      north = Cesium.Cartesian3.subtract(ref, Cesium.Cartesian3.multiplyByScalar(up, Cesium.Cartesian3.dot(ref, up),
                                                                                   new Cesium.Cartesian3()), new Cesium.Cartesian3());
      Cesium.Cartesian3.normalize(north, north);
      east = Cesium.Cartesian3.cross(north, up, new Cesium.Cartesian3());
    }
    var d = viewer.camera.directionWC;
    // 곧장 내려다보면 시선이 수평면에 그림자를 남기지 않는다 — 그때는 화면의 위쪽(카메라 up)이 향한 쪽이 방위다
    var f = Math.abs(Cesium.Cartesian3.dot(d, up)) > 0.999 ? viewer.camera.upWC : d;
    var heading = Cesium.Math.toDegrees(Math.atan2(Cesium.Cartesian3.dot(f, east), Cesium.Cartesian3.dot(f, north)));
    return { heading: (heading + 360) % 360,
             pitch: Cesium.Math.toDegrees(Math.asin(Math.max(-1, Math.min(1, Cesium.Cartesian3.dot(d, up))))) };
  }
  /** 가운데 점 둘레로 돈다 — 방위(위의 기준)·기울기(수평면 기준, −90 이 곧장 내려다봄)·거리는 그대로. */
  function orbit(p, heading, pitch, duration) {
    // 우리 방위와 Cesium 방위의 어긋남(극 가까이에서만 0 이 아니다)을 얹어 Cesium 의 값으로 바꾼다
    var shift = anglesAt(p.pos, true).heading - anglesAt(p.pos, false).heading;
    var hpr = new Cesium.HeadingPitchRange(Cesium.Math.toRadians(heading + shift), Cesium.Math.toRadians(pitch), p.range);
    if (duration) {
      viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(p.pos, 0), { offset: hpr, duration: duration });
    } else {
      viewer.camera.lookAt(p.pos, hpr);
      viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    }
  }

  // 방위 단추(나침반) — 바늘이 달의 북쪽을 가리킨다. 누르면 기울기는 두고 북쪽을 위로 돌린다
  var needle = $("compass-needle"), poseOut = $("pose"), topBtn = $("tool-top"), compassBtn = $("tool-compass");
  $("tool-compass").addEventListener("click", function () {
    var p = pivot(true);
    if (!p) return;
    orbit(p, 0, anglesAt(p.pos, false).pitch, 0.6);
  });
  var lastView = new Cesium.Matrix4();
  scene.postRender.addEventListener(function () {
    if (mode !== "globe" || Cesium.Matrix4.equalsEpsilon(lastView, viewer.camera.viewMatrix, 1e-9)) return;
    Cesium.Matrix4.clone(viewer.camera.viewMatrix, lastView);
    syncAxisNear();
    var p = pivot(false);
    if (!p) { poseOut.textContent = ""; topBtn.disabled = compassBtn.disabled = false; return; }
    var a = anglesAt(p.pos, false);
    needle.setAttribute("transform", "rotate(" + (-a.heading).toFixed(1) + " 12 12)");
    // 이미 북쪽이 위이고 곧장 내려다보면 "북쪽 위" 는 할 일이 없다 — 흐리게 해 눌러도 그대로인 까닭을 보인다.
    // 가운데 점을 못 짚으면(하늘을 보면) 켜 둔다 — 그때도 카메라 발밑으로 내려다보는 일은 한다
    // 방위 단추도 같다 — 북쪽이 이미 위면 흐리게. 곧장 내려다보면 방위는 화면의 위쪽으로 읽는다(`anglesAt`)
    var north = Math.min(a.heading, 360 - a.heading) < 0.5;
    compassBtn.disabled = north;
    topBtn.disabled = north && 90 + a.pitch < 0.5;
    poseOut.textContent = T("기울기 {tilt}° · 방위 {heading}°", { tilt: Math.round(90 + a.pitch), heading: Math.round(a.heading) % 360 });
  });

  // 평면에서 오른쪽 단추·Ctrl 로 끌면 — 구로 넘어가며 기울인다. 넘어간 뒤의 끌기는 우리가 받는다
  // (누르는 순간 구는 숨어 있어 Cesium 이 그 끌기를 모른다). 위로 끌면 눕고, 옆으로 끌면 돈다
  var flatEl = $("map");
  flatEl.addEventListener("contextmenu", function (e) { e.preventDefault(); });
  flatEl.addEventListener("pointerdown", function (e) {
    if (mode !== "flat" || !(e.button === 2 || (e.button === 0 && e.ctrlKey))) return;
    e.preventDefault();
    e.stopPropagation();
    var v = flat.getView(), ll = wrapLon(toLL(v.getCenter())), h = resToHeight(groundRes());
    var ground = scene.globe.getHeight(Cesium.Cartographic.fromDegrees(ll[0], ll[1])) || 0;
    tilting = true;
    setMode("globe", { h: h });
    var p = { pos: Cesium.Cartesian3.fromDegrees(ll[0], ll[1], ground, MOON), range: h - ground };
    var x0 = e.clientX, y0 = e.clientY, heading = 0, pitch = -90;
    function move(ev) {
      heading = ((ev.clientX - x0) * 0.4 % 360 + 360) % 360;
      pitch = Math.max(-90, Math.min(-8, -90 + (y0 - ev.clientY) * 0.35));
      orbit(p, heading, pitch);
    }
    function up() {
      window.removeEventListener("pointermove", move, true);
      window.removeEventListener("pointerup", up, true);
      tilting = false;
      viewer.camera.moveEnd.raiseEvent();       // 거의 안 기울였으면 다시 평면으로
    }
    window.addEventListener("pointermove", move, true);
    window.addEventListener("pointerup", up, true);
  }, true);

  // ══ 패널 ══════════════════════════════════════════════════════════
  document.querySelectorAll(".tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      document.querySelectorAll(".tab").forEach(function (t) { t.classList.toggle("on", t === tab); });
      document.querySelectorAll(".tabbody").forEach(function (b) {
        b.classList.toggle("on", b.id === "tab-" + tab.dataset.tab);
      });
    });
  });
  (function emblemMenu() {
    var button = $("emblem-btn"), menu = $("hidden-menu");
    function show(open) { menu.hidden = !open; button.setAttribute("aria-expanded", open ? "true" : "false"); }
    button.addEventListener("click", function (e) { e.stopPropagation(); show(menu.hidden); });
    document.addEventListener("click", function (e) { if (!menu.hidden && !menu.contains(e.target)) show(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !menu.hidden) show(false); });
  })();

  // 배경
  var baseSelect = $("basemap");
  baseSelect.value = look.base;
  baseSelect.addEventListener("change", function () {
    look.base = baseSelect.value;
    save("gsm.moon.base", look.base);
    var layers = viewer.imageryLayers;
    layers.remove(cBase, true);
    cBase = cesiumBase(look.base);
    layers.add(cBase, layers.indexOf(cUnder) + 1);
    cUnder.show = !!BASES[look.base].under;
    oBase.setSource(baseSource(look.base));
    placeBase();
    applyTune();
  });

  // ── 영상 보정 (042) ──
  //
  // 배경 영상만 고친다 — 지질도의 색은 약속이라 건드리지 않는다. 구는 Cesium 의 ImageryLayer 속성을,
  // 평면은 WebGL 타일의 셰이더 변수를 쓴다. **둘의 공식이 같다** — 밝기는 곱(OL 의 exposure = 밝기 − 1),
  // 대비는 0.5 를 축으로 늘이기(OL 의 contrast = 대비 − 1), 감마는 색^(1/감마), 채도는 OL 의 saturation = 채도 − 1.
  // 처음에는 평면에 CSS 필터와 SVG 감마(feComponentTransfer)를 걸었는데, 캔버스의 SVG 필터는 CPU 로 그려
  // 헤드리스 크롬에서 화면이 멎었다 — 그래서 셰이더로 옮겼다
  //
  // "음영 겹치기" 는 WAC 영상 위에 LOLA 음영을 얹어 지형의 그늘을 살린다. 평면은 곱하기(multiply)로 섞고
  // (Lutz 가 색 지질도를 음영에 곱한 것과 같은 수, CP 94), 구는 섞는 법이 없어 반투명으로 얹는다
  var TUNE_DEFAULT = { bright: 100, contrast: 100, gamma: 100, sat: 100, shade: false };
  var PRESETS = {
    crisp: { bright: 105, contrast: 160, gamma: 90, sat: 100, shade: false },
    relief: { bright: 110, contrast: 130, gamma: 110, sat: 100, shade: true },
  };
  var tune = (function () {
    try { return Object.assign({}, TUNE_DEFAULT, JSON.parse(saved("gsm.moon.tune", "{}")) || {}); }
    catch (e) { return Object.assign({}, TUNE_DEFAULT); }
  })();
  var cShade = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
    url: SHADE.url, tilingScheme: scheme(), maximumLevel: SHADE.max, credit: SHADE.credit,
  }), viewer.imageryLayers.indexOf(cBase) + 1);
  cShade.alpha = 0.4;
  var TUNES = ["bright", "contrast", "gamma", "sat"];
  function tuneText(key, v) { return key === "gamma" ? (v / 100).toFixed(2) : v + "%"; }
  function applyTune() {
    // 밑의 WAC 에도 같게 건다 — 고해상의 틈으로 비치는 WAC 가 따로 놀지 않게
    [cUnder, cBase].forEach(function (base) {
      base.brightness = tune.bright / 100;
      base.contrast = tune.contrast / 100;
      base.gamma = tune.gamma / 100;
      base.saturation = tune.sat / 100;
    });
    // 음영을 음영 위에 겹칠 까닭은 없다 — 배경이 LOLA 음영이면 끈다
    var shade = tune.shade && look.base !== "lola";
    cShade.show = shade;
    oShade.setVisible(shade);
    [oUnder, oBase].forEach(function (layer) {
      layer.updateStyleVariables({ exposure: tune.bright / 100 - 1, contrast: tune.contrast / 100 - 1,
                                   gamma: tune.gamma / 100, saturation: tune.sat / 100 - 1 });
    });
    TUNES.forEach(function (k) {
      $("tune-" + k).value = tune[k];
      $("tune-" + k + "-num").textContent = tuneText(k, tune[k]);
    });
    $("tune-shade").checked = tune.shade;
    var changed = TUNES.some(function (k) { return tune[k] !== TUNE_DEFAULT[k]; }) || tune.shade;
    $("tune-state").textContent = changed ? T("고침") : "";
    save("gsm.moon.tune", JSON.stringify(tune));
  }
  TUNES.forEach(function (k) {
    $("tune-" + k).addEventListener("input", function () { tune[k] = +this.value; applyTune(); });
  });
  $("tune-shade").addEventListener("change", function () { tune.shade = this.checked; applyTune(); });
  $("tune-reset").addEventListener("click", function () { tune = Object.assign({}, TUNE_DEFAULT); applyTune(); });
  document.querySelectorAll("#tune [data-preset]").forEach(function (b) {
    b.addEventListener("click", function () { tune = Object.assign({}, PRESETS[b.dataset.preset]); applyTune(); });
  });
  applyTune();

  // ── 지질 레이어 — 2D 처럼 목록에서 켜고, 켠 것은 카드로 쌓는다 ──
  //
  // 쌓는 차례는 구와 평면이 같다. 구는 배경(0 번) 위로 아래 것부터 `raiseToTop`, 평면은 `zIndex`
  function applyStack() {
    active.forEach(function (e) { ensureTrek(e.name); });
    Object.keys(cGeo).forEach(function (name) {
      var e = entryOf(name);
      cGeo[name].show = !!e;
      oGeo[name].setVisible(!!e);
      if (e) { cGeo[name].alpha = e.opacity; oGeo[name].setOpacity(e.opacity); }
    });
    // 구 — 영상 레이어만 차례가 있다(벡터 데이터 소스는 늘 영상 위다). 평면 — zIndex
    active.slice().reverse().forEach(function (e, i) {
      (cRaise[e.name] || []).forEach(function (l) { viewer.imageryLayers.raiseToTop(l); });
      // 평면도 구처럼 벡터(착륙 지점·동선)는 영상 레이어 위에 둔다 — 사진을 나중에 켜도 점을 덮지 않게
      oGeo[e.name].setZIndex((LAYER[e.name].kind === "vector" ? 50 : 0) + i + 1);
    });
    // 점묶음은 늘 지질 위다
    oPoints.setZIndex(100);
    syncLegend();
  }
  function addLayer(name) {
    if (isOn(name)) return;
    active.unshift({ name: name, opacity: /units$/.test(name) ? 0.6 : 1 });
    saveLayers(); applyStack(); renderActive(); renderCatalog();
  }
  function removeLayer(name) {
    active = active.filter(function (e) { return e.name !== name; });
    saveLayers(); applyStack(); renderActive(); renderCatalog();
  }
  function moveLayer(name, step) {
    var i = active.indexOf(entryOf(name)), j = i + step;
    if (i < 0 || j < 0 || j >= active.length) return;
    var e = active.splice(i, 1)[0];
    active.splice(j, 0, e);
    saveLayers(); applyStack(); renderActive();
  }
  function renderActive() {
    var host = $("active-list");
    $("count-layers").textContent = active.length;
    host.innerHTML = "";
    if (!active.length) {
      host.innerHTML = '<li class="empty">' + esc(T("아직 켠 레이어가 없다")) + "</li>";
      return;
    }
    active.forEach(function (e, index) {
      var li = document.createElement("li");
      var head = document.createElement("div");
      head.className = "active-head";
      var title = document.createElement("span");
      title.className = "active-title";
      title.textContent = T(LAYER[e.name].title);
      head.append(
        iconButton("↑", T("위로"), index === 0, function () { moveLayer(e.name, -1); }),
        iconButton("↓", T("아래로"), index === active.length - 1, function () { moveLayer(e.name, 1); }),
        title,
        iconButton("×", T("끈다"), false, function () { removeLayer(e.name); }));
      var foot = document.createElement("div");
      foot.className = "active-foot";
      var range = document.createElement("input");
      range.type = "range";
      range.min = 0; range.max = 100; range.value = Math.round(e.opacity * 100);
      range.setAttribute("aria-label", T("투명도"));
      var num = document.createElement("span");
      num.className = "opacity-num";
      num.textContent = range.value + "%";
      range.addEventListener("input", function () {
        e.opacity = range.value / 100;
        cGeo[e.name].alpha = e.opacity;
        oGeo[e.name].setOpacity(e.opacity);
        num.textContent = range.value + "%";
      });
      range.addEventListener("change", saveLayers);
      foot.append(range, num);
      var src = document.createElement("p");
      src.className = "active-src";
      src.textContent = LAYER[e.name].src || creditOf(e.name) || "";
      li.append(head, foot, src);
      host.appendChild(li);
    });
  }
  function renderCatalog() {
    var host = $("layer-catalog");
    host.innerHTML = "";
    CATALOG.forEach(function (g) {
      var details = document.createElement("details");
      details.className = "group";
      details.open = true;
      var summary = document.createElement("summary");
      summary.innerHTML = esc(T(g.group)) + ' <span class="count">' + g.layers.length + "</span>";
      details.appendChild(summary);
      g.layers.forEach(function (l) { details.appendChild(layerRow(l)); });
      host.appendChild(details);
    });
    renderTrek();
  }
  function layerRow(l) {
    var row = document.createElement("div");
    row.className = "layer-row";
    var box = document.createElement("input");
    box.type = "checkbox";
    box.id = "lyr-" + l.name;
    box.checked = isOn(l.name);
    box.addEventListener("change", function () { if (box.checked) addLayer(l.name); else removeLayer(l.name); });
    var label = document.createElement("label");
    label.htmlFor = box.id;
    label.textContent = T(l.title);
    if (l.kind === "trek" && l.en !== l.title) label.title = l.en;
    var from = l.src || creditOf(l.name);
    if (from) {                                        // 출처를 제목 밑에 — 켜기 전에도 무엇을 얹는지 보인다 (wetherilli 360)
      var src = document.createElement("small");
      src.className = "src";
      src.textContent = src.title = from;                // 잘려도 끝까지 읽게
      label.appendChild(src);
    }
    row.append(box, label);
    return row;
  }

  // ── NASA Trek 판 목록 (060) ──
  //
  // 레이어군마다 몸 전체를 덮는 판을 먼저 두고, 좁은 곳만 덮는 판은 그 밑의 묶음에 넣는다(달은 천 장 남짓이다).
  // 이름으로 거르고, "보는 자리를 덮는 것만" 이면 화면 가운데를 덮지 않는 좁은 판을 뺀다 — 그때는 움직일
  // 때마다 다시 거른다. 열어 둔 묶음은 다시 그려도 열어 둔다
  var trekOpen = {};
  function viewLL() {
    if (mode === "flat") return wrapLon(toLL(flat.getView().getCenter()));
    var c = cameraLL();
    return c ? [c.lon, c.lat] : null;
  }
  function covers(b, ll) { return ll[0] >= b[0] && ll[0] <= b[2] && ll[1] >= b[1] && ll[1] <= b[3]; }
  function trekGroup(key, title, count, open, more) {
    var details = document.createElement("details");
    details.className = more ? "group more" : "group";
    details.open = open;
    details.addEventListener("toggle", function () { trekOpen[key] = details.open; });
    var summary = document.createElement("summary");
    summary.innerHTML = esc(title) + ' <span class="count">' + count + "</span>";
    details.appendChild(summary);
    return details;
  }
  function renderTrek() {
    var host = $("trek-catalog");
    if (!host) return;
    var q = $("trek-q").value.trim().toLowerCase();
    var at = $("trek-here").checked ? viewLL() : null;
    var narrowing = !!(q || at);
    var total = 0, top = host.scrollTop;
    host.innerHTML = "";
    TREK_GROUPS.forEach(function (g) {
      var hit = g.layers.filter(function (l) {
        if (q && (l.title + " " + l.en + " " + l.src + " " + l.id).toLowerCase().indexOf(q) < 0) return false;
        return !(at && l.bbox && !covers(l.bbox, at));
      });
      if (!hit.length) return;
      total += hit.length;
      var details = trekGroup(g.group, g.group, hit.length, narrowing || !!trekOpen[g.group], false);
      var narrow = [];
      hit.forEach(function (l) { if (l.bbox) narrow.push(l); else details.appendChild(layerRow(l)); });
      if (narrow.length) {
        var key = g.group + "/narrow";
        var more = trekGroup(key, T("좁은 곳만 덮는 판"), narrow.length, narrowing || !!trekOpen[key], true);
        narrow.forEach(function (l) { more.appendChild(layerRow(l)); });
        details.appendChild(more);
      }
      host.appendChild(details);
    });
    $("count-trek").textContent = total;
    host.scrollTop = top;                 // 켜고 끌 때마다 다시 그리므로 — 보던 자리를 지킨다
    if (!total) {
      host.innerHTML = '<p class="empty">' + esc(TREK_GROUPS.length ? T("맞는 판이 없다") : T("판 목록이 아직 없다")) + "</p>";
    }
  }
  $("trek-q").addEventListener("input", renderTrek);
  $("trek-here").addEventListener("change", renderTrek);
  viewer.camera.moveEnd.addEventListener(function () { if ($("trek-here").checked) renderTrek(); });
  flat.on("moveend", function () { if ($("trek-here").checked) renderTrek(); });

  // 지형 (구에서만)
  var terrainBox = $("moon-terrain"), exag = $("moon-exag");
  terrainBox.checked = look.terrain;
  exag.disabled = !look.terrain;
  terrainBox.addEventListener("change", function () {
    look.terrain = terrainBox.checked;
    scene.terrainProvider = look.terrain ? lolaTerrain : flatTerrain;
    exag.disabled = !look.terrain;
    save("gsm.moon.terrain", look.terrain ? "on" : "off");
  });
  exag.value = look.exag;
  function applyExag() {
    look.exag = +exag.value;
    scene.verticalExaggeration = look.exag / 10;
    $("moon-exag-num").textContent = "×" + (look.exag / 10).toFixed(1);
    save("gsm.moon.exag", look.exag);
  }
  exag.addEventListener("input", applyExag);
  applyExag();

  // ══ 좌표 ══════════════════════════════════════════════════════════
  function fmt(ll) {
    return T("달 위도 {lat}° · 경도 {lon}°", { lat: ll[1].toFixed(4), lon: ll[0].toFixed(4) });
  }
  function globeLL(position) {
    var ray = viewer.camera.getPickRay(position);
    var cartesian = ray && scene.globe.pick(ray, scene);
    if (!cartesian) cartesian = viewer.camera.pickEllipsoid(position, MOON);
    if (!cartesian) return null;
    var c = MOON.cartesianToCartographic(cartesian);
    return [Cesium.Math.toDegrees(c.longitude), Cesium.Math.toDegrees(c.latitude)];
  }
  function wrapLon(ll) {
    var lon = ((ll[0] + 180) % 360 + 360) % 360 - 180;
    return [lon, ll[1]];
  }
  var readout = $("readout");
  var handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
  handler.setInputAction(function (movement) {
    var ll = globeLL(movement.endPosition);
    readout.textContent = ll ? fmt(ll) : "";
  }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
  flat.on("pointermove", function (e) {
    if (e.dragging) return;
    readout.textContent = fmt(wrapLon(toLL(e.coordinate)));
  });

  // ══ 팝업 — 누른 자리에 뜬다 ═══════════════════════════════════════
  var popup = $("popup"), popupBody = $("popup-body");
  var asked = 0;
  function closePopup() { popup.classList.remove("on"); ++asked; markAt(null); }
  $("popup-close").addEventListener("click", closePopup);
  function showPopup(html, pixel) {
    popupBody.innerHTML = html;
    popup.classList.add("on");
    var w = wrap.clientWidth, h = wrap.clientHeight;
    var pw = popup.offsetWidth, ph = popup.offsetHeight;
    var left = Math.min(Math.max(8, pixel[0] + 14), w - pw - 8);
    var top = Math.min(Math.max(8, pixel[1] - ph / 2), h - ph - 64);
    // 오른쪽 위 손잡이(도구·자세 두 묶음)를 덮지 않게 그 왼쪽으로 비킨다 — 팝업이 위라 덮으면 못 누른다 (041)
    var bar = $("toolbar");
    if (top < bar.offsetTop + bar.offsetHeight + 8 && left + pw > bar.offsetLeft - 8) {
      left = Math.max(8, Math.min(pixel[0] - pw - 14, bar.offsetLeft - pw - 8));
    }
    popup.style.left = left + "px";
    popup.style.top = Math.max(8, top) + "px";
  }
  // 첫 줄은 누른 자리의 달 위경도 — 2D 처럼 누르면 "위도, 경도" 로 복사한다(아래 `popupBody` 의 click, 041)
  function coordHead(ll) {
    var lat = ll[1].toFixed(6), lon = ll[0].toFixed(6);
    return '<button type="button" class="popup-coord" title="' + esc(T("눌러서 복사한다")) + '" data-copy="' +
           lat + ", " + lon + '"><span class="k">' + esc(T("달 위도")) + '</span><span class="v">' + lat +
           '</span><span class="k">' + esc(T("달 경도")) + '</span><span class="v">' + lon +
           '</span><span class="copy">' + esc(T("복사")) + "</span></button>";
  }
  // 켠 레이어 가운데 `key`(속성·범례의 갈래)가 있는 것을 위에서부터, 같은 갈래는 한 번만 — 통합 지질도와
  // Kaguya TC 지질도(060)를 함께 켜도 같은 표·범례가 두 번 서지 않는다
  function onceBy(layers, key) {
    var seen = {};
    return layers.filter(function (l) {
      if (!l[key] || seen[l[key]]) return false;
      return (seen[l[key]] = true);
    });
  }
  // 켠 레이어 가운데 읽을 수 있는 것(통합·원도)을 위에서부터 다 묻는다 — 둘을 켜 두면 견줘 읽는다
  function askUnit(ll, pixel) {
    markAt(ll);
    var head = coordHead(ll);
    var layers = onceBy(active.map(function (e) { return LAYER[e.name]; }), "info");
    if (!layers.length) { showPopup(head, pixel); return; }
    var mine = ++asked;
    showPopup(head + '<p class="none">' + esc(T("읽는 중")) + "</p>", pixel);
    Promise.all(layers.map(function (l) {
      var at = "?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4);
      // Trek 의 MapServer 판 (060) — 점·선이 잡히게 지금 보는 줌을 함께 보낸다. 찾은 것마다 한 표
      if (l.info === "trek") {
        var z = Math.round(Math.log(180 * M_PER_DEG / 256 / Math.max(1, heightToRes(hereHeight()))) / Math.LN2);
        return fetch(BASE + "trek/moon/map/" + encodeURIComponent(l.id) + "/info/" + at + "&z=" + Math.max(0, z))
          .then(function (r) { return r.json(); }).then(function (data) {
            if (data.error) return data;
            var hits = data.hits || [];
            return { rows: [].concat.apply([], hits.map(function (h) { return h.rows; })),
                     note: T("여기에는 속성이 없다") };
          }).catch(function () { return { error: true }; });
      }
      if (l.info.indexOf("value:") === 0) {
        return fetch(BASE + "moon/values/" + at + "&key=" + l.info.slice(6))
          .then(function (r) { return r.json(); }).then(function (data) {
            if (data.error) return data;
            return { rows: data.rows, note: T("여기에는 값이 없다") };
          }).catch(function () { return { error: true }; });
      }
      var url = BASE + "moon/info/" + at + (l.info === "units" ? "" : "&layer=" + l.info);
      return fetch(url).then(function (r) { return r.json(); }).catch(function () { return { error: true }; });
    })).then(function (all) {
      if (mine !== asked) return;
      var html = head;
      all.forEach(function (data, i) {
        html += "<h3>" + esc(T(layers[i].title)) + "</h3>";
        if (data.error) { html += '<p class="none">' + esc(T("속성을 받지 못했다")) + "</p>"; return; }
        if (!data.rows || !data.rows.length) {
          html += '<p class="none">' + esc(data.note || T("여기에는 지질 단위가 없다")) + "</p>";
          return;
        }
        var sw = layers[i].info === "units" ? swatches[data.unit] : null;
        var chip = sw ? '<img class="swatch-img" src="' + sw + '" alt="">'
                 : data.color ? '<span class="swatch-img" style="display:inline-block;background:' + esc(data.color) + '"></span>' : "";
        var unitRow = data.rows.map(function (r) { return r[1]; }).indexOf(data.unit);
        html += "<table>" + data.rows.map(function (row, k) {
          return "<tr><th>" + esc(row[0]) + "</th><td>" + (k === unitRow ? chip : "") + esc(row[1]) + "</td></tr>";
        }).join("") + "</table>";
      });
      showPopup(html, pixel);
    });
  }
  // 점묶음의 점·모양 — 2D 의 팝업과 같이 딸린 속성을 받은 차례 그대로
  function showFeature(props, ps, ll, pixel) {
    ++asked;
    markAt(ll);
    var title = props["이름표"] || ps.name || "";
    var rows = Object.keys(props).filter(function (k) {
      return k !== "이름표" && k.charAt(0) !== "_" && props[k] !== "" && props[k] != null && typeof props[k] !== "object";
    });
    showPopup((ll ? coordHead(ll) : "") + "<h3>" + esc(title) + '</h3><p class="from"><span class="swatch" style="background:' +
              esc(ps.color) + '"></span>' + esc(ps.name) + "</p>" +
              (rows.length ? "<table>" + rows.map(function (k) {
                return "<tr><th>" + esc(T(k)) + "</th><td>" + esc(props[k]) + "</td></tr>";
              }).join("") + "</table>" : ""), pixel);
  }
  handler.setInputAction(function (click) {
    if (tool) { drawClick(globeLL(click.position), click.position); return; }     // 도구가 켜져 있으면 도구가 받는다 (041)
    var picked = scene.pick(click.position);
    var entity = picked && picked.id;
    var px = [click.position.x, click.position.y];
    if (entity && entity.gsmProps) {
      var pos = entity.position && entity.position.getValue(Cesium.JulianDate.now());
      var ll = null;
      if (pos) { var c = MOON.cartesianToCartographic(pos); ll = [Cesium.Math.toDegrees(c.longitude), Cesium.Math.toDegrees(c.latitude)]; }
      showFeature(entity.gsmProps, entity.gsmSet, ll, px);
      return;
    }
    var at = globeLL(click.position);
    if (at) askUnit(at, px);
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
  flat.on("singleclick", function (e) {
    // 도구가 켜져 있으면 도구가 받는다. 선·면·범위는 평면의 Draw·DragBox 가 따로 받는다 (041)
    if (tool) { if (tool === "point") addTemp(toLL(e.coordinate)); return; }
    var hit = flat.forEachFeatureAtPixel(e.pixel, function (f, layer) { return [f, layer]; }, { hitTolerance: 4 });
    if (hit && hit[1] && hit[1].get("gsmSet")) {
      var g = hit[0].getGeometry();
      var ll = g && g.getType() === "Point" ? wrapLon(toLL(g.getCoordinates())) : null;
      var props = Object.assign({}, hit[0].getProperties());
      delete props.geometry;
      showFeature(props, hit[1].get("gsmSet"), ll, e.pixel);
      return;
    }
    askUnit(wrapLon(toLL(e.coordinate)), e.pixel);
  });

  // ══ 범례 — 오른쪽 아래, 펼쳐 둔다 ═══════════════════════════════
  //
  // 켠 레이어마다 칸 하나 — 통합 지질도는 시대별 49 단위, 원도는 29 갈래와 구조선. 켠 차례(위가 앞)대로
  var swatches = {};
  var legends = {};                // 갈래 → 그린 HTML (한 번 받는다)
  var dock = $("legend-dock");
  // 휴대폰에서는 범례가 구를 덮어 접은 채로 연다 (wetherilli 128)
  dock.open = saved("gsm.moon.legend", window.matchMedia("(max-width: 760px)").matches ? "closed" : "open") !== "closed";
  dock.addEventListener("toggle", function () { save("gsm.moon.legend", dock.open ? "open" : "closed"); });
  // 달의 지질시대 — 젊은 것부터. 서버가 한국어판이면 한국어로, 영어판이면 영어로 준다(`trek.AGES_KO`)
  var AGE_ORDER = [["코페르니쿠스기", "Copernican"], ["에라토스테네스기", "Eratosthenian"], ["임브리움기", "Imbrian"],
                   ["넥타리스기", "Nectarian"], ["선넥타리스기", "Pre-Nectarian"]];
  // 두 시대에 걸친 단위(SPA 지질도의 "넥타리스기–선넥타리스기")는 젊은 쪽 시대 바로 밑에 선다
  function ageRank(age) {
    var parts = String(age).split("–");
    for (var i = 0; i < AGE_ORDER.length; i++) {
      if (AGE_ORDER[i].indexOf(parts[0]) >= 0) return parts.length > 1 ? i + 0.5 : i;
    }
    return AGE_ORDER.length;
  }
  function legendHtml(kind) {
    if (legends[kind] !== undefined) return Promise.resolve(legends[kind]);
    // Trek 판 (060) — 상류가 그려 둔 범례 그림 한 장. 없는 판도 있어 받아 보고 정한다. 글자가 검어서 흰 바탕에 싣는다
    if (/^trek:/.test(kind) && LAYER[kind] && LAYER[kind].ms) {
      return fetch(BASE + "trek/moon/map/" + encodeURIComponent(LAYER[kind].id) + "/legend/")
        .then(function (r) { return r.json(); }).then(function (data) {
          return (legends[kind] = (data.items || []).map(function (item) {
            return '<li><img src="' + esc(item.image) + '" alt="">' + esc(item.label) + "</li>";
          }).join("") || '<li class="empty">' + esc(T("범례가 없다")) + "</li>");
        }).catch(function () { return '<li class="empty">' + esc(T("범례가 없다")) + "</li>"; });
    }
    if (/^trek:/.test(kind)) {
      return new Promise(function (resolve) {
        var img = new Image(), src = (TREK_DATA.legend || "") + encodeURIComponent(kind.slice(5));
        img.onload = function () {
          resolve(legends[kind] = '<li><img class="trek-legend" src="' + esc(src) + '" alt=""></li>');
        };
        img.onerror = function () { resolve(legends[kind] = '<li class="empty">' + esc(T("범례가 없다")) + "</li>"); };
        img.src = src;
      });
    }
    if (kind === "landings") {
      legends[kind] = LANDING_ORDER.map(function (k) {
        var st = LANDING_STYLE[k];
        return '<li><span class="chip dot" style="background:' + st.color + '"></span>' + esc(T(st.label)) + "</li>";
      }).join("");
      return Promise.resolve(legends[kind]);
    }
    // 원도의 단위·구조선은 한 번에 온다(`?layer=orig`)
    var url = BASE + "moon/legend/" + (kind === "units" ? "" : kind === "spa" ? "?layer=spa" : "?layer=orig");
    return fetch(url).then(function (r) { return r.json(); }).then(function (data) {
      var html = "";
      if (kind === "units" || kind === "spa") {
        // 상류의 범례 차례는 시대가 섞여 있다(에라토스테네스기 바다 `Em` 이 임브리움기 크레이터 뒤에 온다).
        // 시대마다 상자 하나로 모으고, 상자는 층서표처럼 젊은 것이 위다(`AGE_ORDER`). 표에 없는 시대는
        // 처음 나온 차례대로 그 밑에 선다 (044). SPA 지질도는 그림 대신 색을 준다 (wetherilli 081)
        var ages = [], byAge = {};
        (data.items || []).forEach(function (item) {
          if (item.unit) swatches[item.unit] = item.image;
          var age = item.age || "";
          if (!byAge[age]) { byAge[age] = []; ages.push(age); }
          byAge[age].push(item);
        });
        ages.sort(function (a, b) { return ageRank(a) - ageRank(b); });   // sort 는 안정이라 같은 순위는 나온 차례
        ages.forEach(function (age) {
          html += '<li class="age-box"><div class="age-head">' + esc(age || T("시대 모름")) +
                  '<span class="age-n">' + byAge[age].length + "</span></div><ul>";
          byAge[age].forEach(function (item) {
            html += "<li>" + (item.image ? '<img src="' + esc(item.image) + '" alt="">'
                    : '<span class="chip" style="background:' + esc(item.color) + '"></span>') + esc(item.label) + "</li>";
          });
          html += "</ul></li>";
        });
      } else if (kind === "orig") {
        (data.units || []).forEach(function (c) {
          html += '<li><span class="chip" style="background:' + esc(c.color) + '"></span>' + esc(c.label) + "</li>";
        });
      } else {
        (data.lines || []).forEach(function (c) {
          html += '<li><span class="chip line' + (c.dash ? " dash" : "") + '" style="border-color:' + esc(c.color) +
                  '"></span>' + esc(c.label) + "</li>";
        });
      }
      legends[kind] = html;
      return html;
    }).catch(function () { return '<li class="empty">' + esc(T("범례를 받지 못했다")) + "</li>"; });
  }
  var legendAsked = 0;
  function syncLegend() {
    var layers = onceBy(active.map(function (e) { return LAYER[e.name]; }), "legend");
    dock.hidden = !layers.length;
    if (!layers.length) return;
    var mine = ++legendAsked;
    Promise.all(layers.map(function (l) { return legendHtml(l.legend); })).then(function (parts) {
      if (mine !== legendAsked) return;
      $("legend-list").innerHTML = parts.map(function (html, i) {
        var head = parts.length > 1 ? '<li class="layer">' + esc(T(layers[i].title)) + "</li>" : "";
        return head + html;
      }).join("");
      $("legend-sub").textContent = layers.length === 1 ? T(layers[0].title) : "";
    });
  }
  // 팝업의 색 조각이 쓰므로 통합판 범례는 처음에 받아 둔다
  legendHtml("units");

  // ══ 내 자료 — 달 점묶음 (037) ═════════════════════════════════════
  //
  // 지구의 점묶음과 같은 틀(`PointSet`)이고 `body: "moon"` 만 다르다. 구에는 Cesium 의 점·선·면으로,
  // 평면에는 OpenLayers 의 벡터 레이어로 같은 GeoJSON 을 그린다
  var pointsets = JSON.parse(($("pointset-data") || {}).textContent || "[]");
  var cSets = {}, oSets = {}, extents = {};
  var PS_OFF = "gsm.moon.pointsets.off";
  function offList() {
    try { return JSON.parse(saved(PS_OFF, "[]")) || []; } catch (e) { return []; }
  }
  function setOff(id, off) {
    var list = offList().filter(function (x) { return x !== id; });
    if (off) list.push(id);
    save(PS_OFF, JSON.stringify(list));
  }
  function csrf() {
    var input = document.querySelector("#upload-form [name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }
  function post(url, body) {
    return fetch(url, { method: "POST", headers: { "X-CSRFToken": csrf() }, body: body || new FormData() })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (!r.ok) throw new Error(d.error || String(r.status));
          return d;
        });
      });
  }
  function countText(ps) {
    var bits = [T("{n}점", { n: ps.count || 0 })];
    if (ps.lines) bits.push(T("선 {n}", { n: ps.lines }));
    if (ps.polygons) bits.push(T("면 {n}", { n: ps.polygons }));
    if (!ps.count && (ps.lines || ps.polygons)) bits.shift();
    if (ps.elevated) bits.push(T("고도 {n}", { n: ps.elevated }));
    return bits.join(" · ");
  }

  // 구 — 점·이름표를 지형에 묻히지 않게 깊이 검사를 끄되, **가까울 때만**이다. 끝없이 끄면 뒷면의
  // 점(창어 4 호)이 달을 뚫고 앞면에 비친다. 1 500 km 는 달 반지름보다 짧다
  var NO_DEPTH = 1500000;
  function ringPositions(ring) {
    var flatArr = [];
    ring.forEach(function (c) { flatArr.push(c[0], c[1]); });
    return Cesium.Cartesian3.fromDegreesArray(flatArr, MOON);
  }
  function addEntity(source, ps, feature) {
    var g = feature.geometry || {}, props = feature.properties || {};
    var color = Cesium.Color.fromCssColorString(ps.color || "#e4572e");
    var label = props["이름표"] || "";
    function add(opts) {
      var e = source.entities.add(opts);
      e.gsmProps = props;
      e.gsmSet = ps;
      return e;
    }
    if (g.type === "Point") {
      add({
        position: Cesium.Cartesian3.fromDegrees(g.coordinates[0], g.coordinates[1], 0, MOON),
        point: { pixelSize: 8, color: color, outlineColor: Cesium.Color.BLACK, outlineWidth: 1.5,
                 heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: NO_DEPTH },
        // 이름표는 가까이 가야 뜬다 — 멀리서는 수천 개가 겹친다
        label: label ? { text: label, font: "12px system-ui, sans-serif", fillColor: Cesium.Color.WHITE,
                         outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
                         style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(0, -14),
                         heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                         distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 400000),
                         disableDepthTestDistance: NO_DEPTH } : undefined,
      });
    } else if (g.type === "LineString" || g.type === "MultiLineString") {
      (g.type === "LineString" ? [g.coordinates] : g.coordinates).forEach(function (line) {
        add({ polyline: { positions: ringPositions(line), width: 2.5, clampToGround: true, material: color } });
      });
    } else if (g.type === "Polygon" || g.type === "MultiPolygon") {
      (g.type === "Polygon" ? [g.coordinates] : g.coordinates).forEach(function (rings) {
        add({ polygon: { hierarchy: new Cesium.PolygonHierarchy(ringPositions(rings[0]),
                           rings.slice(1).map(function (r) { return new Cesium.PolygonHierarchy(ringPositions(r)); })),
                         material: color.withAlpha(0.25) } });
        add({ polyline: { positions: ringPositions(rings[0]), width: 2, clampToGround: true, material: color } });
      });
    }
  }
  // 평면 — 2D 의 점 모양과 같은 꼴
  function flatStyle(ps) {
    var fill = new ol.style.Fill({ color: ps.color }), edge = new ol.style.Stroke({ color: "#000", width: 1.5 });
    var point = new ol.style.Circle({ radius: 5, fill: fill, stroke: edge });
    var line = new ol.style.Stroke({ color: ps.color, width: 2.5 });
    var area = new ol.style.Fill({ color: ps.color + "40" });
    return function (feature, resolution) {
      var label = feature.get("이름표");
      var text = label && resolution < 400 ? new ol.style.Text({
        text: String(label), offsetY: -14, font: "12px system-ui, sans-serif",
        fill: new ol.style.Fill({ color: "#fff" }), stroke: new ol.style.Stroke({ color: "#000", width: 3 }) }) : undefined;
      var type = feature.getGeometry().getType();
      if (/Point/.test(type)) return new ol.style.Style({ image: point, text: text });
      if (/Line/.test(type)) return new ol.style.Style({ stroke: line, text: text });
      return new ol.style.Style({ stroke: line, fill: area, text: text });
    };
  }
  function extentOf(features) {
    var w = 180, s = 90, e = -180, n = -90;
    function walk(c) {
      if (typeof c[0] === "number") {
        w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]);
      } else c.forEach(walk);
    }
    features.forEach(function (f) { if (f.geometry) walk(f.geometry.coordinates); });
    return w <= e ? [w, s, e, n] : null;
  }
  var loading = {};
  function loadSet(ps) {
    if (loading[ps.id]) return loading[ps.id];
    loading[ps.id] = fetch(BASE + "pointsets/" + ps.id + "/geojson/").then(function (r) { return r.json(); }).then(function (data) {
      var feats = data.features || [];
      extents[ps.id] = extentOf(feats);
      var source = new Cesium.CustomDataSource("ps-" + ps.id);
      feats.forEach(function (f) { addEntity(source, ps, f); });
      source.show = ps.visible;
      viewer.dataSources.add(source);
      cSets[ps.id] = source;
      var layer = new ol.layer.Vector({
        source: new ol.source.Vector({ features: new ol.format.GeoJSON().readFeatures(data,
                                         { dataProjection: LL, featureProjection: proj }) }),
        style: flatStyle(ps), declutter: true, visible: ps.visible,
      });
      layer.set("gsmSet", ps);
      oPoints.getLayers().push(layer);
      oSets[ps.id] = layer;
    });
    return loading[ps.id];
  }
  function dropSet(id) {
    if (cSets[id]) viewer.dataSources.remove(cSets[id], true);
    if (oSets[id]) oPoints.getLayers().remove(oSets[id]);
    delete cSets[id]; delete oSets[id]; delete loading[id]; delete extents[id];
  }
  function showSet(ps) {
    if (cSets[ps.id]) cSets[ps.id].show = ps.visible;
    if (oSets[ps.id]) oSets[ps.id].setVisible(ps.visible);
  }
  function goTo(lon, lat, h) {
    closePopup();
    if (mode === "flat" && h < TO_GLOBE_H) {
      useProj(projFor(lat, proj), [lon, lat], heightToRes(h));
      flat.getView().animate({ center: fromLL([lon, lat]), resolution: heightToRes(h) / groundScale(proj, lat),
                               duration: 600 });
    } else {
      if (mode === "flat") setMode("globe");
      flyGlobe(lon, lat, h, 1.5);
    }
  }
  function flyToSet(ps) {
    loadSet(ps).then(function () {
      var x = extents[ps.id];
      if (!x) return;
      var span = Math.max(x[2] - x[0], x[3] - x[1]);
      var h = Math.max(30000, span * M_PER_DEG * 1.4);
      goTo((x[0] + x[2]) / 2, (x[1] + x[3]) / 2, h);
    });
  }
  function iconButton(text, title, disabled, onClick) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "iconbtn";
    b.textContent = text;
    b.title = title;
    b.setAttribute("aria-label", title);
    b.disabled = !!disabled;
    b.addEventListener("click", onClick);
    return b;
  }
  function renderSets() {
    var host = $("pointset-list");
    $("count-points").textContent = pointsets.length;
    host.innerHTML = "";
    if (!pointsets.length) {
      host.innerHTML = '<li class="empty">' + T("왼쪽 위 <b>불러오기</b> 탭에서 올린다") + "</li>";
      return;
    }
    var off = offList();
    pointsets.forEach(function (ps) {
      ps.visible = off.indexOf(ps.id) < 0;
      loadSet(ps);
      showSet(ps);
      var li = document.createElement("li");
      var box = document.createElement("input");
      box.type = "checkbox";
      box.checked = ps.visible;
      box.setAttribute("aria-label", ps.name);
      box.addEventListener("change", function () {
        ps.visible = box.checked;
        setOff(ps.id, !ps.visible);
        showSet(ps);
      });
      var swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = ps.color;
      var text = document.createElement("span");
      text.className = "ps-text";
      text.innerHTML = '<span class="ps-name">' + esc(ps.name) + '</span><span class="ps-count">' +
                       esc(countText(ps)) + "</span>";
      var zoom = iconButton("⊙", T("이 자료로 범위를 맞춘다"), false, function () { flyToSet(ps); });
      var elev = iconButton("⛰", T("표고 채우기 — LOLA 표고에서 점마다 높이를 읽는다 (달 기준구 1737.4 km)"),
                            !ps.count, function () {
        elev.disabled = true;
        post(BASE + "pointsets/" + ps.id + "/elevation/").then(function (d) {
          if (d.pointset) Object.assign(ps, d.pointset);
          alert(T("{n}점 채움 · {m}점은 자료 밖", { n: d.filled, m: d.missed }));
          dropSet(ps.id);
          renderSets();
        }).catch(function (e) {
          elev.disabled = false;
          alert((e && e.message) || T("표고를 받지 못했다"));
        });
      });
      var down = iconButton("⤓", T("GeoJSON 으로 내려받는다"), false, function () {
        location.href = BASE + "pointsets/" + ps.id + "/geojson/?download=1";
      });
      // CSV — 엑셀로 연다. 우리 파일에서 읽는 값(지질 단위·지각 두께·가까운 화석 산지)을 열로 붙인다 (wetherilli 190).
      // 값을 읽는 점은 서버의 `pointvalues.LIMIT`(2 000)까지 — 넘으면 값 없이 받는다고 묻는다
      var csv = iconButton("CSV", T("CSV 로 내려받는다 — 우리 파일에서 읽는 값을 열로 붙인다"), !ps.count, function () {
        var extras = "all";
        if ((ps.count || 0) > 2000) {
          if (!confirm(T("점이 {n} 개라 붙일 값은 빼고 내려받는다 — 값은 {limit} 개까지 읽는다.", { n: ps.count, limit: 2000 }))) return;
          extras = "none";
        }
        location.href = BASE + "pointsets/" + ps.id + "/csv/?extras=" + extras;
      });
      csv.classList.add("wide");
      var del = iconButton("×", T("지운다"), false, function () {
        if (!confirm(T("'{name}' 을 지운다.", { name: ps.name }))) return;
        post(BASE + "pointsets/" + ps.id + "/delete/").then(function () {
          dropSet(ps.id);
          pointsets = pointsets.filter(function (x) { return x.id !== ps.id; });
          renderSets();
        }).catch(function (e) { alert((e && e.message) || ""); });
      });
      li.append(box, swatch, text, zoom, elev, down, csv, del);
      host.appendChild(li);
    });
  }
  renderSets();
  renderCatalog();
  renderActive();
  applyStack();

  // 올리기 — 2D 의 불러오기와 같은 꼴. 몸만 달로 적는다
  var form = $("upload-form"), fileInput = $("upload-file"), msgBox = $("upload-msg");
  var PALETTE = ["#f2c14e", "#e4572e", "#4ea5d9", "#7bc47f", "#c879ff", "#ff8fab"];
  $("upload-color").value = PALETTE[pointsets.length % PALETTE.length];
  fileInput.addEventListener("change", function () {
    var label = form.querySelector(".filebox");
    label.classList.toggle("has", !!fileInput.files.length);
    label.querySelector("span").textContent = fileInput.files.length ? fileInput.files[0].name : T("CSV · GeoJSON 고르기");
  });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!fileInput.files.length) return;
    var data = new FormData(form);
    data.set("body", "moon");
    msgBox.className = "msg";
    msgBox.textContent = T("올리는 중");
    post(BASE + "pointsets/upload/", data).then(function (d) {
      pointsets.unshift(d.pointset);
      setOff(d.pointset.id, false);
      renderSets();
      flyToSet(d.pointset);
      form.reset();
      fileInput.dispatchEvent(new Event("change"));
      $("upload-color").value = PALETTE[pointsets.length % PALETTE.length];
      msgBox.className = "msg good";
      msgBox.textContent = [T("{n}점을 올렸다", { n: d.pointset.count })].concat(d.notes || []).join(" ");
    }).catch(function (err) {
      msgBox.className = "msg bad";
      msgBox.textContent = (err && err.message) || T("올리지 못했다");
    });
  });

  // ══ 좌표·지명으로 이동 — 좌표 막대 ════════════════════════════════
  var gotoForm = $("goto-form"), gotoInput = $("goto-input"), results = $("search-results");
  var found = [], picked = -1, findTimer = null, findAsked = 0;
  function parseLatLon(text) {
    var m = /^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/.exec(text);
    if (!m) return null;
    var lat = +m[1], lon = +m[2];
    return Math.abs(lat) <= 90 && Math.abs(lon) <= 360 ? { lat: lat, lon: lon > 180 ? lon - 360 : lon } : null;
  }
  function renderFound() {
    if (!found.length) {
      results.innerHTML = '<li class="note">' + esc(T("찾은 것이 없다")) + "</li>";
    } else {
      results.innerHTML = found.map(function (p, i) {
        return '<li data-i="' + i + '"' + (i === picked ? ' class="on"' : "") + '><span class="kind">' + esc(p.kind) +
               '</span><span class="title">' + esc(p.name) + '</span><span class="sub">' +
               p.lat.toFixed(3) + ", " + p.lon.toFixed(3) + "</span></li>";
      }).join("") + '<li class="note src">IAU Gazetteer of Planetary Nomenclature · NASA Moon Trek</li>';
    }
    results.hidden = false;
    results.querySelectorAll("li[data-i]").forEach(function (li) {
      li.addEventListener("mousedown", function (e) { e.preventDefault(); choose(found[+li.dataset.i]); });
    });
  }
  function choose(place) {
    results.hidden = true;
    gotoInput.value = place.name;
    // 착륙지는 가까이, 크레이터·바다는 조금 멀리
    goTo(place.lon, place.lat, /Landing|Impact/.test(place.kind) ? 40000 : 200000);
  }
  gotoInput.addEventListener("input", function () {
    clearTimeout(findTimer);
    var q = gotoInput.value.trim();
    if (!q || parseLatLon(q)) { results.hidden = true; return; }
    findTimer = setTimeout(function () {
      var mine = ++findAsked;
      fetch(BASE + "moon/places/?q=" + encodeURIComponent(q)).then(function (r) { return r.json(); }).then(function (data) {
        if (mine !== findAsked) return;
        found = data.results || [];
        picked = found.length ? 0 : -1;
        renderFound();
      });
    }, 200);
  });
  gotoInput.addEventListener("keydown", function (e) {
    if (results.hidden || !found.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      picked = (picked + (e.key === "ArrowDown" ? 1 : found.length - 1)) % found.length;
      renderFound();
    } else if (e.key === "Escape") results.hidden = true;
  });
  gotoInput.addEventListener("blur", function () { setTimeout(function () { results.hidden = true; }, 150); });
  gotoForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var ll = parseLatLon(gotoInput.value);
    if (ll) { results.hidden = true; goTo(ll.lon, ll.lat, 60000); return; }
    if (found.length) choose(found[Math.max(0, picked)]);
  });

  // ══ 자전축 — 구에서 방향을 잡는 꼬챙이 (041·045) ═════════════════
  //
  // 구를 돌리고 기울이다 보면 어느 쪽이 북인지 놓친다. 달 고정 좌표의 Z 축이 곧 자전축이다.
  //
  // 041 은 달 밖으로 나온 두 토막만 그렸다 — 달 속은 가려져서, 돌려 보면 두 토막이 따로 노는 것처럼
  // 보였다(사람이 "달과 함께 눕지 않는다" 고 했다). 그래서 **달 속을 지나는 토막도 흐린 끊은 선으로
  // 비쳐 보이게** 했다(`depthFailMaterial`). 남극점 → 중심 → 북극점이 한 막대로 읽힌다. 중심에 점,
  // 극점(표면)에 점을 찍고, 밖으로 뻗은 끝에 이름을 적는다.
  //
  // **가까이 가면 치운다**(카메라 높이 1 200 km 밑). 달 속의 선이 땅 위로 비쳐 어지럽고, 그 거리에서는
  // 방위 바늘이 같은 일을 한다. 평면은 늘 북쪽이 위라 구에서만 보인다. 켜고 끈 것을 기억한다
  var AXIS_OUT = R * 1.45, AXIS_NEAR = 1200000;
  var axisOn = saved("gsm.moon.axis", "on") !== "off", axisFar = true;
  var WHITE_A = Cesium.Color.WHITE;
  var axisEntities = [
    viewer.entities.add({
      polyline: { positions: [new Cesium.Cartesian3(0, 0, -AXIS_OUT), new Cesium.Cartesian3(0, 0, AXIS_OUT)],
                  arcType: Cesium.ArcType.NONE, width: 2.5, material: WHITE_A.withAlpha(0.95),
                  depthFailMaterial: new Cesium.PolylineDashMaterialProperty({ color: WHITE_A.withAlpha(0.5), dashLength: 12 }) },
    }),
    // 중심 — 늘 비쳐 보인다
    viewer.entities.add({
      position: Cesium.Cartesian3.ZERO,
      point: { pixelSize: 6, color: WHITE_A.withAlpha(0.7), outlineColor: Cesium.Color.BLACK, outlineWidth: 1,
               disableDepthTestDistance: Number.POSITIVE_INFINITY },
    }),
  ].concat([[1, T("북극점")], [-1, T("남극점")]].reduce(function (all, end) {
    // 표면의 극점 — 뒤로 돌면 가려진다
    all.push(viewer.entities.add({
      position: new Cesium.Cartesian3(0, 0, end[0] * MOON.maximumRadius),
      point: { pixelSize: 8, color: WHITE_A, outlineColor: Cesium.Color.BLACK, outlineWidth: 2 },
    }));
    // 밖으로 뻗은 끝의 이름 — 극점이 뒤에 있어도 어느 쪽이 북인지 보인다
    all.push(viewer.entities.add({
      position: new Cesium.Cartesian3(0, 0, end[0] * AXIS_OUT),
      label: { text: end[1], font: "600 12px system-ui, sans-serif", fillColor: WHITE_A,
               outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
               verticalOrigin: end[0] > 0 ? Cesium.VerticalOrigin.BOTTOM : Cesium.VerticalOrigin.TOP,
               pixelOffset: new Cesium.Cartesian2(0, end[0] > 0 ? -4 : 4),
               disableDepthTestDistance: Number.POSITIVE_INFINITY },
    }));
    return all;
  }, []));
  function syncAxisNear() {
    var c = cameraLL(), far = !c || c.h > AXIS_NEAR;
    if (far !== axisFar) { axisFar = far; applyAxis(); }
  }
  function applyAxis() {
    axisEntities.forEach(function (e) { e.show = axisOn && axisFar; });
    $("tool-axis").classList.toggle("on", axisOn);
    $("tool-axis").setAttribute("aria-pressed", axisOn ? "true" : "false");
  }
  $("tool-axis").addEventListener("click", function () {
    axisOn = !axisOn;
    save("gsm.moon.axis", axisOn ? "on" : "off");
    applyAxis();
  });
  applyAxis();

  // ══ 누른 자리 — 속성을 읽은 곳에 표를 꽂는다 (041) ═══════════════
  //
  // 팝업만 뜨면 "어디를 읽었나" 가 모호하다 — 팝업은 누른 자리 옆으로 비켜 서고, 구를 돌리면 더
  // 멀어진다. 속이 빈 고리를 누른 자리에 꽂고, 팝업을 닫으면 뽑는다. 찍은 점(속이 찬 번호 점)과
  // 헷갈리지 않게 꼴을 달리했다
  var MARK_URL = (function () {
    var c = document.createElement("canvas"), s = 28;
    c.width = c.height = s;
    var g = c.getContext("2d");
    g.lineWidth = 5; g.strokeStyle = "rgba(0,0,0,.85)";
    g.beginPath(); g.arc(s / 2, s / 2, 9, 0, 2 * Math.PI); g.stroke();
    g.lineWidth = 2.5; g.strokeStyle = "#fff";
    g.beginPath(); g.arc(s / 2, s / 2, 9, 0, 2 * Math.PI); g.stroke();
    g.fillStyle = "#000"; g.beginPath(); g.arc(s / 2, s / 2, 3.2, 0, 2 * Math.PI); g.fill();
    g.fillStyle = "#fff"; g.beginPath(); g.arc(s / 2, s / 2, 2, 0, 2 * Math.PI); g.fill();
    return c.toDataURL();
  })();
  var markC = viewer.entities.add({
    show: false, position: Cesium.Cartesian3.fromDegrees(0, 0, 0, MOON),
    billboard: { image: MARK_URL, heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                 disableDepthTestDistance: NO_DEPTH },
  });
  var markO = new ol.Feature();
  markO.setStyle(new ol.style.Style({ image: new ol.style.Icon({ src: MARK_URL }) }));
  var oMark = new ol.layer.Vector({ source: new ol.source.Vector({ features: [markO] }), zIndex: 300 });
  flat.addLayer(oMark);
  function markAt(ll) {
    markC.show = !!ll;
    markO.setGeometry(ll ? new ol.geom.Point(fromLL(ll)) : undefined);
    if (ll) markC.position = Cesium.Cartesian3.fromDegrees(ll[0], ll[1], 0, MOON);
  }

  // ══ 도구 — 점 찍기·거리·넓이·범위 (041) ═══════════════════════════
  //
  // 2D 의 그리기 도구와 같은 넷이다. **찍고 잰 것은 달 경위도로 한 곳에 들고, 구와 평면이 저마다
  // 그린다** — 켠 레이어·점묶음처럼 넘어가도 그대로 남는다. 그리던 것(끝내지 않은 선)만 넘어갈 때
  // 버리므로, 그리는 동안은 저절로 넘어가지 않는다(`drawing()`).
  //
  // 길이·넓이는 **달의 구면**(반지름 1737.4 km)으로 잰다. 평면의 가로는 위도만큼 늘어나 있어 평면
  // 좌표로 재면 틀린다. 넓이는 OpenLayers 의 `ol.sphere.getArea` 와 같은 식이고 반지름만 달의 것이다
  var tool = "";                           // "" 이면 누르면 속성을 읽는다
  var temps = [], ranges = [], measured = null;
  var tempSeq = 0, rangeSeq = 0, lastMeasure = "";
  var sketch = [], hover = null, boxFrom = null, boxTo = null;   // 구에서 그리는 중인 것
  var flatSketching = false;

  function rad(d) { return d * Math.PI / 180; }
  function arc(a, b) {
    var dLat = rad(b[1] - a[1]), dLon = rad(b[0] - a[0]);
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  function lengthOf(coords) {
    var m = 0;
    for (var i = 1; i < coords.length; i++) m += arc(coords[i - 1], coords[i]);
    return m;
  }
  function areaOf(ring) {
    var sum = 0, n = ring.length;
    for (var i = 0; i < n; i++) {
      var p = ring[i], q = ring[(i + 1) % n];
      sum += rad(q[0] - p[0]) * (2 + Math.sin(rad(p[1])) + Math.sin(rad(q[1])));
    }
    return Math.abs(sum * R * R / 2);
  }
  // 경도를 앞 꼭짓점에서 180° 안쪽으로 — 날짜변경선(±180°)을 건너도 선이 달을 한 바퀴 돌지 않게
  function unwrap(prev, ll) {
    if (!prev) return ll;
    var lon = ll[0];
    while (lon - prev[0] > 180) lon -= 360;
    while (prev[0] - lon > 180) lon += 360;
    return [lon, ll[1]];
  }
  function asLength(m) { return m >= 1000 ? (m / 1000).toFixed(2) + " km" : m.toFixed(1) + " m"; }
  function asArea(m2) {
    return m2 >= 1e6 ? Math.round(m2 / 1e6).toLocaleString() + " km²" : Math.round(m2).toLocaleString() + " m²";
  }
  function pair(ll) { var w = wrapLon(ll); return w[1].toFixed(5) + ", " + w[0].toFixed(5); }
  function measureOf(m) {
    return m.kind === "area" ? { kind: T("넓이"), text: asArea(areaOf(m.coords)) }
                             : { kind: T("거리"), text: asLength(lengthOf(m.coords)) };
  }

  // 범위 — 경위도 네모. 등거리 원통에서 끈 네모가 곧 경위도 네모다. 구에서는 두 귀를 잇는다
  function rangeFacts(r) {
    var mid = (r.s + r.n) / 2;
    return {
      nw: [r.w, r.n], ne: [r.e, r.n], se: [r.e, r.s], sw: [r.w, r.s],
      center: [(r.w + r.e) / 2, mid],
      area: R * R * rad(r.e - r.w) * (Math.sin(rad(r.n)) - Math.sin(rad(r.s))),
      // 가로는 가운데 위도에서 잰다 — 위아래 변은 위도가 달라 길이가 다르다
      width: R * rad(r.e - r.w) * Math.cos(rad(mid)),
      height: R * rad(r.n - r.s),
    };
  }
  function rangeRows(f) {
    var rows = {};
    rows[T("북서")] = pair(f.nw); rows[T("북동")] = pair(f.ne);
    rows[T("남동")] = pair(f.se); rows[T("남서")] = pair(f.sw);
    rows[T("중앙")] = pair(f.center);
    rows[T("넓이")] = asArea(f.area);
    rows[T("가로 × 세로")] = asLength(f.width) + " × " + asLength(f.height);
    return rows;
  }
  function rangeText(r) {
    var rows = rangeRows(rangeFacts(r));
    return [T("범위 {n}", { n: r.no })].concat(Object.keys(rows).map(function (k) { return k + "\t" + rows[k]; })).join("\n");
  }
  function rangeOf(a, b) {
    b = unwrap(a, b);
    return { w: Math.min(a[0], b[0]), e: Math.max(a[0], b[0]), s: Math.min(a[1], b[1]), n: Math.max(a[1], b[1]) };
  }

  // ── 그리기 — 평면 ──
  var drawSource = new ol.source.Vector();
  var sketchSource = new ol.source.Vector();
  var LABEL_FONT = "600 12px ui-monospace, Menlo, monospace";
  function olLabel(text, offsetY) {
    return new ol.style.Text({ text: text, font: LABEL_FONT, offsetY: offsetY || 0, overflow: true,
                               fill: new ol.style.Fill({ color: "#fff" }), stroke: new ol.style.Stroke({ color: "#000", width: 4 }) });
  }
  function drawStyle(feature) {
    var kind = feature.get("kind"), label = feature.get("label");
    if (kind === "temp") {
      return new ol.style.Style({
        image: new ol.style.Circle({ radius: 5.5, fill: new ol.style.Fill({ color: "#fff" }),
                                     stroke: new ol.style.Stroke({ color: "#000", width: 2 }) }),
        text: olLabel(String(feature.get("no")), -14),
      });
    }
    if (kind === "range") {
      return new ol.style.Style({
        fill: new ol.style.Fill({ color: "rgba(255,255,255,.10)" }),
        stroke: new ol.style.Stroke({ color: "#e4e4e4", width: 2 }),
        text: olLabel(label),
      });
    }
    // 잰 선·면, 그리는 중인 것 — 검은 테두리 위에 흰 끊은 선
    return [
      new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(0,0,0,.7)", width: 4.5 }) }),
      new ol.style.Style({
        fill: new ol.style.Fill({ color: "rgba(255,255,255,.14)" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 2.5, lineDash: [7, 5] }),
        image: new ol.style.Circle({ radius: 4, fill: new ol.style.Fill({ color: "#fff" }),
                                     stroke: new ol.style.Stroke({ color: "#000", width: 1.5 }) }),
        text: label ? olLabel(label) : undefined,
      }),
    ];
  }
  var oDraw = new ol.layer.Vector({ source: drawSource, style: drawStyle, zIndex: 200 });
  flat.addLayer(oDraw);
  var flatInteraction = null;
  function eqc(coords) { return coords.map(fromLL); }

  function installFlat() {
    if (flatInteraction) { flat.removeInteraction(flatInteraction); flatInteraction = null; }
    flatSketching = false;
    sketchSource.clear();
    if (tool === "box") {
      flatInteraction = new ol.interaction.DragBox({ condition: ol.events.condition.always, className: "range-box" });
      flatInteraction.on("boxend", function () {
        var x = flatInteraction.getGeometry().getExtent();
        if (ol.extent.getWidth(x) === 0 || ol.extent.getHeight(x) === 0) return;
        addRange(rangeOf(toLL([x[0], x[1]]), toLL([x[2], x[3]])));
      });
    } else if (tool === "line" || tool === "area") {
      flatInteraction = new ol.interaction.Draw({
        source: sketchSource, type: tool === "line" ? "LineString" : "Polygon", style: drawStyle,
      });
      var kind = tool;
      flatInteraction.on("drawstart", function (evt) {
        flatSketching = true;
        var geometry = evt.feature.getGeometry();
        geometry.on("change", function () {
          var coords = kind === "area" ? geometry.getCoordinates()[0] : geometry.getCoordinates();
          var got = measureOf({ kind: kind, coords: coords.map(toLL) });
          evt.feature.set("label", got.text);
          showMeasure(got);
        });
      });
      flatInteraction.on("drawend", function (evt) {
        var g = evt.feature.getGeometry();
        var coords = (kind === "area" ? g.getCoordinates()[0].slice(0, -1) : g.getCoordinates()).map(toLL);
        flatSketching = false;
        setTimeout(function () { sketchSource.clear(); });    // Draw 가 제 것을 넣은 뒤에 치운다
        finishMeasure(kind, coords);
      });
      flatInteraction.on("drawabort", function () { flatSketching = false; });
    }
    if (flatInteraction) flat.addInteraction(flatInteraction);
  }

  // ── 그리기 — 구 ──
  var cDraw = new Cesium.CustomDataSource("draw");
  viewer.dataSources.add(cDraw);
  var WHITE = Cesium.Color.WHITE, BLACK = Cesium.Color.BLACK;
  function dash() { return new Cesium.PolylineDashMaterialProperty({ color: WHITE, gapColor: BLACK.withAlpha(0.55), dashLength: 14 }); }
  function cLabel(text, offsetY) {
    return { text: text, font: LABEL_FONT, fillColor: WHITE, outlineColor: BLACK, outlineWidth: 4,
             style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(0, offsetY || 0),
             heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: NO_DEPTH };
  }
  function positions(coords) { return ringPositions(coords); }
  function rangeRing(r) {
    // 위아래 변은 위선을 따라야 한다 — 대권으로 이으면 극 쪽으로 휜다. 촘촘히 찍어 위선을 따른다
    var out = [], steps = Math.max(2, Math.ceil((r.e - r.w) / 2));
    for (var i = 0; i <= steps; i++) out.push([r.w + (r.e - r.w) * i / steps, r.n]);
    for (i = steps; i >= 0; i--) out.push([r.w + (r.e - r.w) * i / steps, r.s]);
    out.push([r.w, r.n]);
    return out;
  }
  // 그리는 중인 선 — 누른 꼭짓점과 누르개 자리를 잇는다
  var sketchLine = cDraw.entities.add({
    polyline: { positions: new Cesium.CallbackProperty(function () {
      var pts = sketch.slice();
      if (hover && pts.length) pts.push(unwrap(pts[pts.length - 1], hover));
      if (tool === "area" && pts.length > 2) pts.push(pts[0]);
      return pts.length > 1 ? positions(pts) : [];
    }, false), width: 2.5, clampToGround: true, material: dash() },
  });
  var sketchBox = cDraw.entities.add({
    show: false,
    polyline: { positions: new Cesium.CallbackProperty(function () {
      return boxFrom && boxTo ? positions(rangeRing(rangeOf(boxFrom, boxTo))) : [];
    }, false), width: 2, clampToGround: true, material: WHITE },
  });
  var drawnEntities = [];
  function renderDrawn() {
    drawnEntities.forEach(function (e) { cDraw.entities.remove(e); });
    drawnEntities = [];
    drawSource.clear();
    function add(opts) { drawnEntities.push(cDraw.entities.add(opts)); }
    temps.forEach(function (t) {
      add({ position: Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0, MOON),
            point: { pixelSize: 10, color: WHITE, outlineColor: BLACK, outlineWidth: 2,
                     heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: NO_DEPTH },
            label: cLabel(String(t.no), -15) });
      drawSource.addFeature(new ol.Feature({ geometry: new ol.geom.Point(fromLL([t.lon, t.lat])), kind: "temp", no: t.no }));
    });
    ranges.forEach(function (r) {
      var ring = rangeRing(r), label = T("범위 {n}", { n: r.no });
      add({ polygon: { hierarchy: positions(ring), material: WHITE.withAlpha(0.1) } });
      add({ polyline: { positions: positions(ring), width: 2, clampToGround: true, material: Cesium.Color.fromCssColorString("#e4e4e4") } });
      add({ position: Cesium.Cartesian3.fromDegrees((r.w + r.e) / 2, (r.s + r.n) / 2, 0, MOON), label: cLabel(label) });
      drawSource.addFeature(new ol.Feature({ geometry: new ol.geom.Polygon([eqc(ring)]), kind: "range", label: label }));
    });
    if (measured) {
      var got = measureOf(measured), c = measured.coords;
      var line = measured.kind === "area" ? c.concat([c[0]]) : c;
      if (measured.kind === "area") add({ polygon: { hierarchy: positions(line), material: WHITE.withAlpha(0.14) } });
      add({ polyline: { positions: positions(line), width: 2.5, clampToGround: true, material: dash() } });
      var at = measured.kind === "area" ? centroid(c) : c[c.length - 1];
      add({ position: Cesium.Cartesian3.fromDegrees(at[0], at[1], 0, MOON), label: cLabel(got.text, measured.kind === "area" ? 0 : -16) });
      var geom = measured.kind === "area" ? new ol.geom.Polygon([eqc(line)]) : new ol.geom.LineString(eqc(line));
      drawSource.addFeature(new ol.Feature({ geometry: geom, kind: "measure", label: got.text }));
    }
    renderTemp();
  }
  function centroid(coords) {
    var x = 0, y = 0;
    coords.forEach(function (c) { x += c[0]; y += c[1]; });
    return [x / coords.length, y / coords.length];
  }

  // 구에서 누르고 끄는 것 — 읽는 처리기(LEFT_CLICK)와 따로 둔다
  var drawHandler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
  // Cesium 의 기본 두 번 누르기(개체를 따라가기)는 선을 끝내는 손과 부딪힌다
  viewer.screenSpaceEventHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
  drawHandler.setInputAction(function (movement) {
    if (!tool) return;
    var ll = globeLL(movement.endPosition);
    if (tool === "box" && boxFrom) {
      if (ll) boxTo = ll;
      return;
    }
    hover = ll;
    if (sketch.length && ll) {
      var pts = sketch.concat([unwrap(sketch[sketch.length - 1], ll)]);
      showMeasure(measureOf({ kind: tool, coords: pts }));
    }
  }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
  drawHandler.setInputAction(function () { if (sketch.length) finishGlobeSketch(); }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
  drawHandler.setInputAction(function (e) {
    if (tool !== "box") return;
    boxFrom = globeLL(e.position);
    boxTo = null;
    sketchBox.show = !!boxFrom;
  }, Cesium.ScreenSpaceEventType.LEFT_DOWN);
  drawHandler.setInputAction(function () {
    if (tool !== "box" || !boxFrom) return;
    var a = boxFrom, b = boxTo;
    boxFrom = boxTo = null;
    sketchBox.show = false;
    if (b && (a[0] !== b[0] || a[1] !== b[1])) addRange(rangeOf(a, b));
  }, Cesium.ScreenSpaceEventType.LEFT_UP);

  /** 도구가 켜져 있으면 누른 것을 도구가 받는다. 받았으면 true — 그때는 속성을 읽지 않는다. */
  //: 터치에는 두 번 누르기(LEFT_DOUBLE_CLICK)가 오지 않는다 — Cesium 은 마우스의 dblclick 만 옮긴다. 그래서 **마지막 점을 다시 누르면**
  //  (24 px 안) 선·면을 끝낸다. 시간 창은 두지 않는다 — 구를 그리느라 느린 기기에서는 두 번 누른 사이가 1 초 가까이 벌어졌다.
  //  휴대폰에서 거리 재기가 끝나지 않아 높이 그래프를 볼 수 없었다 (wetherilli 342)
  var lastTap = null;
  function drawClick(ll, px) {
    if (!tool) return false;
    var now = Date.now(), prev = lastTap, again = px && prev && Math.hypot(px.x - prev.x, px.y - prev.y) < 24;
    lastTap = px ? { t: now, x: px.x, y: px.y } : null;
    // 방금 끝낸 자리를 곧바로(3 초 안 — 느린 기기에서는 두 번 누른 사이가 1 초를 넘는다) 또 누른 것은 새 선을 시작하지 않는다 — 그래프가 닫혔다
    if (again && prev.done && now - prev.t < 3000) { lastTap.done = true; return true; }
    if (again && (tool === "line" || tool === "area") && sketch.length) { lastTap.done = true; finishGlobeSketch(); return true; }
    if (!ll) return true;
    if (tool === "point") addTemp(ll);
    else if (tool === "line" || tool === "area") {
      if (!sketch.length) { measured = null; lastMeasure = ""; renderDrawn(); hideProfile(); }
      sketch.push(unwrap(sketch[sketch.length - 1], ll));
    }
    return true;
  }
  function finishGlobeSketch() {
    // 두 번 누르면 LEFT_CLICK 이 두 번 먼저 온다 — 겹친 꼭짓점을 걷어낸다
    var pts = sketch.filter(function (p, i) { return !i || arc(sketch[i - 1], p) > 1; });
    sketch = []; hover = null;
    if (pts.length >= (tool === "area" ? 3 : 2)) finishMeasure(tool, pts);
    else updateToolOut();
  }
  function cancelSketch() {
    sketch = []; hover = null; boxFrom = boxTo = null; sketchBox.show = false;
    if (flatInteraction && flatInteraction.abortDrawing) flatInteraction.abortDrawing();
    flatSketching = false;
    updateToolOut();
  }
  /** 무엇이든 그리는 중인가 — 그동안은 구와 평면을 저절로 넘지 않는다. */
  function drawing() { return sketch.length > 0 || !!boxFrom || flatSketching; }

  // ── 찍고 잰 것 ──
  // 재는 것은 한 번에 하나만 둔다 — 여럿이 겹치면 어느 수가 어느 선의 것인지 모른다. 범위는 여럿을 둔다
  function finishMeasure(kind, coords) {
    measured = { kind: kind, coords: coords };
    var got = measureOf(measured);
    renderDrawn();
    showMeasure(got, true);
    if (kind === "line") showProfile(coords); else hideProfile();
  }

  // ── 높이 그래프 (wetherilli 100) ──
  // 거리를 다 재면 그 선의 LOLA 표고를 받아 아래 가운데 판에 그린다. 가로는 대원 거리(재는 수와 같다), 세로는
  // 달 기준구(1 737.4 km)에서 잰 높이다. 그래프 위를 훑으면 그 자리를 지도에도 찍는다
  var PROFILE = { W: 640, H: 170, L: 50, R: 10, T: 10, B: 22 };
  var profileSeq = 0, profileData = null, profileBand = null;
  // 지질 띠 (wetherilli 180) — 우리 파일로 그리는 판을 켰을 때만. Trek 판은 점마다 상류에 물어야 해서 띠가 없다
  var BAND_LAYER = { "orig-units": "moon:orig-units" };
  function bandLayer() {
    var top = active.filter(function (e) { return BAND_LAYER[e.name]; })[0];
    return top && window.GSMBand ? BAND_LAYER[top.name] : null;
  }
  function hideProfile() {
    profileSeq += 1;
    profileData = null;
    $("profile").hidden = true;
  }
  function showProfile(coords) {
    var seq = ++profileSeq, box = $("profile");
    profileData = null;
    box.hidden = false;
    $("profile-svg").innerHTML = "";
    profileBand = null;
    if (window.GSMBand) GSMBand.reset($("profile-svg"), PROFILE);
    $("profile-sum").textContent = "";
    $("profile-read").textContent = T("높이를 읽는 중…");
    // 256 ppd 한 칸(118 m)에 한 점쯤, 64–512 점
    var n = Math.max(64, Math.min(512, Math.round(lengthOf(coords) / 118)));
    var line = coords.map(function (c) { return c[0].toFixed(5) + "," + c[1].toFixed(5); }).join(";");
    fetch(BASE + "moon/profile/?line=" + encodeURIComponent(line) + "&n=" + n)
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        if (seq !== profileSeq) return;
        drawProfile(d);
        var layer = bandLayer();
        if (!layer || !profileData) return;
        GSMBand.load(BASE, layer, line, n).then(function (band) {
          if (seq !== profileSeq || !band || !profileData) return;
          profileBand = band;
          GSMBand.draw($("profile-svg"), PROFILE, profileData.X, d, band, T("지질"));
        });
      })
      .catch(function () { if (seq === profileSeq) $("profile-read").textContent = T("높이를 읽지 못했다"); });
  }
  function asHeight(m) { return Math.round(m).toLocaleString() + " m"; }
  function drawProfile(d) {
    var P = PROFILE, pw = P.W - P.L - P.R, ph = P.H - P.T - P.B;
    var got = d.elev.filter(function (e) { return e !== null; });
    if (!got.length) { $("profile-read").textContent = T("높이를 읽지 못했다"); return; }
    var lo = Math.min.apply(null, got), hi = Math.max.apply(null, got), total = d.dist[d.dist.length - 1] || 1;
    var pad = Math.max(10, (hi - lo) * 0.08), y0 = lo - pad, y1 = hi + pad;
    function X(dist) { return P.L + pw * dist / total; }
    function Y(e) { return P.T + ph * (1 - (e - y0) / (y1 - y0)); }
    // 못 읽은 점에서 선을 끊는다
    var path = "", area = "", run = [];
    function flush() {
      if (run.length > 1) {
        path += "M" + run.join("L");
        area += "M" + run[0].split(",")[0] + "," + (P.T + ph) + "L" + run.join("L") + "L" +
                run[run.length - 1].split(",")[0] + "," + (P.T + ph) + "Z";
      }
      run = [];
    }
    d.elev.forEach(function (e, i) {
      if (e === null) { flush(); return; }
      run.push(X(d.dist[i]).toFixed(1) + "," + Y(e).toFixed(1));
    });
    flush();
    var up = 0, down = 0;
    for (var i = 1; i < d.elev.length; i++) {
      if (d.elev[i] === null || d.elev[i - 1] === null) continue;
      var dh = d.elev[i] - d.elev[i - 1];
      if (dh > 0) up += dh; else down -= dh;
    }
    var svg = '<g>';
    [y0 + (y1 - y0) * 0.1, (y0 + y1) / 2, y1 - (y1 - y0) * 0.1].forEach(function (e) {
      svg += '<line class="grid" x1="' + P.L + '" x2="' + (P.W - P.R) + '" y1="' + Y(e).toFixed(1) + '" y2="' + Y(e).toFixed(1) + '"/>' +
             '<text class="tick" x="' + (P.L - 5) + '" y="' + (Y(e) + 3.5).toFixed(1) + '" text-anchor="end">' + esc(Math.round(e).toLocaleString()) + '</text>';
    });
    [0, 0.5, 1].forEach(function (f) {
      svg += '<text class="tick" x="' + X(total * f).toFixed(1) + '" y="' + (P.H - 6) + '" text-anchor="' +
             (f === 0 ? "start" : f === 1 ? "end" : "middle") + '">' + esc(asLength(total * f)) + '</text>';
    });
    svg += '</g><path class="area" d="' + area + '"/><path class="line" d="' + path + '"/>' +
           '<line class="cursor" id="profile-cursor" y1="' + P.T + '" y2="' + (P.T + ph) + '" visibility="hidden"/>' +
           '<circle class="dot" id="profile-dot" r="3.5" visibility="hidden"/>';
    $("profile-svg").innerHTML = svg;
    $("profile-sum").textContent = T("최저 {lo} · 최고 {hi} · 오르막 {up} · 내리막 {down}",
      { lo: asHeight(lo), hi: asHeight(hi), up: asHeight(up), down: asHeight(down) });
    var read = T("LOLA 256 ppd · 달 기준구 1737.4 km 에서 잰 높이");
    $("profile-read").textContent = read;
    profileData = { d: d, X: X, Y: Y, total: total, read: read };
  }
  (function () {
    var svg = $("profile-svg");
    function at(evt) {
      if (!profileData) return;
      var r = svg.getBoundingClientRect(), P = PROFILE;
      var x = (evt.clientX - r.left) * P.W / r.width;
      var dist = Math.max(0, Math.min(1, (x - P.L) / (P.W - P.L - P.R))) * profileData.total;
      var d = profileData.d, best = 0;
      for (var i = 1; i < d.dist.length; i++) if (Math.abs(d.dist[i] - dist) < Math.abs(d.dist[best] - dist)) best = i;
      var cx = profileData.X(d.dist[best]).toFixed(1), cur = $("profile-cursor"), dot = $("profile-dot");
      cur.setAttribute("x1", cx); cur.setAttribute("x2", cx); cur.setAttribute("visibility", "visible");
      if (d.elev[best] !== null) {
        dot.setAttribute("cx", cx); dot.setAttribute("cy", profileData.Y(d.elev[best]).toFixed(1));
        dot.setAttribute("visibility", "visible");
      } else dot.setAttribute("visibility", "hidden");
      var unit = window.GSMBand ? GSMBand.unitAt(profileBand, best) : "";
      var here = { d: asLength(d.dist[best]), h: d.elev[best] === null ? "—" : asHeight(d.elev[best]), unit: unit };
      $("profile-read").textContent = unit ? T("거리 {d} · 높이 {h} · {unit}", here) : T("거리 {d} · 높이 {h}", here);
      markAt([d.lon[best], d.lat[best]]);
    }
    svg.addEventListener("mousemove", at);
    svg.addEventListener("mouseleave", function () {
      if (!profileData) return;
      $("profile-cursor").setAttribute("visibility", "hidden");
      $("profile-dot").setAttribute("visibility", "hidden");
      $("profile-read").textContent = profileData.read;
      markAt(null);
    });
    $("profile-close").addEventListener("click", hideProfile);
  })();
  function addTemp(ll) {
    var w = wrapLon(ll);
    tempSeq += 1;
    temps.push({ no: tempSeq, lon: w[0], lat: w[1] });
    renderDrawn();
  }
  function addRange(r) {
    rangeSeq += 1;
    r.no = rangeSeq;
    ranges.push(r);
    renderDrawn();
    showRange(r);
  }
  // 지금 보는 높이 — 점으로 옮겨 갈 때 당기거나 물리지 않는다
  function hereHeight() {
    if (mode === "flat") return resToHeight(groundRes());
    var c = cameraLL();
    return c ? Math.min(c.h, 200000) : 200000;
  }
  function pixelOf(ll) {
    if (mode === "flat") return flat.getPixelFromCoordinate(fromLL(ll));
    var p = scene.cartesianToCanvasCoordinates(Cesium.Cartesian3.fromDegrees(ll[0], ll[1], 0, MOON));
    return p ? [p.x, p.y] : [wrap.clientWidth / 2, wrap.clientHeight / 2];
  }
  function showRange(r) {
    var f = rangeFacts(r);
    lastMeasure = T("범위 {n}", { n: r.no }) + " " + asArea(f.area);
    var out = $("measure-out");
    out.textContent = lastMeasure;
    out.classList.add("done");
    updateToolOut();
    ++asked;
    markAt(null);
    showPopup("<h3>" + esc(T("범위 {n}", { n: r.no })) + "</h3><table>" + Object.keys(rangeRows(f)).map(function (k) {
      return "<tr><th>" + esc(k) + "</th><td>" + esc(rangeRows(f)[k]) + "</td></tr>";
    }).join("") + "</table>", pixelOf(f.center));
  }
  function showMeasure(got, done) {
    var out = $("measure-out");
    out.textContent = got.kind + " " + got.text;
    out.classList.toggle("done", !!done);
    lastMeasure = got.kind + " " + got.text;
    updateToolOut();
  }
  /** 손잡이 옆의 알림 — 누른 곳 가까이에서 답이 나와야 한다(2D 와 같다). */
  function updateToolOut() {
    var out = $("tool-out"), bits = [];
    if (lastMeasure) bits.push(lastMeasure);
    if (temps.length) bits.push(T("점 {n}개", { n: temps.length }));
    if (tool === "point" && !temps.length) bits.push(T("지도를 눌러 점을 찍는다"));
    if (tool === "line" && !lastMeasure) bits.push(T("눌러 가며 잇는다 · 두 번 누르면 끝"));
    if (tool === "area" && !lastMeasure) bits.push(T("눌러 가며 두른다 · 두 번 누르면 끝"));
    if (tool === "box" && !ranges.length) bits.push(T("누른 채 끌어 네모를 그린다"));
    out.textContent = bits.join("  ·  ");
    out.hidden = !bits.length;
  }
  // 복사 — 운영이 http 로 열리는 자리가 있어 clipboard API 가 없으면 옛 길(textarea)로 (2D 와 같다)
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () {
        return legacyCopy(text) ? undefined : Promise.reject();
      });
    }
    return legacyCopy(text) ? Promise.resolve() : Promise.reject();
  }
  function legacyCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.cssText = "position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    area.remove();
    return ok;
  }
  popupBody.addEventListener("click", function (e) {
    var head = e.target.closest(".popup-coord");
    if (!head) return;
    var mark = head.querySelector(".copy");
    copyText(head.dataset.copy).then(function () {
      head.classList.add("copied");
      mark.textContent = T("복사했다");
      setTimeout(function () { head.classList.remove("copied"); mark.textContent = T("복사"); }, 900);
    }, function () {});
  });
  function copyButton(text, copied, title) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "temp-coord";
    b.title = title;
    b.textContent = text;
    b.addEventListener("click", function () {
      var done = function () { b.textContent = T("복사했다"); setTimeout(function () { b.textContent = text; }, 700); };
      copyText(copied).then(done, function () {});
    });
    return b;
  }
  function renderTemp() {
    var host = $("temp-list");
    $("count-temp").textContent = temps.length + ranges.length;
    updateToolOut();
    host.innerHTML = "";
    if (!temps.length && !ranges.length) {
      host.innerHTML = '<li class="empty">' + T("지도 오른쪽 위 <b>점</b> 도구로 찍는다") + "</li>";
      return;
    }
    ranges.forEach(function (r) {
      var li = document.createElement("li");
      li.className = "range-item";
      var no = document.createElement("span");
      no.className = "temp-no range";
      no.textContent = r.no;
      var f = rangeFacts(r);
      li.append(no,
        copyButton(asArea(f.area) + " · " + pair(f.center), rangeText(r), T("눌러서 꼭짓점·중앙·넓이를 복사한다")),
        iconButton("⊙", T("이 범위로 가서 수치를 본다"), false, function () {
          var span = Math.max((r.e - r.w) * Math.cos(rad(f.center[1])), r.n - r.s);
          goTo(f.center[0], f.center[1], Math.max(30000, span * M_PER_DEG * 1.6));
          setTimeout(function () { showRange(r); }, 1600);
        }),
        iconButton("×", T("지운다"), false, function () {
          ranges = ranges.filter(function (x) { return x !== r; });
          closePopup();
          renderDrawn();
        }));
      host.appendChild(li);
    });
    temps.forEach(function (t) {
      var li = document.createElement("li");
      var no = document.createElement("span");
      no.className = "temp-no";
      no.textContent = t.no;
      var text = pair([t.lon, t.lat]);
      li.append(no, copyButton(text, text, T("눌러서 복사한다")),
        iconButton("⊙", T("이 점으로 이동"), false, function () { goTo(t.lon, t.lat, hereHeight()); }),
        iconButton("×", T("지운다"), false, function () {
          temps = temps.filter(function (x) { return x !== t; });
          renderDrawn();
        }));
      host.appendChild(li);
    });
  }
  function clearDrawn() {
    cancelSketch();
    temps = []; ranges = []; measured = null;
    hideProfile();
    tempSeq = rangeSeq = 0;
    lastMeasure = "";
    var out = $("measure-out");
    out.textContent = T("아직 잰 것이 없다");
    out.classList.remove("done");
    closePopup();
    renderDrawn();
  }

  // 점묶음으로 저장 — 2D 와 같은 길(`pointsets/create/`)이고 몸만 달이다. 좌표는 ±180° 로 되돌려 싣는다
  function lonlat(coords) { return coords.map(wrapLon); }
  function saveTemp() {
    var msg = $("save-msg");
    if (!temps.length && !ranges.length && !measured) {
      msg.className = "msg bad";
      msg.textContent = T("저장할 점이 없다.");
      return;
    }
    var name = prompt(T("목록 이름"), T("찍은 점 {date}", { date: new Date().toLocaleDateString(LANG === "en" ? "en-GB" : "ko-KR") }));
    if (name === null) return;
    var shapes = ranges.map(function (r) {
      return { geometry: { type: "Polygon", coordinates: [lonlat(rangeRing(r))] },
               label: T("범위 {n}", { n: r.no }), props: rangeRows(rangeFacts(r)) };
    });
    if (measured) {
      var got = measureOf(measured), c = lonlat(measured.coords);
      shapes.push({ geometry: measured.kind === "area" ? { type: "Polygon", coordinates: [c.concat([c[0]])] }
                                                      : { type: "LineString", coordinates: c },
                    label: got.kind + " " + got.text, props: {} });
    }
    msg.className = "msg";
    msg.textContent = T("저장하는 중…");
    fetch(BASE + "pointsets/create/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({
        name: name, color: "#f2f2f2", body: "moon", shapes: shapes,
        points: temps.map(function (t) { return { lat: t.lat, lon: t.lon, label: T("점 {n}", { n: t.no }) }; }),
      }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.d.error || "");
        pointsets.unshift(res.d.pointset);
        setOff(res.d.pointset.id, false);
        renderSets();
        // 저장했으니 임시 표시는 치운다 — 같은 점이 두 겹으로 남으면 헷갈린다
        clearDrawn();
        msg.className = "msg good";
        msg.textContent = T("'{name}' 으로 저장했다.", { name: res.d.pointset.name });
      })
      .catch(function (e) {
        msg.className = "msg bad";
        msg.textContent = (e && e.message) || T("저장하지 못했다");
      });
  }

  function setTool(next) {
    cancelSketch();
    tool = next;
    document.querySelectorAll(".tool[data-draw]").forEach(function (b) { b.classList.toggle("on", b.dataset.draw === next); });
    $("globe").style.cursor = $("map").style.cursor = next ? "crosshair" : "";
    // 구에서 범위를 끄는 동안은 구가 끌려 돌지 않는다. 휠로 당기는 것은 된다
    var cam = scene.screenSpaceCameraController, still = next === "box";
    cam.enableRotate = cam.enableTranslate = cam.enableTilt = cam.enableLook = !still;
    if (next) { closePopup(); }
    installFlat();
    updateToolOut();
  }
  document.querySelectorAll(".tool[data-draw]").forEach(function (b) {
    // 누른 손잡이를 다시 누르면 꺼진다 — 아무것도 안 켜져 있으면 누르면 속성을 읽는다
    b.addEventListener("click", function () { setTool(tool === b.dataset.draw ? "" : b.dataset.draw); });
  });
  $("tool-clear").addEventListener("click", clearDrawn);
  $("clear-temp").addEventListener("click", clearDrawn);
  $("save-temp").addEventListener("click", saveTemp);
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    if (drawing()) cancelSketch();
    else if (tool) setTool("");
  });
  renderTemp();

  // ══ 그림으로 내려받기 (048) ═══════════════════════════════════════
  //
  // 2D·지구 3D 의 "그림" 과 같은 꼴 — 지금 보는 화면 한 장에 밑의 띠를 붙여 **무엇을 봤는지** 적는다.
  // 띠에는 구·평면, 배경(보정했으면 그 값), 켠 레이어, 점묶음, 가운데, 출처, 날짜가 들어간다.
  //
  // - 구는 Cesium 캔버스를 **그린 바로 그 프레임(`postRender`) 안에서** 옮겨 담는다. WebGL 은 그린 뒤 버퍼를
  //   비우는데, `preserveDrawingBuffer` 를 켜면 늘 느려진다(지구 3D 와 같은 판단). 타일이 다 올 때까지
  //   (`tilesLoaded`, 길어야 10 초) 기다린다. 기울인 화면은 앞뒤의 축척이 달라 **축척 막대를 넣지 않고**
  //   기울기·방위를 적는다
  // - 평면은 2D 처럼 레이어 캔버스들을 투명도·변환 그대로 겹친다. 배경이 WebGL 타일(042)이라 역시 그린
  //   바로 뒤(`rendercomplete`)에 담는다. 음영 겹치기는 화면에서 CSS 의 곱하기(mix-blend-mode)라 합칠 때도
  //   곱한다. 축척 막대를 넣는다 — 등거리 원통의 가운데 위도에서 잰다(`EQC.getPointResolution`)
  //
  // 팝업·패널은 HTML 이라 담기지 않는다. 찍고 잰 것·누른 자리의 고리·자전축은 캔버스에 있어 담긴다.
  // Trek 에서 곧장 받는 타일은 모두 CORS 로 받는다 — 하나라도 아니면 캔버스가 더럽혀져 뽑히지 않는다
  var exportBtn = $("tool-export");
  exportBtn.addEventListener("click", function () {
    exportBtn.disabled = true;
    var finish = function (canvas) {
      if (!canvas) { exportBtn.disabled = false; alert(T("그림을 만들지 못했다")); return; }
      canvas.toBlob(function (blob) {
        exportBtn.disabled = false;
        if (!blob) { alert(T("그림을 만들지 못했다")); return; }
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "GSM-moon-" + stampText().replace(/[-: ]/g, "").slice(0, 12) + ".png";
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      }, "image/png");
    };
    if (mode === "flat") captureFlat(finish); else captureGlobe(finish);
  });

  function captureGlobe(done) {
    var t0 = Date.now();
    var remove = scene.postRender.addEventListener(function () {
      if (!scene.globe.tilesLoaded && Date.now() - t0 < 10000) return;
      remove();
      var gl = scene.canvas, w = gl.clientWidth, h = gl.clientHeight;
      done(safely(function () { return compose(w, h, gl.width / w, function (ctx) { ctx.drawImage(gl, 0, 0); }); }));
    });
    scene.requestRender();
  }

  function captureFlat(done) {
    flat.once("rendercomplete", function () {
      var size = flat.getSize(), w = size[0], h = size[1], ratio = window.devicePixelRatio || 1;
      done(safely(function () {
        return compose(w, h, ratio, function (ctx) {
          flat.getViewport().querySelectorAll(".ol-layers canvas").forEach(function (c) {
            if (!c.width) return;
            var holder = c.parentNode, opacity = holder.style.opacity || c.style.opacity;
            ctx.globalAlpha = opacity === "" ? 1 : Number(opacity);
            ctx.globalCompositeOperation = getComputedStyle(holder).mixBlendMode === "multiply" ? "multiply" : "source-over";
            var m = /^matrix\(([^(]*)\)$/.exec(c.style.transform || "");
            var t = m ? m[1].split(",").map(Number) : [w / c.width, 0, 0, h / c.height, 0, 0];
            ctx.setTransform(t[0] * ratio, t[1] * ratio, t[2] * ratio, t[3] * ratio, t[4] * ratio, t[5] * ratio);
            ctx.drawImage(c, 0, 0);
          });
          ctx.globalAlpha = 1;
          ctx.globalCompositeOperation = "source-over";
        });
      }));
    });
    flat.renderSync();
  }

  /** 교차 출처 타일이 섞여 캔버스가 더럽혀지면 뽑을 때(`toBlob`) 막힌다 — 여기서 미리 걸러 null 을 낸다. */
  function safely(make) {
    try {
      var canvas = make();
      canvas.getContext("2d").getImageData(0, 0, 1, 1);
      return canvas;
    } catch (e) { return null; }
  }

  function stampText() {
    var d = new Date();
    function two(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + two(d.getMonth() + 1) + "-" + two(d.getDate()) + " " +
      two(d.getHours()) + ":" + two(d.getMinutes());
  }

  /** 화면 한 장(`paint` 가 그린다) + 밑의 띠. 달 화면처럼 흑백이다. */
  function compose(w, h, ratio, paint) {
    var lineH = 17, pad = 12, bar = mode === "flat" ? 170 : 0;
    // 넘치는 줄은 " · " 에서 끊어 다음 줄로 잇는다 — 출처는 잘리면 안 된다(누가 만든 그림인지가 거기 있다)
    var probe = document.createElement("canvas").getContext("2d");
    var lines = [];
    exportLines().forEach(function (line, i) {
      probe.font = (i === 0 ? "bold 14px " : "12px ") + "sans-serif";
      var max = w - pad * 2 - (i === 0 ? bar : 0), cur = "";
      line.split(" · ").forEach(function (bit) {
        var next = cur ? cur + " · " + bit : bit;
        if (cur && probe.measureText(next).width > max) { lines.push(cur); cur = "   " + bit; }
        else cur = next;
      });
      lines.push(i === 0 ? { head: cur } : cur);
    });
    var foot = pad * 2 + lineH * lines.length;
    var out = document.createElement("canvas");
    out.width = Math.round(w * ratio);
    out.height = Math.round((h + foot) * ratio);
    var ctx = out.getContext("2d");
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, out.width, out.height);
    paint(ctx);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.fillStyle = "#f4f4f4";
    ctx.fillRect(0, h, w, foot);
    ctx.fillStyle = "#111";
    ctx.fillRect(0, h, w, 1);
    ctx.textBaseline = "top";
    lines.forEach(function (line, i) {
      var head = typeof line === "object";
      ctx.font = (head ? "bold 14px " : "12px ") + "sans-serif";
      ctx.fillStyle = head ? "#111" : "#333";
      ctx.fillText(fitText(ctx, head ? line.head : line, w - pad * 2 - (head ? bar : 0)), pad, h + pad + i * lineH + (i ? 3 : 0));
    });
    if (bar) drawScaleBar(ctx, w - pad - 150, h + pad + 2, 150);
    return out;
  }

  /** 띠에 적을 줄들. 첫 줄이 제목이다. */
  function exportLines() {
    var shown = active.map(function (e) { return T(LAYER[e.name].title); });
    var mine = pointsets.filter(function (ps) { return ps.visible; });
    var select = $("basemap"), base = select.options[select.selectedIndex].text;
    var tuned = TUNES.filter(function (k) { return tune[k] !== TUNE_DEFAULT[k]; });
    if (tuned.length || tune.shade) {
      base += " · " + T("영상 보정") + " " + tuned.map(function (k) { return tuneText(k, tune[k]); }).join("/") +
              (tune.shade ? (tuned.length ? " + " : "") + T("음영") : "");
    }
    var where;
    if (mode === "flat") {
      where = fmt(clean(wrapLon(toLL(flat.getView().getCenter()))));
    } else {
      var p = pivot(false);
      if (p) {
        var c = MOON.cartesianToCartographic(p.pos), a = anglesAt(p.pos, false);
        where = fmt(clean([Cesium.Math.toDegrees(c.longitude), Cesium.Math.toDegrees(c.latitude)])) + " · " +
                T("기울기 {tilt}° · 방위 {heading}°", { tilt: Math.round(90 + a.pitch), heading: Math.round(a.heading) % 360 });
      } else where = "—";
      if (look.terrain) where += " · " + T("지형 과장") + " ×" + (look.exag / 10).toFixed(1);
    }
    var credits = [mode === "flat" ? baseCredit(look.base) : BASES[look.base].credit];
    if (BASES[look.base].under) credits.push(BASES.wac.credit);
    if (tune.shade && look.base !== "lola") credits.push(SHADE.credit);
    active.forEach(function (e) { credits.push(creditOf(e.name) || LAYER[e.name].src); });
    if (mode === "globe" && look.terrain) credits.push("LRO LOLA DEM (NASA/GSFC)");
    credits = credits.filter(function (c, i) { return c && credits.indexOf(c) === i; });
    var kind = mode !== "flat" ? T("구") : proj === EQC ? T("평면") :
      T("평면") + " (" + T(proj === NPS ? "북극 평사도법" : "남극 평사도법") + ")";
    var out = [T("대돌여지도") + " · " + T("달") + " · " + kind + " · " + stampText()];
    out.push(T("배경") + ": " + base);
    out.push(T("레이어") + ": " + (shown.length ? shown.join(" / ") : "—"));
    if (mine.length) out.push(T("점묶음") + ": " + mine.map(function (ps) { return ps.name; }).join(", "));
    out.push(T("가운데") + ": " + where);
    out.push(T("출처") + ": " + credits.join(" · "));
    return out;
  }

  // 소수 넷째 자리에서 0 이 되는 값은 0 으로 — "-0.0000°" 가 찍히지 않게
  function clean(ll) { return ll.map(function (v) { return Math.abs(v) < 5e-5 ? 0 : v; }); }
  function fitText(ctx, text, max) {
    if (ctx.measureText(text).width <= max) return text;
    while (text.length > 1 && ctx.measureText(text + "…").width > max) text = text.slice(0, -1);
    return text + "…";
  }

  /** 평면 가운데 위도의 땅 축척으로 막대를 그린다. 1·2·5 × 10ⁿ 로 반올림한다. */
  function drawScaleBar(ctx, x, y, maxWidth) {
    var v = flat.getView();
    var metersPerPx = ol.proj.getPointResolution(proj, v.getResolution(), v.getCenter(), "m");
    if (!isFinite(metersPerPx) || metersPerPx <= 0) return;
    var raw = metersPerPx * maxWidth;
    var pow = Math.pow(10, Math.floor(Math.log10(raw)));
    var nice = [5, 2, 1].map(function (k) { return k * pow; }).filter(function (n) { return n <= raw; })[0] || pow;
    var px = nice / metersPerPx;
    ctx.fillStyle = "#111";
    ctx.fillRect(x, y + 14, px, 4);
    ctx.fillRect(x, y + 10, 1.5, 8);
    ctx.fillRect(x + px - 1.5, y + 10, 1.5, 8);
    ctx.font = "12px sans-serif";
    ctx.fillText(nice >= 1000 ? (nice / 1000) + " km" : nice + " m", x, y - 4);
  }

  // ══ 대기 화면 (058) — 지구(`map.js`)와 같은 규칙이다 ═══════════════
  // 첫 화면의 타일이 다 오면 걷는다. 적어도 1.2 초는 보이고, 상류가 느려도 12 초 뒤에는 걷는다.
  // 구는 Cesium 의 타일 대기열이 비었을 때, 평면으로 열리면 OpenLayers 의 첫 `rendercomplete` 다
  (function () {
    var splash = document.getElementById("splash");
    if (!splash) return;
    var shownAt = Date.now(), done = false, off = null;
    function lift() {
      if (done) return;
      done = true;
      if (off) off();
      setTimeout(function () {
        splash.classList.add("gone");
        setTimeout(function () { splash.remove(); }, 600);
      }, Math.max(0, 1200 - (Date.now() - shownAt)));
    }
    off = viewer.scene.globe.tileLoadProgressEvent.addEventListener(function (queued) {
      if (queued === 0 && mode === "globe" && viewer.scene.globe.tilesLoaded) lift();
    });
    flat.once("rendercomplete", function () { if (mode === "flat") lift(); });
    setTimeout(lift, 12000);
  })();

  // ══ 처음 자리 — 기억한 것. 처음이면 앞면 한가운데를 멀리서 ═══════
  // 맨 끝에 둔다 — 평면으로 여는 길이 팝업·목록을 다 만든 뒤라야 한다
  try {
    var v = JSON.parse(saved("gsm.moon.view", "null"));
    if (v && isFinite(v.lon) && isFinite(v.lat) && isFinite(v.h)) {
      viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(v.lon, v.lat, v.h, MOON),
                              orientation: { heading: v.heading || 0, pitch: isFinite(v.pitch) ? v.pitch : -Math.PI / 2, roll: 0 } });
    } else flyGlobe(0, 0, 5200000);
    var f = JSON.parse(saved("gsm.moon.flat", "null"));
    if (saved("gsm.moon.mode", "globe") === "flat" && f && isFinite(f.lon) && isFinite(f.res)) {
      setMode("flat", { lon: f.lon, lat: f.lat, h: resToHeight(f.res) });
    }
  } catch (e) { flyGlobe(0, 0, 5200000); }

  // 공유 링크 (wetherilli 189) — 지금 보는 것(구면 카메라, 평면이면 가운데와 땅의 해상도)·켠 레이어·배경
  function shareLink() {
    var q = { m: mode, l: GSMShare.pack(active), b: look.base };
    if (mode === "flat") {
      var ll = toLL(flat.getView().getCenter());
      q.c = ll[0].toFixed(5) + "," + ll[1].toFixed(5);
      q.res = Math.round(groundRes());
    } else {
      var c = cameraLL();
      if (c) {
        q.c = c.lon.toFixed(5) + "," + c.lat.toFixed(5);
        q.h = Math.round(c.h);
        // 바로 북쪽을 보면 Cesium 이 2π(6.2832)를 줄 때가 있다 — 0 과 같은 쪽이라 0 으로 적어 링크가 늘 같게 (wetherilli 344)
        var heading = ((viewer.camera.heading % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
        q.hd = (2 * Math.PI - heading < 1e-4 ? 0 : heading).toFixed(4);
        q.pt = viewer.camera.pitch.toFixed(4);
      }
    }
    return GSMShare.link(q);
  }
  if (window.GSMShare) {
    GSMShare.wire($("tool-share"), shareLink, { done: T("복사했다"), ask: T("이 링크를 복사한다") });
    if (SHARED) GSMShare.notice(T("링크로 연 화면이다 — 여기서 바꾼 것은 이 브라우저에 기억하지 않는다"), T("내 화면으로"));
  }

  // ── 패널 접기 (jikhanjung 008) ────────────────────────────────────
  //
  // 지구 지도(jikhanjung 007)와 같은 손잡이. 접힌 채인지는 세 화면이 한 열쇠(`gsm.panelFolded`)를
  // 같이 쓴다 — 접어 두는 것은 사람의 버릇이지 화면의 것이 아니다. 접고 편 뒤에는 평면과 구를
  // 둘 다 다시 잰다(숨은 쪽도 — 바꿔 들어갈 때 어긋나지 않게).
  (function () {
    var handle = document.getElementById("panel-handle");
    if (!handle) return;
    var KEY = "gsm.panelFolded";
    function apply(folded, keep) {
      document.body.classList.toggle("panel-folded", folded);
      handle.textContent = folded ? ">" : "<";
      handle.title = folded ? T("패널을 편다") : T("패널을 접는다");
      handle.setAttribute("aria-expanded", folded ? "false" : "true");
      if (keep) {
        try { localStorage.setItem(KEY, folded ? "1" : "0"); } catch (e) { /* 사생활 모드 */ }
      }
      setTimeout(function () {
        flat.updateSize();
        viewer.resize();
        viewer.scene.requestRender();
      }, 0);
    }
    // 휴대폰은 접힌 채로 연다 — 편 채로 두었을 때만 편다 (wetherilli 128)
    var phone = window.matchMedia("(max-width: 760px)").matches, folded = phone;
    try { var kept = localStorage.getItem(KEY); if (kept) folded = kept === "1"; } catch (e) { /* 사생활 모드 */ }
    if (folded) apply(true, false);
    handle.addEventListener("click", function () {
      apply(!document.body.classList.contains("panel-folded"), true);
    });
  })();
})();
