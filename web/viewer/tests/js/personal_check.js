// 개인 레이어 읽개(personal.js)의 시험 — test_manage.py 가 node 로 부른다.
// 실패하면 까닭을 찍고 1 로 끝난다.
const assert = require("assert");
const P = require(process.argv[2]);

// 점 — CSV 와 JSON 이 같은 레이어가 된다
const csv = [
  "#format: gsm-personal-layer",
  "#version: 1",
  "#name: 시료, 2026",
  "#label: name",
  "#column: name | 시료 번호 | string",
  "#column: age | 연대 | number | U-Pb",
  "#column: n | 수 | integer",
  "id,lon,lat,name,age,n",
  'S1,127.1,37.5,"쉼표, ""따옴표""",172.4,3',
  "S2,,,빈 좌표,,",
  "S3,128,36, 앞뒤 공백 ,abc,",
].join("\r\n");
const c = P.parse(csv, "a.csv");
assert.strictEqual(c.kind, "point");
assert.strictEqual(c.name, "시료, 2026");
assert.strictEqual(c.count, 3);
assert.strictEqual(c.drawn, 2);
assert.strictEqual(c.meta.version, 1);
assert.deepStrictEqual(c.features[0].properties, { name: '쉼표, "따옴표"', age: 172.4, n: 3 });
assert.strictEqual(c.features[1].geometry, null);
assert.strictEqual(c.features[2].properties.name, " 앞뒤 공백 ");   // 잃지 않는다
assert.strictEqual(c.features[2].properties.age, "abc");            // 숫자가 아니면 글자 그대로
const j = P.parse(JSON.stringify(P.toGeoJSON(Object.assign({}, c))), "a.json");
assert.deepStrictEqual(j.features, c.features);
assert.deepStrictEqual(j.columns, c.columns);
const c2 = P.parse(P.toCSV(Object.assign({}, j)), "b.csv");
assert.deepStrictEqual(c2.features, c.features);

// 면 — WKT 칸이면 면이다
const poly = P.parse("geometry,name\r\n\"POLYGON ((0 0, 1 0, 1 1, 0 0))\",A\r\n", "p.csv");
assert.strictEqual(poly.kind, "polygon");
assert.strictEqual(poly.warnings.length, 0);
const mp = P.parseWKT("MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((5 5, 6 5, 6 6, 5 5)))");
assert.deepStrictEqual(P.parseWKT(P.wkt(mp)), mp);

// 섞여 오면 모양마다 가른다 (wetherilli 126) — 좌표 없는 행은 맨 앞 갈래에
const mixed = P.parse(JSON.stringify({ type: "FeatureCollection", features: [
  { type: "Feature", id: 1, geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }, properties: {} },
  { type: "Feature", id: 2, geometry: { type: "Point", coordinates: [1, 2] }, properties: {} },
  { type: "Feature", id: 3, geometry: { type: "LineString", coordinates: [[0, 0], [1, 1]] }, properties: {} },
  { type: "Feature", id: 4, geometry: null, properties: {} },
  { type: "Feature", id: 5, geometry: { type: "Point", coordinates: [3, 4] }, properties: {} },
] }), "m.json");
assert.strictEqual(mixed.kind, "mixed");
assert.deepStrictEqual(mixed.kinds, { polygon: 1, point: 2, line: 1 });
const parts = P.split(mixed);
assert.deepStrictEqual(parts.map(x => x.kind), ["point", "line", "polygon"]);
assert.deepStrictEqual(parts[0].features.map(f => f.id), [2, 4, 5]);
assert.strictEqual(parts[0].drawn, 2);
assert.strictEqual(parts.reduce((n, x) => n + x.count, 0), 5);       // 잃지 않는다
// 연결 기록은 제 모양의 갈래만 받는다
const lineRec = { name: "선", linkPart: "line", link: { url: "https://a/x" } };
P.applyFetched(lineRec, { parsed: mixed, via: "server" });
assert.deepStrictEqual(lineRec.features.map(f => f.id), [3]);
// 연결 묶기
const groups = P.linkGroups([{ id: "a", link: {}, linkGroup: "g" }, { id: "b" }, { id: "c", link: {}, linkGroup: "g" }, { id: "d", link: {} }]);
assert.deepStrictEqual(groups.map(g => g.map(r => r.id)), [["a", "c"], ["d"]]);
// 좌표 칸이 없으면 받지 않는다
assert.throws(() => P.parse("a,b\r\n1,2\r\n", "x.csv"), /좌표 칸이 없다/);
// 범위 밖 좌표는 그 행만 문제로 남긴다
const far = P.parse("lon,lat,k\r\n127,37,a\r\n500,37,b\r\n", "f.csv");
assert.strictEqual(far.drawn, 1);
assert.strictEqual(far.problems.length, 1);
// 별명 좌표 칸은 읽되 경고한다
assert.strictEqual(P.parse("경도,위도\r\n127,37\r\n", "k.csv").warnings.length, 1);
// 선을 받는다 — JSON·WKT 둘 다, 되쓰기도
const line = P.parse(JSON.stringify({ type: "FeatureCollection", features: [
  { type: "Feature", geometry: { type: "LineString", coordinates: [[0, 0], [1, 1]] }, properties: { k: "a" } }] }), "l.json");
assert.strictEqual(line.kind, "line");
const ml = P.parseWKT("MULTILINESTRING ((0 0, 1 1), (2 2, 3 3))");
assert.deepStrictEqual(P.parseWKT(P.wkt(ml)), ml);
assert.strictEqual(P.parse(P.toCSV(Object.assign({}, line)), "l.csv").features[0].geometry.type, "LineString");
// 그 밖의 모양은 받지 않는다
assert.throws(() => P.parse(JSON.stringify({ type: "FeatureCollection", features: [
  { type: "Feature", geometry: { type: "GeometryCollection", geometries: [] }, properties: {} }] }), "g.json"), /그릴 좌표/);
// EUC-KR 로 저장한 CSV 도 읽는다 (엑셀)
const euckr = Buffer.from([0xc0, 0xa7, 0xb5, 0xb5]);   // "위도"
assert.strictEqual(P.decode(euckr).text, "위도");
// 연결 (P09·122) — 주소와 인증 방식을 거른다
assert.deepStrictEqual(P.checkLink({ url: " https://a.example/x.json ", auth: { mode: "none" } }),
  { url: "https://a.example/x.json", auth: { mode: "none", name: "", key: "" } });
assert.throws(() => P.checkLink({ url: "ftp://a/x", auth: { mode: "none" } }), /http/);
assert.throws(() => P.checkLink({ url: "nope", auth: { mode: "none" } }), /주소/);
assert.throws(() => P.checkLink({ url: "https://a/x", auth: { mode: "header", key: "k" } }), /이름/);
assert.throws(() => P.checkLink({ url: "https://a/x", auth: { mode: "bearer" } }), /비었다/);
// 받은 것을 덮어도 사람이 고친 이름·색은 둔다
const rec = { name: "내 이름", color: "#123456", link: { url: "https://a/x" } };
P.applyFetched(rec, { parsed: c, via: "server" });
assert.strictEqual(rec.name, "내 이름");
assert.strictEqual(rec.color, "#123456");
assert.strictEqual(rec.count, 3);
assert.strictEqual(rec.status.via, "server");
// 내려받기에 키가 실리지 않는다
const withKey = Object.assign({}, c, { link: { url: "https://a/x", auth: { mode: "bearer", key: "SECRET" } } });
assert.ok(!JSON.stringify(P.toGeoJSON(withKey)).includes("SECRET"));
assert.ok(!P.toCSV(withKey).includes("SECRET"));
// API 의 목차에서 자료 주소를 고른다 (wetherilli 129) — 같은 호스트, 자리표 없는 url 만
const index = JSON.stringify({ api_version: "1", endpoints: {
  sites: { url: "https://kofhin.psok.or.kr/fsis/api/v1/sites/", method: "GET" },
  site_detail: { url_template: "https://kofhin.psok.or.kr/fsis/api/v1/sites/{id}/" },
  other: { url: "https://evil.example/steal" },
  tmpl: { url: "https://kofhin.psok.or.kr/fsis/api/v1/sites/{id}/" } } });
assert.deepStrictEqual(P.endpointsOf(index, "https://kofhin.psok.or.kr/fsis/api/v1/"),
  ["https://kofhin.psok.or.kr/fsis/api/v1/sites/"]);
assert.deepStrictEqual(P.endpointsOf("not json", "https://a/"), []);
// 피처 하나도 받는다 — 상세 주소
const one = P.parse(JSON.stringify({ type: "Feature", id: 54, geometry: { type: "Point", coordinates: [128, 36] }, properties: { name: "x" } }), "a.json");
assert.strictEqual(one.count, 1);
assert.strictEqual(one.kind, "point");
console.log("ok");
