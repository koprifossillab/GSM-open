// 소개 화면(`/GSM/`)의 그림을 운영 화면에서 찍는다 (wetherilli 113). intro_shots.sh 가 부른다.
//
//   node intro_shots.js <지도 주소> <뿌리 주소> <ko|en> <PNG 를 둘 곳> [장면 이름…]
//
// 지도는 브라우저 저장소(`gsm.region`·`gsm.view.<지역>`·`gsm.layers.<지역>`)로 자리와 켠 레이어를
// 되살린다 — 그것을 미리 넣고 연다. 3D·달·화성·온 지구는 주소로 연다. 언어는 쿠키(`gsm_lang`)다.
//
// **배경은 비상업·제3자 조건이 붙은 것(EOX Sentinel-2·Esri 남극 위성)을 쓰지 않는다** (040) —
// 이 그림은 저장소에 담겨 밖으로 나간다.
const path = require('path');
const { chromium } = require(process.env.PW_CORE || 'playwright-core');

const [MAP, ROOT, LANG, OUT] = process.argv.slice(2, 6);
const ONLY = process.argv.slice(6);
const W = 1600, H = 1000;

const view = (lon, lat, zoom, proj) => JSON.stringify({ lon, lat, zoom, proj });
const layers = (...names) => JSON.stringify(names.map(n => ({ name: n, opacity: 1 })));

/** 지역 화면 하나 — 저장소를 채우고 연다. */
function region(key, v, ls, extra = {}) {
  const sfx = key === 'korea' ? '' : '.' + key;
  const store = {
    'gsm.regions': JSON.stringify(['japan', 'eastasia', 'antarctica', 'greenland', 'svalbard', 'jan_mayen']),
    'gsm.region': key,
    ['gsm.view' + sfx]: v,
    ['gsm.layers' + sfx]: ls,
  };
  if (extra.basemap) store['gsm.basemap' + sfx] = extra.basemap;
  return { url: MAP, store, ...extra };
}

/** 지도 위를 눌러 선·면을 긋는다. 마지막 점은 두 번 눌러 끝낸다. */
async function draw(p, mode, pts) {
  const box = await p.locator('#map').boundingBox();
  await p.click(`.tool[data-mode="${mode}"]`);
  for (let i = 0; i < pts.length; i++) {
    const x = box.x + box.width * pts[i][0], y = box.y + box.height * pts[i][1];
    if (i === pts.length - 1 && mode !== 'point') await p.mouse.dblclick(x, y); else await p.mouse.click(x, y);
    await p.waitForTimeout(450);
  }
}

const SHOTS = {
  // 남극 — GeoMAP 지질도 위에 극지연구소 암석 시료의 자리. 대륙 하나, 빅토리아랜드(장보고기지 둘레) 하나
  antarctica: region('antarctica', view(165, -77, 2.2, 'EPSG:3031'),
    layers('kopri:rock_antarctica', 'geomap_simple_geology'), { basemap: 'rema' }),
  antarctica_close: region('antarctica', view(163.5, -74.6, 6.2, 'EPSG:3031'),
    layers('kopri:rock_antarctica', 'geomap_simple_geology'), { basemap: 'rema' }),
  // 그린란드 — 서해안은 편마암이라 GEUS 50만이 성기다. 퇴적분지가 있는 동해안(스코스비순)을 본다
  greenland: region('greenland', view(-25, 72.5, 5.0, 'EPSG:3413'),
    layers('kopri:rock_greenland', 'grl_g500_lithostr_search'), { basemap: 'arcticdem', wait: 15000 }),
  svalbard: region('svalbard', view(15.5, 78.6, 6.6, 'EPSG:3413'),
    layers('kopri:rock_svalbard', 'npolar:svalbard_units', 'npolar:svalbard_faults'), { basemap: 'npi_sat' }),
  // 남극 더 — 드로닝모드랜드(NPI 1:25만), 빙저 지형(IBCSO) 위의 기지·운석 발견 지점 (wetherilli 115)
  antarctica_dml: region('antarctica', view(6, -72.2, 5.2, 'EPSG:3031'),
    layers('npolar:dml_structures', 'npolar:dml_units'), { basemap: 'rema' }),
  antarctica_ibcso: region('antarctica', view(0, -90, 1.6, 'EPSG:3031'),
    layers('kopri:stations', 'kopri:meteorites'), { basemap: 'ibcso_bed' }),
  // 그린란드 더 — 하천 퇴적물 지화학(남·서), 정부 포털의 연대측정 지점
  greenland_geochem: region('greenland', view(-47, 64, 4.6, 'EPSG:3413'),
    layers('geochemistry_greenland_ss_sw'), { basemap: 'arcticdem', wait: 15000 }),
  greenland_portal: region('greenland', view(-40, 72, 3.4, 'EPSG:3413'),
    layers('grportal:geochron', 'grl_g500_lithostr_search'), { basemap: 'arcticdem', wait: 15000 }),
  // 스발바르 더 — 종이 지질도(음영), 다산기지가 있는 뉘올레순의 빙하 전면 변화, 그리고 얀마옌
  svalbard_paper: region('svalbard', view(15.6, 78.2, 8.6, 'EPSG:3413'),
    layers('npolar:svalbard_paper'), { basemap: 'npi_sat' }),
  svalbard_glacier: region('svalbard', view(12.2, 78.92, 9.6, 'EPSG:3413'),
    layers('npolar:svalbard_glacier_fronts'), { basemap: 'npi_sat' }),
  jan_mayen: region('jan_mayen', view(-8.4, 71.0, 9.4, 'EPSG:3413'),
    layers('janmayen:vents', 'janmayen:lines', 'janmayen:units'), { basemap: 'arcticdem' }),
  // 한국 더 — KIGAM 지화학도(구리)·해저지질도(표층퇴적물), 그리고 한국·일본을 한 화면에(동아시아)
  korea_geochem: region('korea', view(127.8, 36.2, 7.4, 'EPSG:3857'), layers('L_geochemMP_CU'), { basemap: 'vworld_white' }),
  korea_marine: region('korea', view(127.0, 35.2, 7.2, 'EPSG:3857'), layers('M_geology_deposits_type'), { basemap: 'vworld' }),
  eastasia: region('eastasia', view(129.9, 34.6, 7.6, 'EPSG:3857'),
    layers('gsj:geology', 'L_250K_Geology_Map'), { basemap: 'vworld' }),
  // 계측 — 점을 찍고 거리를 재면 높이 그래프가 뜬다
  measure: region('korea', view(128.45, 38.12, 12.2, 'EPSG:3857'), layers('L_50K_Geology_Map'), {
    basemap: 'vworld',
    act: async (p) => {
      await draw(p, 'point', [[.30, .30], [.78, .70]]);
      await draw(p, 'line', [[.25, .62], [.48, .40], [.70, .30]]);
      await p.waitForTimeout(6000);
    },
  }),
  // 넓이를 두르고 그림으로 내려받는다 — 화면 한 장, 내려받은 PNG 한 장
  exported: region('korea', view(128.47, 38.13, 11.6, 'EPSG:3857'), layers('L_50K_Geology_Map'), {
    basemap: 'vworld',
    act: async (p) => {
      await draw(p, 'area', [[.35, .30], [.62, .26], [.70, .58], [.40, .66]]);
      await p.waitForTimeout(2000);
      const dl = p.waitForEvent('download', { timeout: 60000 });
      await p.click('#tool-export');
      await (await dl).saveAs(path.join(OUT, 'exported_file.png'));
    },
  }),
  // 출처 셋 — 같은 자리(설악산)의 KIGAM 과 VWorld, 그리고 일본(후지산)
  src_kigam: region('korea', view(128.45, 38.12, 11.4, 'EPSG:3857'), layers('L_50K_Geology_Map'), { basemap: 'vworld' }),
  src_vworld: region('korea', view(128.45, 38.12, 11.4, 'EPSG:3857'),
    layers('lt_l_gimsfault', 'lt_c_gimshydro'), { basemap: 'vworld_hybrid' }),
  src_gsj: region('japan', view(138.73, 35.36, 10.4, 'EPSG:3857'), layers('gsj:geology'), { basemap: 'gsi_pale' }),
  // 3D·달·화성·온 지구 — 주소로 연다. WebGL 이 소프트웨어로 돌아 오래 기다린다
  korea3d_wide: { url: ROOT + '3d/?lat=37.9&lon=128.3&z=10.6&region=korea&layer=L_250K_Geology_Map', wait: 20000 },
  korea3d: { url: ROOT + '3d/?lat=38.119&lon=128.465&z=13.2&region=korea&layer=L_50K_Geology_Map', wait: 20000 },
  svalbard3d: { url: ROOT + '3d/?lat=78.92&lon=12.3&z=10.4&region=svalbard&layer=npolar:svalbard_units', wait: 20000 },
  moon: { url: ROOT + 'moon/', wait: 25000 },
  mars: { url: ROOT + 'mars/', wait: 25000 },
  // 수성 — 지질도(마리너 10 이 찍은 서쪽 반구)가 보이게 서경 100° 쪽에서 연다 (wetherilli 146)
  mercury: { url: ROOT + 'mercury/', wait: 25000,
             store: { 'gsm.mercury.view': JSON.stringify({ lon: -100, lat: 5, h: 7200000, heading: 0, pitch: -1.5708 }) } },
  earth: { url: ROOT + 'earth/', wait: 25000 },
};

(async () => {
  const b = await chromium.launch({
    executablePath: process.env.PW_CHROME || undefined,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  const host = new URL(ROOT).hostname;
  for (const [name, s] of Object.entries(SHOTS)) {
    if (ONLY.length && !ONLY.includes(name)) continue;
    // 사내망이 HTTPS 를 다시 서명한다 — 묶어 온 chromium 은 그 인증서를 모른다. 찍을 때만 넘긴다
    const ctx = await b.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, ignoreHTTPSErrors: true,
                                     locale: LANG === 'en' ? 'en-GB' : 'ko-KR' });
    await ctx.addCookies([{ name: 'gsm_lang', value: LANG, domain: host, path: '/' }]);
    if (s.store) {
      await ctx.addInitScript(store => {
        if (sessionStorage.getItem('__seeded')) return;
        localStorage.clear();
        for (const [k, v] of Object.entries(store)) localStorage.setItem(k, v);
        sessionStorage.setItem('__seeded', '1');
      }, s.store);
    }
    const p = await ctx.newPage();
    p.on('pageerror', e => console.log('  [pageerror]', name, e.message));
    const t0 = Date.now();
    try { await p.goto(s.url, { waitUntil: 'networkidle', timeout: 90000 }); }
    catch (e) { console.log('  [goto]', name, e.message.split('\n')[0]); }
    await p.waitForTimeout(s.wait || 5000);
    if (s.act) await s.act(p);
    try { await p.waitForLoadState('networkidle', { timeout: 30000 }); } catch (e) { /* 계속 오는 것이 있으면 그냥 찍는다 */ }
    await p.waitForTimeout(1500);
    await p.screenshot({ path: path.join(OUT, name + '.png') });
    console.log(`  ${LANG} ${name} ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    await ctx.close();
  }
  await b.close();
})();
