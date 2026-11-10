/* 대돌여지도 — 남극 고지형 3D (wetherilli 443).
 *
 * 3D(`map3d.js`, MapLibre)는 메르카토르라 남위 85° 너머(남극점 둘레 550 km)를 그리지 못하고 동남극을 동서로 늘린다.
 * Gernon 외 2026 의 고지형 격자는 남극점을 품으므로 **Cesium 의 둥근 지구**에 세운다 — 달·화성·온 지구 화면과 같은 틀이다.
 *
 * - 땅: `paleo3d/dem/<연대>/` — 서버가 고지형 격자를 Cesium 의 경위도 격자 65×65 로 편다. 격자 밖은 오늘의 IBCSO 빙저
 * - 색: `geo/gernontopo/<연대>/` — 2D 의 칠한 3031 타일을 서버가 경위도 격자로 편 것. 밑은 IBCSO 빙저 색(`geo/ibcso/bed/`)과 Blue Marble
 * - 등고선·빙상 범위: 2D·3D 와 같은 덩이(`points/?layer=&age=`)를 땅에 붙여 긋는다
 * - 연대 막대: 2D·3D 와 같은 꼴, 같은 기억(`gsm.paleoage`). ▶ 는 땅이 다 선 뒤 다음 칸으로 간다
 */
(function () {
  "use strict";

  var BASE = location.pathname.replace(/paleo3d\/?$/, "");
  var LANG = document.documentElement.lang === "en" ? "en" : "ko";
  var I18N = JSON.parse((document.getElementById("i18n-data") || {}).textContent || "{}");
  function T(text, vars) {
    var out = (LANG === "en" && I18N[text]) || text;
    if (vars) out = out.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; });
    return out;
  }
  function $(id) { return document.getElementById(id); }
  function saved(key, fallback) {
    try { var v = localStorage.getItem(key); return v == null ? fallback : v; } catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, String(value)); } catch (e) { /* 사생활 모드 */ }
  }

  var AGES = JSON.parse(($("gernon-ages") || {}).textContent || "[]");
  var DEM_MAX = JSON.parse(($("dem-max") || {}).textContent || "9");
  var AGE_KEY = "gsm.paleoage";                 // 2D·3D 의 연대 막대와 같은 열쇠
  var age = +saved(AGE_KEY, AGES[0]);
  if (AGES.indexOf(age) < 0) age = AGES[0];
  var look = {
    ground: saved("gsm.paleo3d.ground", "paleo") === "today" ? "today" : "paleo",
    drape: saved("gsm.paleo3d.drape", "1") === "1",
    contours: saved("gsm.paleo3d.contours", "0") === "1",
    ice: saved("gsm.paleo3d.ice", "0") === "1",
    exag: Math.max(10, Math.min(100, +saved("gsm.paleo3d.exag", "30") || 30)),
  };

  function status(text) { var el = $("p3-status"); if (el) el.textContent = text || ""; }

  // ══ 구 ════════════════════════════════════════════════════════════
  var GEO = new Cesium.GeographicTilingScheme();
  var SOUTH50 = Cesium.Rectangle.fromDegrees(-180, -90, 180, -50);
  var SOUTH60 = Cesium.Rectangle.fromDegrees(-180, -90, 180, -60);

  // 바탕 — Blue Marble(온 지구 화면과 같은 GIBS 중계)
  var blueMarble = new Cesium.ImageryLayer(new Cesium.WebMapServiceImageryProvider({
    url: BASE + "gibs/wms/", layers: "BlueMarble_ShadedRelief_Bathymetry",
    parameters: { format: "image/jpeg", transparent: false },
    tilingScheme: new Cesium.GeographicTilingScheme(), maximumLevel: 6,
    credit: "Blue Marble · NASA EOSDIS GIBS",
  }));

  // ── 땅 — 65×65 높이 격자. 서버 줌 끝(`DEM_MAX`) 너머는 조상 격자를 겹선형으로 늘린다(달 화면과 같은 꼴) ──
  var DEM_SIZE = 65;
  var demMemo = {}, memoAges = [];
  function demKey() { return look.ground === "today" ? "today" : String(age); }
  function demGrid(which, x, y, level) {
    var id = which + "/" + level + "/" + x + "/" + y;
    if (!demMemo[id]) {
      demMemo[id] = fetch(BASE + "paleo3d/dem/" + id + ".png").then(function (r) {
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
        for (var i = 0; i < out.length; i++) out[i] = px[i * 4] * 256 + px[i * 4 + 1] + px[i * 4 + 2] / 256 - 32768;
        return out;
      }).catch(function () {
        delete demMemo[id];                    // 다음에 다시 묻는다. 이번에는 평평하게
        return new Float32Array(DEM_SIZE * DEM_SIZE);
      });
    }
    return demMemo[id];
  }
  /** 메모리에 두는 땅은 연대 넷까지 — 재생하며 34 장을 다 쥐지 않는다 */
  function keepMemo(which) {
    memoAges = memoAges.filter(function (a) { return a !== which; });
    memoAges.push(which);
    while (memoAges.length > 4) {
      var drop = memoAges.shift() + "/";
      Object.keys(demMemo).forEach(function (k) { if (k.indexOf(drop) === 0) delete demMemo[k]; });
    }
  }
  function terrainFor(which) {
    keepMemo(which);
    return new Cesium.CustomHeightmapTerrainProvider({
      width: DEM_SIZE, height: DEM_SIZE, tilingScheme: GEO,
      credit: "Gernon et al. 2026 · IBCSO v2",
      callback: function (x, y, level) {
        // 남위 50° 북쪽은 묻지 않는다 — 빙저도 고지형도 없다
        if (90 - (y + 1) * 180 / Math.pow(2, level) > -50) return new Float32Array(DEM_SIZE * DEM_SIZE);
        var top = Math.min(level, DEM_MAX);
        if (level === top) return demGrid(which, x, y, level);
        var k = Math.pow(2, level - top);
        var ax = Math.floor(x / k), ay = Math.floor(y / k);
        var ox = (x - ax * k) / k, oy = (y - ay * k) / k, span = 1 / k, n = DEM_SIZE - 1;
        return demGrid(which, ax, ay, top).then(function (src) {
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
      },
    });
  }

  var viewer = new Cesium.Viewer("globe", {
    baseLayer: blueMarble,
    terrainProvider: terrainFor(demKey()),
    baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
    navigationHelpButton: false, animation: false, timeline: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false,
    showRenderLoopErrors: false,
  });
  var scene = viewer.scene;
  scene.globe.enableLighting = false;
  scene.globe.depthTestAgainstTerrain = true;
  scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1a2c");
  scene.globe.maximumScreenSpaceError = 2.5;
  scene.fog.enabled = false;
  scene.verticalExaggeration = look.exag / 10;
  if (scene.moon) scene.moon.show = false;
  window.__gsmPaleo3d = viewer;
  viewer.scene.renderError.addEventListener(function () {
    status(T("그리기가 멈췄다 — 새로고침하면 다시 그린다"));
  });

  // 오늘의 빙저 색 — 고지형 격자 밖을 채운다
  var ibcsoLayer = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
    url: BASE + "geo/ibcso/bed/{z}/{x}/{y}.png", tilingScheme: new Cesium.GeographicTilingScheme(),
    rectangle: SOUTH50, maximumLevel: 10, hasAlphaChannel: true, credit: "IBCSO v2",
  }));

  // ── 고지형 색 — 연대마다 한 겹. 새 겹이 다 선 뒤 옛 겹을 걷는다(재생할 때 깜빡이지 않게) ──
  var drapeLayer = null, staleDrapes = [];
  function drapeFor(a) {
    var layer = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: BASE + "geo/gernontopo/" + a + "/{z}/{x}/{y}.png", tilingScheme: new Cesium.GeographicTilingScheme(),
      rectangle: SOUTH60, maximumLevel: 8, hasAlphaChannel: true, credit: "Gernon et al. 2026",
    }));
    layer.alpha = 0.92;
    return layer;
  }
  function setDrape() {
    if (drapeLayer) staleDrapes.push(drapeLayer);
    drapeLayer = look.drape && look.ground === "paleo" ? drapeFor(age) : null;
    if (!drapeLayer) dropStaleDrapes();
  }
  function dropStaleDrapes() {
    staleDrapes.forEach(function (l) { viewer.imageryLayers.remove(l, true); });
    staleDrapes = [];
  }
  ibcsoLayer.show = true;

  // ── 등고선·빙상 범위 (2D·3D 와 같은 덩이, 같은 색) ──
  var OVERLAYS = [
    { key: "ice", layer: "antpapers:gernon_ice", fill: true },
    { key: "contours", layer: "antpapers:gernon_contours", fill: false },
  ];
  function colorOf(legend, code, field, fallback) {
    var row = (legend || []).filter(function (r) { return String(r.code) === String(code); })[0];
    return row && row[field] != null ? row[field] : fallback;
  }
  function loadOverlay(o) {
    var ask = o.asked = (o.asked || 0) + 1;
    if (!look[o.key] || look.ground !== "paleo") { swapOverlay(o, null); return; }
    var a = age;
    fetch(BASE + "points/?layer=" + encodeURIComponent(o.layer) + "&age=" + a + "&lang=" + LANG)
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        if (ask !== o.asked) return null;
        return Cesium.GeoJsonDataSource.load(d, { clampToGround: true }).then(function (ds) {
          if (ask !== o.asked) return;
          ds.entities.values.slice().forEach(function (e) {
            var code = e.properties && e.properties.code ? e.properties.code.getValue() : null;
            var color = Cesium.Color.fromCssColorString(colorOf(d.legend, code, "color", "#1f78b4"));
            if (e.polygon) {
              e.polygon.material = color.withAlpha(0.35);
              e.polygon.outline = false;
              var ring = e.polygon.hierarchy.getValue(Cesium.JulianDate.now());
              if (ring && ring.positions) {
                ds.entities.add({ polyline: { positions: ring.positions.concat([ring.positions[0]]), clampToGround: true,
                                              width: 2, material: color } });
              }
            }
            if (e.polyline) {
              e.polyline.material = color;
              e.polyline.width = +colorOf(d.legend, code, "width", 1.5) * 1.3;
            }
          });
          swapOverlay(o, ds);
        });
      })
      .catch(function (err) { console.error(o.layer, err); });
  }
  function swapOverlay(o, ds) {
    if (o.ds) viewer.dataSources.remove(o.ds, true);
    o.ds = ds;
    if (ds) viewer.dataSources.add(ds);
  }
  function loadOverlays() { OVERLAYS.forEach(loadOverlay); }

  // ── 시점 — 남극점을 곧장 내려다보기(2D 의 3031 처럼 0° 가 위)와 동남극을 바다 쪽에서 비스듬히 ──
  function viewTop(fly) {
    var opts = { destination: Cesium.Cartesian3.fromDegrees(0, -89.9, 6.2e6),
                 orientation: { heading: 0, pitch: -Math.PI / 2, roll: 0 } };
    if (fly) viewer.camera.flyTo(Object.assign({ duration: 1.5 }, opts)); else viewer.camera.setView(opts);
  }
  function viewTilt(fly) {
    // 격자 가운데(3031 의 500·1 000 km — 남위 80°, 동경 27°)를 북쪽 바다에서 남쪽으로 본다
    var target = new Cesium.BoundingSphere(Cesium.Cartesian3.fromDegrees(27, -81, 0), 1);
    var offset = new Cesium.HeadingPitchRange(Math.PI, Cesium.Math.toRadians(-30), 2.7e6);
    if (fly) viewer.camera.flyToBoundingSphere(target, { offset: offset, duration: 1.5 });
    else viewer.camera.viewBoundingSphere(target, offset);
    viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
  }
  viewTilt(false);
  $("view-top").addEventListener("click", function () { viewTop(true); });
  $("view-tilt").addEventListener("click", function () { viewTilt(true); });

  // ── 땅이 다 서면 — 이미 서 있으면 곧장, 길어야 10 초 ──
  function whenLoaded(then) {
    var t0 = Date.now(), done = false;
    function check() {
      if (done) return;
      if (scene.globe.tilesLoaded || Date.now() - t0 > 10000) { done = true; then(); return; }
      setTimeout(check, 150);
    }
    setTimeout(check, 300);                    // 새 땅의 요청이 줄에 오를 틈
  }
  function settle() {
    status(T("땅을 세우는 중…"));
    var at = age, ground = look.ground;
    whenLoaded(function () {
      if (at !== age || ground !== look.ground) return;
      dropStaleDrapes();
      status("");
      window.__gsmPaleo3dReady = true;
    });
  }

  // ── 연대 ──
  function setAge(a) {
    if (a === age) return;
    age = a;
    save(AGE_KEY, a);
    if (look.ground === "paleo") viewer.terrainProvider = terrainFor(demKey());
    setDrape();
    loadOverlays();
    refreshAgebar();
    settle();
  }
  function refreshAgebar() {
    var bar = $("agebar"), at = AGES.indexOf(age);
    bar.hidden = look.ground !== "paleo" || !AGES.length;
    if (bar.hidden) { stopPlay(); return; }
    var range = $("agebar-range");
    range.max = AGES.length - 1;
    range.value = at;
    range.setAttribute("aria-valuetext", age + " Ma");
    $("agebar-age").textContent = T("{age} Ma", { age: age });
    $("agebar-older").disabled = at === 0;
    $("agebar-younger").disabled = at === AGES.length - 1;
  }
  function stepAge(delta) {
    var at = Math.max(0, Math.min(AGES.length - 1, AGES.indexOf(age) + delta));
    setAge(AGES[at]);
    return at;
  }
  var playing = false, timer = null, PAUSE_MS = 700;
  function stopPlay() {
    playing = false;
    if (timer) clearTimeout(timer);
    timer = null;
    var play = $("agebar-play");
    play.textContent = "▶";
    play.title = T("재생 — 옛날에서 오늘 쪽으로 저절로 넘긴다");
    play.setAttribute("aria-pressed", "false");
  }
  function playStep() {
    if (!playing) return;
    if (stepAge(1) >= AGES.length - 1) { stopPlay(); return; }
    whenLoaded(function () { if (playing) timer = setTimeout(playStep, PAUSE_MS); });
  }
  $("agebar-older").addEventListener("click", function () { stopPlay(); stepAge(-1); });
  $("agebar-younger").addEventListener("click", function () { stopPlay(); stepAge(1); });
  $("agebar-range").addEventListener("input", function () {
    stopPlay();
    if (AGES[+this.value] != null) setAge(AGES[+this.value]);
  });
  $("agebar-play").addEventListener("click", function () {
    if (playing) { stopPlay(); return; }
    if (AGES.indexOf(age) >= AGES.length - 1) setAge(AGES[0]);
    playing = true;
    this.textContent = "❚❚";
    this.title = T("멈춘다");
    this.setAttribute("aria-pressed", "true");
    timer = setTimeout(playStep, PAUSE_MS);
  });

  // ── 판의 칸들 ──
  var ground = $("ground");
  ground.value = look.ground;
  ground.addEventListener("change", function () {
    stopPlay();
    look.ground = ground.value === "today" ? "today" : "paleo";
    save("gsm.paleo3d.ground", look.ground);
    viewer.terrainProvider = terrainFor(demKey());
    setDrape();
    loadOverlays();
    refreshAgebar();
    syncBoxes();
    settle();
  });
  function syncBoxes() {
    ["drape", "contours", "ice"].forEach(function (k) { $(k).disabled = look.ground !== "paleo"; });
  }
  ["drape", "contours", "ice"].forEach(function (k) {
    var box = $(k);
    box.checked = look[k];
    box.addEventListener("change", function () {
      look[k] = box.checked;
      save("gsm.paleo3d." + k, look[k] ? "1" : "0");
      if (k === "drape") { setDrape(); settle(); } else loadOverlay(OVERLAYS.filter(function (o) { return o.key === k; })[0]);
    });
  });
  var exag = $("exag");
  exag.value = look.exag;
  function showExag() { $("ex-num").textContent = "×" + (look.exag / 10).toFixed(1); }
  exag.addEventListener("input", function () {
    look.exag = +exag.value;
    scene.verticalExaggeration = look.exag / 10;
    save("gsm.paleo3d.exag", look.exag);
    showExag();
  });
  showExag();
  function fold(folded) {
    var btn = $("fold3d");
    $("panel3d").classList.toggle("folded", folded);
    btn.setAttribute("aria-expanded", folded ? "false" : "true");
    btn.title = folded ? T("펴기") : T("접기");
    btn.setAttribute("aria-label", btn.title);
  }
  $("fold3d").addEventListener("click", function () { fold(!$("panel3d").classList.contains("folded")); });
  // 휴대폰은 판이 접힌 채로 연다 — 펴면 구를 거의 다 덮는다
  if (window.matchMedia && window.matchMedia("(max-width: 760px)").matches) fold(true);
  // 2D·3D 로 갈 때 연대는 열쇠(`gsm.paleoage`)가 넘긴다 — 남극 탭으로 연다
  $("to2d").addEventListener("click", function () { save("gsm.region", "antarctica"); });

  syncBoxes();
  setDrape();
  loadOverlays();
  stopPlay();
  refreshAgebar();
  settle();
})();
