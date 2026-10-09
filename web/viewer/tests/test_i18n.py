"""영어판.

**문장을 새로 적으면 번역표에도 적는다** (CLAUDE.md "영어판"). 그 약속을
사람의 기억에 맡기지 않으려고 여기서 코드를 긁어 대조한다 — JS 의
`T("…")`, 템플릿의 `{% t "…" %}`, 파이썬의 `msg("…")`.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from viewer import i18n

HERE = Path(__file__).resolve().parent.parent
KOREAN = re.compile(r"[가-힣]")


def used_keys():
    js = "".join((HERE / "static/viewer" / n).read_text(encoding="utf-8")
                 for n in ("map.js", "map3d.js", "moon.js", "mars.js", "mercury.js", "earth.js", "personal.js", "manage.js", "offline.js"))
    html = "".join((HERE / "templates/viewer" / n).read_text(encoding="utf-8")
                   for n in ("map.html", "map3d.html", "moon.html", "mars.html", "mercury.html", "earth.html", "intro.html", "manage.html"))
    keys = set(re.findall(r'\bT\("((?:[^"\\]|\\.)*)"', js))
    keys |= set(re.findall(r'\{% t "((?:[^"\\]|\\.)*)"(?: [^%]*)? %\}', html))      # 자리표 값이 붙은 꼴도 (wetherilli 314)
    for name in ("views.py", "pointsets.py", "linked.py"):
        src = (HERE / name).read_text(encoding="utf-8")
        # msg("…") 는 여러 줄로 이어 붙일 수 있다 — "a" "b" 를 하나로 합친다
        for call in re.findall(r'\bmsg\(\s*((?:"(?:[^"\\]|\\.)*"\s*)+)', src):
            keys.add("".join(re.findall(r'"((?:[^"\\]|\\.)*)"', call)))
    return {k for k in keys if KOREAN.search(k)}


class Coverage(SimpleTestCase):
    def test_화면에_쓰는_문장은_모두_번역표에_있다(self):
        missing = sorted(used_keys() - set(i18n.EN))
        self.assertEqual(missing, [], "i18n.EN 에 영어를 적는다:\n" + "\n".join(missing))

    def test_긁어내기가_실제로_문장을_찾는다(self):
        """긁는 정규식이 깨지면 위 시험이 늘 통과한다. 그것을 막는다."""
        keys = used_keys()
        self.assertGreater(len(keys), 150)
        self.assertIn("점 {n}개", keys)                           # JS
        self.assertIn("레이어 고르기", keys)                       # 템플릿
        self.assertIn("{line}째 줄 — 좌표를 읽지 못해 건너뛰었다", keys)  # 파이썬

    def test_씨앗의_레이어는_모두_영어_제목이_있다(self):
        """카탈로그는 영어판에서 레이어 **이름**으로 `LAYER_EN` 을 찾는다(`views._catalog`). 지역 탭의 화석·화산 열둘이 제목으로만
        적혀 영어판에 한국어가 떴다 (wetherilli 203). `manage.py i18n_missing` 은 DB 가 있어야 돌아 씨앗 파일을 곧장 본다"""
        import json
        missing = []
        for path in sorted((HERE.parent.parent / "data").glob("*_layers.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for row in data.get("레이어", []) if isinstance(data, dict) else []:
                if KOREAN.search(row.get("title", "")) and row["name"] not in i18n.LAYER_EN:
                    missing.append(f"{path.name}: {row['name']}")
        self.assertEqual(missing, [], "i18n.LAYER_EN 에 영어 제목을 적는다:\n" + "\n".join(missing))

    def test_씨앗의_한국어_설명은_모두_영어가_있다(self):
        """레이어 설명에 한국어가 들면 `ABSTRACT_EN` 에 영어를 적는다 — 없으면 영어판에서 숨는다 (wetherilli 333)"""
        import json
        missing = []
        for path in sorted((HERE.parent.parent / "data").glob("*_layers.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for row in data.get("레이어", []) if isinstance(data, dict) else []:
                if KOREAN.search(row.get("abstract", "")) and row["name"] not in i18n.ABSTRACT_EN:
                    missing.append(f"{path.name}: {row['name']}")
        self.assertEqual(missing, [], "i18n.ABSTRACT_EN 에 영어 설명을 적는다:\n" + "\n".join(missing))
        self.assertFalse([k for k, v in i18n.ABSTRACT_EN.items() if KOREAN.search(v)], "영어 설명에 한글이 남았다")

    def test_자리표가_짝이_맞는다(self):
        for ko, en in i18n.EN.items():
            self.assertEqual(sorted(re.findall(r"\{(\w+)\}", ko)),
                             sorted(re.findall(r"\{(\w+)\}", en)), ko)

    def test_영어에_한글이_새지_않는다(self):
        """열 이름 안내(`위도`·`경도`·`X좌표`)처럼 사람이 한글 그대로 적어야
        하는 것만 빼고."""
        allowed = ("<code>위도</code>", "<code>경도</code>", "X좌표·Y좌표")
        for ko, en in i18n.EN.items():
            stripped = en
            for a in allowed:
                stripped = stripped.replace(a, "")
            self.assertIsNone(KOREAN.search(stripped), ko)


class Translate(SimpleTestCase):
    def test_한국어판은_그대로(self):
        self.assertEqual(i18n.t("레이어", "ko"), "레이어")

    def test_영어판은_표를_찾는다(self):
        self.assertEqual(i18n.t("레이어", "en"), "Layers")

    def test_표에_없으면_한국어로_남는다(self):
        self.assertEqual(i18n.t("없는 문장", "en"), "없는 문장")

    def test_Msg_는_한국어_문자열이면서_원문_틀을_든다(self):
        m = i18n.msg("…모두 {n}줄을 건너뛰었다", n=3)
        self.assertEqual(m, "…모두 3줄을 건너뛰었다")
        self.assertEqual(i18n.t(m, "en"), "…3 rows skipped in all")


class Age(SimpleTestCase):
    """상류가 실제로 준 값들이다 (25만·5만·100만 지질도, 2026-09-27)."""

    CASES = {
        "신생대 제4기": "Cenozoic Quaternary",
        "선캄브리아시대": "Precambrian",
        "현생누대 고생대 석탄기~페름기": "Phanerozoic Paleozoic Carboniferous – Permian",
        "현생누대 중생대 트라이아스기 후기~쥐라기 전기":
            "Phanerozoic Mesozoic Late Triassic – Early Jurassic",
        "선캄브리아시대 원생누대 고원생대 스타테로스기":
            "Precambrian Proterozoic Paleoproterozoic Statherian",
        "선캄브리아시대 원생누대 중원생대 엑타시스기~스테노스기":
            "Precambrian Proterozoic Mesoproterozoic Ectasian – Stenian",
        "신생대 신진기~고진기": "Cenozoic Neogene – Paleogene",
        "현생누대 신생대 제4기 홀로세": "Phanerozoic Cenozoic Quaternary Holocene",
        # 100만 지질도의 옛 표기
        "고생대 데본기-오오도비스기": "Paleozoic Devonian – Ordovician",
        "중생대 쥬라기-트라이아스기": "Mesozoic Jurassic – Triassic",
        "신생대 고제3기": "Cenozoic Paleogene",
        "원생대 후기-전기": "Late Proterozoic – Early Proterozoic",
        "시생대": "Archean",
        "미분류": "Unclassified",
        "시대 미상": "Age unknown",
        "중생대 시대미상": "Mesozoic Age unknown",
        # 지체구조도
        "시생대-원생대": "Archean – Proterozoic",
        "고생대화성활동": "Paleozoic igneous activity",
        "Nodata": "Nodata",
    }

    def test_상류의_값을_옮긴다(self):
        for ko, en in self.CASES.items():
            self.assertEqual(i18n.age_en(ko), en, ko)

    def test_모르는_낱말이_있으면_통째로_둔다(self):
        self.assertEqual(i18n.age_en("중생대 무슨기"), "중생대 무슨기")

    def test_빈_값은_그대로(self):
        self.assertEqual(i18n.age_en(""), "")

    def test_도폭_링크_이름표도_옮긴다(self):
        got = i18n.props_en({"도폭": {"text": "유성[1977]", "links": [
            {"label": "(원도)", "url": "https://x/a.pdf"}]}})
        self.assertEqual(got["Map sheet"]["links"][0]["label"], "(original map)")
        self.assertEqual(got["Map sheet"]["text"], "유성[1977]")

    def test_속성은_이름과_지질시대만_옮긴다(self):
        got = i18n.props_en({"지질시대": "중생대 백악기", "지층명": "경상누층군", "symnum": "1"})
        self.assertEqual(got, {"Geologic age": "Mesozoic Cretaceous",
                               "Formation": "경상누층군", "symnum": "1"})


    def test_영어_짝이_있으면_제자리에_올리고_원문은_곁에(self):
        got = i18n.props_en({"지층명": "경상누층군", "영문지층명": "Gyeongsang Supergroup",
                             "지질시대": "중생대"})
        self.assertEqual(list(got), ["Formation", "Formation (Korean)", "Geologic age"])
        self.assertEqual(got["Formation"], "Gyeongsang Supergroup")
        self.assertEqual(got["Formation (Korean)"], "경상누층군")

    def test_영어_짝이_비었으면_그대로(self):
        got = i18n.props_en({"지층명": "경상누층군", "영문지층명": " "})
        self.assertEqual(got["Formation"], "경상누층군")
        self.assertIn("Formation (English)", got)

    def test_지체구조운동은_닫힌_낱말이라_옮긴다(self):
        got = i18n.props_en({"지체구조운동": "구조동시성 대륙내 열곡", "지체구조구": "경기육괴"})
        self.assertEqual(got["Tectonic event"], "Syntectonic intracontinental rift")
        self.assertEqual(got["Tectonic province"], "경기육괴")


class LangOf(SimpleTestCase):
    def req(self, cookie=None, accept=""):
        from django.test import RequestFactory
        r = RequestFactory().get("/", HTTP_ACCEPT_LANGUAGE=accept)
        if cookie:
            r.COOKIES["gsm_lang"] = cookie
        return r

    def test_쿠키가_먼저다(self):
        self.assertEqual(i18n.lang_of(self.req("en", "ko-KR")), "en")
        self.assertEqual(i18n.lang_of(self.req("ko", "en-US")), "ko")

    def test_한국어를_안_받는_브라우저는_영어로_연다(self):
        self.assertEqual(i18n.lang_of(self.req(accept="en-US,en;q=0.9")), "en")

    def test_한국어를_받으면_한국어(self):
        self.assertEqual(i18n.lang_of(self.req(accept="en-US,ko;q=0.8")), "ko")

    def test_이상한_쿠키는_버린다(self):
        self.assertEqual(i18n.lang_of(self.req("fr", "ko")), "ko")

    def test_아무것도_없으면_한국어(self):
        self.assertEqual(i18n.lang_of(self.req()), "ko")


class Page(TestCase):
    fixtures = []

    def get(self, lang):
        self.client.cookies["gsm_lang"] = lang
        return self.client.get("/GSM/map/").content.decode("utf-8")

    def test_영어판_화면(self):
        html = self.get("en")
        # 번역표 JSON 에는 한국어 열쇠가 있으므로 그 앞까지만 본다
        html = html.split('<script id="i18n-data"')[0]
        self.assertIn('<html lang="en">', html)
        self.assertIn("<title>Great Stone Map</title>", html)
        self.assertIn("Choose layers", html)
        self.assertNotIn("레이어 고르기", html)

    def test_한국어판은_번역표를_싣지_않는다(self):
        html = self.get("ko")
        self.assertIn('<html lang="ko">', html)
        self.assertIn('<script id="i18n-data" type="application/json">{}</script>', html)

    def test_업로드_오류도_영어로(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.cookies["gsm_lang"] = "en"
        f = SimpleUploadedFile("a.csv", "a,b\n1,2\n".encode("utf-8"))
        got = self.client.post("/GSM/pointsets/upload/", {"file": f}).json()
        self.assertTrue(got["error"].startswith("No coordinate columns found."), got)
