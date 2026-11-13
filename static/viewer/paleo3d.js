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

  // ══ 시점 — 온 지구·달·화성 화면의 "자세" 묶음과 같은 손·같은 단추 (wetherilli 444) ═══════════
  //
  // 손 — 왼쪽으로 끌면 구를 돌리고, 오른쪽 단추(또는 Ctrl·가운데 단추·두 손가락)로 끌면 기울이고 돈다. 휠은 당기고 민다.
  // 돌고 기울이는 중심은 **화면 한가운데 아래의 지형 점**이다(`earth.js` 와 같다).
  // 방위는 그 점의 수평면에서 지구의 북쪽이 0°, 시계 방향. **위도 89.5° 너머는 경도 0° 쪽이 0°** 다 — 남극점 위에서는
  // 2D 남극 탭(3031)처럼 경도 0° 가 위로 온다
  var ELL = Cesium.Ellipsoid.WGS84;
  var cam = scene.screenSpaceCameraController;
  cam.tiltEventTypes = [Cesium.CameraEventType.MIDDLE_DRAG, Cesium.CameraEventType.PINCH,
                        Cesium.CameraEventType.RIGHT_DRAG,
                        { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL }];
  cam.zoomEventTypes = [Cesium.CameraEventType.WHEEL, Cesium.CameraEventType.PINCH];
  var X_AXIS = new Cesium.Cartesian3(1, 0, 0), Z_AXIS = new Cesium.Cartesian3(0, 0, 1);

  function cameraLL() {
    var c = ELL.cartesianToCartographic(viewer.camera.positionWC);
    return c ? { lon: Cesium.Math.toDegrees(c.longitude), lat: Cesium.Math.toDegrees(c.latitude), h: c.height } : null;
  }
  function flyGlobe(lon, lat, h, duration) {
    var dest = Cesium.Cartesian3.fromDegrees(lon, lat, h, ELL);
    var orient = { heading: 0, pitch: -Math.PI / 2, roll: 0 };
    if (duration) viewer.camera.flyTo({ destination: dest, orientation: orient, duration: duration });
    else viewer.camera.setView({ destination: dest, orientation: orient });
  }
  /** 화면 한가운데 아래의 점과 거기까지의 거리. `terrain` 이면 지형을, 아니면 타원체를 짚는다(가볍다). */
  function pivot(terrain) {
    var cv = scene.canvas, mid = new Cesium.Cartesian2(cv.clientWidth / 2, cv.clientHeight / 2);
    var pos = null;
    if (terrain) {
      var ray = viewer.camera.getPickRay(mid);
      pos = ray && scene.globe.pick(ray, scene);
    }
    if (!pos) pos = viewer.camera.pickEllipsoid(mid, ELL);
    return pos ? { pos: pos, range: Cesium.Cartesian3.distance(viewer.camera.positionWC, pos) } : null;
  }
  /** 점 `pos` 의 수평면에서 본 카메라의 방위·기울기(도). `cesium` 이면 Cesium 의 동-북-위(`lookAt` 에 넘길 값),
   *  아니면 위의 기준(극 가까이는 경도 0° 쪽)이다. */
  function anglesAt(pos, cesium) {
    var up = ELL.geodeticSurfaceNormal(pos, new Cesium.Cartesian3());
    var north, east;
    if (cesium) {
      var m = Cesium.Transforms.eastNorthUpToFixedFrame(pos, ELL);
      east = Cesium.Matrix4.getColumn(m, 0, new Cesium.Cartesian4());
      north = Cesium.Matrix4.getColumn(m, 1, new Cesium.Cartesian4());
      east = new Cesium.Cartesian3(east.x, east.y, east.z);
      north = new Cesium.Cartesian3(north.x, north.y, north.z);
    } else {
      var lat = Cesium.Math.toDegrees(ELL.cartesianToCartographic(pos).latitude);
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
    var shift = anglesAt(p.pos, true).heading - anglesAt(p.pos, false).heading;
    var hpr = new Cesium.HeadingPitchRange(Cesium.Math.toRadians(heading + shift), Cesium.Math.toRadians(pitch), p.range);
    if (duration) {
      viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(p.pos, 0), { offset: hpr, duration: duration });
    } else {
      viewer.camera.lookAt(p.pos, hpr);
      viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    }
  }

  // 처음 자리 — 격자 가운데(3031 의 500·1 000 km — 남위 80°, 동경 27°)를 북쪽 바다에서 남쪽으로 비스듬히 본다
  function viewHome(fly) {
    var target = new Cesium.BoundingSphere(Cesium.Cartesian3.fromDegrees(27, -81, 0), 1);
    var offset = new Cesium.HeadingPitchRange(Math.PI, Cesium.Math.toRadians(-30), 2.7e6);
    if (fly) viewer.camera.flyToBoundingSphere(target, { offset: offset, duration: 1.5 });
    else { viewer.camera.viewBoundingSphere(target, offset); viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY); }
  }
  viewHome(false);
  $("tool-home").addEventListener("click", function () { viewHome(true); });
  // 남극점 — 극 위에서 곧장 내려다본다. 경도 0° 가 위(2D 의 3031 과 같은 방향)
  $("tool-pole").addEventListener("click", function () { flyGlobe(0, -89.9, 6.2e6, 1.5); });
  // 북쪽 위 — 가운데 점 위로 올라가 곧장 내려다본다
  $("tool-top").addEventListener("click", function () {
    var p = pivot(true);
    if (p) { orbit(p, 0, -90, 0.8); return; }
    var c = cameraLL();
    if (c) flyGlobe(c.lon, c.lat, c.h, 0.8);
  });
  // 평면 — 2D 남극 탭으로. 연대는 열쇠(`gsm.paleoage`)가 넘긴다
  $("tool-mode").addEventListener("click", function () {
    save("gsm.region", "antarctica");
    location.href = $("to2d").href;
  });

  // 방위 단추(나침반) — 바늘이 지구의 북쪽을 가리킨다. 누르면 기울기는 두고 북쪽을 위로 돌린다
  var needle = $("compass-needle"), poseOut = $("pose"), topBtn = $("tool-top"), compassBtn = $("tool-compass");
  compassBtn.addEventListener("click", function () {
    var p = pivot(true);
    if (!p) return;
    orbit(p, 0, anglesAt(p.pos, false).pitch, 0.6);
  });

  // 자전축 — 지구 고정 좌표의 Z 축. 지구 속 토막은 흐린 끊은 선으로 비친다. 가까이 가면(카메라 4 800 km 밑) 치운다
  // 끝의 이름은 온 지구와 달리 구에 가린다 — 남극점 위에서 곧장 내려다보면 뒤쪽 "북극점" 이 "남극점" 에 겹쳤다
  var AXIS_OUT = 6371008.8 * 1.45, AXIS_NEAR = 4800000, WHITE_A = Cesium.Color.WHITE;
  var axisOn = saved("gsm.paleo3d.axis", "on") !== "off", axisFar = true;
  var axisEntities = [
    viewer.entities.add({
      polyline: { positions: [new Cesium.Cartesian3(0, 0, -AXIS_OUT), new Cesium.Cartesian3(0, 0, AXIS_OUT)],
                  arcType: Cesium.ArcType.NONE, width: 2.5, material: WHITE_A.withAlpha(0.95),
                  depthFailMaterial: new Cesium.PolylineDashMaterialProperty({ color: WHITE_A.withAlpha(0.5), dashLength: 12 }) },
    }),
    viewer.entities.add({
      position: Cesium.Cartesian3.ZERO,
      point: { pixelSize: 6, color: WHITE_A.withAlpha(0.7), outlineColor: Cesium.Color.BLACK, outlineWidth: 1,
               disableDepthTestDistance: Number.POSITIVE_INFINITY },
    }),
  ].concat([[1, T("북극점")], [-1, T("남극점")]].reduce(function (all, end) {
    all.push(viewer.entities.add({
      position: new Cesium.Cartesian3(0, 0, end[0] * ELL.minimumRadius),
      point: { pixelSize: 8, color: WHITE_A, outlineColor: Cesium.Color.BLACK, outlineWidth: 2 },
    }));
    all.push(viewer.entities.add({
      position: new Cesium.Cartesian3(0, 0, end[0] * AXIS_OUT),
      label: { text: end[1], font: "600 12px system-ui, sans-serif", fillColor: WHITE_A,
               outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
               verticalOrigin: end[0] > 0 ? Cesium.VerticalOrigin.BOTTOM : Cesium.VerticalOrigin.TOP,
               pixelOffset: new Cesium.Cartesian2(0, end[0] > 0 ? -4 : 4) },
    }));
    return all;
  }, []));
  function applyAxis() {
    axisEntities.forEach(function (e) { e.show = axisOn && axisFar; });
    $("tool-axis").classList.toggle("on", axisOn);
    $("tool-axis").setAttribute("aria-pressed", axisOn ? "true" : "false");
  }
  $("tool-axis").addEventListener("click", function () {
    axisOn = !axisOn;
    save("gsm.paleo3d.axis", axisOn ? "on" : "off");
    applyAxis();
  });
  applyAxis();

  // 시점이 바뀔 때마다 — 바늘·기울기·방위 읽기, 할 일이 없는 단추는 흐리게, 자전축은 가까우면 치운다
  var lastView = new Cesium.Matrix4();
  scene.postRender.addEventListener(function () {
    if (Cesium.Matrix4.equalsEpsilon(lastView, viewer.camera.viewMatrix, 1e-9)) return;
    Cesium.Matrix4.clone(viewer.camera.viewMatrix, lastView);
    var c = cameraLL(), far = !c || c.h > AXIS_NEAR;
    if (far !== axisFar) { axisFar = far; applyAxis(); }
    var p = pivot(false);
    if (!p) { poseOut.textContent = ""; topBtn.disabled = compassBtn.disabled = false; return; }
    var a = anglesAt(p.pos, false);
    needle.setAttribute("transform", "rotate(" + (-a.heading).toFixed(1) + " 12 12)");
    var north = Math.min(a.heading, 360 - a.heading) < 0.5;
    compassBtn.disabled = north;
    topBtn.disabled = north && 90 + a.pitch < 0.5;
    poseOut.textContent = T("기울기 {tilt}° · 방위 {heading}°", { tilt: Math.round(90 + a.pitch), heading: Math.round(a.heading) % 360 });
  });

  // 좌표 — 손 밑의 위경도
  var readout = $("readout");
  new Cesium.ScreenSpaceEventHandler(scene.canvas).setInputAction(function (movement) {
    var ray = viewer.camera.getPickRay(movement.endPosition);
    var at = (ray && scene.globe.pick(ray, scene)) || viewer.camera.pickEllipsoid(movement.endPosition, ELL);
    if (!at) { readout.textContent = ""; return; }
    var ll = ELL.cartesianToCartographic(at);
    readout.textContent = T("위도 {lat}° · 경도 {lon}°", { lat: Cesium.Math.toDegrees(ll.latitude).toFixed(4),
                                                         lon: Cesium.Math.toDegrees(ll.longitude).toFixed(4) });
  }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

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
