# 담아 둔 것

**OpenLayers 9.2.4** — `ol.js`, `ol.css` (BSD-2-Clause, `ol.LICENSE.md` 동봉 — 2026-10-05 에 `https://cdn.jsdelivr.net/npm/ol@9.2.4/LICENSE.md` 에서, wetherilli 348)

CDN 에서 불러오지 않고 저장소에 담는 까닭은 둘이다.

1. **KOPRI 망이 TLS 를 가로챈다.** 체인 끝이 `CN=KOPRI SSL` 이라, 그 루트를
   안 가진 프로그램은 바깥 CDN 을 못 읽는다. 브라우저는 대개 루트가 깔려 있어
   되지만, 되고 안 되고가 그 컴퓨터의 설정에 달리는 것을 제품에 두지 않는다
2. **형제 저장소(DiaRUGA·ForGIA)에 바깥 링크가 하나도 없다.** 같은 집 규칙이다

받은 자리와 확인값:

```
https://cdn.jsdelivr.net/npm/ol@9.2.4/dist/ol.js
https://cdn.jsdelivr.net/npm/ol@9.2.4/ol.css
```

판을 올릴 때는 두 파일을 같이 받고 이 문서의 판 번호를 고친다.
118c329cf58d41122a4097f9a8abe5f52b56eb80cfc7df83c5ccef8d7b976fbe  ol.js
b46a588ec4f9db4f824ea15ab2b78bd9d1dfb17172a785c69e23fa8953db437f  ol.css

**MapLibre GL JS 4.7.1** — `maplibre/` (BSD-3, `LICENSE.txt` 동봉). 3D 실험
화면(`/GSM/3d/`)만 쓴다 (devlog 015).

```
https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js
https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css
```

**proj4js 2.22.0** — `proj4.js` (MIT, `proj4.LICENSE.md` 동봉). 극지 화면의
평사도법(EPSG:3413·3031)을 OpenLayers 에 알린다 (devlog 017). `ol.js` 뒤,
`map.js` 앞에 싣는다.

```
https://cdn.jsdelivr.net/npm/proj4@2.22.0/dist/proj4.js
https://cdn.jsdelivr.net/npm/proj4@2.22.0/LICENSE.md
```
af7df653d91ea591f33d26fb958990bbd3071b2db644a4edaba441cc9861a474  proj4.js

**글꼴 조각 — Noto Sans Regular 0–511** — `maplibre/glyphs/` (SIL OFL 1.1, `glyphs/LICENSE.txt`).
3D 화면의 점묶음 이름표가 로마자·숫자를 그리는 데 쓴다(P02 §7). 한글·한자는 조각 없이
브라우저 글꼴이 그린다(`localIdeographFontFamily`). OpenMapTiles 가 미리 구운 것이다.

```
https://raw.githubusercontent.com/openmaptiles/fonts/gh-pages/Klokantech%20Noto%20Sans%20Regular/0-255.pbf
https://raw.githubusercontent.com/openmaptiles/fonts/gh-pages/Klokantech%20Noto%20Sans%20Regular/256-511.pbf
https://raw.githubusercontent.com/openmaptiles/fonts/master/noto-sans/LICENSE
```
2b5324d3fcaa58f93c71d4e6ee70eba532f15585401d764daf99efc427a62693  0-255.pbf
052e7e11d0420e7a6772478413f5d2bb910d150f76830bdf17dfabcabe87aaf1  256-511.pbf

**CesiumJS 1.145.0** — `cesium/` (Apache-2.0, `LICENSE.md` 동봉). 달 시험 화면(`/GSM/moon/`)만
쓴다 (P05). 달 타원체(`Ellipsoid.MOON`)를 갖고 극까지 온전한 구를 그린다. npm 묶음의
`Build/Cesium/` 에서 `Cesium.js`·`Workers/`·`ThirdParty/`·`Assets/`·`Widgets/` 만 담았다 (14 MB,
`index.js`·`index.cjs` 는 뺐다). 템플릿이 `window.CESIUM_BASE_URL` 을 이 자리로 알린다.

```
https://registry.npmjs.org/cesium/-/cesium-1.145.0.tgz
```
dbb7a1606ef2150c7266eee6eb10bfeba1bd1351cdce1df85787a45491f482e3  cesium/Cesium.js
