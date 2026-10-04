/* 대돌여지도 · 온 지구 (wetherilli P06·086).
 *
 * **화성 화면(`mars.js`)을 옮겨 와 지구의 자료로 바꿨다.** 틀 — 구(Cesium)와 평면(OpenLayers)을 오가는 것,
 * 레이어 목록·카드·범례·점묶음·그리기 도구·그림 내려받기 — 은 달·화성과 같다. 고친 것은 몸과 자료다.
 *
 * - 몸 — WGS84 타원체(Cesium 의 기본). 길이·넓이는 평균 반지름(6 371.0088 km)의 구로 잰다 — `ol.sphere` 와 같은
 *   값이다. 평면은 경위도(EPSG:4326) 그대로이고, 위도 65° 너머는 지역 탭이 쓰는 극 평사도법(북 3413·남 3031)이다.
 *   달·화성은 OpenLayers 가 4326 을 지구로 재서 따로 투영을 지었지만, 여기는 지구라 빌려 쓴다
 * - 지질도(Macrostrat)·속성·범례는 서버의 문(`macrostrat.py`)을 거친다. 배경(NASA GIBS Blue Marble)·표고(AWS
 *   Terrarium)는 브라우저가 곧장 부른다 — 지역 탭의 극지 배경·3D 가 이미 그렇게 쓴다
 *
 * 화성에만 있는 것(착륙지·로버 경로·크레이터·옛 지질도·Trek 판 목록·지명 찾기)은 뺐다.
 */
(function () {
  "use strict";

  var BASE = location.pathname.replace(/earth\/?$/, "");
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
    var seed = { "gsm.earth.layers": JSON.stringify(GSMShare.layers(q.l)), "gsm.earth.mode": q.m === "flat" ? "flat" : "globe" };
    var c = (q.c || "").split(",").map(Number), ok = c.length === 2 && isFinite(c[0]) && isFinite(c[1]);
    if (ok && isFinite(+q.h)) {
      seed["gsm.earth.view"] = JSON.stringify({ lon: c[0], lat: c[1], h: +q.h, heading: isFinite(+q.hd) ? +q.hd : 0,
                                              pitch: isFinite(+q.pt) ? +q.pt : -Math.PI / 2 });
    }
    if (ok && isFinite(+q.res)) seed["gsm.earth.flat"] = JSON.stringify({ lon: c[0], lat: c[1], res: +q.res });
    if (q.b) seed["gsm.earth.base"] = q.b;
    if (q.a && isFinite(+q.a)) seed["gsm.earth.age"] = q.a;
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

  // ══ 지구와 격자 ═══════════════════════════════════════════════════
  var R = 6371008.8;                                 // 길이·넓이를 재는 구 (평균 반지름, `ol.sphere` 와 같다)
  var M_PER_DEG = Math.PI * 6378137 / 180;           // 평면(4326)의 1° — 적도 반지름으로. 축척 막대는 OpenLayers 가 잰다
  // 배경 — NASA GIBS 의 Blue Marble(500 m). 셋 다 4326·3413·3031 판이 있어 구·평면·극 평면이 같은 영상이다.
  // 구는 WMS(4326)로, 평면은 WMTS 로 받는다 — GIBS 의 4326 WMTS 는 줌 0 이 288° 한 장이라 Cesium 의 격자와 맞지 않는다
  // 서버가 브라우저가 부르던 주소 그대로 받아 담는다(`basemaps.py`, wetherilli 184) — 상류가 한 장에 1–3 초라 두 번째부터 빠르다
  var GIBS_WMS = BASE + "gibs/wms/";
  var GIBS_WMTS = BASE + "gibs/{e}/{name}/{z}/{y}/{x}.jpeg";
  var BASES = {
    bm: { name: "BlueMarble_ShadedRelief_Bathymetry", credit: "Blue Marble shaded relief & bathymetry · NASA EOSDIS GIBS" },
    bmng: { name: "BlueMarble_NextGeneration", credit: "Blue Marble Next Generation · NASA EOSDIS GIBS" },
    relief: { name: "BlueMarble_ShadedRelief", credit: "Blue Marble shaded relief · NASA EOSDIS GIBS" },
    // GEBCO 해저 지형(공공 도메인, wetherilli 135) — GIBS 가 아니라 GEBCO 의 WMS 다. 4326 뿐이라 극 평면은 Blue Marble 로 갈음한다
    gebco: { name: "GEBCO_LATEST", wms: BASE + "gebco/wms/", format: "image/png", max: 8,
             credit: "GEBCO Compilation Group (2026) GEBCO 2026 Grid" },
  };
  // 지질 레이어 목록 — 달·화성과 같은 꼴이다. 이름은 서버 `earth/tiles/<이름>` 의 것
  //   info    누르면 읽는 갈래 (`earth/info/`)   legend  범례 칸의 갈래   src  카드 밑의 출처
  var CATALOG = [
    // 나라마다 가장 자세한 지도를 이어 붙인 판 — 빈 곳은 GSC 세계 지질도(1:3500만)가 채운다 (`macrostrat.py`)
    { group: "온 지구 지질도 (Macrostrat)", layers: [
      { name: "geology", title: "지질 단위", info: "geology", legend: "geology",
        src: "Macrostrat carto · CC BY 4.0" },
    ] },
    // 판 회전에 쓰는 대륙 조각의 경계 — 오늘의 것. 옛 연대에는 서버가 돌려 칠한 판이 배경이 된다 (wetherilli 091)
    { group: "판 조각 (PALEOMAP 2016)", layers: [
      { name: "plates", title: "판 조각 경계", grid: "ll", src: "PALEOMAP 2016 (Scotese) · CC BY 4.0" },
    ] },
    // 그때의 지구에만 뜨는 것 — 연대(1 Ma 부터)를 따라 타일이 바뀐다 (P07·wetherilli 097)
    //   then  1 Ma 부터만 뜬다. 오늘의 레이어는 그 반대다
    // 오늘의 지리 — Natural Earth(퍼블릭 도메인). 이름표는 타일이 아니라 화면이 쓴다(`labels`) (102)
    { group: "지리 (Natural Earth)", layers: [
      { name: "names", title: "산맥·바다 이름", labels: true, src: "Natural Earth 10 m · public domain" },
      { name: "water", title: "강·호수", grid: "ll", max: 7, src: "Natural Earth 10 m · public domain" },
      { name: "ice", title: "빙하·빙붕", grid: "ll", max: 7, src: "Natural Earth 10 m · public domain" },
    ] },
    // 지각 두께 — 오늘의 것(2° 모형). 누르면 두께가 뜬다 (101)
    { group: "지각 (CRUST 2.0)", layers: [
      { name: "crust", title: "지각 두께", grid: "ll", info: "crust", legend: "crust", max: 5,
        src: "CRUST 2.0 (Laske, Masters & Reif 2000) · EarthByte · CC BY 4.0" },
    ] },
    // 화석 산지 — 모든 연대에 뜬다(`always`). 오늘은 모든 산지, 옛 연대는 그 연대를 품은 산지를 그때의 자리에 (098)
    { group: "화석 산지 (PBDB)", layers: [
      { name: "fossils", title: "화석 산지", grid: "ll", always: true, legend: "geology",
        src: "Paleobiology Database · CC BY 4.0" },
    ] },
    // 지구 속 — 구에서만. 땅을 비치게 하고 그 밑에 그린다. 모든 연대에 뜬다(가장 가까운 20 Myr 시점) (106)
    { group: "지구 속 (OPT1 모의)", layers: [
      { name: "mantle", title: "맨틀 슬랩·하부 더미", mantle: true, always: true,
        src: "Müller et al. 2022 OPT1 · CC BY 4.0 — 모의 결과" },
    ] },
    // 최근 빙기 — 1 ka–1 Ma 의 오늘의 지구에만 뜬다(`ka`). 25–1 ka 의 빙상 가장자리 (104)
    { group: "최근 빙기", layers: [
      { name: "icemargins", title: "빙상 가장자리", grid: "ll", ka: true,
        src: "NADI-1 (Dalton et al. 2023) · DATED-1 (Hughes et al. 2016)" },
    ] },
    // 움직이는 지구 — 시시각각 바뀌는 것을 한 레이어군에 모은다: 바람, 아라온호(아래에서 더한다), 앞으로 구름·해류 (koprifossillab 010).
    // 바람은 오늘의 레이어다. 지금(GFS, 기본)과 지난(ERA5 2005-06 ~ 2007-12), 지상 10 m(기본)·250 hPa 를 카드에서 고른다.
    // 타일이 아니라 입자로 그린다(`syncWind`) (koprifossillab P02)
    { group: "움직이는 지구", flux: true, layers: [
      { name: "wind", title: "바람", wind: true, legend: "wind", src: "NOAA GFS · ERA5 (Copernicus, CC BY 4.0)" },
      // 구름량 — 바람과 같은 시각 축(지금/지난·날짜·재생)을 쓴다. 영상 한 장으로 덮는다(`applyCloud`) (koprifossillab 011)
      { name: "cloud", title: "구름", cloud: true, src: "NOAA GFS · ERA5 (Copernicus, CC BY 4.0)" },
      // 위성 구름 — NOAA GMGSI 정지궤도 적외선 합성, 한 시간마다. 가장 새 장 하나를 덮는다(`syncSat`) (koprifossillab 012)
      { name: "satcloud", title: "위성 구름", sat: true, src: "NOAA/NESDIS GMGSI · public domain" },
    ] },
    { group: "그때의 지구", layers: [
      { name: "coast", title: "옛 해안선", grid: "ll", then: true,
        src: "PaleoCoastlines v7.1 (Kocsis & Scotese 2021) · CC BY 4.0" },
    ] },
  ];
  var THEN = JSON.parse(($("then-data") || {}).textContent || "{}");
  // 아라온호 항적 — 극지연구소 위치 판에서 매시간 쌓은 것. 쌓은 것이 있고 연구실 안에서 열 때만 (koprifossillab 006)
  //   track  타일이 아니라 화면이 GeoJSON 을 그린다(`syncTrack`). 오늘의 것이다
  // 레이어군은 "움직이는 지구" 다 (koprifossillab 010)
  // 해류 — ECCO2 표층(3 일 평균)을 서버가 구워 두었을 때만. 바람처럼 입자로 흘린다(`syncOcean`) (koprifossillab 014)
  if (THEN.ocean) {
    CATALOG.filter(function (g) { return g.flux; })[0].layers.push(
      { name: "ocean", title: "해류", ocean: true, legend: "ocean", src: "ECCO2 cube92 (NASA JPL·MIT) · Menemenlis et al. 2008" });
  }
  // 홀로세 화산 — GVP 의 1 200 여 곳. 받아 둔 것이 있을 때만. 오늘의 레이어라 1 Ma 부터는 꺼진다 (wetherilli 134)
  // 플라이스토세 화산은 따로 받아 따로 켠다 — 마지막 분화 열이 없어 한 색이다 (wetherilli 194)
  if ((THEN.volcanoes && THEN.volcanoes.length) || (THEN.pleistocene && THEN.pleistocene.length)) {
    var VOLCANO_LAYERS = [];
    if (THEN.volcanoes && THEN.volcanoes.length) {
      VOLCANO_LAYERS.push({ name: "volcanoes", title: "홀로세 화산", grid: "ll", legend: "volcano",
                            src: "Global Volcanism Program, Smithsonian Institution" });
    }
    if (THEN.pleistocene && THEN.pleistocene.length) {
      VOLCANO_LAYERS.push({ name: "pleistocene", title: "플라이스토세 화산", grid: "ll", legend: "pleistocene",
                            src: "Global Volcanism Program, Smithsonian Institution" });
    }
    CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "fossils"; }) + 1, 0,
      { group: "화산 (GVP)", layers: VOLCANO_LAYERS });
  }
  // 지진 — USGS 의 M5 이상, 1900 년부터. 규모의 칸 셋을 따로 켠다. 오늘의 레이어다 (wetherilli 138)
  //   quake  타일 주소의 칸(`earth/quakes/tiles/<칸>/…`)이자 누를 때 묻는 칸
  if (THEN.quakes && THEN.quakes.length) {
    var QUAKE_SRC = "U.S. Geological Survey ComCat · public domain";
    CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "fossils"; }) + 1, 0,
      { group: "지진 (USGS)", layers: [
        { name: "quake6", title: "M6 이상", grid: "ll", quake: true, legend: "quake", legendTitle: "지진 (USGS)", src: QUAKE_SRC },
        { name: "quake55", title: "M5.5–6", grid: "ll", quake: true, legend: "quake", legendTitle: "지진 (USGS)", src: QUAKE_SRC },
        { name: "quake5", title: "M5–5.5", grid: "ll", quake: true, legend: "quake", legendTitle: "지진 (USGS)", src: QUAKE_SRC },
      ] });
  }
  // 제4기 고생태 산지 — Neotoma. 자료형 칸 다섯을 따로 켠다. 옛 연대(1 Ma 안쪽)에는 그 연대를 품은 산지만 (wetherilli 139)
  //   neo  타일 주소의 칸(`earth/neotoma/tiles/<칸>/<ka>/…`)이자 누를 때 묻는 칸
  if (THEN.neotoma && THEN.neotoma.length) {
    var NEO_SRC = "Neotoma Paleoecology Database · CC BY 4.0";
    CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "fossils"; }) + 1, 0,
      { group: "고생태 산지 (Neotoma)", layers: THEN.neotoma.map(function (row) {
        return { name: row.band, title: row.name, grid: "ll", neo: true, legend: "neotoma",
                 legendTitle: "고생태 산지 (Neotoma)", src: NEO_SRC };
      }) });
  }
  // 세계 암상 — GLiM 0.5° 칸의 가장 넓은 암상. 지각 두께 다음에 둔다. 오늘의 레이어다 (wetherilli 267)
  if (THEN.glim && THEN.glim.length) {
    CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "crust"; }) + 1, 0,
      { group: "암상 (GLiM)", layers: [
        { name: "glim", title: "세계 암상", grid: "ll", info: "glim", legend: "glim", max: 5,
          src: "GLiM (Hartmann & Moosdorf 2012) · PANGAEA · CC BY 3.0" }] });
  }
  // 지열류 — IHFC 2024 판의 측정 7 만 곳. 오늘의 레이어다. 누르면 가까운 측정 (wetherilli 267)
  if (THEN.heatflow && THEN.heatflow.length) {
    CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "fossils"; }) + 1, 0,
      { group: "지열류 (IHFC)", layers: [
        { name: "heatflow", title: "지열류", grid: "ll", legend: "heatflow",
          src: "IHFC Global Heat Flow Database 2024 · CC BY 4.0" }] });
  }
  // 바다 밑 — 해양 지각 연대(Seton 2020)·퇴적층 두께(GlobSed v3). 구워 둔 것이 있을 때만, 오늘의 레이어다. 누르면 값이 뜬다 (wetherilli 264)
  var SEA = THEN.seafloor || {};
  if (SEA.age || SEA.sediment) {
    var SEA_LAYERS = [];
    if (SEA.age) SEA_LAYERS.push({ name: "seaage", title: "해양 지각 연대", grid: "ll", info: "seafloor", legend: "seaage", max: 6,
                                   src: "Seton et al. 2020 · EarthByte · CC BY 4.0" });
    if (SEA.sediment) SEA_LAYERS.push({ name: "sediment", title: "해저 퇴적층 두께", grid: "ll", info: "seafloor", legend: "sediment", max: 6,
                                        src: "GlobSed v3 (Straume et al. 2019) · NOAA NCEI" });
    CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "crust"; }) + 1, 0,
      { group: "바다 밑 (Seton 2020 · GlobSed)", layers: SEA_LAYERS });
  }
  // 지각 응력 — World Stress Map 2025 의 S_Hmax 막대(품질 A–D). 오늘의 레이어다. 누르면 가까운 측정 (wetherilli 273)
  if (THEN.stress && THEN.stress.length) {
    CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "fossils"; }) + 1, 0,
      { group: "지각 응력 (World Stress Map)", layers: [
        { name: "stress", title: "최대 수평 응력 방향", grid: "ll", legend: "stress", src: "World Stress Map 2025 · CC BY 4.0" }] });
  }
  // 판 경계·세계 지질구 — Hasterok 2022. 오늘의 지구다(판 회전의 조각 경계 `plates` 와 다른 모형). 지각 두께 앞에 둔다 (wetherilli 272)
  var TECT = THEN.tectonics || {};
  if (TECT.boundaries) {
    CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "crust"; }), 0,
      { group: "판·지질구 (Hasterok 2022)", layers: [
        { name: "tbound", title: "판 경계", grid: "ll", legend: "tbound", max: 7, src: "Hasterok et al. 2022 · CC BY 4.0" },
        { name: "tprov", title: "세계 지질구", grid: "ll", info: "tectonics", legend: "tprov", max: 7,
          src: "Hasterok et al. 2022 · CC BY 4.0" }] });
  }
  // 세계 광상 — USGS MRDS 와 세계 광상 표, 첫 광종으로 칸 여섯. 오늘의 레이어다. 누르면 가까운 곳 (wetherilli 276)
  //   mineral  타일 주소의 칸(`earth/minerals/tiles/<칸>/…`)이자 누를 때 묻는 칸
  if (THEN.minerals && THEN.minerals.length) {
    var MIN_SRC = "USGS MRDS · Global Mineral Resource Assessment · public domain";
    CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "fossils"; }) + 1, 0,
      { group: "세계 광상 (USGS)", layers: THEN.minerals.map(function (row) {
        return { name: row.band, title: row.name, grid: "ll", mineral: true, legend: "mineral", legendTitle: "세계 광상 (USGS)", src: MIN_SRC };
      }) });
  }
  // 세계 활성단층 — GEM Global Active Faults. 판·지질구 레이어군 곁에 둔다(없으면 지각 두께 앞). 오늘의 지구다 (wetherilli 279)
  if (THEN.faults && THEN.faults.length) {
    var FAULT_LAYER = { name: "gemfaults", title: "활성단층 (GEM)", grid: "ll", info: "faults", legend: "gemfaults", max: 8,
                        src: "GEM Global Active Faults (Styron & Pagani 2020) · CC BY-SA 4.0" };
    var TECT_GROUP = CATALOG.filter(function (g) { return g.layers.some(function (l) { return l.name === "tbound"; }); })[0];
    if (TECT_GROUP) TECT_GROUP.layers.splice(1, 0, FAULT_LAYER);
    else CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "crust"; }), 0,
                        { group: "활성단층 (GEM)", layers: [FAULT_LAYER] });
  }
  // 충돌구(오늘)·거대 화성암 지대(모든 연대 — 대륙 위의 것은 판 회전으로 그때의 자리에) (wetherilli 283)
  var IMP = THEN.impacts || {};
  if (IMP.impacts) {
    CATALOG.splice(CATALOG.findIndex(function (g) { return g.layers[0].name === "fossils"; }) + 1, 0,
      { group: "충돌구·거대 화성암 지대", layers: [
        { name: "impacts", title: "충돌구", grid: "ll", info: "impacts", legend: "impacts", max: 7, src: "Wikidata · CC0" },
        { name: "lips", title: "거대 화성암 지대 (LIP)", grid: "ll", info: "impacts", legend: "lips", always: true, max: 7,
          src: "Johansson et al. 2018 · EarthByte · CC BY 4.0" }] });
  }
  if (THEN.araon) {
    CATALOG.filter(function (g) { return g.flux; })[0].layers.push(
      { name: "araon", title: "아라온호 항적", track: true, src: "KOPRI · RV Araon live position" });
  }
  // ── 레이어군을 주제로 묶는다 (wetherilli 278) ──
  // 레이어가 늘며 자료마다 레이어군이 하나씩(열일곱) 생기고, 덧붙인 차례대로 끼워 넣어 차례가 뒤섞였다. 위에서 자료마다 지은 레이어를
  // 그대로 두고, 패널의 레이어군만 주제로 다시 묶는다. 출처는 레이어 카드의 `src` 가 적는다.
  // **패널의 차례만 바뀐다** — 지도에 쌓는 차례와 누를 때 묻는 차례는 켠 차례(`active`)를 따르고, 처음 켜는 것은 그대로다(지질 단위).
  // 새 레이어는 아래 표에 이름을 적는다. 적지 않으면 맨 끝 "그 밖" 에 선다(시험 `test_earth_panel` 이 적었는지 본다)
  var THEMES = [
    ["지질", ["geology", "glim", "seaage", "sediment", "impacts"]],
    ["구조·판", ["tbound", "gemfaults", "tprov", "plates", "stress"]],
    ["지구물리", ["crust", "heatflow", "mantle"]],
    ["자원", []],                                     // 세계 광상(USGS)의 광종 칸은 `mineral` 로 여기 선다 (wetherilli 276)
    ["화산·지진", ["volcanoes", "pleistocene", "lips", "quake6", "quake55", "quake5"]],
    ["화석·고생태", ["fossils"]],                      // 고생태 산지(Neotoma)의 자료형 칸은 `neo` 로 여기 선다
    ["그때의 지구", ["coast", "icemargins"]],
    ["움직이는 지구", ["wind", "cloud", "satcloud", "ocean", "araon"]],
    ["지리", ["names", "water", "ice"]],
  ];
  CATALOG = (function (groups) {
    var theme = {};
    THEMES.forEach(function (t, i) { t[1].forEach(function (n) { theme[n] = i; }); });
    var out = THEMES.map(function (t) { return { group: t[0], layers: [] }; }).concat([{ group: "그 밖", layers: [] }]);
    var rows = [];
    groups.forEach(function (g) { g.layers.forEach(function (l) { rows.push(l); }); });
    THEMES.forEach(function (t, i) {                   // 주제 안의 차례는 표의 차례
      t[1].forEach(function (n) { rows.forEach(function (l) { if (l.name === n) out[i].layers.push(l); }); });
    });
    rows.forEach(function (l) {
      if (theme[l.name] !== undefined) return;
      // 이름이 자료에서 오는 칸 — 고생태 산지(Neotoma)의 자료형, 세계 광상의 광종
      var by = l.neo ? "화석·고생태" : l.mineral ? "자원" : "";
      out[by ? THEMES.findIndex(function (t) { return t[0] === by; }) : out.length - 1].layers.push(l);
    });
    out[THEMES.findIndex(function (t) { return t[0] === "움직이는 지구"; })].flux = true;
    return out.filter(function (g) { return g.layers.length; });
  })(CATALOG);
  var LAYER = {};
  CATALOG.forEach(function (g) { g.layers.forEach(function (l) { LAYER[l.name] = l; }); });
  var ALL_NAMES = Object.keys(LAYER);
  var GEO_NAMES = ALL_NAMES.filter(function (n) { return !LAYER[n].labels && !LAYER[n].mantle && !LAYER[n].track && !LAYER[n].wind && !LAYER[n].cloud && !LAYER[n].sat && !LAYER[n].ocean; });   // 타일로 그리는 것
  var GEO_MAX = 16;            // 서버의 `macrostrat.MAX_ZOOM`
  function geoUrl(name) {
    if (name === "plates") return paleoUrl("edge", 0);
    if (name === "coast") return paleoUrl("coast", paleoOn() ? age : 0);
    if (name === "crust") return BASE + "earth/crust/tiles/{z}/{x}/{y}.png" + vq("crust");
    if (name === "impacts") return BASE + "earth/impacts/impacts/0/{z}/{x}/{y}.png" + vq("impacts");
    if (name === "lips") return BASE + "earth/impacts/lips/" + Math.round(paleoOn() ? age : 0) + "/{z}/{x}/{y}.png" + vq("impacts");
    if (name === "gemfaults") return BASE + "earth/faults/tiles/{z}/{x}/{y}.png" + vq("faults");
    if (LAYER[name] && LAYER[name].mineral) return BASE + "earth/minerals/tiles/" + name + "/{z}/{x}/{y}.png" + vq("minerals");
    if (name === "stress") return BASE + "earth/stress/tiles/{z}/{x}/{y}.png" + vq("stress");
    if (name === "tbound" || name === "tprov") return BASE + "earth/tectonics/" + name + "/{z}/{x}/{y}.png" + vq("tectonics");
    if (name === "glim") return BASE + "earth/glim/tiles/{z}/{x}/{y}.png" + vq("glim");
    if (name === "heatflow") return BASE + "earth/heatflow/tiles/{z}/{x}/{y}.png" + vq("heatflow");
    if (name === "seaage" || name === "sediment") return BASE + "earth/seafloor/" + name + "/{z}/{x}/{y}.png" + vq(name);
    if (name === "icemargins") return BASE + "earth/icemargins/tiles/" + Math.min(1000, Math.round(age * 1000)) + "/{z}/{x}/{y}.png" + vq("icemargins");
    if (name === "water" || name === "ice") return BASE + "earth/ne/tiles/" + name + "/{z}/{x}/{y}.png" + vq("ne");
    if (name === "fossils") return BASE + "earth/fossils/tiles/" + Math.round(age * 1000) + "/{z}/{x}/{y}.png" + vq("fossils");
    if (name === "volcanoes") return BASE + "earth/volcanoes/tiles/{z}/{x}/{y}.png" + vq("volcanoes");
    if (name === "pleistocene") return BASE + "earth/volcanoes/pleistocene/tiles/{z}/{x}/{y}.png" + vq("pleistocene");
    if (LAYER[name].neo) return BASE + "earth/neotoma/tiles/" + name + "/" + Math.min(999, Math.round(age * 1000)) + "/{z}/{x}/{y}.png" + vq("neotoma");
    if (LAYER[name].quake) return BASE + "earth/quakes/tiles/" + name + "/{z}/{x}/{y}.png" + vq("quakes");
    return BASE + "earth/tiles/" + name + "/{z}/{x}/{y}.png";
  }
  var GEO_CREDIT = "Macrostrat (CC BY 4.0) · Peters, Husson & Czaplewski 2018, G-cubed";
  var PALEO_CREDIT = "PALEOMAP 2016 (CC BY 4.0) · Scotese 2016, PALEOMAP PaleoAtlas for GPlates";
  var COAST_CREDIT = "PaleoCoastlines v7.1 (CC BY 4.0) · Kocsis & Scotese 2021, Earth-Science Reviews";
  var PBDB_CREDIT = "Paleobiology Database (CC BY 4.0) · paleobiodb.org";
  var CRUST_CREDIT = "CRUST 2.0 (CC BY 4.0) · Laske, Masters & Reif 2000 · EarthByte GPlates 2.3";
  var STRESS_CREDIT = "World Stress Map 2025 (CC BY 4.0) · Heidbach et al., GFZ";
  var TECT_CREDIT = "Hasterok et al. 2022, Earth-Science Reviews (CC BY 4.0)";
  var GLIM_CREDIT = "GLiM (CC BY 3.0) · Hartmann & Moosdorf 2012, G-cubed";
  var HEATFLOW_CREDIT = "IHFC Global Heat Flow Database 2024 (CC BY 4.0) · GFZ Data Services";
  var SEAAGE_CREDIT = "Seton et al. 2020, G-cubed · EarthByte (CC BY 4.0)";
  var SEDIMENT_CREDIT = "GlobSed v3 · Straume et al. 2019, G-cubed · NOAA NCEI";
  var GVP_CREDIT = "Global Volcanism Program, Smithsonian Institution · Volcanoes of the World";
  var QUAKE_CREDIT = "U.S. Geological Survey · ANSS ComCat";
  var NEO_CREDIT = "Neotoma Paleoecology Database (CC BY 4.0)";
  var NE_CREDIT = "Natural Earth 10 m (public domain)";
  var ICE_CREDIT = "NADI-1 (Dalton et al. 2023, CC BY 4.0) · DATED-1 (Hughes et al. 2016, CC BY 3.0)";
  var MANTLE_CREDIT = "Müller et al. (2022) OPT1, Solid Earth (CC BY 4.0)";
  var MIN_CREDIT = "USGS Mineral Resources Data System · Global Mineral Resource Assessment (public domain)";
  var FAULT_CREDIT = "GEM Global Active Faults (Styron & Pagani 2020) · CC BY-SA 4.0";
  var IMPACT_CREDIT = "Wikidata (CC0)", LIP_CREDIT = "Johansson et al. 2018 · EarthByte GPlates 2.3 (CC BY 4.0)";
  function creditOf(name) {
    if (name === "impacts") return IMPACT_CREDIT;
    if (name === "lips") return LIP_CREDIT;
    if (name === "gemfaults") return FAULT_CREDIT;
    if (LAYER[name] && LAYER[name].mineral) return MIN_CREDIT;
    if (LAYER[name] && LAYER[name].neo) return NEO_CREDIT;
    return { geology: GEO_CREDIT, plates: PALEO_CREDIT, coast: COAST_CREDIT, fossils: PBDB_CREDIT, volcanoes: GVP_CREDIT, pleistocene: GVP_CREDIT, quake6: QUAKE_CREDIT, quake55: QUAKE_CREDIT, quake5: QUAKE_CREDIT, crust: CRUST_CREDIT, stress: STRESS_CREDIT, tbound: TECT_CREDIT, tprov: TECT_CREDIT, glim: GLIM_CREDIT, heatflow: HEATFLOW_CREDIT, seaage: SEAAGE_CREDIT, sediment: SEDIMENT_CREDIT,
             names: NE_CREDIT, water: NE_CREDIT, ice: NE_CREDIT, icemargins: ICE_CREDIT, mantle: MANTLE_CREDIT }[name];
  }
  // 판 조각 타일 — 서버가 연대마다 돌려 그린다(`paleo.render_tile`). 경위도 격자, 줌 0 이 180° 두 장이다
  var PALEO_MAX = 6;           // 서버의 `paleo.MAX_ZOOM`
  function paleoUrl(style, age) { return BASE + "earth/paleo/tiles/" + style + "/" + age + "/{z}/{x}/{y}.png" + vq(style === "coast" ? "coast" : "paleo"); }

  // ── 켠 것 — 구와 평면이 함께 쓴다. 이 브라우저에 기억한다 ──
  var look = {
    base: saved("gsm.earth.base", "bm"),
    terrain: saved("gsm.earth.terrain", "on") !== "off",
    exag: +saved("gsm.earth.exag", "15"),
  };
  if (!BASES[look.base]) look.base = "bm";
  // 연대 (wetherilli 091) — Ma, 0 이 오늘. 주소(`?age=`)가 이기고, 없으면 이 브라우저에 남긴 것
  var AGE_MAX = 1100;          // PALEOMAP 2016 이 덮는 끝
  var PALEO_FROM = 1;          // 이 연대부터는 판을 돌린 그때의 지구다. 그 안쪽은 오늘의 지구에 얹는다
  function snapAge(a) {
    if (!(a > 0)) return 0;
    if (a >= PALEO_FROM - 0.0005) return Math.min(AGE_MAX, Math.round(a));       // 판 조각 타일은 1 Myr 마다다
    return Math.max(0.001, Math.round(a * 1000) / 1000);                         // 1 ka 마다
  }
  var age = snapAge(parseFloat(new URLSearchParams(location.search).get("age") || saved("gsm.earth.age", "0")));
  function paleoOn() { return age >= PALEO_FROM; }
  // 켠 지질 레이어 — 맨 앞이 위다. `[{name, opacity}]`. 처음이면 지질 단위 하나를 반쯤 비치게
  var active = (function () {
    try {
      var list = JSON.parse(saved("gsm.earth.layers", "null"));
      if (Array.isArray(list)) {
        return list.filter(function (e) { return e && LAYER[e.name]; })
                   .map(function (e) { return { name: e.name, opacity: isFinite(e.opacity) ? +e.opacity : 1 }; });
      }
    } catch (e) { /* 깨진 값 */ }
    return [{ name: "geology", opacity: 0.6 }];
  })();
  // 옛 해안선(097)은 처음 한 번 켜 둔다 — 전에 기억한 목록에도. 사람이 끄면 그대로 꺼진다
  // 화석 산지(098)도 그렇게 한 번 켜 둔다
  [["coast", "gsm.earth.coast.added"], ["fossils", "gsm.earth.fossils.added"],
   ["icemargins", "gsm.earth.icemargins.added"]].forEach(function (pair) {
    if (saved(pair[1], "") === "1") return;
    if (!active.some(function (e) { return e.name === pair[0]; })) active.unshift({ name: pair[0], opacity: 1 });
    save(pair[1], "1");
    save("gsm.earth.layers", JSON.stringify(active));
  });
  /** 지금의 연대에 이 레이어가 뜨나 — 오늘의 것은 오늘에만(1 Ma 안쪽까지), 그때의 것(`then`)은 1 Ma 부터, `always` 는 늘,
   *  최근 빙기의 것(`ka`)은 0 보다 오래고 1 Ma 안쪽일 때만 (P07 §2) */
  function visibleNow(name) {
    var l = LAYER[name];
    return l.always ? true : l.then ? paleoOn() : l.ka ? age > 0 && !paleoOn() : !paleoOn();
  }
  function entryOf(name) { return active.filter(function (e) { return e.name === name; })[0]; }
  function isOn(name) { return !!entryOf(name); }
  function saveLayers() { save("gsm.earth.layers", JSON.stringify(active)); }

  // ══ 구 — Cesium ═══════════════════════════════════════════════════
  // 몸은 Cesium 의 기본(WGS84)이다. 달·화성처럼 구를 따로 짓지 않는다 — 지구의 자료가 다 WGS84 다
  var ELL = Cesium.Ellipsoid.WGS84;
  function cesiumBase(key) {
    var b = BASES[key];
    return new Cesium.ImageryLayer(new Cesium.WebMapServiceImageryProvider({
      url: b.wms || GIBS_WMS, layers: b.name, parameters: { format: b.format || "image/jpeg", transparent: false },
      tilingScheme: new Cesium.GeographicTilingScheme(), maximumLevel: b.max || 8, credit: b.credit,
    }));
  }

  // 지형 — AWS Terrarium(3D 가 쓰는 것과 같다). 메르카토르 격자라 위도 ±85° 너머는 평평하다. 256 칸 타일을 받아
  // 높이로 푼 뒤 65×65 로 뽑는다 — 색을 먼저 줄이면 Terrarium 의 세 바이트가 따로 섞여 높이가 튄다
  var DEM_SIZE = 65;
  var DEM_MAX = 12;            // 서버의 `elevation.TERRARIUM_ZOOM`. 그 너머는 부모 격자를 늘려 쓴다
  var DEM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
  var demMemo = {};
  function demGrid(x, y, level) {
    var id = level + "/" + x + "/" + y;
    if (!demMemo[id]) {
      demMemo[id] = fetch(DEM_URL.replace("{z}", level).replace("{x}", x).replace("{y}", y)).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.blob();
      }).then(function (blob) {
        return createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
      }).then(function (bitmap) {
        var n = bitmap.width, canvas = document.createElement("canvas");
        canvas.width = canvas.height = n;
        var ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(bitmap, 0, 0);
        var px = ctx.getImageData(0, 0, n, n).data;
        var src = new Float32Array(n * n);
        for (var i = 0; i < src.length; i++) src[i] = px[i * 4] * 256 + px[i * 4 + 1] + px[i * 4 + 2] / 256 - 32768;
        return sampleGrid(src, n, 0, 0, 1);
      }).catch(function () {
        delete demMemo[id];                    // 다음에 다시 묻는다. 이번에는 평평하게
        return new Float32Array(DEM_SIZE * DEM_SIZE);
      });
    }
    return demMemo[id];
  }
  /** `n`×`n` 격자의 한 조각([ox, oy] 에서 폭 `span`, 0–1)을 65×65 로 겹선형으로 뽑는다 */
  function sampleGrid(src, n, ox, oy, span) {
    var out = new Float32Array(DEM_SIZE * DEM_SIZE), last = n - 1, m = DEM_SIZE - 1;
    for (var j = 0; j < DEM_SIZE; j++) {
      var fy = (oy + span * j / m) * last, y0 = Math.min(last - 1, Math.floor(fy)), ty = fy - y0;
      for (var i = 0; i < DEM_SIZE; i++) {
        var fx = (ox + span * i / m) * last, x0 = Math.min(last - 1, Math.floor(fx)), tx = fx - x0;
        var a = src[y0 * n + x0], b = src[y0 * n + x0 + 1], c = src[(y0 + 1) * n + x0], d = src[(y0 + 1) * n + x0 + 1];
        out[j * DEM_SIZE + i] = (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
      }
    }
    return out;
  }
  function heights(x, y, level) {
    if (level <= DEM_MAX) return demGrid(x, y, level);
    var k = Math.pow(2, level - DEM_MAX);
    var ax = Math.floor(x / k), ay = Math.floor(y / k);
    return demGrid(ax, ay, DEM_MAX).then(function (src) {
      return sampleGrid(src, DEM_SIZE, (x - ax * k) / k, (y - ay * k) / k, 1 / k);
    });
  }
  var DEM_CREDIT = "Terrain: Mapzen/AWS Terrain Tiles (SRTM, GMTED, ETOPO1 …)";
  var demTerrain = new Cesium.CustomHeightmapTerrainProvider({
    width: DEM_SIZE, height: DEM_SIZE, tilingScheme: new Cesium.WebMercatorTilingScheme(), callback: heights,
    credit: DEM_CREDIT,
  });
  var flatTerrain = new Cesium.EllipsoidTerrainProvider();

  // 배경은 한 겹이다(`cBase`). 달은 밑을 깔았지만(043) 지구의 배경은 모두 온 지구를 덮는다
  var cBase = cesiumBase(look.base);
  var viewer = new Cesium.Viewer("globe", {
    baseLayer: cBase,
    terrainProvider: look.terrain && !paleoOn() ? demTerrain : flatTerrain,
    baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
    navigationHelpButton: false, animation: false, timeline: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false,
    // 그리기가 멈추면 Cesium 은 영어 오류 창을 띄우고 멈춘다 — 우리 안내로 바꾼다(아래 `renderFailed`, wetherilli 110)
    showRenderLoopErrors: false,
  });
  var scene = viewer.scene;
  // 하늘의 대기는 둔다 — 지구다. 땅의 대기(푸른 안개)는 지질도의 색을 흐려 끈다
  scene.globe.showGroundAtmosphere = false;
  scene.globe.enableLighting = false;
  // 지형 뒤의 것은 가린다 — 끄면 자전축처럼 지구 속을 지나는 선이 가까이서 땅 위로 비친다 (045)
  scene.globe.depthTestAgainstTerrain = true;
  scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1a2a");
  scene.globe.maximumScreenSpaceError = 3;
  scene.fog.enabled = false;
  if (scene.moon) scene.moon.show = false;
  if (scene.sun) scene.sun.show = false;
  scene.backgroundColor = Cesium.Color.BLACK;
  scene.verticalExaggeration = look.exag / 10;
  window.__gsmEarth = viewer;

  // ── 그리기가 멈추면 (wetherilli 110) ──
  //
  // 사람이 "Fragment shader failed to compile. Compile log: null" 로 구가 멈춘 것을 보았다. 기록(log)이 비어 있으면 대개
  // 셰이더가 틀린 것이 아니라 **WebGL 문맥을 잃은 것**이다 — 그래픽 메모리가 모자라거나 드라이버가 GPU 를 다시 시작했다.
  // 잃은 문맥은 Cesium 이 되살리지 못한다. 그래서 멈춘 자리에 까닭과 나갈 길 셋을 띄운다 — 새로고침, 가볍게 다시(지형·지구 속을
  // 끄고), 평면으로(평면은 OpenLayers 라 구와 따로 돈다). 가볍게 다시 연 것은 이 브라우저에 남는다
  var failed = false;
  function renderFailed(reason) {
    if (failed) return;
    failed = true;
    viewer.useDefaultRenderLoop = false;
    var box = $("render-failed");
    $("render-failed-why").textContent = reason ? String(reason).split("\n")[0].slice(0, 160) : "";
    box.hidden = false;
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
    save("gsm.earth.terrain", "off");
    try {
      var list = JSON.parse(saved("gsm.earth.layers", "[]")).filter(function (e) { return e.name !== "mantle"; });
      save("gsm.earth.layers", JSON.stringify(list));
    } catch (e) { /* 깨진 값 — 그대로 둔다 */ }
    location.reload();
  });
  $("render-failed-flat").addEventListener("click", function () {
    $("render-failed").hidden = true;
    var c = cameraLL();                                  // 평면으로 열 자리 — 보던 가운데를 그대로
    save("gsm.earth.flat", JSON.stringify({ lon: c ? +c.lon.toFixed(4) : 127.5, lat: c ? +c.lat.toFixed(4) : 30,
                                            res: 4000 }));
    save("gsm.earth.mode", "flat");
    location.reload();                                   // 멈춘 구를 두고 평면만 새로 연다
  });

  // 지질도는 3857 타일이다 — 구도 메르카토르 격자로 받는다
  var cGeo = {};
  function cPaleoProvider(url, credit, max) {
    return new Cesium.UrlTemplateImageryProvider({
      url: url, tilingScheme: new Cesium.GeographicTilingScheme(), maximumLevel: max || PALEO_MAX,
      hasAlphaChannel: true, credit: credit,
    });
  }
  GEO_NAMES.forEach(function (name) {
    var layer = viewer.imageryLayers.addImageryProvider(LAYER[name].grid === "ll" ? cPaleoProvider(geoUrl(name), creditOf(name), LAYER[name].max)
      : new Cesium.UrlTemplateImageryProvider({
      url: geoUrl(name), tilingScheme: new Cesium.WebMercatorTilingScheme(), maximumLevel: GEO_MAX,
      hasAlphaChannel: true, credit: creditOf(name),
    }));
    layer.show = false;
    cGeo[name] = layer;
  });

  // ══ 평면 — OpenLayers ═════════════════════════════════════════════
  //
  // 투영은 셋이다. 적도 쪽은 경위도(EPSG:4326, 도) 그대로다 — GIBS 의 4326 판을 옮기지 않고 받는다(배경의 영상
  // 보정이 WebGL 타일이라 옮겨 그리기를 못 한다, 042). 위도 65° 너머는 지역 탭과 같은 극 평사도법 — 북 3413
  // (기준 위도 70°, 경도 −45° 가 아래), 남 3031(기준 위도 −71°). 둘 다 GIBS 의 극지 격자(±4 194 304 m)로 편다.
  // 지질도(3857)는 OpenLayers 가 옮겨 그린다 — 위도 ±85° 너머는 없다
  proj4.defs("EPSG:3413", "+proj=stere +lat_0=90 +lat_ts=70 +lon_0=-45 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs");
  proj4.defs("EPSG:3031", "+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs");
  ol.proj.proj4.register(proj4);
  var LL = ol.proj.get("EPSG:4326");
  var EQC = LL;                            // 화성의 `EQC` 자리 — 지구는 경위도 그대로다
  var POLAR_HALF = 4194304;                // GIBS 극지 격자의 반 폭
  var POLAR_LAT = 65;                      // 이 위도 너머는 극 평면. 넘나드는 문턱은 ±2° 되돌이
  var POLAR_TS = { n: 70, s: 71 };         // 참 축척의 위도 — 3413·3031 의 `lat_ts`
  function polarProj(code, pole) {
    var p = ol.proj.get(code);
    p.setExtent([-POLAR_HALF, -POLAR_HALF, POLAR_HALF, POLAR_HALF]);
    p.pole = pole;
    return p;
  }
  var NPS = polarProj("EPSG:3413", "n"), SPS = polarProj("EPSG:3031", "s");
  var proj = EQC;                          // 평면이 지금 쓰는 투영
  function toLL(xy) { return ol.proj.transform(xy, proj, LL); }
  function fromLL(ll) { return ol.proj.transform(ll, LL, proj); }
  /** 그 위도에 맞는 투영. 지금 투영(`cur`)을 주면 되돌이를 둔다 — 문턱에서 오락가락하지 않게 */
  function projFor(lat, cur) {
    var a = Math.abs(lat), edge = !cur ? POLAR_LAT : cur === EQC ? POLAR_LAT + 2 : POLAR_LAT - 2;
    return a < edge ? EQC : lat > 0 ? NPS : SPS;
  }
  /** 평면의 한 단위가 땅의 몇 미터인가. 경위도는 남북 1° 가, 극 평사도법은 그 위도의 축척 (구로 근사) */
  function groundScale(p, lat) {
    if (p === EQC) return M_PER_DEG;
    var ts = POLAR_TS[p.pole] * Math.PI / 180;
    return (1 + Math.sin(Math.abs(lat) * Math.PI / 180)) / (1 + Math.sin(ts));
  }
  function groundRes() {
    var v = flat.getView();
    return v.getResolution() * groundScale(proj, toLL(v.getCenter())[1]);
  }

  // GIBS 4326 격자 — 줌 0 이 512 칸 두 장(한 장이 288°), 줌마다 반씩. 여덟까지다
  var GIBS_MAX = 8;
  function gibsGrid() {
    var res = [];
    for (var z = 0; z <= GIBS_MAX; z++) res.push(0.5625 / Math.pow(2, z));
    return new ol.tilegrid.TileGrid({ extent: [-180, -90, 180, 90], origin: [-180, 90], resolutions: res, tileSize: 512 });
  }
  // GIBS 극지 격자 — 줌 0 이 512 칸 2×2 장(한 칸 8 192 m, ±4 194 304 m). 500 m 판은 넷까지다(지역 탭의 `gibsLayer` 와 같다)
  var GIBS_POLAR_MAX = 4;
  function gibsPolarGrid() {
    var res = [];
    for (var z = 0; z <= GIBS_POLAR_MAX; z++) res.push(8192 / Math.pow(2, z));
    return new ol.tilegrid.TileGrid({ extent: [-POLAR_HALF, -POLAR_HALF, POLAR_HALF, POLAR_HALF],
                                      origin: [-POLAR_HALF, POLAR_HALF], resolutions: res, tileSize: 512 });
  }
  // 배경은 WebGL 타일이다 — 영상 보정(밝기·대비·감마·채도)을 GPU 셰이더로 건다(042). 셰이더가 영상을 읽으려면
  // CORS 로 받아야 한다(GIBS 는 `*`)
  function baseSource(key) {
    var polar = proj !== EQC, e = polar ? (proj === NPS ? "3413" : "3031") : "4326";
    if (BASES[key].wms && polar) key = "bm";       // 극 평면을 그려 주지 않는 WMS(GEBCO) — 옮겨 그리지 못해 Blue Marble 로
    if (BASES[key].wms) {
      return new ol.source.TileWMS({
        url: BASES[key].wms, params: { LAYERS: BASES[key].name, VERSION: "1.1.1", FORMAT: BASES[key].format, TILED: true },
        projection: proj, tileGrid: gibsGrid(), crossOrigin: "anonymous", attributions: BASES[key].credit, wrapX: true,
      });
    }
    return new ol.source.XYZ({
      url: GIBS_WMTS.replace("{e}", e).replace("{name}", BASES[key].name),
      projection: proj, tileGrid: polar ? gibsPolarGrid() : gibsGrid(), crossOrigin: "anonymous",
      attributions: BASES[key].credit, wrapX: !polar,
    });
  }
  function baseLayer(className, key) {
    return new ol.layer.WebGLTile({
      className: className, source: baseSource(key),
      style: { variables: { exposure: 0, contrast: 0, gamma: 1, saturation: 0 },
               exposure: ["var", "exposure"], contrast: ["var", "contrast"],
               gamma: ["var", "gamma"], saturation: ["var", "saturation"] },
    });
  }
  var oBase = baseLayer("moon-base", look.base);
  // 지질도 — 3857 z/x/y 를 어느 투영에서나 OpenLayers 가 옮겨 그린다. 그래서 투영을 바꿔도 소스를 갈지 않는다
  function geoSource(name) {
    if (LAYER[name].grid === "ll") return paleoSource(geoUrl(name), creditOf(name), LAYER[name].max);
    return new ol.source.XYZ({ url: geoUrl(name), maxZoom: GEO_MAX, attributions: creditOf(name),
                               crossOrigin: "anonymous" });            // CORS — 그림으로 뽑으려면 (048)
  }
  // 판 조각 — 경위도 격자(줌 0 이 180° 두 장, 256 칸). 극 평면에서는 OpenLayers 가 옮겨 그린다
  function paleoSource(url, credit, max) {
    var res = [];
    for (var z = 0; z <= (max || PALEO_MAX); z++) res.push(180 / 256 / Math.pow(2, z));
    return new ol.source.XYZ({
      url: url, projection: LL, attributions: credit || PALEO_CREDIT, crossOrigin: "anonymous",
      tileGrid: new ol.tilegrid.TileGrid({ extent: [-180, -90, 180, 90], origin: [-180, 90], resolutions: res, tileSize: 256 }),
    });
  }
  var oGeo = {};
  GEO_NAMES.forEach(function (name) {
    oGeo[name] = new ol.layer.Tile({ source: geoSource(name), visible: false });
  });
  var oPoints = new ol.layer.Group({ layers: [] });
  var flat = new ol.Map({
    target: "map",
    layers: [oBase].concat(GEO_NAMES.map(function (n) { return oGeo[n]; }), [oPoints]),
    view: new ol.View({ projection: EQC, center: [0, 0], resolution: 0.05, maxResolution: 180 / 256,
                        constrainResolution: false }),
    controls: ol.control.defaults.defaults({ attributionOptions: { collapsible: true } }).extend([
      new ol.control.ScaleLine({ target: $("scalebar"), bar: true, steps: 4, text: true, minWidth: 110 }),
    ]),
  });
  window.__gsmEarthFlat = flat;
  var cRaise = {};
  GEO_NAMES.forEach(function (n) { cRaise[n] = [cGeo[n]]; });

  // ══ 이름표 — 산맥·고원·사막·바다 (wetherilli 102) ═══════════════════
  //
  // Natural Earth 의 이름을 화면이 쓴다 — 타일에 구워 넣으면 구를 돌릴 때 글자가 누워 읽히지 않는다. 순위(scalerank,
  // 작을수록 크다)로 멀리서는 큰 것만. 구에서는 땅 위 10 km 에 띄워 지구 뒤쪽 것은 지구가 가린다
  var labelRows = null, labelsAsked = false;
  var cLabels = scene.primitives.add(new Cesium.LabelCollection());
  var oLabels = new ol.layer.Vector({ source: new ol.source.Vector(), declutter: true, zIndex: 90, visible: false,
                                      style: function (f, resolution) {
    var rank = f.get("rank"), ground = resolution * groundScale(proj, 0);
    if (rank > Math.max(0, 9 - Math.log(ground / 60) / Math.LN2)) return null;        // 멀수록 큰 것만
    return new ol.style.Style({ text: new ol.style.Text({
      text: f.get("name"), font: (rank <= 2 ? "600 14px " : "600 12px ") + "system-ui, sans-serif",
      fill: new ol.style.Fill({ color: "#fff4d6" }), stroke: new ol.style.Stroke({ color: "rgba(0,0,0,.85)", width: 3 }) }) });
  } });
  flat.addLayer(oLabels);
  function labelDistance(rank) { return rank <= 1 ? Number.POSITIVE_INFINITY : 2.4e7 * Math.pow(0.62, rank); }
  function syncLabels() {
    var e = entryOf("names"), on = !!e && visibleNow("names");
    cLabels.show = on;
    oLabels.setVisible(on);
    if (!on) return;
    var alpha = e.opacity;
    if (labelRows) {
      for (var i = 0; i < cLabels.length; i++) {
        cLabels.get(i).fillColor = Cesium.Color.fromCssColorString("#fff4d6").withAlpha(alpha);
      }
      oLabels.setOpacity(alpha);
      return;
    }
    if (labelsAsked) return;
    labelsAsked = true;
    fetch(BASE + "earth/labels/").then(function (r) { return r.json(); }).then(function (d) {
      labelRows = d.labels || [];
      labelRows.forEach(function (row) {
        cLabels.add({ position: Cesium.Cartesian3.fromDegrees(row[1], row[2], 10000, ELL), text: row[0],
                      font: (row[3] <= 2 ? "600 15px " : "600 13px ") + "system-ui, sans-serif",
                      fillColor: Cesium.Color.fromCssColorString("#fff4d6").withAlpha(alpha),
                      outlineColor: Cesium.Color.BLACK.withAlpha(0.85), outlineWidth: 3,
                      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                      distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, labelDistance(row[3])) });
      });
      oLabels.getSource().addFeatures(labelRows.map(function (row) {
        return new ol.Feature({ geometry: new ol.geom.Point(fromLL([row[1], row[2]])), name: row[0], rank: row[3] });
      }));
      oLabels.setOpacity(alpha);
    }).catch(function () { labelsAsked = false; });
  }

  // ══ 아라온호 항적 (koprifossillab 006) ═══════════════════════════════
  //
  // 서버가 지역 탭과 같은 GeoJSON(`points/?layer=kopri:araon`)을 준다 — 항적(MultiLineString, 날짜변경선·긴 공백에서
  // 끊어 둔 것)과 마지막 자리 하나. 구에는 Cesium 의 선·점으로, 평면에는 벡터 레이어로. 누르면 점묶음처럼 팝업이 뜬다
  var TRACK_SET = { name: T("아라온호 항적"), color: "#ffb000" };
  var LAST_COLOR = "#e4002b";
  var cTrack = null, oTrack = null, trackAsked = false;
  // 기간 (koprifossillab 017) — 서버가 조각마다 `ago`(지금에서 며칠 전)를 붙여 준다. 고른 기간(1개월 기본·6개월·1년) 안의 조각만
  // 그리고 오래된 것일수록 옅게. 지역 탭(`map.js`)과 같은 열쇠에 기억한다
  var TRACK_PERIODS = THEN.araon_periods || [30, 182, 365];
  var TRACK_PERIOD_LABELS = { 30: "1개월", 182: "6개월", 365: "1년" };
  var trackData = null;
  function trackPeriod() {
    var v = +saved("gsm.araon.period", "0");
    return TRACK_PERIODS.indexOf(v) >= 0 ? v : TRACK_PERIODS[0];
  }
  /** 지금 1, 기간 끝 0.15, 기간 밖 0 — 열 칸으로 끊는다 */
  function trackFade(ago) {
    var period = trackPeriod();
    if (ago == null) return 1;
    if (ago > period) return 0;
    return Math.round((1 - 0.85 * ago / period) * 10) / 10;
  }
  function trackPicker() {
    var row = document.createElement("div");
    row.className = "wind-row";
    var select = document.createElement("select");
    select.setAttribute("aria-label", T("항적 기간"));
    TRACK_PERIODS.forEach(function (days) {
      var option = document.createElement("option");
      option.value = days;
      option.textContent = T(TRACK_PERIOD_LABELS[days] || "{n}일", { n: days });
      select.appendChild(option);
    });
    select.value = trackPeriod();
    select.addEventListener("change", function () {
      save("gsm.araon.period", select.value);
      drawTrack();
    });
    var label = document.createElement("span");
    label.textContent = T("항적 기간");
    row.append(label, select);
    return row;
  }
  /** 받아 둔 항적을 고른 기간으로 다시 긋는다 — 구는 개체를 새로 짓고, 평면은 그림만 다시 칠한다 */
  function drawTrack() {
    if (!trackData) return;
    cTrack.entities.removeAll();
    trackData.features.forEach(function (f) {
      var g = f.geometry, props = f.properties, fade = trackFade(props._ago);
      if (!fade) return;
      function add(opts) { var x = cTrack.entities.add(opts); x.gsmProps = props; x.gsmSet = TRACK_SET; }
      var color = Cesium.Color.fromCssColorString(TRACK_SET.color).withAlpha(fade);
      if (g.type === "MultiLineString") {
        // 지난 항적(`past`, 날짜만 안다)은 가늘게 끊어 — 지금 쌓는 항적과 갈라 보이게 (koprifossillab 009)
        var past = props._code === "past";
        g.coordinates.forEach(function (line) {
          var flatArr = [];
          line.forEach(function (c) { flatArr.push(c[0], c[1]); });
          add({ polyline: { positions: Cesium.Cartesian3.fromDegreesArray(flatArr, ELL), width: past ? 2 : 3, clampToGround: true,
                            material: past
                              ? new Cesium.PolylineDashMaterialProperty({ color: color, dashLength: 12 })
                              : new Cesium.PolylineOutlineMaterialProperty({
                                  color: color, outlineColor: Cesium.Color.BLACK.withAlpha(0.6 * fade), outlineWidth: 1 }) } });
        });
      } else if (g.type === "Point") {
        add({ position: Cesium.Cartesian3.fromDegrees(g.coordinates[0], g.coordinates[1], 0, ELL),
              point: { pixelSize: 11, color: Cesium.Color.fromCssColorString(LAST_COLOR), outlineColor: Cesium.Color.WHITE,
                       outlineWidth: 2, heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                       disableDepthTestDistance: 3000000 },
              label: { text: "ARAON", font: "600 12px system-ui, sans-serif", fillColor: Cesium.Color.WHITE,
                       outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                       pixelOffset: new Cesium.Cartesian2(0, -16), heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                       disableDepthTestDistance: 3000000 } });
      }
    });
    if (oTrack) oTrack.changed();
  }
  var trackStyles = {};
  function trackStyle(f) {
    if (f.getGeometry().getType() === "Point") return trackStyles.dot;
    var fade = trackFade(f.get("_ago")), past = f.get("_code") === "past", key = (past ? "p" : "t") + fade;
    if (!fade) return null;
    if (!trackStyles[key]) {
      var rgb = ol.color.asArray(TRACK_SET.color).slice(0, 3);
      trackStyles[key] = past
        ? new ol.style.Style({ stroke: new ol.style.Stroke({ color: rgb.concat(fade), width: 1.6, lineDash: [6, 4] }) })
        : [new ol.style.Style({ stroke: new ol.style.Stroke({ color: [0, 0, 0, 0.55 * fade], width: 4.5 }) }),
           new ol.style.Style({ stroke: new ol.style.Stroke({ color: rgb.concat(fade), width: 2.5 }) })];
    }
    return trackStyles[key];
  }
  trackStyles.dot = new ol.style.Style({
    image: new ol.style.Circle({ radius: 6, fill: new ol.style.Fill({ color: LAST_COLOR }),
                                 stroke: new ol.style.Stroke({ color: "#fff", width: 2 }) }),
    text: new ol.style.Text({ text: "ARAON", offsetY: -16, font: "600 12px system-ui, sans-serif",
                              fill: new ol.style.Fill({ color: "#fff" }), stroke: new ol.style.Stroke({ color: "#000", width: 3 }) }) });
  function syncTrack() {
    var e = entryOf("araon"), on = !!e && visibleNow("araon");
    if (cTrack) cTrack.show = on;
    if (oTrack) { oTrack.setVisible(on); if (e) oTrack.setOpacity(e.opacity); }
    if (!on || trackAsked) return;
    trackAsked = true;
    fetch(BASE + "points/?layer=kopri:araon&lang=" + LANG).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (d) {
      var labels = d.labels || {};
      (d.features || []).forEach(function (f) {
        // 팝업은 열 이름 그대로 적는다 — 서버의 이름표(`labels`)로 바꿔 둔다
        var raw = f.properties || {}, props = {};
        Object.keys(labels).forEach(function (k) { if (raw[k] != null && raw[k] !== "") props[labels[k]] = raw[k]; });
        if (raw.code === "last") props["이름표"] = "ARAON";
        props._code = raw.code;
        props._ago = raw.ago;
        f.properties = props;
      });
      trackData = d;
      cTrack = new Cesium.CustomDataSource("araon");
      viewer.dataSources.add(cTrack);
      oTrack = new ol.layer.Vector({
        source: new ol.source.Vector({ features: new ol.format.GeoJSON().readFeatures(d,
                                         { dataProjection: LL, featureProjection: proj }) }),
        style: trackStyle,
      });
      oTrack.set("gsmSet", TRACK_SET);
      oPoints.getLayers().push(oTrack);
      drawTrack();
      syncTrack();
    }).catch(function () { trackAsked = false; });
  }

  // ══ 지구 속 — OPT1 의 섭입한 판·하부 더미·판 경계 (wetherilli 106) ══════
  //
  // 서버가 시점마다 구워 둔 삼각형(반지름 1 의 구, z 가 북)을 받아 Cesium 의 프리미티브로 땅 밑에 그린다. 방향은 그대로 두고
  // 길이만 타원체의 겉에 맞춘다 — 반지름 비(깊이)가 지켜진다. 켜면 땅을 비치게 한다(`globe.translucency`). 평면에는 없다.
  // **모의 결과이지 관측이 아니다.** 옛 연대에는 OPT1 의 맨틀 기준틀이라 PALEOMAP 판 조각과 맞지 않는다 — 캡션에 적는다
  var MANTLE = THEN.mantle || {};                    // {시점: {slabs: 점 수, piles: …, boundaries: …}}
  // 토모그래피 그림의 관례대로 찬 슬랩은 파랑, 뜨거운 더미는 빨강 (wetherilli 116). 앞서는 바다에 묻힐까 옅은 청록을
  // 썼는데, 그 청록이 이 화면의 테마색·비친 바다와 겹쳐 슬랩이 보이지 않았다. 이제는 맨틀을 켜면 땅이 물러나므로
  // (`MANTLE_SURFACE`) 바다의 파랑과 다툴 일이 적다. 색은 깊이마다 달라 `MANTLE_DEPTH` 에 둔다. 판 경계만 한 색이다
  var BOUNDARY_COLOUR = "#ffe066";
  // 깊이에 따른 음영 (wetherilli 117) — 얕을수록 밝고 깊을수록 어둡다. 한 색으로 칠하면 깊이가 다른 슬랩이 겹쳐 한 장의
  // 판으로 보였다(116). 잣대는 슬랩·더미가 같다 — 반지름 0.95(깊이 약 320 km, OPT1 이 슬랩을 그리기 시작하는 곳)에서
  // 0.55(핵–맨틀 경계 2 890 km) 까지. 같은 밝기면 같은 깊이다. 더미는 대개 깊어 어둡다 — 그것이 뜻이다
  var MANTLE_DEPTH = { top: 0.95, bottom: 0.55,
                       slabs: ["#c4dcff", "#1d47b8"], piles: ["#ffc2b0", "#a8170d"] };
  // 맨틀을 켜면 땅이 물러난다 (wetherilli 116) — 구의 겉은 이만큼만 비치고(`frontFaceAlpha`), 그 위에 얹은
  // 레이어(지질·화석 산지·옛 해안선…)는 제 투명도에 `overlay` 를 한 번 더 곱한다. 겉을 35% 로만 비쳤을 때는 화석 산지 점과
  // 지질 단위가 맨틀을 덮어 땅속을 보려고 켰는데 땅 위가 가장 시끄러웠다. 평면에는 맨틀이 없어 구에만 건다
  var MANTLE_SURFACE = { globe: 0.2, overlay: 0.4 };
  var mantleFrame = null, mantlePrims = [], mantleAsked = 0;
  function mantleFrameOf(a) {                       // 서버의 `mantle.frame_of` 와 같다 — 가장 가까운 것, 같으면 오래된 쪽
    return Math.max(0, Math.min(50, Math.floor((1000 - a) / 20 + 0.5 - 1e-9)));
  }
  function mantlePrimitive(buf, count, name, alpha) {
    var f32 = new Float32Array(buf, 0, count * 3), idx = new Uint32Array(buf, count * 12);
    var pos = new Float64Array(count * 3), scratch = new Cesium.Cartesian3(), onEll = new Cesium.Cartesian3();
    for (var i = 0; i < count; i++) {
      var x = f32[3 * i], y = f32[3 * i + 1], z = f32[3 * i + 2], r = Math.sqrt(x * x + y * y + z * z) || 1;
      Cesium.Cartesian3.fromElements(x / r, y / r, z / r, scratch);
      ELL.scaleToGeocentricSurface(scratch, onEll);
      pos[3 * i] = onEll.x * r; pos[3 * i + 1] = onEll.y * r; pos[3 * i + 2] = onEll.z * r;
    }
    var lines = name === "boundaries";
    var geometry = new Cesium.Geometry({
      attributes: { position: new Cesium.GeometryAttribute({ componentDatatype: Cesium.ComponentDatatype.DOUBLE,
                                                             componentsPerAttribute: 3, values: pos }) },
      indices: idx, primitiveType: lines ? Cesium.PrimitiveType.LINES : Cesium.PrimitiveType.TRIANGLES,
      boundingSphere: Cesium.BoundingSphere.fromVertices(pos),
    });
    if (lines) {
      var colour = Cesium.Color.fromCssColorString(BOUNDARY_COLOUR);
      return new Cesium.Primitive({ asynchronous: false,
        geometryInstances: new Cesium.GeometryInstance({ geometry: geometry,
          attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(colour) } }),
        appearance: new Cesium.PerInstanceColorAppearance({ flat: true, translucent: false }) });
    }
    Cesium.GeometryPipeline.computeNormal(geometry);
    return new Cesium.Primitive({ asynchronous: false,
      geometryInstances: new Cesium.GeometryInstance({ geometry: geometry }),
      appearance: new Cesium.MaterialAppearance({ material: depthMaterial(name, alpha),
                                                   faceForward: true, translucent: alpha < 1, closed: false }) });
  }
  /** 깊이로 칠하는 재질 — 조각마다 지구 중심에서 잰 반지름(지구 반지름 1)을 읽어 얕은 색과 깊은 색 사이를 고른다.
   *  꼭짓점에 색을 싣지 않고 셰이더가 고르는 까닭은, 삼각형이 깊이를 가로지를 때도 매끄럽게 이어지게 하려는 것이다 */
  function depthMaterial(name, alpha) {
    var pair = MANTLE_DEPTH[name];
    return new Cesium.Material({ fabric: {
      uniforms: { shallow: Cesium.Color.fromCssColorString(pair[0]), deep: Cesium.Color.fromCssColorString(pair[1]),
                  top: MANTLE_DEPTH.top, bottom: MANTLE_DEPTH.bottom, alpha: alpha },
      source: [
        "czm_material czm_getMaterial(czm_materialInput materialInput) {",
        "  czm_material m = czm_getDefaultMaterial(materialInput);",
        "  vec3 p = (czm_inverseView * vec4(-materialInput.positionToEyeEC, 1.0)).xyz;",
        "  float t = clamp((top - length(p) / 6371000.0) / (top - bottom), 0.0, 1.0);",
        "  m.diffuse = mix(shallow.rgb, deep.rgb, t);",
        "  m.alpha = alpha;",
        "  return m;",
        "}",
      ].join("\n"),
    } });
  }
  /** 구에 맨틀이 서 있나 — 땅이 물러날지 정한다 */
  function mantleShown() {
    return isOn("mantle") && visibleNow("mantle") && Object.keys(MANTLE).length > 0;
  }
  /** 구에 얹은 레이어의 투명도 — 맨틀이 서면 물러난다 */
  function globeAlpha(e) { return e.opacity * (mantleShown() ? MANTLE_SURFACE.overlay : 1); }
  function dropMantle() {
    mantlePrims.forEach(function (p) { scene.primitives.remove(p); });
    mantlePrims = [];
  }
  function syncMantle(restyle) {
    var e = entryOf("mantle"), on = mantleShown();
    scene.globe.translucency.enabled = on;
    scene.globe.translucency.frontFaceAlpha = MANTLE_SURFACE.globe;
    scene.globe.translucency.backFaceAlpha = 0.0;
    if (!on) { dropMantle(); mantleFrame = null; return; }
    var frame = mantleFrameOf(age);
    if (!MANTLE[frame]) { dropMantle(); mantleFrame = null; return; }        // 그 시점을 굽지 않았다
    if (frame === mantleFrame && !restyle) return;
    mantleFrame = frame;
    var mine = ++mantleAsked, alpha = e.opacity;
    Promise.all(["slabs", "piles", "boundaries"].map(function (name) {
      return fetch(BASE + "earth/mantle/" + frame + "/" + name + ".bin").then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.arrayBuffer();
      });
    })).then(function (bufs) {
      if (mine !== mantleAsked) return;
      dropMantle();
      ["slabs", "piles", "boundaries"].forEach(function (name, i) {
        // 파일은 점(float32 xyz) 다음에 이음(uint32) — 점 수는 화면에 실어 보낸 목록에서
        mantlePrims.push(scene.primitives.add(mantlePrimitive(bufs[i], MANTLE[frame][name], name, alpha)));
      });
    }).catch(function () { if (mine === mantleAsked) mantleFrame = null; });
  }

  // ══ 구 ⇄ 평면 ═════════════════════════════════════════════════════
  //
  // 넘는 높이를 둘로 둔다(되돌이). 구에서 800 km 밑으로 곧장 내려다보면 평면으로, 평면에서 1 280 km
  // 높이만큼 멀어지면 구로. 둘이 같으면 문턱에서 오락가락한다. 화성(400·640 km)의 두 배 — 지구가 두 배 크다
  var TO_FLAT_H = 800000, TO_GLOBE_H = 1280000;
  var HOME_H = 20000000;                  // 처음·"처음 자리" 의 높이 — 반지름의 세 배쯤, 한 반구가 다 든다
  var HOME = [127.5, 30];                 // 처음 자리 — 한반도가 가운데 조금 위에 선다
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
    var c = ELL.cartesianToCartographic(viewer.camera.positionWC);
    return c ? { lon: Cesium.Math.toDegrees(c.longitude), lat: Cesium.Math.toDegrees(c.latitude), h: c.height } : null;
  }
  function flyGlobe(lon, lat, h, duration) {
    var dest = Cesium.Cartesian3.fromDegrees(lon, lat, h, ELL);
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
      // 위도가 투영을 고른다 — 65° 너머는 극 평사도법 (065)
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
    save("gsm.earth.mode", mode);
  }

  /** 평면의 투영을 바꾼다 (화성의 065·달의 052). 타일 소스를 갈아 끼우고, 벡터는 모양을 옮기고, 찍고 잰 것은
   *  경위도에서 다시 그린다. 새 뷰는 `ll` 을 가운데에, 땅의 해상도 `ground` 로 연다. 바뀌었으면 true */
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
    oBase.setSource(baseSource(look.base));       // 지질도(3857)는 OpenLayers 가 새 투영으로 옮겨 그린다
    var polar = p !== EQC;
    flat.setView(new ol.View({
      projection: p, center: fromLL(ll), resolution: ground / groundScale(p, ll[1]), constrainResolution: false,
      maxResolution: polar ? 2 * POLAR_HALF / 256 : 180 / 256,
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
    save("gsm.earth.view", JSON.stringify({
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
    // 해상도는 땅의 미터로 적는다 — 투영마다 단위의 뜻이 달라서다 (065)
    save("gsm.earth.flat", JSON.stringify({ lon: +ll[0].toFixed(5), lat: +ll[1].toFixed(5), res: Math.round(ground) }));
    if (drawing()) return;                // 그리던 선이 끊기지 않게 (041)
    if (ground > heightToRes(TO_GLOBE_H)) { setMode("globe"); return; }
    // 극으로 가면 극 평사도법으로, 돌아오면 등거리 원통으로 — 문턱 둘레 2° 는 되돌이다 (065)
    useProj(projFor(ll[1], proj), ll, ground);
  });

  $("tool-mode").addEventListener("click", function () {
    if (mode === "globe") {
      var c = cameraLL();
      if (!c) return;
      // 멀리서 누르면 문턱 높이까지 내려와 평면으로. 극이면 극 평사도법이다 (065)
      setMode("flat", { lon: c.lon, lat: c.lat, h: Math.min(c.h, TO_FLAT_H) });
    } else {
      autoFlat = false;
      setMode("globe", { h: Math.max(resToHeight(groundRes()), TO_FLAT_H * 1.4) });
    }
  });
  $("tool-home").addEventListener("click", function () {
    if (mode === "flat") setMode("globe", { h: HOME_H });
    flyGlobe(HOME[0], HOME[1], HOME_H, 1.5);
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
  // 보던 산이 가운데에 머문다.
  //
  // - 방위는 **지구의 북극**(자전축을 그 점의 수평면에 내린 쪽)이 0°, 시계 방향. 극점 위에서는 북쪽이 없으므로
  //   **위도 89.5° 너머는 본초 자오선(경도 0°, 그리니치, +X 축) 쪽이 0°** 다 — 화성의 것을 그대로 두었다
  // - 기울기는 그 점에서 **타원체에 접하는 수평면**으로 잰다. 지형의 경사로 재면 절벽에서 값이
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
    if (!pos) pos = viewer.camera.pickEllipsoid(mid, ELL);
    return pos ? { pos: pos, range: Cesium.Cartesian3.distance(viewer.camera.positionWC, pos) } : null;
  }
  /** 점 `pos` 의 수평면에서 본 카메라의 방위·기울기(도). `cesium` 이면 Cesium 의 동-북-위를 쓴다 —
   *  `lookAt` 에 넘길 값이다. 아니면 위의 기준(극 가까이는 지구 쪽)이다. */
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

  // 방위 단추(나침반) — 바늘이 지구의 북쪽을 가리킨다. 누르면 기울기는 두고 북쪽을 위로 돌린다
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
    var p = { pos: Cesium.Cartesian3.fromDegrees(ll[0], ll[1], ground, ELL), range: h - ground };
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
    save("gsm.earth.base", look.base);
    var layers = viewer.imageryLayers;
    layers.remove(cBase, true);
    cBase = cesiumBase(look.base);
    layers.add(cBase, 0);
    oBase.setSource(baseSource(look.base));
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
  // 화성의 "음영 겹치기" 는 뺐다 — 지구의 배경(Blue Marble)은 이미 음영을 품었다
  var TUNE_DEFAULT = { bright: 100, contrast: 100, gamma: 100, sat: 100, shade: false };
  var PRESETS = {
    crisp: { bright: 105, contrast: 160, gamma: 90, sat: 100, shade: false },
    relief: { bright: 110, contrast: 130, gamma: 110, sat: 100, shade: false },
  };
  var tune = (function () {
    try { return Object.assign({}, TUNE_DEFAULT, JSON.parse(saved("gsm.earth.tune", "{}")) || {}); }
    catch (e) { return Object.assign({}, TUNE_DEFAULT); }
  })();
  var TUNES = ["bright", "contrast", "gamma", "sat"];
  function tuneText(key, v) { return key === "gamma" ? (v / 100).toFixed(2) : v + "%"; }
  function applyTune() {
    cBase.brightness = tune.bright / 100;
    cBase.contrast = tune.contrast / 100;
    cBase.gamma = tune.gamma / 100;
    cBase.saturation = tune.sat / 100;
    [oBase].forEach(function (layer) {
      layer.updateStyleVariables({ exposure: tune.bright / 100 - 1, contrast: tune.contrast / 100 - 1,
                                   gamma: tune.gamma / 100, saturation: tune.sat / 100 - 1 });
    });
    TUNES.forEach(function (k) {
      $("tune-" + k).value = tune[k];
      $("tune-" + k + "-num").textContent = tuneText(k, tune[k]);
    });
    var changed = TUNES.some(function (k) { return tune[k] !== TUNE_DEFAULT[k]; });
    $("tune-state").textContent = changed ? T("고침") : "";
    save("gsm.earth.tune", JSON.stringify(tune));
  }
  TUNES.forEach(function (k) {
    $("tune-" + k).addEventListener("input", function () { tune[k] = +this.value; applyTune(); });
  });
  $("tune-reset").addEventListener("click", function () { tune = Object.assign({}, TUNE_DEFAULT); applyTune(); });
  document.querySelectorAll("#tune [data-preset]").forEach(function (b) {
    b.addEventListener("click", function () { tune = Object.assign({}, PRESETS[b.dataset.preset]); applyTune(); });
  });
  applyTune();

  // ══ 바람 — 지금(GFS)·지난(ERA5), 지상 10 m·250 hPa (koprifossillab P02) ══════════════
  //
  // 서버가 구워 둔 1440×721 텍스처(R=u·G=v, 경도 −180 부터, `wind.py`)를 받아 입자를 흘린다. 입자는 경위도로 옮기고, 화면
  // 자리는 평면이면 OpenLayers 가(4326·3413·3031 모두), 구면 Cesium 이 셈한다 — 한 벌로 세 평면과 구를 다 덮는다.
  // Canvas 2D 다. 꼬리는 앞 프레임을 조금씩 지워 만든다. 보는 자리가 움직이면 꼬리를 지우고 새로 긋는다
  var WIND = {
    src: saved("gsm.earth.wind.src", "gfs") === "era5" ? "era5" : "gfs",       // 기본은 지금의 바람
    level: saved("gsm.earth.wind.level", "10m") === "250hPa" ? "250hPa" : "10m",  // 기본은 지상 10 m
    day: saved("gsm.earth.wind.day", ""),                                        // 지난 바람의 날 (YYYYMMDD)
    index: null, playing: false,
  };
  var WIND_REF = { "10m": 12, "250hPa": 45 };   // 이 빠르기(m/s)면 한 프레임에 WIND_PX 칸쯤 간다
  var WIND_PX = 1.4, WIND_LIFE = 80, WIND_FADE = 0.93, WIND_PLAY_MS = 1500;
  // 빠르기를 기준의 몇 배인가로 여덟 칸
  // 해류와 함께 켜도 갈리게 따뜻한 쪽만 쓴다 — 느리면 엷은 회색·흰색, 빠르면 노랑·주황·빨강. 해류는 청록 쪽이다 (koprifossillab 016)
  var WIND_COLORS = ["#bfbfbf", "#e3e3e3", "#ffffff", "#fff2a8", "#ffd65c", "#ffab40", "#ff7a33", "#ff3d3d"];
  var M_PER_LAT = Math.PI * R / 180;
  var windCanvas = $("wind-canvas"), windCtx = windCanvas.getContext("2d");
  var windField = null, windNext = null, windBlend = 0, windParticles = [], windRaf = 0, windViewKey = "", windLast = 0;
  var windCache = {}, windAsked = 0;

  function windTimes() { return (WIND.index && WIND.index[WIND.src] && WIND.index[WIND.src].times) || []; }
  /** 지금 보일 시각의 목록 한 줄 — 지금의 바람은 가장 새 판, 지난 바람은 고른 날(없으면 가장 가까운 날) */
  function windEntry(offset) {
    var list = windTimes();
    if (!list.length) return null;
    if (WIND.src === "gfs") { var pair = windNowPair(); return pair && pair.a; }
    var i = 0;
    for (var k = 0; k < list.length; k++) if (list[k].t <= WIND.day) i = k;
    return list[Math.min(list.length - 1, i + (offset || 0))] || null;
  }
  function stampMs(t) { return Date.UTC(+t.slice(0, 4), +t.slice(4, 6) - 1, +t.slice(6, 8), +(t.slice(8, 10) || 0)); }
  /** 지금의 바람 (koprifossillab 008) — 지금 시각 바로 앞의 장(분석이나 앞선 예보, `a`)과 바로 뒤의 장(예보, `b`), 그리고 `b` 의
   *  가중치 `w`. 목록의 시각은 유효 시각이고 차례로 서 있다. 뒤 장이 없으면(새 판이 늦다) 가장 새 장 하나를 그대로 */
  function windNowPair() {
    var list = windTimes(), now = Date.now(), a = null, b = null;
    list.forEach(function (e) { if (stampMs(e.t) <= now) a = e; else if (!b) b = e; });
    if (!a) return b ? { a: b, b: null, w: 0 } : null;
    if (!b) return { a: a, b: null, w: 0 };
    return { a: a, b: b, w: (now - stampMs(a.t)) / (stampMs(b.t) - stampMs(a.t)) };
  }
  var windPair = null;
  function windNowText() {
    var p = windPair;
    if (!p) return T("바람 자료가 아직 없다");
    function side(e) { return T(e.fh ? "{t} 예보" : "{t} 분석", { t: e.t.slice(8, 10) + " UTC" }); }
    if (!p.b) return T(p.a.fh ? "{t} UTC · GFS 예보" : "{t} UTC · GFS 분석", { t: windStampText(p.a.t) });
    var now = new Date().toISOString();
    return T("{now} UTC 무렵 — GFS {from} ↔ {to}", { now: now.slice(0, 10) + " " + now.slice(11, 16), from: side(p.a), to: side(p.b) });
  }
  function windStampText(t) {
    return t.slice(0, 4) + "-" + t.slice(4, 6) + "-" + t.slice(6, 8) + (t.length > 8 ? " " + t.slice(8, 10) + ":00" : " 00:00");
  }
  function windIndex() {
    return fetch(BASE + "earth/wind/").then(function (r) { return r.json(); }).then(function (d) {
      WIND.index = d;
      if (!WIND.day && d.era5 && d.era5.times.length) WIND.day = d.era5.times[0].t;
      return d;
    });
  }
  /** 텍스처 한 장 -> {u, v} (Float32Array, 721×1440). 같은 것을 두 번 받지 않게 몇 장만 들고 있다 */
  function windLoad(entry) {
    var key = WIND.src + "/" + entry.t + "/" + WIND.level;
    // GFS 는 같은 유효 시각을 새 판이 다시 낸다 — 판을 주소에 붙여 브라우저 캐시가 옛 그림을 내지 않게 (koprifossillab 008)
    var url = BASE + "earth/wind/" + key + ".png" + (entry.run ? "?run=" + entry.run : "");
    key = url;
    if (windCache[key]) return windCache[key];
    var scale = entry[WIND.level];
    windCache[key] = new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () {
        var c = document.createElement("canvas");
        c.width = 1440; c.height = 721;
        var g = c.getContext("2d", { willReadFrequently: true });
        g.drawImage(img, 0, 0);
        var px = g.getImageData(0, 0, 1440, 721).data, n = 1440 * 721;
        var u = new Float32Array(n), v = new Float32Array(n);
        var u0 = scale.u[0], us = (scale.u[1] - scale.u[0]) / 255, v0 = scale.v[0], vs = (scale.v[1] - scale.v[0]) / 255;
        for (var i = 0; i < n; i++) { u[i] = u0 + px[4 * i] * us; v[i] = v0 + px[4 * i + 1] * vs; }
        resolve({ u: u, v: v, t: entry.t });
      };
      img.onerror = function () { delete windCache[key]; reject(new Error(key)); };
      img.src = url;
    });
    var keys = Object.keys(windCache);
    if (keys.length > 6) delete windCache[keys[0]];
    return windCache[key];
  }
  function sampleField(f, lon, lat) {
    var x = (lon + 180) * 4, y = (90 - lat) * 4;
    if (!(y >= 0 && y <= 720)) return null;
    var x0 = Math.floor(x), y0 = Math.floor(y), fx = x - x0, fy = y - y0;
    x0 = ((x0 % 1440) + 1440) % 1440;
    var x1 = (x0 + 1) % 1440, y1 = Math.min(720, y0 + 1);
    var a = y0 * 1440 + x0, b = y0 * 1440 + x1, c = y1 * 1440 + x0, d = y1 * 1440 + x1;
    var w00 = (1 - fx) * (1 - fy), w10 = fx * (1 - fy), w01 = (1 - fx) * fy, w11 = fx * fy;
    return [f.u[a] * w00 + f.u[b] * w10 + f.u[c] * w01 + f.u[d] * w11,
            f.v[a] * w00 + f.v[b] * w10 + f.v[c] * w01 + f.v[d] * w11];
  }
  /** 재생 중이면 두 날 사이를 섞는다 */
  function windAt(lon, lat) {
    var a = sampleField(windField, lon, lat);
    if (!a || !windNext || !windBlend) return a;
    var b = sampleField(windNext, lon, lat);
    return b ? [a[0] + (b[0] - a[0]) * windBlend, a[1] + (b[1] - a[1]) * windBlend] : a;
  }

  // ── 화면 자리 ──
  var windOccluder = null;
  function windToScreen(lon, lat) {
    if (mode === "flat") return flat.getPixelFromCoordinate(fromLL([lon, lat]));
    var c = Cesium.Cartesian3.fromDegrees(lon, lat, 0, ELL);
    if (!windOccluder.isPointVisible(c)) return null;              // 지구 뒤쪽
    var w = Cesium.SceneTransforms.worldToWindowCoordinates(scene, c);
    return w ? [w.x, w.y] : null;
  }
  function windFromScreen(x, y) {
    if (mode === "flat") {
      var c = flat.getCoordinateFromPixel([x, y]);
      if (!c) return null;
      var ll = toLL(c);
      return isFinite(ll[0]) && Math.abs(ll[1]) < 89.5 ? ll : null;
    }
    var cart = viewer.camera.pickEllipsoid(new Cesium.Cartesian2(x, y), ELL);
    if (!cart) return null;                                          // 하늘
    var g = ELL.cartesianToCartographic(cart);
    return [Cesium.Math.toDegrees(g.longitude), Cesium.Math.toDegrees(g.latitude)];
  }
  /** 화면 한 칸이 땅의 몇 미터인가 — 입자의 걸음을 화면에 맞춘다 */
  function windMpp() {
    if (mode === "flat") return groundRes();
    var c = cameraLL();
    return c ? heightToRes(Math.max(1000, c.h)) : 10000;
  }
  function windKey() {
    if (mode === "flat") {
      var v = flat.getView();
      return "f" + proj.getCode() + v.getCenter().join(",") + "/" + v.getResolution() + "/" + v.getRotation();
    }
    var cam = viewer.camera;
    return "g" + [cam.positionWC.x, cam.positionWC.y, cam.positionWC.z, cam.directionWC.x, cam.directionWC.y,
                  cam.directionWC.z].map(function (n) { return n.toFixed(1); }).join(",");
  }
  function windSpawn(p) {
    var w = windCanvas.clientWidth, h = windCanvas.clientHeight;
    for (var tries = 0; tries < 12; tries++) {
      var ll = windFromScreen(Math.random() * w, Math.random() * h);
      if (ll) { p.lon = ll[0]; p.lat = ll[1]; p.age = Math.floor(Math.random() * WIND_LIFE); p.xy = null; return; }
    }
    p.lon = NaN;                                                     // 화면에 땅이 없다 — 다음 프레임에 다시
    p.xy = null;
  }
  function windResize() {
    var w = wrap.clientWidth, h = wrap.clientHeight, r = window.devicePixelRatio || 1;
    if (windCanvas.width !== Math.round(w * r) || windCanvas.height !== Math.round(h * r)) {
      windCanvas.width = Math.round(w * r); windCanvas.height = Math.round(h * r);
      windCtx.setTransform(r, 0, 0, r, 0, 0);
    }
    // 입자 수는 화면 넓이를 따른다 — 휴대폰은 적게
    var want = Math.max(600, Math.min(5000, Math.round(w * h / 260)));
    while (windParticles.length < want) { var p = {}; windSpawn(p); windParticles.push(p); }
    windParticles.length = want;
  }
  function windFrame(now) {
    windRaf = requestAnimationFrame(windFrame);
    if (document.hidden) return;
    // 재생 — 다음 날의 바람·구름이 다 왔으면 섞기를 채운다. 바람이 꺼져 있어도 구름을 위해 돈다
    if (WIND.playing && nextReady) {
      windBlend += (now - (windLast || now)) / WIND_PLAY_MS;
      if (windBlend >= 1) windAdvance();
      else applyCloud();
    }
    if (!windShown() || !windField) { windLast = now; return; }
    if (mode === "globe") windOccluder = new Cesium.EllipsoidalOccluder(ELL, viewer.camera.positionWC);
    var w = windCanvas.clientWidth, h = windCanvas.clientHeight;
    var key = windKey();
    if (key !== windViewKey) {                                       // 움직였다 — 꼬리를 지운다
      windViewKey = key;
      windCtx.clearRect(0, 0, w, h);
      windParticles.forEach(function (p) { p.xy = null; });
    } else {
      windCtx.globalCompositeOperation = "destination-in";
      windCtx.fillStyle = "rgba(0,0,0," + WIND_FADE + ")";
      windCtx.fillRect(0, 0, w, h);
      windCtx.globalCompositeOperation = "source-over";
    }
    windLast = now;
    var ref = WIND_REF[WIND.level], k = windMpp() * WIND_PX / ref;  // 1 m/s 가 한 프레임에 가는 미터
    var buckets = WIND_COLORS.map(function () { return []; });
    windParticles.forEach(function (p) {
      if (!(p.age < WIND_LIFE) || !isFinite(p.lon)) { windSpawn(p); return; }
      p.age++;
      var uv = windAt(p.lon, p.lat);
      if (!uv) { windSpawn(p); return; }
      var cos = Math.max(0.05, Math.cos(p.lat * Math.PI / 180));
      var lat = p.lat + uv[1] * k / M_PER_LAT, lon = p.lon + uv[0] * k / (M_PER_LAT * cos);
      if (Math.abs(lat) > 89.5) { windSpawn(p); return; }
      var xy = windToScreen(lon, lat);
      if (!xy || xy[0] < -20 || xy[1] < -20 || xy[0] > w + 20 || xy[1] > h + 20) { windSpawn(p); return; }
      if (p.xy && Math.abs(xy[0] - p.xy[0]) + Math.abs(xy[1] - p.xy[1]) < 60) {
        var s = Math.sqrt(uv[0] * uv[0] + uv[1] * uv[1]) / ref;
        buckets[Math.min(WIND_COLORS.length - 1, Math.floor(s * 3))].push(p.xy[0], p.xy[1], xy[0], xy[1]);
      }
      p.lon = lon; p.lat = lat; p.xy = xy;
    });
    windCtx.lineWidth = 1.0;
    buckets.forEach(function (segs, i) {
      if (!segs.length) return;
      windCtx.strokeStyle = WIND_COLORS[i];
      windCtx.beginPath();
      for (var j = 0; j < segs.length; j += 4) { windCtx.moveTo(segs[j], segs[j + 1]); windCtx.lineTo(segs[j + 2], segs[j + 3]); }
      windCtx.stroke();
    });
  }
  function windShown() { return isOn("wind") && visibleNow("wind"); }
  function cloudShown() { return isOn("cloud") && visibleNow("cloud"); }
  /** 시각을 맞추는 일(목록·가중치·재생)은 바람과 구름이 함께 쓴다 — 둘 가운데 하나라도 켜져 있으면 돈다 (koprifossillab 011) */
  function fluxShown() { return windShown() || cloudShown(); }

  // ── 구름 (koprifossillab 011) ──
  //
  // 서버가 종류마다 회색 PNG(0–255 = 구름량 0–1)를 준다. 두 시각의 구름량을 가중치로 섞어 흰색·투명도 영상 한 장을 만들어
  // 구(Cesium 영상 레이어)와 평면(OpenLayers `ImageStatic`, 극 평면은 OpenLayers 가 옮겨 그린다)에 덮는다. 투명도 레이어 두
  // 장을 겹치지 않는 것은 가운데 시각에 구름이 옅어 보이기 때문이다. 가중치는 1/16 로 끊어 영상을 바뀔 때만 다시 만든다
  var CLOUD = { kind: saved("gsm.earth.cloud.kind", "total") };
  if (["total", "low", "mid", "high"].indexOf(CLOUD.kind) < 0) CLOUD.kind = "total";
  var CLOUD_ALPHA = new Uint8ClampedArray(256);     // 구름량 -> 투명도. 옅은 구름도 보이게 조금 굽혔다
  for (var ci = 0; ci < 256; ci++) CLOUD_ALPHA[ci] = Math.round(255 * 0.9 * Math.pow(ci / 255, 0.85));
  var cloudA = null, cloudB = null, cloudNext = null, cloudCache = {}, cloudShownKey = "";
  var cloudCanvas = document.createElement("canvas");
  cloudCanvas.width = 1440; cloudCanvas.height = 721;
  var cloudCtx = cloudCanvas.getContext("2d"), cloudImage = cloudCtx.createImageData(1440, 721);
  for (var cj = 0; cj < cloudImage.data.length; cj += 4) {
    cloudImage.data[cj] = cloudImage.data[cj + 1] = cloudImage.data[cj + 2] = 255;
  }
  var cCloud = null, cloudBlob = null;
  var oCloud = new ol.layer.Image({ zIndex: 60, visible: false });
  flat.addLayer(oCloud);
  function cloudLoad(entry) {
    if (!entry || !entry.clouds || entry.clouds.indexOf(CLOUD.kind) < 0) return Promise.resolve(null);
    var url = BASE + "earth/wind/" + WIND.src + "/" + entry.t + "/cloud-" + CLOUD.kind + ".png" +
              (entry.run ? "?run=" + entry.run : "");
    if (cloudCache[url]) return cloudCache[url];
    cloudCache[url] = new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () {
        var c = document.createElement("canvas");
        c.width = 1440; c.height = 721;
        var g = c.getContext("2d", { willReadFrequently: true });
        g.drawImage(img, 0, 0);
        var px = g.getImageData(0, 0, 1440, 721).data, n = 1440 * 721, out = new Uint8Array(n);
        for (var i = 0; i < n; i++) out[i] = px[4 * i];
        out.t = entry.t;
        resolve(out);
      };
      img.onerror = function () { delete cloudCache[url]; reject(new Error(url)); };
      img.src = url;
    });
    var keys = Object.keys(cloudCache);
    if (keys.length > 6) delete cloudCache[keys[0]];
    return cloudCache[url];
  }
  function hideCloud() {
    if (cCloud) { viewer.imageryLayers.remove(cCloud, true); cCloud = null; }
    oCloud.setVisible(false);
    cloudShownKey = "";
  }
  /** 지금의 가중치(`windBlend`)로 두 구름을 섞어 덮는다. `force` 가 아니면 1/16 이 바뀔 때만 */
  function applyCloud(force) {
    var e = entryOf("cloud");
    if (!cloudShown() || !cloudA) { hideCloud(); return; }
    var b = cloudB || cloudNext, w = b ? Math.round(windBlend * 16) / 16 : 0;
    var key = cloudA.t + "/" + (b ? b.t : "") + "/" + w + "/" + CLOUD.kind;
    if (cCloud) { cCloud.alpha = e.opacity; viewer.imageryLayers.raiseToTop(cCloud); }
    oCloud.setOpacity(e.opacity);
    if (!force && key === cloudShownKey) return;
    cloudShownKey = key;
    var d = cloudImage.data, n = 1440 * 721, a = cloudA;
    if (b && w > 0) for (var i = 0; i < n; i++) d[4 * i + 3] = CLOUD_ALPHA[(a[i] * (1 - w) + b[i] * w + 0.5) | 0];
    else for (var k = 0; k < n; k++) d[4 * k + 3] = CLOUD_ALPHA[a[k]];
    cloudCtx.putImageData(cloudImage, 0, 0);
    cloudCanvas.toBlob(function (blob) {
      if (key !== cloudShownKey || !cloudShown()) return;
      var url = URL.createObjectURL(blob), old = cCloud, oldBlob = cloudBlob;
      cloudBlob = url;
      var layer = Cesium.ImageryLayer.fromProviderAsync(Cesium.SingleTileImageryProvider.fromUrl(url, {
        rectangle: Cesium.Rectangle.fromDegrees(-180, -90, 180, 90), credit: "NOAA GFS · ERA5 (Copernicus)" }));
      layer.alpha = entryOf("cloud").opacity;
      viewer.imageryLayers.add(layer);
      cCloud = layer;
      // 새 장이 선 뒤에 옛 장을 걷는다 — 바꾸는 사이에 구름이 깜박이지 않게
      layer.readyEvent.addEventListener(function () {
        if (old) viewer.imageryLayers.remove(old, true);
        if (oldBlob) setTimeout(function () { URL.revokeObjectURL(oldBlob); }, 2000);
      });
      oCloud.setSource(new ol.source.ImageStatic({ url: url, imageExtent: [-180, -90, 180, 90], projection: LL,
                                                   interpolate: true }));
      oCloud.setVisible(true);
    }, "image/png");
  }

  // ── 위성 구름 (koprifossillab 012) ──
  //
  // 서버가 GMGSI 의 가장 새 장을 흰색·투명도로 다 칠해 둔다(3600×1800, 위도 ±72.7° 너머는 비었다). 섞지 않는다 — 관측이라
  // 지금/지난 고르개를 따르지 않고 늘 가장 새 장이다. 10 분마다 새 장이 섰는지 본다
  var cSat = null, oSat = new ol.layer.Image({ zIndex: 61, visible: false }), satUrl = "";
  flat.addLayer(oSat);
  function satShown() { return isOn("satcloud") && visibleNow("satcloud"); }
  function satEntry() {
    var list = (WIND.index && WIND.index.gmgsi && WIND.index.gmgsi.times) || [];
    return list.length ? list[list.length - 1] : null;
  }
  function satText() {
    var e = satEntry();
    return e ? T("{t} UTC · 위성 적외선 (한 시간마다)", { t: windStampText(e.t) }) : T("위성 구름 자료가 아직 없다");
  }
  function dropSat() {
    if (cSat) { viewer.imageryLayers.remove(cSat, true); cSat = null; }
    oSat.setVisible(false);
    satUrl = "";
  }
  function syncSat(reload) {
    if (!satShown()) { dropSat(); return; }
    (WIND.index && !reload ? Promise.resolve(WIND.index) : windIndex()).then(function () {
      var e = satEntry(), opacity = entryOf("satcloud").opacity;
      document.querySelectorAll(".sat-when").forEach(function (p) { p.textContent = satText(); });
      if (!e) { dropSat(); return; }
      var url = BASE + "earth/wind/gmgsi/" + e.t + "/sat.png";
      if (url !== satUrl) {
        satUrl = url;
        var old = cSat;
        cSat = Cesium.ImageryLayer.fromProviderAsync(Cesium.SingleTileImageryProvider.fromUrl(url, {
          rectangle: Cesium.Rectangle.fromDegrees(-180, -90, 180, 90), credit: "NOAA/NESDIS GMGSI" }));
        viewer.imageryLayers.add(cSat);
        cSat.readyEvent.addEventListener(function () { if (old) viewer.imageryLayers.remove(old, true); });
        oSat.setSource(new ol.source.ImageStatic({ url: url, imageExtent: [-180, -90, 180, 90], projection: LL,
                                                 interpolate: true }));
      }
      cSat.alpha = opacity;
      viewer.imageryLayers.raiseToTop(cSat);
      oSat.setOpacity(opacity);
      oSat.setVisible(true);
    }).catch(function () { dropSat(); });
  }
  setInterval(function () { if (satShown()) syncSat(true); }, 10 * 60 * 1000);

  // ── 해류 (koprifossillab 014) ──
  //
  // 서버가 구워 둔 1440×720 텍스처(R=u·G=v·B=바다 가리개, 경도 −180 부터, 위도는 칸 가운데 89.875 부터, `ocean.py`)를 받아
  // 바람과 같은 길로 입자를 흘린다 — 화면 자리 셈(`windToScreen`·`windFromScreen`·`windMpp`·`windKey`)을 함께 쓰고, 판(캔버스)과
  // 입자는 따로다. 바람과 함께 켤 수 있다. 입자는 바다에서만 나고, 육지에 닿으면 다시 난다. 해류는 바람보다 수십 배 느려
  // 기준 빠르기를 0.5 m/s 로 두었다. 구운 것은 달마다 한 장(15 일 무렵의 3 일 평균)이고, 카드에서 달을 고르거나 재생한다 —
  // 재생은 두 달 사이를 섞어 넘긴다(바람의 재생과 같다) (koprifossillab 015)
  var CURRENTS = { index: null, month: saved("gsm.earth.ocean.month", ""), playing: false };
  // 바람과 갈리게 — 색은 바다빛(청록 → 비취 → 엷은 물빛, 흰색·노랑은 바람의 것이라 쓰지 않는다), 선은 굵고 꼬리가 길며
  // 느리게 흐른다. 바람은 가늘고 짧고 빠르다 (koprifossillab 016)
  var OCEAN_REF = 0.5, OCEAN_PX = 0.75, OCEAN_LIFE = 170, OCEAN_FADE = 0.965, OCEAN_PLAY_MS = 2000;
  var OCEAN_COLORS = ["#2a8a8f", "#2c9d97", "#30b0a2", "#3ac3ae", "#4fd5bb", "#6fe4c9", "#97f0da", "#c4f9ec"];
  var oceanCanvas = $("ocean-canvas"), oceanCtx = oceanCanvas.getContext("2d");
  var oceanField = null, oceanNext = null, oceanBlend = 0, oceanLast = 0, oceanCache = {};
  var oceanParticles = [], oceanRaf = 0, oceanViewKey = "", oceanAsked = 0;
  function oceanShown() { return isOn("ocean") && visibleNow("ocean"); }
  function oceanTimes() { return (CURRENTS.index && CURRENTS.index.ecco2 && CURRENTS.index.ecco2.times) || []; }
  /** 고른 달의 장 — 없으면 그 달 앞의 가장 가까운 장, 처음이면 가장 새 장. `offset` 은 그 뒤로 몇 장 */
  function oceanEntry(offset) {
    var list = oceanTimes();
    if (!list.length) return null;
    var i = list.length - 1;
    if (CURRENTS.month) {
      i = 0;
      for (var k = 0; k < list.length; k++) if (list[k].t.slice(0, 6) <= CURRENTS.month) i = k;
    }
    return list[(i + (offset || 0)) % list.length];
  }
  function oceanText() {
    var e = oceanEntry(0);
    return e ? T("{t} · ECCO2 3 일 평균 · 표층 5 m", { t: windStampText(e.t).slice(0, 10) }) : T("해류 자료가 아직 없다");
  }
  function oceanLoad(entry) {
    var url = BASE + "earth/ocean/ecco2/" + entry.t + "/surface.png";
    if (oceanCache[url]) return oceanCache[url];
    var keys = Object.keys(oceanCache);
    if (keys.length > 4) delete oceanCache[keys[0]];
    return (oceanCache[url] = new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () {
        var c = document.createElement("canvas");
        c.width = 1440; c.height = 720;
        var g = c.getContext("2d", { willReadFrequently: true });
        g.drawImage(img, 0, 0);
        var px = g.getImageData(0, 0, 1440, 720).data, n = 1440 * 720;
        var u = new Float32Array(n), v = new Float32Array(n), sea = new Uint8Array(n);
        var u0 = entry.u[0], us = (entry.u[1] - entry.u[0]) / 255, v0 = entry.v[0], vs = (entry.v[1] - entry.v[0]) / 255;
        for (var i = 0; i < n; i++) {
          sea[i] = px[4 * i + 2] > 127 ? 1 : 0;
          u[i] = sea[i] ? u0 + px[4 * i] * us : 0;
          v[i] = sea[i] ? v0 + px[4 * i + 1] * vs : 0;
        }
        resolve({ u: u, v: v, sea: sea, t: entry.t });
      };
      img.onerror = function () { delete oceanCache[url]; reject(new Error(url)); };
      img.src = url;
    }));
  }
  /** 그 자리의 해류 [u, v] (m/s). 가장 가까운 칸이 육지면 null — 입자가 해안에서 다시 난다 */
  function oceanAt(lon, lat) {
    var f = oceanField;
    var x = (lon + 179.875) * 4, y = (89.875 - lat) * 4;
    if (!(y >= 0 && y <= 719)) return null;
    var xn = ((Math.round(x) % 1440) + 1440) % 1440, yn = Math.round(y);
    if (!f.sea[yn * 1440 + xn]) return null;
    var x0 = Math.floor(x), y0 = Math.min(718, Math.floor(y)), fx = x - x0, fy = y - y0;
    x0 = ((x0 % 1440) + 1440) % 1440;
    var x1 = (x0 + 1) % 1440, y1 = y0 + 1;
    var a = y0 * 1440 + x0, b = y0 * 1440 + x1, c = y1 * 1440 + x0, d = y1 * 1440 + x1;
    var w00 = (1 - fx) * (1 - fy), w10 = fx * (1 - fy), w01 = (1 - fx) * fy, w11 = fx * fy;
    var u = f.u[a] * w00 + f.u[b] * w10 + f.u[c] * w01 + f.u[d] * w11, v = f.v[a] * w00 + f.v[b] * w10 + f.v[c] * w01 + f.v[d] * w11;
    var g = oceanNext;
    if (g && oceanBlend > 0) {                                       // 재생 — 다음 달과 섞는다
      u += (g.u[a] * w00 + g.u[b] * w10 + g.u[c] * w01 + g.u[d] * w11 - u) * oceanBlend;
      v += (g.v[a] * w00 + g.v[b] * w10 + g.v[c] * w01 + g.v[d] * w11 - v) * oceanBlend;
    }
    return [u, v];
  }
  /** 재생 — 다음 달을 미리 받아 두고, 섞기가 다 차면 넘긴다. 끝에 닿으면 처음으로 */
  function oceanPrefetch() {
    var next = oceanEntry(1);
    oceanNext = null;
    if (!next || !CURRENTS.playing) return;
    oceanLoad(next).then(function (f) { if (CURRENTS.playing && oceanEntry(1) === next) oceanNext = f; });
  }
  function oceanAdvance() {
    var next = oceanEntry(1);
    if (oceanNext) oceanField = oceanNext;
    oceanBlend = 0;
    CURRENTS.month = next.t.slice(0, 6);
    save("gsm.earth.ocean.month", CURRENTS.month);
    renderOcean();
    oceanPrefetch();
  }
  function oceanSpawn(p) {
    var w = oceanCanvas.clientWidth, h = oceanCanvas.clientHeight;
    for (var tries = 0; tries < 30; tries++) {                      // 바다에서만 난다 — 땅이 많은 화면이면 여러 번 던진다
      var ll = windFromScreen(Math.random() * w, Math.random() * h);
      if (ll && oceanField && oceanAt(ll[0], ll[1])) {
        p.lon = ll[0]; p.lat = ll[1]; p.age = Math.floor(Math.random() * OCEAN_LIFE); p.xy = null; return;
      }
    }
    p.lon = NaN;
    p.xy = null;
  }
  function oceanResize() {
    var w = wrap.clientWidth, h = wrap.clientHeight, r = window.devicePixelRatio || 1;
    if (oceanCanvas.width !== Math.round(w * r) || oceanCanvas.height !== Math.round(h * r)) {
      oceanCanvas.width = Math.round(w * r); oceanCanvas.height = Math.round(h * r);
      oceanCtx.setTransform(r, 0, 0, r, 0, 0);
    }
    var want = Math.max(600, Math.min(6000, Math.round(w * h / 220)));
    while (oceanParticles.length < want) { var p = {}; oceanSpawn(p); oceanParticles.push(p); }
    oceanParticles.length = want;
  }
  function oceanFrame(now) {
    oceanRaf = requestAnimationFrame(oceanFrame);
    if (document.hidden || !oceanShown() || !oceanField) { oceanLast = now; return; }
    if (CURRENTS.playing && oceanNext) {
      oceanBlend += (now - (oceanLast || now)) / OCEAN_PLAY_MS;
      if (oceanBlend >= 1) oceanAdvance();
    }
    oceanLast = now;
    if (mode === "globe") windOccluder = new Cesium.EllipsoidalOccluder(ELL, viewer.camera.positionWC);
    var w = oceanCanvas.clientWidth, h = oceanCanvas.clientHeight, key = windKey();
    if (key !== oceanViewKey) {
      oceanViewKey = key;
      oceanCtx.clearRect(0, 0, w, h);
      oceanParticles.forEach(function (p) { p.xy = null; });
    } else {
      oceanCtx.globalCompositeOperation = "destination-in";
      oceanCtx.fillStyle = "rgba(0,0,0," + OCEAN_FADE + ")";
      oceanCtx.fillRect(0, 0, w, h);
      oceanCtx.globalCompositeOperation = "source-over";
    }
    var k = windMpp() * OCEAN_PX / OCEAN_REF;
    var buckets = OCEAN_COLORS.map(function () { return []; });
    oceanParticles.forEach(function (p) {
      if (!(p.age < OCEAN_LIFE) || !isFinite(p.lon)) { oceanSpawn(p); return; }
      p.age++;
      var uv = oceanAt(p.lon, p.lat);
      if (!uv) { oceanSpawn(p); return; }
      var cos = Math.max(0.05, Math.cos(p.lat * Math.PI / 180));
      var lat = p.lat + uv[1] * k / M_PER_LAT, lon = p.lon + uv[0] * k / (M_PER_LAT * cos);
      if (Math.abs(lat) > 89.5) { oceanSpawn(p); return; }
      var xy = windToScreen(lon, lat);
      if (!xy || xy[0] < -20 || xy[1] < -20 || xy[0] > w + 20 || xy[1] > h + 20) { oceanSpawn(p); return; }
      if (p.xy && Math.abs(xy[0] - p.xy[0]) + Math.abs(xy[1] - p.xy[1]) < 60) {
        var s = Math.sqrt(uv[0] * uv[0] + uv[1] * uv[1]) / OCEAN_REF;
        buckets[Math.min(OCEAN_COLORS.length - 1, Math.floor(s * 3))].push(p.xy[0], p.xy[1], xy[0], xy[1]);
      }
      p.lon = lon; p.lat = lat; p.xy = xy;
    });
    oceanCtx.lineWidth = 1.8;
    buckets.forEach(function (segs, i) {
      if (!segs.length) return;
      oceanCtx.strokeStyle = OCEAN_COLORS[i];
      oceanCtx.beginPath();
      for (var j = 0; j < segs.length; j += 4) { oceanCtx.moveTo(segs[j], segs[j + 1]); oceanCtx.lineTo(segs[j + 2], segs[j + 3]); }
      oceanCtx.stroke();
    });
  }
  function syncOcean() {
    var e = entryOf("ocean"), on = oceanShown();
    oceanCanvas.hidden = !on;
    if (e) oceanCanvas.style.opacity = e.opacity;
    if (!on) {
      if (oceanRaf) { cancelAnimationFrame(oceanRaf); oceanRaf = 0; }
      return;
    }
    var mine = ++oceanAsked;
    (CURRENTS.index ? Promise.resolve(CURRENTS.index) : fetch(BASE + "earth/ocean/").then(function (r) { return r.json(); })
      .then(function (d) { CURRENTS.index = d; return d; })).then(function () {
      renderOcean();
      var entry = oceanEntry(0);
      if (!entry) return null;
      if (oceanField && oceanField.t === entry.t) return oceanField;
      return oceanLoad(entry);
    }).then(function (f) {
      if (mine !== oceanAsked || !f) return;
      if (f !== oceanField) {                                        // 달이 바뀌었을 때만 — 켠 레이어를 다시 쌓을 때마다 불린다
        oceanField = f;
        oceanBlend = 0;
        oceanPrefetch();
      }
      oceanResize();
      oceanViewKey = "";
      if (!oceanRaf) oceanRaf = requestAnimationFrame(oceanFrame);
    }).catch(function () { /* 다음에 켤 때 다시 */ });
  }
  window.addEventListener("resize", function () { if (oceanShown() && oceanField) { oceanResize(); oceanViewKey = ""; } });
  /** 해류 카드 — 달 고르개·재생·지금 보이는 날 */
  function renderOcean() {
    var list = oceanTimes(), entry = oceanEntry(0);
    document.querySelectorAll(".ocean-controls").forEach(function (box) {
      var month = box.querySelector(".ocean-month"), play = box.querySelector(".ocean-play");
      if (list.length) {
        month.min = windStampText(list[0].t).slice(0, 7);
        month.max = windStampText(list[list.length - 1].t).slice(0, 7);
      }
      if (entry) month.value = windStampText(entry.t).slice(0, 7);
      play.disabled = list.length < 2;
      play.textContent = CURRENTS.playing ? "⏸" : "▶";
      play.title = CURRENTS.playing ? T("멈춤") : T("재생");
      box.querySelector(".ocean-when").textContent = oceanText();
    });
  }
  function oceanControls() {
    var box = document.createElement("div");
    box.className = "wind-controls ocean-controls";
    box.innerHTML = '<div class="wind-row"><input type="month" class="ocean-month" aria-label="' + esc(T("해류의 달")) + '">' +
      '<button type="button" class="ocean-play">▶</button></div><p class="wind-when ocean-when"></p>';
    box.querySelector(".ocean-month").addEventListener("change", function (ev) {
      if (!ev.target.value) return;
      CURRENTS.month = ev.target.value.replace("-", "");
      CURRENTS.playing = false;
      save("gsm.earth.ocean.month", CURRENTS.month);
      syncOcean();
    });
    box.querySelector(".ocean-play").addEventListener("click", function () {
      CURRENTS.playing = !CURRENTS.playing;
      oceanBlend = 0; oceanLast = 0;
      oceanPrefetch();
      renderOcean();
    });
    return box;
  }

  /** 켜고 끄고, 출처·높이·종류·날이 바뀌면 다시 받는다. `reload` 면 목록부터 다시 */
  function syncWind(reload) {
    var e = entryOf("wind"), won = windShown(), con = cloudShown();
    windCanvas.hidden = !won;
    if (e) windCanvas.style.opacity = e.opacity;
    if (!con) { hideCloud(); cloudA = cloudB = null; }
    if (!won && !con) {
      if (windRaf) { cancelAnimationFrame(windRaf); windRaf = 0; }
      WIND.playing = false;
      return;
    }
    var mine = ++windAsked;
    (WIND.index && !reload ? Promise.resolve(WIND.index) : windIndex()).then(function () {
      // 지금은 앞뒤 두 장을 섞는다 — 재생과 같은 섞기다
      var pair = WIND.src === "gfs" ? windNowPair() : null;
      var entry = pair ? pair.a : windEntry(0), later = pair && pair.b;
      windPair = pair;
      renderWind();
      if (!entry) { windField = null; cloudA = null; applyCloud(true); return null; }
      return Promise.all([won ? windLoad(entry) : null, won && later ? windLoad(later) : null,
                          con ? cloudLoad(entry) : null, con && later ? cloudLoad(later) : null]).then(function (fs) {
        if (mine !== windAsked) return;
        windField = fs[0]; windNext = fs[1]; cloudA = fs[2]; cloudB = fs[3];
        windBlend = later ? pair.w : 0;
        nextReady = false; cloudNext = null;
        if (WIND.playing) windPrefetch();
        applyCloud(true);
        renderWind();
        if (won) { windResize(); windViewKey = ""; }
        if (!windRaf) windRaf = requestAnimationFrame(windFrame);
      });
    }).catch(function () { if (mine === windAsked) { windField = null; cloudA = null; applyCloud(true); renderWind(); } });
  }
  /** 재생 — 다음 날의 바람·구름을 미리 받아 두고(`nextReady`), 섞기가 다 차면 넘긴다. 끝에 닿으면 처음으로 */
  var nextEntry = null, nextReady = false;
  function windPrefetch() {
    var list = windTimes(), cur = windEntry(0);
    if (!cur || list.length < 2) { WIND.playing = false; return; }
    var i = list.indexOf(cur), next = list[(i + 1) % list.length];
    nextEntry = next; nextReady = false;
    Promise.all([windShown() ? windLoad(next) : null, cloudShown() ? cloudLoad(next) : null]).then(function (fs) {
      if (!WIND.playing || nextEntry !== next) return;
      windNext = fs[0]; cloudNext = fs[1]; nextReady = true;
    });
  }
  function windAdvance() {
    if (windNext) windField = windNext;
    cloudA = cloudNext;
    windNext = null; cloudNext = null; nextReady = false; windBlend = 0;
    WIND.day = nextEntry.t;
    save("gsm.earth.wind.day", WIND.day);
    applyCloud(true);
    renderWind();
    windPrefetch();
  }
  window.addEventListener("resize", function () { if (windShown()) { windResize(); windViewKey = ""; } });
  // 지금의 것은 여섯 시간마다 새 판이 선다 — 반 시간마다 목록을 다시 본다
  setInterval(function () { if (fluxShown() && WIND.src === "gfs") syncWind(true); }, 30 * 60 * 1000);
  // 지금의 것은 일 분마다 가중치를 다시 센다. 지금이 뒤 장을 지나면 두 장을 다시 고른다
  setInterval(function () {
    if (!fluxShown() || WIND.src !== "gfs" || !windPair || !windPair.b) return;
    var p = windNowPair();
    if (!p || !p.b || p.a.t !== windPair.a.t || p.b.t !== windPair.b.t) { syncWind(); return; }
    windPair = p; windBlend = p.w;
    applyCloud();
    renderWind();
  }, 60 * 1000);

  /** 바람·구름 카드의 고르개 — 지금/지난, 높이(바람)·종류(구름), (지난이면) 날짜·재생, 그리고 지금 보이는 시각과 출처.
   *  시각에 닿는 고르개는 두 카드가 함께 따른다 (koprifossillab 011) */
  var windBoxes = [];
  function renderWind() {
    windBoxes.forEach(renderFluxBox);
  }
  function renderFluxBox(windBox) {
    var entry = windEntry(0), list = windTimes(), isCloud = windBox.dataset.layer === "cloud";
    windBox.querySelector(".wind-src").value = WIND.src;
    if (isCloud) windBox.querySelector(".cloud-kind").value = CLOUD.kind;
    else windBox.querySelector(".wind-level").value = WIND.level;
    var past = windBox.querySelector(".wind-past"), day = windBox.querySelector(".wind-day");
    past.hidden = WIND.src !== "era5";
    if (list.length && WIND.src === "era5") {
      day.min = windStampText(list[0].t).slice(0, 10);
      day.max = windStampText(list[list.length - 1].t).slice(0, 10);
      if (entry) day.value = windStampText(entry.t).slice(0, 10);
    }
    var play = windBox.querySelector(".wind-play");
    play.textContent = WIND.playing ? "⏸" : "▶";
    play.title = WIND.playing ? T("멈춤") : T("재생");
    var when = windBox.querySelector(".wind-when");
    when.textContent = !entry ? T("바람 자료가 아직 없다")
      : isCloud && (!entry.clouds || entry.clouds.indexOf(CLOUD.kind) < 0) ? T("이 시각에는 구름 자료가 없다")
      : WIND.src === "gfs" ? windNowText()
      : T("{t} UTC · ERA5 재분석", { t: windStampText(entry.t) });
    var src = windBox.parentNode && windBox.parentNode.querySelector(".active-src");
    if (src && WIND.index && WIND.index[WIND.src]) src.textContent = WIND.index[WIND.src].credit;
  }
  function windControls(layer) {
    var box = document.createElement("div"), cloud = layer === "cloud";
    box.className = "wind-controls";
    box.dataset.layer = layer;
    box.innerHTML =
      '<div class="wind-row"><select class="wind-src" aria-label="' + esc(T(cloud ? "구름" : "바람")) + '">' +
      '<option value="gfs">' + esc(T(cloud ? "지금의 구름" : "지금의 바람")) + '</option><option value="era5">' +
      esc(T(cloud ? "지난 구름" : "지난 바람")) + "</option></select>" +
      (cloud
        ? '<select class="cloud-kind" aria-label="' + esc(T("구름 종류")) + '">' +
          '<option value="total">' + esc(T("전체 구름")) + '</option><option value="low">' + esc(T("하층 구름")) + "</option>" +
          '<option value="mid">' + esc(T("중층 구름")) + '</option><option value="high">' + esc(T("상층 구름")) + "</option></select>"
        : '<select class="wind-level" aria-label="' + esc(T("높이")) + '">' +
          '<option value="10m">' + esc(T("지상 10 m")) + '</option><option value="250hPa">' + esc(T("250 hPa (제트기류)")) +
          "</option></select>") + "</div>" +
      '<div class="wind-row wind-past" hidden><input type="date" class="wind-day" aria-label="' + esc(T("날짜")) + '">' +
      '<button type="button" class="wind-play">▶</button></div>' +
      '<p class="wind-when"></p>';
    box.querySelector(".wind-src").addEventListener("change", function (ev) {
      WIND.src = ev.target.value; WIND.playing = false;
      save("gsm.earth.wind.src", WIND.src);
      syncWind();
    });
    if (cloud) {
      box.querySelector(".cloud-kind").addEventListener("change", function (ev) {
        CLOUD.kind = ev.target.value;
        save("gsm.earth.cloud.kind", CLOUD.kind);
        syncWind();
      });
    } else {
      box.querySelector(".wind-level").addEventListener("change", function (ev) {
        WIND.level = ev.target.value;
        save("gsm.earth.wind.level", WIND.level);
        syncWind();
        syncLegend();
      });
    }
    box.querySelector(".wind-day").addEventListener("change", function (ev) {
      if (!ev.target.value) return;
      WIND.day = ev.target.value.replace(/-/g, "");
      WIND.playing = false;
      save("gsm.earth.wind.day", WIND.day);
      syncWind();
    });
    box.querySelector(".wind-play").addEventListener("click", function () {
      WIND.playing = !WIND.playing;
      windNext = null; cloudNext = null; nextReady = false; windBlend = 0; windLast = 0;
      if (WIND.playing) windPrefetch();
      applyCloud(true);
      renderWind();
    });
    windBoxes.push(box);
    return box;
  }

  // ── 지질 레이어 — 2D 처럼 목록에서 켜고, 켠 것은 카드로 쌓는다 ──
  //
  // 쌓는 차례는 구와 평면이 같다. 구는 배경(0 번) 위로 아래 것부터 `raiseToTop`, 평면은 `zIndex`
  function applyStack() {
    Object.keys(cGeo).forEach(function (name) {
      var e = entryOf(name);
      var shown = !!e && visibleNow(name);
      cGeo[name].show = shown;
      oGeo[name].setVisible(shown);
      if (e) { cGeo[name].alpha = globeAlpha(e); oGeo[name].setOpacity(e.opacity); }
    });
    // 구 — 영상 레이어만 차례가 있다(벡터 데이터 소스는 늘 영상 위다). 평면 — zIndex
    active.slice().reverse().forEach(function (e, i) {
      (cRaise[e.name] || []).forEach(function (l) { viewer.imageryLayers.raiseToTop(l); });
      // 평면도 구처럼 벡터(착륙 지점·동선)는 영상 레이어 위에 둔다 — 사진을 나중에 켜도 점을 덮지 않게
      if (oGeo[e.name]) oGeo[e.name].setZIndex((LAYER[e.name].kind === "vector" ? 50 : 0) + i + 1);
    });
    // 점묶음은 늘 지질 위다
    oPoints.setZIndex(100);
    syncLabels();
    syncTrack();
    syncMantle();
    syncWind();
    syncSat();
    syncOcean();
    syncLegend();
  }
  function addLayer(name) {
    if (isOn(name)) return;
    // 구름은 조금 비치게 — 흰 구름 위에서는 바람 입자가 묻힌다 (koprifossillab 011)
    active.unshift({ name: name, opacity: name === "geology" ? 0.6 : name === "crust" ? 0.7 : name === "cloud" || name === "satcloud" ? 0.75 : 1 });
    saveLayers(); applyStack(); renderActive(); renderCatalog();
    showAge();   // 캡션은 켠 레이어를 따른다(맨틀·빙상·옛 해안선) — 연대를 바꿀 때만 다시 쓰면 켜도 안 뜬다
  }
  function removeLayer(name) {
    active = active.filter(function (e) { return e.name !== name; });
    saveLayers(); applyStack(); renderActive(); renderCatalog();
    showAge();   // 캡션은 켠 레이어를 따른다(맨틀·빙상·옛 해안선) — 연대를 바꿀 때만 다시 쓰면 켜도 안 뜬다
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
    windBoxes = [];                                  // 바람·구름 카드는 다시 짓는다
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
        if (cGeo[e.name]) { cGeo[e.name].alpha = globeAlpha(e); oGeo[e.name].setOpacity(e.opacity); }
        else { syncLabels(); syncTrack(); syncMantle(true); if (e.name === "wind") windCanvas.style.opacity = e.opacity;
               if (e.name === "cloud") applyCloud();
               if (e.name === "satcloud") syncSat();
               if (e.name === "ocean") oceanCanvas.style.opacity = e.opacity; }
        num.textContent = range.value + "%";
      });
      range.addEventListener("change", saveLayers);
      foot.append(range, num);
      var src = document.createElement("p");
      src.className = "active-src";
      src.textContent = LAYER[e.name].src || "";
      if (e.name === "wind" || e.name === "cloud") li.append(head, windControls(e.name), foot, src);
      else if (e.name === "satcloud") {
        // 위성 구름 — 고를 것이 없다. 가장 새 장의 시각과, 비는 곳·속기 쉬운 곳을 적는다
        var when = document.createElement("p"), note = document.createElement("p");
        when.className = "wind-when sat-when";
        when.textContent = satText();
        note.className = "wind-when";
        note.textContent = T("위도 72° 너머는 비어 있다. 추운 땅이 구름처럼 보일 수 있다.");
        li.append(head, when, note, foot, src);
      } else if (e.name === "araon") {
        // 아라온호 — 항적 기간 (koprifossillab 017)
        li.append(head, trackPicker(), foot, src);
      } else if (e.name === "ocean") {
        // 해류 — 달을 고르거나 재생한다 (koprifossillab 015)
        li.append(head, oceanControls(), foot, src);
      } else li.append(head, foot, src);
      host.appendChild(li);
    });
    renderWind();
    renderOcean();
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
    row.append(box, label);
    return row;
  }

  // 지형 (구에서만)
  var terrainBox = $("moon-terrain"), exag = $("moon-exag");
  terrainBox.checked = look.terrain;
  exag.disabled = !look.terrain;
  terrainBox.addEventListener("change", function () {
    look.terrain = terrainBox.checked;
    scene.terrainProvider = look.terrain && !paleoOn() ? demTerrain : flatTerrain;
    exag.disabled = !look.terrain;
    save("gsm.earth.terrain", look.terrain ? "on" : "off");
  });
  exag.value = look.exag;
  function applyExag() {
    look.exag = +exag.value;
    scene.verticalExaggeration = look.exag / 10;
    $("moon-exag-num").textContent = "×" + (look.exag / 10).toFixed(1);
    save("gsm.earth.exag", look.exag);
  }
  exag.addEventListener("input", applyExag);
  applyExag();

  // ══ 좌표 ══════════════════════════════════════════════════════════
  function fmt(ll) {
    return T("위도 {lat}° · 경도 {lon}°", { lat: ll[1].toFixed(4), lon: ll[0].toFixed(4) });
  }
  function globeLL(position) {
    var ray = viewer.camera.getPickRay(position);
    var cartesian = ray && scene.globe.pick(ray, scene);
    if (!cartesian) cartesian = viewer.camera.pickEllipsoid(position, ELL);
    if (!cartesian) return null;
    var c = ELL.cartesianToCartographic(cartesian);
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
  // 첫 줄은 누른 자리의 위경도 — 2D 처럼 누르면 "위도, 경도" 로 복사한다(아래 `popupBody` 의 click, 041)
  function coordHead(ll) {
    var lat = ll[1].toFixed(6), lon = ll[0].toFixed(6);
    return '<button type="button" class="popup-coord" title="' + esc(T("눌러서 복사한다")) + '" data-copy="' +
           lat + ", " + lon + '"><span class="k">' + esc(T("위도")) + '</span><span class="v">' + lat +
           '</span><span class="k">' + esc(T("경도")) + '</span><span class="v">' + lon +
           '</span><span class="copy">' + esc(T("복사")) + "</span></button>";
  }
  // 그때의 자리 (wetherilli 087) — 누른 자리를 아무 연대로나 옮겨 본다. 서버가 PALEOMAP 2016 판 회전으로 셈한다
  // (`paleo.py`). 점묶음의 점에 연대(Ma) 열이 있으면 그 값을 미리 넣는다
  function paleoForm(ll, age) {
    return '<form class="paleo-form" data-lon="' + ll[0].toFixed(5) + '" data-lat="' + ll[1].toFixed(5) + '">' +
           '<label title="' + esc(T("PALEOMAP 2016 판 회전으로 셈한 것이다 — 관측이 아니다")) + '">' + esc(T("그때의 자리")) +
           ' <input type="number" name="age" min="0" max="1100" step="any" placeholder="250" value="' +
           (age == null ? "" : esc(age)) + '"> Ma</label><button type="submit">' + esc(T("옮긴다")) + "</button>" +
           '<output class="paleo-out"></output></form>';
  }
  popupBody.addEventListener("submit", function (e) {
    var form = e.target.closest(".paleo-form");
    if (!form) return;
    e.preventDefault();
    var out = form.querySelector(".paleo-out"), age = form.elements.age.value;
    if (age === "") return;
    out.textContent = T("읽는 중");
    fetch(BASE + "earth/paleo/?lon=" + form.dataset.lon + "&lat=" + form.dataset.lat + "&age=" + encodeURIComponent(age))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        out.textContent = d.error || d.text;
        if (d.lon != null) out.insertAdjacentHTML("beforeend", " " + ettLink([+form.dataset.lon, +form.dataset.lat], d.age));
      })
      .catch(function () { out.textContent = T("속성을 받지 못했다"); });
  });
  // 켠 레이어 가운데 읽을 수 있는 것을 위에서부터 다 묻는다 — 달·화성에서 온 틀이다. 지구는 지질도 하나다.
  // Macrostrat 는 줌마다 그리는 판(축척)이 달라, 보는 줌을 함께 보낸다 — 타일과 같은 판을 읽는다
  function hereZoom() {
    var res = mode === "flat" ? groundRes() : heightToRes(hereHeight());
    return Math.max(0, Math.min(GEO_MAX, Math.round(Math.log(40075016.7 / 256 / Math.max(0.5, res)) / Math.LN2)));
  }
  // ══ EarthThruTime3D 로 건너가기 (wetherilli 088) ════════════════
  //
  // 옛 위치를 ETT 의 고지리 지구본에서 본다. 주소는 ETT 의 것 그대로다(`docs/site-map.md`) — 핀은 **오늘의 좌표**를
  // 넘기고 옮기기는 ETT 가 한다. 둘 다 PALEOMAP 2016 이라 우리가 적은 자리에 핀이 선다(087). 고도 격자(PaleoDEM)는
  // 540 Ma 까지라 그보다 오랜 연대는 기본 판(PaleoAtlas 육지 마스크, 750 Ma 까지 — 그 너머는 판 재구성만)으로 연다.
  // ETT 는 연대를 가장 가까운 시점에 맞춘다. 링크일 뿐이라 자료는 넘어가지 않는다
  var ETT_URL = "https://earththrutime.nopeoplestime.info/";
  var ETT_DEM_MAX = 540;
  function ettHref(ll, age) {
    var w = wrapLon(ll), q = [];
    if (age <= ETT_DEM_MAX) q.push("masks=paleodem2018");
    q.push("age=" + (+age).toFixed(age < 10 ? 3 : 1).replace(/\.?0+$/, ""));
    q.push("pin=" + w[0].toFixed(2) + "," + w[1].toFixed(2));
    return ETT_URL + "?" + q.join("&");
  }
  function ettLink(ll, age) {
    return '<a class="ett-link" target="_blank" rel="noopener" href="' + esc(ettHref(ll, age)) + '" title="' +
           esc(T("EarthThruTime3D 의 고지리 지구본에서 이 자리를 그 연대로 본다 — 새 창")) + '">' +
           esc(T("ETT 에서 {age} Ma", { age: age })) + "</a>";
  }
  function unitTable(u, ll) {
    var chip = u.color ? '<span class="swatch-img" style="display:inline-block;background:' + esc(u.color) + '"></span>' : "";
    var rows = u.rows.map(function (row, k) {
      return "<tr><th>" + esc(row[0]) + "</th><td>" + (k === 0 ? chip : "") + esc(row[1]) + "</td></tr>";
    });
    if (u.then && u.then.length) {
      rows.push('<tr><th>EarthThruTime3D</th><td>' + u.then.map(function (age) { return ettLink(ll, age); }).join(" · ") +
                "</td></tr>");
    }
    return "<table>" + rows.join("") + "</table>";
  }
  function askUnit(ll, pixel) {
    markAt(ll);
    var head = coordHead(ll) + paleoForm(ll);
    var layers = active.filter(function (e) { return LAYER[e.name].info; }).map(function (e) { return LAYER[e.name]; });
    if (!layers.length) { showPopup(head, pixel); return; }
    var mine = ++asked;
    showPopup(head + '<p class="none">' + esc(T("읽는 중")) + "</p>", pixel);
    var at = "?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) + "&z=" + hereZoom();
    var ASK = { geology: "earth/info/", crust: "earth/crust/at/", tectonics: "earth/tectonics/at/", seafloor: "earth/seafloor/at/", glim: "earth/glim/at/", faults: "earth/faults/at/", impacts: "earth/impacts/at/" };
    Promise.all(layers.map(function (l) {
      return fetch(BASE + ASK[l.info] + at + (l.info === "seafloor" || l.info === "impacts" ? "&layer=" + l.name : "")).then(function (r) { return r.json(); }).catch(function () { return { error: true }; });
    })).then(function (all) {
      if (mine !== asked) return;
      var html = head;
      all.forEach(function (data, i) {
        html += "<h3>" + esc(T(layers[i].title)) + "</h3>";
        if (data.error) { html += '<p class="none">' + esc(T("속성을 받지 못했다")) + "</p>"; return; }
        if (layers[i].info === "impacts") {
          html += data.name ? "<p><b>" + esc(data.name) + "</b></p><table>" + data.rows.map(function (row) {
            return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>";
          }).join("") + "</table>" : '<p class="none">' + esc(data.text) + "</p>";
          return;
        }
        if (layers[i].info === "faults") {
          html += data.fault ? '<p><span class="chip" style="background:' + esc(data.fault.color) + '"></span> <b>' + esc(data.fault.name) +
            "</b></p><table>" + data.fault.rows.map(function (row) {
              return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>";
            }).join("") + "</table>" : '<p class="none">' + esc(data.text) + "</p>";
          return;
        }
        if (layers[i].info === "tectonics") {
          html += data.province ? "<p><b>" + esc(data.province.name) + "</b></p><table>" + data.province.rows.map(function (row) {
            return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>";
          }).join("") + "</table>" : '<p class="none">' + esc(data.text) + "</p>";
          return;
        }
        if (layers[i].info === "crust" || layers[i].info === "seafloor" || layers[i].info === "glim") { html += '<p class="none">' + esc(data.text) + "</p>"; return; }
        if (!data.units || !data.units.length) {
          html += '<p class="none">' + esc(T("여기에는 지질 단위가 없다")) + "</p>";
          return;
        }
        // 한 자리에 단위가 여럿일 수 있다(판이 겹친 곳) — 다 싣는다
        html += data.units.map(function (u) { return unitTable(u, ll); }).join("");
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
    // 그때의 지구에서 옮겨 그린 점 — 팝업의 위경도·옛 위치는 오늘의 좌표로 (091)
    if (Array.isArray(props._today)) ll = props._today;
    // 연대(Ma) 열 — "연대 (Ma)"·"age_ma" 따위. 숫자면 옛 위치 칸에 미리 넣는다
    var ageKey = rows.filter(function (k) { return /Ma\)?$|_ma$|^age$/i.test(k) && isFinite(parseFloat(props[k])); })[0];
    showPopup((ll ? coordHead(ll) + paleoForm(ll, ageKey ? parseFloat(props[ageKey]) : null) : "") +
              (props._paleo ? '<p class="none">' + esc(props._paleo) + "</p>" : "") +
              "<h3>" + esc(title) + '</h3><p class="from"><span class="swatch" style="background:' +
              esc(ps.color) + '"></span>' + esc(ps.name) + "</p>" +
              (rows.length ? "<table>" + rows.map(function (k) {
                return "<tr><th>" + esc(T(k)) + "</th><td>" + esc(props[k]) + "</td></tr>";
              }).join("") + "</table>" : ""), pixel);
  }
  handler.setInputAction(function (click) {
    if (tool) { drawClick(globeLL(click.position)); return; }     // 도구가 켜져 있으면 도구가 받는다 (041)
    var picked = scene.pick(click.position);
    var entity = picked && picked.id;
    var px = [click.position.x, click.position.y];
    if (entity && entity.gsmProps) {
      var pos = entity.position && entity.position.getValue(Cesium.JulianDate.now());
      var ll = null;
      if (pos) { var c = ELL.cartesianToCartographic(pos); ll = [Cesium.Math.toDegrees(c.longitude), Cesium.Math.toDegrees(c.latitude)]; }
      showFeature(entity.gsmProps, entity.gsmSet, ll, px);
      return;
    }
    var at = globeLL(click.position);
    if (at) askAt(at, px);
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
    askAt(wrapLon(toLL(e.coordinate)), e.pixel);
  });

  // ══ 범례 — 오른쪽 아래, 펼쳐 둔다 ═══════════════════════════════
  //
  // 켠 레이어마다 칸 하나. Macrostrat 의 색은 단위의 시대(ICS)의 색이라 기(period)의 색으로 읽힌다 — 세·절까지
  // 가른 단위는 색이 조금 다르다. 젊은 것이 위다
  var legends = {};                // 갈래 → 그린 HTML (한 번 받는다)
  var dock = $("legend-dock");
  // 휴대폰에서는 범례가 구를 덮어 접은 채로 연다 (wetherilli 128)
  dock.open = saved("gsm.earth.legend", window.matchMedia("(max-width: 760px)").matches ? "closed" : "open") !== "closed";
  dock.addEventListener("toggle", function () { save("gsm.earth.legend", dock.open ? "open" : "closed"); });
  function ma(v) { return v == null ? "" : (+v).toLocaleString(undefined, { maximumFractionDigits: 2 }); }
  /** 입자 색 여덟 칸과 그 빠르기 — 칸 i 는 빠르기/기준의 세 배가 i 인 것이다(`windFrame`·`oceanFrame` 의 셈과 같다) (koprifossillab 018) */
  function flowLegend(colors, ref, note) {
    var digits = ref < 2 ? 2 : 0;
    function v(x) { return (+x).toLocaleString(undefined, { maximumFractionDigits: digits }); }
    return '<li class="empty">' + esc(note) + "</li>" + colors.map(function (color, i) {
      var a = ref * i / 3, b = ref * (i + 1) / 3;
      var text = i === colors.length - 1 ? T("{a} m/s 넘게", { a: v(a) }) : T("{a}–{b} m/s", { a: v(a), b: v(b) });
      return '<li><span class="chip" style="background:' + esc(color) + '"></span>' + esc(text) + "</li>";
    }).join("");
  }
  function legendHtml(kind) {
    // 바람·해류는 받지 않고 그때그때 — 바람의 기준 빠르기는 높이마다 다르다
    if (kind === "wind") {
      return Promise.resolve(flowLegend(WIND_COLORS, WIND_REF[WIND.level],
        T("입자 색은 바람의 빠르기 — {level}", { level: T(WIND.level === "10m" ? "지상 10 m" : "250 hPa (제트기류)") })));
    }
    if (kind === "ocean") return Promise.resolve(flowLegend(OCEAN_COLORS, OCEAN_REF, T("입자 색은 해류의 빠르기 — 표층 5 m")));
    if (legends[kind] !== undefined) return Promise.resolve(legends[kind]);
    if (kind === "neotoma") {
      legends[kind] = '<li class="empty">' + esc(T("점의 색은 자료형 — 옛 연대에는 그 연대를 품은 산지만")) + "</li>" +
        THEN.neotoma.map(function (row) {
          return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) + "</li>";
        }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "quake") {
      legends[kind] = '<li class="empty">' + esc(T("원의 크기는 규모, 색은 진원 깊이")) + "</li>" +
        THEN.quakes.map(function (row) {
          return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) + "</li>";
        }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "volcano") {
      legends[kind] = '<li class="empty">' + esc(T("세모의 색은 마지막 분화")) + "</li>" +
        THEN.volcanoes.map(function (row) {
          return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) + "</li>";
        }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "pleistocene") {
      legends[kind] = THEN.pleistocene.map(function (row) {
        return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) + "</li>";
      }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "glim" || kind === "heatflow") {
      legends[kind] = (kind === "glim" ? '<li class="empty">' + esc(T("0.5° 칸에서 가장 넓은 암상이다")) + "</li>" : "") +
        (THEN[kind] || []).map(function (row) {
          return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) + "</li>";
        }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "seaage" || kind === "sediment") {
      legends[kind] = (SEA[kind === "seaage" ? "age" : "sediment"] || []).map(function (row) {
        return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) + "</li>";
      }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "stress") {
      legends[kind] = '<li class="empty">' + esc(T("막대는 최대 수평 응력 방향, 길이는 품질(A–D)")) + "</li>" +
        (THEN.stress || []).map(function (row) {
          return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) + "</li>";
        }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "tbound" || kind === "tprov") {
      legends[kind] = (TECT[kind === "tbound" ? "boundaries" : "provinces"] || []).map(function (row) {
        return '<li><span class="chip" style="background:' + esc(row.color) + (row.dash ? ";opacity:.6" : "") + '"></span>' + esc(row.name) + "</li>";
      }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "mineral") {
      legends[kind] = '<li class="empty">' + esc(T("마름모는 세계 광상 표와 대규모 광산, 큰 원은 생산한 곳, 작은 원은 산지·탐사지(줌 4 부터)")) + "</li>" +
        (THEN.minerals || []).map(function (row) {
          return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) + "</li>";
        }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "gemfaults") {
      legends[kind] = (THEN.faults || []).map(function (row) {
        return '<li><span class="chip" style="background:' + esc(row.color) + (row.dash ? ";opacity:.6" : "") + '"></span>' + esc(row.name) + "</li>";
      }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "impacts" || kind === "lips") {
      legends[kind] = (kind === "lips" ? '<li class="empty">' + esc(T("색은 생긴 때. 대륙 위의 것은 판 회전으로 그때의 자리에 — 계산이지 관측이 아니다")) + "</li>" : "") +
        (IMP[kind] || []).map(function (row) {
          return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) + "</li>";
        }).join("");
      return Promise.resolve(legends[kind]);
    }
    if (kind === "crust") {
      legends[kind] = '<li class="empty">' + esc(T("2° 칸의 모형이다 — 관측이 아니다")) + "</li>" +
        (THEN.crust || []).map(function (row) {
          return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) + "</li>";
        }).join("");
      return Promise.resolve(legends[kind]);
    }
    return fetch(BASE + "earth/legend/").then(function (r) { return r.json(); }).then(function (data) {
      var html = '<li class="empty">' + esc(T("색은 시대의 색이다 — 세·절까지 가른 단위는 조금 다르다")) + "</li>";
      html += (data.rows || []).map(function (row) {
        return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) +
               ' <span class="hint">' + esc(ma(row.b_age)) + "–" + esc(ma(row.t_age)) + " Ma</span></li>";
      }).join("");
      legends[kind] = html;
      return html;
    }).catch(function () { return '<li class="empty">' + esc(T("범례를 받지 못했다")) + "</li>"; });
  }
  var legendAsked = 0;
  function syncLegend() {
    // 같은 범례(기의 색)를 쓰는 레이어가 여럿이면 한 번만 — 지질 단위와 화석 산지 (098)
    var kinds = {};
    var layers = active.filter(function (e) { return LAYER[e.name].legend && visibleNow(e.name); })
                       .map(function (e) { return LAYER[e.name]; })
                       .filter(function (l) { return !kinds[l.legend] && (kinds[l.legend] = true); });
    // 바람·해류의 빠르기는 짧고 입자는 늘 위에 그려진다 — 범례도 맨 위에 (koprifossillab 018)
    var FLOW = { wind: 0, ocean: 1 };
    layers.sort(function (a, b) { return (a.legend in FLOW ? FLOW[a.legend] : 9) - (b.legend in FLOW ? FLOW[b.legend] : 9); });
    dock.hidden = !layers.length;
    if (!layers.length) return;
    var mine = ++legendAsked;
    Promise.all(layers.map(function (l) { return legendHtml(l.legend); })).then(function (parts) {
      if (mine !== legendAsked) return;
      $("legend-list").innerHTML = parts.map(function (html, i) {
        var head = parts.length > 1 ? '<li class="layer">' + esc(T(layers[i].legendTitle || layers[i].title)) + "</li>" : "";
        return head + html;
      }).join("");
      $("legend-sub").textContent = layers.length === 1 ? T(layers[0].legendTitle || layers[0].title) : "";
    });
  }

  // ══ 내 자료 — 지구 점묶음 (달의 037·화성의 058 을 옮겼다) ═══════════
  //
  // 지역 탭의 점묶음(`body: "earth"`) 그대로다 — 같은 것을 온 지구에서 본다. 구에는 Cesium 의 점·선·면으로,
  // 평면에는 OpenLayers 의 벡터 레이어로 같은 GeoJSON 을 그린다
  var pointsets = JSON.parse(($("pointset-data") || {}).textContent || "[]");
  var cSets = {}, oSets = {}, extents = {};
  var PS_OFF = "gsm.earth.pointsets.off";
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
  // 점이 지구를 뚫고 앞면에 비친다(달의 창어 4 호가 그랬다). 3 000 km 는 지구 반지름보다 짧다
  var NO_DEPTH = 3000000;
  function ringPositions(ring) {
    var flatArr = [];
    ring.forEach(function (c) { flatArr.push(c[0], c[1]); });
    return Cesium.Cartesian3.fromDegreesArray(flatArr, ELL);
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
        position: Cesium.Cartesian3.fromDegrees(g.coordinates[0], g.coordinates[1], 0, ELL),
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
  var setGen = 0;              // 연대가 바뀌어 다시 받으면 늦게 온 옛 답을 버린다
  function loadSet(ps) {
    if (loading[ps.id]) return loading[ps.id];
    var gen = setGen;
    // 그때의 지구에서는 서버가 점을 그 연대의 자리로 옮겨 준다(`pointsets/<id>/paleo/`). 선·면은 오지 않는다 (091)
    var url = paleoOn() ? BASE + "pointsets/" + ps.id + "/paleo/?age=" + age : BASE + "pointsets/" + ps.id + "/geojson/";
    loading[ps.id] = fetch(url).then(function (r) { return r.json(); }).then(function (data) {
      if (gen !== setGen) return;
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
      var elev = iconButton("⛰", T("표고 채우기 — 표고 타일에서 점마다 고도를 읽는다 (극지 PGC · 일본 국토지리원 · 그 밖 SRTM)"),
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

  // ══ 시간 축 (wetherilli P07·091) ═══════════════════════════════════
  //
  // 연대 하나(`age`, Ma)를 로그 막대로 고른다 — 1 ka 에서 1 100 Ma 까지 여섯 자릿수가 한 막대에 선다. ETT 처럼
  // "전체 시대 / 최근 빙기" 창을 가르지 않았다 — 빙상 밑의 대륙을 묻는 물음이 두 화면으로 쪼개진다(P07 §2).
  //
  // **1 Ma 가 두 뜻을 가른다.** 그 안쪽은 오늘의 지구에 그 연대의 것을 얹는다(판이 움직인 것이 수십 km 안이다).
  // 1 Ma 부터는 서버가 판을 돌려 칠한 **그때의 지구**를 바다색 구 위에 그리고, 오늘의 것(영상·지형·지질도)은
  // 뜨지 않는다 — 오늘 드러난 암석이 그때 거기 드러나 있었다는 뜻으로 읽히지 않게. 판을 돌리는 셈은 서버의
  // `paleo.py` 하나다 — 브라우저에 한 벌 더 두지 않는다
  var AGE_LOG0 = Math.log(0.001) / Math.LN10, AGE_LOG1 = Math.log(AGE_MAX) / Math.LN10;
  var SLIDER = 1000;
  function toSlider(a) {
    if (!(a > 0)) return 0;
    return Math.max(1, Math.min(SLIDER, Math.round(1 + (SLIDER - 1) * (Math.log(a) / Math.LN10 - AGE_LOG0) / (AGE_LOG1 - AGE_LOG0))));
  }
  function fromSlider(v) {
    return v <= 0 ? 0 : snapAge(Math.pow(10, AGE_LOG0 + (v - 1) / (SLIDER - 1) * (AGE_LOG1 - AGE_LOG0)));
  }
  function ageText(a) {
    if (!(a > 0)) return T("오늘");
    if (a < PALEO_FROM) return Math.round(a * 1000).toLocaleString() + " ka";
    return a.toLocaleString() + " Ma";
  }
  /** "250"·"250 Ma"·"20 ka"·"1.2 Ga"·"오늘" → Ma. 못 읽으면 null */
  function parseAge(text) {
    var t = String(text).trim().toLowerCase();
    if (t === "" || t === "0" || t === T("오늘").toLowerCase() || t === "today") return 0;
    var m = /^(\d+(?:[.,]\d+)?)\s*(ka|ma|ga|kyr|myr|gyr)?$/.exec(t.replace(/\s+/g, " "));
    if (!m) return null;
    var v = parseFloat(m[1].replace(",", ".")), unit = (m[2] || "ma").charAt(0);
    return snapAge(unit === "k" ? v / 1000 : unit === "g" ? v * 1000 : v);
  }
  // 자료가 있는 구간 — 막대 위의 띠. 단계마다 한 줄씩 는다 (P07 §4)
  var AGE_BANDS = [
    { title: "판 조각 (PALEOMAP 2016)", from: PALEO_FROM, to: AGE_MAX },
  ];
  var COAST_AGES = (THEN.coast || []).filter(function (a) { return a >= PALEO_FROM; });
  if (COAST_AGES.length) AGE_BANDS.push({ title: "옛 해안선", from: COAST_AGES[0], to: COAST_AGES[COAST_AGES.length - 1] + 10 });
  var ICE_AGES = THEN.icemargins || {};
  var iceAll = (ICE_AGES.nadi || []).concat(ICE_AGES.dated || []);
  if (iceAll.length) {
    AGE_BANDS.push({ title: "빙상 가장자리", from: Math.min.apply(null, iceAll) / 1000, to: Math.max.apply(null, iceAll) / 1000 });
  }
  /** 빙상 가장자리의 조각 — 묶음마다 가장 가까운 것, 반 조각 간격 안에서만 (서버의 `icemargins.pick` 과 같다) */
  function iceStops(a) {
    var ka = a * 1000, out = {};
    [["nadi", 0.5], ["dated", 1]].forEach(function (pair) {
      var best = null;
      (ICE_AGES[pair[0]] || []).forEach(function (c) { if (best == null || Math.abs(c - ka) < Math.abs(best - ka)) best = c; });
      if (best != null && Math.abs(best - ka) <= pair[1] / 2 + 1e-9) out[pair[0]] = best;
    });
    return out;
  }
  /** 옛 해안선의 시점 — 가장 가까운 것, 10 Myr 안에서만 (서버의 `paleocoast.stop` 과 같다) */
  function coastStop(a) {
    var best = null;
    (THEN.coast || []).forEach(function (c) { if (best == null || Math.abs(c - a) < Math.abs(best - a)) best = c; });
    return best != null && Math.abs(best - a) <= 10 ? best : null;
  }
  var AGE_TICKS = [[0.001, "1 ka"], [0.01, "10 ka"], [0.1, "100 ka"], [1, "1 Ma"], [10, "10 Ma"], [100, "100 Ma"], [1000, "1 Ga"]];
  var ageRange = $("age-range"), ageInput = $("age-input");
  function pct(a) { return (toSlider(a) / SLIDER * 100).toFixed(2) + "%"; }
  $("age-ticks").innerHTML = AGE_TICKS.map(function (t) {
    return '<span style="left:' + pct(t[0]) + '">' + t[1] + "</span>";
  }).join("");
  $("age-bands").innerHTML = AGE_BANDS.map(function (b) {
    var left = toSlider(b.from) / SLIDER * 100, right = toSlider(b.to) / SLIDER * 100;
    return '<div class="tb-band" title="' + esc(T(b.title)) + " · " + esc(ageText(b.from)) + "–" + esc(ageText(b.to)) +
           '"><span style="left:' + left.toFixed(2) + "%;width:" + (right - left).toFixed(2) + '%"></span></div>';
  }).join("");
  $("age-bands").style.height = AGE_BANDS.length * 6 + "px";

  // 시대 이름 — 지질도 범례와 같은 ICS 기(period)의 목록을 한 번 받는다
  var periods = null;
  fetch(BASE + "earth/legend/").then(function (r) { return r.json(); })
    .then(function (d) { periods = d.rows || []; showAge(); }).catch(function () { periods = []; });
  function periodOf(a) {
    var hit = (periods || []).filter(function (r) { return r.t_age <= a && a < r.b_age; })[0];
    return hit ? hit.name : "";
  }

  // 그때의 지구 — 칠한 판 조각. 연대마다 타일 주소가 달라 레이어를 갈아 끼운다
  var cPaleo = null, paleoShown = null;
  var oPaleo = new ol.layer.Tile({ visible: false });
  flat.getLayers().insertAt(1, oPaleo);            // 배경 바로 위 — 점묶음·찍은 것은 그 위다
  var OCEAN = "#1b3a5e";
  function showPaleo(a) {
    if (a === paleoShown) return;
    paleoShown = a;
    if (cPaleo) { viewer.imageryLayers.remove(cPaleo, true); cPaleo = null; }
    if (a == null) { oPaleo.setVisible(false); return; }
    cPaleo = viewer.imageryLayers.addImageryProvider(cPaleoProvider(paleoUrl("land", a), PALEO_CREDIT), 1);
    oPaleo.setSource(paleoSource(paleoUrl("land", a)));
    oPaleo.setVisible(true);
  }

  // 연대를 따르는 레이어(옛 해안선·화석 산지) — 타일 주소가 연대마다 달라, 주소가 바뀌면 갈아 끼운다. 구는 같은
  // 자리(차례)에 새로 넣는다
  var urlNow = {};
  GEO_NAMES.forEach(function (n) { urlNow[n] = geoUrl(n); });
  function refreshThen() {
    var changed = GEO_NAMES.filter(function (n) { return geoUrl(n) !== urlNow[n]; });
    if (!changed.length) return;
    changed.forEach(function (name) {
      urlNow[name] = geoUrl(name);
      var at = viewer.imageryLayers.indexOf(cGeo[name]);
      viewer.imageryLayers.remove(cGeo[name], true);
      cGeo[name] = viewer.imageryLayers.addImageryProvider(cPaleoProvider(geoUrl(name), creditOf(name), LAYER[name].max), at);
      cRaise[name] = [cGeo[name]];
      oGeo[name].setSource(geoSource(name));
    });
    applyStack();
  }
  var wasPaleo = null, setsAt = 0;
  function showAge() {
    var p = paleoOn();
    ageRange.value = toSlider(age);
    if (document.activeElement !== ageInput) ageInput.value = ageText(age);
    var period = age > 0 ? periodOf(age) : "";
    $("age-period").textContent = period;
    $("age-now").disabled = !age;
    $("timebar").classList.toggle("paleo", p);
    var note = !age ? "" : p
      ? T("PALEOMAP 2016 판 회전으로 셈한 그때의 지구다 — 관측이 아니다. 다른 판 모델과는 100 Ma 에 1 000 km 안팎 다르다. 오늘의 영상·지형·지질도는 오늘에만 뜬다")
      : T("오늘의 지구다 — 1 Ma 안에서 판이 움직인 것은 수십 km 안이다");
    if (!p && age > 0 && isOn("icemargins")) {
      var ice = iceStops(age), bits = [];
      if (ice.nadi != null) bits.push(T("북미 {ka} ka", { ka: ice.nadi }));
      if (ice.dated != null) bits.push(T("유라시아 {ka} ka", { ka: ice.dated }));
      note += " · " + (bits.length ? T("빙상 가장자리 — {what} (연대 측정을 모은 복원)", { what: bits.join(" · ") })
                                 : T("빙상 가장자리는 25–1 ka 에만 있다"));
    }
    if (isOn("mantle") && Object.keys(MANTLE).length) {
      note += " · " + T("맨틀은 OPT1 의 {ma} Ma — 모의 결과이지 관측이 아니다", { ma: 1000 - 20 * mantleFrameOf(age) }) +
              " " + T("(슬랩 파랑·더미 빨강, 밝을수록 얕다)") +
              (p ? " " + T("(맨틀 기준틀이라 판 조각과 어긋난다)") : "");
    }
    if (p && isOn("coast")) {
      var c = coastStop(age);
      note += " · " + (c == null ? T("옛 해안선은 이 연대에 없다 (0–535 Ma, 가까운 시점 10 Myr 안)")
                                : T("옛 해안선은 {age} Ma 의 것 — 화석이 가리키는 가장 깊은 바다", { age: c }));
    }
    $("age-note").textContent = note.replace(/^ · /, "");
  }
  function applyAge(a) {
    a = snapAge(a);
    var changed = a !== age;
    age = a;
    save("gsm.earth.age", age);
    try {
      var q = new URLSearchParams(location.search);
      if (age) q.set("age", String(age)); else q.delete("age");
      var qs = q.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    } catch (e) { /* file:// 따위 */ }
    var p = paleoOn();
    if (p) hideProfile();                               // 높이 그래프는 오늘의 땅이다 (wetherilli 186)
    showAge();
    if (p !== wasPaleo) {
      wasPaleo = p;
      cBase.show = !p;
      oBase.setVisible(!p);
      scene.globe.baseColor = Cesium.Color.fromCssColorString(p ? OCEAN : "#0b1a2a");
      $("map").style.background = p ? OCEAN : "";
      scene.terrainProvider = look.terrain && !p ? demTerrain : flatTerrain;
      terrainBox.disabled = p;
      exag.disabled = p || !look.terrain;
      applyStack();
    }
    showPaleo(p ? age : null);
    refreshThen();
    // 점묶음 — 그때의 지구에서는 그 연대의 자리로 옮긴 것을 다시 받는다. 오늘의 지구끼리는 그대로다
    var want = p ? age : 0;
    if (want !== setsAt) {
      setsAt = want;
      ++setGen;
      pointsets.forEach(function (ps) { dropSet(ps.id); });
      renderSets();
    }
    if (changed) closePopup();
  }
  var ageTimer = 0;
  ageRange.addEventListener("input", function () {
    var a = fromSlider(+ageRange.value);
    ageInput.value = ageText(a);
    clearTimeout(ageTimer);
    ageTimer = setTimeout(function () { applyAge(a); }, 180);   // 끄는 동안 타일을 쏟아 묻지 않게
  });
  $("age-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var a = parseAge(ageInput.value);
    if (a == null) { ageInput.value = ageText(age); return; }
    ageInput.blur();
    applyAge(a);
  });
  ageInput.addEventListener("blur", function () { ageInput.value = ageText(age); });
  $("age-now").addEventListener("click", function () { applyAge(0); });

  // 그때의 지구를 누르면 — 그 자리에 있던 판 조각과, 그 판의 회전을 되돌린 **오늘의 자리**. 오늘의 자리에서
  // 지질 단위를 다시 묻는다. 계산이지 관측이 아니다
  function askPaleo(ll, pixel) {
    markAt(ll);
    var mine = ++asked, at = age;
    var head = "<h3>" + esc(T("그때의 지구 · {age}", { age: ageText(at) })) + "</h3>" + coordHead(ll);
    showPopup(head + '<p class="none">' + esc(T("읽는 중")) + "</p>", pixel);
    fetch(BASE + "earth/paleo/at/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) + "&age=" + at)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (mine !== asked) return;
        if (d.error || !d.rows) { showPopup(head + '<p class="none">' + esc(d.error || d.text) + "</p>", pixel); return; }
        var today = [d.today_lon, d.today_lat];
        var html = head + "<table>" + d.rows.map(function (row) {
          return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>";
        }).join("") + "</table>" +
          '<button type="button" class="today-go" data-lon="' + today[0] + '" data-lat="' + today[1] + '">' +
          esc(T("오늘의 그 자리로")) + "</button>";
        showPopup(html + '<p class="none">' + esc(T("읽는 중")) + "</p>", pixel);
        return fetch(BASE + "earth/info/?lon=" + today[0].toFixed(4) + "&lat=" + today[1].toFixed(4) + "&z=" + hereZoom())
          .then(function (r) { return r.json(); })
          .then(function (info) {
            if (mine !== asked) return;
            html += "<h3>" + esc(T("오늘 그 자리의 지질 단위")) + "</h3>";
            html += info.units && info.units.length
              ? info.units.map(function (u) { return unitTable(u, today); }).join("")
              : '<p class="none">' + esc(T(info.error ? "속성을 받지 못했다" : "여기에는 지질 단위가 없다")) + "</p>";
            showPopup(html, pixel);
          });
      })
      .catch(function () { if (mine === asked) showPopup(head + '<p class="none">' + esc(T("속성을 받지 못했다")) + "</p>", pixel); });
  }
  // ══ 화석 산지를 누르면 (wetherilli 098) ══════════════════════════
  //
  // 켜져 있으면 먼저 누른 자리 둘레(7 칸)의 산지를 묻는다. 있으면 산지를, 없으면 여느 때처럼 그 자리를(오늘은 지질 단위,
  // 옛 연대는 판 조각) 보인다 — 점묶음의 점을 누른 것과 같은 차례다
  function askAt(ll, pixel) {
    var perPx = (mode === "flat" ? groundRes() : heightToRes(hereHeight())) / 111320;
    // 화산이 켜져 있고 보이면 그것부터 — 없으면 화석 산지, 그다음 그 자리 (wetherilli 134)
    var kinds = [["volcanoes", "holocene"], ["pleistocene", "pleistocene"]].filter(function (k) {
      return isOn(k[0]) && LAYER[k[0]] && visibleNow(k[0]);
    }).map(function (k) { return k[1]; });
    if (kinds.length) {
      var mineV = ++asked;
      fetch(BASE + "earth/volcanoes/at/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) +
            "&r=" + Math.max(0.002, perPx * 8).toFixed(4) + "&kinds=" + kinds.join(","))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (mineV !== asked) return;
          if (d.hits && d.hits.length) showVolcanoes(d.hits, pixel); else askQuake(ll, pixel, perPx);
        })
        .catch(function () { if (mineV === asked) askQuake(ll, pixel, perPx); });
      return;
    }
    askQuake(ll, pixel, perPx);
  }
  // 지진 — 켠 규모 칸에서만 찾는다. 없으면 화석 산지 (wetherilli 138)
  function askQuake(ll, pixel, perPx) {
    var bands = active.filter(function (e) { return LAYER[e.name].quake && visibleNow(e.name); })
                      .map(function (e) { return e.name; });
    if (!bands.length) { askHeat(ll, pixel, perPx, function (l, p, q) { askStress(l, p, q, function (a, b, c) { askMinerals(a, b, c, askFossil); }); }); return; }
    var mine = ++asked;
    fetch(BASE + "earth/quakes/at/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) +
          "&r=" + Math.max(0.002, perPx * 7).toFixed(4) + "&bands=" + bands.join(","))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (mine !== asked) return;
        if (d.hits && d.hits.length) showQuakes(d.hits, pixel); else askHeat(ll, pixel, perPx, afterHeat);
      })
      .catch(function () { if (mine === asked) askHeat(ll, pixel, perPx, afterHeat); });
  }
  // 지열류 다음은 응력, 그다음 고생태 (wetherilli 273)
  function afterHeat(ll, pixel, perPx) { askStress(ll, pixel, perPx, afterStress); }
  // 응력 다음은 광상, 그다음 고생태 (wetherilli 276)
  function afterStress(ll, pixel, perPx) { askMinerals(ll, pixel, perPx, askNeotoma); }
  // 세계 광상 — 켠 칸에서만. 없으면 `next` (wetherilli 276)
  function askMinerals(ll, pixel, perPx, next) {
    var on = active.filter(function (e) { return LAYER[e.name].mineral && visibleNow(e.name); }).map(function (e) { return e.name; });
    if (!on.length) { next(ll, pixel, perPx); return; }
    var mine = ++asked;
    fetch(BASE + "earth/minerals/at/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) +
          "&r=" + Math.max(0.002, perPx * 7).toFixed(4) + "&bands=" + on.join(","))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (mine !== asked) return;
        if (!(d.hits && d.hits.length)) { next(ll, pixel, perPx); return; }
        markAt(d.hits[0].at);
        var html = coordHead(d.hits[0].at);
        if (d.hits.length > 1) html += '<p class="none">' + esc(T("광상 {n} 곳 가운데 크고 가까운 것부터 (USGS)", { n: d.hits.length })) + "</p>";
        html += d.hits.map(function (h) {
          return '<h3><span class="chip" style="background:' + esc(h.color) + '"></span> ' + esc(h.name) + "</h3><table>" +
            h.rows.map(function (row) { return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>"; }).join("") + "</table>" +
            (h.link ? '<p><a class="ett-link" target="_blank" rel="noopener" href="' + esc(h.link) + '">' + esc(T("USGS 에서 보기")) + "</a></p>" : "");
        }).join("");
        showPopup(html, pixel);
      })
      .catch(function () { if (mine === asked) next(ll, pixel, perPx); });
  }
  // 지각 응력 — 켜져 있고 보이면 누른 자리 둘레의 측정. 없으면 `next` (wetherilli 273)
  function askStress(ll, pixel, perPx, next) {
    if (!(isOn("stress") && LAYER.stress && visibleNow("stress"))) { next(ll, pixel, perPx); return; }
    var mine = ++asked;
    fetch(BASE + "earth/stress/at/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) +
          "&r=" + Math.max(0.002, perPx * 8).toFixed(4))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (mine !== asked) return;
        if (!(d.hits && d.hits.length)) { next(ll, pixel, perPx); return; }
        markAt(d.hits[0].at);
        var html = coordHead(d.hits[0].at);
        if (d.hits.length > 1) html += '<p class="none">' + esc(T("측정 {n} 곳 가운데 가까운 것부터 (WSM)", { n: d.hits.length })) + "</p>";
        html += d.hits.map(function (h) {
          return '<h3><span class="chip" style="background:' + esc(h.color) + '"></span> ' + esc(h.name) + "</h3><table>" +
            h.rows.map(function (row) { return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>"; }).join("") + "</table>";
        }).join("") + '<p><a class="ett-link" target="_blank" rel="noopener" href="' + esc(d.link) + '">' + esc(T("World Stress Map (GFZ)")) + "</a></p>";
        showPopup(html, pixel);
      })
      .catch(function () { if (mine === asked) next(ll, pixel, perPx); });
  }
  // 지열류 — 켜져 있고 보이면 누른 자리 둘레의 측정. 없으면 `next` (wetherilli 267)
  function askHeat(ll, pixel, perPx, next) {
    if (!(isOn("heatflow") && LAYER.heatflow && visibleNow("heatflow"))) { next(ll, pixel, perPx); return; }
    var mine = ++asked;
    fetch(BASE + "earth/heatflow/at/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) +
          "&r=" + Math.max(0.002, perPx * 7).toFixed(4))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (mine !== asked) return;
        if (!(d.hits && d.hits.length)) { next(ll, pixel, perPx); return; }
        markAt(d.hits[0].at);
        var html = coordHead(d.hits[0].at);
        if (d.hits.length > 1) html += '<p class="none">' + esc(T("측정 {n} 곳 가운데 가까운 것부터 (IHFC)", { n: d.hits.length })) + "</p>";
        html += d.hits.map(function (h) {
          return "<h3>" + esc(h.name) + "</h3><table>" + h.rows.map(function (row) {
            return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>";
          }).join("") + "</table>";
        }).join("") + '<p><a class="ett-link" target="_blank" rel="noopener" href="' + esc(d.link) + '">' + esc(T("IHFC 자료 (GFZ)")) + "</a></p>";
        showPopup(html, pixel);
      })
      .catch(function () { if (mine === asked) next(ll, pixel, perPx); });
  }
  // 고생태 산지 — 켠 자료형 칸에서, 지금의 연대를 품은 것만. 없으면 화석 산지 (wetherilli 139)
  function askNeotoma(ll, pixel, perPx) {
    var bands = active.filter(function (e) { return LAYER[e.name].neo && visibleNow(e.name); })
                      .map(function (e) { return e.name; });
    if (!bands.length) { askFossil(ll, pixel, perPx); return; }
    var mine = ++asked;
    fetch(BASE + "earth/neotoma/at/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) + "&age=" + age +
          "&r=" + Math.max(0.002, perPx * 7).toFixed(4) + "&bands=" + bands.join(","))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (mine !== asked) return;
        if (d.hits && d.hits.length) showNeotoma(d.hits, pixel); else askFossil(ll, pixel, perPx);
      })
      .catch(function () { if (mine === asked) askFossil(ll, pixel, perPx); });
  }
  function showNeotoma(hits, pixel) {
    markAt(hits[0].at);
    var html = coordHead(hits[0].at);
    if (hits.length > 1) html += '<p class="none">' + esc(T("산지 {n} 곳 가운데 가까운 것부터 (Neotoma)", { n: hits.length })) + "</p>";
    html += hits.map(function (h) {
      return "<h3>" + esc(h.name) + "</h3><table>" + h.rows.map(function (row) {
        return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>";
      }).join("") + '</table><p><a class="ett-link" target="_blank" rel="noopener" href="' + esc(h.link) + '">' +
        esc(T("Neotoma 에서 보기")) + "</a></p>";
    }).join("");
    showPopup(html, pixel);
  }
  function showQuakes(hits, pixel) {
    markAt(hits[0].at);
    var html = coordHead(hits[0].at);
    if (hits.length > 1) html += '<p class="none">' + esc(T("지진 {n} 곳 가운데 가까운 것부터", { n: hits.length })) + "</p>";
    html += hits.map(function (h) {
      return "<h3>" + esc(h.name) + "</h3><table>" + h.rows.map(function (row) {
        return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>";
      }).join("") + '</table><p><a class="ett-link" target="_blank" rel="noopener" href="' + esc(h.link) + '">' +
        esc(T("USGS 에서 보기")) + "</a></p>";
    }).join("");
    showPopup(html, pixel);
  }
  function showVolcanoes(hits, pixel) {
    markAt(hits[0].at);
    var html = coordHead(hits[0].at);
    if (hits.length > 1) html += '<p class="none">' + esc(T("화산 {n} 곳 가운데 가까운 것부터", { n: hits.length })) + "</p>";
    html += hits.map(function (h) {
      return "<h3>" + esc(h.name) + "</h3><table>" + h.rows.map(function (row) {
        return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>";
      }).join("") + '</table><p><a class="ett-link" target="_blank" rel="noopener" href="' + esc(h.link) + '">' +
        esc(T("GVP 에서 보기")) + "</a></p>";
    }).join("");
    showPopup(html, pixel);
  }
  function askFossil(ll, pixel, perPx) {
    var ask = paleoOn() ? askPaleo : askUnit;
    if (!isOn("fossils") || !THEN.fossils) { ask(ll, pixel); return; }
    var mine = ++asked;
    fetch(BASE + "earth/fossils/at/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) + "&age=" + age +
          "&r=" + Math.max(0.002, perPx * 7).toFixed(4))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (mine !== asked) return;
        if (!d.hits || !d.hits.length) { ask(ll, pixel); return; }
        showFossils(d.hits, pixel);
      })
      .catch(function () { if (mine === asked) ask(ll, pixel); });
  }
  function showFossils(hits, pixel) {
    var first = hits[0];
    markAt(first.at);
    var html = coordHead(first.today) + paleoForm(first.today, first.mid);
    if (hits.length > 1) html += '<p class="none">' + esc(T("산지 {n} 곳 가운데 가까운 것부터", { n: hits.length })) + "</p>";
    html += hits.map(function (h) {
      return "<h3>" + esc(h.name) + "</h3><table>" + h.rows.map(function (row) {
        return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>";
      }).join("") + '</table><p><a class="ett-link" target="_blank" rel="noopener" href="' + esc(h.link) + '">' +
        esc(T("PBDB 에서 보기")) + "</a></p>";
    }).join("");
    showPopup(html, pixel);
  }
  function goToday(lon, lat) {
    var c = cameraLL();
    applyAge(0);
    goTo(lon, lat, Math.min(c ? c.h : HOME_H, 3000000));
  }

  renderSets();
  renderCatalog();
  renderActive();
  applyStack();
  setsAt = paleoOn() ? age : 0;
  applyAge(age);

  // 올리기 — 2D 의 불러오기와 같은 꼴. 몸은 지구다 — 지역 탭에도 뜬다
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
    var data = new FormData(form), file = fileInput.files[0];
    data.set("body", "earth");
    msgBox.className = "msg";
    msgBox.textContent = T("올리는 중");
    var upload = function (body, extra) {
      return post(BASE + "pointsets/upload/", body).then(function (d) {
        // 위경도 없이 주소만 적힌 CSV — 지역 탭의 길(wetherilli 152)을 옮겼다: 화면이 나눠 묻고 다시 올린다 (wetherilli 194)
        if (d.geocode) return geocodeRows(d.geocode).then(function (job) {
          if (!job) return;
          var again = new FormData(form);
          again.set("body", "earth");
          again.set("file", new File([job.csv], file.name.replace(/\.[^.]*$/, "") + ".csv", { type: "text/csv" }));
          if (!again.get("name")) again.set("name", file.name.replace(/\.[^.]*$/, ""));
          again.set("crs", "4326");
          return upload(again, job.note);
        });
        pointsets.unshift(d.pointset);
        setOff(d.pointset.id, false);
        renderSets();
        flyToSet(d.pointset);
        form.reset();
        fileInput.dispatchEvent(new Event("change"));
        $("upload-color").value = PALETTE[pointsets.length % PALETTE.length];
        msgBox.className = "msg good";
        msgBox.textContent = [T("{n}점을 올렸다", { n: d.pointset.count })].concat(d.notes || [], extra ? [extra] : []).join(" ");
      });
    };
    upload(data).catch(function (err) {
      msgBox.className = "msg bad";
      msgBox.textContent = (err && err.message) || T("올리지 못했다");
    });
  });
  /** 주소 줄들을 `chunk` 줄씩 서버(`pointsets/geocode/`)로 찾아, 위도·경도·찾은 주소 열을 붙인 CSV 를 짓는다 — `map.js` 의 것과
   *  같다 (wetherilli 152·194). 서버가 VWorld 지오코더로 찾으므로 **한국 주소만** 붙는다. 못 찾은 줄은 빼고 줄 번호를 알린다.
   *  하나도 못 찾았거나 상류가 거절하면 null */
  function geocodeRows(job) {
    var rows = job.rows, chunk = job.chunk || 50, points = [], i = 0;
    var step = function () {
      if (i >= rows.length) return Promise.resolve();
      msgBox.className = "msg";
      msgBox.textContent = T("주소로 좌표를 찾는 중… {done} / {all}줄", { done: i, all: rows.length });
      var part = rows.slice(i, i + chunk);
      return fetch(BASE + "pointsets/geocode/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
        body: JSON.stringify({ addresses: part.map(function (r) { return r.address; }) }),
      }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) throw new Error(res.d.error || T("올리지 못했다"));
          res.d.results.forEach(function (p, k) { points[i + k] = p; });
          i += chunk;
          return step();
        });
    };
    return step().then(function () {
      var missed = job.blank.slice();
      var cols = job.fields.concat([T("위도"), T("경도"), T("찾은 주소")]);
      var lines = [cols.map(csvCell).join(",")];
      rows.forEach(function (row, k) {
        var p = points[k];
        if (!p) { missed.push(row.line); return; }
        lines.push(job.fields.map(function (f) { return csvCell(row.values[f]); })
          .concat([p.lat, p.lon, csvCell(p.matched)]).join(","));
      });
      if (lines.length < 2) {
        msgBox.className = "msg bad";
        msgBox.textContent = T("주소로 좌표를 하나도 찾지 못했다 — 도로명·지번 주소인지 본다.");
        return null;
      }
      missed.sort(function (a, b) { return a - b; });
      var shown = missed.slice(0, 20).join(", ") + (missed.length > 20 ? " …" : "");
      return { csv: lines.join("\n"),
               note: missed.length ? T("주소를 못 찾은 줄 {n}개 — {lines}", { n: missed.length, lines: shown }) : "" };
    }).catch(function (err) {
      msgBox.className = "msg bad";
      msgBox.textContent = (err && err.message) || T("올리지 못했다");
      return null;
    });
  }
  function csvCell(value) {
    var text = value == null ? "" : String(value);
    return /[",\n\r]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  }

  // ══ 좌표·지명으로 이동 — 좌표 막대 ══════════════════════════════
  //
  // 지명은 Natural Earth 의 도시·산맥·바다·호수·강 1 만여 이름이다(`earth/places/`, 102). 한국어·영어 이름으로 찾는다.
  // 화석 산지·지층(PBDB)과 화산(GVP)의 이름도 함께 온다 — 결과마다 갈래(`group`)와 딱지(`kind`), 덧말(`sub`)이 붙는다(wetherilli 187).
  // 화성의 찾기(058)와 같은 꼴이다. 오늘의 자리라 옛 연대에서 고르면 오늘로 돌아온다
  var gotoForm = $("goto-form"), gotoInput = $("goto-input"), results = $("search-results");
  var found = [], foundFrom = [], picked = -1, findTimer = null, findAsked = 0;
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
               '</span><span class="title">' + esc(p.title) + '</span><span class="sub">' +
               (p.sub ? esc(p.sub) + " · " : "") + p.lat.toFixed(3) + ", " + p.lon.toFixed(3) + "</span></li>";
      }).join("") + '<li class="note src">' + esc((foundFrom.length ? foundFrom : ["Natural Earth 10 m"]).join(" · ")) + "</li>";
    }
    results.hidden = false;
    results.querySelectorAll("li[data-i]").forEach(function (li) {
      li.addEventListener("mousedown", function (e) { e.preventDefault(); choose(found[+li.dataset.i]); });
    });
  }
  function choose(place) {
    results.hidden = true;
    gotoInput.value = place.title.replace(/ \(.*\)$/, "");
    if (paleoOn()) applyAge(0);
    // 화석 산지·화산·도시는 가까이, 지층·강·호수는 조금 멀리, 산맥·바다는 멀리
    var h = place.group === "fossil" ? 30000 : place.group === "volcano" ? 60000 : place.group === "formation" ? 400000
          : /도시|city/.test(place.kind) ? 80000 : /강|호수|river|lake/.test(place.kind) ? 400000 : 1500000;
    goTo(place.lon, place.lat, h);
  }
  gotoInput.addEventListener("input", function () {
    clearTimeout(findTimer);
    var q = gotoInput.value.trim();
    if (!q || parseLatLon(q)) { results.hidden = true; return; }
    findTimer = setTimeout(function () {
      var mine = ++findAsked;
      fetch(BASE + "earth/places/?q=" + encodeURIComponent(q)).then(function (r) { return r.json(); }).then(function (data) {
        if (mine !== findAsked) return;
        found = data.results || [];
        foundFrom = data.sources || [];
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
    if (ll) { results.hidden = true; goTo(ll.lon, ll.lat, 120000); return; }
    if (found.length) choose(found[Math.max(0, picked)]);
  });

  // ══ 자전축 — 구에서 방향을 잡는 꼬챙이 (041·045) ═════════════════
  //
  // 구를 돌리고 기울이다 보면 어느 쪽이 북인지 놓친다. 지구 고정 좌표(ECEF)의 Z 축이 곧 자전축이다. 달(041·045)과
  // 같다 — 지구 속을 지나는 토막도 흐린 끊은 선으로 비쳐 남극점 → 중심 → 북극점이 한 막대로 읽힌다.
  // **가까이 가면 치운다**(카메라 높이 4 800 km 밑 — 화성의 두 배). 평면은 늘 북쪽이 위라 구에서만 보인다
  var AXIS_OUT = R * 1.45, AXIS_NEAR = 4800000;
  var axisOn = saved("gsm.earth.axis", "on") !== "off", axisFar = true;
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
      position: new Cesium.Cartesian3(0, 0, end[0] * ELL.minimumRadius),     // 극 반지름
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
    save("gsm.earth.axis", axisOn ? "on" : "off");
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
    show: false, position: Cesium.Cartesian3.fromDegrees(0, 0, 0, ELL),
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
    if (ll) markC.position = Cesium.Cartesian3.fromDegrees(ll[0], ll[1], 0, ELL);
  }

  // ══ 도구 — 점 찍기·거리·넓이·범위 (041) ═══════════════════════════
  //
  // 2D 의 그리기 도구와 같은 넷이다. **찍고 잰 것은 경위도로 한 곳에 들고, 구와 평면이 저마다
  // 그린다** — 켠 레이어·점묶음처럼 넘어가도 그대로 남는다. 그리던 것(끝내지 않은 선)만 넘어갈 때
  // 버리므로, 그리는 동안은 저절로 넘어가지 않는다(`drawing()`).
  //
  // 길이·넓이는 **평균 반지름의 구**(6 371.0088 km)로 잰다 — 평면의 가로는 위도만큼 늘어나 있어 평면
  // 좌표로 재면 틀린다. 넓이는 OpenLayers 의 `ol.sphere.getArea` 와 같은 식이고 반지름도 같다
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
  // 경도를 앞 꼭짓점에서 180° 안쪽으로 — 날짜변경선(±180°)을 건너도 선이 지구를 한 바퀴 돌지 않게
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
      add({ position: Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0, ELL),
            point: { pixelSize: 10, color: WHITE, outlineColor: BLACK, outlineWidth: 2,
                     heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: NO_DEPTH },
            label: cLabel(String(t.no), -15) });
      drawSource.addFeature(new ol.Feature({ geometry: new ol.geom.Point(fromLL([t.lon, t.lat])), kind: "temp", no: t.no }));
    });
    ranges.forEach(function (r) {
      var ring = rangeRing(r), label = T("범위 {n}", { n: r.no });
      add({ polygon: { hierarchy: positions(ring), material: WHITE.withAlpha(0.1) } });
      add({ polyline: { positions: positions(ring), width: 2, clampToGround: true, material: Cesium.Color.fromCssColorString("#e4e4e4") } });
      add({ position: Cesium.Cartesian3.fromDegrees((r.w + r.e) / 2, (r.s + r.n) / 2, 0, ELL), label: cLabel(label) });
      drawSource.addFeature(new ol.Feature({ geometry: new ol.geom.Polygon([eqc(ring)]), kind: "range", label: label }));
    });
    if (measured) {
      var got = measureOf(measured), c = measured.coords;
      var line = measured.kind === "area" ? c.concat([c[0]]) : c;
      if (measured.kind === "area") add({ polygon: { hierarchy: positions(line), material: WHITE.withAlpha(0.14) } });
      add({ polyline: { positions: positions(line), width: 2.5, clampToGround: true, material: dash() } });
      var at = measured.kind === "area" ? centroid(c) : c[c.length - 1];
      add({ position: Cesium.Cartesian3.fromDegrees(at[0], at[1], 0, ELL), label: cLabel(got.text, measured.kind === "area" ? 0 : -16) });
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
  drawHandler.setInputAction(function () { finishGlobeSketch(); }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
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
  function drawClick(ll) {
    if (!tool) return false;
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

  // ── 높이 그래프 (달의 것을 옮겼다, wetherilli 186) ──
  // 거리를 다 재면 그 선의 표고를 받아(`elevation/profile/`, 지역 탭과 같은 문 — wetherilli 109) 아래 가운데 판에 그린다.
  // 표고는 타일로만 읽는다 — 일본은 국토지리원, 나머지는 AWS Terrarium. 그래프 위를 훑으면 그 자리를 지구에도 찍는다.
  // **오늘의 높이다** — 그때의 지구(1 Ma 부터)에서는 판이 옮겨져 화면의 자리와 오늘의 땅이 맞지 않아 그래프를 띄우지 않는다
  var PROFILE = { W: 640, H: 170, L: 50, R: 10, T: 10, B: 22 };
  var profileSeq = 0, profileData = null, profileBand = null;
  // 지질 띠 (wetherilli 180) — 우리 파일로 그리는 판을 켰을 때만. 지질도(Macrostrat)는 점마다 상류에 물어야 해서 띠가 없다
  var BAND_LAYER = { crust: "earth:crust" };
  function bandLayer() {
    var top = active.filter(function (e) { return BAND_LAYER[e.name]; })[0];
    return top && window.GSMBand ? BAND_LAYER[top.name] : null;
  }
  function hideProfile() {
    profileSeq = (profileSeq || 0) + 1;                   // 연대를 되살릴 때 이 줄보다 먼저 불린다 — 아직 undefined 일 수 있다
    profileData = null;
    $("profile").hidden = true;
  }
  function showProfile(coords) {
    if (paleoOn()) { hideProfile(); return; }
    var seq = ++profileSeq, box = $("profile");
    profileData = null;
    box.hidden = false;
    $("profile-svg").innerHTML = "";
    profileBand = null;
    if (window.GSMBand) GSMBand.reset($("profile-svg"), PROFILE);
    $("profile-sum").textContent = "";
    $("profile-read").textContent = T("높이를 읽는 중…");
    // 30 m 에 한 점쯤, 64–512 점 (지역 탭과 같다)
    var n = Math.max(64, Math.min(512, Math.round(lengthOf(coords) / 30)));
    var line = coords.map(function (c) { return c[0].toFixed(5) + "," + c[1].toFixed(5); }).join(";");
    fetch(BASE + "elevation/profile/?line=" + encodeURIComponent(line) + "&n=" + n)
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        if (seq !== profileSeq) return;
        drawProfile(d);
        var layer = bandLayer();
        if (!layer || !profileData) return;
        GSMBand.load(BASE, layer, line, n).then(function (band) {
          if (seq !== profileSeq || !band || !profileData) return;
          profileBand = band;
          GSMBand.draw($("profile-svg"), PROFILE, profileData.X, d, band, T("지각"));
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
    var read = (d.sources || []).some(function (s) { return s.indexOf("gsi") === 0; })
      ? T("국토지리원·AWS 표고 타일에서 읽은 해발 높이 — 바다는 수심(음수)") : T("AWS 표고 타일(SRTM·GMTED)에서 읽은 해발 높이 — 바다는 수심(음수)");
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
    var p = scene.cartesianToCanvasCoordinates(Cesium.Cartesian3.fromDegrees(ll[0], ll[1], 0, ELL));
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
    var go = e.target.closest(".today-go");
    if (go) { goToday(+go.dataset.lon, +go.dataset.lat); return; }
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

  // 점묶음으로 저장 — 2D 와 같은 길(`pointsets/create/`)이고 몸도 지구다. 좌표는 ±180° 로 되돌려 싣는다
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
        name: name, color: "#f2f2f2", body: "earth", shapes: shapes,
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
  //   곱한다. 축척 막대를 넣는다 — 가운데 위도에서 잰다(`ol.proj.getPointResolution`)
  //
  // 팝업·패널은 HTML 이라 담기지 않는다. 찍고 잰 것·누른 자리의 고리·자전축은 캔버스에 있어 담긴다.
  // GIBS·Macrostrat 의 타일은 모두 CORS 로 받는다 — 하나라도 아니면 캔버스가 더럽혀져 뽑히지 않는다
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
        a.download = "GSM-earth-" + stampText().replace(/[-: ]/g, "").slice(0, 12) + ".png";
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

  /** 화면 한 장(`paint` 가 그린다) + 밑의 띠. 띠는 달과 같은 흑백이다 — 인쇄해도 읽히게. */
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
    var shown = active.filter(function (e) { return visibleNow(e.name); })
                      .map(function (e) { return T(LAYER[e.name].title); });
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
        var c = ELL.cartesianToCartographic(p.pos), a = anglesAt(p.pos, false);
        where = fmt(clean([Cesium.Math.toDegrees(c.longitude), Cesium.Math.toDegrees(c.latitude)])) + " · " +
                T("기울기 {tilt}° · 방위 {heading}°", { tilt: Math.round(90 + a.pitch), heading: Math.round(a.heading) % 360 });
      } else where = "—";
      if (look.terrain) where += " · " + T("지형 과장") + " ×" + (look.exag / 10).toFixed(1);
    }
    var credits = paleoOn() ? [PALEO_CREDIT] : [BASES[look.base].credit];
    active.forEach(function (e) {
      if (visibleNow(e.name)) credits.push(creditOf(e.name) || LAYER[e.name].src);
    });
    if (mode === "globe" && look.terrain && !paleoOn()) credits.push(DEM_CREDIT);
    credits = credits.filter(function (c, i) { return c && credits.indexOf(c) === i; });
    var kind = mode !== "flat" ? T("구") : proj === EQC ? T("평면") :
      T("평면") + " (" + T(proj === NPS ? "북극 평사도법" : "남극 평사도법") + ")";
    var out = [T("대돌여지도") + " · " + T("온 지구") + " · " + kind + " · " + stampText()];
    if (age) out.push(T("연대") + ": " + ageText(age) + (paleoOn() ? " · " + T("PALEOMAP 2016 판 회전으로 셈한 그때의 지구") : ""));
    out.push(T("배경") + ": " + (paleoOn() ? T("판 조각 (PALEOMAP 2016)") : base));
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

  // ══ 처음 자리 — 기억한 것. 처음이면 한반도를 멀리서 ═══════════════
  // 맨 끝에 둔다 — 평면으로 여는 길이 팝업·목록을 다 만든 뒤라야 한다
  try {
    var v = JSON.parse(saved("gsm.earth.view", "null"));
    if (v && isFinite(v.lon) && isFinite(v.lat) && isFinite(v.h)) {
      viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(v.lon, v.lat, v.h, ELL),
                              orientation: { heading: v.heading || 0, pitch: isFinite(v.pitch) ? v.pitch : -Math.PI / 2, roll: 0 } });
    } else flyGlobe(HOME[0], HOME[1], HOME_H);
    var f = JSON.parse(saved("gsm.earth.flat", "null"));
    if (saved("gsm.earth.mode", "globe") === "flat" && f && isFinite(f.lon) && isFinite(f.res)) {
      setMode("flat", { lon: f.lon, lat: f.lat, h: resToHeight(f.res) });
    }
  } catch (e) { flyGlobe(HOME[0], HOME[1], HOME_H); }

  // 공유 링크 (wetherilli 189) — 지금 보는 것(구면 카메라, 평면이면 가운데와 땅의 해상도)·켠 레이어·배경
  function shareLink() {
    var q = { m: mode, l: GSMShare.pack(active), b: look.base, a: age || "" };
    if (mode === "flat") {
      var ll = toLL(flat.getView().getCenter());
      q.c = ll[0].toFixed(5) + "," + ll[1].toFixed(5);
      q.res = Math.round(groundRes());
    } else {
      var c = cameraLL();
      if (c) {
        q.c = c.lon.toFixed(5) + "," + c.lat.toFixed(5);
        q.h = Math.round(c.h);
        q.hd = viewer.camera.heading.toFixed(4);
        q.pt = viewer.camera.pitch.toFixed(4);
      }
    }
    return GSMShare.link(q);
  }
  if (window.GSMShare) {
    GSMShare.wire($("tool-share"), shareLink, { done: T("복사했다"), ask: T("이 링크를 복사한다") });
    if (SHARED) GSMShare.notice(T("링크로 연 화면이다 — 여기서 바꾼 것은 이 브라우저에 기억하지 않는다"), T("내 화면으로"));
  }

  // ── 패널 접기 (jikhanjung 008·009) ────────────────────────────────────
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
