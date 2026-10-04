/* 대돌여지도 — 지도 화면.
 *
 * 서버가 아는 것과 여기가 아는 것을 갈라 둔다.
 *   - 인증키는 여기 오지 않는다. 타일은 언제나 ./wms/ 를 부른다
 *   - 좌표 표시는 여기서 한다. 마우스가 움직일 때마다 서버를 부를 수 없다
 *   - 좌표 입력칸이 받는 도분초 해석은 서버에 둔다 (./coords/parse/).
 *     까다로운 쪽이라 파이썬에서 시험하는 편이 낫다
 */
(function () {
  "use strict";

  // 지도는 `map/` 에 산다 — 뿌리는 소개 화면이다 (wetherilli 113). 다른 갈래는 뿌리 밑이다
  // 정적 판의 영어판은 `en/map/` 에 산다 — 뿌리(구운 파일이 있는 곳)는 언어와 상관없이 같다 (wetherilli 167)
  var BASE = location.pathname.replace(/\/(?:en\/)?map\/?$/, "/");

  // ── 말 ───────────────────────────────────────────────────────────
  //
  // 화면의 글은 한국어로 적고 `T()` 로 감싼다. 영어판이면 서버가 번역표
  // (`viewer/i18n.py` 의 `EN`)를 실어 보내고, 표에 없는 문장은 한국어로
  // 남는다. **문장을 새로 적으면 번역표에도 적는다** — 시험
  // (`test_i18n`)이 빠진 것을 잡는다. 숫자·이름이 끼는 자리는 `{n}` 처럼
  // 자리표로 두고 넘긴다 — 영어는 말 차례가 달라 이어 붙이면 어색하다.
  var LANG = document.documentElement.lang === "en" ? "en" : "ko";
  var I18N = JSON.parse((document.getElementById("i18n-data") || {}).textContent || "{}");
  // 화면이 주소를 짓는 우리 타일의 판 (wetherilli 183) — `?v=` 를 붙이면 서버가 길게(immutable) 캐시하게 한다. 판이 바뀌면 주소가 바뀐다
  var TILE_V = JSON.parse((document.getElementById("tile-versions") || {}).textContent || "{}");
  function vq(kind) { return TILE_V[kind] ? "?v=" + TILE_V[kind] : ""; }

  function T(text, vars) {
    var out = (LANG === "en" && I18N[text]) || text;
    if (vars) {
      out = out.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; });
    }
    return out;
  }
  var vworldKey = JSON.parse(document.getElementById("vworld-key").textContent || '""');
  var catalog = JSON.parse(document.getElementById("catalog-data").textContent || "[]");

  // ── 정적 판 (wetherilli P11·162) ─────────────────────────────────
  //
  // 연구소 밖의 GitHub Pages 판은 서버가 없다. 서버가 그린 약속(`static-config` — 실을 지역·상류)이 있으면
  // 그 판이다. **KIGAM 키는 보는 사람이 각자 넣는다** — 이 브라우저(localStorage)에만 30 일 두고, "이 PC 에
  // 기억하지 않기" 면 탭 동안만(sessionStorage). 키는 KIGAM 에만 간다 — 우리 키는 이 판에 없다
  var STATIC = JSON.parse((document.getElementById("static-config") || {}).textContent || "null");
  var KEY_DAYS = 30;

  function readKey(name) {
    var slot = "gsm.key." + name;
    try {
      var held = JSON.parse(sessionStorage.getItem(slot) || "null");
      if (held && held.key) return held.key;
      held = JSON.parse(localStorage.getItem(slot) || "null");
      if (!held || !held.key) return "";
      if (Date.now() - (held.at || 0) > KEY_DAYS * 864e5) { localStorage.removeItem(slot); return ""; }
      held.at = Date.now();                       // 쓸 때마다 30 일을 새로 센다
      localStorage.setItem(slot, JSON.stringify(held));
      return held.key;
    } catch (e) { return staticKeys[name] || ""; }   // 사생활 모드 — 탭 동안만
  }
  var staticKeys = {};
  // 정적 판의 VWorld 는 페이지에 실린 키가 아니라 보는 사람이 넣은 키로 돈다(wetherilli 174) — 굽는 판에는 키가 없다
  if (STATIC) vworldKey = readKey("vworld");

  function writeKey(name, key, remember) {
    var slot = "gsm.key." + name;
    staticKeys[name] = key;
    try {
      localStorage.removeItem(slot);
      sessionStorage.removeItem(slot);
      if (key) (remember ? localStorage : sessionStorage).setItem(slot, JSON.stringify({ key: key, at: Date.now() }));
    } catch (e) { /* 저장소가 막혔다 — 탭 동안만 */ }
  }

  // ── 지역 ─────────────────────────────────────────────────────────
  //
  // 한국·그린란드·남극. **지역마다 레이어 목록·켠 레이어·보던 자리·색이 따로다**
  // (devlog 016). 한국이 기본이고, 다른 지역은 "추가 지역" 에서 더한다.
  // 레이어의 상류도 지역을 따라 갈린다 — 한국은 KIGAM, 그린란드는 GEUS.
  // VWorld 배경·주소 찾기·한국 좌표계는 한국에서만 뜻이 있어 한국에서만 보인다.
  //
  // **화면의 투영도 지역마다 다르다** (devlog 017). 한국은 웹 메르카토르(3857)
  // 그대로다. 극지는 메르카토르에서 잘리고 부풀어서 평사도법으로 본다 —
  // 그린란드는 NSIDC 북극 평사도법(3413), 남극은 남극 평사도법(3031).
  // `home` 은 처음 여는 범위다(그 투영의 미터). 없으면 `center`·`zoom` 을 쓴다.
  // `forgetOldView` — 투영이 바뀌기 전에 기억한 자리를 버린다. 남극은 "준비
  // 중" 이던 때 세종기지 둘레를 기억해 두었는데, 이제는 대륙 전체로 연다.
  var REGIONS = {
    korea: { title: "한국", proj: "EPSG:3857", center: [127.8, 36.2], zoom: 7, vworld: true,
             base: ["L_1M_Geology_Map", "L_250K_Geology_Map", "L_50K_Geology_Map",
                    "L_50K_Geology_Map_NoAttitude", "l_50k_geology_frame_latest", "G_tectonic"],
             first: "L_50K_Geology_Map" },
    greenland: { title: "그린란드", proj: "EPSG:3413", center: [-42.0, 72.0], zoom: 3, vworld: false,
                 home: [-750000, -3450000, 950000, -550000],
                 basemap: "eox_s2", places: "64.176, -51.736 · Nuuk",
                 base: ["grl_g500_lithostr_search", "lithologies"],
                 first: "grl_g500_lithostr_search",
                 // 화석 산지·화산·지진·고생태 산지는 북극해에 하나로 두고 빌린다 (wetherilli 185)
                 borrow: { arctic_ocean: ["earth"] } },
    antarctica: { title: "남극", proj: "EPSG:3031", center: [0, -90], zoom: 1, vworld: false,
                  home: [-2800000, -2400000, 2900000, 2500000],
                  basemap: "esri_antarctic", forgetOldView: true,
                  // 지명은 드로닝모드랜드(NPI)뿐이다 — 그래서 찾기 칸의 예도 거기 것 (wetherilli 096)
                  places: "-72.012, 2.535 · Troll",
                  // 좌표 칸의 예 — 남극점(가운데)은 예로 쓸모가 없어 세종기지를 든다 (021)
                  example: "-62.223, -58.787",
                  base: ["geomap_simple_geology", "geomap_chronostratigraphic",
                         "geomap_simple_lithology", "geomap_faults"],
                  first: "geomap_simple_geology" },
    // ── 얀마옌 (devlog 022) ──
    // NPI 의 1:25만 지질도를 모양째 받아 우리가 그린다. 섬이 길이 55 km 라 범위를
    // 섬 둘레로 잡는다. 3413 은 경도 -45° 가 위라, 북동-남서로 누운 섬이 거의
    // 남북으로 선다. `first` 가 여럿이면 처음 올 때 다 켠다 — 면·선·점이 한 장이다
    jan_mayen: { title: "얀마옌", proj: "EPSG:3413", center: [-8.4, 71.0], zoom: 9, vworld: false,
                 home: [1200000, -1704000, 1270000, -1634000],
                 basemap: "eox_s2",
                 base: ["janmayen:units", "janmayen:lines", "janmayen:vents"],
                 first: ["janmayen:units", "janmayen:lines", "janmayen:vents"],
                 borrow: { arctic_ocean: ["earth"] } },
    // ── 스발바르·북극 (devlog 021) ──
    // 스발바르는 노르웨이 극지연구소(NPI)의 지도 서버를 중계한다 — 타일은 3413 으로
    // 곧장 받는다(`npolarSource`). `places` 면 찾기 칸이 NPI 지명을 뒤진다.
    // **북극은 지역이 아니라 묶음이다.** `includes` 에 적은 지역의 레이어군을 한
    // 화면에 모은다 — 셋 다 3413 이라 섞어 켤 수 있다. 카탈로그에 없는 지역은
    // 저절로 빠진다. 보던 자리·켠 레이어·배경은 북극 탭이 따로 기억한다.
    svalbard: { title: "스발바르", proj: "EPSG:3413", center: [17.0, 78.5], zoom: 6, vworld: false,
                home: [890000, -739000, 1380000, -212000],
                basemap: "npi_sat", places: "78.223, 15.647 · Longyearbyen",
                base: ["npolar:svalbard_units", "npolar:svalbard_faults", "npolar:svalbard_paper"],
                first: "npolar:svalbard_units",
                // 북극해의 해저 지질(EMODnet)을 빌려 보인다 — 스발바르를 둘러싼 바다다. 묶음(`includes`)으로 만들면
                // KPDC 의 북극해 자료까지 따라와서, 상류 하나만 빌린다 (wetherilli 135). 지구 자료 점도 (wetherilli 185)
                borrow: { arctic_ocean: ["emodnet", "earth"] } },
    // ── 북극해 (devlog 076) ──
    // 스발바르·그린란드 탭 밖의 북극 — 지금은 KPDC 자료(아라온의 축치해·베링해 항해, 캐나다
    // 케임브리지베이, 시베리아·스칸디나비아 관측소)뿐이다. 3413 은 경도 -45° 가 아래라 베링 해협이
    // 왼쪽 위에 선다. 처음엔 베링해·축치해·보퍼트해를 연다. 바다라 배경은 해저 음영이 든 Blue Marble.
    // 지질도가 없어 "기본 지질도" 칸을 두지 않는다(`base` 가 비면 레이어군을 펼친다)
    arctic_ocean: { title: "북극해", proj: "EPSG:3413", center: [-160.0, 72.0], zoom: 3, vworld: false,
                    home: [-3100000, -1400000, -400000, 2600000],
                    basemap: "gibs_bm_n", example: "71.5, -156.8",
                    base: [],
                    first: "kopri:kpdc_ocean_arctic_ocean" },
    // ── 노르웨이·스웨덴·핀란드 (wetherilli 140·213) ──
    // NGU(노르웨이)·SGU(스웨덴)·GTK(핀란드)의 기반암 지질도를 중계한다. 스발바르와 같은 3413 이라 북극 묶음에 든다.
    // GTK·SGU 는 3413 을 그대로 받고, NGU 는 3413 을 그려 주지 않아 북극 람베르트(3575)로 받아 옮겨 그린다
    fennoscandia: { title: "노르웨이·스웨덴·핀란드", proj: "EPSG:3413", center: [18.0, 65.0], zoom: 4, vworld: false,
                    home: [1525000, -2371000, 3522000, -455000],
                    basemap: "eox_terrain", example: "69.649, 18.956 · Tromsø",
                    base: ["ngu:Berggrunn_nasjonal_bergartsenheter", "ngu:Berggrunn_regional_hovedbergarter",
                           "gtk:kalliopera_1m_kivilajiseurueet", "gtk:Litologiset_yksiköt_200k25132", "sgu:bedrock"],
                    first: ["ngu:Berggrunn_nasjonal_bergartsenheter", "gtk:kalliopera_1m_kivilajiseurueet", "sgu:bedrock"],
                    borrow: { arctic_ocean: ["earth"] } },
    arctic: { title: "북극", proj: "EPSG:3413", center: [-20.0, 76.0], zoom: 3, vworld: false,
              includes: ["greenland", "svalbard", "jan_mayen", "arctic_ocean", "fennoscandia"],
              home: [-612000, -3344000, 1380000, -212000],
              basemap: "eox_s2", places: "78.223, 15.647 · Longyearbyen",
              base: ["grl_g500_lithostr_search", "npolar:svalbard_units", "janmayen:units"],
              first: ["grl_g500_lithostr_search", "npolar:svalbard_units", "janmayen:units"] },
    // ── 일본·동아시아 (devlog 024) ──
    // 일본은 GSJ 의 심리스 지질도 V2 를 우리 서버가 z/x/y 타일로 중계한다(`gsjSource`).
    // 한국과 같은 3857 이라 **동아시아는 한국·일본을 한 화면에 모은 묶음이다** — 북극처럼
    // `includes` 로 모으고 DB 에는 없다. 다른 나라가 오면 `includes` 에 더한다.
    // 동아시아는 한국을 품으므로 VWorld 배경·주소 찾기·한국 좌표계·KIGAM 띠가 그대로 돈다
    japan: { title: "일본", proj: "EPSG:3857", center: [137.5, 37.0], zoom: 5, vworld: false,
             home: [14304555, 3503550, 16252646, 5716479],
             basemap: "gsi_pale", example: "35.361, 138.727", gsi: "35.361, 138.727 · 富士山",
             base: ["gsj:geology", "gsj:faults", "gsj:boundaries", "gsj:geology_level2"],
             first: "gsj:geology" },
    // ── 중국 (devlog 025) ──
    // USGS geo3al(1:500만)을 우리 서버가 셰이프파일에서 읽어 모양 한 덩이로 준다 — 얀마옌과
    // 같은 길(`kind: points`)이다. **연구실 내부용**이다(이용 조건이 재배포를 막는다).
    // 자료가 몽골·한반도·일본·인도차이나 일부까지 덮지만 탭은 중국에 맞춘다
    china: { title: "중국", proj: "EPSG:3857", center: [104.0, 35.0], zoom: 4, vworld: false,
             home: [8126323, 1920825, 15139451, 7170156],
             basemap: "eox_terrain", example: "39.904, 116.407",
             base: ["geo3al:age", "geo3al:rock"],
             first: "geo3al:age" },
    // ── 대만 (wetherilli 136) ──
    // 경제부 지질조사·광업관리중심(GSMMA)의 WMS 를 우리 서버가 중계한다. **상류가 4326 만 받아** 4326 격자로
    // 받고 OpenLayers 가 옮겨 그린다(`taiwanSource`). 누르면 지질운 API 의 지층(5만·25만)이 뜬다.
    // 범위는 펑후·진먼·마쭈까지 넣으면 넓어져 본섬에 맞춘다
    taiwan: { title: "대만", proj: "EPSG:3857", center: [120.9, 23.7], zoom: 7, vworld: false,
              home: [13277000, 2470000, 13617000, 2948000],
              basemap: "nlsc_grey", example: "25.033, 121.565",
              base: ["gsmma:geology_50k", "gsmma:geology_250k", "gsmma:geology_500k", "gsmma:geology_1m"],
              first: "gsmma:geology_50k" },
    eastasia: { title: "동아시아", proj: "EPSG:3857", center: [135.0, 37.5], zoom: 5, vworld: true,
                includes: ["korea", "japan", "china", "taiwan"],
                home: [13803617, 3763311, 16252646, 5388389],
                basemap: "eox_terrain",
                // 중국(geo3al, 025)은 한반도·일본까지 덮는 1:500만이라 늘 펼쳐 두되 켜지는 않는다
                base: ["L_1M_Geology_Map", "L_250K_Geology_Map", "gsj:geology", "gsj:faults", "gsmma:geology_500k",
                       "geo3al:age"],
                // 넓게 보는 탭이라 한국은 100만, 일본은 20만(가장 넓은 판)을 켠다
                first: ["L_1M_Geology_Map", "gsj:geology"] },
    // ── 영국·프랑스·유럽 (wetherilli 143) ──
    // 영국은 BGS 1:5만(줌 13 부터만 그린다), 프랑스는 BRGM 스캔·암상도를 중계한다. 넓게 볼 때는 EGDI 범유럽 1:100만이
    // 밑을 채운다 — 영국 지역에 두고 프랑스가 빌린다(`borrow`). **유럽은 묶음이다** — 둘을 한 화면에 모은다(DB 에는 없다)
    uk: { title: "영국", proj: "EPSG:3857", center: [-2.5, 54.5], zoom: 6, vworld: false,
          home: [-968000, 6420000, 223000, 8850000],
          basemap: "eox_terrain", example: "53.80, -1.55 · Leeds",
          base: ["egdi:GeologicUnitView_Age", "bgs:BGS.50k.Bedrock", "bgs:BGS.50k.Superficial.deposits"],
          first: ["egdi:GeologicUnitView_Age", "bgs:BGS.50k.Bedrock"],
          // 바다 — EMODnet 의 해저 퇴적물·기반암은 북극해 지역에 있다. 제4기 퇴적층·지질 사건은 영국 지역에 둔다 (wetherilli 176)
          borrow: { arctic_ocean: ["emodnet"] } },
    france: { title: "프랑스", proj: "EPSG:3857", center: [2.5, 46.5], zoom: 6, vworld: false,
              home: [-590000, 5060000, 1080000, 6650000],
              basemap: "eox_terrain", example: "48.857, 2.352 · Paris",
              base: ["brgm:SCAN_F_GEOL1M", "brgm:SCAN_F_GEOL250", "brgm:SCAN_H_GEOL50", "brgm:LITHO_1M_SIMPLIFIEE"],
              first: "brgm:SCAN_F_GEOL1M",
              // 범유럽 1:100만(EGDI)·유럽 바다(EMODnet)는 영국 지역에 들어 있다 — 그 상류의 레이어군만 빌린다
              borrow: { uk: ["egdi", "emodnet"], arctic_ocean: ["emodnet"] } },
    // ── 독일·스페인·아일랜드 (wetherilli 147) ──
    // BGR·IGME·GSI 를 중계한다. 판마다 그리는 줌이 좁아 넓게 볼 때는 EGDI 1:100만을 빌려 깐다. 아일랜드는 섬 전체 —
    // GSI 1:100만이 이미 섬 하나로 이어져 있고, 북아일랜드 1:25만(GSNI, BGS 서버)을 같은 레이어군에 둔다
    germany: { title: "독일", proj: "EPSG:3857", center: [10.4, 51.2], zoom: 6, vworld: false,
               home: [646000, 5975000, 1681000, 7381000],
               basemap: "eox_terrain", example: "51.31, 9.48 · Kassel",
               base: ["egdi:GeologicUnitView_Age", "bgr:gk1000:0", "bgr:guek250:7", "bgr:guek250:4"],
               first: ["egdi:GeologicUnitView_Age", "bgr:guek250:7"],
               borrow: { uk: ["egdi", "emodnet"], arctic_ocean: ["emodnet"] } },
    spain: { title: "스페인", proj: "EPSG:3857", center: [-3.7, 40.2], zoom: 6, vworld: false,
             home: [-1046000, 4287000, 490000, 5450000],
             basemap: "eox_terrain", example: "40.417, -3.704 · Madrid",
             base: ["igme:geologico1m:0", "igme:magna50:0", "igme:magna50:2"],
             first: "igme:geologico1m:0",
             borrow: { uk: ["egdi", "emodnet"], arctic_ocean: ["emodnet"] } },
    ireland: { title: "아일랜드", proj: "EPSG:3857", center: [-7.8, 53.4], zoom: 7, vworld: false,
               home: [-1191000, 6675000, -601000, 7460000],
               basemap: "eox_terrain", example: "53.35, -6.26 · Dublin",
               base: ["gsi:1m:IE_GSI_GSNI_Bedrock_Geology_1M_IE32_ITM", "gsi:100k:IE_GSI_Bedrock_Geology_100K_IE26_ITM",
                      "gsni:5"],
               first: "gsi:1m:IE_GSI_GSNI_Bedrock_Geology_1M_IE32_ITM",
               borrow: { uk: ["egdi", "emodnet"], arctic_ocean: ["emodnet"] } },
    // ── 이탈리아·포르투갈·스위스 (wetherilli 211) ──
    // ISPRA 1:100만·1:10만, LNEG 1:50만, swisstopo 1:50만·GeoCover. EGDI 1:100만(과 바다를 낀 둘은 EMODnet)은 영국에서 빌린다
    italy: { title: "이탈리아", proj: "EPSG:3857", center: [12.5, 42.0], zoom: 6, vworld: false,
             home: [723577, 4369641, 2070543, 5958412],
             basemap: "eox_terrain", example: "41.902, 12.496 · Roma",
             base: ["ispra:1m:0", "ispra:100k:1"],
             first: "ispra:1m:0",
             borrow: { uk: ["egdi", "emodnet"], arctic_ocean: ["emodnet"] } },
    portugal: { title: "포르투갈", proj: "EPSG:3857", center: [-8.0, 39.6], zoom: 7, vworld: false,
                home: [-1068667, 4425177, -679049, 5190986],
                basemap: "eox_terrain", example: "38.722, -9.139 · Lisboa",
                base: ["lneg:500k:2", "lneg:500k:4"],
                first: "lneg:500k:2",
                borrow: { uk: ["egdi", "emodnet"], arctic_ocean: ["emodnet"] } },
    switzerland: { title: "스위스", proj: "EPSG:3857", center: [8.2, 46.8], zoom: 8, vworld: false,
                   home: [656785, 5748357, 1168855, 6073646],
                   basemap: "eox_terrain", example: "46.948, 7.447 · Bern",
                   base: ["swisstopo:geologische_karte", "swisstopo:geocover"],
                   first: "swisstopo:geologische_karte",
                   borrow: { uk: ["egdi"] } },
    // ── 남미 (wetherilli 188·191) ──
    // 나라 탭 둘(콜롬비아·브라질)과 묶음 "남미". SGC 가 내는 남미 1:500만(CGMW 2019)이 대륙 바탕이다 — 콜롬비아 지역에 두고
    // 브라질이 그 레이어군만 빌린다(`borrow` 의 `sgc:sa:` — 이름 앞머리로). 칠레·페루처럼 나라 판이 없는 곳은 묶음에서 1:500만이 메운다
    colombia: { title: "콜롬비아", proj: "EPSG:3857", center: [-73.5, 4.5], zoom: 6, vworld: false,
                home: [-8850000, -479000, -7436000, 1414000],
                basemap: "eox_terrain", example: "4.711, -74.072 · Bogotá",
                base: ["sgc:sa:8", "sgc:co:3"],
                first: "sgc:co:3" },
    brazil: { title: "브라질", proj: "EPSG:3857", center: [-52.0, -14.0], zoom: 4, vworld: false,
              home: [-8260000, -4029000, -3852000, 602000],
              basemap: "eox_terrain", example: "-15.79, -47.88 · Brasília",
              base: ["sgc:sa:8", "sgb:2500k", "sgb:1m", "sgb:250k"],
              first: "sgb:2500k",
              borrow: { colombia: ["sgc:sa:"] } },
    // 페루(wetherilli 195) — INGEMMET 1:5만·1:10만 통합판을 REST 타일 캐시로. 남미 1:500만은 브라질처럼 빌린다
    peru: { title: "페루", proj: "EPSG:3857", center: [-75.0, -9.5], zoom: 6, vworld: false,
            home: [-9084000, -2108000, -7637000, 0],
            basemap: "eox_terrain", example: "-12.046, -77.043 · Lima",
            base: ["sgc:sa:8", "ingemmet:100k", "ingemmet:50k"],
            first: "ingemmet:50k",
            borrow: { colombia: ["sgc:sa:"] } },
    // 아르헨티나 SEGEMAR·우루과이 DINAMIGE (wetherilli 196) — 브라질처럼 남미 1:500만만 콜롬비아에서 빌린다
    argentina: { title: "아르헨티나", proj: "EPSG:3857", center: [-65.0, -38.0], zoom: 4, vworld: false,
                 home: [-8250000, -7400000, -5900000, -2450000],
                 basemap: "eox_terrain", example: "-34.60, -58.38 · Buenos Aires",
                 base: ["sgc:sa:8", "segemar:e2.5M.UnidadesGeologicas", "segemar:e250K_UnidadGeologica"],
                 first: "segemar:e2.5M.UnidadesGeologicas",
                 borrow: { colombia: ["sgc:sa:"] } },
    uruguay: { title: "우루과이", proj: "EPSG:3857", center: [-56.0, -32.6], zoom: 7, vworld: false,
               home: [-6510000, -4170000, -5920000, -3500000],
               basemap: "eox_terrain", example: "-34.90, -56.19 · Montevideo",
               base: ["sgc:sa:8", "dinamige:0"],
               first: "dinamige:0",
               borrow: { colombia: ["sgc:sa:"] } },
    // 에콰도르(wetherilli 198) — IIGE 일반 지질도. 남부는 거의 다, 북부는 도폭 조각만이라 1:500만이 밑을 채운다
    ecuador: { title: "에콰도르", proj: "EPSG:3857", center: [-78.5, -1.6], zoom: 7, vworld: false,
               home: [-9039000, -568000, -8360000, 167000],
               basemap: "eox_terrain", example: "-0.180, -78.468 · Quito",
               base: ["sgc:sa:8", "iige:geologia_general"],
               first: ["sgc:sa:8", "iige:geologia_general"],
               borrow: { colombia: ["sgc:sa:"] } },
    // ── 캐나다 (wetherilli 204) ──
    // NRCan 1:500만(Wheeler)을 바탕에, 온타리오 OGS 1:25만을 위에. 화면은 캐나다 람베르트(3978) — 서경 95° 가 위라 나라가 반듯하고
    // 북극 섬이 부풀지 않는다. 미국·멕시코가 들어오면 묶음 "북미"(`north_america`)가 이 탭을 품는다(유럽·남미와 같은 꼴)
    canada: { title: "캐나다", proj: "EPSG:3978", center: [-96.0, 60.0], zoom: 4, vworld: false,
              home: [-2400000, -900000, 3100000, 4600000],
              basemap: "eox_terrain", example: "45.42, -75.70 · Ottawa",
              base: ["nrcan:wheeler", "ogs:3", "ogs:1", "sigeom:generale", "sigeom:regionale", "ygs:47"],
              first: "nrcan:wheeler" },
    // 북미 묶음(wetherilli 210) — 캐나다·미국·멕시코를 캐나다 람베르트(3978) 한 화면에 모은다. 알래스카와 북극 섬이 부풀지 않고 멕시코(북위
    // 15° 남짓)도 크게 비틀리지 않는다. 처음 켜는 것은 나라마다 넓게 봐도 그려지는 판 하나 — 캐나다 1:500만·미국 SGMC·멕시코 1:25만.
    // 셋은 국경에서만 겹친다. 주 판(온타리오·퀘벡·유콘)과 알래스카는 목록에서 켠다
    north_america: { title: "북미", proj: "EPSG:3978", center: [-100.0, 45.0], zoom: 3, vworld: false,
                     includes: ["canada", "usa", "mexico"],
                     home: [-3995000, -4275000, 3052000, 3777000],
                     basemap: "eox_terrain", example: "45.42, -75.70 · Ottawa",
                     base: ["nrcan:wheeler", "mrdata:sgmc2:sgmc2", "sgm:8", "mrdata:sim3340:units"],
                     first: ["nrcan:wheeler", "mrdata:sgmc2:sgmc2", "sgm:8"] },
    // 남미 묶음 — 레이어군은 북에서 남으로(콜롬비아·에콰도르·페루·브라질·우루과이·아르헨티나) 선다. **처음 켜는 것**은 대륙 바탕
    // 1:500만을 맨 밑에 두고, 나라마다 넓게 봐도 빨리 그려지는 판 하나씩을 그 위에 얹는다 — 브라질 1:250만(1:100만은 줌 6 부터)·
    // 아르헨티나 1:250만·페루 1:5만(타일 캐시)·콜롬비아 1:50만·우루과이 1:50만. 나라 판끼리는 국경에서만 겹친다. 에콰도르는 넓은 줌의
    // 한 장이 7 초를 넘고 북부가 비어 처음에는 켜지 않는다 (wetherilli 198)
    south_america: { title: "남미", proj: "EPSG:3857", center: [-60.0, -15.0], zoom: 3, vworld: false,
                     includes: ["colombia", "ecuador", "peru", "brazil", "uruguay", "argentina"],
                     home: [-9128198, -7558416, -3784863, 1516914],
                     basemap: "eox_terrain", example: "4.711, -74.072 · Bogotá",
                     base: ["sgc:sa:8", "sgc:co:3", "iige:geologia_general", "ingemmet:50k", "sgb:2500k", "dinamige:0",
                            "segemar:e2.5M.UnidadesGeologicas"],
                     first: ["sgc:sa:8", "sgb:2500k", "segemar:e2.5M.UnidadesGeologicas", "ingemmet:50k", "sgc:co:3",
                             "dinamige:0"] },
    // ── 아프리카 (wetherilli 207) ──
    // 대륙 판(CGMW–BRGM 1:1000만)이 바탕이라 탭 하나다. 나라 판(남아공 CGS 따위)이 붙으면 남미처럼 나라 탭과 묶음으로 가른다(188 §3).
    // BGS 지하수 지도책의 나라별 1:500만 암상(38 나라)을 얹는다
    africa: { title: "아프리카", proj: "EPSG:3857", center: [20.0, 2.0], zoom: 3, vworld: false,
              home: [-2900000, -4300000, 6000000, 4600000],
              basemap: "eox_terrain", example: "-1.29, 36.82 · Nairobi",
              base: ["cgmw:AFR_CGMW_BRGM_10M_GeologicUnits", "cgmw:AFR_CGMW_BRGM_10M_Faults", "aga:geology", "cgs:geology_1m",
                     "gsn:NAM_GSN_1M_BLS"],
              first: "cgmw:AFR_CGMW_BRGM_10M_GeologicUnits",
              // 나라 판(남아공·나미비아, wetherilli 209)은 제 나라만 덮는다 — 묶음 탭처럼 범위 밖 타일을 묻지 않는다
              clip: true },
    // 호주(wetherilli 212) — Geoscience Australia 지표 지질도. 레이어 하나가 1:250만·1:100만을 함께 부르고 상류가 축척에 맞는 판을
    // 그린다. 화면은 3857 — GA 가 3577(호주 알베르스)을 그려 주지 않고 남위 10–44° 라 많이 부풀지 않는다
    australia: { title: "호주", proj: "EPSG:3857", center: [134.0, -26.0], zoom: 4, vworld: false,
                 home: [12523000, -5465000, 17143000, -1006000],
                 basemap: "eox_terrain", example: "-31.95, 115.86 · Perth",
                 base: ["ga:lithostratigraphy", "ga:age", "ga:lithology", "ga:faults"],
                 first: "ga:lithostratigraphy" },
    europe: { title: "유럽", proj: "EPSG:3857", center: [0.0, 50.0], zoom: 5, vworld: false,
              includes: ["uk", "ireland", "france", "germany", "spain", "portugal", "italy", "switzerland"],
              // 이탈리아(풀리아·시칠리아)까지 — 동쪽을 넓혔다 (wetherilli 211)
              home: [-1225000, 4232000, 2100000, 8626000],
              basemap: "eox_terrain",
              base: ["egdi:GeologicUnitView_Age", "bgs:BGS.50k.Bedrock", "brgm:SCAN_F_GEOL1M"],
              first: "egdi:GeologicUnitView_Age",
              borrow: { arctic_ocean: ["emodnet"] } },
    // ── 북미 (wetherilli 205·210) ──
    // 미국 — USGS SGMC(본토 48 주, 주 지질도 합본)와 알래스카 SIM 3340. 공공 도메인. 화면은 캐나다와 같은 캐나다 람베르트(3978) —
    // 3857 이면 알래스카가 본토만큼 부푼다. 레이어는 3857 로 받아 화면이 옮겨 그린다(카탈로그 행의 `projection`, wetherilli 210)
    usa: { title: "미국", proj: "EPSG:3978", center: [-105.0, 45.0], zoom: 3, vworld: false,
           home: [-4204000, -2746000, 3309000, 3650000],
           basemap: "eox_terrain", example: "39.74, -104.99 · Denver",
           base: ["mrdata:sgmc2:sgmc2", "mrdata:sgmc2:sgmc2structure", "mrdata:sim3340:units"],
           first: "mrdata:sgmc2:sgmc2" },
    // 멕시코(wetherilli 206) — SGM 1:25만(전국)·1:5만(광업 지구). WMS 가 막혀 서버가 REST export 로 받는다
    mexico: { title: "멕시코", proj: "EPSG:3857", center: [-102.0, 23.5], zoom: 5, vworld: false,
              home: [-13191000, 1592000, -9629000, 3881000],
              basemap: "eox_terrain", example: "22.77, -102.58 · Zacatecas",
              base: ["sgm:8", "sgm:6", "sgm:7"],
              first: "sgm:8" },
  };
  if (STATIC) {
    // 정적 판이 싣지 않은 지역은 탭에서 뺀다. 묶음은 품은 지역 가운데 실린 것만 남기고, 하나도 없으면 뺀다
    Object.keys(REGIONS).forEach(function (key) {
      var spec = REGIONS[key];
      if (spec.includes) {
        spec.includes = spec.includes.filter(function (k) { return STATIC.regions.indexOf(k) >= 0; });
        if (!spec.includes.length) delete REGIONS[key];
      } else if (STATIC.regions.indexOf(key) < 0) {
        delete REGIONS[key];
      }
    });
  }
  var region = "korea";

  //: 남극 GeoMAP 타일의 격자. **우리 서버(`geomap/`)가 이 격자로 굽는다** —
  //  한 글자라도 다르면 타일이 어긋난다. 원점은 왼쪽 위, 256 픽셀, 줌 0 의
  //  해상도가 폭/256 이고 줌마다 반이다. 남극 화면(3031)의 투영 범위도 이것으로
  //  잡아, 화면의 줌 단계가 GeoMAP 타일의 줌과 같게 했다.
  var GEOMAP_GRID = {
    extent: [-3333134.0276, -3333134.0276, 3333134.0276, 3333134.0276],
    tileSize: 256,
    maxZoom: 18,
  };
  //: GeoMAP 타일 주소. `{layer}` 는 카탈로그의 레이어명이다. 굽는 쪽과 맞춘다
  var GEOMAP_TILE_URL = "geomap/{layer}/{z}/{x}/{y}.png";

  // 평사도법 둘을 OpenLayers 에 알린다. proj4 가 없으면(파일을 못 받았으면)
  // 극지도 메르카토르로 돈다 — 잘려도 빈 화면보다 낫다 (`regionProj`).
  if (window.proj4 && ol.proj.proj4) {
    proj4.defs("EPSG:3413", "+proj=stere +lat_0=90 +lat_ts=70 +lon_0=-45 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs");
    proj4.defs("EPSG:3031", "+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs");
    ol.proj.proj4.register(proj4);
    // 3413 의 범위는 NASA GIBS 의 극지 격자와 같게 — 배경의 줌이 화면과 맞는다
    ol.proj.get("EPSG:3413").setExtent([-4194304, -4194304, 4194304, 4194304]);
    ol.proj.get("EPSG:3031").setExtent(GEOMAP_GRID.extent);
    // UTM 33N — 스발바르 배경(NPI 의 위성·지형도 타일)이 이 격자로 구워져 있다.
    // OpenLayers 가 3413 화면에 옮겨 그린다 (devlog 021)
    proj4.defs("EPSG:25833", "+proj=utm +zone=33 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs");
    // 북극 람베르트 등적 유럽판 — NGU 지질도가 3413 을 그려 주지 않아 이것으로 받는다 (wetherilli 140).
    // 범위는 적도까지(극에서 약 9 000 km) — 타일 격자가 이 범위로 선다
    proj4.defs("EPSG:3575", "+proj=laea +lat_0=90 +lon_0=10 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs");
    // 중부원점(GRS80) — phyloserver 의 한반도 지질도가 카카오맵 격자로 잘려 있다 (devlog 026)
    proj4.defs("EPSG:5181", "+proj=tmerc +lat_0=38 +lon_0=127 +k=1 +x_0=200000 +y_0=500000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs");
    // UTM-K(GRS80) — 한반도 지질도 음영판을 이 격자로 잘라 둔다 (devlog 027)
    proj4.defs("EPSG:5179", "+proj=tmerc +lat_0=38 +lon_0=127.5 +k=0.9996 +x_0=1000000 +y_0=2000000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs");
    ol.proj.proj4.register(proj4);
    ol.proj.get("EPSG:3575").setExtent([-9009964.76, -9009964.76, 9009964.76, 9009964.76]);
    // 캐나다 람베르트(NAD83 / Canada Atlas Lambert, wetherilli 204) — 캐나다 탭의 화면. 3857 은 북극 섬을 크게 부풀리고 3413 은
    // 서경 45° 가 위라 캐나다가 50° 기운다. 범위는 3857 과 같은 너비로 — 줌 번호가 같은 해상도다(서버의 `tilegrid.EXTENT` 와 같다)
    proj4.defs("EPSG:3978", "+proj=lcc +lat_0=49 +lon_0=-95 +lat_1=49 +lat_2=77 +x_0=0 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs");
    ol.proj.proj4.register(proj4);
    ol.proj.get("EPSG:3978").setExtent([-20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244]);
  }

  //: 남극은 카탈로그에 레이어군(GeoMAP)이 없을 때만 "준비 중" 이다 — GeoMAP
  //  파일이 없는 자리에 띄운 서버가 그렇다.
  if (REGIONS.antarctica) REGIONS.antarctica.pending = !catalog.some(function (g) {
    return g.region === "antarctica" && g.layers.length;
  });
  //: 스발바르·북극·일본·중국도 카탈로그에 레이어군이 하나도 없으면 "준비 중" 이다 (씨앗을 안 넣은 DB)
  ["svalbard", "arctic", "arctic_ocean", "fennoscandia", "japan", "china", "taiwan", "uk", "france", "germany", "spain", "ireland", "europe", "colombia", "brazil", "peru", "argentina", "uruguay", "ecuador", "south_america", "canada", "africa", "italy", "portugal", "switzerland", "usa", "mexico", "north_america", "australia"].forEach(function (key) {
    if (!REGIONS[key]) return;            // 정적 판이 싣지 않은 지역
    var keys = REGIONS[key].includes || [key];
    REGIONS[key].pending = !catalog.some(function (g) {
      return keys.indexOf(g.region) >= 0 && g.layers.length;
    });
  });

  /** 지금 지역의 화면 투영. 등록되지 않았으면 메르카토르. */
  function regionProj(key) {
    var code = REGIONS[key || region].proj || "EPSG:3857";
    return ol.proj.get(code) ? code : "EPSG:3857";
  }

  function viewProj() { return map.getView().getProjection(); }
  function isMercator() { return viewProj().getCode() === "EPSG:3857"; }

  /** 지도 좌표 <-> 위경도. `ol.proj.toLonLat` 은 투영을 안 주면 3857 로 여긴다 —
   *  극지 화면에서 그대로 부르면 엉뚱한 곳이 나온다. 그래서 늘 이 둘을 거친다. */
  function toLL(coordinate) { return ol.proj.toLonLat(coordinate, viewProj()); }
  function fromLL(lonlat) { return ol.proj.fromLonLat(lonlat, viewProj()); }

  /** 이 해상도가 **3857 로 보았다면 몇 줌인가.** 점을 작게 그리는 문턱(6)·이름표
   *  문턱(11)은 3857 화면에서 맞춘 값이다. 극 평사도법 화면의 줌은 투영 범위 한 장이
   *  줌 0 이라 같은 땅을 두세 단계 낮게 읽는다 — 그대로 쓰면 극지에서만 이름표가
   *  늦게 뜬다. 극 평사도법의 한 단위는 참축척 위도(70°N·71°S) 둘레에서 거의 땅의
   *  1 m 이고, 3857 은 위도 φ 에서 땅을 1/cos φ 배 부풀려 그린다. 그래서 화면 한가운데
   *  위도로 3857 해상도를 되짚는다. 극점을 가운데 둔 남극에서는 80° 로 자른다 */
  var MERC_RES0 = 156543.03392804097;
  function mercZoom(resolution) {
    var view = map.getView();
    if (isMercator()) return view.getZoomForResolution(resolution) || 0;
    var lat = Math.min(Math.abs(toLL(view.getCenter())[1]), 80);
    return Math.log2(MERC_RES0 * Math.cos(lat * Math.PI / 180) / resolution);
  }
  var addedRegions = ["korea"];
  /** 탭 줄에 늘 서는 지역 — 나머지는 "그 외" 로 접는다 (wetherilli 214) */
  var PINNED = ["korea", "arctic", "antarctica"];

  // ── 공유 링크 (wetherilli 189) ──
  // 주소의 해시(`share.js`)로 들어오면 그 지역·자리·레이어·배경을 덧층에 깔고 연다. 아래의 기억(지역·자리·레이어·배경)은 모두
  // `STATE` 를 거친다 — 링크로 연 동안에는 덧층에만 쓰고 그 사람의 localStorage 는 건드리지 않는다. 실리지 않은 지역(정적 판)은
  // 링크를 버리고 늘 하던 대로 연다. 레이어·배경은 되살릴 때 카탈로그에 없으면 조용히 건너뛴다(`restoreState`·`savedBasemap`)
  var SHARED = window.GSMShare ? GSMShare.read() : null;
  if (SHARED && !(SHARED.r && REGIONS[SHARED.r])) SHARED = null;
  var STATE = window.GSMShare ? GSMShare.store(SHARED && sharedSeed(SHARED)) : null;
  function sharedSeed(q) {
    var r = q.r, key = function (name) { return r === "korea" ? name : name + "." + r; };
    var seed = { "gsm.region": r };
    try {
      var kept = JSON.parse(localStorage.getItem("gsm.regions") || "[]") || [];
      seed["gsm.regions"] = JSON.stringify(kept.indexOf(r) >= 0 || r === "korea" ? kept : kept.concat([r]));
    } catch (e) { seed["gsm.regions"] = JSON.stringify(r === "korea" ? [] : [r]); }
    var c = (q.c || "").split(",").map(Number);
    if (c.length === 2 && isFinite(c[0]) && isFinite(c[1]) && isFinite(+q.z)) {
      seed[key("gsm.view")] = JSON.stringify({ lon: c[0], lat: c[1], zoom: +q.z, proj: "EPSG:" + (q.p || "3857") });
    }
    seed[key("gsm.layers")] = JSON.stringify(GSMShare.layers(q.l));
    if (q.b) seed[key("gsm.basemap")] = q.b;
    return seed;
  }
  function stored(key) {
    if (STATE) return STATE.get(key);
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function store(key, value) {
    if (STATE) return STATE.set(key, value);
    try { localStorage.setItem(key, value); } catch (e) { /* 사생활 모드 */ }
  }
  function unstore(key) {
    if (STATE) return STATE.remove(key);
    try { localStorage.removeItem(key); } catch (e) { /* 사생활 모드 */ }
  }
  /** 지금 보는 것의 링크 — 지역·가운데·줌·투영·켠 레이어(위가 앞)·배경. 점묶음·개인 레이어는 그 브라우저의 것이라 싣지 않는다 */
  function shareLink() {
    var view = map.getView(), center = toLL(view.getCenter());
    var rows = active.filter(function (e) { return byName[e.name] && byName[e.name].upstream !== "geonavi"; });
    return GSMShare.link({ r: region, c: center[0].toFixed(5) + "," + center[1].toFixed(5), z: view.getZoom().toFixed(2),
                           p: view.getProjection().getCode().replace("EPSG:", ""), l: GSMShare.pack(rows),
                           b: document.getElementById("basemap").value });
  }

  function stateKey(name) {
    // 한국은 예전 열쇠 그대로 — 이 판 전에 기억해 둔 것을 잃지 않는다
    return region === "korea" ? name : name + "." + region;
  }

  /** 지금 지역이 품는 지역들. 북극(`includes`)이면 그린란드·스발바르·얀마옌이다. */
  function regionKeys(key) {
    return REGIONS[key || region].includes || [key || region];
  }

  /** 빌려 오는 목록(`borrow` 의 한 칸)에 이 레이어가 드나 — 상류 이름(`egdi`)이거나, `:` 로 끝나는 레이어 이름의 앞머리(`sgc:sa:`)다.
   *  앞머리는 한 상류의 판 하나만 빌릴 때 쓴다 — 브라질이 콜롬비아 지역의 SGC 가운데 남미 1:500만만 빌린다 (wetherilli 191) */
  function borrows(from, upstream, name) {
    return !!from && from.some(function (f) {
      return f === upstream || (f.slice(-1) === ":" && String(name || "").indexOf(f) === 0);
    });
  }

  /** 지금 지역의 레이어군. 묶음 지역이면 `includes` 차례로 모은다. */
  function regionCatalog() {
    var keys = regionKeys();
    var borrow = REGIONS[region].borrow || {};
    // 빌려 온 레이어군(`borrow`)은 제 지역의 것 뒤에 선다
    var rank = function (g) { var i = keys.indexOf(g.region || "korea"); return i >= 0 ? i : keys.length; };
    return catalog.filter(function (g) {
      if (keys.indexOf(g.region || "korea") >= 0) return true;
      var from = borrow[g.region];
      return g.layers.some(function (l) { return borrows(from, l.upstream, l.name); });
    }).sort(function (a, b) { return rank(a) - rank(b); });
  }
  var pointsets = JSON.parse(document.getElementById("pointset-data").textContent || "[]");

  //: 끈 점묶음의 번호 — 이 브라우저에 둔다(P02). 서버의 `visible` 을 쓰지 않는 것은
  //  계정이 없는 뷰어라 한 사람이 끄면 모두에게 꺼지기 때문이다. 켠 것이 아니라 끈 것을
  //  적어 새로 올린 점묶음은 켜진 채 뜬다. 3D(`map3d.js`)가 같은 열쇠를 읽고 쓴다
  var PS_OFF_KEY = "gsm.pointsets.off";
  function pointsetsOff() {
    try { return JSON.parse(localStorage.getItem(PS_OFF_KEY) || "[]") || []; } catch (e) { return []; }
  }
  function setPointsetOff(id, off) {
    var ids = pointsetsOff().filter(function (x) { return x !== id; });
    if (off) ids.push(id);
    try { localStorage.setItem(PS_OFF_KEY, JSON.stringify(ids)); } catch (e) { /* 사생활 모드 */ }
  }
  (function () {
    var off = pointsetsOff();
    pointsets.forEach(function (ps) { ps.visible = off.indexOf(ps.id) < 0; });
  })();

  //: 레이어를 켤 때의 투명도. 배경지도를 깔고 보는 것이 예사이므로
  //  처음부터 밑이 비치게 둔다. 100% 로 두면 배경을 덮어서, 사람이
  //  슬라이더를 찾아 내려야 배경이 보인다.
  var DEFAULT_OPACITY = 0.5;

  //: 5만 지질도 도폭 하나가 덮는 범위. 경도 15분 × 위도 10분이다.
  //  좌표를 찍어 이동할 때 이만큼이 화면에 들어오게 맞춘다 — "도폭 한 장"
  //  이 이 축척을 쓰는 사람의 눈금이라, 줌 단계 숫자보다 뜻이 분명하다.
  var SHEET_LON = 15 / 60;
  var SHEET_LAT = 10 / 60;

  var map, popupOverlay, pointLayerGroup, personalGroup;
  var tempSource, tempLayer, measureSource, measureLayer, foundSource, foundLayer;
  var rangeSource, rangeLayer, rangeSeq = 0;
  var mode = "info", drawInteraction = null, tempSeq = 0, lastMeasure = "";
  var active = [];        // 켠 레이어. 앞이 위다 (화면에서 앞에 그려진다)
  var byName = {};        // 레이어명 -> 카탈로그 행
  var pointLayers = {};   // 점묶음 id -> ol 레이어
  var useDms = false;

  var regionOfLayer = {};  // 레이어명 -> 지역 (북극 탭이 레이어 앞에 지역을 적는다)
  catalog.forEach(function (group) {
    group.layers.forEach(function (layer) {
      byName[layer.name] = layer;
      regionOfLayer[layer.name] = group.region || "korea";
    });
  });

  /** 묶음 지역(북극)에서는 레이어 이름 앞에 지역을 적는다 — 그린란드에도 스발바르에도
   *  "지질 단위" 가 있다. 제 지역 탭에서는 이름만. */
  function regionPrefix(name) {
    return wherePrefix(regionOfLayer[name], byName[name] && byName[name].upstream, name);
  }

  /** 묶음 탭에서 레이어(군) 앞에 붙일 지역. 묶음의 다른 지역이 빌려 쓰는 상류(`borrow`)면 붙이지 않는다 —
   *  유럽의 EGDI 는 영국 지역에 두었을 뿐 프랑스도 쓰는 판이다 (wetherilli 143) */
  function wherePrefix(where, upstream, name) {
    var keys = REGIONS[region].includes;
    if (!keys || !where || !REGIONS[where]) return "";
    var shared = keys.some(function (k) {
      var from = k !== where && (REGIONS[k].borrow || {})[where];
      return borrows(from || null, upstream, name);
    });
    return shared ? "" : T(REGIONS[where].title) + " · ";
  }

  function layerTitle(name) {
    var row = byName[name];
    return regionPrefix(name) + (row ? row.title : name);
  }

  // ── 지도 ────────────────────────────────────────────────────────

  function wmsSource(name) {
    return new ol.source.TileWMS({
      url: BASE + "wms",
      params: { LAYERS: name, TILED: true, FORMAT: "image/png", TRANSPARENT: true },
      transition: 0,
      // **WMS 는 언제나 3857 로 받는다.** 극지 화면이면 OpenLayers 가 옮겨
      // 그린다. GEUS 의 50만 지질도가 3413 을 안 주고(2026-09-27), 한 상류의
      // 타일을 두 격자로 받으면 캐시가 둘로 갈린다 (017)
      projection: "EPSG:3857",
      // 상류 부하를 줄인다. 타일 하나가 작을수록 요청이 는다.
      tileGrid: ol.tilegrid.createXYZ({ tileSize: 512 }),
      attributions: sourceNote(name) || undefined,
    });
  }

  /** WMS 레이어의 속성 주소. 서버의 /featureinfo/ 로 돌린다 — 인증키는 서버가 붙인다.
   *  화면과 타일의 투영이 달라도 OpenLayers 가 누른 자리를 타일 투영으로 옮겨 준다. */
  function wmsInfoUrl(source, coordinate, view) {
    var url = source.getFeatureInfoUrl(
      coordinate, view.getResolution(), view.getProjection(),
      { INFO_FORMAT: "application/json", FEATURE_COUNT: 5 });
    return url ? url.replace(BASE + "wms", BASE + "featureinfo/") : null;
  }

  /** 남극 GeoMAP — 우리 서버가 미리 구운 3031 타일 (`GEOMAP_GRID`, devlog 018).
   *  주소·출처는 카탈로그 행(`tiles`·`attribution`)이 준다. */
  function geomapSource(name) {
    var row = byName[name] || {};
    var resolutions = [];
    var width = GEOMAP_GRID.extent[2] - GEOMAP_GRID.extent[0];
    // 잘라 둔 것(IBCSO 자료 출처, 071)은 줌 6 까지다 — 그 위는 OpenLayers 가 늘린다.
    // 정적 판은 구운 줌까지만 있다(`bake_static`) — 그 너머도 늘린다 (wetherilli 165)
    var top = (STATIC && staticBaked("geomap")[name]) || row.maxZoom || GEOMAP_GRID.maxZoom;
    for (var z = 0; z <= top; z++) {
      resolutions.push(width / GEOMAP_GRID.tileSize / Math.pow(2, z));
    }
    return new ol.source.XYZ({
      url: BASE + (row.tiles || GEOMAP_TILE_URL.replace("{layer}", encodeURIComponent(name))),
      projection: "EPSG:3031",
      tileGrid: new ol.tilegrid.TileGrid({
        extent: GEOMAP_GRID.extent,
        origin: [GEOMAP_GRID.extent[0], GEOMAP_GRID.extent[3]],
        resolutions: resolutions,
        tileSize: GEOMAP_GRID.tileSize,
      }),
      transition: 0,
      attributions: row.attribution || undefined,
    });
  }

  /** GeoMAP 의 속성 주소. 구운 타일이라 OpenLayers 가 WMS 주소를 지어 주지 않는다 —
   *  누른 자리를 가운데 둔 101 픽셀 네모를 WMS 꼴로 적어 `/featureinfo/` 에 묻는다.
   *  서버(`geomap.click_point`)가 BBOX·I·J 에서 3031 의 한 점과 둘레를 셈한다. */
  function geomapInfoUrl(source, coordinate, view) {
    var name = source.get("gsmName");
    var proj = view.getProjection();
    var p = ol.proj.transform(coordinate, proj, "EPSG:3031");
    var res = view.getResolution();
    if (proj.getCode() !== "EPSG:3031") {
      res = ol.proj.getPointResolution(proj, res, coordinate) /
            ol.proj.getPointResolution("EPSG:3031", 1, p);
    }
    var half = 50.5 * res;
    var q = new URLSearchParams({
      SERVICE: "WMS", VERSION: "1.3.0", REQUEST: "GetFeatureInfo",
      LAYERS: name, QUERY_LAYERS: name, CRS: "EPSG:3031",
      BBOX: [p[0] - half, p[1] - half, p[0] + half, p[1] + half].join(","),
      WIDTH: 101, HEIGHT: 101, I: 50, J: 50,
      INFO_FORMAT: "application/json", FEATURE_COUNT: 5,
    });
    return BASE + "featureinfo/?" + q.toString();
  }

  /** IBCSO 자료 출처(TID)의 속성 주소 — 누른 자리의 위경도로 묻는다(`ibcso/info/`, 071). */
  function ibcsoInfoUrl(source, coordinate) {
    var ll = toLL(coordinate);
    return BASE + "ibcso/info/?" + new URLSearchParams({
      lat: ll[1].toFixed(6), lon: ll[0].toFixed(6),
    }).toString();
  }

  /** 노르웨이 극지연구소(NPI) — 서버의 `/wms/` 가 NPI 지도 서버의 `export` 로 옮겨
   *  받는다(`npolar.py`). **다른 WMS 와 달리 3857 이 아니라 지역의 투영(3413·3031)으로
   *  받는다** — NPI 지도는 축척에 따라 1:25만과 1:75만을 갈아 끼우는데, 3857 로 물으면
   *  북위 78° 에서 축척이 다섯 배 부풀어 1:25만이 한참 늦게 뜬다 (devlog 021).
   *  투영은 카탈로그 행(`projection`)이 준다. proj4 를 못 읽었으면 3857 로 받는다. */
  function npolarSource(name) {
    var row = byName[name] || {};
    var code = row.projection && ol.proj.get(row.projection) ? row.projection : "EPSG:3857";
    return new ol.source.TileWMS({
      url: BASE + "wms",
      params: { LAYERS: name, TILED: true, FORMAT: "image/png", TRANSPARENT: true },
      transition: 0,
      projection: code,
      // NPI 는 한 장을 그 자리에서 그린다(1~2 초). 512 로 키워 부르는 수를 줄인다
      tileGrid: ol.tilegrid.createXYZ({ extent: ol.proj.get(code).getExtent(), tileSize: 512 }),
      attributions: row.attribution || undefined,
    });
  }

  /** 대만 — GSMMA 지질도 (wetherilli 136). 상류(MapGuide)가 **4326 만 받는다** — 3857·3826 은 `InvalidCRS`.
   *  그래서 4326 격자로 받고 OpenLayers 가 옮겨 그린다. 격자는 줌 0 이 180° 네모 두 장이다 — 한 장이 360° 면
   *  위도가 -270° 까지 걸쳐 상류가 받지 않는다. 대만 범위 밖은 묻지 않는다(`makeLayer` 가 범위를 건다). */
  var TAIWAN_GRID = (function () {
    var resolutions = [];
    for (var z = 0; z <= 19; z++) resolutions.push(180 / 512 / Math.pow(2, z));
    return new ol.tilegrid.TileGrid({ extent: [-180, -90, 180, 90], origin: [-180, 90],
                                      resolutions: resolutions, tileSize: 512 });
  })();

  function taiwanSource(name) {
    var row = byName[name] || {};
    return new ol.source.TileWMS({
      url: BASE + "wms",
      params: { LAYERS: name, TILED: true, FORMAT: "image/png", TRANSPARENT: true, VERSION: "1.3.0" },
      transition: 0,
      projection: "EPSG:4326",
      tileGrid: TAIWAN_GRID,
      attributions: row.attribution || undefined,
    });
  }

  /** 일본 — GSJ 심리스 지질도 (devlog 024). 우리 서버(`gsj/`)가 z/x/y 타일을 중계한다.
   *  주소·줌·출처는 카탈로그 행이 준다. 줌 13 까지만 그려 주고, 더 들어가면
   *  OpenLayers 가 13 을 키워 그린다. */
  function gsjSource(name) {
    var row = byName[name] || {};
    return new ol.source.XYZ({
      url: BASE + row.tiles,
      maxZoom: row.maxZoom || 13,
      transition: 0,
      attributions: row.attribution || undefined,
    });
  }

  /** 지질도Navi 판 (wetherilli 171) — GSJ 가 판마다 구워 둔 z/x/y 타일. CORS 가 열려 있어 그림으로 내려받기에도 든다 */
  function geonaviSource(name) {
    var row = byName[name] || {};
    return new ol.source.XYZ({
      url: row.tiles,
      maxZoom: row.maxZoom || 14,
      crossOrigin: "anonymous",
      transition: 0,
      attributions: row.attribution || undefined,
    });
  }

  /** 국토지리원 주제 타일 (wetherilli 172). 주소·줌·출처는 카탈로그 행이 준다 — 지리원 주소 그대로라 `BASE` 를 붙이지 않는다 */
  function gsiTileSource(name) {
    var row = byName[name] || {};
    return new ol.source.XYZ({
      url: row.tiles, crossOrigin: "anonymous", maxZoom: row.maxZoom || 16, transition: 0,
      attributions: row.attribution || undefined,
    });
  }

  /** 한반도 지질도 — phyloserver 가 카카오맵 격자로 잘라 둔 타일 (devlog 026).
   *  격자(`phyloserver.py` 의 SCAN_*)를 그대로 받고 OpenLayers 가 옮겨 그린다.
   *  카카오 레벨 L 의 한 픽셀은 2^(L-3) m 이고 13 이 가장 거칠다. 타일 번호는 아래에서
   *  위로 세므로, 위에서 아래로 세는 OpenLayers 의 번호를 뒤집는다. */
  var KAKAO_GRID = { origin: [-30000, -60000], levels: [7, 13], top: [2, 5] };

  function phyloserverSource(name) {
    var row = byName[name] || {};
    if (!ol.proj.get("EPSG:5181")) return wmsSource(name);    // proj4 를 못 읽었다
    var g = KAKAO_GRID;
    var span = 256 * Math.pow(2, g.levels[1] - 3);            // 레벨 13 한 장의 길이(m)
    var extent = [g.origin[0], g.origin[1], g.origin[0] + g.top[0] * span, g.origin[1] + g.top[1] * span];
    var resolutions = [];
    for (var level = g.levels[1]; level >= g.levels[0]; level--) resolutions.push(Math.pow(2, level - 3));
    return new ol.source.TileImage({
      projection: "EPSG:5181",
      tileGrid: new ol.tilegrid.TileGrid({ extent: extent, origin: [extent[0], extent[3]],
                                           resolutions: resolutions, tileSize: 256 }),
      tileUrlFunction: function (coord) {
        var level = g.levels[1] - coord[0];
        var rows = g.top[1] * Math.pow(2, coord[0]);
        return BASE + row.tiles.replace("{z}", level).replace("{x}", coord[1])
          .replace("{y}", rows - 1 - coord[2]);
      },
      transition: 0,
      attributions: row.attribution || undefined,
    });
  }

  /** 한반도 지질도 음영판 — 우리 서버(`peninsula/`)가 잘라 둔 5179 타일 (devlog 027).
   *  격자(범위·해상도)는 카탈로그 행이 준다. 원점은 왼쪽 위, 번호는 위에서 아래로다. */
  function peninsulaSource(name) {
    var row = byName[name] || {};
    if (!ol.proj.get("EPSG:5179") || !row.grid) return wmsSource(name);   // proj4 를 못 읽었다
    var extent = row.grid.extent;
    return new ol.source.TileImage({
      projection: "EPSG:5179",
      tileGrid: new ol.tilegrid.TileGrid({ extent: extent, origin: [extent[0], extent[3]],
                                           resolutions: row.grid.resolutions, tileSize: 256 }),
      tileUrlFunction: function (coord) {
        return BASE + row.tiles.replace("{z}", coord[0]).replace("{x}", coord[1]).replace("{y}", coord[2]);
      },
      transition: 0,
      attributions: row.attribution || undefined,
    });
  }

  /** 페루 지질도의 속성 주소 (wetherilli 195) — 그림이 타일 캐시라 일본처럼 누른 자리의 위경도로 묻는다(`ingemmet/info/`). */
  function ingemmetInfoUrl(source, coordinate) {
    var ll = toLL(coordinate);
    return BASE + "ingemmet/info/?" + new URLSearchParams({
      layer: source.get("gsmName"), lat: ll[1].toFixed(6), lon: ll[0].toFixed(6),
    }).toString();
  }

  /** 일본 지질도의 속성 주소 — WMS 가 아니라 누른 자리의 위경도로 묻는다(`gsj/info/`). */
  function gsjInfoUrl(source, coordinate) {
    var ll = toLL(coordinate);
    return BASE + "gsj/info/?" + new URLSearchParams({
      layer: source.get("gsmName"), lat: ll[1].toFixed(6), lon: ll[0].toFixed(6),
    }).toString();
  }

  //: 타일 레이어를 짓는 손 — **상류마다 하나다.** 상류가 주는 꼴이 달라서다
  //  (KIGAM·GEUS·VWorld 는 WMS, GeoMAP 은 우리가 구운 타일). `info` 가 없으면 그
  //  레이어는 눌러도 속성을 묻지 않는다. 벡터·점(`kind`)은 `makeLayer` 가 따로 짓는다
  //  — 그린란드 포털(grportal)이 그렇다. 상류가 새로 오면 여기 한 줄을 더한다.
  var LAYER_KINDS = {
    kigam: { source: wmsSource, info: wmsInfoUrl },
    geus: { source: wmsSource, info: wmsInfoUrl },
    vworld: { source: wmsSource, info: wmsInfoUrl },
    geomap: { source: geomapSource, info: geomapInfoUrl },
    grportal: { source: null, info: null },
    janmayen: { source: null, info: null },
    // 지구 자료 점(wetherilli 185) — 화석 산지·화산·지진·고생태 산지. 점을 한 덩이로 받아 그린다(`kind: points`)
    earth: { source: null, info: null },
    // KIGAM 5만 구조 요소(wetherilli 199) — 화석산지·시료·광산·도폭 틀. 받아 둔 WFS 파일을 한 덩이로
    kigam50k: { source: null, info: null },
    geo3al: { source: null, info: null },     // 중국 — 모양 한 덩이 (025)
    npolar: { source: npolarSource, info: wmsInfoUrl },
    // 극지연구소 KPDC 지도 서버(057) — NPI 처럼 3031 로 곧장 받는다
    kopri: { source: npolarSource, info: wmsInfoUrl },
    // PGC 경사·등고선(wetherilli 099) — NPI 처럼 지역의 투영으로 곧장 받는다. 누르면 그 자리의 값
    pgc: { source: npolarSource, info: wmsInfoUrl },
    gsj: { source: gsjSource, info: gsjInfoUrl },
    // 지질도Navi 판(wetherilli 171) — 브라우저가 tiles.gsj.jp 를 곧장. 속성은 없다(그림 판이다)
    geonavi: { source: geonaviSource, info: null },
    // 국토지리원 주제 타일(wetherilli 172) — 카탈로그가 준 지리원 주소를 브라우저가 곧장 부른다(서버를 거치지 않는다)
    gsitile: { source: gsiTileSource, info: null },
    // CCOP 200만 지질도(wetherilli 108) — 여느 WMS 다. 속성의 4326 풀이는 서버의 문(gsj.py)이 한다
    ccop: { source: wmsSource, info: wmsInfoUrl },
    // 대만 지질도(wetherilli 136) — 4326 WMS. 속성은 서버의 문(gsmma.py)이 지질운 API 로 바꿔 묻는다
    gsmma: { source: taiwanSource, info: wmsInfoUrl },
    // EMODnet 해저 지질(wetherilli 135) — NPI 처럼 3413 으로 곧장 받는다
    emodnet: { source: npolarSource, info: wmsInfoUrl },
    // 노르웨이 NGU(3575)·핀란드 GTK(3413) 기반암(wetherilli 140) — 카탈로그 행의 투영으로 받는다
    ngu: { source: npolarSource, info: wmsInfoUrl },
    gtk: { source: npolarSource, info: wmsInfoUrl },
    // 스웨덴 SGU(wetherilli 213) — GeoServer 가 3413 을 그린다. 레이어 하나가 1:100만·5만 판을 함께 부른다
    sgu: { source: npolarSource, info: wmsInfoUrl },
    // 영국 BGS·프랑스 BRGM·범유럽 EGDI(wetherilli 143) — 3857 이지만 출처를 카탈로그 행에서 받으려고 같은 틀을 쓴다
    bgs: { source: npolarSource, info: wmsInfoUrl },
    brgm: { source: npolarSource, info: wmsInfoUrl },
    egdi: { source: npolarSource, info: wmsInfoUrl },
    // 독일 BGR·스페인 IGME(1:100만은 4326)·아일랜드 GSI·북아일랜드 GSNI(wetherilli 147) — 카탈로그 행의 투영으로 받는다
    bgr: { source: npolarSource, info: wmsInfoUrl },
    igme: { source: npolarSource, info: wmsInfoUrl },
    gsi: { source: npolarSource, info: wmsInfoUrl },
    gsni: { source: npolarSource, info: wmsInfoUrl },
    // 남미·콜롬비아 SGC(wetherilli 188) — ArcGIS WMS 를 3857 로
    sgc: { source: npolarSource, info: wmsInfoUrl },
    // 아르헨티나·우루과이(wetherilli 196) — 유럽 문처럼 카탈로그 행의 투영(3857)으로 서버 문을 거쳐 받는다
    segemar: { source: npolarSource, info: wmsInfoUrl },
    dinamige: { source: npolarSource, info: wmsInfoUrl },
    // 브라질 SGB(wetherilli 191) — GeoServer WMS 를 3857 로. 범례는 보는 범위의 것(`sgb/legend/`)
    sgb: { source: npolarSource, info: wmsInfoUrl },
    // 페루 INGEMMET(wetherilli 195) — 우리 서버가 중계하는 REST 캐시의 z/x/y. 그리는 손은 일본의 것과 같다
    ingemmet: { source: gsjSource, info: ingemmetInfoUrl },
    // 에콰도르 IIGE(wetherilli 198) — ArcGIS WMS 를 3857 로
    iige: { source: npolarSource, info: wmsInfoUrl },
    // 미국 USGS mrdata(wetherilli 205) — MapServer WMS 를 3857 로. 본토의 속성은 서버가 WFS 로 바꿔 묻는다
    mrdata: { source: npolarSource, info: wmsInfoUrl },
    // 멕시코 SGM(wetherilli 206) — 화면에는 3857 WMS 와 같다. 서버의 문이 REST export·identify 로 옮긴다
    sgm: { source: npolarSource, info: wmsInfoUrl },
    // 아프리카(wetherilli 207) — 카탈로그 행의 투영(3857)으로 서버 문을 거쳐 받는다
    cgmw: { source: npolarSource, info: wmsInfoUrl },
    aga: { source: npolarSource, info: wmsInfoUrl },
    // 아프리카 나라 판(wetherilli 209) — 남아공 CGS(서버가 REST export 로 옮긴다)·나미비아 GSN
    cgs: { source: npolarSource, info: wmsInfoUrl },
    gsn: { source: npolarSource, info: wmsInfoUrl },
    // 캐나다 NRCan·온타리오 OGS(wetherilli 204) — 카탈로그 행의 투영(3978)으로 서버 문을 거쳐 받는다. OGS 속성은 문이 REST identify 로 바꾼다
    nrcan: { source: npolarSource, info: wmsInfoUrl },
    ogs: { source: npolarSource, info: wmsInfoUrl },
    // 퀘벡 SIGÉOM·유콘 YGS(wetherilli 210) — 카탈로그 행의 투영(3978)으로 서버 문을 거쳐 받는다. 퀘벡은 Origin 을 보내면 403 이라 문으로만
    sigeom: { source: npolarSource, info: wmsInfoUrl },
    ygs: { source: npolarSource, info: wmsInfoUrl },
    // 호주 GA(wetherilli 212) — ArcGIS WMS 를 3857 로. 범례는 보는 범위의 것(`ga/legend/`)
    ga: { source: npolarSource, info: wmsInfoUrl },
    // 이탈리아 ISPRA·포르투갈 LNEG·스위스 swisstopo(wetherilli 211) — 유럽 문처럼 카탈로그 행의 투영(3857)으로 서버 문을 거친다
    ispra: { source: npolarSource, info: wmsInfoUrl },
    lneg: { source: npolarSource, info: wmsInfoUrl },
    swisstopo: { source: npolarSource, info: wmsInfoUrl },
    phyloserver: { source: phyloserverSource, info: null },
    peninsula: { source: peninsulaSource, info: null },
    // 남극 IBCSO 자료 출처(071) — GeoMAP 과 같은 3031 격자에 우리가 잘라 둔 것
    ibcso: { source: geomapSource, info: ibcsoInfoUrl },
  };

  function layerKind(name) {
    var row = byName[name];
    var up = (row && row.upstream) || "kigam";
    if (STATIC) {
      if (up === "kigam") return STATIC_KIGAM;
      if (up === "vworld") return STATIC_VWORLD;
      // 구운 타일(GeoMAP·IBCSO 자료 출처)은 그림만 — 속성은 서버가 gpkg·격자에서 읽던 것이라 묻지 않는다 (wetherilli 165)
      if (up === "geomap" || up === "ibcso") return { source: geomapSource, info: null };
      var kinds = window.GSM_STATIC_KINDS || {};
      if (kinds[up]) return kinds[up];
    }
    return LAYER_KINDS[up] || LAYER_KINDS.kigam;
  }

  /** 정적 판에 구워 실은 것(`bake_static`, wetherilli 160·165) — `static_site.py` 가 manifest 에서 옮겨 적는다.
   *  `geomap`: 레이어 → 마지막 줌, `points`: 레이어 → 영어판이 따로 있나 */
  function staticBaked(part) {
    return (STATIC && STATIC.baked && STATIC.baked[part]) || {};
  }

  // ── 정적 판의 KIGAM (wetherilli P11·162) ──
  // 문서화된 `/openapi/wms` 를 각자 키로 브라우저가 곧장 부른다. 타일은 `<img>` 라 CORS 가 없어도 받힌다
  // (KIGAM 은 CORS 를 열지 않았다 — docs/정적_밖_경로.md §2). 그래서 `crossOrigin` 을 두지 않고, 속성은
  // 묻지 않는다(`/openapi/wms` 는 GetFeatureInfo 를 막았고 GeoServer 길은 CORS 가 없다). 키가 없으면 타일을 묻지 않는다
  var KIGAM_OPENAPI = "https://data.kigam.re.kr/openapi/wms";
  var STATIC_KIGAM = {
    source: function (name) {
      return new ol.source.TileWMS({
        url: KIGAM_OPENAPI,
        params: { LAYERS: name, TILED: true, FORMAT: "image/png", TRANSPARENT: true, key: readKey("kigam") },
        transition: 0,
        projection: "EPSG:3857",
        tileGrid: ol.tilegrid.createXYZ({ tileSize: 512 }),
        tileLoadFunction: function (tile, src) {
          if (!readKey("kigam")) { tile.setState(4); return; }     // 4 = 빈 타일 — 키가 없으면 묻지 않는다
          tile.getImage().src = src;
        },
      });
    },
    info: null,
  };

  // ── 정적 판의 VWorld (wetherilli 164) ──
  //
  // 검토(docs/정적_밖_경로.md §10)의 권고대로 **공개 판용 키 하나**로 보는 것만 — 그 키는 굽는 사람이 넘긴 것이고
  // 화면에 실린다(`vworldKey`). VWorld 는 배경 WMTS 만 CORS 를 열었다. WMS 그림은 `<img>` 라 받히고(그래서 `crossOrigin`
  // 을 두지 않는다 — 그림으로 내려받기에서는 빠진다), 속성(GetFeatureInfo)·WFS 는 CORS 가 없어 쓰지 않는다. 찾기·좌표→주소는
  // JSONP 로 곧장 — 서버의 `vworld.search`·`reverse` 를 옮겼다
  var VWORLD_API = "https://api.vworld.kr/req/";
  var STATIC_VWORLD = {
    source: function (name) {
      return new ol.source.TileWMS({
        url: VWORLD_API + "wms",
        // 레이어명은 소문자라야 돈다(020). 1.3.0 의 EPSG:3857 은 축 차례가 그대로다
        params: { LAYERS: name.toLowerCase(), STYLES: "", VERSION: "1.3.0", FORMAT: "image/png", TRANSPARENT: true,
                  TILED: true, key: vworldKey, domain: location.origin },
        transition: 0,
        projection: "EPSG:3857",
        tileGrid: ol.tilegrid.createXYZ({ tileSize: 512 }),
        tileLoadFunction: function (tile, src) {
          if (!vworldKey) { tile.setState(4); return; }
          tile.getImage().src = src;
        },
      });
    },
    info: null,
  };
  function vworldLegendUrl(name) {
    return VWORLD_API + "image?" + new URLSearchParams({ service: "image", request: "GetLegendGraphic", format: "png",
      type: "ALL", layer: name.toLowerCase(), style: name.toLowerCase(), key: vworldKey, domain: location.origin });
  }

  /** JSONP 한 번 — `<script>` 로 부르고 콜백으로 받는다. 8 초 넘으면 실패. VWorld 가 준 스크립트가 우리 화면에서 돈다는 것을
   *  받아들였다(검토 §3) — 콜백은 이름이 매번 다르고 받은 뒤 지운다 */
  var jsonpSeq = 0;
  function jsonp(url, params) {
    return new Promise(function (resolve, reject) {
      var name = "__gsmJsonp" + (++jsonpSeq) + "_" + Date.now();
      var script = document.createElement("script");
      var timer = setTimeout(function () { done(); reject(new Error("timeout")); }, 8000);
      function done() { clearTimeout(timer); delete window[name]; script.remove(); }
      window[name] = function (data) { done(); resolve(data); };
      script.onerror = function () { done(); reject(new Error("network")); };
      script.src = url + "?" + new URLSearchParams(Object.assign({}, params, { callback: name }));
      document.head.appendChild(script);
    });
  }
  function vworldJsonp(path, params) {
    return jsonp(VWORLD_API + path, Object.assign({ key: vworldKey, domain: location.origin, format: "json",
                                                   crs: "EPSG:4326" }, params))
      .then(function (data) {
        var body = (data || {}).response || {};
        if (body.status === "NOT_FOUND") return {};
        if (body.status !== "OK") throw new Error(T("VWorld 가 거절했다"));
        return body.result || {};
      });
  }
  //: 찾기 한 번에 묻는 갈래 — 서버의 `vworld.KINDS` 와 같다(읍면동·시군구·도로명·지번·장소)
  var VWORLD_KINDS = [
    ["district", { type: "district", category: "L4" }, 3], ["district", { type: "district", category: "L2" }, 2],
    ["road", { type: "address", category: "road" }, 4], ["parcel", { type: "address", category: "parcel" }, 4],
    ["place", { type: "place" }, 6],
  ];
  /** 서버의 `vworld.search` 를 옮겼다 — 갈래 다섯을 한꺼번에, 이름이 같으면 하나로, 넣은 말로 끝나는 행정구역이 맨 앞 */
  function staticVworldSearch(q) {
    return Promise.all(VWORLD_KINDS.map(function (k) {
      return vworldJsonp("search", Object.assign({ service: "search", request: "search", version: "2.0", size: k[2],
                                                   page: 1, query: q }, k[1]))
        .then(function (result) {
          return (result.items || []).map(function (item) {
            var p = item.point || {}, addr = item.address || {}, title, sub;
            if (k[0] === "place") { title = item.title || ""; sub = addr.road || addr.parcel || ""; }
            else if (k[0] === "district") { title = item.title || ""; sub = ""; }
            else { title = addr[k[0]] || item.title || ""; sub = addr[k[0] === "road" ? "parcel" : "road"] || ""; }
            return { kind: k[0], title: title, sub: sub, lat: +p.y, lon: +p.x };
          }).filter(function (r) { return r.title && isFinite(r.lat) && isFinite(r.lon); });
        }, function (err) { return { failed: err }; });
    })).then(function (all) {
      var failed = all.filter(function (x) { return x.failed; });
      if (failed.length === all.length) throw failed[0].failed;
      var seen = {}, out = [];
      all.forEach(function (rows) {
        if (rows.failed) return;
        rows.forEach(function (r) { if (!seen[r.title]) { seen[r.title] = true; out.push(r); } });
      });
      out.sort(function (a, b) {
        var fa = a.kind === "district" && a.title.slice(-q.length) === q ? 0 : 1;
        var fb = b.kind === "district" && b.title.slice(-q.length) === q ? 0 : 1;
        return fa - fb;
      });
      return out;
    });
  }
  /** 서버의 `vworld.reverse` 를 옮겼다 — 좌표 → `{road, parcel}` */
  function staticVworldWhereis(lat, lon) {
    return vworldJsonp("address", { service: "address", request: "getAddress", version: "2.0", type: "both",
                                    point: lon + "," + lat })
      .then(function (result) {
        var out = { road: "", parcel: "" };
        (Array.isArray(result) ? result : []).forEach(function (row) {
          var kind = String(row.type || "").toLowerCase();
          if (kind in out && !out[kind]) out[kind] = row.text || "";
        });
        return out;
      });
  }

  /** 정적 판에서 KIGAM 레이어들의 키를 바꾼다 — 키를 넣거나 지우면 켠 레이어를 다시 그린다. */
  function refreshKigamKey() {
    active.forEach(function (entry) {
      var row = byName[entry.name];
      if (!row || (row.upstream || "kigam") !== "kigam" || !entry.layer.getSource().updateParams) return;
      entry.layer.getSource().updateParams({ key: readKey("kigam") });
    });
  }

  function layerSource(name) {
    var source = (layerKind(name).source || wmsSource)(name);
    source.set("gsmName", name);
    return source;
  }

  /** 레이어의 출처 표기. KIGAM·GEUS 는 비워 둔다 — 레이어 이름이 곧 출처다.
   *  VWorld 레이어는 밝힌다 (devlog 020). 만든 기관은 국토지리정보원·환경부·농촌진흥청·
   *  항공 공역처럼 레이어마다 달라 VWorld 만 적는다 (wetherilli 084) */
  function sourceNote(name) {
    var row = byName[name];
    return row && row.upstream === "vworld" ? "VWorld" : row && row.upstream === "ccop" ? "CCOP · GSJ" : "";
  }

  /** 켤 레이어 하나를 만든다. 타일(WMS)이 거의 전부이고, 벡터는 따로 짓는다. */
  function makeLayer(name) {
    var row = byName[name];
    if (row && row.kind === "vector") return vectorLayerFor(row);
    if (row && row.kind === "points") return pointLayerFor(row);
    var tile = new ol.layer.Tile({ source: layerSource(name), opacity: DEFAULT_OPACITY });
    // 가까이서만 그려 주는 레이어(일본의 경계·단층·기호, 줌 10·11 부터)는 그보다
    // 멀면 숨긴다 — 빈 타일을 묻지 않는다. 반 단계를 빼야 그 줌의 타일이 뜨는 자리부터 보인다
    if (row && row.minZoom) tile.setMinZoom(row.minZoom - 0.5);
    // 넓게 볼 때만 그려 주는 레이어(프랑스의 1:100만·1:25만 스캔)는 그보다 가까우면 숨긴다 (wetherilli 143)
    if (row && row.lastZoom) tile.setMaxZoom(row.lastZoom + 0.5);
    // 묶음 탭(동아시아)에서는 레이어의 범위 밖 타일을 묻지 않는다 — 일본을 볼 때
    // KIGAM 에 일본·바다 자리를 묻지 않게(호출 제한, 010). 상류가 적은 범위가 빠듯할
    // 수 있어 0.5° 넉넉히 둔다. 극지 묶음(북극)은 위경도 네모가 부채꼴이라 두지 않는다 (024)
    // 지질도Navi 판은 도폭 하나라 좁다 — 어느 탭에서든 범위 밖을 묻지 않는다 (wetherilli 171)
    // 나라 판을 대륙 탭 하나에 얹은 아프리카(`clip`, wetherilli 209)도 같다
    if (row && row.bbox && (REGIONS[region].includes || REGIONS[region].clip || row.upstream === "gsmma" || row.upstream === "geonavi") && isMercator()) {
      // 지질도Navi 판은 Capabilities 의 범위가 판 그대로라 넉넉히 두지 않는다 — 둘레의 없는 타일(404)을 묻지 않게
      var b = row.bbox, pad = row.upstream === "geonavi" ? 0 : 0.5;
      tile.setExtent(ol.proj.transformExtent([b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad],
                                             "EPSG:4326", viewProj()));
    }
    return tile;
  }

  // ── 벡터 레이어 — 모양을 받아 우리가 그린다 ─────────────────────
  //
  // 타일이 아니라 모양(GeoJSON)을 서버(`./vector/`)에서 받는다. 선 색·굵기를
  // 우리가 정하므로 어느 줌에서도 또렷하고, 누르면 그 선의 속성이 곧장 뜬다
  // (상류를 다시 안 탄다). 지금은 단층 하나다 (devlog 020).
  //
  // **위경도 칸(`row.cell`, 대개 1°)으로 나눠 받는다.** 선이 빽빽한 레이어는 칸이 작고
  // 줌 `row.minZoom` 부터 받는다(지하수 등수심선 0.125°·줌 11, 077). 칸 이름은 좌표계와 상관이
  // 없어서 지역마다 투영이 달라도 같은 칸을 같은 주소로 부른다 — 브라우저·서버
  // 캐시가 그대로 맞는다. 받은 칸은 다시 받지 않는다. 칸 경계를 넘는 선은 양쪽
  // 칸에 다 오는데, 모양의 `id` 가 같아 소스가 하나만 둔다.

  //: 레이어마다 선을 어떻게 그리나. `by` 열의 값으로 가른다.
  //  단층의 `legend` 는 VWorld 가 뜻을 밝히지 않았다 — 1 이 거의 전부(2259)이고
  //  2(155)는 경상분지에 몰린 짧은 선이다. 뜻을 모르니 이름을 지어 붙이지 않고
  //  값 그대로 적되, 눈으로 갈리게 2 를 끊은 선으로 그린다.
  var VECTOR_STYLES = {
    lt_l_gimsfault: {
      by: "legend",
      classes: {
        "1": { color: "#8a0a1e", width: 2, dash: null },
        "2": { color: "#8a0a1e", width: 2, dash: [7, 5] },
      },
      other: { color: "#6b3a2a", width: 1.4, dash: null },
    },
    // 지하수 등치선 — 갈래가 아니라 값이다. 한 색으로 긋고 가까이서 값을 선에 적는다
    lt_l_gimspoten: { color: "#1f5fa8", width: 1.2, dash: null, labelBy: "legend", unit: "m" },
    lt_l_gimsec: { color: "#2a7f62", width: 1.2, dash: [6, 3], labelBy: "legend", unit: "µS/cm" },
    lt_l_gimsdepth: { color: "#6a3fa0", width: 1.1, dash: [2, 3], labelBy: "legend", unit: "m" },
    // 수질·지하수 측정망 — 점이다(wetherilli 156). 수질 다섯은 색으로 가르고, 지하수는 네모로 가른다
    lt_p_weissitema: { point: "circle", color: "#1f6fb2", width: 1, radius: 4.5 },
    lt_p_weissitemb: { point: "circle", color: "#1a9a9a", width: 1, radius: 4.5 },
    lt_p_weissitemd: { point: "circle", color: "#5f8f1a", width: 1, radius: 4.5 },
    lt_p_weissiteme: { point: "circle", color: "#8a4a1f", width: 1, radius: 4.5 },
    lt_p_weissitemf: { point: "circle", color: "#7a3fb0", width: 1, radius: 4.5 },
    lt_p_sgisgwchg: { point: "square", color: "#c0392b", width: 1, radius: 5 },
  };
  //: 등치선 값을 적기 시작하는 줌. 멀리서는 글자가 선을 덮는다
  var VECTOR_LABEL_ZOOM = 11;
  var DEFAULT_VECTOR_STYLE = { color: "#b3202a", width: 1.6, dash: null };
  var vectorStyleCache = {};

  function vectorStyleOf(spec) {
    var key = spec.color + "|" + spec.width + "|" + (spec.dash || "") + "|" + (spec.point || "");
    if (spec.point && !vectorStyleCache[key]) {
      // 점 — 흰 테두리를 둘러 지질도 색 위에서도 묻히지 않게 (wetherilli 156)
      var fill = new ol.style.Fill({ color: spec.color });
      var rim = new ol.style.Stroke({ color: "rgba(255,255,255,0.9)", width: 1.5 });
      vectorStyleCache[key] = [new ol.style.Style({ image: spec.point === "square"
        ? new ol.style.RegularShape({ points: 4, radius: spec.radius || 5, angle: Math.PI / 4, fill: fill, stroke: rim })
        : new ol.style.Circle({ radius: spec.radius || 4.5, fill: fill, stroke: rim }) })];
    }
    if (!vectorStyleCache[key]) {
      vectorStyleCache[key] = [
        // 밑에 흰 테두리 — 지질도 색 위에서도 선이 묻히지 않게
        new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(255,255,255,0.75)", width: spec.width + 2.4 }) }),
        new ol.style.Style({ stroke: new ol.style.Stroke({ color: spec.color, width: spec.width, lineDash: spec.dash || undefined }) }),
      ];
    }
    return vectorStyleCache[key];
  }

  function vectorSpec(name, feature) {
    var table = VECTOR_STYLES[name];
    if (!table) return DEFAULT_VECTOR_STYLE;
    if (!table.classes) return table;
    var value = feature ? String(feature.get(table.by)) : "";
    return table.classes[value] || table.other || DEFAULT_VECTOR_STYLE;
  }

  /** 켤 벡터 레이어 하나. `row` 는 카탈로그 행 (`kind: "vector"`). */
  function vectorLayerFor(row) {
    var cell = row.cell || 1;
    var loaded = {};                 // 받은(또는 받는 중인) 칸
    var format = new ol.format.GeoJSON();
    var source = new ol.source.Vector({
      attributions: sourceNote(row.name) || undefined,
      strategy: ol.loadingstrategy.bbox,
      loader: function (extent, resolution, projection, success, failure) {
        var ll = ol.proj.transformExtent(extent, projection, "EPSG:4326");
        var box = row.bbox || [-180, -90, 180, 90];
        var west = Math.max(ll[0], box[0]), south = Math.max(ll[1], box[1]);
        var east = Math.min(ll[2], box[2]), north = Math.min(ll[3], box[3]);
        var cells = [];
        if (west < east && south < north) {
          for (var x = Math.floor(west / cell) * cell; x < east; x += cell) {
            for (var y = Math.floor(south / cell) * cell; y < north; y += cell) {
              var id = x + "," + y;
              if (!loaded[id]) cells.push([x, y]);
            }
          }
        }
        // 세계가 다 들어오는 줌에서 한꺼번에 부르지 않는다. 레이어 범위가
        // 있으면 1° 칸은 이 한계에 닿을 일이 없다 (남한은 50 칸 남짓). 0.125° 칸은 큰 화면의
        // 줌 11 에서 닿는다 — 받은 범위로 적히지 않게 지워 두어, 당겨 보면 다시 부른다
        if (cells.length > 80) { source.removeLoadedExtent(extent); success([]); return; }
        if (!cells.length) { success([]); return; }
        var pending = cells.length, got = [], failed = false;
        cells.forEach(function (c) {
          var id = c[0] + "," + c[1];
          loaded[id] = true;
          var url = BASE + "vector/?layer=" + encodeURIComponent(row.name) +
            "&lon=" + c[0] + "&lat=" + c[1] + "&lang=" + LANG;
          fetch(url)
            .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then(function (data) {
              got = got.concat(format.readFeatures(data, { dataProjection: "EPSG:4326", featureProjection: projection }));
            })
            .catch(function () { delete loaded[id]; failed = true; })   // 다음에 다시 묻는다
            .then(function () {
              pending -= 1;
              if (pending) return;
              source.addFeatures(got);
              if (failed && !got.length) failure(); else success(got);
            });
        });
      },
    });
    var layer = new ol.layer.Vector({
      source: source,
      opacity: DEFAULT_OPACITY,
      // 이 줌 밑에서는 그리지도 받지도 않는다. 타일 레이어(`setMinZoom`)와 같게 반 단계 당긴다
      minZoom: row.minZoom ? row.minZoom - 0.5 : undefined,
      style: function (feature, resolution) {
        var spec = vectorSpec(row.name, feature);
        var styles = vectorStyleOf(spec);
        var value = spec.labelBy && feature.get(spec.labelBy);
        if (value == null || value === "" || mercZoom(resolution) < VECTOR_LABEL_ZOOM) return styles;
        return styles.concat(new ol.style.Style({ text: new ol.style.Text({
          text: String(value), font: "11px sans-serif", placement: "line",
          fill: new ol.style.Fill({ color: spec.color }),
          stroke: new ol.style.Stroke({ color: "rgba(255,255,255,0.9)", width: 3 }),
        }) }));
      },
    });
    // 누른 자리의 속성을 팝업에 올릴 때 이 표식으로 가려낸다 (`onClick`)
    layer.set("gsmVector", row.name);
    return layer;
  }

  /** 벡터 레이어의 범례 — 우리가 그리니 우리가 적는다. 상류 범례는 우리 색과 다르다. */
  function vectorLegend(name) {
    var table = VECTOR_STYLES[name];
    var box = document.createElement("div");
    box.className = "vector-legend";
    var title = byName[name] ? byName[name].title : name;
    var rows = table && table.classes ? Object.keys(table.classes).map(function (value) {
      return { spec: table.classes[value], label: T("구분 {value}", { value: value }) };
    }) : table && table.unit ? [{ spec: table, label: T("등치선 ({unit}) — 줌 {n} 부터 값을 적는다",
                                                        { unit: table.unit, n: VECTOR_LABEL_ZOOM }) }]
      : [{ spec: table && table.point ? table : DEFAULT_VECTOR_STYLE, label: title }];
    rows.forEach(function (r) {
      var line = document.createElement("div");
      line.className = "vector-legend-row";
      var svg = r.spec.point
        ? '<svg width="36" height="10" aria-hidden="true">' + (r.spec.point === "square"
          ? '<rect x="13" y="0.5" width="9" height="9" fill="' + r.spec.color + '" stroke="#fff"/>'
          : '<circle cx="18" cy="5" r="4.5" fill="' + r.spec.color + '" stroke="#fff"/>') + "</svg>"
        : '<svg width="36" height="10" aria-hidden="true"><line x1="2" y1="5" x2="34" y2="5" stroke="' +
          r.spec.color + '" stroke-width="' + r.spec.width + '"' +
          (r.spec.dash ? ' stroke-dasharray="' + r.spec.dash.join(" ") + '"' : "") + "/></svg>";
      line.innerHTML = svg + "<span>" + esc(r.label) + "</span>";
      box.appendChild(line);
    });
    return box;
  }

  /** 배경지도.
   *
   *  **기본은 "없음" 이다.** 처음에는 OpenStreetMap 을 깔았는데, 기관 망의
   *  바깥 IP 가 OSM 정책 위반으로 막혀 있어 타일 자리마다
   *  `403 Access blocked` 그림이 깔렸다 (2026-09-23).
   *
   *  우리 서버로 중계하면 화면은 살지만 그것이야말로 OSM 이 막는 행동이고,
   *  이번엔 서버 IP 가 막힌다. 그래서 중계하지 않고 **고르게** 했다.
   *
   *  배경이 없어도 읽힌다 — 지질도 자체가 지명·행정경계·수계를 그려 준다.
   *  종이 지질도가 그렇게 생겼다.
   */
  // OpenStreetMap 은 고르개에서 뺐다. 기관 망의 바깥 IP 가 OSM 정책 위반으로
  // 막혀 있어(devlog 003) 고를 수 있게 두면 `403 Access blocked` 타일만
  // 깔린다. 고쳐지지 않는 것을 목록에 두는 것은 고르개가 아니라 함정이다.
  var BASEMAPS = {
    none: { title: T("없음 (바탕만)"), make: null },
  };

  // VWorld 는 열쇠가 있을 때만 고르개에 오른다.
  //
  // **브라우저가 곧장 부른다.** 상류 지질도와 다른 점이다 — VWorld 는
  // 브라우저가 직접 부르는 것을 전제로 하고 열쇠에 도메인 제한을 걸어
  // 지킨다. 서버가 중계하면 그 제한이 뜻을 잃고 타일을 전부 우리가 짊어진다.
  // **곧장 닿지 못할 때만**(사내 VPN) 서버를 거친다 — 아래 `vworldSource` (033).
  //
  // WMTS 의 자리 차례가 **z/y/x** 다. z/x/y 로 적으면 엉뚱한 곳이 그려진다.
  if (vworldKey) {
    BASEMAPS.vworld = {
      title: T("VWorld 배경지도"),
      note: T("국토지리정보원"),
      make: function () {
        return new ol.layer.Tile({
          opacity: 0.85,
          source: vworldSource("Base", "png", {
            attributions: '© <a href="https://www.vworld.kr/" target="_blank" rel="noopener">VWorld</a>',
          }),
        });
      },
    };
    // 백지도·야간지도. `Base` 와 같은 창구에 레이어 이름만 다르다.
    // **지질도 밑에는 백지도가 낫다** — 도로·지명 색이 죽어 있어 지질도의
    // 분홍·자홍과 다투지 않는다 (004). 야간은 먹갈색 화면과 어울린다.
    BASEMAPS.vworld_white = {
      title: T("VWorld 백지도"),
      note: T("국토지리정보원. 지질도 밑에 깔기 좋다"),
      make: function () { return vworldPlain("white"); },
    };
    BASEMAPS.vworld_midnight = {
      title: T("VWorld 야간"),
      note: T("국토지리정보원"),
      make: function () { return vworldPlain("midnight"); },
    };
    // 위성 사진과 지명은 **따로 오는 레이어다**(`Satellite`·`Hybrid`).
    // 그래서 지명만 끌 수 있다 — 지질 경계를 볼 때 글자가 방해가 된다.
    // 일반 배경지도(`Base`)는 지명이 그림에 박혀 있어 끄지 못한다.
    BASEMAPS.vworld_hybrid = {
      title: T("VWorld 위성"),
      note: T("국토지리정보원. 지명을 끄고 켤 수 있다"),
      labels: true,
      make: function () {
        var labels = new ol.layer.Tile({
          source: vworldSource("Hybrid", "png"),
          visible: labelsOn(),
        });
        labels.set("gsmLabels", true);
        return new ol.layer.Group({ layers: [
          new ol.layer.Tile({ source: vworldSource("Satellite", "jpeg", {
            attributions: '© <a href="https://www.vworld.kr/" target="_blank" rel="noopener">VWorld</a>',
          })}),
          labels,
        ]});
      },
    };
  }
  // ── 극지 배경 (017) ──
  //
  // VWorld 처럼 **브라우저가 곧장 부른다.** 넷 다 열쇠가 없고 CORS 를 열어
  // 두었다(2026-09-27, Esri 는 09-29). `regions` 에 적은 지역에서만 고르개에 오른다.
  //
  // - **제 투영으로 주는 것을 먼저 쓴다.** NASA GIBS 는 3413·3031 WMTS 를,
  //   PGC 는 REMA·ArcticDEM 을 3031·3413 그대로 준다. 남극의 고해상 위성은
  //   Esri 가 3031 로 구워 둔 것이다 — GIBS Blue Marble(500 m)은 기지 축척에서 흐리다 (040)
  // - Esri 는 **Esri 이용 조건**(Master License Agreement)을 따른다 — EOX 처럼 밖에 열 때 다시 본다
  // - EOX 는 3857 뿐이다(WMS 도 3413·3031 을 400 으로 돌려보낸다). 그린란드는
  //   OpenLayers 가 옮겨 그리면 되지만, 남극은 3857 이 남위 85° 에서 끊겨
  //   극이 비므로 남극에는 두지 않는다
  // - **EOX 는 북위 약 82.5° 위에서 틀린다.** 위성 영상이 거기서 끝나고, 그 위는
  //   흰 바탕에 거친 바다 경계뿐이라 피어리랜드의 피오르가 엉뚱한 자리에 선다.
  //   지형 음영도 같다. GEUS 지질도는 ArcticDEM 과 맞는다 (2026-09-29 대조)
  var EOX_S2 = 'Sentinel-2 cloudless by <a href="https://s2maps.eu" target="_blank" rel="noopener">EOX IT Services GmbH</a> (contains modified Copernicus Sentinel data 2023, CC BY-NC-SA 4.0)';
  var EOX_TERRAIN = 'Terrain Light © <a href="https://maps.eox.at" target="_blank" rel="noopener">EOX IT Services GmbH</a>, data © OpenStreetMap contributors and others (CC BY-NC-SA 4.0)';
  var GIBS = 'Blue Marble © <a href="https://earthdata.nasa.gov/gibs" target="_blank" rel="noopener">NASA EOSDIS GIBS</a>';
  var PGC_REMA = 'REMA © <a href="https://www.pgc.umn.edu/data/rema/" target="_blank" rel="noopener">Polar Geospatial Center</a>, Byrd Polar (CC BY 4.0)';
  var PGC_ARCTICDEM = 'ArcticDEM © <a href="https://www.pgc.umn.edu/data/arcticdem/" target="_blank" rel="noopener">Polar Geospatial Center</a> (CC BY 4.0)';
  var ESRI_ANTARCTIC = 'Antarctic Imagery: Earthstar Geographics · <a href="https://www.arcgis.com/home/item.html?id=6553466517dd4d5e8b0c518b8d6b64cb" target="_blank" rel="noopener">Powered by Esri</a>';

  BASEMAPS.eox_s2 = {
    title: T("Sentinel-2 위성 (EOX)"),
    note: T("EOX · Copernicus Sentinel-2 (2023). 비상업 이용만 된다. 북위 82° 위는 해안선이 거칠다 — ArcticDEM 을 쓴다"),
    regions: ["greenland", "jan_mayen", "svalbard", "arctic_ocean", "fennoscandia", "japan", "china", "taiwan", "uk", "france",
              "germany", "spain", "ireland", "colombia", "brazil", "peru", "argentina", "uruguay", "ecuador", "usa", "mexico", "africa", "canada", "australia",
              "italy", "portugal", "switzerland"],
    make: function () { return eoxLayer("s2cloudless-2023_3857", 16, EOX_S2); },
  };
  BASEMAPS.eox_terrain = {
    title: T("지형 음영 (EOX)"),
    note: T("EOX · OpenStreetMap. 비상업 이용만 된다. 북위 82° 위는 해안선이 거칠다 — ArcticDEM 을 쓴다"),
    regions: ["greenland", "jan_mayen", "svalbard", "arctic_ocean", "fennoscandia", "japan", "china", "taiwan", "uk", "france",
              "germany", "spain", "ireland", "colombia", "brazil", "peru", "argentina", "uruguay", "ecuador", "usa", "mexico", "africa", "canada", "australia",
              "italy", "portugal", "switzerland"],
    make: function () { return eoxLayer("terrain-light_3857", 13, EOX_TERRAIN); },
  };
  BASEMAPS.arcticdem = {
    title: T("ArcticDEM 음영"),
    note: T("Polar Geospatial Center. 2 m 표고에서 그린 음영"),
    regions: ["greenland", "jan_mayen", "svalbard", "arctic_ocean", "fennoscandia"], needs: "EPSG:3413",
    make: function () { return pgcHillshade("arcticdem_latest", "EPSG:3413", PGC_ARCTICDEM); },
  };
  // 같은 ImageServer 의 다른 그리는 법 둘 (wetherilli 092). 여러 방향 음영은 한 방향 음영이 그늘에 묻는
  // 북서향 사면·선구조를 살린다. 높이 색 음영은 빙상·산지·해안 평지를 한눈에 가른다
  BASEMAPS.arcticdem_multi = {
    title: T("ArcticDEM 음영 (여러 방향)"),
    note: T("Polar Geospatial Center. 여러 방향에서 비춘 음영 — 한 방향 음영에서 그늘진 사면이 살아난다"),
    regions: ["greenland", "jan_mayen", "svalbard", "arctic_ocean", "fennoscandia"], needs: "EPSG:3413",
    make: function () { return pgcHillshade("arcticdem_latest", "EPSG:3413", PGC_ARCTICDEM, "Hillshade Multidirectional"); },
  };
  BASEMAPS.arcticdem_tinted = {
    title: T("ArcticDEM 높이 색 음영"),
    note: T("Polar Geospatial Center. 높이를 색으로 칠한 음영"),
    regions: ["greenland", "jan_mayen", "svalbard", "arctic_ocean", "fennoscandia"], needs: "EPSG:3413",
    make: function () { return pgcHillshade("arcticdem_latest", "EPSG:3413", PGC_ARCTICDEM, "Hillshade Elevation Tinted"); },
  };
  BASEMAPS.gibs_bm_n = {
    title: T("Blue Marble 위성 (NASA)"),
    note: T("NASA GIBS. 500 m 해상도라 넓게 볼 때 쓴다"),
    regions: ["greenland", "jan_mayen", "svalbard", "arctic_ocean", "fennoscandia"], needs: "EPSG:3413",
    make: function () { return gibsLayer("3413", "BlueMarble_ShadedRelief_Bathymetry", 4); },
  };
  BASEMAPS.gibs_bm_s = {
    title: T("Blue Marble 위성 (NASA)"),
    note: T("NASA GIBS. 500 m 해상도라 넓게 볼 때 쓴다"),
    regions: ["antarctica"], needs: "EPSG:3031",
    make: function () { return gibsLayer("3031", "BlueMarble_ShadedRelief_Bathymetry", 4); },
  };
  BASEMAPS.esri_antarctic = {
    title: T("남극 위성 (Esri)"),
    note: T("Esri · Earthstar Geographics TerraColor 15 m. 줌 13 까지 영상이 있고 그 위는 늘려 보인다. Esri 이용 조건을 따른다"),
    regions: ["antarctica"], needs: "EPSG:3031",
    make: esriAntarcticLayer,
  };
  BASEMAPS.ibcso_bed = {
    title: T("IBCSO 해저·빙저 지형"),
    note: T("IBCSO v2 (500 m). 빙붕·빙상을 걷어 낸 얼음 밑 기반암과 해저. CC BY 4.0"),
    regions: ["antarctica"], needs: "EPSG:3031",
    make: function () { return ibcsoLayer("bed"); },
  };
  BASEMAPS.ibcso_ice = {
    title: T("IBCSO 해저·얼음 위 지형"),
    note: T("IBCSO v2 (500 m). 빙붕·빙상의 윗면과 해저. CC BY 4.0"),
    regions: ["antarctica"], needs: "EPSG:3031",
    make: function () { return ibcsoLayer("ice"); },
  };
  BASEMAPS.rema = {
    title: T("REMA 음영"),
    note: T("Polar Geospatial Center. 2 m 표고에서 그린 음영"),
    regions: ["antarctica"], needs: "EPSG:3031",
    make: function () { return pgcHillshade("rema_latest", "EPSG:3031", PGC_REMA); },
  };
  BASEMAPS.rema_multi = {
    title: T("REMA 음영 (여러 방향)"),
    note: T("Polar Geospatial Center. 여러 방향에서 비춘 음영 — 한 방향 음영에서 그늘진 사면이 살아난다"),
    regions: ["antarctica"], needs: "EPSG:3031",
    make: function () { return pgcHillshade("rema_latest", "EPSG:3031", PGC_REMA, "Hillshade Multidirectional"); },
  };
  BASEMAPS.rema_tinted = {
    title: T("REMA 높이 색 음영"),
    note: T("Polar Geospatial Center. 높이를 색으로 칠한 음영"),
    regions: ["antarctica"], needs: "EPSG:3031",
    make: function () { return pgcHillshade("rema_latest", "EPSG:3031", PGC_REMA, "Hillshade Elevation Tinted"); },
  };
  // 이름을 `vworld` 로 시작하지 않는다 — 그런 배경은 한국·동아시아에서만 고르게 거른다(`fillBasemaps`).
  // 영상은 VWorld 것이라 열쇠가 없으면 두지 않는다 (wetherilli 093)
  if (vworldKey) BASEMAPS.antarctic_stations = {
    title: T("세종·장보고 기지 위성 (VWorld)"),
    note: T("VWorld · 2013 년 위성영상. 두 기지 둘레 10 km 남짓에만 있고 그 밖은 REMA 음영이다"),
    regions: ["antarctica"], needs: "EPSG:3031",
    make: vworldStationsLayer,
  };

  // ── 스발바르 배경 — 노르웨이 극지연구소 (devlog 021) ──
  //
  // NPI 가 UTM 33N(25833)으로 구워 둔 타일을 브라우저가 곧장 받고 OpenLayers 가
  // 3413 화면에 옮겨 그린다. `export` 로 3413 을 그려 달라고 할 수도 있지만(된다)
  // 한 장에 2~3 초·0.3 MB 이고, 구워 둔 타일은 1 초·15 KB 다. 두 투영 모두 등각이라
  // 옮겨 그려도 흐려지는 것이 적다. `Basisdata/` 의 것만 쓴다 — `Basisdata_Intern/`
  // 은 "Svalbardkartet 안에서만" 이라 적혀 있다. 둘 다 CC BY 4.0 이다
  var NPI_SAT = 'Satellite mosaic © <a href="https://data.npolar.no/" target="_blank" rel="noopener">Norsk Polarinstitutt</a>, contains modified Copernicus Sentinel data (CC BY 4.0)';
  var NPI_TOPO = 'Topographic map © <a href="https://data.npolar.no/" target="_blank" rel="noopener">Norsk Polarinstitutt</a> (CC BY 4.0)';
  BASEMAPS.npi_sat = {
    title: T("Sentinel-2 위성 (NPI)"),
    note: T("노르웨이 극지연구소 · Copernicus Sentinel-2. CC BY 4.0"),
    regions: ["svalbard"], needs: "EPSG:3413",
    make: function () { return npiTiles("NP_Satellitt_Svalbard_WMTS_25833", NPI_SAT); },
  };
  BASEMAPS.npi_topo = {
    title: T("스발바르 지형도 (NPI)"),
    note: T("노르웨이 극지연구소. CC BY 4.0"),
    regions: ["svalbard"], needs: "EPSG:3413",
    make: function () { return npiTiles("NP_Basiskart_Svalbard_WMTS_25833", NPI_TOPO); },
  };

  // ── 일본 배경 — 국토지리원 지리원 타일 (devlog 024) ──
  //
  // VWorld 의 짝이다. 브라우저가 곧장 부르고(열쇠 없음, CORS 열림), 출처만 적으면 된다.
  // 일본 밖은 줌 8 쯤까지만 그린다. **지질도 밑에는 담색(淡色)이 낫다** — VWorld
  // 백지도와 같은 까닭이다(004). 동아시아 탭에서도 고를 수 있다(`includes`)
  var GSI = '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル</a> (国土地理院)';
  BASEMAPS.gsi_pale = {
    title: T("일본 담색 지도 (국토지리원)"),
    note: T("일본 국토지리원. 지질도 밑에 깔기 좋다"),
    regions: ["japan"],
    make: function () { return gsiLayer("pale", "png", 18); },
  };
  BASEMAPS.gsi_std = {
    title: T("일본 표준 지도 (국토지리원)"),
    note: T("일본 국토지리원"),
    regions: ["japan"],
    make: function () { return gsiLayer("std", "png", 18); },
  };
  BASEMAPS.gsi_photo = {
    title: T("일본 항공사진 (국토지리원)"),
    note: T("일본 국토지리원. 일본 밖은 줌 8 까지만 그린다"),
    regions: ["japan"],
    make: function () { return gsiLayer("seamlessphoto", "jpg", 18); },
  };
  BASEMAPS.gsi_hillshade = {
    title: T("일본 음영기복 (국토지리원)"),
    note: T("일본 국토지리원. 지형을 지질도와 견줄 때"),
    regions: ["japan"],
    make: function () { return gsiLayer("hillshademap", "png", 16); },
  };

  // ── 해저 지형 — GEBCO (wetherilli 135) ──
  //
  // 온 바다의 수심과 땅의 높이를 한 장에 칠한 음영(15″ 격자, 약 450 m). 공공 도메인이고 출처만 밝힌다.
  // **서버가 받아 담는다**(`gebco/wms/`, wetherilli 184) — 한 장에 2 초 남짓이라 두 번째부터 빠르다. 정적 판은 서버가 없어
  // 곧장 부른다 — 열쇠가 없고 CORS 가 열려 있다. 지역마다 두므로 `regions` 가 없다.
  // 상류가 3857·4326 만 그려 주어, 극 평사도법 탭은 4326 을 받아 OpenLayers 가 옮겨 그린다(3857 은 극에서 끊긴다).
  // 한 장에 2 초 남짓 걸리고 격자가 450 m 라, 줌 9 보다 가까우면 더 묻지 않고 늘려 그린다
  var GEBCO = 'GEBCO Compilation Group (2026) <a href="https://www.gebco.net/data-products/gridded-bathymetry-data" target="_blank" rel="noopener">GEBCO 2026 Grid</a>';
  BASEMAPS.gebco = {
    title: T("GEBCO 해저 지형"),
    note: T("GEBCO 2026 (약 450 m). 바다의 수심과 땅의 높이를 음영으로. 공공 도메인. 항해에 쓰지 않는다"),
    make: function () { return gebcoLayer("GEBCO_LATEST"); },
  };
  BASEMAPS.gebco_subice = {
    title: T("GEBCO 해저·얼음 밑 지형"),
    note: T("GEBCO 2026 (약 450 m). 빙상을 걷어 낸 얼음 밑 기반암과 해저. 공공 도메인"),
    regions: ["greenland", "antarctica"],
    make: function () { return gebcoLayer("GEBCO_LATEST_SUB_ICE_TOPO"); },
  };

  function gebcoLayer(name) {
    var code = regionProj() === "EPSG:3857" ? "EPSG:3857" : "EPSG:4326";
    return new ol.layer.Tile({
      opacity: 0.9,
      source: new ol.source.TileWMS({
        url: STATIC ? "https://wms.gebco.net/mapserv" : BASE + "gebco/wms/",
        // 1.1.1 이면 4326 도 경도가 먼저다
        params: { LAYERS: name, VERSION: "1.1.1", FORMAT: "image/png", TILED: true },
        projection: code,
        tileGrid: ol.tilegrid.createXYZ({ extent: ol.proj.get(code).getExtent(), maxZoom: 9, tileSize: 512 }),
        crossOrigin: "anonymous",
        transition: 0,
        attributions: GEBCO,
      }),
    });
  }

  // ── 대만 배경 — 내정부 국토측회중심(NLSC) WMTS (wetherilli 141) ──
  // 국토지리원처럼 브라우저가 곧장 부른다 — CORS 가 열려 있고 열쇠가 없다. 3857 격자(GoogleMapsCompatible)라
  // 그대로 얹는다. **지질도 밑에는 회색 판이 낫다** — 일본의 담색과 같은 까닭이다. 대만 밖은 비어 있다
  var NLSC = '<a href="https://maps.nlsc.gov.tw/" target="_blank" rel="noopener">國土測繪圖資服務雲</a> (內政部國土測繪中心)';
  BASEMAPS.nlsc_grey = {
    title: T("대만 회색 지도 (국토측회중심)"),
    note: T("대만 내정부 국토측회중심. 지질도 밑에 깔기 좋다"),
    regions: ["taiwan"],
    make: function () { return nlscLayer("EMAP01", "jpg", 18); },
  };
  BASEMAPS.nlsc_emap = {
    title: T("대만 전자지도 (국토측회중심)"),
    note: T("대만 내정부 국토측회중심"),
    regions: ["taiwan"],
    make: function () { return nlscLayer("EMAP", "jpg", 18); },
  };
  BASEMAPS.nlsc_photo = {
    title: T("대만 정사영상 (국토측회중심)"),
    note: T("대만 내정부 국토측회중심. 대만 밖은 비어 있다"),
    regions: ["taiwan"],
    make: function () { return nlscLayer("PHOTO2", "jpg", 19); },
  };
  BASEMAPS.nlsc_hillshade = {
    title: T("대만 음영기복 (국토측회중심)"),
    note: T("대만 내정부 국토측회중심. 지형을 지질도와 견줄 때"),
    regions: ["taiwan"],
    make: function () { return nlscLayer("MOI_HILLSHADE", "png", 16); },
  };

  function nlscLayer(name, ext, maxZoom) {
    return new ol.layer.Tile({
      opacity: 0.85,
      source: new ol.source.XYZ({
        url: "https://wmts.nlsc.gov.tw/wmts/" + name + "/default/GoogleMapsCompatible/{z}/{y}/{x}",
        crossOrigin: "anonymous",
        maxZoom: maxZoom,
        attributions: NLSC,
      }),
    });
  }

  // 국토지리원의 주제 타일 셋 (wetherilli 156) — 담색·음영기복과 같은 창구다. 지질도와 견줄 때 고른다
  BASEMAPS.gsi_slope = {
    title: T("일본 경사량도 (국토지리원)"),
    note: T("일본 국토지리원. 기울기를 색으로 — 단층애·산사태 지형을 지질도와 견줄 때. 줌 15 까지"),
    regions: ["japan"],
    make: function () { return gsiLayer("slopemap", "png", 15); },
  };
  BASEMAPS.gsi_landcond = {
    title: T("일본 토지조건도 (국토지리원)"),
    note: T("일본 국토지리원. 산지·대지·저지·인공 지형을 가른 1:2만 5천 — 평야와 도시 둘레만 있다. 줌 16 까지"),
    regions: ["japan"],
    make: function () { return gsiLayer("lcmfc2", "png", 16); },
  };
  BASEMAPS.gsi_volcano = {
    title: T("일본 화산기본도 (국토지리원)"),
    note: T("일본 국토지리원. 활화산 둘레만 있는 정밀 지형도 — 그 밖은 빈다. 줌 17 까지"),
    regions: ["japan"],
    make: function () { return gsiLayer("vbm", "png", 17); },
  };

  // ── AWS 법선 타일로 그리는 음영·경사 (wetherilli 156) ──
  //
  // AWS 표고 타일의 `normal` 판은 RGB 가 땅의 법선(x 동, y 북, z 위 — 평지가 127·127·255)이다. 그것을 WebGL 셰이더로 칠한다 —
  // 음영은 북서 45° 빛과의 내적, 경사는 법선이 기운 정도. 브라우저가 곧장 부르고(열쇠 없음, CORS `*`) 줌 15 까지다.
  // 일본 밖(중국·대만)에는 국토지리원 음영이 없어 이것을 둔다
  var AWS_NORMAL = 'Terrain normals: <a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener">AWS Terrain Tiles</a>';
  function awsNormalLayer(kind) {
    var nx = ["-", ["*", ["band", 1], 2], 1];
    var ny = ["-", ["*", ["band", 2], 2], 1];
    var nz = ["-", ["*", ["band", 3], 2], 1];
    // 빛: 방위 315°·고도 45° → (−0.5, 0.5, 0.707)
    var shade = ["clamp", ["+", ["*", nx, -0.5], ["*", ny, 0.5], ["*", nz, 0.7071]], 0, 1];
    var steep = ["clamp", ["-", 1, nz], 0, 1];          // 0 이 평지, 1 이 낭떠러지
    return new ol.layer.WebGLTile({
      opacity: 0.85,
      source: new ol.source.XYZ({
        url: "https://s3.amazonaws.com/elevation-tiles-prod/normal/{z}/{x}/{y}.png",
        crossOrigin: "anonymous", maxZoom: 15, attributions: AWS_NORMAL, transition: 0,
      }),
      style: { color: kind === "slope"
        // 1 − cos(기울기): 0.015 ≈ 10°, 0.05 ≈ 18°, 0.12 ≈ 28°, 0.25 ≈ 41°. 거친 줌은 법선이 펴져 기울기가 작게 나온다
        ? ["interpolate", ["linear"], steep, 0, [250, 250, 245], 0.015, [245, 232, 165], 0.05, [235, 160, 75],
           0.12, [200, 60, 40], 0.25, [100, 20, 30]]
        : ["interpolate", ["linear"], shade, 0, [35, 35, 40], 0.5, [150, 150, 150], 0.75, [225, 225, 222],
           1, [255, 255, 255]] },
    });
  }
  BASEMAPS.aws_shade = {
    title: T("지형 음영 (AWS)"),
    note: T("AWS 표고 타일의 법선으로 그린 음영 — 북서에서 비춘다. 줌 15 까지"),
    regions: ["china", "taiwan"],
    make: function () { return awsNormalLayer("shade"); },
  };
  BASEMAPS.aws_slope = {
    title: T("경사 (AWS)"),
    note: T("AWS 표고 타일의 법선으로 칠한 기울기 — 흰 평지에서 붉은 낭떠러지까지. 줌 15 까지"),
    regions: ["china", "taiwan"],
    make: function () { return awsNormalLayer("slope"); },
  };

  function gsiLayer(name, ext, maxZoom) {
    return new ol.layer.Tile({
      opacity: 0.85,
      source: new ol.source.XYZ({
        url: "https://cyberjapandata.gsi.go.jp/xyz/" + name + "/{z}/{x}/{y}." + ext,
        crossOrigin: "anonymous",
        maxZoom: maxZoom,
        attributions: GSI,
      }),
    });
  }

  /** NPI 가 25833 으로 구워 둔 타일. 격자는 서비스의 `tileInfo` 그대로다 —
   *  원점 (-5120900, 9998100), 256 픽셀, 줌 0 이 21674.71 m, 18 단계. */
  function npiTiles(service, attribution) {
    var resolutions = [];
    for (var z = 0; z < 18; z++) resolutions.push(21674.7100160867 / Math.pow(2, z));
    return new ol.layer.Tile({
      source: new ol.source.XYZ({
        // 조건이 CC BY 4.0 이라 서버가 담는다 — 정적 판만 곧장 (wetherilli 200)
        url: STATIC ? "https://geodata.npolar.no/arcgis/rest/services/Basisdata/" + service + "/MapServer/tile/{z}/{y}/{x}"
                    : BASE + "npi/" + service + "/{z}/{y}/{x}",
        projection: "EPSG:25833",
        tileGrid: new ol.tilegrid.TileGrid({
          origin: [-5120900, 9998100],
          extent: [369976, 8221306, 878241, 9010719],
          resolutions: resolutions,
          tileSize: 256,
        }),
        crossOrigin: "anonymous",
        transition: 0,
        attributions: attribution,
      }),
    });
  }

  /** EOX 의 3857 타일. 극지 화면이면 OpenLayers 가 옮겨 그린다. */
  function eoxLayer(name, maxZoom, attribution) {
    return new ol.layer.Tile({
      opacity: 0.9,
      source: new ol.source.XYZ({
        url: "https://tiles.maps.eox.at/wmts/1.0.0/" + name + "/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg",
        crossOrigin: "anonymous",
        maxZoom: maxZoom,
        attributions: attribution,
      }),
    });
  }

  /** NASA GIBS 극지 WMTS. 격자는 3413·3031 이 같다 — 원점 (-4194304, 4194304),
   *  512 픽셀, 줌 0 이 8192 m. `500m` 격자는 줌 4 까지다. 서버가 같은 경로를 받아 담는다(`gibs/`, wetherilli 184) —
   *  정적 판만 곧장 부른다 */
  function gibsLayer(epsg, name, maxZoom) {
    var resolutions = [];
    for (var z = 0; z <= maxZoom; z++) resolutions.push(8192 / Math.pow(2, z));
    return new ol.layer.Tile({
      source: new ol.source.XYZ({
        url: STATIC ? "https://gibs.earthdata.nasa.gov/wmts/epsg" + epsg + "/best/" + name + "/default/500m/{z}/{y}/{x}.jpeg"
                    : BASE + "gibs/" + epsg + "/" + name + "/{z}/{y}/{x}.jpeg",
        projection: "EPSG:" + epsg,
        tileGrid: new ol.tilegrid.TileGrid({
          extent: [-4194304, -4194304, 4194304, 4194304],
          origin: [-4194304, 4194304],
          resolutions: resolutions,
          tileSize: 512,
        }),
        crossOrigin: "anonymous",
        attributions: GIBS,
      }),
    });
  }

  /** Esri 의 남극 위성 모자이크(Earthstar Geographics TerraColor, 15 m) — 3031 로 구워 둔 타일이라
   *  옮겨 그리지 않는다 (040). 격자는 서비스의 `tileInfo` 그대로다 — 원점 (-33699550.99203,
   *  33699551.01703), 256 픽셀, 줌 0 이 238810.81 m. **영상은 줌 13(29 m)까지다** — 그 위는
   *  "Map data not yet available" 타일을 주므로 격자를 13 에서 끊어 OpenLayers 가 늘려 그리게 한다 */
  function esriAntarcticLayer() {
    var resolutions = [];
    for (var z = 0; z <= 13; z++) resolutions.push(238810.813354 / Math.pow(2, z));
    return new ol.layer.Tile({
      source: new ol.source.XYZ({
        url: "https://services.arcgisonline.com/arcgis/rest/services/Polar/Antarctic_Imagery/MapServer/tile/{z}/{y}/{x}",
        projection: "EPSG:3031",
        tileGrid: new ol.tilegrid.TileGrid({
          origin: [-33699550.99203, 33699551.01703],
          extent: [-4524537.46, -4524537.92, 4524539.62, 4524539.16],
          resolutions: resolutions,
          tileSize: 256,
        }),
        crossOrigin: "anonymous",
        attributions: ESRI_ANTARCTIC,
      }),
    });
  }

  /** 남극 해저·빙저 지형 IBCSO v2 — 우리 서버가 GeoMAP 과 같은 3031 격자로 잘라 둔 것 (047).
   *  원본이 500 m 라 줌 6 까지 자르고, 그 위는 OpenLayers 가 늘려 그린다. 출처는 CC BY 라 늘 적는다 */
  var IBCSO = 'IBCSO v2 (Dorschel et al., 2022, <a href="https://doi.org/10.1594/PANGAEA.937574" target="_blank" rel="noopener">PANGAEA</a>, CC BY 4.0)';
  function ibcsoLayer(which) {
    var resolutions = [];
    var width = GEOMAP_GRID.extent[2] - GEOMAP_GRID.extent[0];
    for (var z = 0; z <= 6; z++) resolutions.push(width / GEOMAP_GRID.tileSize / Math.pow(2, z));
    return new ol.layer.Tile({
      source: new ol.source.XYZ({
        url: BASE + "ibcso/" + which + "/{z}/{x}/{y}.webp" + vq(which),
        projection: "EPSG:3031",
        tileGrid: new ol.tilegrid.TileGrid({
          extent: GEOMAP_GRID.extent,
          origin: [GEOMAP_GRID.extent[0], GEOMAP_GRID.extent[3]],
          resolutions: resolutions,
          tileSize: GEOMAP_GRID.tileSize,
        }),
        attributions: IBCSO,
      }),
    });
  }

  /** PGC 의 표고 ImageServer 에서 음영을 그려 받는다 (기본 `Hillshade Gray`, `fn` 으로 다른 그리는 법).
   *  미리 구운 타일이 아니라 부를 때마다 PGC 가 그린다 — 한 장에 1~2 초.
   *  그래서 타일을 512 로 키워 부르는 수를 줄인다. */
  function pgcHillshade(service, code, attribution, fn) {
    return new ol.layer.Tile({
      opacity: 0.85,
      source: new ol.source.TileArcGISRest({
        url: "https://di-pgc.img.arcgis.com/arcgis/rest/services/" + service + "/ImageServer",
        params: { renderingRule: JSON.stringify({ rasterFunction: fn || "Hillshade Gray" }), FORMAT: "jpgpng" },
        projection: code,
        tileGrid: ol.tilegrid.createXYZ({ extent: ol.proj.get(code).getExtent(), tileSize: 512, maxZoom: 16 }),
        crossOrigin: "anonymous",
        attributions: attribution,
      }),
    });
  }

  var baseLayer = null;

  // ── VWorld 를 곧장 받지 못하면 서버를 거친다 (033) ──
  //
  // 배경지도는 브라우저가 `api.vworld.kr` 에서 곧장 받는다(003). 그런데 **사내
  // VPN 이 그 연결을 끊는다**(`ERR_CONNECTION_RESET`) — VPN 은 이 서버만
  // 통과시킨다. 그래서 VWorld 배경을 처음 깔 때 한 장을 곧장 받아 보고,
  // **연결이 끊기면** 그 뒤로는 VWorld 타일을 전부 `vworld/` 로 받는다.
  //
  // 받아 보는 한 장은 `no-store` 다 — 브라우저가 들고 있던 것이 나오면
  // 끊긴 길을 붙은 줄로 안다. VWorld 가 오류를 **답한** 것은 끊긴 것이 아니라
  // 곧장 받기를 그대로 둔다. 서버를 거쳐도 같은 오류가 올 뿐이다.
  var vworldRelay = false;
  var vworldProbed = false;
  var vworldSources = [];

  /** VWorld 테마 위성영상 — 남극 두 기지 둘레(2013) 와 그 범위(서, 남, 동, 북). 캐퍼빌리티가 준 범위다.
   *  **자리 차례가 z/x/y** 로 배경지도와 반대다(004). 중계 길은 배경지도와 같은 꼴로 받고
   *  서버(`vworld.WMTS_THEMES`)가 바꿔 부른다 (wetherilli 093) */
  var VWORLD_THEMES = {
    AntarcticaSejong: [-58.8196, -62.2679, -58.6073, -62.1697],
    AntarcticaJangbogo: [163.9775, -74.6491, 164.3443, -74.5501],
  };

  function vworldUrl(layer, ext) {
    if (vworldRelay) return BASE + "vworld/" + layer + "/{z}/{y}/{x}." + ext;
    if (VWORLD_THEMES[layer]) {
      return "https://api.vworld.kr/req/wmts/1.0.0/" + encodeURIComponent(vworldKey)
             + "/Satellite/themes/cities/2013/" + layer + "/{z}/{x}/{y}.png";
    }
    return "https://api.vworld.kr/req/wmts/1.0.0/" + encodeURIComponent(vworldKey)
           + "/" + layer + "/{z}/{y}/{x}." + ext;
  }

  /** 세종·장보고 기지 위성 — 영상이 기지 둘레 10 km 남짓뿐이라 밑에 REMA 음영을 깔고 그 위에
   *  두 기지를 제 범위 안에서만 부른다. 줌 10–18 (2026-09-30 에 받아 봤다) */
  function vworldStationsLayer() {
    var layers = [pgcHillshade("rema_latest", "EPSG:3031", PGC_REMA)];
    Object.keys(VWORLD_THEMES).forEach(function (name) {
      layers.push(new ol.layer.Tile({
        extent: ol.proj.transformExtent(VWORLD_THEMES[name], "EPSG:4326", "EPSG:3031"),
        source: vworldSource(name, "png", {
          minZoom: 10, maxZoom: 18,
          attributions: '© <a href="https://www.vworld.kr/" target="_blank" rel="noopener">VWorld</a>',
        }),
      }));
    });
    return new ol.layer.Group({ layers: layers });
  }

  /** VWorld WMTS 한 겹의 소스. 자리 차례가 z/y/x 다. */
  function vworldSource(layer, ext, extra) {
    var opts = { url: vworldUrl(layer, ext), crossOrigin: "anonymous", maxZoom: 19 };
    Object.keys(extra || {}).forEach(function (k) { opts[k] = extra[k]; });
    var source = new ol.source.XYZ(opts);
    vworldSources.push({ source: source, layer: layer, ext: ext });
    probeVworld();
    return source;
  }

  function probeVworld() {
    // 정적 판에는 돌아갈 서버(`vworld/`)가 없다 — 끊기면 끊긴 대로 둔다 (wetherilli 164)
    if (vworldProbed || vworldRelay || STATIC) return;
    vworldProbed = true;
    var ctl = new AbortController();
    var timer = setTimeout(function () { ctl.abort(); }, 8000);
    fetch("https://api.vworld.kr/req/wmts/1.0.0/" + encodeURIComponent(vworldKey)
          + "/Base/7/50/109.png", { cache: "no-store", signal: ctl.signal })
      .then(function () { clearTimeout(timer); }, function () {
        clearTimeout(timer);
        vworldRelay = true;
        vworldSources.forEach(function (s) { s.source.setUrl(vworldUrl(s.layer, s.ext)); });
      });
  }

  /** VWorld 의 한 장짜리 배경(`white`·`midnight`). */
  function vworldPlain(name) {
    return new ol.layer.Tile({
      opacity: 0.85,
      source: vworldSource(name, "png", {
        attributions: '© <a href="https://www.vworld.kr/" target="_blank" rel="noopener">VWorld</a>',
      }),
    });
  }

  function setBasemap(key) {
    if (baseLayer) {
      map.removeLayer(baseLayer);
      baseLayer = null;
    }
    var spec = BASEMAPS[key];
    if (spec && spec.make) {
      baseLayer = spec.make();
      baseLayer.setZIndex(0);
      map.getLayers().insertAt(0, baseLayer);
    }
    // 배경도 지역마다 따로 기억한다 — 한국의 VWorld 는 그린란드에 없다
    store(stateKey("gsm.basemap"), key);
  }

  function labelsOn() {
    try {
      return localStorage.getItem("gsm.basemapLabels") !== "0";
    } catch (e) { return true; }
  }

  /** 배경지도의 지명 겹을 켜고 끈다. 겹이 없는 배경이면 아무 일도 안 한다. */
  function setLabels(on) {
    try { localStorage.setItem("gsm.basemapLabels", on ? "1" : "0"); } catch (e) { /* 사생활 모드 */ }
    if (!baseLayer || !baseLayer.getLayers) return;
    baseLayer.getLayers().forEach(function (l) {
      if (l.get("gsmLabels")) l.setVisible(on);
    });
  }

  function savedBasemap() {
    try {
      var key = stored(stateKey("gsm.basemap"));
      if (key && BASEMAPS[key]) return key;
    } catch (e) { /* 사생활 모드 */ }
    // 극지는 지역이 고른 배경으로 시작한다. 상류 지질도가 한국처럼 지명·
    // 해안선을 그려 주지 않아, 바탕이 없으면 어디를 보는지 모른다
    var own = REGIONS[region].basemap;
    if (own && BASEMAPS[own]) return own;
    // 열쇠가 있으면 위성+지명으로 시작한다. 지질을 지형·시설과 견주어
    // 보는 것이 예사라 빈 바탕보다 낫다.
    if (BASEMAPS.vworld_hybrid && REGIONS[region].vworld) return "vworld_hybrid";
    return "none";
  }

  function initMap() {
    pointLayerGroup = new ol.layer.Group({ layers: [] });
    personalGroup = new ol.layer.Group({ layers: [] });

    // 재는 것과 찍은 점. **어느 것도 저장하지 않는다** — 새로 고치면 사라진다.
    // 점묶음(`PointSet`)과 다른 자리다. 저쪽은 올린 자료라 남고, 이쪽은
    // 지금 보면서 재는 것이라 남을 까닭이 없다.
    measureSource = new ol.source.Vector();
    measureLayer = new ol.layer.Vector({ source: measureSource, style: measureStyle });
    tempSource = new ol.source.Vector();
    tempLayer = new ol.layer.Vector({ source: tempSource, style: tempStyle });
    // 잡은 범위. 재는 것(`measureSource`)과 달리 여럿을 두고 목록에 남긴다
    rangeSource = new ol.source.Vector();
    rangeLayer = new ol.layer.Vector({ source: rangeSource, style: rangeStyle });
    // 좌표를 찍어 찾아간 자리. 한 번에 하나만 둔다.
    foundSource = new ol.source.Vector();
    foundLayer = new ol.layer.Vector({ source: foundSource, style: foundStyle });

    map = new ol.Map({
      target: "map",
      layers: [pointLayerGroup, personalGroup, rangeLayer, measureLayer, tempLayer, foundLayer],
      view: makeView(regionProj()),
      // 축척 막대는 제 자리(왼쪽 아래)에 두면 좌표 막대가 덮는다.
      // 그래서 좌표 막대 바로 위의 칸에 붙인다.
      // OL 의 나침반(`rotate`)은 끈다 — 돌린 지도는 "자세" 묶음의 방위 단추가 되돌린다 (wetherilli 114)
      controls: ol.control.defaults.defaults({ attributionOptions: { collapsible: true }, rotate: false })
        .extend([
          new ol.control.ScaleLine({ target: document.getElementById("scalebar"), bar: true, steps: 2, text: true, minWidth: 130 }),
        ]),
    });

    popupOverlay = new ol.Overlay({
      element: document.getElementById("popup"),
      // 아래 가장자리에는 좌표 막대가 덮여 있다. 여백을 주지 않으면 팝업
      // 아랫단이 막대 밑으로 들어간다. 여백은 사방에 걸려서 휴대폰(390 px)에서는 320 px 팝업 + 72 px 둘이 들지 않아
      // 팝업이 왼쪽 밖으로 밀렸다 — 좁은 화면은 12 px 로 (휴대폰 시험이 잡았다, wetherilli 193)
      autoPan: { animation: { duration: 200 }, margin: popupMargin() },
      offset: [0, -8],
      positioning: "bottom-center",
    });
    map.addOverlay(popupOverlay);

    showProjection(false);
    showZoom();
    initPanelHandle();
    initProfile();
    map.on("moveend", showZoom);
    map.on("moveend", renderEdges);
    map.on("moveend", saveView);
    map.on("moveend", function () { if (GEONAVI.here && GEONAVI.open) renderGeonavi(); });   // wetherilli 171
    map.on("moveend", refreshExtentLegends);
    window.addEventListener("resize", renderEdges);
    map.on("singleclick", onClick);
    initAttitudes();
    rightDragRotate(map);
    initCompass();
  }

  /** 우클릭한 채 끌면 지도가 돈다 — 화면 가운데를 축으로, 누른 자리가 가운데를 도는 만큼 (wetherilli 114).
   *  OL 의 DragRotate 와 같은 셈인데, 그것은 왼쪽 단추만 받아 손으로 단다. 지도 위의 오른쪽 단추 메뉴는
   *  늘 막는다 — 리눅스·맥은 누르는 순간 메뉴가 떠서 끌 틈이 없다. 나란히 보기의 오른쪽 지도에도 단다 */
  function rightDragRotate(target) {
    var viewport = target.getViewport();
    var last = null, pointer = null;
    function angle(e) {
      var r = viewport.getBoundingClientRect();
      return Math.atan2(r.top + r.height / 2 - e.clientY, e.clientX - r.left - r.width / 2);
    }
    function end(e) {
      if (last === null || e.pointerId !== pointer) return;
      last = pointer = null;
      // 끝날 때 제약을 푼다 — 0° 가까이 놓으면 정북으로 붙는다(OL 의 `constrainRotation`)
      target.getView().endInteraction();
    }
    viewport.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    viewport.addEventListener("pointerdown", function (e) {
      if (e.button !== 2 || e.pointerType !== "mouse") return;
      e.preventDefault();
      last = angle(e);
      pointer = e.pointerId;
      viewport.setPointerCapture(pointer);
      target.getView().beginInteraction();
    });
    viewport.addEventListener("pointermove", function (e) {
      if (last === null || e.pointerId !== pointer) return;
      var now = angle(e);
      target.getView().adjustRotation(-(now - last));
      last = now;
    });
    viewport.addEventListener("pointerup", end);
    viewport.addEventListener("pointercancel", end);
    viewport.addEventListener("lostpointercapture", end);
  }

  /** "자세" 묶음의 방위 단추 — 바늘이 지도의 본래 위쪽(3857 은 북쪽, 극지는 투영의 위쪽)을 가리키고,
   *  누르면 처음 방위로 되돌린다. 돌지 않았으면 흐리게 둔다 — 눌러도 그대로인 까닭을 보인다 (wetherilli 114) */
  function initCompass() {
    var button = document.getElementById("tool-compass");
    var needle = document.getElementById("compass-needle");
    var shown = null;
    button.addEventListener("click", function () {
      map.getView().animate({ rotation: 0, duration: 400 });
    });
    map.on("postrender", function () {
      var r = map.getView().getRotation();
      if (r === shown) return;
      shown = r;
      needle.setAttribute("transform", "rotate(" + (r * 180 / Math.PI).toFixed(1) + " 12 12)");
      button.disabled = Math.abs(r) < 1e-6;
    });
  }

  /** 투영 하나의 보기. **OpenLayers 는 보기의 투영을 바꾸지 못한다** — 지역을
   *  바꿔 투영이 달라지면 보기를 새로 만든다 (`setProjection`). */
  function makeView(code) {
    if (code === "EPSG:3857") {
      return new ol.View({
        // 남한 전체가 들어오는 자리
        center: ol.proj.fromLonLat([127.8, 36.2]),
        zoom: 7,
        minZoom: 5,
        maxZoom: 19,
      });
    }
    // 극지. 투영 범위 밖으로 끌려 나가지 않게 가둔다. 줌 0 이 투영 범위
    // 한 장이라, 남극은 화면의 줌이 GeoMAP 타일의 줌과 같다
    return new ol.View({
      projection: code,
      center: [0, 0],
      zoom: 2,
      minZoom: 0,
      maxZoom: 17,
      extent: ol.proj.get(code).getExtent(),
    });
  }

  /** 처음 여는 자리로 간다 — 극지는 범위(`home`)로, 한국은 가운데·줌으로. */
  function goHome() {
    var spec = REGIONS[region];
    var view = map.getView();
    if (spec.home && !isMercator()) {
      // 아래 여백은 좌표 막대가 덮는 만큼이다
      view.fit(spec.home, { size: map.getSize() || [1200, 800], padding: [8, 8, 56, 8] });
      return;
    }
    view.setCenter(fromLL(spec.center));
    view.setZoom(spec.zoom);
  }

  /** 화면의 투영을 바꾼다. 보기를 새로 만들고, 화면에 얹힌 벡터(찍은 점·잰 선
   *  ·범위·점묶음)를 새 투영으로 옮긴다. 점묶음은 새 투영으로 다시 읽는다 —
   *  서버의 GeoJSON 은 위경도라 읽을 때 투영을 정한다. */
  function setProjection(code) {
    var from = viewProj();
    if (from.getCode() === code) return;
    map.setView(makeView(code));
    // **처음 그린 것의 위경도에서 옮긴다.** 투영에서 투영으로 곧장 옮기면
    // 남극에서 찍은 점이 한국(3857)을 거쳐 올 때 남위 85° 에서 잘려 돌아온다
    [tempSource, measureSource, rangeSource, foundSource].forEach(function (source) {
      source.getFeatures().forEach(function (f) {
        var ll = f.get("_ll") || f.getGeometry().clone().transform(from, "EPSG:4326");
        f.set("_ll", ll);
        f.setGeometry(ll.clone().transform("EPSG:4326", code));
      });
    });
    pointLayerGroup.getLayers().clear();
    pointLayers = {};
    renderPointSets();
    drawPersonal();
    // 나란히 보기의 오른쪽 지도는 같은 보기를 나눠 쓴다
    if (map2) map2.setView(map.getView());
    showProjection(true);
  }

  /** 화면 투영의 이름표 — 축척 막대 옆에 EPSG 번호를 적는다. 극지와 중위도를
   *  오가면 투영이 바뀌는데 화면만 보고는 모르니, 늘 적어 두고 바뀔 때 잠깐 밝힌다. */
  var PROJ_NAMES = {
    "EPSG:3857": "웹 메르카토르",
    "EPSG:3413": "북극 평사도법",
    "EPSG:3031": "남극 평사도법",
    "EPSG:3978": "캐나다 람베르트",
  };
  function showProjection(changed) {
    var el = document.getElementById("projbadge");
    if (!el) return;
    var code = viewProj().getCode();
    el.textContent = code;
    el.title = PROJ_NAMES[code] ? T(PROJ_NAMES[code]) : code;
    if (!changed) return;
    el.classList.remove("flash");
    void el.offsetWidth;  // 애니메이션을 처음부터 다시 돌린다
    el.classList.add("flash");
  }

  /** 패널 접기 — 지도 칸 왼쪽 가장자리의 손잡이. 접힌 채로 두었는지는 이 브라우저가 기억한다 (jikhanjung 007). */
  var PANEL_KEY = "gsm.panelFolded";
  function initPanelHandle() {
    var handle = document.getElementById("panel-handle");
    if (!handle) return;
    function apply(folded, save) {
      document.body.classList.toggle("panel-folded", folded);
      handle.textContent = folded ? ">" : "<";
      handle.title = folded ? T("패널을 편다") : T("패널을 접는다");
      handle.setAttribute("aria-expanded", folded ? "false" : "true");
      if (save) {
        try { localStorage.setItem(PANEL_KEY, folded ? "1" : "0"); } catch (e) { /* 사생활 모드 */ }
      }
      // 지도 칸의 폭이 바뀌었으니 다시 잰다
      setTimeout(function () { map.updateSize(); if (typeof map2 !== "undefined" && map2) map2.updateSize(); renderEdges(); }, 0);
    }
    // 휴대폰은 접힌 채로 연다 — 편 채로 두었을 때만 편다 (wetherilli 128)
    var saved = window.matchMedia("(max-width: 760px)").matches;
    try { var kept = localStorage.getItem(PANEL_KEY); if (kept) saved = kept === "1"; } catch (e) { /* 사생활 모드 */ }
    if (saved) apply(true, false);
    handle.addEventListener("click", function () {
      apply(!document.body.classList.contains("panel-folded"), true);
    });
  }

  /** 지금의 줌 — EPSG 번호 옆에 늘 적는다. 맞춰 보기(fit)를 하면 소수가 되므로 한 자리까지 (jikhanjung 006). */
  function showZoom() {
    var el = document.getElementById("zoombadge");
    if (!el || !map) return;
    var z = map.getView().getZoom();
    if (z === undefined || z === null || isNaN(z)) { el.textContent = ""; return; }
    var r = Math.round(z * 10) / 10;
    el.textContent = T("줌 {z}", { z: r % 1 === 0 ? r.toFixed(0) : r.toFixed(1) });
    el.title = T("줌 수준 — 한 단계 오를 때마다 두 배로 가까워진다");
  }

  /** 켠 레이어를 화면 순서에 맞춰 다시 쌓는다.
   *  `active[0]` 이 맨 앞이므로 OpenLayers 에는 거꾸로 넣는다. */
  function restack() {
    map.getLayers().getArray().slice().forEach(function (l) {
      if (l.get("gsm")) map.removeLayer(l);
    });
    // 배경지도는 있으면 z=0 에 있다. 켠 레이어는 그 위에 쌓는다.
    var baseCount = baseLayer ? 1 : 0;
    active.slice().reverse().forEach(function (entry, index) {
      entry.layer.setZIndex(baseCount + index);
      entry.layer.set("gsm", true);
      map.getLayers().insertAt(baseCount + index, entry.layer);
    });
    pointLayerGroup.setZIndex(500);
    personalGroup.setZIndex(520);
    rangeLayer.setZIndex(550);
    measureLayer.setZIndex(600);
    tempLayer.setZIndex(700);
    foundLayer.setZIndex(800);
    if (attitudeLayer) attitudeLayer.setZIndex(520);
    renderActive();
    refreshAttitudes();
    saveLayers();
    if (typeof refreshCompare === "function") refreshCompare();
  }

  // ── 기억하기 ─────────────────────────────────────────────────────
  //
  // 켠 레이어(차례·투명도)와 보던 자리를 브라우저에 둔다. 새로 고치면 다
  // 풀리던 것이 불편했다. **이 브라우저에만 남는다** — 서버에 올리지 않고,
  // 사생활 모드처럼 저장이 막혀도 처음 화면으로 돌 뿐 멈추지 않는다.

  var restoring = false;   // 되살리는 동안에는 저장하지 않는다

  function saveLayers() {
    if (restoring) return;
    var rows = active.map(function (e) {
      var out = { name: e.name, opacity: Math.round(e.opacity * 100) / 100 };
      // 지질도Navi 판은 카탈로그 밖이라 행을 함께 둔다 — 되살릴 때 판 목록을 기다리지 않게 (wetherilli 171)
      if (byName[e.name] && byName[e.name].upstream === "geonavi") out.row = geonaviSaved(byName[e.name]);
      return out;
    });
    store(stateKey("gsm.layers"), JSON.stringify(rows));
  }

  /** 보던 자리는 **위경도와 줌, 그리고 그 줌을 잰 투영**으로 둔다. 줌은
   *  투영마다 뜻이 달라서, 투영이 바뀌면 땅 위의 픽셀 크기로 옮긴다 (`restoreState`). */
  function saveView() {
    var view = map.getView();
    var center = toLL(view.getCenter());
    var state = { lon: +center[0].toFixed(5), lat: +center[1].toFixed(5),
                  zoom: +view.getZoom().toFixed(2), proj: view.getProjection().getCode() };
    store(stateKey("gsm.view"), JSON.stringify(state));
  }

  function readJson(key) {
    try { return JSON.parse(stored(key) || "null"); } catch (e) { return null; }
  }

  /** 기억한 것이 있으면 되살리고 true. 처음 온 사람이면 false. */
  function restoreState() {
    var view = readJson(stateKey("gsm.view"));
    var code = viewProj().getCode();
    // 투영을 적지 않은 것은 이 판(017) 전에 메르카토르로 기억한 것이다
    var savedProj = view && view.proj || "EPSG:3857";
    if (view && savedProj !== code && !view.proj && REGIONS[region].forgetOldView) {
      // 처음 온 것처럼 연다 — 기억을 지워야 대표 레이어도 켜진다
      unstore(stateKey("gsm.view"));
      unstore(stateKey("gsm.layers"));
      return false;
    }
    if (view && isFinite(view.lon) && isFinite(view.lat) && isFinite(view.zoom)) {
      map.getView().setCenter(fromLL([view.lon, view.lat]));
      if (savedProj === code) map.getView().setZoom(view.zoom);
      else map.getView().setResolution(carryZoom(view, savedProj));
    }
    var rows = readJson(stateKey("gsm.layers"));
    if (!Array.isArray(rows)) return false;
    restoring = true;
    // addLayer 는 맨 위에 얹는다. 그래서 맨 아래 것부터 얹는다.
    rows.slice().reverse().forEach(function (row) {
      if (row && !byName[row.name] && row.row) geonaviRestore(row.name, row.row);
      if (!row || !byName[row.name]) return;     // 카탈로그에서 내려간 레이어
      addLayer(row.name);
      var entry = active[0];
      if (entry.name === row.name && isFinite(row.opacity)) {
        entry.opacity = Math.min(1, Math.max(0, row.opacity));
        entry.layer.setOpacity(entry.opacity);
      }
    });
    restoring = false;
    renderActive();
    saveLayers();
    return true;
  }

  /** 다른 투영에서 기억한 줌을 지금 투영의 해상도로. 기억한 자리에서 한 픽셀이
   *  땅 위의 몇 m 였는지를 재고, 지금 투영에서 같은 m 가 되게 한다. */
  function carryZoom(view, savedProj) {
    var old = ol.proj.get(savedProj) || ol.proj.get("EPSG:3857");
    var oldExtent = old.getExtent();
    var oldRes = ol.extent.getWidth(oldExtent) / 256 / Math.pow(2, view.zoom);
    var ground = ol.proj.getPointResolution(old, oldRes, ol.proj.fromLonLat([view.lon, view.lat], old));
    var here = map.getView().getCenter();
    return ground / ol.proj.getPointResolution(viewProj(), 1, here);
  }

  /** 스발바르 도폭 하나(`npolar:svalbard_sheets@A4G`)의 카탈로그 행. 카탈로그에는 도폭
   *  스캔 전부만 있어, 밑 행을 베껴 이름·제목만 바꾼다 (P01 6 단계). */
  function sheetRow(name, label) {
    var at = name.indexOf("@");
    var base = at > 0 && byName[name.slice(0, at)];
    var code = name.slice(at + 1);
    if (!base || !/^[A-Z]{1,2}\d{1,4}G$/.test(code)) return null;
    var row = Object.assign({}, base, {
      name: name,
      title: label ? T("도폭 {code} {name}", { code: code, name: label }) : T("도폭 {code}", { code: code }),
    });
    byName[name] = row;
    regionOfLayer[name] = regionOfLayer[base.name];
    return row;
  }

  function addLayer(name) {
    if (active.some(function (e) { return e.name === name; })) return;
    var row = byName[name] || sheetRow(name);
    if (!row) return;
    // 점 레이어(`kind: points`)는 밑을 가리지 않으므로 처음부터 진하게 둔다.
    // 면을 싣는 것(얀마옌 지질 단위)은 카탈로그가 투명도를 따로 준다
    var opacity = row.opacity || (row.kind === "points" ? 1 : DEFAULT_OPACITY);
    active.unshift({
      name: name,
      title: layerTitle(name),
      opacity: opacity,
      legendOpen: false,
      layer: makeLayer(name),
    });
    restack();
  }

  function removeLayer(name) {
    var index = active.findIndex(function (e) { return e.name === name; });
    if (index < 0) return;
    map.removeLayer(active[index].layer);
    active.splice(index, 1);
    restack();
  }

  function move(name, delta) {
    var index = active.findIndex(function (e) { return e.name === name; });
    var target = index + delta;
    if (index < 0 || target < 0 || target >= active.length) return;
    var moved = active.splice(index, 1)[0];
    active.splice(target, 0, moved);
    restack();
  }

  /** `name` 을 `target` 자리(0 이 맨 위)로 옮긴다. 끌어 놓을 때 쓴다. */
  function moveTo(name, target) {
    var index = active.findIndex(function (e) { return e.name === name; });
    if (index < 0) return;
    var moved = active.splice(index, 1)[0];
    if (index < target) target -= 1;          // 빼낸 만큼 뒤쪽 자리가 당겨진다
    active.splice(Math.max(0, Math.min(target, active.length)), 0, moved);
    restack();
  }

  // 끌고 있는 레이어. 끌기는 줄의 머리에서만 시작한다 — 줄 전체를 끌 수
  // 있게 하면 투명도 막대를 움직이다 줄이 끌려간다.
  var dragName = null;

  function wireDrag(li, head, entry, index) {
    head.draggable = true;
    head.classList.add("grab");
    head.addEventListener("dragstart", function (e) {
      dragName = entry.name;
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", entry.name);
      li.classList.add("dragging");
    });
    head.addEventListener("dragend", function () {
      dragName = null;
      document.querySelectorAll("#active-list li").forEach(function (x) {
        x.classList.remove("dragging", "drop-before", "drop-after");
      });
    });
    function after(e) {
      var box = li.getBoundingClientRect();
      return e.clientY > box.top + box.height / 2;
    }
    li.addEventListener("dragover", function (e) {
      if (!dragName) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      li.classList.toggle("drop-after", after(e));
      li.classList.toggle("drop-before", !after(e));
    });
    li.addEventListener("dragleave", function () {
      li.classList.remove("drop-before", "drop-after");
    });
    li.addEventListener("drop", function (e) {
      if (!dragName) return;
      e.preventDefault();
      moveTo(dragName, index + (after(e) ? 1 : 0));
    });
  }

  // ── 레이어 패널 ─────────────────────────────────────────────────

  // 늘 펼쳐 두는 기본 지질도는 지역마다 다르다 — `REGIONS[지역].base`.
  // 한국의 지체구조도는 상류가 "그 밖" 에 넣어 두었지만 지질도로 늘 보는
  // 것이라 기본으로 끌어온다.

  /** 카탈로그.
   *
   *  **기본 지질도 몇 장만 펼치고 나머지는 모두 "추가 지질도" 안으로
   *  접는다.** 61 개를 한 줄로 늘어놓으면 패널이 화면보다 길어져서 아래의
   *  "그리기" 칸이 밀려 안 보인다. 늘 보는 것과 찾아서 켜는 것의 차이를
   *  접기로 나타낸다. 추가 지질도 안에서는 상류의 레이어군을 그대로 쓴다.
   */
  // ── 레이어 목록 (wetherilli 133) ─────────────────────────────────
  //
  // 줄을 눌러 켜고 끈다 — 줄에 다른 기능이 없어 체크박스를 겨눌 까닭이 없다. 체크박스 자리에는 **상류 딱지**를 두고,
  // 같은 상류가 이어지는 줄은 딱지 밑으로 줄을 그어 묶는다(어느 레이어가 어느 기관 것인지 한눈에). 레이어군 머리에는
  // "모두 켜기" — 그 군을 다 켜고, 다 켜져 있으면 "모두 끄기" 가 된다.

  //: 상류의 짧은 이름 — 기관 이름이라 옮기지 않는다
  var UPSTREAM_TAGS = {
    kigam: "KIGAM", vworld: "VWorld", geus: "GEUS", grportal: "GRL", npolar: "NPI", janmayen: "NPI",
    gsj: "GSJ", gsitile: "GSIJ", geonavi: "GSJ", ccop: "CCOP", gsmma: "GSMMA", emodnet: "EMOD", ngu: "NGU", gtk: "GTK", sgu: "SGU", bgs: "BGS", brgm: "BRGM", egdi: "EGDI", bgr: "BGR", igme: "IGME", gsi: "GSI", gsni: "GSNI", sgc: "SGC", sgb: "SGB", ingemmet: "INGEMMET", iige: "IIGE", cgmw: "CGMW", aga: "BGS", cgs: "CGS", gsn: "GSN", mrdata: "USGS", sgm: "SGM", nrcan: "NRCan", ogs: "OGS", sigeom: "SIGÉOM", ygs: "YGS", ga: "GA", ispra: "ISPRA", lneg: "LNEG", swisstopo: "swisstopo", segemar: "SEGEMAR", dinamige: "DINAMIGE", geomap: "GeoMAP", geo3al: "USGS", kopri: "KOPRI", pgc: "PGC", ibcso: "IBCSO",
    phyloserver: "LAB", peninsula: "LAB",
    // 지구 자료 점(wetherilli 185) — 기관이 넷이라 딱지는 하나로 두고 이름은 레이어 제목이 적는다
    earth: "EARTH",
    kigam50k: "KIGAM",
  };
  var UPSTREAM_NAMES = {
    kigam: T("한국지질자원연구원"), vworld: T("브이월드(국토교통부)"), geus: T("덴마크·그린란드 지질조사소"), grportal: T("그린란드 정부 포털"),
    npolar: T("노르웨이 극지연구소"), janmayen: T("노르웨이 극지연구소"), gsj: T("일본 지질조사종합센터"), gsitile: T("일본 국토지리원"), geonavi: T("일본 지질조사종합센터"), ccop: "CCOP",
    gsmma: T("대만 지질조사·광업관리중심"),
    emodnet: "EMODnet Geology",
    ngu: T("노르웨이 지질조사소"), gtk: T("핀란드 지질조사소"), sgu: T("스웨덴 지질조사소"),
    bgs: T("영국 지질조사소"), brgm: T("프랑스 지질광물조사소"), egdi: "EGDI (EuroGeoSurveys)",
    bgr: T("독일 연방 지구과학·자원청"), igme: T("스페인 지질광물연구소"), gsi: T("아일랜드 지질조사소"),
    sgc: T("콜롬비아 지질조사소"), sgb: T("브라질 지질조사소"), ingemmet: T("페루 지질광업야금연구소"), iige: T("에콰도르 지질·에너지 연구소"), mrdata: T("미국 지질조사국"), sgm: T("멕시코 지질조사소"),
    nrcan: T("캐나다 천연자원부"), ogs: T("온타리오 지질조사소"), sigeom: T("퀘벡 지질 광업 정보 체계"), ygs: T("유콘 지질조사소"),
    ispra: T("이탈리아 지질조사소 (ISPRA)"), lneg: T("포르투갈 국립 에너지·지질연구소"), swisstopo: T("스위스 연방 지형청"),
    segemar: T("아르헨티나 지질광업조사소"), dinamige: T("우루과이 광업지질국"),
    cgmw: T("세계지질도위원회·프랑스 지질광물조사소"), aga: T("영국 지질조사소 — 아프리카 지하수 지도책"),
    cgs: T("남아프리카공화국 지질조사소"), gsn: T("나미비아 지질조사소"), ga: "Geoscience Australia",
    gsni: T("북아일랜드 지질조사소"),
    geomap: "GeoMAP (SCAR)", geo3al: T("미국 지질조사국"), kopri: T("극지연구소"), pgc: T("미네소타대 극지공간정보센터"),
    ibcso: "IBCSO", phyloserver: T("연구실 자료"), peninsula: T("연구실 자료"),
    earth: T("온 지구 화면에 모아 둔 자료 — PBDB·GVP·USGS·Neotoma"),
    kigam50k: T("한국지질자원연구원 5만 수치지질도"),
  };

  function upstreamOf(name) { return (byName[name] && byName[name].upstream) || "kigam"; }
  function isOn(name) { return active.some(function (e) { return e.name === name; }); }
  function toggleLayer(name) { if (isOn(name)) removeLayer(name); else addLayer(name); }

  /** 목록의 켜짐 표시를 `active` 에 맞춘다 — 켜고 끄는 길이 여럿이라(줄·켠 목록의 ×·모두 끄기·되살리기) 한 곳에서 */
  function syncRows() {
    document.querySelectorAll("#layer-catalog .layer-row").forEach(function (row) {
      var on = isOn(row.dataset.layer);
      row.classList.toggle("on", on);
      row.setAttribute("aria-checked", on ? "true" : "false");
    });
    document.querySelectorAll("#layer-catalog .group-all").forEach(function (b) {
      var all = JSON.parse(b.dataset.layers).every(isOn);
      b.textContent = all ? T("모두 끄기") : T("모두 켜기");
      b.title = all ? T("이 묶음의 레이어를 모두 끈다") : T("이 묶음의 레이어를 모두 켠다");
    });
  }

  function renderCatalog() {
    var host = document.getElementById("layer-catalog");
    host.innerHTML = "";

    /** 레이어 줄. `tie` 는 앞 줄과 같은 상류인가(딱지 대신 묶는 줄), `last` 는 그 묶음의 끝인가,
     *  `lead` 는 뒤에 같은 상류가 이어지는 첫 줄인가(딱지 밑으로 줄을 내린다) */
    function layerRow(layer, tie, last, lead) {
      var row = document.createElement("div");
      row.className = "layer-row";
      row.dataset.search = (layer.title + " " + layer.name).toLowerCase();
      row.dataset.layer = layer.name;
      row.setAttribute("role", "switch");
      row.setAttribute("aria-checked", "false");
      row.tabIndex = 0;

      var up = upstreamOf(layer.name);
      var tag = document.createElement("span");
      tag.className = "up up-" + up + (tie ? " tie" : "") + (last ? " end" : "") + (lead ? " lead" : "");
      if (!tie) {
        tag.textContent = UPSTREAM_TAGS[up] || up.toUpperCase();
        tag.title = UPSTREAM_NAMES[up] || up;
      }

      var label = document.createElement("span");
      label.className = "layer-name";
      label.textContent = layerTitle(layer.name);
      if (layer.abstract) row.title = layer.abstract;
      if (!layer.verified) {
        var mark = document.createElement("span");
        mark.className = "unverified";
        mark.textContent = " ·";
        mark.title = T("오픈API 로 그려지는지 아직 대조하지 않았다");
        label.appendChild(mark);
      }

      row.addEventListener("click", function () { toggleLayer(layer.name); });
      row.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleLayer(layer.name); }
      });
      row.append(tag, label);
      return row;
    }

    /** 레이어들을 줄로 — 같은 상류가 이어지면 묶는다 */
    function fill(box, layers) {
      layers.forEach(function (layer, i) {
        var up = upstreamOf(layer.name);
        var prev = i > 0 && upstreamOf(layers[i - 1].name) === up;
        var next = i < layers.length - 1 && upstreamOf(layers[i + 1].name) === up;
        box.appendChild(layerRow(layer, prev, prev && !next, !prev && next));
      });
    }

    function folder(className, title, count, open, layers) {
      var details = document.createElement("details");
      details.className = className;
      details.open = !!open;
      var summary = document.createElement("summary");
      summary.innerHTML = '<span class="group-title">' + esc(title) + '</span> <span class="count">' + count + "</span>";
      if (layers && layers.length > 1) {
        var all = document.createElement("button");
        all.type = "button";
        all.className = "group-all";
        all.dataset.layers = JSON.stringify(layers.map(function (l) { return l.name; }));
        all.addEventListener("click", function (e) {
          e.preventDefault();               // 접고 펴지 않는다
          e.stopPropagation();
          var names = layers.map(function (l) { return l.name; });
          if (names.every(isOn)) names.forEach(removeLayer);
          // 거꾸로 켠다 — 나중에 켠 것이 위에 얹히므로, 목록의 첫 줄이 맨 위에 오게
          else names.slice().reverse().forEach(function (n) { if (!isOn(n)) addLayer(n); });
        });
        summary.appendChild(all);
      }
      details.appendChild(summary);
      return details;
    }

    var BASE_LAYERS = REGIONS[region].base;
    var base = BASE_LAYERS.filter(function (name) { return byName[name]; });
    // 기본으로 펼쳐 둘 것이 카탈로그에 하나도 없는 지역은 기본 칸을 두지 않고
    // 아래의 "추가 지질도" 를 펼친다
    if (base.length) {
      var baseLayers = base.map(function (name) { return byName[name]; });
      var baseBox = folder("group base", T("기본 지질도"), base.length, true, baseLayers);
      fill(baseBox, baseLayers);
      host.appendChild(baseBox);
    }

    var rest = [];
    var restCount = 0;
    regionCatalog().forEach(function (group) {
      var layers = group.layers.filter(function (l) { return BASE_LAYERS.indexOf(l.name) < 0; });
      if (!layers.length) return;
      restCount += layers.length;
      // 북극 탭에서는 레이어군 앞에 지역을 적는다 — 그린란드의 "지질도" 가 어디 것인지
      var where = wherePrefix(group.region, layers[0] && layers[0].upstream, layers[0] && layers[0].name);
      // 이름이 같은 레이어군은 한 칸으로 — 유럽 바다의 EMODnet 은 북극해(퇴적물·기반암)와 영국(제4기 퇴적층·지질 사건)에
      // 나뉘어 있다. 카탈로그의 차례대로 잇는다 (wetherilli 176)
      var name = where + group.name, at = catalog.indexOf(group);
      var same = rest.filter(function (g) { return g.name === name; })[0];
      if (same) {
        same.layers = at < same.at ? layers.concat(same.layers) : same.layers.concat(layers);
        same.at = Math.min(same.at, at);
        return;
      }
      rest.push({ name: name, layers: layers, at: at });
    });
    if (restCount) {
      // "추가 지질도" 통째로는 모두 켜기를 두지 않는다 — 수십 장을 한꺼번에 켜게 된다
      var more = folder("group more", T("추가 지질도"), restCount, !base.length);
      rest.forEach(function (group) {
        // 기본 칸이 없고 레이어군이 하나뿐이면(북극해) 그것까지 펼친다 — 두 번 눌러야 레이어가 보이지 않게
        var details = folder("group", group.name, group.layers.length, !base.length && rest.length === 1, group.layers);
        fill(details, group.layers);
        more.appendChild(details);
      });
      host.appendChild(more);
    }
    if (hasGeonavi()) host.appendChild(geonaviFolder());
    syncRows();
  }

  // ── 지질도Navi 판 (wetherilli 171) ───────────────────────────────
  //
  // GSJ 지질도Navi 의 판 1 849 장(5만 지질도폭 763 …)을 일본·동아시아 탭의 레이어 목록 밑에 시리즈로 묶어 세운다.
  // 달 Trek 판(060)의 틀이다 — 씨앗을 서버가 추려 주고, 레이어는 켤 때 짓는다. 다만 목록이 60 KB 남짓이라 지도 화면에
  // 싣지 않고 **이 칸을 펼 때 받는다**(`gsj/geonavi/`). 켠 판은 행을 저장해 두어 되살릴 때 목록을 기다리지 않는다.
  // 판은 카탈로그 밖이라 이름 앞에 `geonavi:` 를 붙인다. 타일은 브라우저가 tiles.gsj.jp 를 곧장 부른다
  var GEONAVI = { data: null, loading: false, failed: false, open: false, q: "", here: false, openSeries: {} };
  var GEONAVI_LIMIT = 300;        // 거른 판을 한 번에 그리는 끝 — 넘으면 더 좁히라고 적는다
  var GEONAVI_TILES = /^https:\/\/tiles\.gsj\.jp\/tiles\/geomap\/[\w.-]+\/\{z\}\/\{x\}\/\{y\}\.png$/;
  var GEONAVI_LEGEND = /^https:\/\/gbank\.gsj\.jp\/geonavi\/docdata\/data\/pict_data\/[\w.-]+$/;

  function hasGeonavi() {
    return !STATIC && (region === "japan" || (REGIONS[region].includes || []).indexOf("japan") >= 0);
  }

  /** 판 하나([이름, 도폭, bbox, 줌 끝, 범례])를 카탈로그 행으로 올린다. 이름은 `geonavi:<판>` */
  function geonaviRow(series, item) {
    var name = "geonavi:" + item[0];
    if (byName[name]) return byName[name];
    var data = GEONAVI.data;
    var row = {
      name: name, upstream: "geonavi", verified: true,
      title: T("{series} · {sheet}", { series: series.name, sheet: item[1] }),
      bbox: item[2], maxZoom: item[3],
      tiles: data.tiles + item[0] + "/{z}/{x}/{y}.png",
      legendImg: item[4] ? data.legend + item[4] : "",
      attribution: data.attribution,
    };
    byName[name] = row;
    regionOfLayer[name] = "japan";
    return row;
  }

  function geonaviSaved(row) {
    return { title: row.title, bbox: row.bbox, maxZoom: row.maxZoom, tiles: row.tiles,
             legendImg: row.legendImg, attribution: row.attribution };
  }

  /** 저장해 둔 행으로 판을 되살린다. 주소는 GSJ 의 꼴일 때만 믿는다 */
  function geonaviRestore(name, saved) {
    if (!/^geonavi:[\w.-]+$/.test(name) || !saved || !GEONAVI_TILES.test(saved.tiles || "")) return;
    if (saved.legendImg && !GEONAVI_LEGEND.test(saved.legendImg)) return;
    byName[name] = {
      name: name, upstream: "geonavi", verified: true, title: String(saved.title || name),
      bbox: Array.isArray(saved.bbox) && saved.bbox.length === 4 ? saved.bbox.map(Number) : null,
      maxZoom: Math.min(20, Math.max(0, +saved.maxZoom || 14)), tiles: saved.tiles,
      legendImg: saved.legendImg || "", attribution: String(saved.attribution || ""),
    };
    regionOfLayer[name] = "japan";
  }

  /** 지질도Navi 판의 범례 — GSJ 가 판마다 떠 둔 범례 그림(원도의 범례를 스캔한 것) */
  function geonaviLegend(entry) {
    var row = byName[entry.name] || {};
    if (!row.legendImg) return note(T("범례가 없는 레이어다"));
    var a = document.createElement("a");
    a.href = row.legendImg;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.title = T("범례 그림을 새 창에서 크게 본다");
    var img = document.createElement("img");
    img.className = "legend-img";
    img.alt = T("{title} 범례", { title: entry.title });
    img.loading = "lazy";
    img.src = row.legendImg;
    img.addEventListener("error", function () { a.replaceWith(note(T("범례를 받지 못했다"))); });
    a.appendChild(img);
    return a;
  }

  function loadGeonavi() {
    if (GEONAVI.data || GEONAVI.loading) return;
    GEONAVI.loading = true;
    fetch(BASE + "gsj/geonavi/")
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) { GEONAVI.data = data; })
      .catch(function () { GEONAVI.failed = true; })
      .then(function () { GEONAVI.loading = false; renderGeonavi(); });
  }

  /** 레이어 목록 밑의 "지질도Navi 판" 칸. 펼 때 판 목록을 받는다 */
  function geonaviFolder() {
    var details = document.createElement("details");
    details.className = "group more geonavi";
    details.open = GEONAVI.open;
    var summary = document.createElement("summary");
    summary.innerHTML = '<span class="group-title">' + esc(T("지질도Navi 판")) + '</span> <span class="count" id="count-geonavi"></span>';
    details.appendChild(summary);

    var filter = document.createElement("div");
    filter.className = "trek-filter geonavi-filter";
    var q = document.createElement("input");
    q.type = "search";
    q.id = "geonavi-q";
    q.value = GEONAVI.q;
    q.placeholder = T("판 이름으로 거르기");
    q.setAttribute("aria-label", T("판 이름으로 거르기"));
    var here = document.createElement("label");
    var box = document.createElement("input");
    box.type = "checkbox";
    box.id = "geonavi-here";
    box.checked = GEONAVI.here;
    here.append(box, " " + T("보는 자리를 덮는 것만"));
    filter.append(q, here);
    var list = document.createElement("div");
    list.id = "geonavi-list";
    details.append(filter, list);

    q.addEventListener("input", function () { GEONAVI.q = q.value; renderGeonavi(); });
    box.addEventListener("change", function () { GEONAVI.here = box.checked; renderGeonavi(); });
    details.addEventListener("toggle", function () {
      GEONAVI.open = details.open;
      if (details.open) { loadGeonavi(); renderGeonavi(); }
    });
    if (GEONAVI.open) { loadGeonavi(); setTimeout(renderGeonavi, 0); }
    return details;
  }

  function geonaviRowEl(series, item) {
    var name = "geonavi:" + item[0];
    var row = document.createElement("div");
    row.className = "layer-row";
    row.dataset.layer = name;
    row.setAttribute("role", "switch");
    row.setAttribute("aria-checked", isOn(name) ? "true" : "false");
    row.classList.toggle("on", isOn(name));
    row.tabIndex = 0;
    row.title = item[0];
    var label = document.createElement("span");
    label.className = "layer-name";
    label.textContent = item[1];
    row.appendChild(label);
    function flip() { geonaviRow(series, item); toggleLayer(name); }
    row.addEventListener("click", flip);
    row.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); flip(); }
    });
    return row;
  }

  /** 판 목록을 그린다. 거르지 않으면 시리즈만 접어 두고 펼친 시리즈의 판만 짓는다 — 1 849 줄을 한꺼번에 짓지 않는다 */
  function renderGeonavi() {
    var list = document.getElementById("geonavi-list");
    if (!list) return;
    var count = document.getElementById("count-geonavi");
    list.innerHTML = "";
    if (!GEONAVI.data) {
      list.appendChild(note(GEONAVI.failed ? T("판 목록을 받지 못했다") : T("받는 중…")));
      return;
    }
    var q = GEONAVI.q.trim().toLowerCase();
    var at = GEONAVI.here ? toLL(map.getView().getCenter()) : null;
    var narrowing = !!(q || at);
    var total = 0, shown = 0;
    GEONAVI.data.series.forEach(function (series) {
      var hit = series.layers.filter(function (item) {
        if (q && (series.name + " " + item[1] + " " + item[0]).toLowerCase().indexOf(q) < 0) return false;
        var b = item[2];
        return !(at && b && !(at[0] >= b[0] && at[0] <= b[2] && at[1] >= b[1] && at[1] <= b[3]));
      });
      if (!hit.length) return;
      total += hit.length;
      var details = document.createElement("details");
      details.className = "group";
      details.open = narrowing || !!GEONAVI.openSeries[series.key];
      var summary = document.createElement("summary");
      summary.innerHTML = '<span class="group-title">' + esc(series.name) + '</span> <span class="count">' + hit.length + "</span>";
      details.appendChild(summary);
      function fillRows() {
        if (details.dataset.filled) return;
        details.dataset.filled = "1";
        hit.forEach(function (item) {
          if (narrowing && shown >= GEONAVI_LIMIT) return;
          shown += 1;
          details.appendChild(geonaviRowEl(series, item));
        });
      }
      if (details.open) fillRows();
      details.addEventListener("toggle", function () {
        if (!narrowing) GEONAVI.openSeries[series.key] = details.open;
        if (details.open) fillRows();
      });
      list.appendChild(details);
    });
    if (count) count.textContent = total;
    if (!total) list.appendChild(note(T("맞는 판이 없다")));
    else if (narrowing && shown < total) {
      list.appendChild(note(T("{n} 판 가운데 앞의 {m} 판만 — 더 좁혀 거른다", { n: total, m: shown })));
    }
  }

  function setCount(id, n) {
    var el = document.getElementById(id);
    if (el) el.textContent = n;
  }

  /** 켠 지질 레이어를 모두 끈다 (wetherilli 131). 하나씩 끄는 것과 같은 길(`removeLayer`)로 — 저장된 상태·고르개 칸도 따라간다 */
  function removeAllLayers() {
    active.slice().forEach(function (entry) { removeLayer(entry.name); });
  }

  function renderActive() {
    syncRows();
    var off = document.getElementById("layers-off");
    if (off) off.disabled = !active.length;
    var host = document.getElementById("active-list");
    setCount("count-layers", active.length);
    host.innerHTML = "";
    if (!active.length) {
      host.innerHTML = '<li class="empty">' + esc(T("아직 켠 레이어가 없다")) + "</li>";
      return;
    }
    active.forEach(function (entry, index) {
      var li = document.createElement("li");

      var head = document.createElement("div");
      head.className = "active-head";

      var up = iconButton("↑", T("위로"), index === 0, function () { move(entry.name, -1); });
      var down = iconButton("↓", T("아래로"), index === active.length - 1, function () { move(entry.name, 1); });
      var title = document.createElement("span");
      title.className = "active-title";
      title.textContent = entry.title;
      title.title = entry.name;
      var legendBtn = iconButton(T("범"), T("범례를 펼친다"), false, function () {
        entry.legendOpen = !entry.legendOpen;
        renderActive();
      });
      var bbox = byName[entry.name] && byName[entry.name].bbox;
      var fit = iconButton("⊙", T("이 레이어가 있는 곳으로 범위를 맞춘다"), !bbox, function () {
        fitLayer(entry.name);
      });
      var off = iconButton("×", T("끈다"), false, function () { removeLayer(entry.name); });

      head.append(up, down, title, fit, legendBtn, off);
      head.title = T("끌어서 차례를 바꾼다");
      wireDrag(li, head, entry, index);

      var foot = document.createElement("div");
      foot.className = "active-foot";
      var range = document.createElement("input");
      range.type = "range";
      range.min = 0; range.max = 100; range.value = Math.round(entry.opacity * 100);
      var num = document.createElement("span");
      num.className = "opacity-num";
      num.textContent = range.value + "%";
      range.addEventListener("input", function () {
        entry.opacity = range.value / 100;
        entry.layer.setOpacity(entry.opacity);
        num.textContent = range.value + "%";
      });
      range.addEventListener("change", saveLayers);
      foot.append(range, num);

      li.append(head, foot);

      // 서버가 "자료가 없다" 고 답한 레이어는 범례를 펴지 않아도 까닭이 보이게
      var failed = entry.layer.get && entry.layer.get("gsmError");
      if (failed) li.appendChild(note(failed));

      var src = sourceNote(entry.name);
      if (src) {
        var srcLine = document.createElement("p");
        srcLine.className = "active-src";
        srcLine.textContent = src;
        li.appendChild(srcLine);
      }

      // 아라온호 항적 — 1개월·6개월·1년 (koprifossillab 017)
      var periods = byName[entry.name] && byName[entry.name].periods;
      if (periods) li.appendChild(periodPicker(entry, periods));
      // 지화학 — 칠할 원소 (wetherilli 159)
      if (byName[entry.name] && byName[entry.name].style === "value") {
        var picker = valuePicker(entry);
        if (picker) li.appendChild(picker);
      }

      // 5만 지질도 — 층리·엽리·편리·절리를 늘 그릴지 (jikhanjung 005)
      if (ATTITUDE_LAYERS.indexOf(entry.name) >= 0 && isMercator()) li.appendChild(attitudeToggles());

      // 가까이서만 그려 주는 레이어 — 멀리서 켜면 아무것도 안 보이는 까닭을 적는다
      var minZoom = byName[entry.name] && byName[entry.name].minZoom;
      if (minZoom) li.appendChild(note(T("줌 {n} 부터 그려진다", { n: minZoom })));

      entry.legendBox = null;
      if (entry.legendOpen && byName[entry.name] && byName[entry.name].kind === "vector") {
        li.appendChild(vectorLegend(entry.name));
      } else if (entry.legendOpen && byName[entry.name] && byName[entry.name].kind === "points") {
        li.appendChild(pointLegend(entry));
      } else if (entry.legendOpen && byName[entry.name] && byName[entry.name].noLegend) {
        li.appendChild(note(T("범례가 없는 레이어다")));
      } else if (entry.legendOpen && byName[entry.name] && byName[entry.name].classLegend) {
        li.appendChild(classLegend(byName[entry.name].classLegend));
      } else if (entry.legendOpen && byName[entry.name] && byName[entry.name].upstream === "geonavi") {
        li.appendChild(geonaviLegend(entry));
      } else if (entry.legendOpen && byName[entry.name] && byName[entry.name].legend &&
                 !(STATIC && layerKind(entry.name).legend)) {
        // 보는 범위의 범례(`legendUrl`)는 서버 길이다 — 정적 판에서 상류 손이 범례를 따로 가지면 그쪽을 탄다(호주 GA, wetherilli 212)
        entry.legendBox = gsjLegend(entry);
        li.appendChild(entry.legendBox);
      } else if (entry.legendOpen && STATIC && layerKind(entry.name).legend) {
        // 정적 판의 극지 상류는 범례도 상류에서 곧장 — 그림·줄·링크 셋 가운데 하나로 온다 (wetherilli 161)
        li.appendChild(staticLegend(entry));
      } else if (entry.legendOpen) {
        var img = document.createElement("img");
        img.className = "legend-img";
        img.alt = T("{title} 범례", { title: entry.title });
        img.src = STATIC && (byName[entry.name] || {}).upstream === "vworld" ? vworldLegendUrl(entry.name)
          : STATIC && (byName[entry.name] || {}).upstream === "kigam"
          ? KIGAM_OPENAPI + "?" + new URLSearchParams({ service: "WMS", version: "1.0.0", request: "GetLegendGraphic",
                                                        format: "image/png", layer: entry.name, key: readKey("kigam") })
          // 정적 판의 GeoMAP 범례는 구워 둔 그림 (wetherilli 165)
          : STATIC && (byName[entry.name] || {}).upstream === "geomap" ? BASE + "legend/geomap/" + entry.name + ".png"
          : BASE + "legend/?layer=" + encodeURIComponent(entry.name);
        img.addEventListener("error", function () {
          img.replaceWith(note(T("범례를 받지 못했다")));
        });
        li.appendChild(img);
      }
      host.appendChild(li);
    });
  }

  /** 정적 판의 극지 범례 (`GSM_STATIC_KINDS[상류].legend`, wetherilli 161). 받은 것은 그 레이어 항목에 담아 두어 범례 칸을
   *  다시 그릴 때마다 상류에 묻지 않는다. `{img}` 는 그림 한 장(EMODnet·KPDC), `{rows}` 는 칸마다 그림과 이름(NPI 의
   *  `legend?f=json`), `{link}` 는 그림이 아니라 쪽(GEUS 는 HTML 범례로 넘긴다) */
  function staticLegend(entry) {
    var box = document.createElement("div");
    box.className = "vector-legend";
    if (!entry.staticLegend) entry.staticLegend = layerKind(entry.name).legend(entry.name, byName[entry.name] || {});
    entry.staticLegend.then(function (got) {
      if (!got) {
        box.appendChild(note(T("범례가 없는 레이어다")));
      } else if (got.img) {
        var img = document.createElement("img");
        img.className = "legend-img";
        img.alt = T("{title} 범례", { title: entry.title });
        img.src = got.img;
        img.addEventListener("error", function () { img.replaceWith(note(T("범례를 받지 못했다"))); });
        box.appendChild(img);
      } else if (got.rows) {
        got.rows.forEach(function (r) {
          var line = document.createElement("div");
          line.className = "vector-legend-row";
          var swatch = document.createElement("img");
          swatch.src = r.src;
          swatch.alt = "";
          var label = document.createElement("span");
          label.textContent = r.label;
          line.appendChild(swatch);
          line.appendChild(label);
          box.appendChild(line);
        });
      } else if (got.link) {
        var a = document.createElement("a");
        a.href = got.link;
        a.target = "_blank";
        a.rel = "noopener";
        a.textContent = T("범례 열기");
        box.appendChild(a);
      }
    }).catch(function () {
      entry.staticLegend = null;                  // 다음에 다시 묻는다
      box.appendChild(note(T("범례를 받지 못했다")));
    });
    return box;
  }

  /** 레이어의 범위(`Layer.bbox`, 위경도)로 지도를 옮긴다.
   *  해저지질도처럼 바다에만 있는 레이어를 켰는데 화면에 아무것도 안
   *  보일 때 쓴다. 범위는 상류의 `GetCapabilities` 가 준 것이다. */
  function fitLayer(name) {
    var bbox = byName[name] && byName[name].bbox;
    if (!bbox) return;
    // 극지 화면에서는 위경도 네모가 부채꼴이 된다. 가장자리를 촘촘히 짚어 옮긴다
    var extent = ol.proj.transformExtent(bbox, "EPSG:4326", viewProj(), 32);
    map.getView().fit(extent, { padding: [40, 40, 60, 40], duration: 300 });
  }

  function iconButton(text, title, disabled, onClick) {
    var b = document.createElement("button");
    b.className = "iconbtn";
    b.type = "button";
    b.textContent = text;
    b.title = title;
    b.disabled = disabled;
    b.addEventListener("click", onClick);
    return b;
  }

  function note(text) {
    var p = document.createElement("p");
    p.className = "hint";
    p.textContent = text;
    return p;
  }

  // ── 도구 — 점 찍기·거리·넓이 ───────────────────────────────────
  //
  // 공식 뷰어가 주는 보조 기능을 옮겨 왔다. **하나도 저장하지 않는다** —
  // 지금 보면서 재는 것이라, 새로 고치면 사라지는 것이 맞다. 남길 것은
  // "내 자료" 로 올린다.

  var MODE_HINT = {
    info: T("지도를 누르면 그 지점의 지질 속성이 뜬다."),
    point: T("지도를 누르면 점이 찍히고 위경도가 적힌다. 점을 눌러 지운다."),
    line: T("눌러 가며 선을 잇는다. 두 번 누르면 끝난다."),
    area: T("눌러 가며 둘레를 두른다. 두 번 누르면 끝난다."),
    box: T("누른 채 끌어 네모를 그린다. 손을 떼면 꼭짓점·중앙·넓이가 뜬다."),
  };

  function tempStyle(feature) {
    return new ol.style.Style({
      image: new ol.style.Circle({
        radius: 6,
        fill: new ol.style.Fill({ color: "#5c3a1e" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 2 }),
      }),
      text: new ol.style.Text({
        text: String(feature.get("no")),
        offsetY: -14,
        font: "600 11px ui-monospace, Menlo, monospace",
        fill: new ol.style.Fill({ color: "#3f2712" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 3 }),
      }),
    });
  }

  /** 찾아간 자리. 겹고리로 눈에 띄게 하고 위경도를 곁에 적는다. */
  function foundStyle(feature) {
    return [
      new ol.style.Style({
        image: new ol.style.Circle({
          radius: 15,
          fill: new ol.style.Fill({ color: "rgba(158, 59, 42, .16)" }),
          stroke: new ol.style.Stroke({ color: "rgba(158, 59, 42, .6)", width: 2 }),
        }),
      }),
      new ol.style.Style({
        image: new ol.style.Circle({
          radius: 5,
          fill: new ol.style.Fill({ color: "#9e3b2a" }),
          stroke: new ol.style.Stroke({ color: "#fff", width: 2 }),
        }),
        text: new ol.style.Text({
          text: feature.get("label") || "",
          offsetY: -26,
          font: "600 11px ui-monospace, Menlo, monospace",
          fill: new ol.style.Fill({ color: "#7a2c1f" }),
          stroke: new ol.style.Stroke({ color: "#fff", width: 4 }),
          overflow: true,
        }),
      }),
    ];
  }

  /** 찍어 넣은 좌표로 간다.
   *
   *  **도폭 한 장이 화면에 들어오게** 맞춘다(`SHEET_LON`×`SHEET_LAT`).
   *  줌 단계를 숫자로 박으면 화면 크기에 따라 보이는 범위가 달라지는데,
   *  범위를 주고 맞추면 어느 화면에서나 같은 만큼이 보인다.
   */
  function goTo(lat, lon, label) {
    var extent = ol.proj.transformExtent(
      [lon - SHEET_LON / 2, lat - SHEET_LAT / 2,
       lon + SHEET_LON / 2, lat + SHEET_LAT / 2],
      "EPSG:4326", map.getView().getProjection());

    foundSource.clear();
    foundSource.addFeature(new ol.Feature({
      geometry: new ol.geom.Point(fromLL([lon, lat])),
      label: label || formatPair(lon, lat),
    }));

    map.getView().fit(extent, { duration: 450, callback: function () {
      // 화면 한복판에 정확히 놓는다. fit 은 범위를 맞출 뿐이라
      // 가장자리에서 한두 픽셀 어긋나는 일이 있다.
      map.getView().setCenter(fromLL([lon, lat]));
    } });
  }

  function measureStyle(feature) {
    var label = feature.get("label") || "";
    return new ol.style.Style({
      fill: new ol.style.Fill({ color: "rgba(92, 58, 30, .16)" }),
      stroke: new ol.style.Stroke({ color: "#5c3a1e", width: 2.5, lineDash: [7, 5] }),
      image: new ol.style.Circle({
        radius: 4,
        fill: new ol.style.Fill({ color: "#5c3a1e" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 1.5 }),
      }),
      text: label ? new ol.style.Text({
        text: label,
        font: "600 12px ui-monospace, Menlo, monospace",
        fill: new ol.style.Fill({ color: "#3f2712" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 4 }),
        overflow: true,
      }) : undefined,
    });
  }

  /** 미터를 사람이 읽는 길이로. */
  function asLength(m) {
    return m >= 1000 ? (m / 1000).toFixed(2) + " km" : m.toFixed(1) + " m";
  }

  /** 제곱미터를 사람이 읽는 넓이로. 헥타르를 함께 적는다 —
   *  현장에서 면적을 말할 때 ha 를 쓰는 일이 잦다. */
  function asArea(m2) {
    if (m2 >= 1e6) return (m2 / 1e6).toFixed(3) + " km² (" + (m2 / 1e4).toFixed(1) + " ha)";
    if (m2 >= 1e4) return (m2 / 1e4).toFixed(2) + " ha (" + Math.round(m2).toLocaleString() + " m²)";
    return Math.round(m2).toLocaleString() + " m²";
  }

  function measureOf(geometry) {
    var opts = { projection: map.getView().getProjection() };
    if (geometry instanceof ol.geom.Polygon) {
      return { text: asArea(ol.sphere.getArea(geometry, opts)), kind: T("넓이") };
    }
    return { text: asLength(ol.sphere.getLength(geometry, opts)), kind: T("거리") };
  }

  function setMode(next) {
    mode = next;
    if (drawInteraction) {
      map.removeInteraction(drawInteraction);
      drawInteraction = null;
    }
    document.querySelectorAll(".tool[data-mode]").forEach(function (b) {
      b.classList.toggle("on", b.dataset.mode === next);
    });
    document.getElementById("map").style.cursor =
      next === "info" ? "" : "crosshair";
    updateToolOut();

    if (next === "box") {
      drawInteraction = rangeInteraction();
      map.addInteraction(drawInteraction);
      return;
    }
    if (next !== "line" && next !== "area") return;

    drawInteraction = new ol.interaction.Draw({
      source: measureSource,
      type: next === "line" ? "LineString" : "Polygon",
      style: measureStyle,
    });
    drawInteraction.on("drawstart", function (evt) {
      // 재는 것은 한 번에 하나만 둔다. 여럿이 겹치면 어느 것이 어느 것인지
      // 알 수 없고, 화면이 금세 지저분해진다.
      measureSource.clear();
      hideProfile();
      var geometry = evt.feature.getGeometry();
      geometry.on("change", function () {
        var got = measureOf(geometry);
        evt.feature.set("label", got.text);
        showMeasure(got);
      });
    });
    drawInteraction.on("drawend", function (evt) {
      var got = measureOf(evt.feature.getGeometry());
      evt.feature.set("label", got.text);
      showMeasure(got, true);
      // 거리를 다 재면 그 선의 높이 그래프 (wetherilli 109)
      if (next === "line") showProfile(evt.feature.getGeometry().getCoordinates().map(toLL));
    });
    map.addInteraction(drawInteraction);
  }

  // ── 범위잡기 ─────────────────────────────────────────────────────
  //
  // 누른 채 끌어 네모를 그리고, 손을 떼면 네 꼭짓점·중앙·넓이를 보인다.
  // 시료 채취 권역이나 도폭 밖 조사 범위를 적어 두는 자리다. **여럿을 잡아
  // 두고 "찍고 잰 것" 에 남긴다** — 재는 선은 하나만 두는 것과 다르다.
  // 저장하지 않는다. 남길 것은 "점묶음으로 저장" 으로 꼭짓점과 중앙을 올린다.

  function rangeStyle(feature) {
    return new ol.style.Style({
      fill: new ol.style.Fill({ color: "rgba(201, 162, 75, .14)" }),
      stroke: new ol.style.Stroke({ color: "#c9a24b", width: 2 }),
      text: new ol.style.Text({
        text: T("범위 {n}", { n: feature.get("no") }),
        font: "600 12px ui-monospace, Menlo, monospace",
        fill: new ol.style.Fill({ color: "#3f2712" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 4 }),
        overflow: true,
      }),
    });
  }

  function rangeInteraction() {
    // 누르고 끄는 동안은 지도가 끌리지 않는다 (DragBox 가 먼저 받는다)
    var box = new ol.interaction.DragBox({ condition: ol.events.condition.always, className: "range-box" });
    box.on("boxend", function () {
      var extent = box.getGeometry().getExtent();
      if (ol.extent.getWidth(extent) === 0 || ol.extent.getHeight(extent) === 0) return;
      addRange(extent);
    });
    return box;
  }

  /** 범위 하나의 수치. 넓이는 구면으로 잰다 — 3857 의 네모 넓이는 위도에
   *  따라 부풀어서, 우리나라에서는 1.5 배쯤 크게 나온다.
   *
   *  **극지 화면의 네모는 위경도 네모가 아니다.** 위가 북쪽이 아니어서
   *  꼭짓점을 동서남북으로 부를 수 없다 — 화면의 네 귀(왼쪽 위 …)로 부르고,
   *  꼭짓점과 가운데를 하나씩 옮긴다. */
  function rangeFacts(extent) {
    if (!isMercator()) return polarRangeFacts(extent);
    var sw = toLL([extent[0], extent[1]]);
    var ne = toLL([extent[2], extent[3]]);
    var w = sw[0], s = sw[1], e = ne[0], n = ne[1];
    var polygon = ol.geom.Polygon.fromExtent(extent);
    var opts = { projection: map.getView().getProjection() };
    return {
      nw: [w, n], ne: [e, n], se: [e, s], sw: [w, s],
      center: [(w + e) / 2, (s + n) / 2],
      area: ol.sphere.getArea(polygon, opts),
      // 가로는 가운데 위도에서 잰다. 위아래 변은 위도가 달라 길이가 다르다
      width: ol.sphere.getDistance([w, (s + n) / 2], [e, (s + n) / 2]),
      height: ol.sphere.getDistance([w, s], [w, n]),
    };
  }

  function polarRangeFacts(extent) {
    var polygon = ol.geom.Polygon.fromExtent(extent);
    var midY = (extent[1] + extent[3]) / 2;
    var nw = toLL([extent[0], extent[3]]), ne = toLL([extent[2], extent[3]]);
    var se = toLL([extent[2], extent[1]]), sw = toLL([extent[0], extent[1]]);
    return {
      screen: true,
      nw: nw, ne: ne, se: se, sw: sw,
      center: toLL(ol.extent.getCenter(extent)),
      area: ol.sphere.getArea(polygon, { projection: viewProj() }),
      width: ol.sphere.getDistance(toLL([extent[0], midY]), toLL([extent[2], midY])),
      height: ol.sphere.getDistance(sw, nw),
    };
  }

  function rangeRows(f) {
    var rows = {};
    rows[f.screen ? T("왼쪽 위") : T("북서")] = formatPair(f.nw[0], f.nw[1]);
    rows[f.screen ? T("오른쪽 위") : T("북동")] = formatPair(f.ne[0], f.ne[1]);
    rows[f.screen ? T("오른쪽 아래") : T("남동")] = formatPair(f.se[0], f.se[1]);
    rows[f.screen ? T("왼쪽 아래") : T("남서")] = formatPair(f.sw[0], f.sw[1]);
    rows[T("중앙")] = formatPair(f.center[0], f.center[1]);
    rows[T("넓이")] = asArea(f.area);
    rows[T("가로 × 세로")] = asLength(f.width) + " × " + asLength(f.height);
    return rows;
  }

  function rangeText(feature) {
    var rows = rangeRows(rangeFacts(feature.getGeometry().getExtent()));
    return [T("범위 {n}", { n: feature.get("no") })].concat(Object.keys(rows).map(function (k) {
      return k + "\t" + rows[k];
    })).join("\n");
  }

  function addRange(extent) {
    rangeSeq += 1;
    var feature = new ol.Feature({ geometry: ol.geom.Polygon.fromExtent(extent), no: rangeSeq });
    rangeSource.addFeature(feature);
    renderTemp();
    showRange(feature);
  }

  function showRange(feature) {
    var extent = feature.getGeometry().getExtent();
    var facts = rangeFacts(extent);
    lastMeasure = T("범위 {n}", { n: feature.get("no") }) + " " + asArea(facts.area);
    var out = document.getElementById("measure-out");
    out.textContent = lastMeasure;
    out.classList.add("done");
    updateToolOut();
    // 팝업은 위경도의 한가운데에 띄운다 — 표의 "중앙" 과 첫 줄 위경도가 같아야 한다.
    // 지도 좌표(3857)의 한가운데는 위도가 몇 백만 분의 1 도 어긋난다
    var ll = ol.proj.transformExtent(extent, viewProj(), "EPSG:4326");
    showPopup(fromLL(facts.center),
              [{ title: T("범위 {n}", { n: feature.get("no") }), props: rangeRows(facts) }], "",
              { rose: attitudeLayersOn() ? "bbox=" + ll.map(function (v) { return v.toFixed(5); }).join(",") : "" });
  }

  function showMeasure(got, done) {
    var out = document.getElementById("measure-out");
    out.textContent = got.kind + " " + got.text;
    out.classList.toggle("done", !!done);
    lastMeasure = got.kind + " " + got.text;
    updateToolOut();
  }

  /** 지도 위 손잡이 옆의 알림.
   *
   *  **재는 결과가 손잡이 곁에 있어야 한다.** 처음에는 왼쪽 패널에만
   *  적었는데, 손잡이를 누른 자리에서는 아무 일도 안 일어나는 것처럼
   *  보였다. 누른 곳에서 답이 나와야 한다. */
  function updateToolOut() {
    var out = document.getElementById("tool-out");
    var points = tempSource ? tempSource.getFeatures().length : 0;
    var bits = [];
    if (lastMeasure) bits.push(lastMeasure);
    if (points) bits.push(T("점 {n}개", { n: points }));
    if (mode === "point" && !points) bits.push(T("지도를 눌러 점을 찍는다"));
    if (mode === "line" && !lastMeasure) bits.push(T("눌러 가며 잇는다 · 두 번 누르면 끝"));
    if (mode === "area" && !lastMeasure) bits.push(T("눌러 가며 두른다 · 두 번 누르면 끝"));
    if (mode === "box" && !rangeSource.getFeatures().length) bits.push(T("누른 채 끌어 네모를 그린다"));
    out.textContent = bits.join("  ·  ");
    out.hidden = !bits.length;
  }

  function addTempPoint(coordinate) {
    var ll = toLL(coordinate);
    tempSeq += 1;
    var feature = new ol.Feature({
      geometry: new ol.geom.Point(coordinate),
      no: tempSeq,
      lat: ll[1],
      lon: ll[0],
    });
    tempSource.addFeature(feature);
    renderTemp();
  }

  function renderTemp() {
    var host = document.getElementById("temp-list");
    var features = tempSource.getFeatures();
    var ranges = rangeSource.getFeatures();
    setCount("count-temp", features.length + ranges.length);
    updateToolOut();
    host.innerHTML = "";
    ranges.forEach(function (feature) { host.appendChild(rangeItem(feature)); });
    if (!features.length && ranges.length) return;
    if (!features.length) {
      host.innerHTML = '<li class="empty">' + T("지도 오른쪽 위 <b>점</b> 도구로 찍는다") + "</li>";
      return;
    }
    features.forEach(function (feature) {
      var li = document.createElement("li");

      var no = document.createElement("span");
      no.className = "temp-no";
      no.textContent = feature.get("no");

      var text = document.createElement("button");
      text.type = "button";
      text.className = "temp-coord";
      text.title = T("눌러서 복사한다");
      text.textContent = formatPair(feature.get("lon"), feature.get("lat"));
      text.addEventListener("click", function () {
        var value = text.textContent;
        copyText(value).then(function () {
          text.textContent = T("복사했다");
          setTimeout(function () { text.textContent = value; }, 700);
        });
      });

      var go = iconButton("⊙", T("이 점으로 이동"), false, function () {
        map.getView().animate({
          center: feature.getGeometry().getCoordinates(), duration: 300,
        });
      });
      var del = iconButton("×", T("지운다"), false, function () {
        tempSource.removeFeature(feature);
        renderTemp();
      });

      li.append(no, text, go, del);
      host.appendChild(li);
    });
  }

  function rangeItem(feature) {
    var li = document.createElement("li");
    li.className = "range-item";
    var no = document.createElement("span");
    no.className = "temp-no range";
    no.textContent = feature.get("no");
    var facts = rangeFacts(feature.getGeometry().getExtent());
    var text = document.createElement("button");
    text.type = "button";
    text.className = "temp-coord";
    text.title = T("눌러서 꼭짓점·중앙·넓이를 복사한다");
    text.textContent = asArea(facts.area) + " · " + formatPair(facts.center[0], facts.center[1]);
    text.addEventListener("click", function () {
      var value = text.textContent;
      copyText(rangeText(feature)).then(function () {
        text.textContent = T("복사했다");
        setTimeout(function () { text.textContent = value; }, 700);
      });
    });
    var go = iconButton("⊙", T("이 범위로 가서 수치를 본다"), false, function () {
      map.getView().fit(feature.getGeometry().getExtent(), { padding: [60, 60, 80, 60], duration: 300 });
      showRange(feature);
    });
    var del = iconButton("×", T("지운다"), false, function () {
      rangeSource.removeFeature(feature);
      renderTemp();
    });
    li.append(no, text, go, del);
    return li;
  }

  /** 찍어 둔 점을 **목록으로 저장한다.** 구글 지도의 "장소 저장" 과 같은 자리다.
   *
   *  임시 표시는 새로 고치면 사라진다. 그러다 "이건 남겨야겠다" 싶은 때가
   *  오는데, 그때 파일로 내보냈다 다시 올리게 하면 아무도 안 한다.
   *  있는 그대로 점묶음이 되게 했다.
   */
  /** 지도 좌표(화면 투영)의 기하를 GeoJSON(4326)으로. */
  function toGeoJson(geometry) {
    var g = geometry.clone().transform(map.getView().getProjection(), "EPSG:4326");
    return { type: g.getType(), coordinates: g.getCoordinates() };
  }

  /** 잡은 범위는 **네모 그대로** 올린다. 꼭짓점·중앙·넓이는 딸린 속성으로
   *  붙여, 점묶음에서 네모를 누르면 범위잡기 때와 같은 표가 뜬다. */
  function rangeShapes(ranges) {
    return ranges.map(function (feature) {
      var rows = rangeRows(rangeFacts(feature.getGeometry().getExtent()));
      return { geometry: toGeoJson(feature.getGeometry()),
               label: T("범위 {n}", { n: feature.get("no") }), props: rows };
    });
  }

  /** 거리·넓이로 잰 선·면도 함께 올린다. 잰 값이 이름표가 된다. */
  function measureShapes(measured) {
    return measured.map(function (feature) {
      var got = measureOf(feature.getGeometry());
      return { geometry: toGeoJson(feature.getGeometry()),
               label: got.kind + " " + got.text, props: {} };
    });
  }

  function saveTemp() {
    var features = tempSource.getFeatures();
    var ranges = rangeSource.getFeatures();
    var measured = measureSource.getFeatures();
    var msg = document.getElementById("save-msg");
    if (!features.length && !ranges.length && !measured.length) {
      msg.className = "msg bad";
      msg.textContent = T("저장할 점이 없다.");
      return;
    }
    var name = prompt(T("목록 이름"), T("찍은 점 {date}", { date: new Date().toLocaleDateString(LANG === "en" ? "en-GB" : "ko-KR") }));
    if (name === null) return;

    msg.className = "msg";
    msg.textContent = T("저장하는 중…");

    fetch(BASE + "pointsets/create/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({
        name: name,
        color: "#5c3a1e",
        points: features.map(function (f) {
          return { lat: f.get("lat"), lon: f.get("lon"), label: T("점 {n}", { n: f.get("no") }) };
        }),
        shapes: rangeShapes(ranges).concat(measureShapes(measured)),
      }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) {
          msg.className = "msg bad";
          msg.textContent = res.d.error || T("저장하지 못했다");
          return;
        }
        pointsets.unshift(res.d.pointset);
        renderPointSets();
        // 저장했으니 임시 표시는 치운다. 같은 점이 두 겹으로 남으면 헷갈린다.
        tempSource.clear();
        tempSeq = 0;
        rangeSource.clear();
        rangeSeq = 0;
        measureSource.clear();
        lastMeasure = "";
        renderTemp();
        msg.className = "msg good";
        msg.textContent = T("'{name}' 으로 저장했다.", { name: res.d.pointset.name });
      })
      .catch(function () {
        msg.className = "msg bad";
        msg.textContent = T("저장하지 못했다");
      });
  }

  function wireTools() {
    // **누른 손잡이를 다시 누르면 꺼진다.** 아무것도 안 켜져 있으면 속성을
    // 읽는 것이 기본이라, "속성 읽기" 단추를 따로 두지 않는다.
    document.querySelectorAll(".tool[data-mode]").forEach(function (button) {
      button.addEventListener("click", function () {
        setMode(mode === button.dataset.mode ? "info" : button.dataset.mode);
      });
    });
    document.getElementById("tool-clear").addEventListener("click", clearDrawn);
    // 남극 탭의 "자세" — 우리 기지로 바로 간다 (049). 좌표는 극지연구소·위키백과가 적은 기지 자리다.
    // 해상도 12 m/px 면 기지와 둘레 10 km 남짓이 한 화면에 든다
    var STATIONS = {
      jangbogo: [164.22882, -74.62402],     // 장보고과학기지 74°37′26″S 164°13′44″E — 테라노바만
      sejong: [-58.78833, -62.22278],       // 세종과학기지 62°13′22″S 58°47′18″W — 킹조지섬 바턴반도
    };
    document.querySelectorAll(".tool[data-goto]").forEach(function (button) {
      button.addEventListener("click", function () {
        var ll = STATIONS[button.dataset.goto];
        if (!ll) return;
        map.getView().animate({ center: fromLL(ll), resolution: 12, rotation: 0, duration: 900 });
      });
    });
    document.getElementById("tool-export").addEventListener("click", exportPng);
    // 3D 는 한국의 `gsm.view` 만 읽는다. 일본·중국·동아시아 탭에서도 지금 자리를 열게
    // 누르는 순간 주소에 가운데와 줌을 싣는다
    document.getElementById("tool-3d").addEventListener("click", function () {
      var view = map.getView();
      var ll = toLL(view.getCenter());
      // 극 평사도법의 줌은 3857 보다 두세 단계 낮게 읽는다 — 되짚은 줌을 넘긴다(`mercZoom`)
      var top = active.filter(function (e) { return e.layer.getVisible(); })[0];
      // 3D(메르카토르)는 위도 ±85° 너머가 없다. 극지 탭의 가운데가 극점이면 3D 가 한 귀퉁이만 보인다 —
      // 80° 안으로 끌어온다. 가장 작은 줌도 한국(8)에 묶지 않는다 — 극지는 5 다. 남위 78°·줌 5 면
      // 경도 140° 폭(남극횡단산맥 하나)이 한 화면에 든다. 더 낮추면 메르카토르의 세계 전체와 85° 의 끝이
      // 절벽처럼 드러난다 (2026-09-29, 050)
      var lat = Math.max(-80, Math.min(80, ll[1]));
      this.href = BASE + "3d/?lat=" + lat.toFixed(5) + "&lon=" + ll[0].toFixed(5) +
        "&z=" + Math.max(isMercator() ? 8 : 5, mercZoom(view.getResolution())).toFixed(2) +
        "&region=" + region +                    // 3D 도 이 지역의 색으로 뜬다
        (top ? "&layer=" + encodeURIComponent(top.name) : "");
    });
    document.getElementById("save-temp").addEventListener("click", saveTemp);
    document.getElementById("clear-temp").addEventListener("click", clearDrawn);
    renderTemp();
    setMode("info");
  }

  // ── 그림으로 내려받기 ───────────────────────────────────────────
  //
  // 지금 보는 지도를 PNG 한 장으로. OpenLayers 는 레이어마다 캔버스를 따로 그리므로
  // 그 캔버스들을 투명도·변환 그대로 한 장에 겹치고, 밑에 띠를 붙여 **무엇을 봤는지**
  // 적는다 — 지역·켠 레이어·점묶음·가운데 좌표·축척 막대·출처·날짜. 인쇄는 이 그림을
  // 인쇄한다. 브라우저가 곧장 부르는 배경(VWorld·EOX …)은 `crossOrigin` 으로 받아
  // 캔버스를 더럽히지 않는다. 그래도 막히면 까닭을 말한다. 비교(나란히)의 오른쪽 지도는
  // 담지 않는다.

  function exportPng() {
    var button = document.getElementById("tool-export");
    button.disabled = true;
    map.once("rendercomplete", function () {
      try {
        var canvas = composeExport();
        canvas.toBlob(function (blob) {
          button.disabled = false;
          if (!blob) { alert(T("그림을 만들지 못했다")); return; }
          var a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "GSM-" + stampText().replace(/[-: ]/g, "").slice(0, 12) + ".png";
          document.body.appendChild(a);
          a.click();
          setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
        }, "image/png");
      } catch (e) {
        button.disabled = false;
        // 교차 출처 그림이 섞여 캔버스가 더럽혀졌다 (SecurityError)
        alert(T("배경지도가 그림으로 뽑는 것을 막았다 — 배경을 '없음' 으로 두고 다시 한다"));
      }
    });
    map.renderSync();
  }

  function stampText() {
    var d = new Date();
    function two(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + two(d.getMonth() + 1) + "-" + two(d.getDate()) + " " +
      two(d.getHours()) + ":" + two(d.getMinutes());
  }

  /** 레이어 캔버스를 겹친 지도 + 밑의 띠. 화면 픽셀 비율대로 또렷하게 뽑는다. */
  function composeExport() {
    var ratio = window.devicePixelRatio || 1;
    var size = map.getSize();
    var w = size[0], h = size[1];
    var lines = exportLines();
    var lineH = 17, pad = 12;
    var foot = pad * 2 + lineH * lines.length + 26;
    var out = document.createElement("canvas");
    out.width = Math.round(w * ratio);
    out.height = Math.round((h + foot) * ratio);
    var ctx = out.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, out.width, out.height);

    map.getViewport().querySelectorAll(".ol-layer canvas, canvas.ol-layer").forEach(function (c) {
      if (!c.width) return;
      var opacity = c.parentNode.style.opacity || c.style.opacity;
      ctx.globalAlpha = opacity === "" ? 1 : Number(opacity);
      var m = /^matrix\(([^(]*)\)$/.exec(c.style.transform || "");
      var t = m ? m[1].split(",").map(Number) : [w / c.width, 0, 0, h / c.height, 0, 0];
      ctx.setTransform(t[0] * ratio, t[1] * ratio, t[2] * ratio, t[3] * ratio, t[4] * ratio, t[5] * ratio);
      var bg = c.parentNode.style.backgroundColor;
      if (bg) { ctx.fillStyle = bg; ctx.fillRect(0, 0, c.width, c.height); }
      ctx.drawImage(c, 0, 0);
    });
    ctx.globalAlpha = 1;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

    // 띠 — 지도와 선을 그어 가른다
    ctx.fillStyle = "#faf7f1";
    ctx.fillRect(0, h, w, foot);
    ctx.fillStyle = "#3f2712";
    ctx.fillRect(0, h, w, 1);
    ctx.textBaseline = "top";
    lines.forEach(function (line, i) {
      ctx.font = (i === 0 ? "bold 14px " : "12px ") + "sans-serif";
      ctx.fillStyle = i === 0 ? "#1f1409" : "#3f3228";
      ctx.fillText(fitText(ctx, line, w - pad * 2 - (i === 0 ? 170 : 0)), pad, h + pad + i * lineH + (i ? 3 : 0));
    });
    drawScaleBar(ctx, w - pad - 150, h + pad + 2, 150);
    return out;
  }

  /** 띠에 적을 줄들. 첫 줄이 제목이다. */
  function exportLines() {
    var shown = active.filter(function (e) { return e.layer.getVisible(); });
    var mine = pointsets.filter(function (ps) { return ps.visible; });
    var center = toLL(map.getView().getCenter());
    var credits = Array.prototype.map.call(
      document.querySelectorAll(".ol-attribution li"), function (li) { return li.textContent.trim(); })
      .filter(Boolean);
    // KIGAM 은 화면에서 출처를 비워 둔다(레이어 이름이 곧 출처다). 그림은 떨어져 돌아다니므로 적는다
    if (shown.some(function (e) { return (byName[e.name] || {}).upstream === "kigam"; })) {
      credits.unshift(T("한국지질자원연구원"));
    }
    var out = [T("대돌여지도") + " · " + T(REGIONS[region].title) + " · " + stampText()];
    out.push(T("레이어") + ": " + (shown.length ? shown.map(function (e) { return e.title; }).join(" / ") : "—"));
    if (mine.length) out.push(T("점묶음") + ": " + mine.map(function (ps) { return ps.name; }).join(", "));
    out.push(T("가운데") + ": " + formatPair(center[0], center[1]) + " · " + viewProj().getCode());
    if (credits.length) out.push(T("출처") + ": " + credits.join(" · "));
    return out;
  }

  /** 넘치면 끝을 줄임표로 자른다. */
  function fitText(ctx, text, max) {
    if (ctx.measureText(text).width <= max) return text;
    while (text.length > 1 && ctx.measureText(text + "…").width > max) text = text.slice(0, -1);
    return text + "…";
  }

  /** 지도 가운데의 땅 축척으로 막대를 그린다. 1·2·5 × 10ⁿ 로 반올림한다. */
  function drawScaleBar(ctx, x, y, maxWidth) {
    var view = map.getView();
    var metersPerPx = ol.proj.getPointResolution(viewProj(), view.getResolution(), view.getCenter(), "m");
    if (!isFinite(metersPerPx) || metersPerPx <= 0) return;
    var raw = metersPerPx * maxWidth;
    var pow = Math.pow(10, Math.floor(Math.log10(raw)));
    var nice = [5, 2, 1].map(function (k) { return k * pow; }).filter(function (v) { return v <= raw; })[0] || pow;
    var px = nice / metersPerPx;
    ctx.fillStyle = "#1f1409";
    ctx.fillRect(x, y + 14, px, 4);
    ctx.fillRect(x, y + 10, 1.5, 8);
    ctx.fillRect(x + px - 1.5, y + 10, 1.5, 8);
    ctx.font = "12px sans-serif";
    ctx.fillText(nice >= 1000 ? (nice / 1000) + " km" : nice + " m", x, y - 4);
  }

  function clearDrawn() {
    hideProfile();
    tempSource.clear();
    measureSource.clear();
    foundSource.clear();
    rangeSource.clear();
    rangeSeq = 0;
    tempSeq = 0;
    lastMeasure = "";
    renderTemp();
    var out = document.getElementById("measure-out");
    out.textContent = T("아직 잰 것이 없다");
    out.classList.remove("done");
    updateToolOut();
  }

  // ── 높이 그래프 (wetherilli 109) ─────────────────────────────────
  //
  // 달 화면의 것(wetherilli 100)을 옮겼다. 거리를 다 재면 그 선을 대원을 따라 고르게 나눈 점의 표고를 받아(`elevation/profile/`)
  // 아래 가운데 판에 그린다. 표고는 타일로만 읽는다 — 일본은 국토지리원, 나머지(극지도)는 AWS Terrarium. 점 사이에 맞춘 줌이라
  // 긴 선은 거칠다. 그래프 위를 훑으면 그 자리를 지도에 찍는다
  var PROFILE = { W: 640, H: 170, L: 50, R: 10, T: 10, B: 22 };
  var profileSeq = 0, profileData = null, profileSource = null, profileBand = null;
  // 지질 띠 (wetherilli 180) — 켠 레이어 가운데 맨 위의, 우리 파일로 그리는 것(`band`)만. 상류뿐인 곳은 띠가 없다
  function bandLayer() {
    if (STATIC || !window.GSMBand) return null;
    var top = active.filter(function (e) { return e.layer.getVisible() && byName[e.name] && byName[e.name].band; })[0];
    return top ? top.name : null;
  }
  function profileMark(ll) {
    if (!profileSource) {
      profileSource = new ol.source.Vector();
      map.addLayer(new ol.layer.Vector({ source: profileSource, zIndex: 120, style: new ol.style.Style({
        image: new ol.style.Circle({ radius: 6, fill: new ol.style.Fill({ color: "#c9a24b" }),
                                     stroke: new ol.style.Stroke({ color: "#fff", width: 2 }) }) }) }));
    }
    profileSource.clear();
    if (ll) profileSource.addFeature(new ol.Feature(new ol.geom.Point(fromLL(ll))));
  }
  function hideProfile() {
    profileSeq += 1;
    profileData = null;
    var box = document.getElementById("profile");
    if (box) box.hidden = true;
    if (profileSource) profileSource.clear();
  }
  function showProfile(coords) {
    var seq = ++profileSeq, box = document.getElementById("profile");
    profileData = null;
    profileBand = null;
    box.hidden = false;
    document.getElementById("profile-svg").innerHTML = "";
    if (window.GSMBand) GSMBand.reset(document.getElementById("profile-svg"), PROFILE);
    document.getElementById("profile-sum").textContent = "";
    document.getElementById("profile-read").textContent = T("높이를 읽는 중…");
    var length = ol.sphere.getLength(new ol.geom.LineString(coords), { projection: "EPSG:4326" });
    // 30 m 에 한 점쯤, 64–512 점
    var n = Math.max(64, Math.min(512, Math.round(length / 30)));
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
          GSMBand.draw(document.getElementById("profile-svg"), PROFILE, profileData.X, d, band, T("지질"));
          profileData.read = T("{read} · 지질 띠 — {layer}", { read: profileData.read, layer: layerTitle(layer) });
          document.getElementById("profile-read").textContent = profileData.read;
        });
      })
      .catch(function () { if (seq === profileSeq) document.getElementById("profile-read").textContent = T("높이를 읽지 못했다"); });
  }
  function asHeight(m) { return Math.round(m).toLocaleString() + " m"; }
  function drawProfile(d) {
    var P = PROFILE, pw = P.W - P.L - P.R, ph = P.H - P.T - P.B;
    var got = d.elev.filter(function (e) { return e !== null; });
    if (!got.length) { document.getElementById("profile-read").textContent = T("높이를 읽지 못했다"); return; }
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
    var svg = "<g>";
    [y0 + (y1 - y0) * 0.1, (y0 + y1) / 2, y1 - (y1 - y0) * 0.1].forEach(function (e) {
      svg += '<line class="grid" x1="' + P.L + '" x2="' + (P.W - P.R) + '" y1="' + Y(e).toFixed(1) + '" y2="' + Y(e).toFixed(1) + '"/>' +
             '<text class="tick" x="' + (P.L - 5) + '" y="' + (Y(e) + 3.5).toFixed(1) + '" text-anchor="end">' +
             esc(Math.round(e).toLocaleString()) + "</text>";
    });
    [0, 0.5, 1].forEach(function (f) {
      svg += '<text class="tick" x="' + X(total * f).toFixed(1) + '" y="' + (P.H - 6) + '" text-anchor="' +
             (f === 0 ? "start" : f === 1 ? "end" : "middle") + '">' + esc(asLength(total * f)) + "</text>";
    });
    svg += '</g><path class="area" d="' + area + '"/><path class="line" d="' + path + '"/>' +
           '<line class="cursor" id="profile-cursor" y1="' + P.T + '" y2="' + (P.T + ph) + '" visibility="hidden"/>' +
           '<circle class="dot" id="profile-dot" r="3.5" visibility="hidden"/>';
    document.getElementById("profile-svg").innerHTML = svg;
    document.getElementById("profile-sum").textContent = T("최저 {lo} · 최고 {hi} · 오르막 {up} · 내리막 {down}",
      { lo: asHeight(lo), hi: asHeight(hi), up: asHeight(up), down: asHeight(down) });
    var read = (d.sources || []).some(function (s) { return s.indexOf("gsi") === 0; })
      ? T("국토지리원·AWS 표고 타일에서 읽은 해발 높이 — 바다는 수심(음수)") : T("AWS 표고 타일(SRTM·GMTED)에서 읽은 해발 높이 — 바다는 수심(음수)");
    document.getElementById("profile-read").textContent = read;
    profileData = { d: d, X: X, Y: Y, total: total, read: read };
  }
  function initProfile() {
    var svg = document.getElementById("profile-svg");
    if (!svg) return;
    svg.addEventListener("mousemove", function (evt) {
      if (!profileData) return;
      var r = svg.getBoundingClientRect(), P = PROFILE;
      var x = (evt.clientX - r.left) * P.W / r.width;
      var dist = Math.max(0, Math.min(1, (x - P.L) / (P.W - P.L - P.R))) * profileData.total;
      var d = profileData.d, best = 0;
      for (var i = 1; i < d.dist.length; i++) if (Math.abs(d.dist[i] - dist) < Math.abs(d.dist[best] - dist)) best = i;
      var cx = profileData.X(d.dist[best]).toFixed(1), cur = document.getElementById("profile-cursor");
      var dot = document.getElementById("profile-dot");
      cur.setAttribute("x1", cx); cur.setAttribute("x2", cx); cur.setAttribute("visibility", "visible");
      if (d.elev[best] !== null) {
        dot.setAttribute("cx", cx); dot.setAttribute("cy", profileData.Y(d.elev[best]).toFixed(1));
        dot.setAttribute("visibility", "visible");
      } else dot.setAttribute("visibility", "hidden");
      var unit = window.GSMBand ? GSMBand.unitAt(profileBand, best) : "";
      var at = { d: asLength(d.dist[best]), h: d.elev[best] === null ? "—" : asHeight(d.elev[best]), unit: unit };
      document.getElementById("profile-read").textContent = unit ? T("거리 {d} · 높이 {h} · {unit}", at) : T("거리 {d} · 높이 {h}", at);
      profileMark([d.lon[best], d.lat[best]]);
    });
    svg.addEventListener("mouseleave", function () {
      if (!profileData) return;
      document.getElementById("profile-cursor").setAttribute("visibility", "hidden");
      document.getElementById("profile-dot").setAttribute("visibility", "hidden");
      document.getElementById("profile-read").textContent = profileData.read;
      profileMark(null);
    });
    document.getElementById("profile-close").addEventListener("click", hideProfile);
  }

  // ── 점 레이어 (그린란드 정부 포털) ──────────────────────────────
  //
  // 타일이 아니라 **점을 통째로** 받아 여기서 그린다 (devlog 019). 서버의
  // `./points/?layer=` 가 한 레이어를 GeoJSON 한 덩이로 준다 — 2 만 점도
  // 줄여(gzip) 0.4 MB 다. 누르면 받아 둔 속성을 그 자리에서 읽는다.
  //
  // 이 덩이 밖에서는 `addLayer`·`renderActive`·`onClick`·비교 칸이 `kind` 를
  // 보고 한 줄씩 갈라 여기를 부를 뿐이다. 켜기·끄기·투명도·차례는 타일
  // 레이어와 같은 길을 탄다 — `entry.layer` 가 ol 레이어이기만 하면 된다.
  // 좌표계는 **지도의 것을 따른다** (`projection` 인자 — 화면이 3857 이 아닐 수 있다).

  //: 연대(Ma)의 갈래. 색은 ICS 국제층서표의 누대·대 색을 바탕으로, 그린란드에
  //  많은 원생누대·시생누대는 더 잘게 가르고 서로 가려 보이게 짙기를 벌렸다.
  var AGE_CLASSES = [
    { upto: 66, color: "#f2f91d", label: "신생대" },
    { upto: 252, color: "#67c5ca", label: "중생대" },
    { upto: 541, color: "#99c08d", label: "고생대" },
    { upto: 1000, color: "#feb342", label: "신원생대" },
    { upto: 1600, color: "#fd8d3c", label: "중원생대" },
    { upto: 2500, color: "#f74370", label: "고원생대" },
    { upto: 2800, color: "#c51b7d", label: "신시생대" },
    { upto: Infinity, color: "#7a0177", label: "중시생대 이전" },
  ];
  //  NPI(021)의 시료 보관소(`rock`)는 노르웨이 국기의 빨강, 야외 조사 지점(`site`)은 짙은 청.
  var POINT_COLORS = { mineral: "#d7301f", intrusion: "#6a3d9a", sample: "#8c8c8c", none: "#9e9e9e",
                       rock: "#ba0c2f", site: "#3f6d9e" };
  //: 한 번 누를 때 레이어 하나에서 팝업에 올리는 점의 수. 한 시료에 연대가
  //  여럿 딸린 자리가 많아 하나로는 모자라고, 다 올리면 팝업이 읽히지 않는다.
  var POINT_POPUP_MAX = 6;

  /** 점 레이어 한 덩이의 주소. 정적 판은 구워 둔 파일 `points/<상류>/<이름>.json` — 물음(`?layer=`)을 파일로 둘 수
   *  없어서다. 얀마옌·극지연구소처럼 언어마다 답이 다른 것은 영어판 `.en.json` 이 따로 있다 (wetherilli 160·165) */
  function pointsUrl(name) {
    // 판이 있는 덩이(지구 자료 점, wetherilli 185)는 `&v=` 를 붙인다 — 판이 같으면 브라우저가 오래 들고 있다
    var ver = byName[name] && byName[name].version;
    if (!STATIC) return BASE + "points/?layer=" + encodeURIComponent(name) + "&lang=" + LANG + (ver ? "&v=" + encodeURIComponent(ver) : "");
    var en = LANG === "en" && staticBaked("points")[name];
    return BASE + "points/" + name.replace(":", "/") + (en ? ".en" : "") + ".json";
  }

  function pointLayerFor(row) {
    var layer;
    var source = new ol.source.Vector({
      attributions: pointAttribution(row),
      loader: function (extent, resolution, projection, success, failure) {
        // 잘라 주는 레이어(전암 화학, wetherilli 163)는 고른 원소의 점만 받는다. 정적 판은 구운 덩이 하나라 자르지 않는다
        var slice = row.slice && !STATIC ? "&value=" + encodeURIComponent(storedValue()) : "";
        // 정적 판에서 구워 싣지 않은 극지 점은 상류(ArcGIS)에서 곧장 받는다 — 서버의 `/points/` 와 같은 덩이로 온다 (wetherilli 161)
        var live = STATIC && !Object.prototype.hasOwnProperty.call(staticBaked("points"), row.name) && layerKind(row.name).points;
        (live ? layerKind(row.name).points(row.name, row) : fetch(pointsUrl(row.name) + slice)
          .then(function (r) {
            if (r.ok) return r.json();
            // 서버가 까닭을 적어 보낸다 — "자료가 서버에 없다" 따위. 패널에 띄운다
            return r.json().catch(function () { return {}; }).then(function (d) {
              layer.set("gsmError", d.error || "");
              throw new Error(String(r.status));
            });
          }))
          .then(function (data) {
            var features = new ol.format.GeoJSON().readFeatures(data, {
              dataProjection: "EPSG:4326",
              featureProjection: projection || map.getView().getProjection(),
            });
            layer.set("gsmLabels", data.labels || {});
            // 링크로 그릴 열. 서버(`arcpoints.links`)가 적어 준다 — 옛 서버면 `link` 하나
            layer.set("gsmLinks", data.links || ["link"]);
            layer.set("gsmLegend", data.legend || null);
            // 연속값 레이어(지화학, wetherilli 159) — 고를 수 있는 원소와 처음의 원소
            if (data.values) { layer.set("gsmValues", data.values); layer.set("gsmDefault", data.default || ""); }
            if (data.slice) { layer.set("gsmSlice", data.slice); layer.set("gsmTotal", data.total || 0); }
            layer.set("gsmCount", features.length);
            // 극지연구소(055) — 남극 전체를 덮는 넓은 범위라 그리지 않은 자료의 수
            layer.set("gsmWide", data.wide || 0);
            source.addFeatures(features);
            // 암맥(026) — 멀리서 볼 도폭별 로즈를 같은 자료에서 세어 곁들인다
            if (row.style === "dike") source.addFeatures(dikeRoses(features));
            if (success) success(features);
            renderActive();
          })
          .catch(function () {
            layer.set("gsmFailed", true);
            source.removeLoadedExtent(extent);
            if (failure) failure();
            renderActive();
          });
      },
    });
    // 면이 만 개를 넘는 것(중국 geo3al, 025)은 한 장으로 구워 그린다 — 움직이는 동안
    // 다시 칠하지 않아 끌기가 버벅이지 않는다. 누른 자리 찾기는 그대로 된다
    var Kind = row.render === "image" ? ol.layer.VectorImage : ol.layer.Vector;
    layer = new Kind({
      source: source,
      style: row.style === "dike" ? dikeStyle()
        : row.style === "sheet" ? sheetStyle()
        : row.style === "value" ? valueStyle(function () { return layer; })
        : LEGEND_STYLED[row.style] ? legendStyle(row.style, function () { return layer; })
        : portalPointStyle(row.style || "sample"),
      opacity: 1,
      // 겹친 점을 하나씩 그린다 — 2 만 점이라 글자처럼 걸러내지(declutter) 않는다
    });
    layer.set("gsmPoints", row.name);
    if (row.periods) layer.set("gsmPeriods", row.periods);
    return layer;
  }

  // ── 기간을 고르는 점 레이어 — 아라온호 항적 (koprifossillab 017) ──
  //
  // 서버가 레이어에 고를 기간(`periods`, 날수 — 앞의 것이 기본)을, 조각마다 `ago`(지금에서 며칠 전)를 붙여 준다. 고른 기간
  // 안의 조각만 그리고, 오래된 것일수록 옅게 한다. 고른 것은 이 브라우저에 기억한다 — 온 지구 화면과 같은 열쇠다
  var PERIOD_KEY = "gsm.araon.period";
  var PERIOD_LABELS = { 30: "1개월", 182: "6개월", 365: "1년" };
  function periodOf(periods) {
    var v = 0;
    try { v = +localStorage.getItem(PERIOD_KEY); } catch (e) { /* 사생활 모드 */ }
    return periods.indexOf(v) >= 0 ? v : periods[0];
  }
  /** 며칠 전이 기간의 어디쯤인가로 진하기 — 지금 1, 기간 끝 0.15. 기간 밖이면 0. 열 칸으로 끊어 그림을 아낀다 */
  function periodFade(periods, ago) {
    var period = periodOf(periods);
    if (ago > period) return 0;
    return Math.round((1 - 0.85 * ago / period) * 10) / 10;
  }
  function periodPicker(entry, periods) {
    var row = document.createElement("div");
    row.className = "period-row";
    var select = document.createElement("select");
    select.setAttribute("aria-label", T("항적 기간"));
    periods.forEach(function (days) {
      var option = document.createElement("option");
      option.value = days;
      option.textContent = T(PERIOD_LABELS[days] || "{n}일", { n: days });
      select.appendChild(option);
    });
    select.value = periodOf(periods);
    select.addEventListener("change", function () {
      try { localStorage.setItem(PERIOD_KEY, select.value); } catch (e) { /* 사생활 모드 */ }
      // 같은 열쇠를 쓰는 다른 탭의 항적도 함께 — 켠 것만 다시 그리면 된다
      active.forEach(function (e) { if (e.layer.get && e.layer.get("gsmPeriods")) e.layer.changed(); });
    });
    var label = document.createElement("span");
    label.className = "period-label";
    label.textContent = T("항적 기간");
    row.append(label, select);
    return row;
  }

  /** 지도 귀퉁이의 출처. 레이어마다 같은 글로 적어 OL 이 한 줄로 합치게 한다 —
   *  레이어별 항목 주소는 범례 칸에 둔다(`pointLegend`). */
  function pointAttribution(row) {
    if (row.attribution) return row.attribution;       // 얀마옌(NPI) — 서버가 적어 준다
    // 다이아몬드 탐사 자료(DED)는 CC BY 4.0 이 적혀 있다 (wetherilli 157)
    if (row.license) {
      return '<a href="' + esc(row.portal || "") + '" target="_blank" rel="noopener">' +
        esc(T("그린란드 정부 광물자원 포털")) + "</a> · " + esc(row.license);
    }
    return '<a href="' + esc(row.portal || "") + '" target="_blank" rel="noopener">' +
      esc(T("그린란드 정부 광물자원 포털")) + "</a> · GEUS · " + esc(T("이용 조건 표시 없음"));
  }

  function ageColor(age) {
    if (typeof age !== "number" || !isFinite(age)) return POINT_COLORS.none;
    for (var i = 0; i < AGE_CLASSES.length; i++) {
      if (age < AGE_CLASSES[i].upto) return AGE_CLASSES[i].color;
    }
    return POINT_COLORS.none;
  }

  /** 점의 모양. 연대는 동그라미(색=연대), 광물 산출지는 마름모, 관입암체는
   *  세모, 시료는 포털이 시료 갈래마다 매긴 색의 작은 동그라미.
   *  멀리서는 작게 그린다 — 2 만 점이 그린란드 하나를 덮는다.
   *
   *  이름을 점묶음의 `pointStyle(color)` 와 갈랐다. 같은 이름이면 뒤의 것이
   *  이겨서 포털 점이 "age" 를 색으로 읽고 하나도 안 그려진다 (합칠 때 보았다). */
  function portalPointStyle(kind) {
    var cache = {};
    return function (feature, resolution) {
      var far = mercZoom(resolution) < 6;
      var color = kind === "age" ? ageColor(feature.get("age"))
        : kind === "sample" ? (feature.get("color") || POINT_COLORS.sample)
        : POINT_COLORS[kind] || POINT_COLORS.none;
      var key = color + (far ? "f" : "n");
      if (cache[key]) return cache[key];
      var fill = new ol.style.Fill({ color: color });
      var stroke = new ol.style.Stroke({ color: kind === "sample" && far ? "rgba(0,0,0,0)" : "rgba(20,20,20,0.85)",
                                         width: far ? 0.6 : 1 });
      var r = kind === "sample" || kind === "site" ? (far ? 2 : 3.5) : (far ? 4 : 6);
      var image = kind === "mineral"
        ? new ol.style.RegularShape({ points: 4, radius: r + 1.5, angle: 0, fill: fill, stroke: stroke })
        : kind === "intrusion"
        ? new ol.style.RegularShape({ points: 3, radius: r + 1.5, angle: 0, fill: fill, stroke: stroke })
        : new ol.style.Circle({ radius: r, fill: fill, stroke: stroke });
      cache[key] = new ol.style.Style({ image: image });
      return cache[key];
    };
  }

  // ── 연속값 색 (wetherilli 159) ─────────────────────────────────
  //
  // 점마다 숫자 하나(지화학이면 고른 원소의 함량)를 **분위수 일곱 칸**으로 나눠 viridis 로 칠한다 — 사람이 골랐다.
  // 칸은 그 레이어에 받은 점들의 측정값(양수)으로 화면이 셈한다. 지화학의 관례대로 음수는 **검출 한계 밑**(속이 빈 회색
  // 동그라미), 값이 없는 점(분석하지 않은 것)은 그리지 않는다. 고른 원소는 레이어마다가 아니라 한 열쇠에 기억한다 —
  // 토양·중광물·회사·애추를 같은 원소로 견주게. 그 레이어에 없는 원소면 서버가 적은 처음 원소로 돌아간다
  var VALUE_RAMP = ["#440154", "#443983", "#31688e", "#21918c", "#35b779", "#90d743", "#fde725"];   // viridis 일곱
  var VALUE_KEY = "gsm.value.element";
  var VALUE_BELOW = "#9e9e9e";
  //: 한계를 모르는 검출 한계 밑의 표지 — 서버의 `arcpoints.BELOW_UNKNOWN`(−1e-9). 이것만큼 작으면 한계를 적지 않는다
  var VALUE_UNKNOWN_BELOW = 1e-6;
  function storedValue() {
    try { return localStorage.getItem(VALUE_KEY) || ""; } catch (e) { return ""; }
  }
  function valueChoice(layer) {
    // 잘라 받은 레이어는 받은 원소가 곧 고른 원소다 — 받는 사이에 다른 것을 골랐어도 그린 것과 범례가 어긋나지 않게
    if (layer.get("gsmSlice")) return layer.get("gsmSlice");
    var values = layer.get("gsmValues") || [], chosen = storedValue();
    var has = function (k) { return values.some(function (v) { return v.key === k; }); };
    if (has(chosen)) return chosen;
    if (has(layer.get("gsmDefault"))) return layer.get("gsmDefault");
    return values.length ? values[0].key : "";
  }
  function valueSpec(layer) {
    var key = valueChoice(layer);
    return (layer.get("gsmValues") || []).filter(function (v) { return v.key === key; })[0] || null;
  }
  /** 고른 원소의 칸 경계 `[b1 … b6]`(측정값의 1/7 … 6/7 분위수). 같은 값이 많으면 겹친 경계를 걷어 칸이 줄어든다 */
  function valueBreaks(layer) {
    var key = valueChoice(layer), memo = layer.get("gsmBreaks");
    if (memo && memo.key === key && memo.n === layer.getSource().getFeatures().length) return memo.breaks;
    var nums = [];
    layer.getSource().getFeatures().forEach(function (f) {
      var v = f.get(key);
      if (typeof v === "number" && v > 0) nums.push(v);
    });
    nums.sort(function (a, b) { return a - b; });
    var breaks = [];
    for (var i = 1; i < VALUE_RAMP.length && nums.length; i++) {
      var b = nums[Math.min(nums.length - 1, Math.floor(nums.length * i / VALUE_RAMP.length))];
      if (!breaks.length || b > breaks[breaks.length - 1]) breaks.push(b);
    }
    var out = { lo: nums[0], hi: nums[nums.length - 1], breaks: breaks, count: nums.length };
    layer.set("gsmBreaks", { key: key, n: layer.getSource().getFeatures().length, breaks: out }, true);
    return out;
  }
  /** 값 → 칸 번호. 칸이 줄었으면 램프의 양 끝을 살려 고르게 뽑는다 */
  function valueClass(br, v) {
    var i = 0;
    while (i < br.breaks.length && v >= br.breaks[i]) i++;
    var n = br.breaks.length + 1;
    return n === 1 ? VALUE_RAMP.length - 1 : Math.round(i * (VALUE_RAMP.length - 1) / (n - 1));
  }
  function valueStyle(getLayer) {
    var cache = {};
    return function (feature, resolution) {
      var layer = getLayer(), key = valueChoice(layer), v = feature.get(key);
      if (typeof v !== "number") return null;               // 분석하지 않은 점
      var far = mercZoom(resolution) < 6;
      var cls = v < 0 ? "below" : valueClass(valueBreaks(layer), v);
      var id = cls + (far ? "f" : "n");
      if (cache[id]) return cache[id];
      var image = cls === "below"
        ? new ol.style.Circle({ radius: far ? 2 : 3, stroke: new ol.style.Stroke({ color: VALUE_BELOW, width: 1 }) })
        : new ol.style.Circle({ radius: far ? 3 : 5, fill: new ol.style.Fill({ color: VALUE_RAMP[cls] }),
                                stroke: new ol.style.Stroke({ color: "rgba(255,255,255,0.85)", width: far ? 0.5 : 0.8 }) });
      // 높은 값이 위에 그려지게 — 낮은 칸부터 먼저
      cache[id] = new ol.style.Style({ image: image, zIndex: cls === "below" ? -1 : cls });
      return cache[id];
    };
  }
  function valueNumber(v) {
    var a = Math.abs(v);
    return a >= 1000 ? Math.round(v).toLocaleString() : String(+v.toPrecision(3));
  }
  function valueLabel(spec) { return T(spec.label) + " (" + spec.unit + ")"; }
  /** 켠 레이어 카드의 원소 고르개 */
  function valuePicker(entry) {
    var values = entry.layer.get("gsmValues");
    if (!values || !values.length) return null;
    var row = document.createElement("div");
    row.className = "period-row";
    var label = document.createElement("span");
    label.className = "period-label";
    label.textContent = T("칠할 원소");
    var select = document.createElement("select");
    select.setAttribute("aria-label", T("칠할 원소"));
    values.forEach(function (v) {
      var option = document.createElement("option");
      option.value = v.key;
      option.textContent = valueLabel(v) + " — " + T("{n}점", { n: v.n.toLocaleString() });
      select.appendChild(option);
    });
    select.value = valueChoice(entry.layer);
    select.addEventListener("change", function () {
      try { localStorage.setItem(VALUE_KEY, select.value); } catch (e) { /* 사생활 모드 */ }
      // 같은 열쇠를 쓰는 다른 지화학 레이어도 함께 다시 칠한다. 잘라 받은 레이어는 그 원소의 점을 다시 받는다
      active.forEach(function (e) {
        if (!e.layer.get || !e.layer.get("gsmValues")) return;
        if (e.layer.get("gsmSlice")) {
          e.layer.unset("gsmSlice");
          e.layer.unset("gsmBreaks");
          e.layer.getSource().clear(true);
          e.layer.getSource().refresh();
        } else e.layer.changed();
      });
      renderActive();
    });
    row.append(label, select);
    return row;
  }
  function valueLegend(entry, row, box) {
    var layer = entry.layer, spec = valueSpec(layer);
    if (!spec) {
      box.appendChild(note(layer.get("gsmFailed") ? (layer.get("gsmError") || T("점을 받지 못했다")) : T("받는 중…")));
      return box;
    }
    var br = valueBreaks(layer), key = spec.key, counts = {}, below = 0, none = 0;
    layer.getSource().getFeatures().forEach(function (f) {
      var v = f.get(key);
      if (typeof v !== "number") none++;
      else if (v < 0) below++;
      else { var c = valueClass(br, v); counts[c] = (counts[c] || 0) + 1; }
    });
    var head = document.createElement("div");
    head.className = "value-head";
    head.textContent = valueLabel(spec) + " · " + T("분위수로 나눈 칸");
    box.appendChild(head);
    var edges = [br.lo].concat(br.breaks, [br.hi]), n = br.breaks.length + 1;
    for (var i = br.count ? n - 1 : -1; i >= 0; i--) {         // 높은 칸이 위
      var cls = n === 1 ? VALUE_RAMP.length - 1 : Math.round(i * (VALUE_RAMP.length - 1) / (n - 1));
      var line = document.createElement("div");
      var sw = document.createElement("span");
      sw.className = "sw dot";
      sw.style.background = VALUE_RAMP[cls];
      var text = document.createElement("span");
      text.textContent = valueNumber(edges[i]) + " – " + valueNumber(edges[i + 1]) + "  (" + (counts[cls] || 0) + ")";
      line.append(sw, text);
      box.appendChild(line);
    }
    if (below) {
      var bl = document.createElement("div"), bsw = document.createElement("span"), bt = document.createElement("span");
      bsw.className = "sw dot";
      bsw.style.background = "transparent";
      bsw.style.border = "1.5px solid " + VALUE_BELOW;
      bt.textContent = T("검출 한계 밑") + "  (" + below + ")";
      bl.append(bsw, bt);
      box.appendChild(bl);
    }
    // 잘라 받은 레이어는 그 원소가 있는 점만 받았다 — 분석하지 않은 수는 전체 점의 수에서 뺀다
    if (layer.get("gsmSlice")) none = Math.max(0, (layer.get("gsmTotal") || 0) - layer.getSource().getFeatures().length);
    if (none) box.appendChild(note(T("분석하지 않은 {n}점은 그리지 않았다", { n: none.toLocaleString() })));
    if (row.source) {
      var a = document.createElement("a");
      a.className = "proplink";
      a.href = row.source;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = T("포털의 원본 항목 — 이용 조건 표시 없음");
      box.appendChild(a);
    }
    return box;
  }

  /** 누른 점 하나 → 팝업 한 칸. 이름은 서버가 준 한국어(`labels`)이고
   *  영어판이면 팝업이 `T()` 로 옮긴다(`i18n.PROP_EN`). */
  /** 스발바르 도폭 경계 — 선만 긋고 속은 비운다(밑의 지질도가 보이게). 속을 아주 옅게
   *  칠해 두는 것은 면 안쪽을 눌러도 걸리게 하려는 것이다. 가까이 오면 번호·이름을 적는다. */
  var SHEET_COLOR = "#1d3b6e";
  function sheetStyle() {
    var fill = new ol.style.Fill({ color: "rgba(29, 59, 110, 0.04)" });
    var stroke = new ol.style.Stroke({ color: SHEET_COLOR, width: 1.6 });
    var plain = new ol.style.Style({ fill: fill, stroke: stroke });
    return function (feature, resolution) {
      var zoom = mercZoom(resolution);
      if (zoom < 5) return plain;
      var text = feature.get("code") + (zoom >= 7 && feature.get("name") ? " " + feature.get("name") : "");
      return new ol.style.Style({
        fill: fill, stroke: stroke,
        text: new ol.style.Text({
          text: text, font: "bold 12px sans-serif", overflow: false,
          fill: new ol.style.Fill({ color: SHEET_COLOR }),
          stroke: new ol.style.Stroke({ color: "rgba(255,255,255,0.9)", width: 3 }),
        }),
      });
    };
  }

  /** 도폭 경계를 누르면 뜨는 "이 도폭만 켜기" — 스캔이 있는 도폭에만. */
  function sheetAction(feature) {
    var code = feature.get("code");
    if (!feature.get("scan") || !code) return null;
    var name = "npolar:svalbard_sheets@" + code;
    return { text: "", links: [{ label: T("이 도폭만 켜기"), action: function () {
      sheetRow(name, feature.get("name"));
      addLayer(name);
    } }] };
  }

  function pointPart(feature, layer, seen) {
    var name = layer.get("gsmPoints");
    seen[name] = (seen[name] || 0) + 1;
    if (seen[name] > POINT_POPUP_MAX) return null;
    var labels = layer.get("gsmLabels") || {};
    var props = {};
    Object.keys(labels).forEach(function (key) {
      var value = feature.get(key);
      if (value === undefined || value === null || value === "") return;
      if ((layer.get("gsmLinks") || ["link"]).indexOf(key) >= 0) {
        // 서버가 http·https 만 넘긴다(`arcpoints.clean`). 여기서 한 번 더 본다
        if (!/^https?:\/\//i.test(String(value))) return;
        value = { text: "", links: [{ url: String(value), label: T("열기") }] };
      }
      props[labels[key]] = value;
    });
    if ((byName[name] || {}).style === "value") {
      // 고른 원소의 값 한 줄 — 원소 열 일흔다섯을 다 올리면 팝업이 읽히지 않는다
      var spec = valueSpec(layer), v = spec && feature.get(spec.key);
      if (spec) {
        props[valueLabel(spec)] = typeof v !== "number" ? T("분석하지 않음")
          : v < 0 ? (-v < VALUE_UNKNOWN_BELOW ? T("검출 한계 밑") : T("검출 한계 밑 (< {n})", { n: valueNumber(-v) }))
          : valueNumber(v);
      }
    }
    if ((byName[name] || {}).style === "sheet") {
      var action = sheetAction(feature);
      if (action) props[T("스캔")] = action;
    }
    return { title: layerTitle(name), props: props };
  }

  /** 일본 지질도의 범례 (devlog 024). 원본은 2 416 칸이라 그림으로 받지 않고
   *  **보는 범위에 든 것만** 물어 여기서 그린다 — 지도를 옮기면 다시 묻는다
   *  (`refreshExtentLegends`). 간략판은 14 칸을 통째로, 선·기호는 원본 뷰어로 잇는다. */
  function gsjLegend(entry) {
    var row = byName[entry.name] || {};
    var box = document.createElement("div");
    box.className = "vector-legend";
    if (row.legend === "none") {
      box.appendChild(note(T("선·기호의 범례는 GSJ 가 따로 주지 않는다")));
      var a = document.createElement("a");
      a.className = "proplink";
      a.href = row.viewer;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = T("원본 뷰어에서 본다 — GSJ");
      box.appendChild(a);
      return box;
    }
    box.appendChild(note(T("받는 중…")));
    var q = { layer: entry.name };
    if (row.legend === "extent") {
      var view = map.getView();
      var ext = ol.proj.transformExtent(view.calculateExtent(map.getSize()), viewProj(), "EPSG:4326");
      q.bbox = [Math.max(ext[0], -180), Math.max(ext[1], -85), Math.min(ext[2], 180), Math.min(ext[3], 85)]
        .map(function (v) { return v.toFixed(2); }).join(",");
      q.z = Math.round(view.getZoom());
    }
    // 대만(wetherilli 142)도 같은 꼴의 범례를 준다 — 주소는 카탈로그 행이 알린다
    fetch(BASE + (row.legendUrl || "gsj/legend/") + "?" + new URLSearchParams(q).toString())
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.d.error || "");
        var rows = res.d.rows || [];
        box.innerHTML = "";
        if (row.legend === "extent") {
          box.appendChild(note(rows.length ? T("지금 보는 범위에 든 것 {n}칸", { n: rows.length + (res.d.more || 0) })
            : T("지금 보는 범위에는 칠해진 것이 없다")));
        }
        rows.forEach(function (r) {
          var line = document.createElement("div");
          var sw = document.createElement("span");
          sw.className = "sw box";
          sw.style.background = r.color;
          // 무늬가 있는 지층은 그림 조각을 견본으로 준다(대만) — 색 한 칸으로는 빗금·점이 안 보인다
          if (r.swatch) {
            sw.style.backgroundImage = "url(" + r.swatch + ")";
            sw.style.backgroundSize = "cover";
            sw.style.imageRendering = "pixelated";
          }
          var label = document.createElement("span");
          label.textContent = (r.symbol && r.swatch ? r.symbol + " " : "") + r.lithology + (r.age ? " — " + r.age : "");
          label.title = r.symbol;
          line.append(sw, label);
          box.appendChild(line);
        });
        if (res.d.more) box.appendChild(note(T("…그 밖 {n}칸 — 더 들어가면 줄어든다", { n: res.d.more })));
      })
      .catch(function (err) {
        box.innerHTML = "";
        box.appendChild(note(err.message || T("범례를 받지 못했다")));
      });
    return box;
  }

  /** 갈래마다 색 한 칸인 범례 — 서버가 카탈로그 행에 표째 보낸다(`classLegend`, IBCSO 자료 출처 071).
   *  이름은 서버가 이미 화면 말로 옮겨 보냈다. */
  function classLegend(table) {
    var box = document.createElement("div");
    box.className = "vector-legend";
    (table.groups || []).forEach(function (group) {
      var head = document.createElement("div");
      head.className = "vector-legend-head";
      head.textContent = group.name;
      box.appendChild(head);
      group.rows.forEach(function (r) {
        var line = document.createElement("div");
        var sw = document.createElement("span");
        sw.className = "sw box";
        sw.style.background = r.color;
        var label = document.createElement("span");
        label.textContent = r.label;
        label.title = "TID " + r.code;
        line.append(sw, label);
        box.appendChild(line);
      });
    });
    return box;
  }

  /** 지도를 옮기면 범위 범례만 다시 받는다. 목록 전체를 다시 그리지 않는다. */
  function refreshExtentLegends() {
    active.forEach(function (entry) {
      var row = byName[entry.name];
      if (!entry.legendBox || !row || row.legend !== "extent") return;
      var fresh = gsjLegend(entry);
      entry.legendBox.replaceWith(fresh);
      entry.legendBox = fresh;
    });
  }

  /** 범례 자리. 타일 레이어는 상류의 범례 그림을 받지만, 점 레이어는
   *  여기서 그린 색이 곧 범례다. */
  function pointLegend(entry) {
    var row = byName[entry.name] || {};
    var kind = row.style || "sample";
    var box = document.createElement("div");
    box.className = "vector-legend";
    if (LEGEND_STYLED[kind]) return dataLegend(entry, row, box);
    if (kind === "value") return valueLegend(entry, row, box);
    if (kind === "dike") return dikeLegend(entry, row, box);
    function item(color, text, shape) {
      var line = document.createElement("div");
      var sw = document.createElement("span");
      sw.className = "sw " + (shape || "dot");
      sw.style.background = color;
      var label = document.createElement("span");
      label.textContent = text;
      line.append(sw, label);
      box.appendChild(line);
    }
    if (kind === "age") {
      AGE_CLASSES.forEach(function (c, i) {
        var from = i ? AGE_CLASSES[i - 1].upto : 0;
        var span = isFinite(c.upto) ? from + "–" + c.upto + " Ma" : "≥ " + from + " Ma";
        item(c.color, T(c.label) + "  " + span);
      });
    } else if (kind === "sample") {
      item(POINT_COLORS.sample, T("색은 포털이 시료 갈래마다 매긴 것이다"));
    } else {
      item(POINT_COLORS[kind], entry.title, kind === "mineral" ? "diamond"
        : kind === "intrusion" ? "triangle" : "dot");
    }
    var count = entry.layer.get("gsmCount");
    var foot = entry.layer.get("gsmFailed") ? T("점을 받지 못했다")
      : count === undefined ? T("받는 중…") : T("{n}점", { n: count.toLocaleString() });
    box.appendChild(note(foot));
    if (row.source) {
      var a = document.createElement("a");
      a.className = "proplink";
      a.href = row.source;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      // NPI(021)는 CC BY 4.0 이라 적혀 있다. 그린란드 포털은 적혀 있지 않다(019)
      a.textContent = row.license ? T("원본 자료 — Norsk Polarinstitutt, CC BY 4.0")
        : T("포털의 원본 항목 — 이용 조건 표시 없음");
      box.appendChild(a);
    }
    return box;
  }

  // ── 자료가 색을 주는 레이어 — 얀마옌 지질도 (devlog 022) ─────────
  //
  // 포털 점과 같은 길(`/points/`)로 오지만 선·면도 싣고, 색은 자료가 준다.
  // 서버가 `legend` 에 geo_code 마다 색·굵기·끊음·모양을 적어 보내고, 그리는 것과
  // 범례가 같은 표를 읽는다 — 둘이 어긋날 수 없다. 면의 색은 feature 의 `color`
  // (자료의 `rgb` 열)다.
  var LEGEND_STYLED = { unit: true, line: true, vent: true, "class": true };

  function legendStyle(kind, getLayer) {
    var cache = {};
    return function (feature, resolution) {
      var code = feature.get("code");
      if (kind === "class") return classStyle(feature, resolution, getLayer, cache);
      if (cache[code]) return cache[code];
      var table = {};
      (getLayer().get("gsmLegend") || []).forEach(function (r) { table[r.code] = r; });
      var spec = table[code] || {};
      var color = feature.get("color") || spec.color || "#888888";
      var style;
      if (kind === "unit") {
        style = new ol.style.Style({
          fill: new ol.style.Fill({ color: color }),
          stroke: new ol.style.Stroke({ color: "rgba(40, 30, 20, 0.55)", width: 0.6 }),
        });
      } else if (kind === "line") {
        style = [
          new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(255,255,255,0.7)", width: (spec.width || 1.6) + 2 }) }),
          new ol.style.Style({ stroke: new ol.style.Stroke({ color: color, width: spec.width || 1.6,
                                                               lineDash: spec.dash || undefined }) }),
        ];
      } else {
        var fill = new ol.style.Fill({ color: color });
        var stroke = new ol.style.Stroke({ color: "rgba(20,20,20,0.9)", width: 1 });
        style = new ol.style.Style({ image: spec.shape === "star"
          ? new ol.style.RegularShape({ points: 5, radius: 6.5, radius2: 2.8, angle: 0, fill: fill, stroke: stroke })
          : new ol.style.RegularShape({ points: 3, radius: 4.5, angle: 0, fill: fill, stroke: stroke }) });
      }
      cache[code] = style;
      return style;
    };
  }

  /** 극지연구소(053–056) — 서버가 갈래(`code`)마다 색·모양을 준다. 점은 모양대로, 범위(면·선)는
   *  같은 색의 테두리와 옅은 속으로 그린다. 멀리서는 점을 작게 — 암석 시료가 빅토리아랜드에 몰려 있다. */
  function classStyle(feature, resolution, getLayer, cache) {
    var code = feature.get("code");
    var type = feature.getGeometry().getType();
    var far = mercZoom(resolution) < 5;
    // 기간을 고르는 레이어(koprifossillab 017) — 기간 밖은 그리지 않고, 오래된 것일수록 옅게
    var periods = getLayer().get("gsmPeriods"), ago = feature.get("ago"), fade = 1;
    if (periods && ago != null) {
      fade = periodFade(periods, ago);
      if (!fade) return null;
    }
    var key = code + "|" + type + (far ? "f" : "n") + fade;
    if (cache[key]) return cache[key];
    var spec = {};
    (getLayer().get("gsmLegend") || []).forEach(function (r) { if (r.code === code) spec = r; });
    var color = spec.color || "#888888";
    if (fade < 1) { var faded = ol.color.asArray(color).slice(); faded[3] = fade; color = faded; }
    var style;
    if (spec.shape === "line") {
      // 항적(아라온호, koprifossillab 006) — 범례가 선이라 적은 갈래는 굵게, 테두리를 둘러 바다 위에서 보이게
      style = [new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(0,0,0," + 0.55 * fade + ")", width: 4.5 }) }),
               new ol.style.Style({ stroke: new ol.style.Stroke({ color: color, width: 2.5 }) })];
    } else if (spec.shape === "stroke") {
      // 5만 단층·습곡(wetherilli 202) — 굵기·끊김을 서버의 표가 준다. 선이 수천이라 테두리 없이 가늘게
      style = new ol.style.Style({ stroke: new ol.style.Stroke({ color: color, width: spec.width || 1.4,
                                                                lineDash: spec.dash || undefined }) });
    } else if (spec.shape === "dash") {
      // 날짜만 아는 지난 항적(koprifossillab 009) — 지금 쌓는 것과 갈라 보이게 가늘게 끊어
      style = new ol.style.Style({ stroke: new ol.style.Stroke({ color: color, width: 1.6, lineDash: [6, 4] }) });
    } else if (type === "Polygon" || type === "MultiPolygon" || type === "LineString" || type === "MultiLineString") {
      var rgb = ol.color.asArray(color);
      style = new ol.style.Style({
        fill: new ol.style.Fill({ color: [rgb[0], rgb[1], rgb[2], 0.08] }),
        stroke: new ol.style.Stroke({ color: color, width: 1.4 }),
      });
    } else {
      var r = spec.shape === "star" ? 8 : far ? 3 : 4.5;
      var fill = new ol.style.Fill({ color: color });
      var stroke = new ol.style.Stroke({ color: "rgba(255,255,255,0.9)", width: far ? 0.6 : 1 });
      var image = spec.shape === "star"
        ? new ol.style.RegularShape({ points: 5, radius: r, radius2: r * 0.45, angle: 0, fill: fill, stroke: stroke })
        : spec.shape === "diamond"
        ? new ol.style.RegularShape({ points: 4, radius: r + 1.5, angle: 0, fill: fill, stroke: stroke })
        : spec.shape === "square"
        ? new ol.style.RegularShape({ points: 4, radius: r + 1, angle: Math.PI / 4, fill: fill, stroke: stroke })
        // 홀로세 화산(wetherilli 185) — 온 지구 화면처럼 세모
        : spec.shape === "triangle"
        ? new ol.style.RegularShape({ points: 3, radius: r + 1.5, angle: 0, fill: fill,
                                      stroke: new ol.style.Stroke({ color: "rgba(30,20,20,0.9)", width: far ? 0.6 : 1 }) })
        : new ol.style.Circle({ radius: r, fill: fill, stroke: stroke });
      style = new ol.style.Style({ image: image });
    }
    cache[key] = style;
    return style;
  }

  /** 범례 — 서버가 보낸 표(`legend`)를 그대로. 이름은 자료의 영어 이름이라 옮기지 않는다
   *  (극지연구소의 갈래 이름만은 우리가 붙인 한국어라 옮긴다). */
  function dataLegend(entry, row, box) {
    var rows = entry.layer.get("gsmLegend") || [];
    rows.forEach(function (r) {
      var line = document.createElement("div");
      if (r.depth) line.style.paddingLeft = (r.depth * 14) + "px";
      var sw;
      if (row.style === "line") {
        sw = document.createElement("span");
        sw.className = "sw-line";
        sw.innerHTML = '<svg width="30" height="10" aria-hidden="true"><line x1="1" y1="5" x2="29" y2="5" stroke="' +
          esc(r.color || "#888") + '" stroke-width="' + (r.width || 1.6) + '"' +
          (r.dash ? ' stroke-dasharray="' + r.dash.join(" ") + '"' : "") + "/></svg>";
      } else if (row.style === "class" && r.shape === "stroke") {
        sw = document.createElement("span");
        sw.className = "sw-line";
        sw.innerHTML = '<svg width="30" height="10" aria-hidden="true"><line x1="1" y1="5" x2="29" y2="5" stroke="' +
          esc(r.color || "#888") + '" stroke-width="' + (r.width || 1.4) + '"' +
          (r.dash ? ' stroke-dasharray="' + r.dash.join(" ") + '"' : "") + "/></svg>";
      } else if (row.style === "class" && (r.shape === "line" || r.shape === "dash")) {
        sw = document.createElement("span");
        sw.className = "sw-line";
        sw.innerHTML = '<svg width="30" height="10" aria-hidden="true"><line x1="1" y1="5" x2="29" y2="5" stroke="' +
          esc(r.color || "#888") + '" stroke-width="' + (r.shape === "dash" ? '1.6" stroke-dasharray="6 4' : "2.5") + '"/></svg>';
      } else if (row.style === "class") {
        sw = document.createElement("span");
        sw.className = "sw " + ({ square: "box", star: "star", diamond: "diamond", triangle: "triangle" }[r.shape] || "dot");
        sw.style.background = r.color || "#888";
      } else {
        sw = document.createElement("span");
        sw.className = "sw " + (row.style === "unit" ? "box" : r.shape === "star" ? "star" : "triangle");
        sw.style.background = r.color || "#888";
      }
      var label = document.createElement("span");
      label.textContent = (row.style === "class" ? T(r.label) : r.label) + "  (" + r.count + ")";
      line.append(sw, label);
      box.appendChild(line);
    });
    var err = entry.layer.get("gsmError");
    if (!rows.length) {
      box.appendChild(note(entry.layer.get("gsmFailed") ? (err || T("점을 받지 못했다")) : T("받는 중…")));
    }
    if (entry.layer.get("gsmWide")) {
      box.appendChild(note(T("남극 전체처럼 넓은 범위의 자료 {n}건은 그리지 않았다", { n: entry.layer.get("gsmWide") })));
    }
    if (row.source) {
      var a = document.createElement("a");
      a.className = "proplink";
      a.href = row.source;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      // 지구 자료 점(wetherilli 185)처럼 서버가 원본 자료의 글(조건 포함)을 적어 주면 그것을
      a.textContent = row.sourceLabel ? T(row.sourceLabel)
        : row.upstream === "geo3al"
        ? T("원본 자료 — USGS geo3al (OFR 97-470F). 연구실 내부용, 재배포 금지")
        : row.upstream === "kopri" ? T("원본 자료 — 극지연구소 KPDC")
        // 그린란드 포털의 면·갈래 레이어(wetherilli 089) — 이용 조건이 적혀 있지 않다(019)
        : row.upstream === "grportal" && row.license ? T("포털의 원본 항목 — CC BY 4.0, Hutchison (2020)")
        : row.upstream === "grportal" ? T("포털의 원본 항목 — 이용 조건 표시 없음")
        : T("원본 자료 — Norsk Polarinstitutt, CC BY 4.0");
      box.appendChild(a);
    }
    return box;
  }

  // ── 암맥 — 연구실 phyloserver 의 기록 (devlog 026) ──────────────
  //
  // 포털 점과 같은 길(`/points/`)로 온다. 끝점이 둘인 기록은 선, 하나뿐인 것은 점.
  // **줌이 표현을 정한다** — 암맥은 대개 수백 m 라 줌 11 아래에서는 1 px 도 안
  // 된다. 그래서 그보다 멀면 선을 숨기고 도폭마다 주향을 센 로즈를 그린다.
  // 로즈는 서버가 따로 주지 않고 **같은 자료에서 여기서 센다** — 선과 로즈가
  // 다른 자료를 보면 안 된다 (phyloserver 의 one-map 과 같은 까닭이다).
  // 색은 암석 갈래(`cls`)다. 갈래는 서버가 암석 이름에서 가른 것이다.

  var DIKE_CLASSES = [
    { code: "acid", color: "#c2185b", label: "산성암맥" },
    { code: "intermediate", color: "#ef6c00", label: "중성암맥" },
    { code: "basic", color: "#1b5e20", label: "염기성암맥" },
    { code: "vein", color: "#1565c0", label: "석영맥·광맥" },
    { code: "other", color: "#616161", label: "그 밖·미상" },
  ];
  //: 이 줌 아래에서는 선 대신 로즈를 그린다
  var DIKE_ROSE_BELOW = 11;
  //: 로즈의 칸 — 10° 씩 18 칸. 주향은 방향이 없어 맞은편에도 같은 꽃잎을 그린다
  var DIKE_ROSE_BINS = 18;
  //: 가장 큰 로즈의 반지름(지도 단위 — 3857 이라 북위 37° 에서 땅보다 1.25 배 길다).
  //  도폭 칸이 경도 15′·위도 10′ 이라 3857 에서 가로 27.8 km·세로 23 km 남짓이다.
  //  이만하면 이웃 도폭의 로즈와 겹치지 않는다. 화면에서는 4–60 px 사이로 둔다
  var DIKE_ROSE_METERS = 11000;

  function dikeColor(cls) {
    for (var i = 0; i < DIKE_CLASSES.length; i++) {
      if (DIKE_CLASSES[i].code === cls) return DIKE_CLASSES[i].color;
    }
    return DIKE_CLASSES[DIKE_CLASSES.length - 1].color;
  }

  function dikeStyle() {
    var cache = {};
    return function (feature, resolution) {
      var zoom = map.getView().getZoomForResolution(resolution) || 0;
      var far = zoom < DIKE_ROSE_BELOW;
      var rose = feature.get("rose");
      if (rose) return far ? roseStyle(feature, resolution) : null;
      if (far) return null;
      var cls = feature.get("cls") || "other";
      var point = feature.getGeometry().getType() === "Point";
      var wide = zoom >= 14;
      var key = cls + (point ? "p" : "l") + (wide ? "w" : "");
      if (cache[key]) return cache[key];
      var color = dikeColor(cls);
      cache[key] = point
        ? new ol.style.Style({ image: new ol.style.Circle({ radius: wide ? 4 : 3,
            fill: new ol.style.Fill({ color: color }),
            stroke: new ol.style.Stroke({ color: "rgba(255,255,255,0.9)", width: 1 }) }) })
        : [
          new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(255,255,255,0.8)", width: wide ? 5 : 4 }) }),
          new ol.style.Style({ stroke: new ol.style.Stroke({ color: color, width: wide ? 3 : 2, lineCap: "round" }) }),
        ];
      return cache[key];
    };
  }

  /** 도폭마다 로즈 feature 하나. 자리는 그 도폭 암맥들 가운데(선의 가운데 점의 평균)이고,
   *  팝업에 도폭·수·평균 주향이 뜬다. 평균은 방향이 없는 자료라 각을 두 배로 해서 잰다. */
  function dikeRoses(features) {
    var bySheet = {};
    features.forEach(function (f) {
      var strike = f.get("strike");
      var sheet = f.get("sheet");
      if (typeof strike !== "number" || !sheet) return;
      var ext = f.getGeometry().getExtent();
      var s = bySheet[sheet] || (bySheet[sheet] = { x: 0, y: 0, n: 0, sin: 0, cos: 0, bins: [] });
      s.x += (ext[0] + ext[2]) / 2;
      s.y += (ext[1] + ext[3]) / 2;
      s.n += 1;
      s.sin += Math.sin(strike * Math.PI / 90);
      s.cos += Math.cos(strike * Math.PI / 90);
      var bin = Math.floor(strike / (180 / DIKE_ROSE_BINS)) % DIKE_ROSE_BINS;
      s.bins[bin] = (s.bins[bin] || 0) + 1;
    });
    var most = 1;
    Object.keys(bySheet).forEach(function (k) { most = Math.max(most, bySheet[k].n); });
    return Object.keys(bySheet).map(function (sheet) {
      var s = bySheet[sheet];
      var mean = Math.atan2(s.sin, s.cos) * 90 / Math.PI;
      var f = new ol.Feature({ geometry: new ol.geom.Point([s.x / s.n, s.y / s.n]) });
      f.setProperties({ rose: s.bins, share: Math.sqrt(s.n / most), sheet: sheet, n: s.n,
                        mean: Math.round((mean + 180) % 180) + "°" });
      return f;
    });
  }

  /** 로즈 한 송이. 꽃잎의 길이는 칸의 수의 제곱근이다 — 넓이가 수에 비례하게.
   *  크기는 땅 위의 길이로 정한다 — 줌을 바꿔도 로즈가 제 도폭 칸 안에 든다.
   *  그 안에서 암맥이 적은 도폭은 작게(가장 많은 도폭에 견준 제곱근, 적어도 0.45). */
  function roseStyle(feature, resolution) {
    var full = DIKE_ROSE_METERS / resolution;
    var radius = Math.round(Math.max(4, Math.min(60, full * Math.max(0.45, feature.get("share")))));
    var styles = feature.get("roseStyles") || {};
    if (styles[radius]) return styles[radius];
    var style;
    var bins = feature.get("rose");
    var ratio = window.devicePixelRatio || 1;
    var size = radius * 2 + 4;
    var canvas = document.createElement("canvas");
    canvas.width = canvas.height = size * ratio;
    var ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    var c = size / 2;
    var top = 1;
    for (var i = 0; i < DIKE_ROSE_BINS; i++) top = Math.max(top, bins[i] || 0);
    ctx.beginPath();
    ctx.arc(c, c, radius, 0, 2 * Math.PI);
    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.fill();
    ctx.strokeStyle = "rgba(60,40,20,0.5)";
    ctx.lineWidth = 1;
    ctx.stroke();
    var step = Math.PI / DIKE_ROSE_BINS;
    ctx.fillStyle = "rgba(120,40,40,0.85)";
    for (var b = 0; b < DIKE_ROSE_BINS; b++) {
      if (!bins[b]) continue;
      var r = radius * Math.sqrt(bins[b] / top);
      [0, Math.PI].forEach(function (flip) {
        // 북이 0°, 시계 방향. 캔버스의 0 은 동쪽이라 90° 를 뺀다
        var a0 = b * step + flip - Math.PI / 2;
        ctx.beginPath();
        ctx.moveTo(c, c);
        ctx.arc(c, c, r, a0, a0 + step);
        ctx.closePath();
        ctx.fill();
      });
    }
    style = new ol.style.Style({ image: new ol.style.Icon({ img: canvas, width: size, height: size }) });
    styles[radius] = style;
    feature.set("roseStyles", styles, true);
    return style;
  }

  function dikeLegend(entry, row, box) {
    var counts = {};
    var roses = 0;
    entry.layer.getSource().getFeatures().forEach(function (f) {
      if (f.get("rose")) { roses += 1; return; }
      var cls = f.get("cls") || "other";
      counts[cls] = (counts[cls] || 0) + 1;
    });
    DIKE_CLASSES.forEach(function (c) {
      var line = document.createElement("div");
      var sw = document.createElement("span");
      sw.className = "sw-line";
      sw.innerHTML = '<svg width="30" height="10" aria-hidden="true"><line x1="1" y1="5" x2="29" y2="5" stroke="' +
        c.color + '" stroke-width="2.5"/></svg>';
      var label = document.createElement("span");
      label.textContent = T(c.label) + (counts[c.code] ? "  (" + counts[c.code].toLocaleString() + ")" : "");
      line.append(sw, label);
      box.appendChild(line);
    });
    var count = entry.layer.get("gsmCount");
    box.appendChild(note(entry.layer.get("gsmFailed") ? (entry.layer.get("gsmError") || T("점을 받지 못했다"))
      : count === undefined ? T("받는 중…")
      : T("암맥 {n}건 · 줌 {z} 아래에서는 도폭 {m}곳의 로즈", { n: count.toLocaleString(), z: DIKE_ROSE_BELOW, m: roses })));
    box.appendChild(note(T("갈래는 적힌 암석 이름에서 GSM 이 가른 것이다")));
    if (row.source) {
      var a = document.createElement("a");
      a.className = "proplink";
      a.href = row.source;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = T("원본 기록 — phyloserver");
      box.appendChild(a);
    }
    return box;
  }

  // ── 클릭해 속성 읽기 ────────────────────────────────────────────

  // ── 5만 지질도의 자세 기호 (jikhanjung 004) ──────────────────────
  //
  // 5만 지질도 타일에는 층리·엽리·편리·절리 기호가 그림으로 박혀 있어 누를 수 없다.
  // 받아 둔 자리(`kigam50k/attitudes/`)를 보이지 않는 점으로 깔아 두고, **커서를 올리면
  // 손가락으로 바꾸고 그 기호를 그려 보인다.** 누르면 경사·경사 방향·주향이 팝업에 뜬다.
  // 층리 뺀 판에서는 이것이 층리를 찾는 길이다. 5만 지질도(두 판 어느 것이든)를 켜고
  // 줌 12 이상일 때만 받는다 — 1:5만 도폭의 기호를 전국에 깔 까닭이 없다.

  var ATTITUDE_LAYERS = ["L_50K_Geology_Map", "L_50K_Geology_Map_NoAttitude"];
  // 줌 11 에서는 한 화면에 점이 수천이라 지도가 느려진다(사람) — 12 부터 받고 그린다 (jikhanjung 006)
  var ATTITUDE_MIN_ZOOM = 12;
  var ATTITUDE_COLORS = { bedding: "#b3261e", foliation: "#1f5fa8", schistosity: "#6b3fa0", joint: "#2e7d32" };
  var ATTITUDE_NAMES = { bedding: "층리", foliation: "엽리", schistosity: "편리", joint: "절리" };
  var attitudeSource = null, attitudeLayer = null, attitudeHover = null;
  var attitudeLoaded = null, attitudeSeq = 0;
  //: 늘 그릴 종류. 끈 것은 커서를 올릴 때만 그린다. 이 브라우저에만 남는다 (jikhanjung 005)
  var ATTITUDE_KEY = "gsm.attitudes";
  var attitudeShown = (function () {
    try { return JSON.parse(localStorage.getItem(ATTITUDE_KEY) || "{}") || {}; } catch (e) { return {}; }
  })();
  //: 경사각 숫자를 늘 적는 줌. 그보다 멀면 선과 눈금만 — 숫자가 겹쳐 읽히지 않는다
  var ATTITUDE_LABEL_ZOOM = 13;

  function setAttitudeShown(kind, on) {
    attitudeShown[kind] = !!on;
    try { localStorage.setItem(ATTITUDE_KEY, JSON.stringify(attitudeShown)); } catch (e) { /* 사생활 모드 */ }
    if (attitudeLayer) attitudeLayer.changed();
  }

  /** 5만 지질도 카드 밑의 체크 넷 — 켠 종류의 기호를 늘 그린다. */
  function attitudeToggles() {
    var box = document.createElement("div");
    box.className = "attitude-toggles";
    box.title = T("켜면 늘 그리고, 끄면 커서를 올릴 때만 그린다 — 줌 {n} 부터", { n: ATTITUDE_MIN_ZOOM });
    Object.keys(ATTITUDE_NAMES).forEach(function (kind) {
      var label = document.createElement("label");
      var input = document.createElement("input");
      input.type = "checkbox";
      input.checked = !!attitudeShown[kind];
      input.addEventListener("change", function () {
        setAttitudeShown(kind, input.checked);
        // 두 판의 카드가 함께 켜져 있으면 다른 카드의 체크도 맞춘다
        document.querySelectorAll('.attitude-toggles input[data-kind="' + kind + '"]').forEach(function (other) {
          other.checked = input.checked;
        });
      });
      input.dataset.kind = kind;
      label.className = kind;          // 글자색이 지도 위 기호의 색이다 (map.css)
      label.append(input, document.createTextNode(T(ATTITUDE_NAMES[kind])));
      box.appendChild(label);
    });
    return box;
  }
  var ATTITUDE_HIT = new ol.style.Style({
    // 보이지 않지만 맞힐 수 있게 — 알파가 0 이면 OpenLayers 가 맞힌 것으로 치지 않는 판이 있다
    image: new ol.style.Circle({ radius: 7, fill: new ol.style.Fill({ color: "rgba(0,0,0,0.01)" }) }),
  });

  function initAttitudes() {
    attitudeSource = new ol.source.Vector();
    attitudeLayer = new ol.layer.Vector({ source: attitudeSource, style: attitudeStyle, visible: false,
                                          updateWhileInteracting: false });
    attitudeLayer.set("gsmAttitude", true);
    attitudeLayer.setZIndex(520);
    map.addLayer(attitudeLayer);
    map.on("moveend", refreshAttitudes);
    map.on("pointermove", function (e) {
      if (e.dragging || mode !== "info") return;
      var hit = null;
      if (attitudeLayer.getVisible()) {
        hit = map.forEachFeatureAtPixel(e.pixel, function (f) { return f; },
          { hitTolerance: 3, layerFilter: function (l) { return l === attitudeLayer; } });
      }
      if (hit !== attitudeHover) {
        var old = attitudeHover;
        attitudeHover = hit;
        if (old) old.changed();
        if (hit) hit.changed();
      }
      map.getTargetElement().style.cursor = hit ? "pointer" : "";
    });
  }

  function attitudeWanted() {
    if (!attitudeLayer || !isMercator()) return false;
    if ((map.getView().getZoom() || 0) < ATTITUDE_MIN_ZOOM) return false;
    return active.some(function (e) { return ATTITUDE_LAYERS.indexOf(e.name) >= 0; });
  }

  function attitudeLayersOn() {
    return isMercator() && active.some(function (e) { return ATTITUDE_LAYERS.indexOf(e.name) >= 0; });
  }

  // ── 장미도 — 도폭 하나(또는 잡은 범위)의 층리·엽리·편리·절리 (wetherilli 197, jikhanjung P01 §5 의 5 단계) ──
  //
  // 서버(`kigam50k/rose/`)가 각도를 10° 칸으로 세어 주고 여기서 SVG 로 그린다. 주향은 축이라 열여덟 칸을 마주 보게 겹쳐
  // 그리고, 경사 방향은 서른여섯 칸 그대로다. 꽃잎의 길이는 수의 제곱근 — 넓이가 수에 비례한다(등면적 장미도)
  var ROSE_KINDS = [["bedding", "층리"], ["foliation", "엽리"], ["schistosity", "편리"], ["joint", "절리"]];

  function roseBlock(query, isRange) {
    var box = document.createElement("div");
    box.className = "rose-block";
    var open = document.createElement("button");
    open.type = "button";
    open.className = "rose-open";
    open.textContent = isRange ? T("이 범위의 층리·엽리 장미도") : T("이 도폭의 층리·엽리 장미도");
    box.appendChild(open);
    open.addEventListener("click", function () {
      open.disabled = true;
      fetch(BASE + "kigam50k/rose/?" + query)
        .then(function (r) { return r.json(); })
        .then(function (data) { box.innerHTML = ""; drawRoseBlock(box, data, isRange); popupOverlay.panIntoView({ animation: { duration: 200 }, margin: popupMargin() }); })
        .catch(function () { open.disabled = false; open.textContent = T("장미도를 받지 못했다"); });
    });
    return box;
  }

  function drawRoseBlock(box, data, isRange) {
    var kinds = ROSE_KINDS.filter(function (k) { return (data.n || {})[k[0]]; });
    var head = document.createElement("h3");
    head.textContent = data.sheet ? T("{name} 도폭 ({no}) — 자세 기호", { name: data.sheet.name, no: data.sheet.no })
      : isRange ? T("잡은 범위 — 자세 기호") : T("자세 기호");
    box.appendChild(head);
    if (data.error || !kinds.length) {
      var none = document.createElement("p");
      none.className = "none";
      none.textContent = data.error || T("이 자리에는 받아 둔 층리·엽리·절리가 없다");
      box.appendChild(none);
      return;
    }
    var state = { kind: kinds.slice().sort(function (a, b) { return data.n[b[0]] - data.n[a[0]]; })[0][0], axis: "strike" };
    var tabs = document.createElement("div");
    tabs.className = "rose-tabs";
    var axes = document.createElement("div");
    axes.className = "rose-tabs";
    var pic = document.createElement("div");
    pic.className = "rose-pic";
    var foot = document.createElement("p");
    foot.className = "rose-foot";
    function tab(host, label, on, pick) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.classList.toggle("on", on);
      b.addEventListener("click", function () { pick(); render(); });
      host.appendChild(b);
    }
    function render() {
      tabs.innerHTML = "";
      axes.innerHTML = "";
      kinds.forEach(function (k) {
        tab(tabs, T(k[1]) + " " + data.n[k[0]], state.kind === k[0], function () { state.kind = k[0]; });
      });
      tab(axes, T("주향"), state.axis === "strike", function () { state.axis = "strike"; });
      tab(axes, T("경사 방향"), state.axis === "dipdir", function () { state.axis = "dipdir"; });
      var bins = data[state.axis][state.kind];
      pic.innerHTML = roseSvg(state.axis === "strike" ? bins.concat(bins) : bins) + dipSvg(data.dip[state.kind]);
      var bits = [T("받은 날 {date}", { date: data.fetched || "?" })];
      if (data.nodip[state.kind]) bits.push(T("경사 미상 {n}", { n: data.nodip[state.kind] }));
      if (state.axis === "strike") bits.push(T("주향은 경사 방향 − 90° (오른손 법칙)"));
      foot.textContent = bits.join(" · ");
    }
    box.append(tabs, axes, pic, foot);
    render();
  }

  /** 꽃잎 서른여섯(10° 칸) — 북이 위, 시계 방향. 꽃잎 길이는 수의 제곱근 */
  function roseSvg(bins) {
    var size = 140, c = size / 2, R = c - 13;
    var max = Math.max.apply(null, bins) || 1;
    function at(deg, r) {
      var a = deg * Math.PI / 180;
      return (c + r * Math.sin(a)).toFixed(1) + "," + (c - r * Math.cos(a)).toFixed(1);
    }
    var out = ['<svg class="rose-svg" viewBox="0 0 ' + size + " " + size + '" width="' + size + '" height="' + size + '" role="img">'];
    out.push('<circle cx="' + c + '" cy="' + c + '" r="' + R + '" class="ring"/>');
    out.push('<circle cx="' + c + '" cy="' + c + '" r="' + (R * Math.SQRT1_2).toFixed(1) + '" class="ring half"/>');
    bins.forEach(function (n, i) {
      if (!n) return;
      var r = R * Math.sqrt(n / max);
      out.push('<path class="petal" d="M' + c + "," + c + " L" + at(i * 10, r) + " A" + r.toFixed(1) + "," + r.toFixed(1) +
               " 0 0 1 " + at(i * 10 + 10, r) + ' Z"><title>' + (i * 10) + "–" + (i * 10 + 10) + "° · " + n + "</title></path>");
    });
    [["N", 0], ["E", 90], ["S", 180], ["W", 270]].forEach(function (d) {
      out.push('<text x="' + at(d[1], R + 8).split(",")[0] + '" y="' + at(d[1], R + 8).split(",")[1] +
               '" class="tick">' + d[0] + "</text>");
    });
    out.push("</svg>");
    return out.join("");
  }

  /** 경사 분포 — 10° 칸 아홉 */
  function dipSvg(bins) {
    var w = 108, h = 140, base = h - 20, top = 14, bw = (w - 10) / 9;
    var max = Math.max.apply(null, bins) || 1;
    var out = ['<svg class="dip-svg" viewBox="0 0 ' + w + " " + h + '" width="' + w + '" height="' + h + '" role="img">'];
    out.push('<text x="' + (w / 2) + '" y="10" class="tick">' + esc(T("경사")) + "</text>");
    bins.forEach(function (n, i) {
      var bh = (base - top) * n / max;
      out.push('<rect class="bar" x="' + (5 + i * bw + 1).toFixed(1) + '" y="' + (base - bh).toFixed(1) + '" width="' + (bw - 2).toFixed(1) +
               '" height="' + bh.toFixed(1) + '"><title>' + (i * 10) + "–" + (i * 10 + 10) + "° · " + n + "</title></rect>");
    });
    out.push('<line x1="5" x2="' + (w - 5) + '" y1="' + base + '" y2="' + base + '" class="ring"/>');
    [0, 30, 60, 90].forEach(function (d) {
      out.push('<text x="' + (5 + d / 10 * bw).toFixed(1) + '" y="' + (base + 14) + '" class="tick">' + d + "°</text>");
    });
    out.push("</svg>");
    return out.join("");
  }

  function refreshAttitudes() {
    if (!attitudeLayer) return;
    var want = attitudeWanted();
    attitudeLayer.setVisible(want);
    if (!want) {
      if (attitudeHover) { attitudeHover = null; map.getTargetElement().style.cursor = ""; }
      return;
    }
    var ext = ol.proj.transformExtent(map.getView().calculateExtent(map.getSize()), viewProj(), "EPSG:4326");
    if (attitudeLoaded && ol.extent.containsExtent(attitudeLoaded, ext)) return;
    // 조금 넓게 받아 둔다 — 조금 끌 때마다 다시 묻지 않게. 소수 둘째 자리로 잘라 캐시가 맞게
    var w = ext[2] - ext[0], h = ext[3] - ext[1];
    var box = [ext[0] - w * 0.5, ext[1] - h * 0.5, ext[2] + w * 0.5, ext[3] + h * 0.5].map(function (v, i) {
      return i < 2 ? Math.floor(v * 100) / 100 : Math.ceil(v * 100) / 100;
    });
    var seq = ++attitudeSeq;
    fetch(BASE + "kigam50k/attitudes/?bbox=" + box.join(","))
      .then(function (r) { return r.ok ? r.json() : { points: [] }; })
      .catch(function () { return { points: [] }; })
      .then(function (data) {
        if (seq !== attitudeSeq) return;
        attitudeSource.clear();
        attitudeHover = null;
        attitudeSource.addFeatures((data.points || []).map(function (p) {
          var f = new ol.Feature({ geometry: new ol.geom.Point(fromLL([p.lon, p.lat])) });
          f.setProperties({ att: p, fetched: data.fetched || "" });
          return f;
        }));
        attitudeLoaded = data.truncated ? null : box;
      });
  }

  /** 평소에는 보이지 않는 점, 커서가 올라간 것과 늘 그리기로 켠 종류만 기호로 그린다. */
  function attitudeStyle(feature, resolution) {
    var p = feature.get("att");
    var hovered = feature === attitudeHover;
    if (!hovered && !attitudeShown[p.kind]) return ATTITUDE_HIT;
    // 3857 에서 줌 13 의 해상도 ≈ 19.1 m/px — 그보다 가까우면 숫자까지
    var labels = hovered || resolution <= 156543.03392804097 / Math.pow(2, ATTITUDE_LABEL_ZOOM) + 1e-9;
    var c = feature.getGeometry().getCoordinates();
    var color = ATTITUDE_COLORS[p.kind] || "#333";
    // 멀리서는 작게 — 줌 12(처음 그리는 줌)에서 0.7 배, 한 단계마다 0.15 씩 커져 14 에서 제 크기.
    // 기호가 겹쳐 뭉치는 것을 덜려는 것이다. 커서가 올라간 것은 늘 제 크기 (jikhanjung 006)
    var zoom = Math.log(156543.03392804097 / resolution) / Math.LN2;
    var k = hovered ? 1 : Math.max(0.55, Math.min(1, 0.7 + 0.15 * (zoom - 12)));
    // 늘 그리는 것은 가늘게, 커서가 올라간 것은 굵게 — 어느 것을 가리키는지 보이게
    var halo = new ol.style.Stroke({ color: "rgba(255,255,255,.9)", width: hovered ? 5 : 1.5 + 2 * k });
    var ink = new ol.style.Stroke({ color: color, width: hovered ? 2.5 : 0.8 + 0.8 * k });
    var styles = [new ol.style.Style({
      image: new ol.style.Circle({ radius: hovered ? 3 : 1 + k, fill: new ol.style.Fill({ color: color }),
                                   stroke: new ol.style.Stroke({ color: "#fff", width: hovered ? 1.5 : 1 }) }),
      zIndex: hovered ? 10 : 0,
    })];
    if (p.dipdir === null || p.dipdir === undefined) return styles;
    // 3857 은 북쪽이 위다 — 방위각(북에서 시계 방향)을 그대로 쓴다
    function at(az, px) {
      var a = az * Math.PI / 180;
      return [c[0] + Math.sin(a) * px * resolution, c[1] + Math.cos(a) * px * resolution];
    }
    var strike = (p.dipdir + 270) % 360;
    var lines = [new ol.geom.LineString([at(strike, 13 * k), at(strike + 180, 13 * k)])];
    var vertical = /수직/.test(p.type) || p.dip === 90;
    var flat = /수평/.test(p.type) || p.dip === 0;
    if (!flat) {
      lines.push(new ol.geom.LineString([c, at(p.dipdir, 7 * k)]));
      if (vertical) lines.push(new ol.geom.LineString([c, at(p.dipdir + 180, 7 * k)]));
    }
    lines.forEach(function (g) {
      styles.push(new ol.style.Style({ geometry: g, stroke: halo, zIndex: hovered ? 10 : 0 }));
      styles.push(new ol.style.Style({ geometry: g, stroke: ink, zIndex: hovered ? 11 : 1 }));
    });
    if (labels && p.dip !== null && p.dip !== undefined && !vertical && !flat) {
      styles.push(new ol.style.Style({
        geometry: new ol.geom.Point(at(p.dipdir, 7 * k + 10)),
        zIndex: hovered ? 12 : 2,
        text: new ol.style.Text({ text: String(p.dip), font: (hovered ? "700 12px" : "600 10.5px") + " sans-serif",
                                  fill: new ol.style.Fill({ color: color }),
                                  stroke: new ol.style.Stroke({ color: "#fff", width: 3 }) }),
      }));
    }
    return styles;
  }

  function quadrantOf(az) {
    return az < 90 ? "NE" : az < 180 ? "SE" : az < 270 ? "SW" : "NW";
  }

  function attitudePart(feature) {
    var p = feature.get("att");
    var deg = function (v) { return v === null || v === undefined ? T("미상") : v + "°"; };
    var props = {};
    props["경사"] = deg(p.dip);
    props["경사 방향"] = deg(p.dipdir);
    props["주향"] = p.dipdir === null || p.dipdir === undefined ? T("미상") : ((p.dipdir + 270) % 360) + "°";
    if (p.quad) props["원문 사분면"] = p.quad;
    props["도폭"] = p.sheet + (p.sheet_no ? " (" + p.sheet_no + ")" : "");
    var dipQuad = (p.quad || "").split("/")[1];
    if (dipQuad && p.dipdir !== null && p.dipdir !== undefined && quadrantOf(p.dipdir) !== dipQuad) {
      props["알림"] = T("경사 방향과 원문 사분면이 맞지 않는다 — 기호는 경사 방향대로 그렸다");
    }
    props["출처"] = T("KIGAM 5만 지질도 · {date} 받음", { date: feature.get("fetched") });
    return { title: T(p.type || ATTITUDE_NAMES[p.kind] || p.kind), props: props };
  }

  function onClick(evt) {
    if (mode === "point") {
      addTempPoint(evt.coordinate);
      return;
    }
    if (mode !== "info") return;      // 재는 중에는 팝업을 띄우지 않는다

    var parts = [];
    var pointSeen = {};     // 점 레이어마다 몇 개를 올렸나 (pointPart)
    var personalSeen = {};  // 개인 레이어마다 몇 개를 올렸나 (personalPart)

    // 내 점이 먼저다 — 눌러서 맞힌 것이 분명하기 때문이다
    map.forEachFeatureAtPixel(evt.pixel, function (feature, layer) {
      // 5만 지질도의 자세 기호(층리·엽리·편리·절리) — 받아 둔 값을 그 자리에서 읽는다
      if (layer && layer.get("gsmAttitude")) {
        parts.push(attitudePart(feature));
        return;
      }
      // 벡터 레이어(단층)의 선. 속성은 서버가 팝업에 맞춰 곁들여 보냈다
      var vectorName = layer && layer.get("gsmVector");
      if (vectorName) {
        var row = byName[vectorName];
        parts.push({ title: row ? row.title : vectorName,
                     props: feature.get("_popup") || plain(feature.getProperties()) });
        return;
      }
      // 점 레이어(그린란드 정부 포털)의 점. 받아 둔 속성을 그 자리에서 읽는다
      if (layer && layer.get("gsmPoints")) {
        // 면은 누른 자리를 품은 것만 — 5 px 너그러움은 점을 누르기 쉽게 하려는 것이라,
        // 작게 본 면에서는 옆 단위 두셋이 함께 걸린다 (중국 geo3al, 025)
        var geom = feature.getGeometry();
        var areal = geom && /Polygon$/.test(geom.getType());
        if (areal && !geom.intersectsCoordinate(evt.coordinate)) return;
        var pp = pointPart(feature, layer, pointSeen);
        if (pp) parts.push(pp);
        return;
      }
      if (feature.get("no") !== undefined && feature.get("lat") !== undefined) {
        parts.push({
          title: T("찍은 점 {n}", { n: feature.get("no") }),
          props: {
            "위도": feature.get("lat").toFixed(6),
            "경도": feature.get("lon").toFixed(6),
            "도분초": coordText(feature.get("lon"), feature.get("lat")),
          },
        });
        return;
      }
      if (feature.get("_개인")) {
        personalParts(feature, personalSeen).forEach(function (own) { parts.push(own); });
        return;
      }
      parts.push({ title: feature.get("_점묶음") || T("내 자료"), props: plain(feature.getProperties()) });
    }, {
      hitTolerance: 5,
      // 찾아간 자리의 표식은 자료가 아니다. 거리·넓이 선도 그렇다
      layerFilter: function (layer) {
        return layer !== foundLayer && layer !== measureLayer && layer !== rangeLayer;
      },
    });

    Object.keys(personalSeen).forEach(function (id) {
      var over = personalSeen[id].n - PERSONAL_POPUP_MAX;
      if (over > 0) {
        parts.push({ title: personalSeen[id].name, props: { "…": T("같은 자리에 {n}건 더 있다 — 관리 화면에서 내려받아 본다", { n: over }) } });
      }
    });

    // 벡터 레이어는 위에서 이미 읽었다 — 서버에 속성을 다시 묻지 않는다
    var queryable = active.filter(function (e) {
      var row = byName[e.name];
      return row && row.queryable && row.kind !== "vector" && row.kind !== "points";
    });

    if (!queryable.length) {
      // 벡터 레이어만 켜 두고 선을 비껴 누른 것이면 "켠 것이 없다" 가 아니다
      showPopup(evt.coordinate, parts, parts.length ? ""
        : active.length ? T("이 자리에는 아무것도 없다") : T("켠 레이어가 없다"));
      return;
    }

    showPopup(evt.coordinate, parts, T("읽는 중…"));

    var view = map.getView();
    var pending = queryable.length;
    var results = new Array(queryable.length);

    queryable.forEach(function (entry, index) {
      // 속성 주소는 레이어의 상류가 안다 (`LAYER_KINDS`)
      var info = layerKind(entry.name).info;
      var url = info && info(entry.layer.getSource(), evt.coordinate, view);
      if (!url) { pending -= 1; return; }

      // 정적 판의 상류(`GSM_STATIC_KINDS`)는 주소가 아니라 받은 것을 준다 — 그쪽 꼴로 이미 손질해서
      (url.then ? url : fetch(url).then(function (r) { return r.json(); }))
        .catch(function () { return { features: [] }; })
        .then(function (data) {
          results[index] = (data.features || []).map(function (f) {
            return { title: entry.title, props: f.props };
          });
          pending -= 1;
          if (pending === 0) {
            var all = parts.concat.apply(parts, results.filter(Boolean));
            showPopup(evt.coordinate, all, all.length ? "" : T("이 자리에는 아무것도 없다"));
          }
        });
    });

    if (pending === 0) showPopup(evt.coordinate, parts, parts.length ? "" : T("이 자리에는 아무것도 없다"));
  }

  /** IBCSO 수심·표고 (070). 실패하면 빈 것 — 팝업의 다른 줄을 막지 않는다. */
  function depthFor(lon, lat) {
    if (STATIC) return Promise.resolve({});        // 원본 격자가 수백 MB 라 정적 판에 싣지 않았다 (wetherilli 165)
    return fetch(BASE + "ibcso/depth/?" + new URLSearchParams({ lat: lat.toFixed(6), lon: lon.toFixed(6) }))
      .then(function (r) { return r.ok ? r.json() : {}; })
      .catch(function () { return {}; });
  }

  /** 얼음 위와 해저·빙저가 같으면(드러난 땅·얼음 없는 바다) 한 값만, 다르면 얼음 두께까지 적는다. */
  function depthText(d) {
    if (d.bed === undefined && d.ice === undefined) return "";
    var m = function (v) { return v.toLocaleString() + " m"; };
    var bits = [];
    if (d.ice !== undefined && d.bed !== undefined && d.ice - d.bed > 1) {
      bits.push(T("얼음 위 {m}", { m: m(d.ice) }), T("해저·빙저 {m}", { m: m(d.bed) }),
                T("얼음 두께 {m}", { m: m(d.ice - d.bed) }));
    } else {
      var v = d.bed !== undefined ? d.bed : d.ice;
      bits.push(v < 0 ? T("수심 {m}", { m: m(-v) }) : T("표고 {m}", { m: m(v) }));
    }
    if (d.tid) bits.push(d.tid);
    return "IBCSO · " + bits.join(" · ");
  }

  /** 팝업을 화면 안으로 끌어올 때의 여백 — 사방에 걸린다. 넓은 화면은 좌표 막대를 비키는 72 px, 휴대폰은 320 px 팝업이 들게
   *  12 px (wetherilli 193). 처음 띄울 때와 속성이 늦게 와 자랐을 때 두 곳이 같은 값을 쓴다 */
  function popupMargin() { return window.innerWidth < 500 ? 12 : 72; }

  function showPopup(coordinate, parts, emptyText, opts) {
    var body = document.getElementById("popup-body");
    body.innerHTML = "";

    // **첫 줄은 언제나 누른 자리의 위경도다.** 속성이 무엇이 나오든,
    // 무엇도 안 나오든 "여기가 어디인가" 는 늘 답이 되어야 한다.
    var ll = toLL(coordinate);
    var head = document.createElement("button");
    head.type = "button";
    head.className = "popup-coord";
    head.title = T("눌러서 복사한다");
    var value = formatPair(ll[0], ll[1]);
    var lat = useDms ? dd2dms(ll[1], true) : ll[1].toFixed(6);
    var lon = useDms ? dd2dms(ll[0], false) : ll[0].toFixed(6);
    head.innerHTML =
      '<span class="k">' + esc(T("위도")) + '</span><span class="v">' + esc(lat) + "</span>" +
      '<span class="k">' + esc(T("경도")) + '</span><span class="v">' + esc(lon) + "</span>" +
      '<span class="copy">' + esc(T("복사")) + "</span>";
    head.addEventListener("click", function () {
      copyText(value).then(function () {
        head.classList.add("copied");
        head.querySelector(".copy").textContent = T("복사했다");
        setTimeout(function () {
          head.classList.remove("copied");
          head.querySelector(".copy").textContent = T("복사");
        }, 900);
      });
    });
    body.appendChild(head);

    // 고른 좌표계가 평면이면 그 좌표를 한 줄. 눌러서 복사한다
    if (crsCode() !== "4326") {
      var tm = document.createElement("button");
      tm.type = "button";
      tm.className = "popup-tm";
      tm.title = T("눌러서 복사한다");
      body.appendChild(tm);
      var crsName = document.getElementById("crs-pick").selectedOptions[0].text;
      projectedFor(ll[0], ll[1]).then(function (d) {
        if (!d) { tm.remove(); return; }
        var value = d.east.toFixed(2) + " " + d.north.toFixed(2);
        tm.innerHTML = '<span class="k">' + esc(crsName) + "</span>" +
          '<span class="v">' + esc(T("동")) + " " + esc(d.east.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })) +
          " · " + esc(T("북")) + " " + esc(d.north.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })) + "</span>";
        tm.addEventListener("click", function () {
          copyText(value).then(function () {
            tm.classList.add("copied");
            setTimeout(function () { tm.classList.remove("copied"); }, 900);
          });
        });
      });
    }

    // 주소는 VWorld 열쇠가 있을 때만 묻는다. 바다처럼 주소가 없는 자리면 줄을 두지 않는다.
    // 극지는 묻지 않는다 — VWorld 는 우리나라 주소만 안다
    if (vworldKey && REGIONS[region].vworld) {
      var addr = document.createElement("p");
      addr.className = "popup-addr";
      body.appendChild(addr);
      addressFor(ll[0], ll[1]).then(function (d) {
        var lines = [d.road, d.parcel && d.parcel !== d.road ? d.parcel : ""].filter(Boolean);
        if (lines.length) addr.textContent = lines.join(" · ");
        else addr.remove();
      });
    }

    // 남극 바다·얼음 밑이면 IBCSO 의 수심·표고를 한 줄 (070). 잘라 둔 격자가 없거나 자료 밖이면 줄을 두지 않는다
    if (ll[1] <= -50 && viewProj().getCode() === "EPSG:3031") {
      var depth = document.createElement("p");
      depth.className = "popup-addr popup-depth";
      body.appendChild(depth);
      depthFor(ll[0], ll[1]).then(function (d) {
        var text = depthText(d);
        if (text) depth.textContent = text;
        else depth.remove();
      });
    }

    if (!parts.length) {
      var none = document.createElement("p");
      none.className = "none";
      none.textContent = emptyText || "";
      body.appendChild(none);
    } else {
      parts.forEach(function (part) {
        var h = document.createElement("h3");
        h.textContent = part.title;
        body.appendChild(h);
        var table = document.createElement("table");
        var extras = 0;
        Object.keys(part.props).forEach(function (key) {
          var tr = document.createElement("tr");
          var th = document.createElement("th");
          th.textContent = T(key);
          tr.append(th, valueCell(part.props[key]));
          if (EXTRA_PROPS.indexOf(key) >= 0) {
            tr.className = "extra";
            extras += 1;
          }
          table.appendChild(tr);
        });
        table.classList.toggle("show-extra", showExtraProps);
        body.appendChild(table);
        if (extras) body.appendChild(extraToggle(table, extras));
      });
    }
    // 5만 지질도를 켜 두었으면 그 자리 도폭의 층리·엽리 장미도를 부르는 단추 (wetherilli 197). 잡은 범위는 그 범위의 것
    var roseQuery = opts && "rose" in opts ? opts.rose
      : attitudeLayersOn() ? "lat=" + ll[1].toFixed(5) + "&lon=" + ll[0].toFixed(5) : "";
    if (roseQuery) body.appendChild(roseBlock(roseQuery, !!(opts && opts.rose)));
    document.getElementById("popup").classList.add("on");
    document.getElementById("map-wrap").classList.add("popup-open");
    popupOverlay.setPosition(coordinate);
    // 속성이 늦게 와서 팝업이 자라도 자리는 그대로라 OL 이 다시 끌어오지
    // 않는다. 채운 뒤에 한 번 더 화면 안으로 끌어온다.
    popupOverlay.panIntoView({ animation: { duration: 200 }, margin: popupMargin() });
  }

  /** 평소에는 접어 두는 속성. 사람이 읽을 것이 아니거나 다른 줄과 겹친다.
   *
   *  - `symnum` — 대표암상의 분류 번호로 보인다. 같은 쥐라기 화강암이면
   *    도폭이 달라도(`Jbgr` 무주 · `Jsgr` 뚝섬) 같은 값(101401)이다
   *  - `mapname` — 도폭 이름. `도폭` 줄에 이미 있다
   *  - `mapidx` — 도폭 번호(`GF20`). 도폭을 찾을 때만 쓴다
   *
   *  "모두 표시" 를 누르면 펼친다. 한 번 펼치면 다음 팝업에도 펼쳐 둔다. */
  var EXTRA_PROPS = ["symnum", "mapname", "mapidx"];
  var showExtraProps = false;

  function extraToggle(table, count) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "extra-toggle";
    b.dataset.count = count;
    b.addEventListener("click", function () {
      showExtraProps = !showExtraProps;
      syncExtra();
    });
    syncExtra(b);
    return b;
  }

  function syncExtra(only) {
    var buttons = only ? [only] : document.querySelectorAll("#popup-body .extra-toggle");
    buttons.forEach(function (b) {
      b.textContent = showExtraProps ? T("접기") : T("모두 표시 ({n})", { n: b.dataset.count });
    });
    if (only) return;
    document.querySelectorAll("#popup-body table").forEach(function (t) {
      t.classList.toggle("show-extra", showExtraProps);
    });
  }

  /** 속성값 한 칸. 서버가 `{text, links}` 로 갈라 보낸 것은 진짜 링크로 그린다.
   *  **5만 지질도의 `도폭`** 이 그렇게 온다 — 원도 PDF 와 수치지질도 DOI 가
   *  딸려 있다. 주소 검사는 서버가 이미 했다(`views._split_links`). 여기서는
   *  `textContent` 와 `href` 만 쓰고 **innerHTML 을 쓰지 않는다.** */
  function valueCell(value) {
    var td = document.createElement("td");
    if (value && typeof value === "object" && value.links) {
      if (value.text) td.appendChild(document.createTextNode(value.text));
      value.links.forEach(function (link) {
        // 화면 안의 일(스발바르 "이 도폭만 켜기")은 주소 없이 단추로 그린다
        if (link.action) {
          var b = document.createElement("button");
          b.type = "button";
          b.className = "proplink action";
          b.textContent = link.label;
          b.addEventListener("click", link.action);
          td.appendChild(b);
          return;
        }
        var a = document.createElement("a");
        a.className = "proplink";
        a.href = link.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = link.label;
        td.appendChild(a);
      });
    } else {
      td.textContent = String(value);
    }
    return td;
  }

  function plain(props) {
    var out = {};
    Object.keys(props).forEach(function (k) {
      if (k === "geometry" || k.charAt(0) === "_") return;
      if (props[k] === null || props[k] === "") return;
      out[k] = props[k];
    });
    return out;
  }

  // ── 좌표 ────────────────────────────────────────────────────────

  function dd2dms(value, isLat) {
    var hemi = isLat ? (value >= 0 ? "N" : "S") : (value >= 0 ? "E" : "W");
    value = Math.abs(value);
    var deg = Math.floor(value);
    var rest = (value - deg) * 60;
    var min = Math.floor(rest);
    var sec = (rest - min) * 60;
    if (Math.round(sec * 10) / 10 >= 60) { sec = 0; min += 1; }
    if (min >= 60) { min = 0; deg += 1; }
    return deg + "°" + String(min).padStart(2, "0") + "'" +
      sec.toFixed(1).padStart(4, "0") + '"' + hemi;
  }

  function coordText(lon, lat) {
    return dd2dms(lat, true) + " " + dd2dms(lon, false);
  }

  function formatPair(lon, lat) {
    return useDms
      ? dd2dms(lat, true) + " " + dd2dms(lon, false)
      : lat.toFixed(6) + ", " + lon.toFixed(6);
  }

  /** 보이는 지도의 네 가장자리 위경도. 종이 지도의 테두리 눈금처럼 읽는다.
   *
   *  **커서 자리의 좌표는 없앴다.** 움직일 때마다 바뀌어 읽을 틈이 없고,
   *  누른 자리는 팝업 첫 줄이 이미 답한다. 대신 "지금 어디를 보고 있나" 를
   *  테두리에 적는다. 웹 메르카토르라 위도는 x 와, 경도는 y 와 무관하다 —
   *  가장자리 한가운데 한 점씩만 읽으면 된다. 아래쪽은 좌표 막대가 덮는
   *  만큼을 빼고 읽는다. */
  function renderEdges() {
    var size = map.getSize();
    if (!size) return;
    var w = size[0], h = size[1];
    var bar = document.getElementById("coordbar").offsetHeight || 0;
    var bottom = h - bar;
    // 첫 그림이 그려지기 전에는 화면 자리를 좌표로 못 옮긴다(null) — 휴대폰에서는 크기가
    // 먼저 정해져 그 틈에 불렸다 (wetherilli 128)
    if (!map.getCoordinateFromPixel([0, 0])) return;
    function at(px, py) { return toLL(map.getCoordinateFromPixel([px, py])); }
    function lat(v) { return useDms ? dd2dms(v, true) : Math.abs(v).toFixed(4) + "°" + (v >= 0 ? "N" : "S"); }
    function lon(v) { return useDms ? dd2dms(v, false) : Math.abs(v).toFixed(4) + "°" + (v >= 0 ? "E" : "W"); }
    var top = at(w / 2, 0), down = at(w / 2, bottom);
    var left = at(0, bottom / 2), right = at(w, bottom / 2);
    // 극지 화면은 위가 북쪽이 아니라 가장자리마다 위경도가 둘 다 바뀐다 —
    // 네 가장자리 한가운데의 위경도를 통째로 적는다. 돌린 지도도 같다 (wetherilli 114)
    var both = !isMercator() || map.getView().getRotation() !== 0;
    function pair(p) { return lat(p[1]) + " " + lon(p[0]); }
    document.getElementById("edge-n").textContent = both ? pair(top) : lat(top[1]);
    document.getElementById("edge-s").textContent = both ? pair(down) : lat(down[1]);
    document.getElementById("edge-w").textContent = both ? pair(left) : lon(left[0]);
    document.getElementById("edge-e").textContent = both ? pair(right) : lon(right[0]);
  }

  // ── 개인 레이어 (wetherilli P08·118) ─────────────────────────────
  //
  // 관리 화면(`manage/`)에서 반입해 **이 브라우저의 IndexedDB 에 둔 것**이다(`personal.js`).
  // 서버로 가지 않는다 — 점묶음(`PointSet`)과 다른 자리다. 켜고 끄기·색·이름도 그 기록에 적어
  // 관리 화면과 이 창이 같은 것을 본다. 저쪽에서 바꾸면 여기로 알림이 온다(BroadcastChannel).

  var Personal = window.GSMPersonal;
  var personal = [];             // 저장소의 기록
  var personalLayers = {};       // 기록 id -> ol 레이어
  //: 한 자리에서 레이어마다 팝업에 올리는 수. 지역 대표점에 수백 건이 겹치기도 한다(nkfcluster)
  var PERSONAL_POPUP_MAX = 8;

  /** 저장소에서 읽어 그린다. `fresh` 면 연결 레이어(P09·122)를 새로 받는다 — 지도를 열 때 한 번.
   *  다른 창의 알림으로 다시 읽을 때는 받지 않는다(받으면 저장 → 알림 → 다시 받기로 돈다). */
  function loadPersonal(fresh) {
    if (!Personal) return;
    Personal.setTranslator(T);
    Personal.configure({ proxy: document.body.dataset.linkedProxy === "1" ? BASE + "linked/fetch/" : "", csrf: csrf });
    Personal.list().then(function (rows) {
      personal = rows;
      drawPersonal();
      if (fresh !== true) return;
      // 마지막으로 받은 것을 먼저 그려 두고, 새것이 오면 그것만 바꿔 그린다
      // 한 연결에서 모양마다 갈라 둔 기록들은 한 번 받아 함께 덮는다 (wetherilli 126)
      Personal.linkGroups(personal).forEach(function (group) {
        Personal.refresh(group).then(drawPersonal);
      });
    }).catch(function () {
      personal = [];
      drawPersonal();
    });
  }

  /** 기록마다 ol 레이어를 새로 만든다. 투영이 바뀔 때도 이것을 부른다 — 위경도에서 다시 옮긴다. */
  function drawPersonal() {
    if (!personalGroup) return;
    personalGroup.getLayers().clear();
    personalLayers = {};
    var format = new ol.format.GeoJSON({ featureProjection: viewProj() });
    personal.forEach(function (rec) {
      var labels = {};
      (rec.columns || []).forEach(function (c) { labels[c.key] = c.label || c.key; });
      // **같은 자리의 점은 하나로 모은다** (wetherilli 120). 지역 대표점에 수백 건이 겹치는 자료(nkfcluster)에서
      // 네모 수백 장을 포개 그리면 하나로 보여 몇 건인지 모른다. 모은 점에는 건수를 단다(`pointIcon`).
      // 자리는 원본 위경도로 맞춘다 — 화면 투영으로 옮긴 뒤에 맞추면 소수점 끝이 갈려 따로 놀 수 있다
      var features = [];
      var stacks = {};
      rec.features.forEach(function (f, i) {
        if (!f.geometry) return;
        var item = { props: f.properties, fid: f.id === undefined ? i + 1 : f.id };
        if (f.geometry.type === "Point") {
          var key = f.geometry.coordinates[0].toFixed(7) + "," + f.geometry.coordinates[1].toFixed(7);
          if (stacks[key]) { stacks[key].get("_items").push(item); return; }
        }
        var feature;
        try { feature = format.readFeature({ type: "Feature", geometry: f.geometry, properties: {} }); } catch (e) { return; }
        // 속성은 한 덩이로 붙인다 — 원본 열 이름이 ol 의 것(geometry 따위)과 부딪히지 않게
        feature.setProperties({ _개인: rec.id, _items: [item] });
        if (f.geometry.type === "Point") stacks[key] = feature;
        features.push(feature);
      });
      features.forEach(function (feature) {
        var items = feature.get("_items");
        var first = rec.label ? items[0].props[rec.label] : null;
        if (first === null || first === undefined || first === "") return;
        feature.set("이름표", items.length > 1 ? T("{name} 외 {n}건", { name: first, n: items.length - 1 }) : first);
      });
      var layer = new ol.layer.Vector({
        source: new ol.source.Vector({ features: features }),
        style: personalStyle(rec),
        declutter: true,
        visible: rec.visible !== false,
      });
      layer.set("gsmPersonal", { id: rec.id, name: rec.name, labels: labels });
      personalLayers[rec.id] = layer;
      personalGroup.getLayers().push(layer);
    });
    renderPersonal();
  }

  // ── 개인 레이어의 꾸밈 (wetherilli 131) ──────────────────────────
  //
  // 기록마다 `color` 와 `style`(점: 모양·크기, 선·면: 굵기·선 꼴, 면: 채움 투명도)을 든다. 목록의 아이콘을 누르면
  // 고르개가 뜬다(`openStylePicker`). **지도 기호·겹친 점·목록 아이콘·고르개 미리 보기를 한 함수(`drawSymbol`)가 그린다** —
  // 넷이 따로 그리면 고른 것과 지도에 뜬 것이 달라진다.

  var STYLE_DEFAULT = { shape: "circle", size: 7, width: 2.2, dash: "solid", opacity: 0.3 };
  function styleOf(rec) {
    var s = rec.style || {};
    var out = {};
    Object.keys(STYLE_DEFAULT).forEach(function (k) { out[k] = s[k] === undefined ? STYLE_DEFAULT[k] : s[k]; });
    return out;
  }

  /** 목록 아이콘에 맞춘 꾸밈 — 큰 점은 아이콘 칸에 맞게 줄인다 */
  function iconStyle(rec) {
    var st = styleOf(rec);
    st.size = Math.min(st.size, 7.5);
    return st;
  }

  /** 모양의 길을 그린다 — 가운데 (cx, cy), 반지름 r. */
  function shapePath(g, shape, cx, cy, r) {
    g.beginPath();
    function poly(n, rot, radii) {
      for (var i = 0; i < n; i++) {
        var a = rot + i * 2 * Math.PI / n, rr = radii ? radii[i % radii.length] : r;
        if (i) g.lineTo(cx + rr * Math.cos(a), cy + rr * Math.sin(a)); else g.moveTo(cx + rr * Math.cos(a), cy + rr * Math.sin(a));
      }
      g.closePath();
    }
    if (shape === "square") g.rect(cx - r * 0.86, cy - r * 0.86, r * 1.72, r * 1.72);
    else if (shape === "diamond") poly(4, -Math.PI / 2);
    else if (shape === "triangle") { poly(3, -Math.PI / 2, [r * 1.15]); }
    else if (shape === "star") poly(10, -Math.PI / 2, [r * 1.18, r * 0.5]);
    else if (shape === "hexagon") poly(6, 0);
    else g.arc(cx, cy, r, 0, 2 * Math.PI);
  }

  function dashOf(dash, width) {
    if (dash === "dashed") return [width * 3, width * 2];
    if (dash === "dotted") return [0.1, width * 2];
    return null;
  }

  /** 한 기호를 캔버스에 그린다. kind 가 point 면 모양(겹친 수 n 이 둘 넘으면 장을 포개고 건수 딱지),
   *  line 이면 짧은 선, polygon 이면 채운 네모. 크기는 캔버스 크기에 맞춘다 — 목록·고르개용. */
  function drawSymbol(canvas, kind, color, st, n) {
    var pr = Math.max(1, Math.round(window.devicePixelRatio || 1));
    var w = canvas._cssW, h = canvas._cssH;
    canvas.width = w * pr; canvas.height = h * pr;
    var g = canvas.getContext("2d");
    g.scale(pr, pr);
    g.clearRect(0, 0, w, h);
    if (kind === "line") {
      g.lineCap = "round";
      g.strokeStyle = "rgba(0, 0, 0, 0.45)"; g.lineWidth = st.width + 2.5;
      g.setLineDash(dashOf(st.dash, st.width + 2.5) || []);
      g.beginPath(); g.moveTo(3, h - 4); g.lineTo(w * 0.45, h * 0.35); g.lineTo(w - 3, h * 0.55); g.stroke();
      g.strokeStyle = color; g.lineWidth = st.width; g.setLineDash(dashOf(st.dash, st.width) || []);
      g.beginPath(); g.moveTo(3, h - 4); g.lineTo(w * 0.45, h * 0.35); g.lineTo(w - 3, h * 0.55); g.stroke();
      return canvas;
    }
    if (kind === "polygon") {
      g.fillStyle = hexAlpha(color, st.opacity);
      g.fillRect(3, 3, w - 6, h - 6);
      g.strokeStyle = color; g.lineWidth = Math.min(st.width, 3); g.setLineDash(dashOf(st.dash, Math.min(st.width, 3)) || []);
      g.strokeRect(3, 3, w - 6, h - 6);
      return canvas;
    }
    var r = Math.min(st.size, (Math.min(w, h) - 6) / 2);
    var cx = w / 2, cy = h / 2;
    if (n > 1) { cx -= 3; cy += 3; }
    function one(dx, dy, alpha) {
      g.save();
      g.globalAlpha = alpha;
      g.shadowColor = "rgba(0, 0, 0, 0.45)"; g.shadowBlur = 3; g.shadowOffsetY = 1;
      shapePath(g, st.shape, cx + dx, cy + dy, r);
      g.fillStyle = color; g.fill();
      g.shadowColor = "transparent";
      g.lineWidth = 1.6; g.strokeStyle = "#fff"; g.stroke();
      g.restore();
    }
    if (n > 1) { one(3.5, -3.5, 0.5); one(1.75, -1.75, 0.75); }
    one(0, 0, 1);
    if (n > 1) {
      var label = n > 999 ? "999+" : String(n);
      var br = label.length < 2 ? 7 : label.length < 3 ? 8.5 : 10.5;
      var bx = cx + r + 1, by = cy - r - 1;
      g.fillStyle = "#1f1409"; g.strokeStyle = "#fff"; g.lineWidth = 1.4;
      g.beginPath(); g.arc(bx, by, br, 0, 2 * Math.PI); g.fill(); g.stroke();
      g.fillStyle = "#fff"; g.font = "700 " + (label.length < 3 ? 10 : 8.5) + "px sans-serif";
      g.textAlign = "center"; g.textBaseline = "middle";
      g.fillText(label, bx, by + 0.5);
    }
    return canvas;
  }

  function symbolCanvas(w, h) {
    var c = document.createElement("canvas");
    c._cssW = w; c._cssH = h;
    c.style.width = w + "px"; c.style.height = h + "px";
    return c;
  }

  /** 점 기호 — 색·모양·크기·겹친 수마다 한 번만 굽는다. 그림 안에 건수를 그려 넣는 까닭은 120
   *  (이 판의 OL 은 글자에 `declutterMode` 를 주지 못해, 이름표로 달면 겹침 거르기에 지워진다). */
  var symbolIcons = {};
  function pointIcon(color, st, n) {
    var key = [color, st.shape, st.size, n > 1 ? n : 1].join("/");
    if (symbolIcons[key]) return symbolIcons[key];
    var badge = n > 1 ? 24 : 0;
    var size = Math.ceil(2 * (st.size * 1.2 + 4)) + badge;
    var canvas = drawSymbol(symbolCanvas(size, size), "point", color, st, n);
    var pr = canvas.width / size;
    symbolIcons[key] = new ol.style.Icon({ img: canvas, size: [canvas.width, canvas.height], scale: 1 / pr,
                                           declutterMode: "none" });
    return symbolIcons[key];
  }

  /** 개인 레이어의 모양. 점묶음(흰 테 동그라미)과 갈리게 그림자를 깔고, 고른 모양·크기·굵기·투명도를 따른다. */
  function personalStyle(rec) {
    var color = rec.color || Personal.DEFAULT_COLOR;
    var st = styleOf(rec);
    var dash = dashOf(st.dash, st.width);
    var halo = new ol.style.Stroke({ color: "rgba(20, 12, 4, 0.45)", width: st.width + 2.5, lineDash: dashOf(st.dash, st.width + 2.5) || undefined });
    var line = new ol.style.Stroke({ color: color, width: st.width, lineDash: dash || undefined, lineCap: "round" });
    var area = new ol.style.Fill({ color: hexAlpha(color, st.opacity) });
    var base = pointStyle(color);
    return function (feature, resolution) {
      var text = base(feature, resolution).getText();
      var n = (feature.get("_items") || []).length;
      var kind = feature.getGeometry().getType();
      if (kind.indexOf("Point") >= 0) return new ol.style.Style({ image: pointIcon(color, st, n), text: text });
      return [new ol.style.Style({ stroke: halo }),
              new ol.style.Style({ stroke: line, fill: /Polygon/.test(kind) ? area : undefined, text: text })];
    };
  }

  /** 꾸밈을 바꿨다 — 지도와 목록 아이콘을 다시 그리고, 잠시 뒤 저장한다(끌개를 움직이는 동안 매번 저장하지 않게). */
  var saveStyleTimer = {};
  function restyle(rec) {
    if (personalLayers[rec.id]) personalLayers[rec.id].setStyle(personalStyle(rec));
    var icon = document.querySelector('#personal-list [data-rec="' + rec.id + '"]');
    if (icon) drawSymbol(icon, rec.kind, rec.color, iconStyle(rec), 1);
    clearTimeout(saveStyleTimer[rec.id]);
    saveStyleTimer[rec.id] = setTimeout(function () { Personal.put(rec); }, 400);
  }

  /** 꾸밈 고르개 — 목록의 아이콘을 누르면 그 곁에 뜬다. 바꾸는 대로 지도에 보인다. */
  var picker = null;
  function closeStylePicker() {
    if (picker) { picker.remove(); picker = null; }
  }
  function openStylePicker(rec, anchor) {
    closeStylePicker();
    var st = styleOf(rec);
    picker = document.createElement("div");
    picker.className = "style-picker";
    picker.setAttribute("role", "dialog");
    picker.setAttribute("aria-label", T("꾸밈"));

    function section(title) {
      var sec = document.createElement("div");
      sec.className = "sp-sec";
      var h = document.createElement("div");
      h.className = "sp-title";
      h.textContent = title;
      sec.appendChild(h);
      picker.appendChild(sec);
      return sec;
    }
    function update(patch) {
      rec.style = Object.assign({}, rec.style || {}, patch);
      st = styleOf(rec);
      restyle(rec);
      refreshChoices();
    }
    var refreshers = [];
    function refreshChoices() { refreshers.forEach(function (f) { f(); }); }

    // 색
    var colors = section(T("색"));
    var row = document.createElement("div");
    row.className = "sp-colors";
    Personal.PALETTE.forEach(function (c) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "sp-color";
      b.style.background = c;
      b.title = c;
      b.addEventListener("click", function () { rec.color = c; custom.value = c; restyle(rec); refreshChoices(); });
      refreshers.push(function () { b.classList.toggle("on", (rec.color || "").toLowerCase() === c); });
      row.appendChild(b);
    });
    var custom = document.createElement("input");
    custom.type = "color";
    custom.className = "sp-custom";
    custom.title = T("다른 색");
    custom.value = rec.color || Personal.DEFAULT_COLOR;
    custom.addEventListener("input", function () { rec.color = custom.value; restyle(rec); refreshChoices(); });
    row.appendChild(custom);
    colors.appendChild(row);

    function slider(sec, label, min, max, step, get, set, fmt) {
      var wrap = document.createElement("label");
      wrap.className = "sp-slider";
      var name = document.createElement("span");
      name.textContent = label;
      var input = document.createElement("input");
      input.type = "range"; input.min = min; input.max = max; input.step = step; input.value = get();
      var out = document.createElement("span");
      out.className = "sp-val";
      out.textContent = fmt(get());
      input.addEventListener("input", function () { set(Number(input.value)); out.textContent = fmt(Number(input.value)); });
      wrap.append(name, input, out);
      sec.appendChild(wrap);
    }

    if (rec.kind === "point") {
      var shapes = section(T("모양"));
      var srow = document.createElement("div");
      srow.className = "sp-shapes";
      Personal.SHAPES.forEach(function (shape) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "sp-shape";
        b.title = SHAPE_NAMES[shape];
        var c = symbolCanvas(26, 26);
        b.appendChild(c);
        refreshers.push(function () {
          drawSymbol(c, "point", rec.color, Object.assign({}, st, { shape: shape, size: 8 }), 1);
          b.classList.toggle("on", st.shape === shape);
        });
        b.addEventListener("click", function () { update({ shape: shape }); });
        srow.appendChild(b);
      });
      shapes.appendChild(srow);
      slider(shapes, T("크기"), 4, 14, 0.5, function () { return st.size; }, function (v) { update({ size: v }); },
             function (v) { return v + " px"; });
    } else {
      var lines = section(rec.kind === "polygon" ? T("테두리") : T("선"));
      slider(lines, T("굵기"), 0.5, 8, 0.5, function () { return st.width; }, function (v) { update({ width: v }); },
             function (v) { return v + " px"; });
      var drow = document.createElement("div");
      drow.className = "seg sp-dash";
      [["solid", T("실선")], ["dashed", T("파선")], ["dotted", T("점선")]].forEach(function (d) {
        var b = document.createElement("button");
        b.type = "button";
        b.textContent = d[1];
        refreshers.push(function () { b.classList.toggle("on", st.dash === d[0]); });
        b.addEventListener("click", function () { update({ dash: d[0] }); });
        drow.appendChild(b);
      });
      lines.appendChild(drow);
      if (rec.kind === "polygon") {
        var fill = section(T("채움"));
        slider(fill, T("투명도"), 0, 100, 5, function () { return Math.round((1 - st.opacity) * 100); },
               function (v) { update({ opacity: Math.round(100 - v) / 100 }); }, function (v) { return v + "%"; });
      }
    }

    var foot = document.createElement("div");
    foot.className = "sp-foot";
    var reset = document.createElement("button");
    reset.type = "button";
    reset.className = "btn quiet";
    reset.textContent = T("모양을 처음대로");
    reset.addEventListener("click", function () { rec.style = {}; st = styleOf(rec); restyle(rec); closeStylePicker(); });
    var done = document.createElement("button");
    done.type = "button";
    done.className = "btn";
    done.textContent = T("닫는다");
    done.addEventListener("click", closeStylePicker);
    foot.append(reset, done);
    picker.appendChild(foot);

    document.body.appendChild(picker);
    refreshChoices();
    // 아이콘 오른쪽에 붙이되, 화면 밖으로 나가면 안으로 당긴다
    var a = anchor.getBoundingClientRect(), pw = picker.offsetWidth, ph = picker.offsetHeight;
    var left = Math.min(a.right + 8, window.innerWidth - pw - 8);
    var top = Math.min(Math.max(8, a.top - 12), window.innerHeight - ph - 8);
    picker.style.left = Math.max(8, left) + "px";
    picker.style.top = Math.max(8, top) + "px";
  }
  var SHAPE_NAMES = { circle: T("동그라미"), square: T("네모"), diamond: T("마름모"), triangle: T("세모"), star: T("별"), hexagon: T("육각") };
  document.addEventListener("mousedown", function (e) {
    if (picker && !picker.contains(e.target) && !(e.target.closest && e.target.closest(".ps-symbol"))) closeStylePicker();
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeStylePicker(); });

  /** 팝업 덩이들 — 모은 점이면 든 것마다 하나. 열 이름은 반입한 양식의 label 로 적는다.
   *  레이어마다 `PERSONAL_POPUP_MAX` 건까지만 내고 나머지는 세기만 한다(넘친 것은 onClick 이 한 줄로). */
  function personalParts(feature, seen) {
    var id = feature.get("_개인");
    var layer = personalLayers[id];
    var info = layer && layer.get("gsmPersonal");
    if (!info) return [];
    var items = feature.get("_items") || [];
    seen[id] = seen[id] || { n: 0, name: info.name };
    var out = [];
    items.forEach(function (item, i) {
      seen[id].n += 1;
      if (seen[id].n > PERSONAL_POPUP_MAX) return;
      var props = {};
      Object.keys(item.props || {}).forEach(function (key) {
        var value = item.props[key];
        if (value === null || value === undefined || value === "") return;
        if (/^https?:\/\//i.test(String(value))) value = { text: "", links: [{ url: String(value), label: T("열기") }] };
        props[info.labels[key] || key] = value;
      });
      out.push({ title: items.length > 1 ? T("{name} — 이 자리 {i}/{n}", { name: info.name, i: i + 1, n: items.length }) : info.name,
                 props: props });
    });
    return out;
  }

  function renderPersonal() {
    var host = document.getElementById("personal-list");
    if (!host) return;
    setCount("count-personal", personal.length);
    host.innerHTML = "";
    // 반입한 것이 없으면 블록을 감춘다 (wetherilli 120). 들어가는 길은 바닥의 관리 단추다
    document.getElementById("box-personal").hidden = !personal.length;
    if (!personal.length) return;
    personal.forEach(function (rec) {
      var li = document.createElement("li");
      var box = document.createElement("input");
      box.type = "checkbox";
      box.checked = rec.visible !== false;
      box.addEventListener("change", function () {
        rec.visible = box.checked;
        if (personalLayers[rec.id]) personalLayers[rec.id].setVisible(rec.visible);
        Personal.put(rec);
      });
      // 아이콘 — 지도에 뜬 그대로 그린다. 누르면 꾸밈 고르개 (wetherilli 131)
      var swatch = document.createElement("button");
      swatch.type = "button";
      swatch.className = "ps-symbol";
      swatch.title = T("색·모양을 바꾼다");
      var icon = symbolCanvas(22, 22);
      icon.dataset.rec = rec.id;
      drawSymbol(icon, rec.kind, rec.color || Personal.DEFAULT_COLOR, iconStyle(rec), 1);
      swatch.appendChild(icon);
      swatch.addEventListener("click", function (e) {
        e.stopPropagation();
        if (picker && picker._rec === rec.id) { closeStylePicker(); return; }
        openStylePicker(rec, swatch);
        picker._rec = rec.id;
      });
      var name = document.createElement("span");
      name.className = "ps-name";
      name.textContent = rec.name;
      var count = document.createElement("span");
      count.className = "ps-count";
      count.textContent = (rec.link ? "🔗 " : "") +
        (rec.kind === "polygon" ? T("면 {n}", { n: rec.drawn }) : rec.kind === "line" ? T("선 {n}", { n: rec.drawn })
          : T("{n}점", { n: rec.drawn })) +
        (rec.count > rec.drawn ? " · " + T("좌표 없음 {n}", { n: rec.count - rec.drawn }) : "");
      // 연결 레이어를 못 받았으면 옛것을 그리고 있다는 것을 적는다
      if (rec.link && rec.status && !rec.status.ok) {
        count.textContent += " · " + T("받지 못해 옛것");
        count.classList.add("stale");
        count.title = rec.status.error || "";
      } else if (rec.link && rec.fetched) {
        count.title = T("마지막으로 받은 때 {when}", { when: new Date(rec.fetched).toLocaleString() });
      }
      var zoom = iconButton("⊙", T("이 자료로 범위를 맞춘다"), false, function () {
        var source = personalLayers[rec.id] && personalLayers[rec.id].getSource();
        var extent = source && source.getExtent();
        if (extent && isFinite(extent[0])) {
          map.getView().fit(extent, { padding: [40, 40, 60, 40], maxZoom: 14, duration: 300 });
        }
      });
      var label = document.createElement("span");
      label.className = "ps-text";
      label.append(name, count);
      li.append(box, swatch, label, zoom);
      host.appendChild(li);
    });
    // 용량이 넘었으면 블록 밑에 한 줄 (wetherilli 131). 자세한 것은 관리 화면의 저장 자료
    Personal.measure(personal).then(function (m) {
      var warn = document.getElementById("personal-warn");
      if (!warn) return;
      warn.hidden = !m.warnings.length;
      warn.className = "personal-warn" + (m.warnings.some(function (w) { return w.level === "bad"; }) ? " bad" : "");
      warn.innerHTML = "";
      m.warnings.slice(0, 2).forEach(function (w) {
        var line = document.createElement("span");
        line.textContent = w.text;
        warn.appendChild(line);
      });
      if (m.warnings.length) {
        var a = document.createElement("a");
        a.href = BASE + "manage/";
        a.textContent = T("관리 화면에서 정리한다");
        warn.appendChild(a);
      }
    });
  }

  if (Personal) Personal.onChange(function () { loadPersonal(false); });

  // ── 점묶음 ──────────────────────────────────────────────────────

  //: 이름표를 보이기 시작하는 줌. 이보다 멀리서 보면 글자가 점을 덮는다.
  var LABEL_MIN_ZOOM = 11;

  /** 점묶음의 모양. 점은 동그라미, 선·면은 점묶음의 색으로 그린다.
   *  가까이 보면 **이름표를 곁에 적는다** — 전에는 눌러야 떴다. 겹치는
   *  글자는 OL 이 걸러낸다(`declutter`). */
  function pointStyle(color) {
    var dot = new ol.style.Circle({
      radius: 5,
      fill: new ol.style.Fill({ color: color }),
      stroke: new ol.style.Stroke({ color: "#fff", width: 1.5 }),
    });
    var line = new ol.style.Stroke({ color: color, width: 2.5 });
    var area = new ol.style.Fill({ color: hexAlpha(color, 0.18) });
    return function (feature, resolution) {
      var kind = feature.getGeometry().getType();
      var isPoint = kind === "Point";
      var label = feature.get("이름표");
      var text = label && mercZoom(resolution) >= LABEL_MIN_ZOOM ? new ol.style.Text({
        text: String(label),
        font: "12px sans-serif",
        offsetX: isPoint ? 8 : 0,
        textAlign: isPoint ? "left" : "center",
        placement: /LineString/.test(kind) ? "line" : "point",
        overflow: !isPoint,
        fill: new ol.style.Fill({ color: "#1f1409" }),
        stroke: new ol.style.Stroke({ color: "rgba(255,255,255,0.9)", width: 3 }),
      }) : undefined;
      if (isPoint) return new ol.style.Style({ image: dot, text: text });
      return new ol.style.Style({
        stroke: line,
        fill: /Polygon/.test(kind) ? area : undefined,
        text: text,
      });
    };
  }

  /** "#rrggbb" 에 투명도를 준다. 면을 칠할 때 밑의 지질도가 비쳐야 한다. */
  function hexAlpha(hex, alpha) {
    var m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || "");
    if (!m) return "rgba(228, 87, 46, " + alpha + ")";
    return "rgba(" + parseInt(m[1], 16) + ", " + parseInt(m[2], 16) + ", " + parseInt(m[3], 16) + ", " + alpha + ")";
  }

  /** 목록에 적는 수 — "12점", 선·면이 있으면 "12점 · 선 1 · 면 2". */
  function countText(ps) {
    var bits = [T("{n}점", { n: ps.count || 0 })];
    if (ps.lines) bits.push(T("선 {n}", { n: ps.lines }));
    if (ps.polygons) bits.push(T("면 {n}", { n: ps.polygons }));
    if (!ps.count && (ps.lines || ps.polygons)) bits.shift();
    if (ps.elevated) bits.push(T("고도 {n}", { n: ps.elevated }));
    return bits.join(" · ");
  }

  function loadPointSet(ps) {
    if (pointLayers[ps.id]) {
      pointLayers[ps.id].setVisible(ps.visible);
      return;
    }
    var source = new ol.source.Vector({
      url: BASE + "pointsets/" + ps.id + "/geojson/",
      // 서버는 위경도로 준다. 읽을 때 화면 투영으로 옮긴다 — 투영이 바뀌면
      // 점묶음을 다시 읽는다 (`setProjection`)
      format: new ol.format.GeoJSON({ featureProjection: viewProj() }),
    });
    source.on("featuresloadend", function (e) {
      e.features.forEach(function (f) { f.set("_점묶음", ps.name); });
    });
    var layer = new ol.layer.Vector({
      source: source,
      style: pointStyle(ps.color),
      declutter: true,
      visible: ps.visible,
    });
    pointLayers[ps.id] = layer;
    pointLayerGroup.getLayers().push(layer);
  }

  // 3D 창에서 켜고 끄면 이 창도 따라간다 (다른 창의 저장소 바뀜만 온다)
  window.addEventListener("storage", function (e) {
    if (e.key !== PS_OFF_KEY) return;
    var off = pointsetsOff();
    pointsets.forEach(function (ps) { ps.visible = off.indexOf(ps.id) < 0; });
    renderPointSets();
  });

  function renderPointSets() {
    var host = document.getElementById("pointset-list");
    setCount("count-points", pointsets.length);
    host.innerHTML = "";
    if (!pointsets.length) {
      host.innerHTML = '<li class="empty">' + T("왼쪽 위 <b>불러오기</b> 탭에서 올린다") + "</li>";
      return;
    }
    pointsets.forEach(function (ps) {
      loadPointSet(ps);
      var li = document.createElement("li");

      var box = document.createElement("input");
      box.type = "checkbox";
      box.checked = ps.visible;
      box.addEventListener("change", function () {
        ps.visible = box.checked;
        setPointsetOff(ps.id, !ps.visible);
        if (pointLayers[ps.id]) pointLayers[ps.id].setVisible(ps.visible);
      });

      var swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = ps.color;

      var name = document.createElement("span");
      name.className = "ps-name";
      name.textContent = ps.name;

      var count = document.createElement("span");
      count.className = "ps-count";
      count.textContent = countText(ps);

      var zoom = iconButton("⊙", T("이 자료로 범위를 맞춘다"), false, function () {
        var source = pointLayers[ps.id] && pointLayers[ps.id].getSource();
        var extent = source && source.getExtent();
        if (extent && isFinite(extent[0])) {
          map.getView().fit(extent, { padding: [40, 40, 60, 40], maxZoom: 14, duration: 300 });
        }
      });

      // 표고 타일에서 점마다 고도를 읽어 채운다(P03). 원본의 `고도` 열은 건드리지 않고
      // "표고(DEM)"·"표고 출처" 두 칸으로 따로 싣는다. 다시 누르면 덮는다
      var elev = iconButton("⛰", T("표고 채우기 — 표고 타일에서 점마다 고도를 읽는다 (극지 PGC · 일본 국토지리원 · 그 밖 SRTM)"),
                            !ps.count, function () {
        elev.disabled = true;
        post(BASE + "pointsets/" + ps.id + "/elevation/").then(function (r) {
          return r.json().catch(function () { return {}; }).then(function (d) {
            if (!r.ok) throw new Error(d.error || "");
            return d;
          });
        }).then(function (d) {
          elev.disabled = false;
          if (d.pointset) Object.assign(ps, d.pointset, { visible: ps.visible });
          if (pointLayers[ps.id]) pointLayers[ps.id].getSource().refresh();
          alert(T("{n}점 채움 · {m}점은 자료 밖", { n: d.filled, m: d.missed }));
          renderPointSets();
        }).catch(function (e) {
          elev.disabled = false;
          alert((e && e.message) || T("표고를 받지 못했다"));
        });
      });

      // VWorld 에서 한국 점마다 도로명·지번·읍면동·가장 가까운 단층·둘레 지명을 읽어 채운다(074).
      // 점이 적으면 올릴 때 이미 채웠다. 원본의 `주소` 열은 건드리지 않고 "(VWorld)" 칸으로 따로 싣는다
      var place = null;
      if (vworldKey && ps.korean) {
        place = iconButton("📍", T("둘레 채우기 — VWorld 에서 점마다 주소·읍면동·가까운 단층·둘레 지명·보호구역·지목·소유구분을 읽는다 ({n}/{m}점 채움)",
                                   { n: ps.placed || 0, m: ps.korean }), false, function () {
          place.disabled = true;
          post(BASE + "pointsets/" + ps.id + "/places/").then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (d) {
              if (!r.ok) throw new Error(d.error || "");
              return d;
            });
          }).then(function (d) {
            place.disabled = false;
            if (d.pointset) Object.assign(ps, d.pointset, { visible: ps.visible });
            if (pointLayers[ps.id]) pointLayers[ps.id].getSource().refresh();
            alert(T("{n}점 채움 · {m}점은 받지 못했다", { n: d.filled, m: d.missed }));
            renderPointSets();
          }).catch(function (e) {
            place.disabled = false;
            alert((e && e.message) || T("VWorld 에서 받지 못했다"));
          });
        });
      }

      // 올린 것을 GeoJSON 으로 돌려받는다. 원래 CSV 였어도 위경도와 속성이
      // 그대로 나온다 — QGIS 에 곧장 얹을 수 있다
      var save = iconButton("⤓", T("GeoJSON 으로 내려받는다"), false, function () {
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
          if (pointLayers[ps.id]) {
            pointLayerGroup.getLayers().remove(pointLayers[ps.id]);
            delete pointLayers[ps.id];
          }
          pointsets = pointsets.filter(function (x) { return x.id !== ps.id; });
          renderPointSets();
        });
      });

      // 이름과 수를 두 줄로 쌓는다. 한 줄이면 "3점 · 선 1 · 면 2" 가 이름을 밀어낸다
      var label = document.createElement("span");
      label.className = "ps-text";
      label.append(name, count);
      li.append(box, swatch, label, zoom, elev);
      if (place) li.append(place);
      li.append(save, csv, del);
      host.appendChild(li);
    });
  }

  function csrf() {
    var input = document.querySelector("#upload-form [name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": csrf() },
      body: body || new FormData(),
    });
  }

  // ── 지역 바꾸기 ──────────────────────────────────────────────────

  function readRegions() {
    try {
      var added = JSON.parse(stored("gsm.regions") || "null");
      if (Array.isArray(added)) {
        addedRegions = ["korea"].concat(added.filter(function (r) { return REGIONS[r] && r !== "korea"; }));
      }
      var saved = stored("gsm.region");
      if (saved && REGIONS[saved] && (addedRegions.indexOf(saved) >= 0 || PINNED.indexOf(saved) >= 0)) region = saved;
    } catch (e) { /* 사생활 모드 */ }
    // 소개 화면의 "이 지도로" 가 지역을 주소로 넘긴다(`?region=`). 탭이 없으면 더하고, 주소에서는
    // 지운다 — 새로 고칠 때마다 그 지역으로 끌려가지 않게 (wetherilli 113)
    var params = new URLSearchParams(location.search);
    var wanted = params.get("region");
    if (wanted && REGIONS[wanted]) {
      if (addedRegions.indexOf(wanted) < 0 && PINNED.indexOf(wanted) < 0) addedRegions.push(wanted);
      region = wanted;
      params.delete("region");
      var qs = params.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    }
  }

  function saveRegions() {
    try {
      store("gsm.regions", JSON.stringify(addedRegions.slice(1)));
      store("gsm.region", region);
    } catch (e) { /* 사생활 모드 */ }
  }

  /** 지역 탭 — 늘 보이는 셋(한국·북극·남극)과, 나머지를 접은 "그 외" 하나 (wetherilli 214).
   *  지역이 서른을 넘어 탭 줄이 몇 줄로 늘어났다. 더한 지역은 "그 외" 의 위 칸에, 아직 안 더한 것은
   *  그 밑의 "+ 추가 지역" 칸에 묶음째 선다. 접힌 지역을 보는 동안에는 "그 외" 단추가 그 지역 이름이 된다 */
  var foldCloser = false;
  function renderRegions() {
    var host = document.getElementById("regions");
    host.innerHTML = "";
    var pinned = PINNED.filter(function (k) { return REGIONS[k]; });
    pinned.forEach(function (key) {
      var tab = document.createElement("button");
      tab.type = "button";
      tab.className = "region-tab" + (key === region ? " on" : "");
      tab.dataset.region = key;
      tab.textContent = T(REGIONS[key].title);
      tab.addEventListener("click", function () { switchRegion(key); });
      host.appendChild(tab);
    });
    var folded = addedRegions.filter(function (k) { return pinned.indexOf(k) < 0; });
    var more = Object.keys(REGIONS).filter(function (k) { return addedRegions.indexOf(k) < 0 && pinned.indexOf(k) < 0; });
    if (!folded.length && !more.length) return;
    var inFold = pinned.indexOf(region) < 0;
    var wrap = document.createElement("div");
    wrap.className = "region-more";
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "region-tab region-fold" + (inFold ? " on" : "");
    btn.dataset.region = inFold ? region : "";
    btn.setAttribute("aria-haspopup", "true");
    btn.textContent = (inFold ? T(REGIONS[region].title) : T("그 외")) + " ▾";
    var menu = document.createElement("ul");
    menu.className = "region-menu";
    menu.hidden = true;
    function head(text) {
      var li = document.createElement("li");
      li.className = "head";
      li.textContent = text;
      menu.appendChild(li);
    }
    // 더한 지역 — 누르면 그리로, × 로 뺀다
    folded.forEach(function (key) {
      var li = document.createElement("li");
      li.className = "added" + (key === region ? " on" : "");
      li.dataset.region = key;
      li.textContent = T(REGIONS[key].title);
      li.addEventListener("click", function () { switchRegion(key); });
      var x = document.createElement("span");
      x.className = "region-x";
      x.textContent = "×";
      x.title = T("이 지역을 탭에서 뺀다");
      x.addEventListener("click", function (e) {
        e.stopPropagation();
        addedRegions = addedRegions.filter(function (r) { return r !== key; });
        if (region === key) switchRegion("korea"); else { saveRegions(); renderRegions(); }
      });
      li.appendChild(x);
      menu.appendChild(li);
    });
    if (more.length) head("+ " + T("추가 지역"));
    // 묶음(`includes` — 동아시아·북극) 밑에 딸린 지역을 들여 세운다 (wetherilli 111). 묶음을 이미 더했으면 머리는
    // 누를 수 없는 제목으로만 남는다. 어느 묶음에도 들지 않는 지역은 그대로
    function item(key, cls) {
      var li = document.createElement("li");
      li.className = cls || "";
      li.dataset.region = key;
      li.textContent = T(REGIONS[key].title) + (REGIONS[key].pending ? " — " + T("준비 중") : "");
      if (more.indexOf(key) >= 0) {
        li.addEventListener("click", function () {
          addedRegions.push(key);
          switchRegion(key);
        });
      } else li.className += " head";
      menu.appendChild(li);
    }
    var parentOf = {};
    Object.keys(REGIONS).forEach(function (k) {
      (REGIONS[k].includes || []).forEach(function (c) { if (!parentOf[c]) parentOf[c] = k; });
    });
    Object.keys(REGIONS).forEach(function (key) {
      if (parentOf[key]) return;                                           // 묶음 밑에서 세운다
      var kids = (REGIONS[key].includes || []).filter(function (c) { return more.indexOf(c) >= 0; });
      if (more.indexOf(key) < 0 && !kids.length) return;
      item(key, kids.length ? "group" : "");
      kids.forEach(function (c) { item(c, "sub"); });
    });
    // 차림은 화면에 붙여(fixed) 단추 밑에 세운다 — 패널과 휴대폰의 탭 줄(가로 굴림)이 넘친 것을 잘라서다
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      menu.hidden = !menu.hidden;
      if (menu.hidden) return;
      var r = btn.getBoundingClientRect();
      menu.style.top = (r.bottom + 4) + "px";
      menu.style.maxHeight = Math.min(560, Math.max(160, window.innerHeight - r.bottom - 12)) + "px";
      menu.style.left = Math.max(8, Math.min(r.left, window.innerWidth - menu.offsetWidth - 8)) + "px";
    });
    menu.addEventListener("click", function (e) { e.stopPropagation(); });
    if (!foldCloser) {
      foldCloser = true;
      var closeFold = function (e) {
        var open = document.querySelector("#regions .region-menu");
        if (open && !(e && e.type === "scroll" && open.contains(e.target))) open.hidden = true;
      };
      document.addEventListener("click", closeFold);
      document.addEventListener("scroll", closeFold, true);
      window.addEventListener("resize", closeFold);
    }
    wrap.append(btn, menu);
    host.appendChild(wrap);
  }

  /** 지역을 바꾼다. 지금 지역의 것을 기억해 두고, 새 지역의 것을 되살린다. */
  function switchRegion(next) {
    if (!REGIONS[next]) return;
    saveView();
    if (compareMode !== "off") setCompare("off");
    // 켠 레이어를 모두 내린다 (기억은 이미 해 두었다)
    active.slice().forEach(function (e) { map.removeLayer(e.layer); });
    active = [];
    region = next;
    setProjection(regionProj());
    applyRegion();
    saveRegions();
    renderRegions();
    renderCatalog();
    if (!restoreState()) {
      goHome();
      openFirstLayer();
    }
    restack();
    closePopup();
  }

  /** 지역에 딸린 겉모습 — 색 테마, 배경 고르개, 한국 전용 칸, 준비 중 알림. */
  /** 극지(평사도법으로 보는 지역)에서는 극지 아이콘 — 숨은 차림 단추·설정 제목·브라우저 탭 (wetherilli 123) */
  function setEmblem() {
    var btn = document.getElementById("emblem-btn");
    var polar = REGIONS[region].proj !== "EPSG:3857";
    var src = polar ? btn.dataset.emblemPolar : btn.dataset.emblem;
    document.querySelectorAll("img.emblem").forEach(function (img) { if (img.getAttribute("src") !== src) img.src = src; });
    var icon = document.getElementById("favicon");
    if (icon && icon.getAttribute("href") !== src) {
      icon.setAttribute("type", polar ? "image/png" : "image/svg+xml");
      icon.setAttribute("href", src);
    }
  }

  function applyRegion() {
    document.documentElement.setAttribute("data-region", region);
    setEmblem();
    var spec = REGIONS[region];
    fillBasemaps();
    var select = document.getElementById("basemap");
    // 배경은 지역마다 기억한다. 고르개에 없는 것이면(열쇠가 빠졌다) 없음으로
    var saved = savedBasemap();
    select.value = select.querySelector('option[value="' + saved + '"]') ? saved : "none";
    setBasemap(select.value);
    // 지명 칸은 지명을 끌 수 있는 배경(위성)에서만 보인다
    var labelled = BASEMAPS[select.value] && BASEMAPS[select.value].labels;
    document.getElementById("basemap-labels-wrap").style.display = labelled ? "" : "none";
    document.getElementById("crs-pick").hidden = !spec.vworld;
    // 3D 는 메르카토르 하나뿐이라 남위 85° 안쪽은 없다(P02 §7). 그래도 남극도 연다 — 기지와
    // 산맥은 거의 그 바깥이고, 지형은 REMA·ArcticDEM 을 서버가 옮겨 준다 (032). 지질은 3857 로도
    // 그려 주는 NPI 드로닝모드랜드와, 3031 로 굽는 것을 서버가 3857 로 다시 펴 주는 GeoMAP 이다 (040)
    if (syncGotoHint) syncGotoHint();
    var note = document.getElementById("region-note");
    note.hidden = !spec.pending;
    document.getElementById("layer-catalog").hidden = !!spec.pending;
  }

  /** 처음 온 지역이면 대표 레이어 하나를 켜 둔다. */
  function openFirstLayer() {
    // 대표가 카탈로그에 없으면 그 지역 목록의 첫 레이어
    // `first` 가 여럿이면(얀마옌) 적힌 차례로 켠다 — 뒤의 것이 위에 얹힌다
    var here = regionCatalog();
    var firsts = [].concat(REGIONS[region].first || []).filter(function (n) { return byName[n]; });
    if (!firsts.length && here[0] && here[0].layers[0]) firsts = [here[0].layers[0].name];
    firsts.forEach(function (first) {
      addLayer(first);
    });
  }

  // ── 주제도 비교 ──────────────────────────────────────────────────
  //
  // 두 가지다. **밀어 보기**는 고른 레이어를 세로 막대의 왼쪽에만 그려,
  // 막대를 끌며 밑의 것과 견준다. 같은 자리를 두 주제도로 번갈아 보는 데
  // 좋다. **나란히**는 지도를 둘로 가른다 — 두 지도가 같은 보기(`ol.View`)를
  // 나눠 써서 함께 움직이고, 한쪽의 마우스 자리를 다른 쪽에 점으로 비춘다.
  // 투명도를 내려 겹치는 것만으로는 5만과 25만처럼 색이 비슷한 것을 가르기
  // 어렵다.

  var compareMode = "off";
  var swipePos = 0.5;                 // 막대의 자리. 지도 폭에 대한 비
  var swipeName = null;               // 막대 왼쪽에만 그리는 레이어
  var swipeKeys = [];
  var map2 = null, map2Layer = null, map2Base = null, map2Name = null;
  var mirror1 = null, mirror2 = null;

  function clipBefore(e) {
    var ctx = e.context;
    var size = map.getSize();
    var x = size[0] * swipePos;
    var tl = ol.render.getRenderPixel(e, [0, 0]);
    var tr = ol.render.getRenderPixel(e, [x, 0]);
    var bl = ol.render.getRenderPixel(e, [0, size[1]]);
    var br = ol.render.getRenderPixel(e, [x, size[1]]);
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(tl[0], tl[1]);
    ctx.lineTo(bl[0], bl[1]);
    ctx.lineTo(br[0], br[1]);
    ctx.lineTo(tr[0], tr[1]);
    ctx.closePath();
    ctx.clip();
  }

  function clipAfter(e) { e.context.restore(); }

  function unclip() {
    swipeKeys.forEach(function (k) { ol.Observable.unByKey(k); });
    swipeKeys = [];
  }

  function applySwipe() {
    unclip();
    var entry = active.find(function (e) { return e.name === swipeName; });
    if (entry) {
      swipeKeys = [entry.layer.on("prerender", clipBefore), entry.layer.on("postrender", clipAfter)];
    }
    placeSwipeBar();
    map.render();
  }

  function placeSwipeBar() {
    var bar = document.getElementById("swipe");
    bar.hidden = compareMode !== "swipe";
    bar.style.left = (swipePos * 100) + "%";
  }

  function rightLayerTitle() {
    var row = byName[map2Name];
    return row ? row.title : "";
  }

  function buildMap2() {
    if (!map2) {
      map2 = new ol.Map({
        target: "map2",
        view: map.getView(),            // 같은 보기를 나눠 쓴다 — 함께 움직인다
        controls: [],
        layers: [],
      });
      mirror1 = mirrorOverlay(map);
      mirror2 = mirrorOverlay(map2);
      rightDragRotate(map2);
      map.on("pointermove", function (e) { if (compareMode === "split") mirror2.setPosition(e.coordinate); });
      map2.on("pointermove", function (e) { if (compareMode === "split") mirror1.setPosition(e.coordinate); });
      map.getViewport().addEventListener("pointerleave", function () { mirror2.setPosition(undefined); });
      map2.getViewport().addEventListener("pointerleave", function () { mirror1.setPosition(undefined); });
    }
    if (map2.getView() !== map.getView()) map2.setView(map.getView());   // 지역을 바꿨다
    if (map2Base) map2.removeLayer(map2Base);
    var spec = BASEMAPS[document.getElementById("basemap").value];
    map2Base = spec && spec.make ? spec.make() : null;
    if (map2Base) { map2Base.setZIndex(0); map2.addLayer(map2Base); }
    if (map2Layer) map2.removeLayer(map2Layer);
    map2Layer = null;
    if (map2Name && byName[map2Name]) {
      map2Layer = makeLayer(map2Name);
      map2Layer.setZIndex(1);
      map2.addLayer(map2Layer);
    }
    document.getElementById("split-right").textContent = rightLayerTitle();
    document.getElementById("split-left").textContent =
      active.length ? active.map(function (e) { return e.title; }).join(" · ") : T("켠 레이어가 없다");
  }

  /** 다른 쪽 지도의 마우스 자리를 비추는 작은 점. */
  function mirrorOverlay(target) {
    var el = document.createElement("div");
    el.className = "mirror-dot";
    var overlay = new ol.Overlay({ element: el, positioning: "center-center", stopEvent: false });
    target.addOverlay(overlay);
    return overlay;
  }

  function setCompare(mode) {
    compareMode = mode;
    document.querySelectorAll("#compare-mode button").forEach(function (b) {
      b.classList.toggle("on", b.dataset.cmp === mode);
    });
    var wrap = document.getElementById("map-wrap");
    wrap.classList.toggle("split", mode === "split");
    document.getElementById("map2").hidden = mode !== "split";
    if (mode !== "swipe") unclip();
    if (mode === "split") buildMap2();
    if (mode !== "split" && mirror1) { mirror1.setPosition(undefined); mirror2.setPosition(undefined); }
    refreshCompare();
    // 지도 칸의 폭이 바뀌었으니 다시 잰다
    setTimeout(function () { map.updateSize(); if (map2) map2.updateSize(); }, 0);
  }

  /** 비교 칸의 고르개를 지금 켠 레이어에 맞춘다. restack 이 부른다. */
  function refreshCompare() {
    var pick = document.getElementById("compare-pick");
    var wrap = document.getElementById("compare-pick-wrap");
    var hint = document.getElementById("compare-hint");
    if (!pick) return;
    wrap.hidden = compareMode === "off";
    hint.textContent = compareMode === "swipe" ? T("고른 레이어가 막대 왼쪽에만 보인다. 막대를 끌어 견준다.")
      : compareMode === "split" ? T("왼쪽은 켠 레이어, 오른쪽은 고른 레이어. 두 지도가 함께 움직인다.")
      : "";
    pick.innerHTML = "";
    if (compareMode === "swipe") {
      document.getElementById("compare-pick-label").textContent = T("막대 왼쪽");
      if (!active.some(function (e) { return e.name === swipeName; })) {
        swipeName = active.length ? active[0].name : null;
      }
      active.forEach(function (e) {
        var o = document.createElement("option");
        o.value = e.name; o.textContent = e.title;
        pick.appendChild(o);
      });
      if (active.length < 2) hint.textContent = T("먼저 레이어를 둘 이상 켠다.");
      pick.value = swipeName || "";
      applySwipe();
    } else if (compareMode === "split") {
      document.getElementById("compare-pick-label").textContent = T("오른쪽");
      var here = regionCatalog();
      var inRegion = function (name) {
        return here.some(function (g) { return g.layers.some(function (l) { return l.name === name; }); });
      };
      if (!map2Name || !inRegion(map2Name)) {
        // 오른쪽 지도도 지금 지역의 레이어로 — 그린란드에서 한국 지질도를 띄우지 않는다
        map2Name = active.length > 1 ? active[1].name
          : inRegion("L_250K_Geology_Map") ? "L_250K_Geology_Map"
          : (here[0] && here[0].layers[0] ? here[0].layers[0].name : null);
      }
      here.forEach(function (group) {
        var og = document.createElement("optgroup");
        og.label = group.name;
        group.layers.forEach(function (l) {
          if (l.kind === "vector" || l.kind === "points") return;   // 나란히 보기의 오른쪽은 타일만 그린다
          var o = document.createElement("option");
          o.value = l.name; o.textContent = l.title;
          og.appendChild(o);
        });
        pick.appendChild(og);
      });
      pick.value = map2Name;
      buildMap2();
      placeSwipeBar();
    } else {
      placeSwipeBar();
    }
  }

  function wireCompare() {
    document.querySelectorAll("#compare-mode button").forEach(function (b) {
      b.addEventListener("click", function () { setCompare(b.dataset.cmp); });
    });
    document.getElementById("compare-pick").addEventListener("change", function () {
      if (compareMode === "swipe") { swipeName = this.value; applySwipe(); }
      if (compareMode === "split") { map2Name = this.value; buildMap2(); }
    });
    document.getElementById("basemap").addEventListener("change", function () {
      if (compareMode === "split") buildMap2();
    });
    // 막대 끌기. 손잡이만이 아니라 막대 어디를 잡아도 된다
    var bar = document.getElementById("swipe");
    var dragging = false;
    bar.addEventListener("pointerdown", function (e) {
      dragging = true;
      bar.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    bar.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      var box = document.getElementById("map").getBoundingClientRect();
      swipePos = Math.min(0.98, Math.max(0.02, (e.clientX - box.left) / box.width));
      placeSwipeBar();
      map.render();
    });
    bar.addEventListener("pointerup", function () { dragging = false; });
    setCompare("off");
  }

  // ── 붙이기 ──────────────────────────────────────────────────────

  /** 배경 고르개를 지금 지역에 맞춘다. VWorld 는 우리나라만 그린다. */
  function fillBasemaps() {
    var select = document.getElementById("basemap");
    select.innerHTML = "";
    Object.keys(BASEMAPS).forEach(function (key) {
      if (/^vworld/.test(key) && !REGIONS[region].vworld) return;
      var spec = BASEMAPS[key];
      // 묶음 지역(북극)은 품은 지역의 배경을 다 고를 수 있다
      if (spec.regions && !spec.regions.some(function (r) { return r === region || regionKeys().indexOf(r) >= 0; })) return;
      if (spec.needs && regionProj() !== spec.needs) return;     // proj4 를 못 읽었다
      var option = document.createElement("option");
      option.value = key;
      option.textContent = BASEMAPS[key].title;
      if (BASEMAPS[key].note) option.title = BASEMAPS[key].note;
      select.appendChild(option);
    });
  }

  function wireBasemap() {
    var select = document.getElementById("basemap");
    fillBasemaps();
    var labelBox = document.getElementById("basemap-labels");
    var labelWrap = document.getElementById("basemap-labels-wrap");

    function syncLabelBox() {
      var spec = BASEMAPS[select.value];
      var has = !!(spec && spec.labels);
      labelWrap.style.display = has ? "" : "none";
      labelBox.checked = labelsOn();
    }

    select.value = savedBasemap();
    if (!select.value) select.value = "none";
    select.addEventListener("change", function () {
      setBasemap(select.value);
      syncLabelBox();
      restack();
    });
    labelBox.addEventListener("change", function () { setLabels(labelBox.checked); });

    setBasemap(select.value);
    syncLabelBox();
  }

  // ── 설정과 판 이력 ─────────────────────────────────────────────

  // ── 모양 고르기 — 이 브라우저에만 남는다 ─────────────────────────
  //
  // 서버로 보내지 않는다. 고른 사람의 눈에만 걸린 일이고, 저장하려면
  // 계정이 있어야 하는데 이 뷰어에는 계정이 없다.

  var LOOKS = [
    // 실험 기능 — 켜면 <html data-labs="on"> 이 되고 `.labs` 붙은 것이 보인다
    { key: "labs", attr: "data-labs", store: "gsm.labs", fallback: "off", sel: "#opt-labs" },
    { key: "theme", attr: "data-theme", store: "gsm.theme", fallback: "brown", sel: "#opt-theme" },
    { key: "font", attr: "data-font", store: "gsm.font", fallback: "sans", sel: "#opt-font" },
    { key: "size", attr: "data-size", store: "gsm.size", fallback: "m", sel: "#opt-size" },
  ];

  /** 고르개에 없는 값이 남아 있으면 기본으로 돌린다. 앞 판의
   *  `auto`·`dark` 가 이 브라우저에 남아 있을 수 있다. */
  function readLook(spec) {
    var value;
    try { value = localStorage.getItem(spec.store); } catch (e) { value = null; }
    var known = Array.prototype.some.call(
      document.querySelectorAll(spec.sel + " button"),
      function (b) { return b.dataset[spec.key] === value; });
    return known ? value : spec.fallback;
  }

  function applyLook(spec, value) {
    document.documentElement.setAttribute(spec.attr, value);
    try { localStorage.setItem(spec.store, value); } catch (e) { /* 사생활 모드 */ }
    document.querySelectorAll(spec.sel + " button").forEach(function (b) {
      b.classList.toggle("on", b.dataset[spec.key] === value);
    });
  }

  /** 설정 창을 열기 전에도 걸어 둔다 — 창을 한 번도 안 연 사람도
   *  지난번에 고른 모양으로 보아야 한다. */
  function initLooks() {
    LOOKS.forEach(function (spec) { applyLook(spec, readLook(spec)); });
  }

  function wireLooks() {
    LOOKS.forEach(function (spec) {
      document.querySelectorAll(spec.sel + " button").forEach(function (button) {
        button.addEventListener("click", function () {
          applyLook(spec, button.dataset[spec.key]);
        });
      });
    });
  }

  /** 한국어·영어. 화면 틀을 서버가 그리므로 **쿠키로 서버에 알리고 다시
   *  읽는다.** 쿠키에는 `ko`·`en` 두 글자만 담긴다. */
  function wireLang() {
    document.querySelectorAll("#opt-lang button").forEach(function (b) {
      b.classList.toggle("on", b.dataset.lang === LANG);
      b.addEventListener("click", function () {
        if (b.dataset.lang === LANG) return;
        if (STATIC) {
          // 정적 판은 말마다 따로 구웠다 — 쿠키를 읽을 서버가 없다. 보던 자리(주소의 꼬리)는 그대로 넘긴다 (wetherilli 167)
          try { localStorage.setItem("gsm.lang", b.dataset.lang); } catch (e) { /* 사생활 모드 */ }
          location.href = BASE + (b.dataset.lang === "en" ? "en/" : "") + "map/" + location.search + location.hash;
          return;
        }
        document.cookie = "gsm_lang=" + b.dataset.lang + "; path=/; max-age=31536000; SameSite=Lax";
        location.reload();
      });
    });
  }

  function wireSettings() {
    var sheet = document.getElementById("settings");
    var loaded = false;

    function open() {
      sheet.hidden = false;
      renderState();
      renderDeleted();
      if (loaded) return;
      loaded = true;
      // 정적 판은 굽을 때 떠 둔 판 이력(`patchnotes.json`, deploy/static_site.py)을 읽는다 — 서버가 없다
      fetch(BASE + (STATIC ? "patchnotes.json" : "patchnotes/"))
        .then(function (r) { return r.json(); })
        .then(function (d) { renderNotes(d.notes || []); })
        .catch(function () {
          document.getElementById("notes").textContent = T("판 이력을 읽지 못했다.");
        });
    }

    function close() { sheet.hidden = true; }

    document.getElementById("gear").addEventListener("click", open);
    document.getElementById("settings-close").addEventListener("click", close);
    sheet.addEventListener("click", function (e) { if (e.target === sheet) close(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !sheet.hidden) close();
    });

    document.querySelectorAll(".stab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll(".stab").forEach(function (t) { t.classList.remove("on"); });
        document.querySelectorAll(".stabbody").forEach(function (b) { b.classList.remove("on"); });
        tab.classList.add("on");
        document.getElementById("stab-" + tab.dataset.stab).classList.add("on");
      });
    });

    wireLooks();
    wireLang();
  }

  /** 지금 무엇으로 돌고 있는지. 화면을 보고 상태를 물어오는 일이 잦아 둔다. */
  function renderState() {
    var rows = [
      [T("배경지도"), (BASEMAPS[document.getElementById("basemap").value] || {}).title || T("없음")],
      [T("켠 레이어"), active.length ? active.map(function (e) { return e.title; }).join(", ") : T("없음")],
      [T("찍은 점"), T("{n}개", { n: tempSource.getFeatures().length })],
      [T("올린 자료"), T("{n}묶음", { n: pointsets.length })],
      [T("좌표 표기"), useDms ? T("도분초") : T("십진도")],
    ];
    var host = document.getElementById("settings-state");
    host.innerHTML = "";
    rows.forEach(function (row) {
      var dt = document.createElement("dt");
      dt.textContent = row[0];
      var dd = document.createElement("dd");
      dd.textContent = row[1];
      host.append(dt, dd);
    });
  }

  /** 설정의 "지금 상태" 아래 — 최근 지운 점묶음과 되살리기. */
  function renderDeleted() {
    var host = document.getElementById("deleted-list");
    fetch(BASE + "pointsets/deleted/")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        host.innerHTML = "";
        if (!d.deleted.length) {
          host.innerHTML = '<li class="empty">' + esc(T("지운 것이 없다")) + "</li>";
          return;
        }
        d.deleted.forEach(function (row) {
          var li = document.createElement("li");
          var when = new Date(row.deleted_at).toLocaleString(LANG === "en" ? "en-GB" : "ko-KR",
            { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
          var text = document.createElement("span");
          text.className = "del-text";
          text.innerHTML = '<b>' + esc(row.name) + "</b> <span class=\"del-meta\">" +
            esc(countText({ count: row.points, lines: row.lines, polygons: row.polygons })) +
            " · " + esc(when) + (row.client ? " · " + esc(row.client) : "") + "</span>";
          li.appendChild(text);
          if (row.restored) {
            var done = document.createElement("span");
            done.className = "del-done";
            done.textContent = T("되살림");
            li.appendChild(done);
          } else {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn quiet";
            btn.textContent = T("되살리기");
            btn.addEventListener("click", function () {
              btn.disabled = true;
              post(BASE + "pointsets/deleted/" + row.id + "/restore/")
                .then(function (r) { return r.json().then(function (d2) { return { ok: r.ok, d: d2 }; }); })
                .then(function (res) {
                  if (!res.ok) { btn.textContent = res.d.error || T("되살리지 못했다"); return; }
                  pointsets.unshift(res.d.pointset);
                  renderPointSets();
                  renderDeleted();
                  renderState();
                });
            });
            li.appendChild(btn);
          }
          host.appendChild(li);
        });
      })
      .catch(function () { host.innerHTML = '<li class="empty">' + esc(T("읽지 못했다")) + "</li>"; });
  }

  function renderNotes(notes) {
    var host = document.getElementById("notes");
    host.innerHTML = "";
    if (!notes.length) {
      host.textContent = T("아직 적힌 판이 없다.");
      return;
    }
    notes.forEach(function (note) {
      var head = document.createElement("h4");
      head.innerHTML = esc(note.version) +
        (note.title ? ' <span class="note-title">' + esc(note.title) + "</span>" : "") +
        (note.date ? ' <span class="note-date">' + esc(note.date) + "</span>" : "");
      host.appendChild(head);

      if (note.lead) {
        var lead = document.createElement("p");
        lead.className = "note-lead";
        lead.textContent = note.lead;
        host.appendChild(lead);
      }
      if (note.items.length) {
        var ul = document.createElement("ul");
        note.items.forEach(function (item) {
          var li = document.createElement("li");
          // 문서에 `코드` 가 섞여 온다. 한 겹만 풀어 준다.
          li.innerHTML = esc(item).replace(/`([^`]+)`/g, "<code>$1</code>")
                                  .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
          ul.appendChild(li);
        });
        host.appendChild(ul);
      }
    });
  }

  function wireTabs() {
    document.querySelectorAll(".tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll(".tab").forEach(function (t) { t.classList.remove("on"); });
        document.querySelectorAll(".tabbody").forEach(function (b) { b.classList.remove("on"); });
        tab.classList.add("on");
        document.getElementById("tab-" + tab.dataset.tab).classList.add("on");
      });
    });
  }

  function wireCoordBar() {
    document.getElementById("dms-toggle").addEventListener("click", function () {
      useDms = !useDms;
      this.classList.toggle("on", useDms);
      renderEdges();
    });

    /** 정적 판의 좌표 읽기 — "위도, 경도" 십진도만. 도분초·평면 좌표는 서버(`coords.py`)가 읽는다 */
    function parseDecimal(q) {
      var m = q.match(/^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/);
      var lat = m && +m[1], lon = m && +m[2];
      return m && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? Promise.resolve({ lat: lat, lon: lon }) : Promise.reject();
    }

    var input = document.getElementById("goto-input");
    document.getElementById("goto-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var q = input.value.trim();
      if (!q) return;
      // 목록이 떠 있고 하나를 골라 두었으면 그리로 간다
      var picked = document.querySelector("#search-results li.on");
      if (picked) { picked.click(); return; }
      // **좌표가 먼저다.** 좌표로 읽히면 곧장 가고, 아니면 주소·장소로 찾는다
      (STATIC ? parseDecimal(q) : fetch(BASE + "coords/parse/?q=" + encodeURIComponent(q) + "&crs=" + encodeURIComponent(crsCode()))
        .then(function (r) { return r.ok ? r.json() : Promise.reject(); }))
        .then(function (d) {
          if (d.candidates) { renderOrders(d.candidates); return; }
          closeResults();
          goTo(d.lat, d.lon);
        })
        .catch(function () { searchPlaces(q); });
    });
    input.addEventListener("input", closeResults);
    input.addEventListener("keydown", function (e) {
      var items = Array.prototype.slice.call(document.querySelectorAll("#search-results li[data-i]"));
      if (!items.length) return;
      var at = items.findIndex(function (li) { return li.classList.contains("on"); });
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        at = e.key === "ArrowDown" ? Math.min(items.length - 1, at + 1) : Math.max(0, at - 1);
        items.forEach(function (li, i) { li.classList.toggle("on", i === at); });
        items[at].scrollIntoView({ block: "nearest" });
      } else if (e.key === "Escape") {
        closeResults();
      }
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest("#coordbar")) closeResults();
    });
  }

  // ── 주소·장소 찾기 (VWorld) ──────────────────────────────────────
  //
  // 서버의 `search/` 가 VWorld 에 묻는다. KIGAM 은 타지 않는다. 이름이 같은
  // 곳이 많아(가정동은 대전에도 인천에도 있다) **곧장 가지 않고 목록을
  // 띄운다.** 사람이 고른다.

  var KIND = { district: "행정구역", road: "도로명", parcel: "지번", place: "장소", order: "좌표",
               name: "지명", gsi: "주소·지명" };

  function closeResults() {
    var box = document.getElementById("search-results");
    box.hidden = true;
    box.innerHTML = "";
  }

  function searchPlaces(q) {
    var box = document.getElementById("search-results");
    box.hidden = false;
    if (!REGIONS[region].vworld) {
      // 스발바르·그린란드·남극(드로닝모드랜드)·북극은 지명을 뒤진다 (021·wetherilli 096). 나머지는 좌표로만 간다
      if (REGIONS[region].places) { searchNames(q); return; }
      if (REGIONS[region].gsi) { searchGsi(q); return; }
      box.innerHTML = '<li class="note">' + esc(T("이 지역에서는 좌표로 간다 — 주소·장소는 한국·일본, 지명은 스발바르·그린란드·북극·남극 탭에서 찾는다")) + "</li>";
      return;
    }
    box.innerHTML = '<li class="note">' + esc(T("찾는 중…")) + "</li>";
    // 정적 판은 서버(`search/`)가 없어 VWorld 를 JSONP 로 곧장 부른다 (wetherilli 164)
    (STATIC ? staticVworldSearch(q).then(function (results) { return { ok: true, d: { results: results } }; })
      : fetch(BASE + "search/?q=" + encodeURIComponent(q))
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); }))
      .then(function (res) {
        if (!res.ok) throw new Error(res.d.error || "");
        renderResults(res.d.results || []);
      })
      .catch(function (err) {
        box.innerHTML = '<li class="note">' + esc(err.message || T("찾지 못했다")) + "</li>";
      });
  }

  /** 스발바르 지명 8 393 에서 찾는다 — 서버가 한 번 받아 둔 것을 뒤진다(`placenames/`). */
  /** 지명 찾기의 출처 — 찾은 것이 없을 때도 이 글로 "지명 찾기였다" 를 가른다 */
  var PLACE_SOURCES = {
    svalbard: "지명 검색: 노르웨이 극지연구소 (스발바르)",
    greenland: "지명 검색: 그린란드 정부 (Nunat Aqqi)",
    antarctica: "지명 검색: 노르웨이 극지연구소 (드로닝모드랜드)",
    arctic: "지명 검색: 노르웨이 극지연구소 · 그린란드 정부",
  };

  function searchNames(q) {
    var box = document.getElementById("search-results");
    box.innerHTML = '<li class="note">' + esc(T("찾는 중…")) + "</li>";
    // 묶음 지역(북극)은 품은 지역들의 지명을 함께 뒤진다 — 서버가 지명이 없는 지역은 건너뛴다.
    // 정적 판은 구운 색인을 화면이 뒤진다 (wetherilli 166)
    (STATIC ? staticNames(q).then(function (rows) { return { ok: true, d: { results: rows } }; })
      : fetch(BASE + "placenames/?q=" + encodeURIComponent(q) + "&region=" + encodeURIComponent(regionKeys().join(",")))
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); }))
      .then(function (res) {
        if (!res.ok) throw new Error(res.d.error || "");
        renderResults(res.d.results || [], "", T(PLACE_SOURCES[region] || "지명 검색"));
      })
      .catch(function (err) {
        box.innerHTML = '<li class="note">' + esc(err.message || T("찾지 못했다")) + "</li>";
      });
  }

  // ── 정적 판의 지명 찾기 (wetherilli 166) ──
  // 서버의 `placenames/`(`arcpoints.match_index`)를 옮겼다. 색인은 `static_site.py` 가 구운 지명에서 지어 둔다 —
  // 한 줄은 [이름들, 곁말, 위도, 경도, 앞세움]. 지역마다 처음 찾을 때 한 번 받는다(그린란드 3 만 3 천 건)

  /** 찾기를 위해 접는다 — `arcpoints.fold` 와 같다 */
  function foldName(text) {
    return String(text || "").toLowerCase().replace(/æ/g, "ae").replace(/ø/g, "o").replace(/å/g, "a").replace(/ĸ/g, "q")
      .normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, " ").trim();
  }
  var placeIndexes = {};
  function placeIndex(url) {
    if (!placeIndexes[url]) {
      placeIndexes[url] = fetch(BASE + url)
        .then(function (r) { return r.ok ? r.json() : Promise.reject(new Error(T("찾지 못했다"))); })
        .then(function (rows) {
          rows.forEach(function (row) { row.folded = row[0].map(foldName); });
          return rows;
        });
      placeIndexes[url].catch(function () { delete placeIndexes[url]; });
    }
    return placeIndexes[url];
  }
  function staticNames(query) {
    var urls = [];
    regionKeys().forEach(function (key) {
      (staticBaked("placenames")[key] || []).forEach(function (u) { if (urls.indexOf(u) < 0) urls.push(u); });
    });
    var q = foldName(query);
    if (!urls.length || !q) return Promise.resolve([]);
    return Promise.all(urls.map(placeIndex)).then(function (lists) {
      var ranked = [];
      [].concat.apply([], lists).forEach(function (row) {
        var best = null;
        row.folded.forEach(function (name, i) {
          if (name.indexOf(q) < 0) return;
          var rank = name === q ? 0 : name.indexOf(q) === 0 ? 1 : 2;
          if (!best || rank < best[0]) best = [rank, i];
        });
        if (best) ranked.push({ rank: best[0], first: row[4], len: row[0][best[1]].length, i: best[1], row: row });
      });
      // 같은 이름 → 앞이 같은 것 → 들어 있는 것, 같으면 앞세울 것(도시·마을), 짧은 이름, 이름 차례
      ranked.sort(function (a, b) {
        return a.rank - b.rank || a.first - b.first || a.len - b.len || (a.row[0][0] < b.row[0][0] ? -1 : a.row[0][0] > b.row[0][0] ? 1 : 0);
      });
      return ranked.slice(0, 20).map(function (r) {
        var shown = r.row[0];
        return { kind: "name", title: r.i === 0 ? shown[0] : shown[0] + " (" + shown[r.i] + ")", sub: r.row[1],
                 lat: r.row[2], lon: r.row[3] };
      });
    });
  }

  /** 일본 — 국토지리원의 주소·지명 찾기(지리원 지도가 쓰는 것)를 브라우저가 곧장 부른다 (wetherilli 155).
   *  열쇠가 없고 CORS 가 열려 있어 문을 거치지 않는다. 지리원 지도를 위한 것이라 예고 없이 바뀔 수 있다고 국토지리원이
   *  밝혔다 — 닫히면 좌표로만 간다. 사람이 칠 때만 부른다 */
  var GSI_SEARCH = "https://msearch.gsi.go.jp/address-search/AddressSearch?q=";
  function searchGsi(q) {
    var box = document.getElementById("search-results");
    box.innerHTML = '<li class="note">' + esc(T("찾는 중…")) + "</li>";
    fetch(GSI_SEARCH + encodeURIComponent(q))
      .then(function (r) { return r.ok ? r.json() : Promise.reject(new Error(T("찾지 못했다"))); })
      .then(function (rows) {
        renderResults((Array.isArray(rows) ? rows : []).slice(0, 30).filter(function (f) {
          return f && f.geometry && f.geometry.coordinates;
        }).map(function (f) {
          return { kind: "gsi", title: (f.properties || {}).title || "", lon: +f.geometry.coordinates[0],
                   lat: +f.geometry.coordinates[1] };
        }), "", T("주소·지명 검색: 국토지리원 (지리원 지도)"));
      })
      .catch(function (err) {
        box.innerHTML = '<li class="note">' + esc(err.message || T("찾지 못했다")) + "</li>";
      });
  }

  function renderResults(rows, lead, src) {
    var box = document.getElementById("search-results");
    box.hidden = false;
    box.innerHTML = "";
    if (lead) {
      var head = document.createElement("li");
      head.className = "note";
      head.textContent = lead;
      box.appendChild(head);
    }
    if (!rows.length) {
      box.innerHTML = '<li class="note">' + esc(src ? T("찾은 것이 없다 — 이 지역의 지명을 넣어 본다")
        : T("찾은 것이 없다 — 주소·장소·행정구역을 넣어 본다")) + "</li>";
      return;
    }
    rows.forEach(function (row, i) {
      var li = document.createElement("li");
      li.dataset.i = i;
      li.innerHTML = '<span class="kind">' + esc(T(KIND[row.kind] || row.kind)) + "</span>" +
        '<span class="title">' + esc(row.title) + "</span>" +
        (row.sub ? '<span class="sub">' + esc(row.sub) + "</span>" : "");
      li.addEventListener("click", function () {
        closeResults();
        goTo(row.lat, row.lon, row.kind === "order" ? undefined
          : row.kind === "place" ? row.title : row.title.replace(/\s*\(.*\)$/, ""));
      });
      li.addEventListener("mouseenter", function () {
        box.querySelectorAll("li").forEach(function (x) { x.classList.toggle("on", x === li); });
      });
      box.appendChild(li);
    });
    if (lead) return;          // 좌표 차례 고르기는 VWorld 를 타지 않았다
    var note = document.createElement("li");
    note.className = "note src";
    note.textContent = src || T("주소 검색: VWorld (국토지리정보원)");
    box.appendChild(note);
  }

  // ── 좌표계 ──────────────────────────────────────────────────────
  //
  // 좌표 칸 옆의 고르개. 평면 좌표계(TM 등)를 고르면 좌표 칸이 동·북 두
  // 수를 받고, 팝업에 그 좌표가 한 줄 더 뜬다. 바꾸는 셈은 서버(`crs.py`)가
  // 한다 — 옛 측지계 옮기기까지 브라우저에 두면 같은 셈이 두 곳에 산다.
  // 올리기 칸의 좌표계도 처음에는 이것을 따른다.

  function crsCode() {
    var pick = document.getElementById("crs-pick");
    if (!pick || !REGIONS[region].vworld) return "4326";     // 한국 좌표계는 한국에서만
    return pick.value;
  }

  function wireCrs() {
    var pick = document.getElementById("crs-pick");
    var upload = document.getElementById("upload-crs");
    var input = document.getElementById("goto-input");
    gotoPlain = input.placeholder;
    try {
      var saved = localStorage.getItem("gsm.crs");
      if (saved && pick.querySelector('option[value="' + saved + '"]')) pick.value = saved;
    } catch (e) { /* 사생활 모드 */ }
    function sync() {
      upload.value = pick.value;
      input.placeholder = crsCode() === "4326" ? gotoPlaceholder()
        : T("{name} — 동 북 두 수, 또는 N 420005 E 232509 · 주소·장소도 된다",
            { name: pick.options[pick.selectedIndex].text });
      try { localStorage.setItem("gsm.crs", pick.value); } catch (e) { /* 사생활 모드 */ }
    }
    pick.addEventListener("change", sync);
    syncGotoHint = sync;
    sync();
  }

  //: 좌표 칸의 안내. 한국은 템플릿이 적은 것(주소 예시), 스발바르·북극은 지명,
  //  나머지 극지는 좌표만 (devlog 021). 지역을 바꾸면 `applyRegion` 이 다시 적는다
  var gotoPlain = "", syncGotoHint = null;

  function gotoPlaceholder() {
    var spec = REGIONS[region];
    if (spec.vworld) return gotoPlain;
    if (spec.places) return T("좌표·지명으로 이동 — {example}", { example: spec.places });
    if (spec.gsi) return T("좌표·주소·지명으로 이동 — {example}", { example: spec.gsi });
    var example = spec.example || (spec.center[1].toFixed(1) + ", " + spec.center[0].toFixed(1));
    return T("좌표로 이동 — 위도, 경도 (예: {example})", { example: example });
  }

  var projectMemo = {};

  /** 팝업에 고른 평면 좌표계의 좌표를 한 줄 붙인다. */
  function projectedFor(lon, lat) {
    var code = crsCode();
    if (code === "4326") return Promise.resolve(null);
    var key = code + ":" + lat.toFixed(6) + "," + lon.toFixed(6);
    if (!projectMemo[key]) {
      projectMemo[key] = fetch(BASE + "coords/project/?crs=" + code + "&lat=" + lat + "&lon=" + lon)
        .then(function (r) { return r.ok ? r.json() : null; })
        .catch(function () { return null; });
    }
    return projectMemo[key];
  }

  /** 평면 좌표 두 수가 어느 차례로도 말이 될 때 — 둘을 띄워 고르게 한다. */
  function renderOrders(rows) {
    renderResults(rows.map(function (r) {
      return {
        kind: "order", lat: r.lat, lon: r.lon,
        title: formatPair(r.lon, r.lat),
        sub: T("동 {e} · 북 {n}", { e: r.east.toLocaleString(), n: r.north.toLocaleString() })
             + (r.order === "en" ? " · " + T("적은 차례") : ""),
      };
    }), T("두 차례 모두 한반도 안이다 — 고른다. 이름을 붙여 적으면(N 420005 E 232509) 곧장 간다."));
  }

  // 팝업 첫 줄 밑의 주소. 같은 자리를 여러 번 누르므로 브라우저에도 들고 있는다.
  var addressMemo = {};

  function addressFor(lon, lat) {
    var key = lat.toFixed(5) + "," + lon.toFixed(5);
    if (!addressMemo[key]) {
      addressMemo[key] = (STATIC ? staticVworldWhereis(+lat.toFixed(5), +lon.toFixed(5))
        : fetch(BASE + "whereis/?lat=" + lat.toFixed(5) + "&lon=" + lon.toFixed(5))
          .then(function (r) { return r.ok ? r.json() : {}; }))
        .catch(function () { return {}; });
    }
    return addressMemo[key];
  }

  function wireUpload() {
    var form = document.getElementById("upload-form");
    var file = document.getElementById("upload-file");
    var msg = document.getElementById("upload-msg");

    file.addEventListener("change", function () {
      var box = file.closest(".filebox");
      box.classList.toggle("has", !!file.files.length);
      if (file.files.length) box.querySelector("span").textContent = file.files[0].name;
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!file.files.length) return;
      var data = new FormData();
      data.append("file", file.files[0]);
      data.append("name", document.getElementById("upload-name").value);
      data.append("color", document.getElementById("upload-color").value);
      data.append("crs", document.getElementById("upload-crs").value);

      msg.className = "msg";
      msg.textContent = T("읽는 중…");

      var upload = function (body, extra) {
        return post(BASE + "pointsets/upload/", body)
          .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
          .then(function (res) {
            if (!res.ok) {
              msg.className = "msg bad";
              msg.textContent = res.d.error || T("올리지 못했다");
              return;
            }
            // 위경도 없이 주소만 적힌 CSV — 화면이 나눠 묻고 다시 올린다 (wetherilli 152)
            if (res.d.geocode) return geocodeRows(res.d.geocode).then(function (job) {
              if (!job) return;
              var again = new FormData();
              again.append("file", new File([job.csv], file.files[0].name.replace(/\.[^.]*$/, "") + ".csv",
                                            { type: "text/csv" }));
              again.append("name", data.get("name") || file.files[0].name.replace(/\.[^.]*$/, ""));
              again.append("color", data.get("color"));
              again.append("crs", "4326");
              return upload(again, job.note);
            });
            pointsets.unshift(res.d.pointset);
            renderPointSets();
            msg.className = "msg good";
            msg.textContent = T("올렸다 — {what}.", { what: countText(res.d.pointset) }) +
              (res.d.notes && res.d.notes.length ? " " + res.d.notes.join(" / ") : "") + (extra ? " " + extra : "");
            form.reset();
            var box = file.closest(".filebox");
            box.classList.remove("has");
            box.querySelector("span").textContent = T("CSV · GeoJSON 고르기");
          });
      };
      upload(data).catch(function () {
        msg.className = "msg bad";
        msg.textContent = T("올리지 못했다");
      });
    });

    /** 주소 줄들을 `chunk` 줄씩 VWorld 로 찾아, 위도·경도·찾은 주소 열을 붙인 CSV 를 짓는다 (wetherilli 152).
     *  올리기 한 번이 60 초에 묶여 서버가 한꺼번에 찾지 않는다 — 한 요청이 10 초 안쪽이 되게 나눈다.
     *  못 찾은 줄은 빼고 줄 번호를 알린다. 하나도 못 찾았거나 VWorld 가 거절하면 null */
    function geocodeRows(job) {
      var rows = job.rows, chunk = job.chunk || 50, points = [], i = 0;
      var step = function () {
        if (i >= rows.length) return Promise.resolve();
        msg.className = "msg";
        msg.textContent = T("주소로 좌표를 찾는 중… {done} / {all}줄", { done: i, all: rows.length });
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
          msg.className = "msg bad";
          msg.textContent = T("주소로 좌표를 하나도 찾지 못했다 — 도로명·지번 주소인지 본다.");
          return null;
        }
        missed.sort(function (a, b) { return a - b; });
        var shown = missed.slice(0, 20).join(", ") + (missed.length > 20 ? " …" : "");
        return { csv: lines.join("\n"),
                 note: missed.length ? T("주소를 못 찾은 줄 {n}개 — {lines}", { n: missed.length, lines: shown }) : "" };
      }).catch(function (err) {
        msg.className = "msg bad";
        msg.textContent = (err && err.message) || T("올리지 못했다");
        return null;
      });
    }

    function csvCell(value) {
      var text = value == null ? "" : String(value);
      return /[",\n\r]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
    }
  }

  function closePopup() {
    document.getElementById("popup").classList.remove("on");
    document.getElementById("map-wrap").classList.remove("popup-open");
    popupOverlay.setPosition(undefined);
  }

  function wirePopup() {
    document.getElementById("popup-close").addEventListener("click", closePopup);
  }

  function esc(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /** 클립보드에 넣는다. 됐으면 풀리고 못 했으면 거절되는 Promise.
   *
   *  **`navigator.clipboard` 는 https 나 localhost 에서만 있다.** 운영은
   *  `http://paleolab` 이라 그것이 아예 없어서, 앞 판에서는 복사를 눌러도
   *  아무 일 없이 넘어갔다. 그때는 옛 길(`execCommand("copy")`)로 간다 —
   *  낡았다고 적혀 있지만 모든 브라우저가 아직 받는다. 누른 그 순간에
   *  불러야 하므로 이 함수는 클릭 처리기 안에서 곧장 부른다. */
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

  /** 대돌여지도 아이콘의 숨은 차림. 누르면 뜨고, 밖을 누르거나 Esc 면 닫힌다 (P05). */
  function wireEmblemMenu() {
    var button = document.getElementById("emblem-btn");
    var menu = document.getElementById("hidden-menu");
    if (!button || !menu) return;
    function show(open) {
      menu.hidden = !open;
      button.setAttribute("aria-expanded", open ? "true" : "false");
    }
    button.addEventListener("click", function (e) {
      e.stopPropagation();
      show(menu.hidden);
    });
    document.addEventListener("click", function (e) {
      if (!menu.hidden && !menu.contains(e.target)) show(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !menu.hidden) { show(false); button.focus(); }
    });
  }

  /** 정적 판의 키 (wetherilli P11·162·174) — **KIGAM·VWorld 둘 다 보는 사람이 각자 넣는다**(사용자 결정, 2026-10-02).
   *  공개 판을 처음 열 때 둘을 받는 창을 띄우고, 한국 탭 위 알림 줄에 상태와 "키 바꾸기" 를 둔다. 키는 이 브라우저에만
   *  남는다(30 일, "이 PC 에 기억하지 않기" 면 탭 동안만). VWorld 키는 배경·찾기가 시작할 때 읽으므로 넣으면 다시 연다 */
  var STATIC_KEYS = [
    { name: "kigam", label: "KIGAM 인증키", what: "한국 지질도",
      get: "https://data.kigam.re.kr/", getLabel: "지오빅데이터 오픈플랫폼에서 받기" },
    { name: "vworld", label: "VWorld 인증키", what: "배경지도·주소 찾기·지질 참고",
      get: "https://www.vworld.kr/dev/v4dv_apikeyguide_s001.do", getLabel: "VWorld 에서 받기" },
  ];

  function wireStaticKey() {
    var box = document.getElementById("static-key");
    if (!STATIC) return;
    if (box) {
      box.innerHTML = "";
      var held = STATIC_KEYS.filter(function (k) { return readKey(k.name); });
      var text = document.createElement("span");
      text.textContent = held.length === STATIC_KEYS.length ? T("인증키 둘을 넣었다 — 이 브라우저에만 있다")
        : held.length ? T("{name} 만 넣었다", { name: T(held[0].label) })
        : T("인증키를 넣어야 한국 지질도와 배경지도가 보인다");
      var open = document.createElement("button");
      open.type = "button";
      open.className = "btn quiet";
      open.textContent = held.length ? T("키 바꾸기") : T("키 넣기");
      open.addEventListener("click", openKeyDialog);
      box.append(text, open);
    }
    // 처음 열 때(둘 가운데 하나라도 없으면) 묻는다. "나중에" 를 누르면 그 탭에서는 다시 묻지 않는다
    var later = false;
    try { later = sessionStorage.getItem("gsm.key.later") === "1"; } catch (e) { /* 사생활 모드 */ }
    if (!later && STATIC_KEYS.some(function (k) { return !readKey(k.name); })) openKeyDialog();
    // 넣어 둔 KIGAM 키가 받히는지 한 장 물어 본다. 휴대폰에서는 알림 줄이 접힌 패널 안이라, 안 받히면 키 창을 띄워 까닭을 보인다
    var kigam = readKey("kigam");
    if (kigam) probeKigam(kigam).then(function (result) {
      if (result === "ok") return;
      if (box) {
        var why = document.createElement("span");
        why.className = "key-check";
        box.appendChild(why);
        showVerdict(why, result);
      }
      var shown = document.querySelector("#key-dialog .key-check");
      if (shown) showVerdict(shown, result);
      else openKeyDialog({ verdict: result });
    });
  }

  /** KIGAM 이 이 키로 타일을 주는지 (wetherilli 179) — 한국 한가운데 512 타일 한 장을 화면이 묻는 것과 같은 꼴로 묻는다
   *  (브라우저 캐시가 맞게). `<img>` 는 까닭을 말해 주지 않아, 안 받히면 같은 주소를 `no-cors` fetch 로 한 번 더 묻는다 —
   *  응답이 오면(내용은 못 읽는다) 서버가 키를 거절한 것이고(KIGAM 은 틀린 키에 500 HTML 을 준다), 오지 않으면 망·인증서에서
   *  끊긴 것이다. 결과는 "ok"·"refused"·"unreached" */
  function probeKigam(key) {
    var url = KIGAM_OPENAPI + "?" + new URLSearchParams({
      REQUEST: "GetMap", SERVICE: "WMS", VERSION: "1.3.0", FORMAT: "image/png", STYLES: "", TRANSPARENT: "true",
      LAYERS: "L_50K_Geology_Map", TILED: "true", key: key, WIDTH: "512", HEIGHT: "512", CRS: "EPSG:3857",
      BBOX: "13775786.985667605,4383204.9499851465,14401959.121379768,5009377.08569731",
    });
    return new Promise(function (resolve) {
      var img = new Image();
      var timer = setTimeout(function () { img.onload = img.onerror = null; resolve("unreached"); }, 20000);
      img.onload = function () { clearTimeout(timer); resolve("ok"); };
      img.onerror = function () {
        clearTimeout(timer);
        if (!window.fetch) { resolve("refused"); return; }
        fetch(url, { mode: "no-cors", cache: "no-store", referrerPolicy: "no-referrer" })
          .then(function () { resolve("refused"); }, function () { resolve("unreached"); });
      };
      img.src = url;
    });
  }

  function showVerdict(el, result) {
    el.hidden = false;
    el.classList.add("bad");
    el.textContent = result === "refused"
      ? T("KIGAM 이 이 키로 지질도를 주지 않았다. 키를 다시 붙여 넣어 본다 — 휴대폰에서 손으로 옮겨 적으면 한 글자만 틀려도 안 된다. 키를 받을 때 쓸 곳(IP·주소)을 적었다면 이 기기가 그 밖인지도 본다.")
      : T("KIGAM(data.kigam.re.kr)에 닿지 못했다. 이 망(회사·학교 Wi-Fi, VPN, 광고 차단)이 막거나 기기가 인증서를 받지 않는다 — 다른 망(모바일 데이터)에서 열어 본다.");
  }

  function openKeyDialog(opts) {
    if (opts && opts.type) opts = null;          // 단추에서 불리면 이벤트가 온다
    if (document.getElementById("key-dialog")) return;
    var back = document.createElement("div");
    back.id = "key-dialog";
    back.className = "key-dialog";
    var card = document.createElement("div");
    card.className = "key-card";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "true");
    var head = document.createElement("h2");
    head.textContent = T("인증키 넣기");
    var lead = document.createElement("p");
    lead.innerHTML = T("이 판은 연구소 밖에서 서버 없이 돈다. <b>지질도와 배경지도는 각자 받은 인증키로 본다.</b> 키는 이 브라우저에만 남고 그 키를 준 곳(KIGAM·VWorld)에만 간다.");
    card.append(head, lead);
    var inputs = {};
    STATIC_KEYS.forEach(function (k) {
      var row = document.createElement("label");
      row.className = "key-row";
      var name = document.createElement("span");
      name.className = "key-name";
      name.textContent = T(k.label);
      var hint = document.createElement("small");
      hint.textContent = T(k.what);
      var input = document.createElement("input");
      input.type = "password";
      input.autocomplete = "off";
      input.placeholder = readKey(k.name) ? T("넣어 두었다 — 바꾸려면 새로 적는다") : T("인증키");
      var get = document.createElement("a");
      get.href = k.get;
      get.target = "_blank";
      get.rel = "noopener noreferrer";
      get.textContent = T(k.getLabel);
      row.append(name, hint, input, get);
      card.appendChild(row);
      inputs[k.name] = input;
    });
    var note = document.createElement("p");
    note.className = "key-note";
    note.textContent = T("VWorld 키를 받을 때 서비스 URL 에 이 판의 주소({url})를 적는다.", { url: location.origin });
    var forget = document.createElement("label");
    forget.className = "key-forget";
    var check = document.createElement("input");
    check.type = "checkbox";
    forget.append(check, document.createTextNode(T("이 PC 에 기억하지 않기")));
    var buttons = document.createElement("div");
    buttons.className = "key-buttons";
    var clear = document.createElement("button");
    clear.type = "button";
    clear.className = "btn quiet";
    clear.textContent = T("키 지우기");
    clear.addEventListener("click", function () {
      STATIC_KEYS.forEach(function (k) { writeKey(k.name, "", false); });
      location.reload();
    });
    var later = document.createElement("button");
    later.type = "button";
    later.className = "btn quiet";
    later.textContent = T("나중에");
    later.addEventListener("click", function () {
      try { sessionStorage.setItem("gsm.key.later", "1"); } catch (e) { /* 사생활 모드 */ }
      back.remove();
    });
    var save = document.createElement("button");
    save.type = "button";
    save.className = "btn";
    save.textContent = T("저장");
    var verdict = document.createElement("p");
    verdict.className = "key-check";
    verdict.hidden = true;
    save.addEventListener("click", function () {
      var changed = false;
      var kigam = "";
      STATIC_KEYS.forEach(function (k) {
        // 휴대폰에서 붙여 넣으면 앞뒤 빈칸·줄바꿈·폭 없는 문자가 끼기도 한다 — 키에는 빈칸이 없다 (wetherilli 179)
        var value = inputs[k.name].value.replace(/[\s\u200B-\u200D\uFEFF]+/g, "");
        if (value) { writeKey(k.name, value, !check.checked); changed = true; }
        if (value && k.name === "kigam") kigam = value;
      });
      if (!changed) { back.remove(); return; }
      if (!kigam) { location.reload(); return; }   // 배경·찾기·타일이 처음부터 그 키로 서게
      // KIGAM 키는 다시 열기 전에 한 장 물어 본다 — 안 받히면 까닭을 이 창에 띄우고 머문다
      save.disabled = true;
      verdict.hidden = false;
      verdict.textContent = T("KIGAM 에 키를 물어 보는 중…");
      probeKigam(kigam).then(function (result) {
        if (result === "ok") { location.reload(); return; }
        save.disabled = false;
        save.textContent = T("그래도 연다");
        save.onclick = function () { location.reload(); };
        showVerdict(verdict, result);
      });
    });
    buttons.append(clear, later, save);
    card.append(note, forget, verdict, buttons);
    if (opts && opts.verdict) showVerdict(verdict, opts.verdict);
    back.appendChild(card);
    document.body.appendChild(back);
    var first = STATIC_KEYS.filter(function (k) { return !readKey(k.name); })[0] || STATIC_KEYS[0];
    inputs[first.name].focus();
  }

  function cssEscape(text) {
    return String(text).replace(/["\\]/g, "\\$&");
  }

  initLooks();
  readRegions();
  document.documentElement.setAttribute("data-region", region);
  setEmblem();
  initMap();
  wireBasemap();
  wireCompare();
  renderCatalog();
  renderActive();
  renderPointSets();
  loadPersonal(true);
  document.getElementById("layers-off").addEventListener("click", removeAllLayers);
  wireTools();
  wireSettings();
  wireTabs();
  wireCoordBar();
  wireCrs();
  wireUpload();
  wirePopup();
  wireEmblemMenu();
  wireStaticKey();

  renderRegions();
  applyRegion();
  if (!restoreState()) goHome();
  // 처음 온 지역이면 대표 레이어 하나를 켠다 — 한국은 5만 지질도. 빈 지도보다
  // 무엇이든 보이는 편이 낫고, **5만이 실제로 가장 많이 보는 축척이다.**
  // 기억한 것이 있으면 그것을 따른다 — 다 끄고 떠났으면 다 꺼진 채로 연다.
  if (!active.length && !readJson(stateKey("gsm.layers"))) openFirstLayer();
  // 공유 링크 (wetherilli 189) — 단추와, 링크로 열었다는 띠
  if (window.GSMShare) {
    GSMShare.wire(document.getElementById("tool-share"), shareLink,
                  { done: T("복사했다"), ask: T("이 링크를 복사한다") });
    if (SHARED) GSMShare.notice(T("링크로 연 화면이다 — 여기서 바꾼 것은 이 브라우저에 기억하지 않는다"), T("내 화면으로"));
  }

  // ── 대기 화면 ────────────────────────────────────────────────────
  //
  // **덜 그려진 지도를 보이지 않는다.** 첫 타일이 다 그려질 때
  // (`rendercomplete`) 걷는다. 너무 빨리 걷히면 깜빡이는 것처럼 보여서
  // 적어도 한 바퀴(1.2 초)는 보이고, 상류가 느려 타일이 끝내 안 와도
  // 12 초 뒤에는 걷는다 — 지도 말고 나머지는 쓸 수 있어야 한다.
  (function () {
    var splash = document.getElementById("splash");
    if (!splash) return;
    var shownAt = Date.now();
    var done = false;
    function lift() {
      if (done) return;
      done = true;
      var wait = Math.max(0, 1200 - (Date.now() - shownAt));
      setTimeout(function () {
        splash.classList.add("gone");
        setTimeout(function () { splash.remove(); }, 600);
      }, wait);
    }
    map.once("rendercomplete", lift);
    setTimeout(lift, 12000);
  })();
})();
