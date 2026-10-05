/* 대돌여지도 3D (devlog 015 — 059 에서 실험을 벗었다).
 *
 * VWorld 3D 엔진이 아니라 **MapLibre + 공개 표고 타일**로 짓는다. VWorld 3D 는
 * 지형을 받아 오는 창구(XDServer `Layer=dem`)가 닫혀 있다(004, 2026-09-27 에도).
 * 표고는 AWS Terrain Tiles(Terrarium 인코딩, 열쇠 없음)이고, 지질도는 2D 와
 * 같은 서버 중계(`wms/`)를 탄다 — 인증키도 캐시도 그대로다.
 */
(function () {
  "use strict";

  var BASE = location.pathname.replace(/3d\/?$/, "");
  var vworldKey = JSON.parse(document.getElementById("vworld-key").textContent || '""');

  // 영어판 — 2D(`map.js`)와 같은 꼴이다. 실험 화면이 본 화면의 속을 끌어다 쓰지 않게 따로 둔다
  var LANG = document.documentElement.lang === "en" ? "en" : "ko";
  var I18N = JSON.parse((document.getElementById("i18n-data") || {}).textContent || "{}");
  function T(text, vars) {
    var out = (LANG === "en" && I18N[text]) || text;
    if (vars) out = out.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; });
    return out;
  }
  var DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

  function wmsTiles(layer) {
    return [BASE + "wms/?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&FORMAT=image/png" +
            "&TRANSPARENT=true&STYLES=&CRS=EPSG:3857&WIDTH=512&HEIGHT=512" +
            "&LAYERS=" + encodeURIComponent(layer) + "&BBOX={bbox-epsg-3857}"];
  }

  // 지역 — 머리의 스크립트가 `<html data-region>` 에 달았다(2D 의 3D 단추가 넘긴다). 자리를
  // 기억하는 열쇠도 2D 처럼 지역마다다(`map.js` 의 stateKey) — 한국만 예전 열쇠 그대로
  var REGION = document.documentElement.getAttribute("data-region") || "korea";
  var VIEW_KEY = REGION === "korea" ? "gsm.view" : "gsm.view." + REGION;

  /** 2D 에서 보던 자리. 같은 브라우저 저장소를 읽는다. 없으면 설악산. */
  function startView() {
    var q = new URLSearchParams(location.search);
    // 2D(OpenLayers)의 줌은 256 px 타일 기준이고 MapLibre 는 512 px 기준이라 한 단계 작다.
    // 주소·저장소의 줌은 2D 의 것이므로 1 을 빼서 쓰고, 적을 때 1 을 더한다
    if (q.get("lat") && q.get("lon")) {
      return { center: [+q.get("lon"), +q.get("lat")], zoom: +(q.get("z") || 13) - 1 };
    }
    try {
      var v = JSON.parse(localStorage.getItem(VIEW_KEY) || "null");
      // 극지 탭이 적은 줌은 극 평사도법의 줌이라 3D(메르카토르)에 그대로 쓰지 않는다
      // 캐나다 람베르트(3978, 캐나다·미국 탭)는 범위를 3857 과 같은 너비로 잡아 줌이 같은 해상도다 — 그대로 쓴다 (wetherilli 210)
      if (v && isFinite(v.lon) && (!v.proj || v.proj === "EPSG:3857" || v.proj === "EPSG:3978")) {
        return { center: [v.lon, v.lat], zoom: Math.max(8, v.zoom) - 1 };
      }
    } catch (e) { /* 사생활 모드 */ }
    return { center: [128.465, 38.119], zoom: 12 };
  }

  var start = startView();
  var select = document.getElementById("layer3d");
  // 2D 에서 켜 둔 맨 위 레이어를 주소로 받는다(스발바르면 NPI 지질 단위, 남극이면 GeoMAP).
  // 3D 목록에 없으면 그 지역의 첫 레이어, 그것도 없으면 25만
  var asked = new URLSearchParams(location.search).get("layer");
  // 목록은 **지금 지역의 레이어군만** 남긴다 (050). 서버는 모든 지역의 것을 싣는다 — 남극을 보는데 한국
  // 지질도가 뜨지 않게. 묶음 탭은 품은 지역들이다(2D 의 `REGIONS.*.includes` 와 같다)
  var BUNDLES = { arctic: ["greenland", "svalbard", "jan_mayen", "arctic_ocean", "fennoscandia", "iceland"], eastasia: ["korea", "japan", "china", "taiwan", "mongolia"],
                  europe: ["uk", "ireland", "france", "germany", "spain", "portugal", "italy", "switzerland", "austria", "poland", "netherlands", "belgium"], south_america: ["colombia", "ecuador", "peru", "brazil", "paraguay", "uruguay", "argentina"], north_america: ["canada", "usa", "mexico"],
                  oceania: ["australia", "new_zealand", "new_caledonia", "french_polynesia"], southeast_asia: ["thailand", "malaysia", "indonesia", "philippines"],
                  central_america: ["nicaragua", "panama", "dominican_republic", "caribbean"] };
  var ALLOWED = BUNDLES[REGION] || [REGION];
  [].slice.call(select.querySelectorAll("optgroup")).forEach(function (g) {
    if (ALLOWED.indexOf(g.getAttribute("data-region")) < 0) g.remove();
  });
  if (!select.options.length) {
    // 3D 로 얹을 지질 레이어가 없는 지역(극지 투영으로만 받는 것) — 지형만 본다
    var none = document.createElement("option");
    none.value = "";
    none.textContent = T("이 지역에는 3D 로 얹을 지질 레이어가 없다");
    select.appendChild(none);
    select.disabled = true;
  }
  // 2D 가 넘긴 레이어가 목록에 있으면 그것, 없으면 이 지역의 첫 레이어
  select.value = asked && select.querySelector('option[value="' + asked.replace(/"/g, "") + '"]')
    ? asked : select.options[0].value;

  /** "지질 레이어" 의 소스. 대개 `wms/` 의 3857 타일이고, 남극 GeoMAP 은 우리가 굽는 3031 타일을
   *  서버가 3857 로 다시 편 것(`warp/geomap/`, 040)이다. GeoMAP 은 남위 60° 남쪽만 덮고, 대륙을
   *  한눈에 볼 줌 3 부터 받는다. 출처는 목록이 적은 것(`data-attribution`)을 쓴다 */
  function geologySource(name) {
    if (!name) {
      // 얹을 것이 없다 — 아무 데도 닿지 않는 네모라 타일을 묻지 않는다
      return { type: "raster", tiles: [BASE + "wms/"], tileSize: 512, bounds: [0, 0, 0.000001, 0.000001] };
    }
    var opt = [].filter.call(select.options, function (o) { return o.value === name; })[0];
    var attribution = (opt && opt.getAttribute("data-attribution")) || "© 한국지질자원연구원";
    if (opt && opt.getAttribute("data-upstream") === "geomap") {
      return { type: "raster", tileSize: 512, minzoom: 3, maxzoom: 17, bounds: [-180, -85.06, 180, -60],
               tiles: [BASE + "warp/geomap/" + name + "/{z}/{x}/{y}@2x.png"], attribution: attribution };
    }
    // IBCSO 자료 출처·ADMAP 자력 이상 — 우리가 자른 3031 판을 서버가 3857 로 편 것 (wetherilli 335)
    if (opt && (name === "ibcso:tid" || name === "admap:anomaly")) {
      return { type: "raster", tileSize: 512, minzoom: 2, maxzoom: 17,
               bounds: [-180, -85.06, 180, name === "ibcso:tid" ? -50 : -60],
               tiles: [BASE + "warp/" + name.replace(":", "/") + "/{z}/{x}/{y}@2x.png"], attribution: attribution };
    }
    var src = { type: "raster", tiles: wmsTiles(name), tileSize: 512, attribution: attribution };
    var tiles = opt && opt.getAttribute("data-tiles");
    if (tiles) {
      // 일본 GSJ·지리원 주제 타일 — 3857 z/x/y 256 px 를 그대로 받는다(wetherilli 187). 줌은 타일의 줌이라 2D 의 것 그대로다.
      // 그보다 멀면 묻지 않고, 그보다 가까우면 늘린다
      src = { type: "raster", tiles: [/^https?:/.test(tiles) ? tiles : BASE + tiles], tileSize: 256, attribution: attribution };
      if (opt.getAttribute("data-min")) src.minzoom = +opt.getAttribute("data-min");
      if (opt.getAttribute("data-max")) src.maxzoom = +opt.getAttribute("data-max");
    }
    // 제 범위 밖은 묻지 않는다 — 2D 의 묶음 탭과 같다(0.5° 넉넉히, 024). 유럽 탭에서 스페인 판이 영국 바다를 묻지 않게
    var bbox = opt && opt.getAttribute("data-bbox");
    if (bbox) {
      var b = bbox.split(",").map(Number);
      if (b.length === 4 && b.every(isFinite)) src.bounds = [Math.max(-180, b[0] - 0.5), Math.max(-85, b[1] - 0.5),
                                                            Math.min(180, b[2] + 0.5), Math.min(85, b[3] + 0.5)];
    }
    return src;
  }

  /** "지질 레이어" 의 한 겹. 가까이서만(BGS 1:5만) 또는 멀리서만(BRGM 스캔) 그리는 레이어는 2D 처럼 그 밖에서 숨긴다.
   *  2D(256 px 기준)의 줌은 MapLibre(512 px 기준)보다 하나 크고, 2D 는 반 단계 넉넉히 보인다(`makeLayer`). z/x/y 원천은
   *  원천의 `minzoom` 이 이미 막는다 */
  function geologyLayer(name, opacity) {
    var layer = { id: "kigam", type: "raster", source: "kigam", paint: { "raster-opacity": opacity } };
    var opt = [].filter.call(select.options, function (o) { return o.value === name; })[0];
    if (opt && !opt.getAttribute("data-tiles")) {
      if (opt.getAttribute("data-min")) layer.minzoom = Math.max(0, +opt.getAttribute("data-min") - 1.5);
      if (opt.getAttribute("data-last")) layer.maxzoom = +opt.getAttribute("data-last") - 0.5;
    }
    return layer;
  }

  var sources = {
    // 표고는 256 px 타일을 512 로 여겨 **한 단계 거칠게** 부른다 — 타일 수가 4 분의 1 이다.
    // 스발바르를 z13 으로 열면 PGC 타일이 96 장, 빈 캐시에서 55 초였다(2026-09-29). 한 픽셀이
    // 땅 수 m–수십 m 라 지형에는 넉넉하다
    dem: { type: "raster-dem", tiles: [DEM], encoding: "terrarium", tileSize: 512, maxzoom: 15,
           attribution: "Terrain: Mapzen/AWS Terrain Tiles · 국토지리원 · ArcticDEM/REMA © PGC (CC BY 4.0) · " +
                        "IBCSO v2 (Dorschel et al., 2022, CC BY 4.0)" },
    shade: { type: "raster-dem", tiles: [DEM], encoding: "terrarium", tileSize: 512, maxzoom: 15 },
    kigam: geologySource(select.value),
  };
  var layers = [{ id: "bg", type: "background", paint: { "background-color": "#e8e0d2" } }];
  // VWorld 를 곧장 받지 못하면(사내 VPN 이 끊는다) 서버를 거친다 — 평면 지도와 같다 (033)
  var VWORLD = "https://api.vworld.kr/req/wmts/1.0.0/" + encodeURIComponent(vworldKey);
  if (vworldKey) {
    sources.base = { type: "raster", tileSize: 256, maxzoom: 19, attribution: "© VWorld",
      tiles: [VWORLD + "/white/{z}/{y}/{x}.png"],
      // VWorld 는 한반도 둘레(대략 동경 120–134°, 북위 30–44°) 밖에서 그림 대신 XML 오류를 준다 —
      // 스발바르에서 "소스 이미지를 디코드하지 못했다" 가 떴다(2026-09-29). 그 밖은 묻지 않는다
      bounds: [120, 30, 134, 44] };
    layers.push({ id: "base", type: "raster", source: "base" });
  }
  // 남극은 IBCSO v2 를 배경으로 깐다(051) — 우리가 잘라 둔 3031 타일을 서버가 3857 로 편 것(`warp/ibcso/`).
  // 판은 500 m 라 줌 8 넘어서는 브라우저가 늘린다. 고른 판은 지형도 따른다(아래 `demRequest`)
  var baseSel = document.getElementById("base3d");
  var IBCSO_KEY = "gsm.3d.ibcso";
  var ibcsoKind = "";
  if (REGION === "antarctica" && baseSel) {
    try { ibcsoKind = localStorage.getItem(IBCSO_KEY); } catch (e) { ibcsoKind = null; }
    if (ibcsoKind === null || !baseSel.querySelector('option[value="' + ibcsoKind.replace(/"/g, "") + '"]')) {
      ibcsoKind = "ice";
    }
    baseSel.value = ibcsoKind;
  }
  function ibcsoSource(kind) {
    return { type: "raster", tileSize: 512, minzoom: 2, maxzoom: 8, bounds: [-180, -85.06, 180, -50],
             tiles: [BASE + "warp/ibcso/" + kind + "/{z}/{x}/{y}@2x.png"],
             attribution: "IBCSO v2 (Dorschel et al., 2022, doi:10.1594/PANGAEA.937574, CC BY 4.0)" };
  }
  if (ibcsoKind) {
    sources.ibcso = ibcsoSource(ibcsoKind);
    layers.push({ id: "ibcso", type: "raster", source: "ibcso" });
  }
  // 지형의 판 — 빙저를 고르면 표고 타일 주소에 `?bed` 를 달아 `demRequest` 가 `dem/bed/` 로 돌린다.
  // 주소가 바뀌어야 MapLibre 가 받아 둔 타일을 버리고 새로 받는다
  function demTiles() { return [DEM + (ibcsoKind === "bed" ? "?bed" : "")]; }
  sources.dem.tiles = sources.shade.tiles = demTiles();
  layers.push({ id: "shade", type: "hillshade", source: "shade",
                paint: { "hillshade-exaggeration": 0.5, "hillshade-shadow-color": "#3f2712" } });
  layers.push(geologyLayer(select.value, 0.7));

  // 이름표의 글꼴 조각 — 로마자·숫자(0–511)만 담았다(`vendor/maplibre/glyphs/`, OFL).
  // 한글·한자는 조각 없이 브라우저 글꼴이 그린다(`localIdeographFontFamily`). P02 §7
  var GLYPHS = JSON.parse((document.getElementById("glyphs-url") || {}).textContent || '""');

  // 일본 자리의 표고 타일은 국토지리원 것(10 m)을 서버가 Terrarium 꼴로 바꿔 준다(`dem/`,
  // devlog 031). AWS(SRTM 30 m)보다 촘촘하다 — 후지산을 3 774 m 로 읽는다(AWS 3 754 m).
  // 경계는 서버의 `elevation.in_japan` 과 같다. 국토지리원 타일은 z14 가 끝이다
  var GSI_MAX_ZOOM = 14;
  var POLAR_LAT = 60;         // 서버의 `elevation.POLAR_LAT`
  var POLAR_MIN_ZOOM = 11;    // 서버의 `elevation.POLAR_MIN_ZOOM` — 멀리서는 AWS(브라우저가 곧장, 빠르다)
  function inJapan(lat, lon) {
    if (!(lon >= 122.9 && lon <= 154.0 && lat >= 20.0 && lat <= 45.6)) return false;
    if (lon < 129.0) return false;
    if (lat > 35.0 && lon < 129.7) return false;                       // 한반도 동남해안
    if (lon >= 130.7 && lon <= 131.95 && lat >= 37.1 && lat <= 37.6) return false;   // 울릉도·독도
    return true;
  }
  var IBCSO_NORTH = -50;      // 서버의 `elevation.IBCSO_NORTH`
  function demRequest(url) {
    var m = /\/terrarium\/(\d+)\/(\d+)\/(\d+)\.png(\?bed)?$/.exec(url);
    if (!m) return undefined;
    var z = +m[1], x = +m[2], y = +m[3], n = Math.pow(2, z), bed = !!m[4];
    var lon = (x + 0.5) / n * 360 - 180;
    var lat = Math.atan(Math.sinh(Math.PI * (1 - 2 * (y + 0.5) / n))) * 180 / Math.PI;
    var path = z + "/" + x + "/" + y + ".png";
    // 남위 50° 남쪽은 줌과 상관없이 서버다 — IBCSO 500 m 해저(051), 가까이서는 REMA 2 m(032). AWS 는
    // 남빙양이 옛 GEBCO 라 해저가 뭉개지고, 빙붕 밑을 모른다
    if (lat <= IBCSO_NORTH) return { url: location.origin + BASE + "dem/" + (bed ? "bed/" : "") + path };
    // 위도 60° 너머는 PGC ArcticDEM 2 m 를 서버가 옮겨 준다(032). AWS 는 여기서 이음매가
    // 계단처럼 드러나고 결이 뭉개진다
    var ours = (lat >= POLAR_LAT && z >= POLAR_MIN_ZOOM) || (z <= GSI_MAX_ZOOM && inJapan(lat, lon));
    if (ours) return { url: location.origin + BASE + "dem/" + path };
    // 빙저를 골랐어도 남극 밖은 AWS 그대로다 — 붙여 둔 `?bed` 를 떼고 보낸다
    return bed ? { url: url.replace(/\?bed$/, "") } : undefined;
  }

  var map = new maplibregl.Map({
    container: "map3d",
    // 바꿀 것이 없으면 아무것도 돌려주지 않는다 — `{url}` 을 돌려주면 지질도 타일의 상대 주소가
    // 풀리지 않아 요청이 나가지 않았다(2026-09-29, 스발바르에서 보았다)
    transformRequest: function (url, kind) { return kind === "Tile" ? demRequest(url) : undefined; },
    style: { version: 8, sources: sources, layers: layers,
             glyphs: GLYPHS ? location.origin + GLYPHS + "{fontstack}/{range}.pbf" : undefined },
    localIdeographFontFamily: "'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif",
    center: start.center, zoom: start.zoom, pitch: 60, bearing: -20, maxPitch: 80,
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new maplibregl.ScaleControl(), "bottom-left");
  map.on("load", function () {
    map.setTerrain({ source: "dem", exaggeration: 1.5 });
    renderCustom();
    renderPointSets();
    window.__gsm3dReady = true;
    if (vworldKey) probeVworld();
  });

  /** 한 장을 곧장 받아 보고, 연결이 끊기면 배경을 `vworld/` 로 돌린다 (`map.js` 와 같다). */
  function probeVworld() {
    var ctl = new AbortController();
    var timer = setTimeout(function () { ctl.abort(); }, 8000);
    fetch(VWORLD + "/Base/7/50/109.png", { cache: "no-store", signal: ctl.signal })
      .then(function () { clearTimeout(timer); }, function () {
        clearTimeout(timer);
        // `setTiles` 는 주소만 바꾸고 끊겼던 타일을 다시 받지 않는다 — 소스째 새로 얹는다
        var spec = sources.base;
        spec.tiles = [location.origin + BASE + "vworld/white/{z}/{y}/{x}.png"];
        map.removeLayer("base");
        map.removeSource("base");
        map.addSource("base", spec);
        map.addLayer({ id: "base", type: "raster", source: "base" }, "shade");
      });
  }
  window.__gsm3d = map;

  // 레이어를 바꾸면 소스째 새로 얹는다 — 받는 곳(`wms/`·`warp/`)과 줌 범위·출처가 레이어마다 달라
  // `setTiles` 로는 모자란다. 쌓인 차례와 투명도는 그대로 둔다
  select.addEventListener("change", function () {
    var order = map.getStyle().layers.map(function (l) { return l.id; });
    var before = order[order.indexOf("kigam") + 1];
    map.removeLayer("kigam");
    map.removeSource("kigam");
    map.addSource("kigam", geologySource(select.value));
    map.addLayer(geologyLayer(select.value, document.getElementById("opacity3d").value / 100), before);
  });
  document.getElementById("opacity3d").addEventListener("input", function () {
    map.setPaintProperty("kigam", "raster-opacity", this.value / 100);
    document.getElementById("op-num").textContent = this.value + "%";
  });
  // 배경을 바꾸면 지형도 같은 판으로 — 얼음 위 배경에 기반암 땅이 서거나 그 거꾸로면 둘이 어긋난다
  function setIbcso(kind) {
    ibcsoKind = kind;
    try { localStorage.setItem(IBCSO_KEY, kind); } catch (e) { /* 사생활 모드 */ }
    if (map.getLayer("ibcso")) map.removeLayer("ibcso");
    if (map.getSource("ibcso")) map.removeSource("ibcso");
    if (kind) {
      map.addSource("ibcso", ibcsoSource(kind));
      map.addLayer({ id: "ibcso", type: "raster", source: "ibcso" }, "shade");
    }
    map.getSource("dem").setTiles(demTiles());
    map.getSource("shade").setTiles(demTiles());
    document.getElementById("base3d-hint").hidden = kind !== "bed";
  }
  if (baseSel) {
    baseSel.addEventListener("change", function () { setIbcso(baseSel.value); });
    document.getElementById("base3d-hint").hidden = ibcsoKind !== "bed";
  }
  document.getElementById("exag3d").addEventListener("input", function () {
    var x = this.value / 10;
    map.setTerrain({ source: "dem", exaggeration: x });
    document.getElementById("ex-num").textContent = "×" + x.toFixed(1);
  });
  document.getElementById("shade3d").addEventListener("change", function () {
    map.setLayoutProperty("shade", "visibility", this.checked ? "visible" : "none");
  });
  // 2D 로 돌아갈 때 지금 자리를 가지고 간다 — 그 지역의 열쇠에, 메르카토르 줌이라고 적어서.
  // 전에는 늘 한국의 열쇠에 적어, 스발바르 3D 에서 돌아가면 한국 탭이 스발바르로 열렸다.
  // 극지 탭은 적힌 투영을 보고 줌을 옮겨 센다(`map.js` 의 carryZoom)
  map.on("moveend", function () {
    var c = map.getCenter();
    try {
      localStorage.setItem(VIEW_KEY, JSON.stringify({ lon: +c.lng.toFixed(5), lat: +c.lat.toFixed(5),
                                                      zoom: +(map.getZoom() + 1).toFixed(2), proj: "EPSG:3857" }));
    } catch (e) { /* 사생활 모드 */ }
  });

  // ── 커스텀 지질도 ────────────────────────────────────────────────
  //
  // 한반도 지질도(스캔·음영·민판)는 5179·5181 격자라 MapLibre 가 못 받는다 — 서버가
  // 3857 로 다시 편 타일(`warp/`)을 얹는다. 암맥(026)은 모양 한 덩이를 받아 암석 갈래로
  // 칠한다. 지질 레이어 위, 점묶음 아래에 둔다. 켠 것은 이 브라우저에 기억한다.

  var custom = JSON.parse((document.getElementById("custom-data") || {}).textContent || "[]");
  var CUSTOM_KEY = "gsm.3d.custom";
  //: 암맥의 색 — 2D(`map.js` 의 DIKE_CLASSES)와 같게 둔다
  var DIKE_COLORS = ["match", ["get", "cls"], "acid", "#c2185b", "intermediate", "#ef6c00",
                     "basic", "#1b5e20", "vein", "#1565c0", "#616161"];
  var customLabels = {};     // 레이어 → 팝업 이름표 (서버가 `labels` 로 준다)

  function customOn() {
    try { return JSON.parse(localStorage.getItem(CUSTOM_KEY) || "[]") || []; } catch (e) { return []; }
  }
  function setCustomOn(name, on) {
    var names = customOn().filter(function (n) { return n !== name; });
    if (on) names.push(name);
    try { localStorage.setItem(CUSTOM_KEY, JSON.stringify(names)); } catch (e) { /* 사생활 모드 */ }
  }
  function customId(row) { return "cu-" + row.name.replace(/[^\w]/g, "-"); }
  function customLayerIds(row) {
    var id = customId(row);
    return row.kind === "points" ? [id + "-line", id + "-point"] : [id];
  }
  /** 점묶음보다 밑에 깐다 — 먼저 생긴 점묶음 레이어가 있으면 그 앞에 끼운다. */
  function beneathPointSets() {
    var first = map.getStyle().layers.filter(function (l) { return l.id.indexOf("ps-") === 0; })[0];
    return first ? first.id : undefined;
  }

  function showCustom(row) {
    var id = customId(row);
    if (map.getSource(id)) {
      customLayerIds(row).forEach(function (l) { map.setLayoutProperty(l, "visibility", "visible"); });
      return;
    }
    var before = beneathPointSets();
    if (row.kind === "points") {
      map.addSource(id, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      fetch(BASE + "points/?layer=" + encodeURIComponent(row.name) + "&lang=" + LANG)
        .then(function (r) { return r.json(); })
        .then(function (d) {
          customLabels[row.name] = d.labels || {};
          map.getSource(id).setData({ type: "FeatureCollection", features: d.features || [] });
        });
      map.addLayer({ id: id + "-line", type: "line", source: id,
                     filter: ["==", ["geometry-type"], "LineString"],
                     paint: { "line-color": DIKE_COLORS, "line-width": 2.5 } }, before);
      map.addLayer({ id: id + "-point", type: "circle", source: id,
                     filter: ["==", ["geometry-type"], "Point"],
                     paint: { "circle-radius": 3.5, "circle-color": DIKE_COLORS,
                              "circle-stroke-color": "#fff", "circle-stroke-width": 1,
                              "circle-pitch-alignment": "viewport" } }, before);
      return;
    }
    map.addSource(id, { type: "raster", tileSize: 256, minzoom: 5, maxzoom: 17,
                        tiles: [BASE + "warp/" + row.name.replace(":", "/") + "/{z}/{x}/{y}.png"] });
    map.addLayer({ id: id, type: "raster", source: id, paint: { "raster-opacity": 0.8 } }, before);
  }

  function hideCustom(row) {
    if (!map.getSource(customId(row))) return;
    customLayerIds(row).forEach(function (l) { map.setLayoutProperty(l, "visibility", "none"); });
  }

  function renderCustom() {
    var host = document.getElementById("custom3d");
    if (!host || !custom.length) return;
    document.getElementById("custom3d-head").hidden = false;
    host.innerHTML = "";
    var on = customOn();
    custom.forEach(function (row) {
      var shown = on.indexOf(row.name) >= 0;
      if (shown) showCustom(row); else hideCustom(row);
      var li = document.createElement("li");
      var box = document.createElement("input");
      box.type = "checkbox";
      box.checked = shown;
      box.addEventListener("change", function () {
        setCustomOn(row.name, box.checked);
        renderCustom();
      });
      var name = document.createElement("span");
      name.className = "ps-name";
      name.textContent = row.title;
      name.title = row.title;
      li.append(box, name);
      host.appendChild(li);
    });
  }

  // ── 내 자료(점묶음) — P02 ────────────────────────────────────────
  //
  // 서버의 `pointsets/<번호>/geojson/` 을 그대로 얹는다. 점은 둥근 점으로 지형 위에
  // 앉히고(세우지 않는다), 선·면은 지형 표면에 입힌다. 켜고 끈 것은 2D 와 같은 열쇠
  // (`gsm.pointsets.off`)에 둔다. **켠 것만 받는다** — 끈 점묶음은 소스도 만들지 않는다.

  var pointsets = JSON.parse((document.getElementById("pointset-data") || {}).textContent || "[]");
  var PS_OFF_KEY = "gsm.pointsets.off";
  //: 켠 점이 이보다 많으면 패널에 한 줄 띄운다. 막지는 않는다
  var MANY_POINTS = 20000;
  var loaded = {};            // 번호 → 받은 GeoJSON (범위 맞추기에 쓴다)

  function offIds() {
    try { return JSON.parse(localStorage.getItem(PS_OFF_KEY) || "[]") || []; } catch (e) { return []; }
  }
  function setOff(id, off) {
    var ids = offIds().filter(function (x) { return x !== id; });
    if (off) ids.push(id);
    try { localStorage.setItem(PS_OFF_KEY, JSON.stringify(ids)); } catch (e) { /* 사생활 모드 */ }
  }
  function isOn(ps) { return offIds().indexOf(ps.id) < 0; }

  //: 이름표를 다는 줌 — 2D 의 `LABEL_MIN_ZOOM` 과 같다. 멀리서는 글자가 점을 덮는다
  var LABEL_MIN_ZOOM = 11;

  function layerIds(ps) {
    var p = "ps-" + ps.id + "-";
    var ids = [p + "fill", p + "edge", p + "line", p + "point"];
    return GLYPHS ? ids.concat([p + "label", p + "lname"]) : ids;
  }

  function addPointSet(ps) {
    var id = "ps-" + ps.id;
    if (map.getSource(id)) {
      layerIds(ps).forEach(function (l) { map.setLayoutProperty(l, "visibility", "visible"); });
      return;
    }
    var url = BASE + "pointsets/" + ps.id + "/geojson/";
    map.addSource(id, { type: "geojson", data: url });
    fetch(url).then(function (r) { return r.json(); }).then(function (d) { loaded[ps.id] = d; })
      .catch(function () { /* 범위 맞추기만 못 한다 */ });
    var polygon = ["match", ["geometry-type"], ["Polygon", "MultiPolygon"], true, false];
    var line = ["match", ["geometry-type"], ["LineString", "MultiLineString"], true, false];
    map.addLayer({ id: id + "-fill", type: "fill", source: id, filter: polygon,
                   paint: { "fill-color": ps.color, "fill-opacity": 0.25 } });
    map.addLayer({ id: id + "-edge", type: "line", source: id, filter: polygon,
                   paint: { "line-color": ps.color, "line-width": 2 } });
    map.addLayer({ id: id + "-line", type: "line", source: id, filter: line,
                   layout: { "line-join": "round", "line-cap": "round" },
                   paint: { "line-color": ps.color, "line-width": 3 } });
    // 2D 의 점과 같게 — 점묶음 색, 흰 테 1.5 px. 늘 정면을 본다(`viewport`)
    map.addLayer({ id: id + "-point", type: "circle", source: id,
                   filter: ["==", ["geometry-type"], "Point"],
                   paint: { "circle-radius": 5, "circle-color": ps.color,
                            "circle-stroke-color": "#fff", "circle-stroke-width": 1.5,
                            "circle-pitch-alignment": "viewport" } });
    if (!GLYPHS) return;
    // 이름표 — 점·면은 곁에, 선은 선을 따라. 2D 와 같은 먹색에 흰 테
    var text = { "text-color": "#1f1409", "text-halo-color": "#ffffff", "text-halo-width": 1.5 };
    map.addLayer({ id: id + "-label", type: "symbol", source: id, minzoom: LABEL_MIN_ZOOM,
                   filter: ["all", ["has", "이름표"], ["!", line]],
                   layout: { "text-field": ["to-string", ["get", "이름표"]], "text-font": ["Noto Sans Regular"],
                             "text-size": 12, "text-anchor": "left", "text-offset": [0.8, 0],
                             "text-optional": true },
                   paint: text });
    map.addLayer({ id: id + "-lname", type: "symbol", source: id, minzoom: LABEL_MIN_ZOOM,
                   filter: ["all", ["has", "이름표"], line],
                   layout: { "text-field": ["to-string", ["get", "이름표"]], "text-font": ["Noto Sans Regular"],
                             "text-size": 12, "symbol-placement": "line" },
                   paint: text });
  }

  function hidePointSet(ps) {
    if (!map.getSource("ps-" + ps.id)) return;
    layerIds(ps).forEach(function (l) { map.setLayoutProperty(l, "visibility", "none"); });
  }

  /** 받은 GeoJSON 의 위경도 범위 `[[서, 남], [동, 북]]`. 비었으면 null. */
  function boundsOf(data) {
    var b = [Infinity, Infinity, -Infinity, -Infinity];
    function walk(c) {
      if (typeof c[0] === "number") {
        b[0] = Math.min(b[0], c[0]); b[1] = Math.min(b[1], c[1]);
        b[2] = Math.max(b[2], c[0]); b[3] = Math.max(b[3], c[1]);
      } else c.forEach(walk);
    }
    (data.features || []).forEach(function (f) { if (f.geometry) walk(f.geometry.coordinates); });
    return isFinite(b[0]) ? [[b[0], b[1]], [b[2], b[3]]] : null;
  }

  function fitPointSet(ps) {
    var go = function (d) {
      var b = boundsOf(d);
      if (b) map.fitBounds(b, { padding: 60, maxZoom: 14, duration: 600 });
    };
    if (loaded[ps.id]) return go(loaded[ps.id]);
    fetch(BASE + "pointsets/" + ps.id + "/geojson/").then(function (r) { return r.json(); })
      .then(function (d) { loaded[ps.id] = d; go(d); });
  }

  function countText(ps) {
    var bits = [T("{n}점", { n: ps.count || 0 })];
    if (ps.lines) bits.push(T("선 {n}", { n: ps.lines }));
    if (ps.polygons) bits.push(T("면 {n}", { n: ps.polygons }));
    if (!ps.count && (ps.lines || ps.polygons)) bits.shift();
    return bits.join(" · ");
  }

  function renderPointSets() {
    var host = document.getElementById("ps3d");
    if (!host) return;
    host.innerHTML = "";
    if (!pointsets.length) {
      var empty = document.createElement("li");
      empty.className = "empty";
      empty.textContent = T("올린 점묶음이 없다 — 2D 에서 올린다");
      host.appendChild(empty);
    }
    var shown = 0;
    pointsets.forEach(function (ps) {
      var on = isOn(ps);
      if (on) { addPointSet(ps); shown += ps.count || 0; } else hidePointSet(ps);
      var li = document.createElement("li");
      var box = document.createElement("input");
      box.type = "checkbox";
      box.checked = on;
      box.addEventListener("change", function () {
        setOff(ps.id, !box.checked);
        renderPointSets();
      });
      var swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = ps.color;
      var name = document.createElement("span");
      name.className = "ps-name";
      name.textContent = ps.name;
      name.title = ps.name + " — " + countText(ps);
      var count = document.createElement("span");
      count.className = "ps-count";
      count.textContent = countText(ps);
      var fit = document.createElement("button");
      fit.type = "button";
      fit.textContent = "⊙";
      fit.title = T("이 자료로 범위를 맞춘다");
      fit.addEventListener("click", function () { fitPointSet(ps); });
      li.append(box, swatch, name, count, fit);
      host.appendChild(li);
    });
    var warn = document.getElementById("ps3d-warn");
    if (warn) {
      warn.hidden = shown <= MANY_POINTS;
      warn.textContent = T("켠 점이 {n}개다 — 지형과 함께 그리면 느릴 수 있다", { n: shown.toLocaleString() });
    }
  }

  // 2D 창에서 켜고 끄면 따라간다
  window.addEventListener("storage", function (e) {
    if (e.key === PS_OFF_KEY && map.isStyleLoaded()) renderPointSets();
  });

  // ── 누르면 속성 — 2D 팝업과 같은 꼴: 머리는 점묶음 이름, 밑에 이름표, 표는 딸린 속성

  function esc(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function psLayers() {
    var ids = [];
    pointsets.forEach(function (ps) {
      if (map.getSource("ps-" + ps.id)) ids = ids.concat(layerIds(ps));
    });
    return ids;
  }

  /** 누를 수 있는 커스텀 레이어(암맥) — 지금 얹혀 있는 것만. */
  function customPickLayers() {
    var ids = [];
    custom.forEach(function (row) {
      if (row.kind === "points" && map.getSource(customId(row))) ids = ids.concat(customLayerIds(row));
    });
    return ids;
  }

  /** 암맥 하나의 팝업 — 서버가 준 이름표(`labels`)대로. 링크는 http·https 만 잇는다. */
  function customPopup(row, props) {
    var labels = customLabels[row.name] || {};
    var html = '<div class="popup3d"><h3>' + esc(row.title) + "</h3><table>";
    Object.keys(labels).forEach(function (k) {
      var v = props[k];
      if (v === undefined || v === null || v === "") return;
      var cell = /^https?:\/\//i.test(String(v))
        ? '<a href="' + esc(v) + '" target="_blank" rel="noopener noreferrer">' + esc(T("열기")) + "</a>"
        : esc(v);
      html += "<tr><th>" + esc(T(labels[k])) + "</th><td>" + cell + "</td></tr>";
    });
    return html + "</table></div>";
  }

  map.on("click", function (e) {
    var layers = psLayers().concat(customPickLayers());
    if (!layers.length) return;
    var pad = 4;
    var hits = map.queryRenderedFeatures([[e.point.x - pad, e.point.y - pad], [e.point.x + pad, e.point.y + pad]],
                                         { layers: layers });
    if (!hits.length) return;
    var f = hits[0];
    if (f.layer.id.indexOf("cu-") === 0) {
      var row = custom.filter(function (r) { return f.layer.id.indexOf(customId(r)) === 0; })[0];
      if (row) {
        new maplibregl.Popup({ maxWidth: "320px" }).setLngLat(e.lngLat)
          .setHTML(customPopup(row, f.properties || {})).addTo(map);
      }
      return;
    }
    var psId = +String(f.layer.id).split("-")[1];
    var ps = pointsets.filter(function (x) { return x.id === psId; })[0] || {};
    var props = f.properties || {};
    var html = '<div class="popup3d"><h3>' + esc(ps.name || T("내 자료")) + "</h3>";
    if (props["이름표"]) html += '<p class="label">' + esc(props["이름표"]) + "</p>";
    var rows = Object.keys(props).filter(function (k) { return k !== "이름표"; });
    if (rows.length) {
      html += "<table>" + rows.map(function (k) {
        return "<tr><th>" + esc(T(k)) + "</th><td>" + esc(props[k]) + "</td></tr>";
      }).join("") + "</table>";
    }
    html += "</div>";
    new maplibregl.Popup({ maxWidth: "320px" }).setLngLat(e.lngLat).setHTML(html).addTo(map);
  });
  map.on("mousemove", function (e) {
    var layers = psLayers().concat(customPickLayers());
    var hit = layers.length && map.queryRenderedFeatures(e.point, { layers: layers }).length;
    map.getCanvas().style.cursor = hit ? "pointer" : "";
  });

  // ── 그림으로 내려받기 ───────────────────────────────────────────
  //
  // 2D 의 "그림"(`map.js` 의 `exportPng`)과 같은 꼴 — 지금 보는 화면 한 장에 밑의 띠를
  // 붙여 **무엇을 봤는지** 적는다. 띠에는 레이어·점묶음·가운데·기울기·방위·지형 과장·
  // 출처·날짜가 들어간다. **축척 막대는 없다** — 기울인 화면은 앞과 뒤의 축척이 달라
  // 막대 하나가 거짓말을 한다.
  //
  // WebGL 캔버스는 그린 뒤 버퍼를 비운다(`preserveDrawingBuffer` 를 켜면 늘 느려진다).
  // 그래서 타일이 다 온 뒤(`idle`) 한 번 더 그리게 하고, **그 `render` 안에서 곧바로**
  // 옮겨 담는다. 팝업·패널은 HTML 이라 담기지 않는다.

  function exportPng() {
    var button = document.getElementById("export3d");
    button.disabled = true;
    map.once("idle", function () {
      map.once("render", function () {
        var canvas;
        try {
          canvas = composeExport();
        } catch (e) {
          button.disabled = false;
          alert(T("그림을 만들지 못했다"));
          return;
        }
        canvas.toBlob(function (blob) {
          button.disabled = false;
          if (!blob) { alert(T("그림을 만들지 못했다")); return; }
          var a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "GSM-3D-" + stampText().replace(/[-: ]/g, "").slice(0, 12) + ".png";
          document.body.appendChild(a);
          a.click();
          setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
        }, "image/png");
      });
      map.triggerRepaint();
    });
    map.triggerRepaint();
  }

  function stampText() {
    var d = new Date();
    function two(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + two(d.getMonth() + 1) + "-" + two(d.getDate()) + " " +
      two(d.getHours()) + ":" + two(d.getMinutes());
  }

  /** 3D 캔버스 + 밑의 띠. 캔버스의 픽셀 그대로 뽑는다(고해상도 화면이면 그만큼 크다). */
  function composeExport() {
    var gl = map.getCanvas();
    var w = gl.clientWidth, h = gl.clientHeight;
    var ratio = gl.width / w;
    var lines = exportLines();
    var lineH = 17, pad = 12;
    var foot = pad * 2 + lineH * lines.length;
    var out = document.createElement("canvas");
    out.width = gl.width;
    out.height = Math.round((h + foot) * ratio);
    var ctx = out.getContext("2d");
    ctx.drawImage(gl, 0, 0);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    // 띠 — 2D 와 같은 색
    ctx.fillStyle = "#faf7f1";
    ctx.fillRect(0, h, w, foot);
    ctx.fillStyle = "#3f2712";
    ctx.fillRect(0, h, w, 1);
    ctx.textBaseline = "top";
    lines.forEach(function (line, i) {
      ctx.font = (i === 0 ? "bold 14px " : "12px ") + "sans-serif";
      ctx.fillStyle = i === 0 ? "#1f1409" : "#3f3228";
      ctx.fillText(fitText(ctx, line, w - pad * 2), pad, h + pad + i * lineH + (i ? 3 : 0));
    });
    return out;
  }

  /** 띠에 적을 줄들. 첫 줄이 제목이다. */
  function exportLines() {
    var shown = [select.options[select.selectedIndex].text];
    var on = customOn();
    custom.forEach(function (row) { if (on.indexOf(row.name) >= 0) shown.push(row.title); });
    var mine = pointsets.filter(isOn);
    var c = map.getCenter();
    // MapLibre 는 소스들의 출처를 " | " 로 이어 적는다
    var attrib = document.querySelector(".maplibregl-ctrl-attrib-inner");
    var credits = (attrib ? attrib.textContent : "").split("|")
      .map(function (t) { return t.trim(); }).filter(Boolean);
    var out = [T("대돌여지도") + " 3D · " + stampText()];
    if (ibcsoKind) out.push(T("배경") + ": " + baseSel.options[baseSel.selectedIndex].text);
    out.push(T("레이어") + ": " + shown.join(" / "));
    if (mine.length) out.push(T("점묶음") + ": " + mine.map(function (ps) { return ps.name; }).join(", "));
    out.push(T("가운데") + ": " + Math.abs(c.lat).toFixed(5) + "°" + (c.lat < 0 ? "S" : "N") + " " +
             Math.abs(c.lng).toFixed(5) + "°" + (c.lng < 0 ? "W" : "E") + " · " +
             T("기울기 {pitch}° · 방위 {bearing}° · 지형 과장 ×{x}", {
               pitch: Math.round(map.getPitch()),
               bearing: Math.round((map.getBearing() + 360) % 360),
               x: (map.getTerrain() || {}).exaggeration || 1 }));
    if (credits.length) out.push(T("출처") + ": " + credits.join(" · "));
    return out;
  }

  /** 넘치면 끝을 줄임표로 자른다. */
  function fitText(ctx, text, max) {
    if (ctx.measureText(text).width <= max) return text;
    while (text.length > 1 && ctx.measureText(text + "…").width > max) text = text.slice(0, -1);
    return text + "…";
  }

  document.getElementById("export3d").addEventListener("click", exportPng);

  /** 판 접기 — 휴대폰에서는 판이 지형을 다 덮으므로 접힌 채로 연다 (wetherilli 128). */
  (function () {
    var panel = document.getElementById("panel3d"), btn = document.getElementById("fold3d");
    function apply(folded) {
      panel.classList.toggle("folded", folded);
      btn.title = folded ? T("패널을 편다") : T("패널을 접는다");
      btn.setAttribute("aria-expanded", folded ? "false" : "true");
    }
    apply(window.matchMedia("(max-width: 760px)").matches);
    btn.addEventListener("click", function () { apply(!panel.classList.contains("folded")); });
  })();
})();
