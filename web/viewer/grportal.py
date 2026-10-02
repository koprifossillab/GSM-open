"""그린란드 정부의 광물자원 포털(ArcGIS)로 나가는 문 — 시료·연대·광물 산출지.

`kigam.py`·`vworld.py`·`geus.py` 와 나란한 **네 번째 문**이다 (CLAUDE.md
"상류마다 문이 하나"). 이 상류의 레이어는 여기로만 나간다.

- 주소: `services5.arcgis.com/wbN76kmEQ2ue8VQm/arcgis/rest/services/<서비스>/FeatureServer/0`
  그린란드 정부(광물자원청, 계정 `emni_nanoq`)가 올린 공개 FeatureServer 다.
  Asiaq 가 차린 웹지도 "Online Map Geological data from Greenland" 가 이것들을
  얹어 보인다. 값의 뿌리는 GEUS 자료다(`data.geus.dk` 링크가 딸려 온다)
- **타일이 아니라 점을 받는다.** 레이어 하나가 수백~2 만 점이라 통째로 받아
  한 덩이의 GeoJSON 으로 브라우저에 준다. 브라우저가 그리고, 누르면 그
  자리에서 속성을 읽는다 — 상류에 한 번 더 묻지 않는다
- 한 번에 2 000 점까지 준다(`maxRecordCount`). `resultOffset` 으로 넘기며 받고,
  한 장과 한 장 사이에 **쉰다** — 2 만 점이 열 번이다
- 이용 조건은 항목에 적혀 있지 않다(`licenseInfo` 가 비어 있다). 웹지도의
  한 줄 소개가 "Free Geological Data for Greenland" 다. devlog 019
"""
import json
import logging

import requests
from django.conf import settings

from . import arcpoints, usage

log = logging.getLogger(__name__)

#: 한 번에 받는 점의 수. 상류의 `maxRecordCount` 와 같다.
PAGE = 2000
#: 한 레이어에서 넘기는 장의 한계. 상류가 끝을 알려주지 않고 돌기만 할 때를 막는다.
MAX_PAGES = 40
#: 장과 장 사이에 쉬는 초. 한 레이어를 받는 동안 브라우저가 기다리므로
#: 너무 길게는 못 둔다 — 2 만 점이면 열 장, 쉬는 것만 5 초다.
PAUSE = 0.5
#: 좌표를 이 자리까지만 둔다 (`arcpoints.DIGITS`).
DIGITS = arcpoints.DIGITS


class PortalError(RuntimeError):
    pass


_field = arcpoints.field

#: 다이아몬드 탐사 자료(DED)의 이용 조건 — 항목마다 같은 글이 적혀 있다(2026-10-02 확인)
DED_LICENSE = "CC BY 4.0 · Hutchison (2020) Greenland diamond exploration data package, Government of Greenland"


# ── 지화학 원소 (wetherilli 159) ──────────────────────────────────
#
# 토양·중광물 농축·회사 자료·애추 넷이 같은 열 77 개를 갖는다(셰이프파일에서 옮겨 열 이름이 10 자로 잘렸다). 원소마다
# `_num` 이 붙은 수 열을 받는다 — 회사 자료에는 `_num` 없는 글 열도 있는데 그것은 받지 않는다.
# **값의 관례**(2026-10-02 에 토양 2 000 점을 받아 보았다): 양수는 측정값, **음수는 검출 한계 밑**(절댓값이 한계),
# **0 은 분석하지 않은 것**이다. 그래서 `assay` 로 받는다 — 0 은 빼고 음수는 그대로 둔다(화면이 "검출 한계 밑" 으로 칠한다).
#: (우리 열쇠, 상류 열, 이름, 단위). 차례가 고르개의 차례다 — 주성분 산화물, 그다음 원자 번호
ELEMENTS = tuple(
    [(k, f, n, "wt%") for k, f, n in (
        ("sio2", "sio2_wt_pc", "SiO₂"), ("tio2", "tio2_wt_pc", "TiO₂"), ("al2o3", "al2o3_wt_p", "Al₂O₃"),
        ("fe2o3t", "fe2o3_tot_", "Fe₂O₃ (전철)"), ("fe2o3", "fe2o3_wt_p", "Fe₂O₃"), ("feo", "feo_wt_pct", "FeO"),
        ("mno", "mno_wt_pct", "MnO"), ("mgo", "mgo_wt_pct", "MgO"), ("cao", "cao_wt_pct", "CaO"),
        ("na2o", "na2o_wt_pc", "Na₂O"), ("k2o", "k2o_wt_pct", "K₂O"), ("p2o5", "p2o5_wt_pc", "P₂O₅"),
        ("loi", "loi_wt_pct", "강열 감량"), ("cl", "cl_wt_pct_", "Cl"))]
    + [(sym, f"{sym}_{unit}_num", sym.capitalize(), unit) for sym, unit in (
        ("be", "ppm"), ("b", "ppm"), ("s", "ppm"), ("sc", "ppm"), ("v", "ppm"), ("cr", "ppm"), ("co", "ppm"),
        ("ni", "ppm"), ("cu", "ppm"), ("zn", "ppm"), ("ga", "ppm"), ("ge", "ppm"), ("as", "ppm"), ("se", "ppm"),
        ("br", "ppm"), ("rb", "ppm"), ("sr", "ppm"), ("y", "ppm"), ("zr", "ppm"), ("nb", "ppm"), ("mo", "ppm"),
        ("ru", "ppb"), ("rh", "ppb"), ("pd", "ppb"), ("ag", "ppm"), ("cd", "ppm"), ("in", "ppm"), ("sn", "ppm"),
        ("sb", "ppm"), ("te", "ppm"), ("i", "ppm"), ("cs", "ppm"), ("ba", "ppm"), ("la", "ppm"), ("ce", "ppm"),
        ("pr", "ppm"), ("nd", "ppm"), ("sm", "ppm"), ("eu", "ppm"), ("gd", "ppm"), ("tb", "ppm"), ("dy", "ppm"),
        ("ho", "ppm"), ("er", "ppm"), ("tm", "ppm"), ("yb", "ppm"), ("lu", "ppm"), ("hf", "ppm"), ("ta", "ppm"),
        ("w", "ppm"), ("re", "ppb"), ("os", "ppb"), ("ir", "ppb"), ("pt", "ppb"), ("au", "ppb"), ("hg", "ppm"),
        ("tl", "ppm"), ("pb", "ppm"), ("bi", "ppm"), ("th", "ppm"), ("u", "ppm"))])
#: 처음 켤 때의 원소 — 사람이 골랐다(구리, 토양 2 000 점 가운데 1 295 점에 값이 있다)
DEFAULT_ELEMENT = "cu"


# ── 전암 화학 (wetherilli 163) ────────────────────────────────────
#
# `Rock_Chemical_Analysis_from_Greenland` 31 769 점. 값이 모두 **쉼표 소수의 글**이고 **원소 무게 퍼센트**다(규소 중앙값 22.9 %,
# 구리 0.0087 % = 87 ppm, 금 3e-6 % = 30 ppb — 2026-10-02 에 다 받아 보았다). 포털 항목에 설명이 없어 분포로 가렸다.
# 받을 때 화면 단위로 옮긴다 — 주성분 wt%, 미량 ppm, 귀금속 ppb(`arcpoints.pct`). 시료 번호 말고 다른 속성(암석명·지점)이 없다.
# 비활성 기체·짧게 사는 방사성 원소(H·He·N·O·Ne·Ar·Kr·Xe·Rn·Fr·Ra·Ac·Po·At·Pa)는 값이 거의 없거나 뜻이 없어 뺐다
#: (우리 열쇠, 상류 열, 이름, 단위)
WHOLE_ROCK = tuple(
    [(c.lower(), c, n, "wt%") for c, n in (
        ("SI", "Si"), ("TI", "Ti"), ("AL", "Al"), ("FE", "Fe (전철)"), ("FE2", "Fe²⁺"), ("FE3", "Fe³⁺"), ("MN", "Mn"),
        ("MG", "Mg"), ("CA", "Ca"), ("NA", "Na"), ("K", "K"), ("P", "P"), ("C", "C"), ("S", "S"),
        ("LOI", "강열 감량"), ("VOL", "휘발분"))]
    + [({"GER": "ge", "ARS": "as", "IND": "in"}.get(c, c.lower()), c,
        {"GER": "Ge", "ARS": "As", "IND": "In"}.get(c, c.capitalize()), "ppm") for c in (
        "LI", "BE", "B", "F", "CL", "SC", "V", "CR", "CO", "NI", "CU", "ZN", "GA", "GER", "ARS", "SE", "BR", "RB", "SR",
        "Y", "ZR", "NB", "MO", "AG", "CD", "IND", "SN", "SB", "TE", "I", "CS", "BA", "LA", "CE", "PR", "ND", "SM", "EU",
        "GD", "TB", "DY", "HO", "ER", "TM", "YB", "LU", "HF", "TA", "W", "HG", "TL", "PB", "BI", "TH", "U")]
    + [(c.lower(), c, c.capitalize(), "ppb") for c in ("RU", "RH", "PD", "RE", "OS", "IR", "PT", "AU")])


#: 레이어명 → 상류 서비스와 받는 열. **열쇠가 짧은 까닭** — 2 만 점마다 되풀이되는
#: 이름이라 짧을수록 덜 싣는다. 팝업의 이름(`label`)은 한 번만 따로 보낸다.
#: `label` 이 없는 열(색 따위)은 그리는 데만 쓰고 팝업에 올리지 않는다.
#: 팝업 이름의 영어는 `i18n.PROP_EN` 에 적는다.
LAYERS = {
    "grportal:geochron": {
        "service": "geochron",
        "item": "6ddb07fed184429cab4c8a3f1326d644",
        "style": "age",
        "fields": {
            "sample": _field("sample_no", "시료 번호"),
            "age": _field("age_num", "연대 (Ma)", "number"),
            "err": _field("uncertaint", "오차 (Ma)"),
            "interp": _field("interpreta", "해석"),
            "mineral": _field("mineral", "광물"),
            "tech": _field("technique", "측정법"),
            "appr": _field("approach", "계산법"),
            "lith": _field("lithology", "암상"),
            "rock": _field("rock_type", "암석 갈래"),
            "terrane": _field("terrane", "지괴"),
            "fm": _field("formation", "지층"),
            "unit": _field("unit", "단위"),
            "ref": _field("reference", "문헌"),
            "link": _field("details", "GEUS 상세", "link"),
        },
    },
    "grportal:mineral_occurrences": {
        "service": "mineral_occurrences",
        "item": "bf6ac25c4cd6453eb5400d464aff8fab",
        "style": "mineral",
        "fields": {
            "name": _field("name", "이름"),
            "comm": _field("commodity", "광종"),
            "group": _field("commodity_", "광종 무리"),
            "status": _field("economic_s", "경제성"),
            "link": _field("report", "보고서", "link"),
        },
    },
    "grportal:intrusions": {
        "service": "intrusions",
        "item": "0936c8ef763c46e7b9c06b92180b0d09",
        "style": "intrusion",
        "fields": {
            "name": _field("name", "이름"),
            "desc": _field("descriptio", "설명"),
            "link": _field("link", "보고서", "link"),
        },
    },
    "grportal:samples": {
        "service": "samples_grportal",
        "item": "bb962bb1fc6a420b99349f7e59992bab",
        "style": "sample",
        "fields": {
            "no": _field("sampleno", "시료 번호"),
            "type": _field("sample_typ", "시료 갈래"),
            "lith": _field("lithology_", "암상"),
            "mat": _field("material_s", "시료 기재"),
            "loc": _field("localityna", "채취 지점"),
            "by": _field("collector", "채취자"),
            "date": _field("collected_", "채취일"),
            # 포털이 시료 갈래마다 매겨 둔 색("220 220 0"). 그 색으로 그린다
            "color": _field("rgb", "", "rgb"),
        },
    },
    # 그린란드 공식 지명(Nunat Aqqi) 33 025 — 레이어로 켜지 않고 찾기 칸이 뒤진다 (wetherilli 096). 포털에 판이 다섯
    # 있다(`Nunat_Aqqi`·`…_pisortatigut_aug2018`·`Stednavne_03_08_2018_official` 따위). 열이 같고 가장 나중에
    # 고친(2019-06) `Nunat_Aqqi` 를 쓴다. 이름은 새 철자·옛 철자(`ĸ`)·덴마크어·다른 이름 넷을 다 뒤진다
    "grportal:place_names": {
        "service": "Nunat_Aqqi", "oid": "OBJECTID",
        "item": "",
        "style": "name",
        "fields": {
            "name": _field("Aqqa_stednavn", "지명"),
            "old": _field("Allattaasitoqqamik_gml_stave", "옛 철자"),
            "da": _field("Qallunaatut_Dansk", "덴마크어 이름"),
            "alt": _field("Allatut_Alternativ", "다른 이름"),
            "kind": _field("Sammisaq_Genstand", "갈래"),
            "mun": _field("Kommune", "지자체"),
        },
    },
    # ── 면과 갈래 색 (wetherilli 089) ─────────────────────────────────
    # 아래는 `style: class` 로 간다 — 극지연구소(053)와 같은 틀. 갈래(`classes`)를 받은 값에서
    # 가르고 덩이에 `legend` 를 싣는다. 면(`areal`)은 `generalize` 도(°)로 줄여 받는다.
    # `layer` 는 FeatureServer 안의 번호(적지 않으면 0), `fresh` 는 캐시를 믿는 초(적지 않으면 3 년)
    #
    # 광물 잠재 구역 — GEUS·그린란드 정부가 2009–2014 에 광종마다 연 평가 워크숍(USGS 3 단계 평가)의 구역.
    # `n90`…`n01` 은 "이 확률로 적어도 몇 개" 의 미발견 광상 수다. 색은 포털이 광종마다 매긴 것(`rgb`)
    "grportal:mineral_tracts": {
        "service": "gmom_tracts",
        "item": "91249221eda646ffa8c303936d169394",
        "style": "class", "areal": True, "generalize": 0.005,
        "classes": {"by": "work", "table": (
            ("cu", "구리", "#008c28", "square", ("Copper",)),
            ("au", "금", "#149bf0", "square", ("Gold",)),
            ("ni", "니켈", "#8c28f0", "square", ("Nickel",)),
            ("ree", "희토류", "#f0288c", "square", ("Rare Earth",)),
            ("w", "텅스텐", "#288cf0", "square", ("Tungsten",)),
            ("zn", "아연", "#8cf028", "square", ("Zinc",)),
        ), "else": ("other", "그 밖·미상", "#757575", "square")},
        "fields": {
            "tract": _field("tract_name", "구역"),
            "work": _field("workshop", "평가 광종"),
            "year": _field("year", "평가 연도"),
            "model": _field("mineralisa", "광상 모델"),
            "known": _field("number_kno", "알려진 광상 수", "number"),
            "unk": _field("number_unk", "미발견 광상 수 (추정)", "number"),
            "n90": _field("n90", "미발견 광상 수 (90%)", "number"),
            "n50": _field("n50", "미발견 광상 수 (50%)", "number"),
            "n10": _field("n10", "미발견 광상 수 (10%)", "number"),
            "n05": _field("n05", "미발견 광상 수 (5%)", "number"),
            "n01": _field("n01", "미발견 광상 수 (1%)", "number"),
            "link": _field("report", "보고서", "link"),
            "geo": _field("geology_an", "지질 해설", "link"),
        },
    },
    # 불안정 사면·매스무브먼트 — 그린란드 정부 지질과가 "작업 중, 정기적으로 고친다(마지막 2026-02)"
    # 라고 적은 지도다. 한 서비스에 그린란드어·영어 이름의 같은 레이어가 둘씩 있어(5=2, 8=7) 영어 쪽을 받는다.
    # 그래서 캐시를 30 일만 믿는다
    "grportal:unstable_slopes": {
        "service": "Map_of_unstable_slopes_and_registered_mass_movements_WFL1", "layer": 2, "oid": "OBJECTID",
        "item": "43ac21a7a6dc4d389b42637004e2cad1",
        "style": "class", "areal": True, "generalize": 0.0001, "fresh": 30 * 86400,
        "classes": {"by": "", "table": (), "else": ("slope", "불안정 사면", "#f2c200", "square")},
        "fields": {
            "place": _field("Placename", "지명"),
            "near": _field("closest_si", "가까운 마을"),
            "dist": _field("distance_s", "마을까지 (km)", "number"),
            "vol": _field("Min_volume", "최소 부피 (m³)", "number"),
            "area": _field("area", "면적 (m²)", "number"),
            "h": _field("heights", "높이 (m)", "number"),
            "run": _field("Runout_3d_", "도달 거리 (m)", "number"),
            "geol": _field("Geology", "지질"),
            "src": _field("source_dat", "원자료"),
        },
    },
    "grportal:mass_movements": {
        "service": "Map_of_unstable_slopes_and_registered_mass_movements_WFL1", "layer": 7, "oid": "OBJECTID",
        "item": "43ac21a7a6dc4d389b42637004e2cad1",
        "style": "class", "areal": True, "generalize": 0.0001, "fresh": 30 * 86400,
        "classes": {"by": "tsu", "table": (
            ("tsunami", "매스무브먼트 — 쓰나미를 일으켰다", "#b71c1c", "square", ("1",)),
        ), "else": ("event", "매스무브먼트", "#6d4c41", "square")},
        "fields": {
            "name": _field("Stednavn", "이름"),
            "when": _field("Skred_periode", "일어난 때"),
            "tsu": _field("Tsunamigeneration", "쓰나미 (1 = 일으켰다)"),
            "vol": _field("Volumen", "부피 (m³)", "number"),
            "area": _field("skredareal", "면적 (m²)", "number"),
            "h": _field("H", "낙차 (m)", "number"),
            "run": _field("Runout", "도달 거리 (m)", "number"),
            "src": _field("Kildedata", "원자료"),
            "note": _field("Remarks", "비고"),
        },
    },
    # 다이아몬드 탐사 자료(DED)의 산출지 3 029 — 킴벌라이트·램프로파이어·카보나타이트 따위의 암맥·관입체.
    # 모르는 값을 -999 로 적어 `measure` 로 받는다. 시추공·지시광물·탐사 구역은 아래에 (wetherilli 157)
    "grportal:diamond_occurrences": {
        "service": "DED_GL_OCCURRENCES", "license": DED_LICENSE,
        "item": "2f2965291cb84ba996a5754cfeddc111",
        "style": "class",
        "classes": {"by": "rock", "table": (
            ("kimb", "킴벌라이트질", "#6a1b9a", "diamond", ("Kimberlit",)),
            ("carb", "카보나타이트", "#00897b", "dot", ("Carbonatite", "Soevite", "Fenite")),
            ("lampo", "램프로아이트", "#c2185b", "dot", ("Lamproit",)),
            ("lampr", "램프로파이어", "#ef6c00", "dot", ("Lamprophyre", "Alnoite", "Shonkinite")),
        ), "else": ("other", "그 밖·미상", "#757575", "dot")},
        "fields": {
            "loc": _field("LOCNAME", "지점"),
            "other": _field("OTHER_NAME", "다른 이름"),
            "rock": _field("ROCK_GROUP", "암석군"),
            "morph": _field("MORPHOLOGY", "산상"),
            "strike": _field("STRIKE", "주향 (°)", "measure"),
            "dip": _field("DIP", "경사 (°)", "measure"),
            "dipdir": _field("DIPDIR", "경사 방향"),
            "len": _field("DIMENSION1", "길이 (m)", "measure"),
            "wid": _field("DIMENSION2", "너비 (m)", "measure"),
            "grade": _field("DIAM_GRADE", "다이아몬드 품위"),
            "desc": _field("COMMENTS1", "기재"),
            "note": _field("COMMENTS2", "비고"),
            "srct": _field("SOURCETYPE", "출처 갈래"),
            "owner": _field("OWNERNAME", "보고한 곳"),
            "year": _field("DATE", "연도"),
        },
    },
    # ── 다이아몬드 탐사 자료(DED)의 나머지 (wetherilli 157) ──
    # 시추공 202 — 이상대(자력·전자탐사)를 뚫어 킴벌라이트를 만났는가
    "grportal:diamond_drillholes": {
        "service": "DED_GL_DRILLHOLES", "license": DED_LICENSE,
        "item": "92f7e8d418dc4ea49a90138005198195",
        "style": "class",
        "classes": {"by": "kim", "table": (
            ("yes", "킴벌라이트를 만났다", "#6a1b9a", "square", ("Yes",)),
            # `Not_Reported` 도 `No` 로 시작한다 — 먼저 가른다
            ("nr", "보고 없음", "#cfd8dc", "square", ("Not_",)),
            ("no", "만나지 못했다", "#90a4ae", "square", ("No",)),
        ), "else": ("other", "그 밖", "#cfd8dc", "square")},
        "fields": {
            "hole": _field("COMPHOLEID", "시추공"),
            "prospect": _field("PROSPECT", "탐사지"),
            "loc": _field("LOCALITY", "지점"),
            "anom": _field("ANOMALY", "이상대"),
            "anomt": _field("ANOM_TYPE", "이상대 갈래"),
            "kim": _field("KPRESENT", "킴벌라이트"),
            "kthick": _field("KTOTTHICK", "킴벌라이트 두께 (m)", "measure"),
            "eoh": _field("EOH", "시추 길이 (m)", "measure"),
            "az": _field("AZIMUTH", "방위 (°)", "measure"),
            "dip": _field("DIP", "경사 (°)", "measure"),
            "lith": _field("LITH_DESCN", "암상"),
            "geol": _field("GEOLASSOC", "주변 지질"),
            "op": _field("OPERATOR", "시추한 곳"),
            "year": _field("PUBYEAR", "보고 연도", "number"),
            "desc": _field("COMMENTS1", "기재"),
        },
    },
    # 지시광물 농도 1 048 — 시료 1 kg 에서 나온 지시광물(석류석·단사휘석·티탄철석 …) 낟알 수. 가운데값 3, 위 1% 는 8 천
    "grportal:diamond_indicators": {
        "service": "DED_GL_thm_BA_ind_inds_per_kg", "license": DED_LICENSE,
        "item": "3ed631e3ab304d5280ce0f4eb816b4e3",
        "style": "class",
        "classes": {"by": "pkg", "numeric": True, "table": (
            ("c100", "100 낟알/kg 넘게", "#b71c1c", "dot", (100, None)),
            ("c10", "10–100 낟알/kg", "#ef6c00", "dot", (10, 100)),
            ("c1", "1–10 낟알/kg", "#fbc02d", "dot", (1, 10)),
        ), "else": ("c0", "1 낟알/kg 밑", "#b0bec5", "dot")},
        "fields": {
            "sample": _field("SOUSAMPNA", "시료"),
            "sub": _field("SOUSUBSAMP", "나눈 시료"),
            "pkg": _field("INDIC_PKG", "지시광물 (낟알/kg)", "number"),
        },
    },
    # 다이아몬드 농도 178 — 시료 1 kg 에서 나온 다이아몬드 수. 가운데값 0.09, 위 10% 는 1 넘게
    "grportal:diamond_per_kg": {
        "service": "DED_GL_thm_BA_ind_dia_per_kg", "license": DED_LICENSE,
        "item": "4b4be03654de44a9867f83827177c28c",
        "style": "class",
        "classes": {"by": "pkg", "numeric": True, "table": (
            ("d1", "1 개/kg 넘게", "#4a148c", "diamond", (1, None)),
            ("d025", "0.25–1 개/kg", "#8e24aa", "diamond", (0.25, 1)),
            ("d005", "0.05–0.25 개/kg", "#ce93d8", "diamond", (0.05, 0.25)),
        ), "else": ("d0", "0.05 개/kg 밑", "#e1bee7", "diamond")},
        "fields": {
            "sample": _field("SOUSAMPNA", "시료"),
            "sub": _field("SOUSUBSAMP", "나눈 시료"),
            "pkg": _field("DIAM_PKG", "다이아몬드 (개/kg)", "number"),
        },
    },
    # 석류석 분류 2 468 — 낟알마다 화학으로 가른 갈래(Grütter 외 2004 의 G1–G12)를 시료마다 센 것.
    # G10 은 하즈버자이트질(다이아몬드 지시), G10D 는 그 가운데 다이아몬드 안정역의 것, G9 는 러졸라이트질
    "grportal:garnet_classes": {
        "service": "DED_GL_thm_BA_ind_chemGT", "license": DED_LICENSE,
        "item": "74f3199421cb4568b012adb9d8070c04",
        "style": "class",
        "classes": {"by": "", "table": (
            # `{"gt0": 열}` — 그 열의 값이 0 보다 크다. 함수가 아니라 글자로 적어 정적 판(JS)도 같은 표로 가른다 (wetherilli 161)
            ("g10d", "G10D 가 있다 (다이아몬드 안정역)", "#b71c1c", "dot", {"gt0": "g10d"}),
            ("g10", "G10 이 있다", "#ef6c00", "dot", {"gt0": "g10"}),
            ("g9", "G9 만 (러졸라이트질)", "#43a047", "dot", {"gt0": "g9"}),
        ), "else": ("other", "그 밖의 석류석", "#b0bec5", "dot")},
        "fields": {
            "sample": _field("SOUSAMPNA", "시료"),
            "g10d": _field("GT_G10D", "G10D 낟알", "number"),
            "g10": _field("GT_G10", "G10 낟알", "number"),
            "g9": _field("GT_G9", "G9 낟알", "number"),
            "g11": _field("GT_G11", "G11 낟알", "number"),
            "g12": _field("GT_G12", "G12 낟알", "number"),
            "g1": _field("GT_G1", "G1 낟알", "number"),
            "g3": _field("GT_G3", "G3 낟알", "number"),
            "g4": _field("GT_G4", "G4 낟알", "number"),
            "g5": _field("GT_G5", "G5 낟알", "number"),
        },
    },
    # 탐사 구역 — 탐사된 곳(시료 둘레)과 다이아몬드 가능성이 있으나 탐사되지 않은 곳. 둘 다 조각 수천의 면 하나다.
    # 속성은 면을 만든 흔적(첫 시료의 값·원본 셰이프 경로)이라 받지 않는다
    "grportal:diamond_explored": {
        "service": "DED_GL_Explored_Polygons", "license": DED_LICENSE,
        "item": "d175bd2708e5425780af72123bde181d",
        "style": "class", "areal": True, "generalize": 0.02,
        "classes": {"by": "", "table": (), "else": ("explored", "탐사된 곳", "#1e88e5", "square")},
        "fields": {},
    },
    "grportal:diamond_unexplored": {
        "service": "DED_GL_Unexplored_Polygons", "license": DED_LICENSE,
        "item": "0606178fa0b646ab818c5eab92c865a4",
        "style": "class", "areal": True, "generalize": 0.02,
        "classes": {"by": "", "table": (), "else": ("unexplored", "탐사되지 않은 곳 (가능성 있음)", "#fb8c00", "square")},
        "fields": {},
    },
    **{f"grportal:geochem_{key}": {
        "service": service, "item": item, "style": "value",
        "fields": {
            "sample": _field("sampleno", "시료 번호"),
            "type": _field("sample_typ", "시료 갈래"),
            "year": _field("year", "해"),
            "sheet": _field("map_sheet", "도폭"),
            "who": _field("fullname", "채취·보고"),
            "link": _field(link, "GEUS 상세", "link"),
            **{k: _field(f, "", "assay") for k, f, _, _ in ELEMENTS},
        },
    } for key, service, item, link in (
        ("soil", "geochemistry_soil", "8724682f88e548288870bdd1611e52a1", "link"),
        ("heavy", "geochemistry_heavy_minerals_conc", "a4ae0f04bd84410d8a696ca3fc097d24", "link"),
        ("companies", "geochemistry_companies", "ae1c3db86cfe4767a0d7f4e0fa54c25a", "link"),
        ("scree", "geochemistry_scree", "ae10729f316549fbbfe68f6f32204d16", "details"),
    )},
    # 전암 화학 3 만 점 — 원소 열을 다 실으면 덩이가 수십 MB 라 **고른 원소만 잘라 준다**(`slice`, `value_slice`)
    "grportal:whole_rock": {
        "service": "Rock_Chemical_Analysis_from_Greenland", "item": "57e5bb29a3f044ca986fa9c22e5ab659",
        "style": "value", "slice": True,
        "fields": {
            "sample": _field("ORIGINALSA", "시료 번호"),
            "anal": _field("SAMPLETREA", "분석 번호"),
            **{k: _field(f, "", {"wt%": "pct_wt", "ppm": "pct_ppm", "ppb": "pct_ppb"}[u]) for k, f, _, u in WHOLE_ROCK},
        },
    },
}

#: 지도 귀퉁이에 적는 출처. 항목 주소가 있으면 그리로, 없으면 웹지도로 잇는다.
WEBMAP = "https://asiaq.maps.arcgis.com/apps/webappviewer/index.html?id=4f800688403c4cfea40175950dd94875"


def knows(name: str) -> bool:
    return name in LAYERS


def license_of(name: str) -> str:
    """항목에 적힌 이용 조건. 적혀 있지 않으면 빈 글 (019)."""
    return LAYERS.get(name, {}).get("license", "")


def source_url(name: str) -> str:
    item = LAYERS.get(name, {}).get("item")
    return f"https://www.arcgis.com/home/item.html?id={item}" if item else WEBMAP


def signature(name: str) -> str:
    """캐시 열쇠에 넣는 것 (`arcpoints.signature`). 019 의 열쇠 그대로다 —
    틀을 떼어 냈다고 받아 둔 점을 다시 받지 않는다."""
    spec = LAYERS[name]
    head = f"{spec['service']}|FID"
    if spec.get("layer") or spec.get("generalize"):
        head = f"{spec['service']}/{spec.get('layer', 0)}|{spec.get('oid', 'FID')}|g={spec.get('generalize', 0)}"
    return arcpoints.signature(spec, head)


def fresh_seconds(name: str):
    """캐시를 믿는 초. None 이면 다른 받아온 것처럼 3 년이다 (`views.point_features`)."""
    return LAYERS[name].get("fresh")


def labels(name: str) -> dict:
    return arcpoints.labels(LAYERS[name])


def _query_url(service: str, layer: int = 0) -> str:
    return f"{settings.GRPORTAL_URL.rstrip('/')}/{service}/FeatureServer/{layer}/query"


def _get_page(service: str, fields: list, offset: int, *, layer: int = 0, oid: str = "FID",
              generalize: float = 0) -> dict:
    params = {
        "where": "1=1", "outFields": ",".join(fields), "returnGeometry": "true",
        "outSR": "4326", "f": "geojson", "orderByFields": f"{oid} ASC",
        "resultOffset": offset, "resultRecordCount": PAGE,
    }
    if generalize:
        params["maxAllowableOffset"] = generalize
    try:
        r = requests.get(_query_url(service, layer), params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("grportal", ok=False)
        raise PortalError(f"그린란드 포털에 닿지 못했다: {exc}") from exc
    log.info("grportal %s offset=%d -> %s", service, offset, r.status_code)
    blocked = usage.looks_blocked(r.status_code, r.content[:1000])
    if r.status_code != 200:
        usage.record("grportal", ok=False, blocked=blocked)
        raise PortalError(f"그린란드 포털이 받지 않았다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        usage.record("grportal", ok=False)
        raise PortalError("그린란드 포털이 JSON 이 아닌 것을 주었다") from exc
    # ArcGIS 는 잘못된 요청에도 200 에 {"error": …} 를 싣는다
    if "error" in data:
        usage.record("grportal", ok=False)
        raise PortalError(f"그린란드 포털의 오류: {data['error'].get('message', '')}")
    usage.record("grportal", ok=True)
    return data


def fetch(name: str, pause: float = None) -> list:
    """레이어 하나의 점을 **모두** 받아 짧은 열쇠의 GeoJSON feature 목록으로.

    상류가 준 값은 고치지 않는다 — 앞뒤 빈칸만 떼고, 빈 값은 뺀다. 이 목록이
    그대로 캐시에 담긴다.
    """
    spec = LAYERS[name]
    fields = spec["fields"]
    oid = spec.get("oid", "FID")
    # FID 를 늘 함께 받는다 — 열을 골라 받으면 상류가 feature 의 `id` 를 비워 보낸다
    wanted = sorted({f["from"] for f in fields.values()} | {oid})
    return arcpoints.collect(
        lambda offset: _get_page(spec["service"], wanted, offset, layer=spec.get("layer", 0), oid=oid,
                                 generalize=spec.get("generalize", 0)),
        fields, page=PAGE, max_pages=MAX_PAGES, pause=PAUSE if pause is None else pause,
        name=name, oid=oid, areal=spec.get("areal", False))


#: 받은 feature 를 우리 꼴로 줄이는 틀은 `arcpoints` 에 있다 (NPI 와 함께 쓴다, 021)
compact = arcpoints.compact
_clean = arcpoints.clean


def class_of(spec: dict, props: dict) -> tuple:
    """feature 하나의 갈래 (code, label, color, shape). 받은 값이 표의 머리말로 시작하면 그 갈래다 —
    위에서부터 먼저 맞는 것. 캐시에는 넣지 않고 내보낼 때 가른다 — 색을 고쳐도 다시 받지 않는다."""
    classes = spec["classes"]
    raw = props.get(classes["by"]) if classes["by"] else None
    value = str(raw if raw is not None else "")
    for code, label, color, shape, heads in classes["table"]:
        if isinstance(heads, dict):
            # 다른 열을 보고 가른다 — 석류석 갈래 (wetherilli 157). `gt0` 는 그 열의 값이 0 보다 큰 것
            if (props.get(heads["gt0"]) or 0) > 0:
                return code, label, color, shape
        elif callable(heads):
            if heads(props):
                return code, label, color, shape
        elif classes.get("numeric"):
            # 값의 구간 `(이상, 미만)` — 미만이 None 이면 끝이 없다
            low, high = heads
            if isinstance(raw, (int, float)) and raw >= low and (high is None or raw < high):
                return code, label, color, shape
        elif value.startswith(heads):
            return code, label, color, shape
    return classes["else"]


def _value_body(spec: dict, features_json: bytes) -> bytes:
    """연속값 레이어(지화학, wetherilli 159)의 덩이 — `values`([{key, label, unit, n, below}])에 이 레이어에서 값이 하나라도
    있는 원소만 싣는다(`n` 은 측정값의 수, `below` 는 검출 한계 밑의 수). 색은 화면이 고른 원소의 분위수로 칠한다."""
    features = json.loads(features_json)
    keys, counts = {k for k, *_ in _table(spec)}, {}
    for feature in features:
        for key, value in feature["properties"].items():
            if isinstance(value, (int, float)) and key in keys:
                n, below = counts.get(key, (0, 0))
                counts[key] = (n + (value > 0), below + (value < 0))
    values = [{"key": k, "label": label, "unit": unit, "n": counts[k][0], "below": counts[k][1]}
              for k, _, label, unit in _table(spec) if counts.get(k, (0, 0))[0]]
    return json.dumps({"type": "FeatureCollection", "labels": arcpoints.labels(spec), "links": arcpoints.links(spec),
                       "style": "value", "values": values, "default": DEFAULT_ELEMENT,
                       "features": features}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _table(spec: dict) -> tuple:
    return WHOLE_ROCK if spec.get("slice") else ELEMENTS


_SLICES = {}


def value_slice(name: str, features_json: bytes, key: str) -> bytes:
    """잘라 주는 연속값 레이어(전암 화학, wetherilli 163)의 덩이 — **고른 원소의 값이 있는 점만**, 그 원소와 시료 번호만
    싣는다. `values` 는 원소마다의 수(덩이 전체를 한 번 세어 기억한다). 모르는 원소면 처음 원소(구리)로."""
    spec = LAYERS[name]
    memo = _SLICES.get(name)
    if not memo or memo[0] != len(features_json):
        features = json.loads(features_json)
        meta = json.loads(_value_body(spec, json.dumps(features).encode()))["values"]
        memo = _SLICES[name] = (len(features_json), features, meta)
    _, features, values = memo
    known = {v["key"] for v in values}
    key = key if key in known else (DEFAULT_ELEMENT if DEFAULT_ELEMENT in known else next(iter(known), ""))
    base = [k for k, f in spec["fields"].items() if f["label"]]
    out = [{"type": "Feature", "id": f.get("id"), "geometry": f["geometry"],
            "properties": {**{b: f["properties"][b] for b in base if b in f["properties"]}, key: f["properties"][key]}}
           for f in features if key in f["properties"]]
    return json.dumps({"type": "FeatureCollection", "labels": arcpoints.labels(spec), "links": arcpoints.links(spec),
                       "style": "value", "values": values, "default": DEFAULT_ELEMENT, "slice": key,
                       "total": len(features), "features": out},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def body(name: str, features_json: bytes) -> bytes:
    """브라우저에 보내는 한 덩이 (`arcpoints.body`). 갈래가 있는 레이어는 feature 마다 `code`,
    덩이에 `legend`([{code, label, color, shape, count}])를 싣는다 — 극지연구소와 같은 꼴이다."""
    spec = LAYERS[name]
    if spec["style"] == "value":
        return _value_body(spec, features_json)
    if "classes" not in spec:
        return arcpoints.body(spec, features_json)
    features = json.loads(features_json)
    counts, table = {}, {}
    for feature in features:
        code, label, color, shape = class_of(spec, feature["properties"])
        feature["properties"]["code"] = code
        counts[code] = counts.get(code, 0) + 1
        table[code] = (label, color, shape)
    order = [row[0] for row in spec["classes"]["table"]] + [spec["classes"]["else"][0]]
    legend = [{"code": c, "label": table[c][0], "color": table[c][1], "shape": table[c][2], "count": counts[c]}
              for c in order if c in counts]
    return json.dumps({"type": "FeatureCollection", "labels": arcpoints.labels(spec),
                       "links": arcpoints.links(spec), "style": "class", "legend": legend,
                       "features": features}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
