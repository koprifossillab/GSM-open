// 공개 예시(docs/personal_layer/examples)가 관리 화면의 읽개로 경고 없이 읽히는지 — test_manage.py 가 node 로 부른다 (wetherilli 399).
// AI 가 이 예시를 보고 양식을 배운다 — 예시가 깨지면 배운 것도 깨진다
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const P = require(process.argv[2]);
const dir = process.argv[3];

const want = { "field_samples.geojson": "point", "field_samples.csv": "point",
               "traverse.geojson": "line", "survey_areas.csv": "polygon" };
const got = {};
for (const name of fs.readdirSync(dir).sort()) {
  assert.ok(name in want, name + " — 예시를 더했으면 여기에도 적는다");
  const r = P.parse(fs.readFileSync(path.join(dir, name), "utf8"), name);
  assert.strictEqual(r.kind, want[name], name);
  assert.deepStrictEqual(r.warnings, [], name + " 의 경고");
  assert.deepStrictEqual(r.problems, [], name + " 의 읽지 못한 줄");
  assert.strictEqual(r.meta.format, "gsm-personal-layer", name);
  assert.ok(r.drawn > 0, name + " — 지도에 뜨는 것이 없다");
  got[name] = r;
}
// 같은 자료를 두 꼴로 적은 것은 같은 레이어가 된다
assert.deepStrictEqual(got["field_samples.csv"].features, got["field_samples.geojson"].features);
assert.deepStrictEqual(got["field_samples.csv"].columns, got["field_samples.geojson"].columns);
assert.strictEqual(got["field_samples.csv"].name, got["field_samples.geojson"].name);
console.log("ok");
