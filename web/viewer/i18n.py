"""말 — 한국어와 영어.

**원문은 한국어다.** 화면·JS·서버 메시지를 한국어로 적고, 영어는 이 파일의
표에서 찾는다. 열쇠가 한국어 원문 그대로라 코드를 읽는 사람이 무엇을
옮긴 것인지 곧바로 안다. 표에 없는 것은 한국어로 남는다 — 영어판이 한
글자 빠졌다고 화면이 깨지지는 않는다.

**문장을 새로 적거나 고치면 여기도 적는다** (CLAUDE.md "영어판").
`test_i18n` 이 JS 의 `T("…")`, 템플릿의 `{% t "…" %}`, 파이썬의 `msg("…")`
를 모두 긁어 이 표에 없는 것을 잡는다. 레이어 제목처럼 자료에서 오는 것은
시험이 아니라 `manage.py i18n_missing` 이 보여준다.

숫자·이름이 끼는 문장은 `{n}`·`{name}` 자리표로 둔다. 영어는 말 차례가
달라 조각을 이어 붙이면 어색하다.

**속성 값은 옮기지 않는다** — 지층명·암석명은 상류가 한국어로 주는 자료이고
수천 가지다. 지질시대만은 낱말을 조합한 것이라 옮긴다. 영문 명칭은 ICS
국제층서표(https://stratigraphy.org/chart)를 따른다.
"""
import re

LANGS = ("ko", "en")
COOKIE = "gsm_lang"


def lang_of(request) -> str:
    """쿠키가 먼저다. 없으면 브라우저가 한국어를 받지 않을 때만 영어로 연다."""
    chosen = request.COOKIES.get(COOKIE, "")
    if chosen in LANGS:
        return chosen
    accept = request.META.get("HTTP_ACCEPT_LANGUAGE", "").lower()
    if accept and "ko" not in accept and "en" in accept:
        return "en"
    return "ko"


class Msg(str):
    """한국어로 채워진 문자열이면서 원문 틀과 값을 따로 들고 있다.

    업로드 알림처럼 뷰 밖(`pointsets.py`)에서 만들어져 뷰가 사람에게 보일 때
    영어로 바꿔야 하는 문장에 쓴다. 그냥 쓰면 한국어 문자열이라 기존 코드와
    시험은 그대로 돈다.
    """

    def __new__(cls, template, **params):
        self = super().__new__(cls, template.format(**params))
        self.template = template
        self.params = params
        return self


def msg(template: str, **params) -> Msg:
    return Msg(template, **params)


def t(text, lang: str = "ko", **params) -> str:
    """한 문장을 옮긴다. `Msg` 면 원문 틀로 찾는다."""
    if isinstance(text, Msg):
        template, params = text.template, {**text.params, **params}
    else:
        template = str(text)
    out = EN.get(template, template) if lang == "en" else template
    if lang == "en":
        # 자리표에 들어가는 값도 표에 있으면 옮긴다 — 좌표계 이름 같은 것
        params = {k: EN.get(v, v) if isinstance(v, str) else v for k, v in params.items()}
    return out.format(**params) if params else out


def client_table(lang: str) -> dict:
    """브라우저에 실어 보낼 표. 한국어판이면 비운다 — 옮길 것이 없다."""
    if lang != "en":
        return {}
    return {**EN, **PROP_EN}


# ── 화면·메시지 ──────────────────────────────────────────────────────

EN = {
    # 대만 지질 민감구역의 갈래 (wetherilli 336)
    "활성단층 민감구역": "Active fault sensitive area", "지하수 함양 민감구역": "Groundwater recharge sensitive area",
    "지질 유산 민감구역": "Geoheritage sensitive area", "산사태·지활 민감구역": "Landslide sensitive area",
    # 레이어 찾기 (wetherilli 332)
    "레이어 찾기 — 모든 지역에서": "Find a layer — across all regions",
    "{n} 개 — 다른 지역의 것은 그 탭으로 옮겨 켠다": "{n} found — picking one from another region switches to that tab",
    "맞는 레이어가 없다": "No matching layer",
    "이 탭": "This tab",
    "앞의 {n} 개만 보인다 — 낱말을 더 적어 좁힌다": "Showing the first {n} — add words to narrow it down",
    # 캐나다 (wetherilli 204)
    "캐나다": "Canada", "캐나다 천연자원부": "Natural Resources Canada", "온타리오 지질조사소": "Ontario Geological Survey",
    "캐나다 람베르트": "Canada Atlas Lambert",
    # 북미 묶음·퀘벡·유콘 (wetherilli 210)
    "북미": "North America", "퀘벡 지질 광업 정보 체계": "SIGÉOM (Québec geomining information system)",
    "유콘 지질조사소": "Yukon Geological Survey", "지구조 요소": "Tectonic element",
    # 캐나다 주 판 둘째 (wetherilli 235)
    "사스카치원 지질조사소": "Saskatchewan Geological Survey", "노바스코샤 자연자원·재생에너지부": "Nova Scotia Natural Resources and Renewables",
    "앨버타 지질조사소": "Alberta Geological Survey",
    # 이탈리아·포르투갈·스위스 (wetherilli 211)
    "이탈리아": "Italy", "포르투갈": "Portugal", "스위스": "Switzerland",
    "이탈리아 지질조사소 (ISPRA)": "Geological Survey of Italy (ISPRA)", "포르투갈 국립 에너지·지질연구소": "LNEG (Portugal)",
    "스위스 연방 지형청": "swisstopo (Switzerland)",
    # 아이슬란드 (wetherilli 216)
    "아이슬란드": "Iceland", "아이슬란드 자연사연구소": "Icelandic Institute of Natural History",
    # 뉴질랜드·오세아니아 (wetherilli 218)
    "뉴질랜드": "New Zealand", "오세아니아": "Oceania", "뉴질랜드 지질·핵과학연구소 (GNS)": "GNS Science (New Zealand)",
    # 몽골 (wetherilli 221)
    "몽골": "Mongolia", "몽골 국가지질조사소 (MonGeoCat)": "National Geological Survey of Mongolia (MonGeoCat)",
    # 인도 (wetherilli 226)
    "인도": "India", "인도 지질조사소 (그림: BGS)": "Geological Survey of India (map by BGS)",
    # 사우디아라비아 (wetherilli 227)
    "사우디아라비아": "Saudi Arabia", "사우디 지질조사소": "Saudi Geological Survey",
    # 동남아 (wetherilli 228)
    "인도네시아": "Indonesia", "말레이시아": "Malaysia", "필리핀": "Philippines", "태국": "Thailand", "동남아": "Southeast Asia",
    # 중앙아메리카·카리브 (wetherilli 242)
    "니카라과": "Nicaragua", "도미니카공화국": "Dominican Republic", "카리브": "Caribbean", "파나마": "Panama", "파라과이": "Paraguay",
    "누벨칼레도니": "New Caledonia", "프랑스령 폴리네시아": "French Polynesia", "폴리네시아": "French Polynesia", "누벨칼레도니 정부 (Géorep)": "Government of New Caledonia (Géorep)",
    "파라과이 광업·에너지 차관실 (VMME)": "Vice-Ministry of Mines and Energy of Paraguay (VMME)",
    "파라과이 지질도(VMME)를 받지 못했다": "Could not fetch the geologic map of Paraguay (VMME)",
    "스미스소니언 열대연구소 (STRI)": "Smithsonian Tropical Research Institute (STRI)",
    "파나마 지질도(STRI)를 받지 못했다": "Could not fetch the geologic map of Panama (STRI)",
    "USGS 카리브 지질도를 받지 못했다": "Could not fetch the USGS Caribbean geologic map",
    "중미·카리브": "Central America & Caribbean", "니카라과 국토연구원 (INETER)": "Nicaraguan Institute of Territorial Studies (INETER)",
    # 오스트리아·폴란드·네덜란드·벨기에 (wetherilli 237)
    "오스트리아": "Austria", "폴란드": "Poland", "네덜란드": "Netherlands", "벨기에": "Belgium",
    "폴란드 지질연구소 (PIG-PIB)": "Polish Geological Institute (PIG-PIB)", "네덜란드 지질조사부 (TNO)": "Geological Survey of the Netherlands (TNO)",
    "플랑드르 지하 자료은행 (DOV)": "Flanders Subsurface Database (DOV)", "왈로니아 공공서비스 (SPW)": "Public Service of Wallonia (SPW)",
    "브리티시컬럼비아 지질조사소": "British Columbia Geological Survey", "캘리포니아 지질조사소": "California Geological Survey",
    "네바다 광산지질국": "Nevada Bureau of Mines and Geology", "워싱턴 지질조사소": "Washington Geological Survey", "오리건 지질광물산업부": "Oregon DOGAMI", "알래스카 지질·지구물리조사소": "Alaska Division of Geological & Geophysical Surveys",
    "인도네시아 지질청 (ESDM)": "Geological Agency of Indonesia (ESDM)", "말레이시아 광물지구과학국": "Minerals and Geoscience Department Malaysia",
    "필리핀 광산지질국": "Mines and Geosciences Bureau (Philippines)", "태국 광물자원국": "Department of Mineral Resources (Thailand)",
    # KIGAM 5만 단층·습곡·광종·변질대 (wetherilli 202)
    "드러스트": "Thrust", "추정 드러스트": "Inferred thrust", "정단층": "Normal fault", "추정 정단층": "Inferred normal fault",
    "주향이동단층": "Strike-slip fault", "추정 주향이동단층": "Inferred strike-slip fault", "추정 단층": "Inferred fault",
    "단층": "Fault",
    # 5만 선구조·신장광물·습곡축·유동구조의 갈래 (wetherilli 223)
    "1차 선구조": "First-order lineation", "2차 선구조": "Second-order lineation", "3차 선구조": "Third-order lineation",
    "선구조": "Lineation", "그 밖의 선구조": "Other lineations", "신장광물": "Stretched mineral",
    "침강각 미상 신장광물": "Stretched mineral (plunge unknown)", "그 밖의 신장광물": "Other stretched minerals",
    "습곡축": "Fold axis", "소습곡축": "Minor fold axis", "2·3차 습곡축": "Second- and third-order fold axes",
    "유동구조": "Flow structure", "유상구조": "Flow banding", "수직 유동구조": "Vertical flow structure",
    "배사": "Anticline", "향사": "Syncline", "역전 등사 배사": "Overturned isoclinal anticline",
    "역전 등사 향사": "Overturned isoclinal syncline", "침강 배사": "Plunging anticline", "침강 향사": "Plunging syncline",
    "그 밖의 습곡": "Other folds",
    "금·은": "Gold and silver", "석탄": "Coal", "철": "Iron", "동·연·아연 따위": "Copper, lead, zinc and others",
    "비금속·그 밖": "Non-metallic and other",
    "열변성대": "Thermal metamorphic zone", "접촉변질대": "Contact alteration zone", "변질대": "Alteration zone",
    "열수광화대": "Hydrothermal mineralized zone", "접촉변성대": "Contact metamorphic zone",
    "그 밖의 변질·변성대": "Other alteration or metamorphic zones",
    # KIGAM 5만 구조 요소 레이어 (wetherilli 199)
    "유공충": "Foraminifera", "식물화석": "Plant fossils", "화석산지": "Fossil locality",
    "SHRIMP 연대": "SHRIMP dating", "K-Ar 연대": "K-Ar dating", "연대측정": "Dating", "지구화학 분석": "Geochemistry",
    "그 밖의 시료": "Other samples", "광산·채굴지": "Mines and workings", "갱도·갱구": "Adits and shafts",
    "폐광·휴광": "Closed or idle mines", "5만 도폭": "1:50k map sheet",
    "5만 구조 요소를 아직 받지 않았다 (fetch_kigam50k)": "The 1:50k structural data have not been fetched yet (fetch_kigam50k)",
    "원본 자료 — KIGAM 5만 수치지질도, CC BY-NC": "Source — KIGAM 1:50k digital geological map, CC BY-NC",
    "한국지질자원연구원 5만 수치지질도": "KIGAM 1:50k digital geological map",
    # 층리·엽리 장미도 (wetherilli 197)
    "이 범위의 층리·엽리 장미도": "Rose diagram of bedding and foliation in this extent",
    "이 도폭의 층리·엽리 장미도": "Rose diagram of bedding and foliation on this map sheet",
    "장미도를 받지 못했다": "Could not load the rose diagram",
    "{name} 도폭 ({no}) — 자세 기호": "{name} sheet ({no}) — attitude symbols",
    "잡은 범위 — 자세 기호": "Selected extent — attitude symbols",
    "이 자리에는 받아 둔 층리·엽리·절리가 없다": "No stored bedding, foliation or joints here",
    "받은 날 {date}": "Fetched {date}",
    "경사 미상 {n}": "Dip unknown {n}",
    "주향은 경사 방향 − 90° (오른손 법칙)": "Strike = dip direction − 90° (right-hand rule)",
    "5만 지질도의 자세 기호 파일이 없다": "The 1:50k attitude symbol files are not on the server",
    "주향": "Strike", "경사 방향": "Dip direction", "경사": "Dip",
    # 지역 탭의 지구 자료 점 (wetherilli 185)
    "제4기": "Quaternary", "신진기": "Neogene", "고진기": "Paleogene", "백악기": "Cretaceous", "쥐라기": "Jurassic",
    "트라이아스기": "Triassic", "페름기": "Permian", "석탄기": "Carboniferous", "데본기": "Devonian",
    "실루리아기": "Silurian", "오르도비스기": "Ordovician", "캄브리아기": "Cambrian", "선캄브리아": "Precambrian",
    "원본 자료 — Paleobiology Database, CC BY 4.0": "Source — Paleobiology Database, CC BY 4.0",
    "원본 자료 — 스미스소니언 GVP, 비상업·인용 조건": "Source — Smithsonian GVP, non-commercial use with citation",
    "원본 자료 — USGS ComCat, 공공 영역": "Source — USGS ComCat, public domain",
    "원본 자료 — Neotoma, CC BY 4.0": "Source — Neotoma, CC BY 4.0",
    "화석 산지 자료를 아직 모으지 않았다 (fetch_pbdb)": "Fossil collections have not been gathered yet (fetch_pbdb)",
    "홀로세 화산 자료를 아직 모으지 않았다 (fetch_gvp)": "Holocene volcanoes have not been gathered yet (fetch_gvp)",
    "지진 자료를 아직 모으지 않았다 (fetch_quakes)": "Earthquakes have not been gathered yet (fetch_quakes)",
    "고생태 산지 자료를 아직 모으지 않았다 (fetch_neotoma)": "Paleoecology sites have not been gathered yet (fetch_neotoma)",
    "모아 둔 자료를 읽지 못했다": "Could not read the gathered data",
    "온 지구 화면에 모아 둔 자료 — PBDB·GVP·USGS·Neotoma": "Data gathered for the Whole Earth view — PBDB, GVP, USGS, Neotoma",
    # 점묶음 CSV (wetherilli 190)
    "CSV 로 내려받는다 — 우리 파일에서 읽는 값을 열로 붙인다": "Download as CSV — with values read from our own files as extra columns",
    "점이 {n} 개라 붙일 값은 빼고 내려받는다 — 값은 {limit} 개까지 읽는다.":
        "This set has {n} points, so it downloads without the extra values — they are read for up to {limit} points.",
    "점이 {n} 개라 붙일 값을 읽지 않는다 — {limit} 개까지다. extras=none 으로 부른다":
        "{n} points is too many to read extra values for — the limit is {limit}. Call with extras=none",
    # 이름
    "대돌여지도": "Great Stone Map",
    "GSM — 한국지질자원연구원 지오빅데이터 오픈플랫폼 오픈API 지도뷰어":
        "GSM — a map viewer for the KIGAM Geo Big Data Open Platform API",
    "불러오는 중": "Loading",

    # 띠
    "<b>임시 경로로 받고 있다.</b> 인증키가 아직 없어 문서에 없는 주소 (<code>/mgeo/geoserver/wms</code>)로 지도를 받는다. 키가 들어오면 <code>dev_direct_wms</code> 를 지우고 다시 띄운다 — 그때부터 문서화된 <code>/openapi/wms</code> 로 간다.":
        "<b>Using a temporary route.</b> There is no API key yet, so maps come from an undocumented address (<code>/mgeo/geoserver/wms</code>). Once a key arrives, delete <code>dev_direct_wms</code> and restart — requests then go to the documented <code>/openapi/wms</code>.",
    "인증키가 없다. 타일 자리에 안내가 뜬다 — <code>GSM_KIGAM_KEY</code> 를 채우거나 <code>kigam_key</code> 파일을 둔다.":
        "No API key. Tiles show a notice instead — set <code>GSM_KIGAM_KEY</code> or add a <code>kigam_key</code> file.",

    # 패널
    "레이어": "Layers",
    "불러오기": "Import",
    "레이어 고르기": "Choose layers",
    "배경": "Basemap",
    "지명 보이기": "Show place names",
    "켠 지질 레이어": "Active layers",
    "위가 앞이다": "top is front",
    "아직 켠 레이어가 없다": "No layers on yet",
    # 바람 (koprifossillab P02)
    "움직이는 지구": "Earth in flux",
    "구름": "Clouds",
    "지금의 구름": "Current clouds",
    "지난 구름": "Past clouds",
    "구름 종류": "Cloud type",
    "전체 구름": "Total cloud",
    "하층 구름": "Low cloud",
    "중층 구름": "Middle cloud",
    "상층 구름": "High cloud",
    "이 시각에는 구름 자료가 없다": "No cloud data for this time",
    "위성 구름": "Satellite clouds",
    "{t} UTC · 위성 적외선 (한 시간마다)": "{t} UTC · satellite infrared (hourly)",
    "위성 구름 자료가 아직 없다": "No satellite clouds yet",
    # 해류 (koprifossillab 014)
    "해류": "Ocean currents",
    "{t} · ECCO2 3 일 평균 · 표층 5 m": "{t} · ECCO2 3-day mean · surface (5 m)",
    "해류 자료가 아직 없다": "No ocean currents yet",
    "해류의 달": "Month (ocean currents)",
    # 바람·해류의 빠르기 범례 (koprifossillab 018)
    "입자 색은 바람의 빠르기 — {level}": "Particle colour is wind speed — {level}",
    "입자 색은 해류의 빠르기 — 표층 5 m": "Particle colour is current speed — surface (5 m)",
    "{a}–{b} m/s": "{a}–{b} m/s",
    "{a} m/s 넘게": "over {a} m/s",
    # 아라온호 항적 기간 (koprifossillab 017)
    "항적 기간": "Track period",
    "1개월": "1 month",
    "6개월": "6 months",
    "1년": "1 year",
    "{n}일": "{n} days",
    "위도 72° 너머는 비어 있다. 추운 땅이 구름처럼 보일 수 있다.": "Empty beyond 72° latitude. Cold ground can look like cloud.",
    "바람": "Wind",
    "지금의 바람": "Current wind",
    "지난 바람": "Past wind",
    "높이": "Height",
    "지상 10 m": "10 m above ground",
    "250 hPa (제트기류)": "250 hPa (jet stream)",
    "재생": "Play",
    "바람 자료가 아직 없다": "No wind data yet",
    "{t} UTC · GFS 분석": "{t} UTC · GFS analysis",
    "{t} UTC · ERA5 재분석": "{t} UTC · ERA5 reanalysis",
    "{t} UTC · GFS 예보": "{t} UTC · GFS forecast",
    "{now} UTC 무렵 — GFS {from} ↔ {to}": "around {now} UTC — GFS {from} ↔ {to}",
    "{t} 분석": "{t} analysis",
    "{t} 예보": "{t} forecast",
    "기본 지질도": "Geological maps",
    "추가 지질도": "More maps",
    "오픈API 로 그려지는지 아직 대조하지 않았다": "Not yet checked against the Open API",
    "위로": "Move up",
    "아래로": "Move down",
    "범": "L",
    "범례를 펼친다": "Show legend",
    "{title} 범례": "{title} legend",
    "범례를 받지 못했다": "Could not load the legend",
    "이 레이어가 있는 곳으로 범위를 맞춘다": "Zoom to this layer's extent",
    "끈다": "Turn off",
    "끌어서 차례를 바꾼다": "Drag to reorder",
    "실험 기능": "Experimental features",
    "켬": "On",
    "다 여물지 않은 기능을 먼저 써 본다. 지금은 실험 중인 기능이 없다 — 3D 보기는 상시 기능이 되었다.":
        "Try features that are not finished yet. Nothing is experimental right now — 3D view is now a regular feature.",
    "3D 로 본다 — 지금 보던 자리를 연다": "View in 3D — opens where you are",
    "이 지역에는 3D 로 얹을 지질 레이어가 없다": "No geology layer for 3D in this region",
    # 남극 탭의 "자세" — 우리 기지로 (049)
    "장보고": "Jang Bogo",
    "세종": "Sejong",
    "장보고과학기지로 간다 — 74°37′26″S 164°13′44″E": "Go to Jang Bogo Station — 74°37′26″S 164°13′44″E",
    "세종과학기지로 간다 — 62°13′22″S 58°47′18″W": "Go to King Sejong Station — 62°13′22″S 58°47′18″W",
    # 달 (devlog 036, P05). 대돌여지도 아이콘의 숨은 차림에서 들어간다
    "달": "Moon",
    "지질": "Geology",
    "지형": "Terrain",
    "범례": "Legend",
    "지질 단위": "Geologic units",
    "지질 경계": "Geologic contacts",
    "선 구조 (능선·열구·단층)": "Linear features (ridges, rilles, faults)",
    "LRO 광각 카메라 영상": "LRO Wide Angle Camera mosaic",
    "고해상 영상 (Kaguya 지형 카메라 + LRO 광각)": "High-resolution imagery (Kaguya Terrain Camera + LRO WAC)",
    "LOLA 표고 음영": "LOLA hillshade",
    "루나 오비터 모자이크 (1966–67)": "Lunar Orbiter mosaic (1966–67)",
    "클레멘타인 750 nm 모자이크 (1994)": "Clementine 750 nm mosaic (1994)",
    "마리너 10 모자이크 (1974–75)": "Mariner 10 mosaic (1974–75)",
    "LOLA 표고로 세운다": "Raise with LOLA elevation",
    "앞면 한가운데로": "Back to the centre of the near side",
    "지명·착륙지 찾기 (Tycho, Apollo 11 …)": "Find a place or landing site (Tycho, Apollo 11 …)",
    "찾은 것이 없다": "Nothing found",
    "범례를 받지 못했다": "Could not get the legend",
    "끌면 돌고, 휠로 가까이 간다. 오른쪽 단추나 Ctrl+끌기로 기울인다. 누르면 그 자리의 지질 단위를 읽는다.":
        "Drag to turn, wheel to zoom. Right-drag or Ctrl+drag to tilt. Click to read the geologic unit there.",
    "영상·지질도·표고: NASA Moon Trek (LRO LROC·LOLA, USGS Astrogeology).":
        "Imagery, geology and elevation: NASA Moon Trek (LRO LROC, LOLA, USGS Astrogeology).",
    "지구로 돌아간다": "Back to Earth",
    "달 위도 {lat}° · 경도 {lon}°": "Lunar lat {lat}° · lon {lon}°",
    "읽는 중": "Reading…",
    "여기에는 지질 단위가 없다": "No geologic unit here",
    "속성을 받지 못했다": "Could not get the attributes",
    "닫기": "Close",
    # 달 화면을 2D 의 틀로 (038)
    "지구": "Earth",
    "구": "Globe",
    "평면": "Flat",
    "앞면": "Near side",
    "북쪽 위": "North up",
    "도구": "Tools",
    "이동": "Go",
    "구에서만": "globe only",
    "구와 평면을 오간다": "Switch between globe and flat map",
    "기울기와 방위를 풀고 곧장 내려다본다": "Reset tilt and heading and look straight down",
    "곧장 내려다보며 가까이 가면 평면으로, 멀어지면 다시 구로 넘어간다. 기울이면 구에 머문다.":
        "Zoom in looking straight down to switch to the flat map; zoom out to return to the globe. Tilting keeps the globe.",
    "달 위경도": "Lunar lat, lon",
    "달 지질 단위": "Lunar geologic units",
    "달 지질 (USGS 1:500만, 2020)": "Lunar geology (USGS 1:5M, 2020)",
    "달에 얹은 내 것": "My data on the Moon",
    "바깥 자료를 달에": "Outside data onto the Moon",
    "좌표·지명·착륙지로 이동 — -43.31, -11.36 · Tycho · Apollo 11":
        "Go to coordinates, a place or a landing site — -43.31, -11.36 · Tycho · Apollo 11",
    "좌표는 달의 위도·경도(도)다. 평면 좌표계는 받지 않는다.":
        "Coordinates are lunar latitude and longitude in degrees. Projected coordinate systems are not accepted.",
    "{n}점을 올렸다": "Uploaded {n} points",
    # 달 지질도 원도 (039)
    "원도 파일이 없다": "The original maps file is missing",
    "SPA 지질도 파일이 없다": "The SPA geologic map file is missing",
    "달 지질 원도 (USGS 1:500만, 1971–1979)": "Lunar geology, original maps (USGS 1:5M, 1971–1979)",
    "원도 지질 단위": "Original map units",
    "원도 구조선": "Original map structures",
    "원도 — 29 갈래로 묶은 색": "Original maps — 29 colour groups",
    "구조선": "Structures",
    # 달 착륙지 (046)
    "착륙지": "Landing sites",
    "착륙·충돌 지점": "Landing and impact sites",
    "아폴로 EVA 동선": "Apollo EVA traverses",
    "착륙지 고해상 사진 (LRO NAC)": "Landing-site close-ups (LRO NAC)",
    # NASA Trek 판 목록 (060) — 판 제목·레이어군은 씨앗이 영어·한글을 다 싣는다
    "NASA Trek 판": "NASA Trek products",
    "판 이름으로 거르기": "Filter by name",
    "보는 자리를 덮는 것만": "Only those covering this spot",
    "좁은 곳만 덮는 판": "Regional products",
    "맞는 판이 없다": "No matching products",
    # 지질도Navi 판 (wetherilli 171)
    "{series} · {sheet}": "{series} · {sheet}",
    "지질도Navi 판": "GSJ Geomap Navi sheets",
    "범례 그림을 새 창에서 크게 본다": "Open the legend image in a new window",
    "판 목록을 받지 못했다": "Could not load the sheet list",
    "{n} 판 가운데 앞의 {m} 판만 — 더 좁혀 거른다": "Showing the first {m} of {n} — narrow the filter",
    "판 목록이 아직 없다": "No product list yet",
    "범례가 없다": "No legend",
    "그런 레이어는 없다": "No such layer",
    "여기에는 속성이 없다": "Nothing here",
    "유인 착륙": "Crewed landing",
    "연착륙": "Soft landing",
    "로버": "Rover",
    "충돌": "Impact",
    "종류": "Type",
    "날짜": "Date",
    "임무": "Mission",
    "사람": "Crew",
    # 달 영상 보정 (042)
    "영상 보정": "Image adjustment",
    "밝기": "Brightness",
    "대비": "Contrast",
    "감마": "Gamma",
    "채도": "Saturation",
    "고침": "adjusted",
    "선명하게": "Crisp",
    "지형 강조": "Relief",
    "되돌리기": "Reset",
    "LOLA 음영 겹치기 — 영상 위에 지형의 그늘을 곱한다": "Overlay LOLA hillshade — multiply terrain shading onto the image",
    # 달 도구·자세 (041)
    "자세": "View",
    "달 위도": "Lunar lat", "달 경도": "Lunar lon",
    "자전축": "Axis",
    "시대 모름": "Age unknown",
    # 화성 (058) — 달 화면을 옮긴 것. 달과 같은 문장은 위의 것을 함께 쓴다
    "화성": "Mars",
    "화성 위도": "Mars lat", "화성 경도": "Mars lon",
    "화성 위도 {lat}° · 경도 {lon}°": "Mars lat {lat}° · lon {lon}°",
    "VWorld 가 거절했다": "VWorld refused the request",
    # 연속값 색 — 그린란드 지화학 (wetherilli 159)
    "칠할 원소": "Colour by",
    "분위수로 나눈 칸": "quantile classes",
    "검출 한계 밑": "Below detection limit",
    "검출 한계 밑 (< {n})": "Below detection limit (< {n})",
    "분석하지 않음": "Not analysed",
    "분석하지 않은 {n}점은 그리지 않았다": "{n} points not analysed are not drawn",
    "Fe₂O₃ (전철)": "Fe₂O₃ (total)",
    "강열 감량": "LOI",
    "Fe (전철)": "Fe (total)",
    "휘발분": "Volatiles",
    # 수성 화면 (wetherilli P10)
    "수성": "Mercury",
    "수성 위도": "Mercury lat", "수성 경도": "Mercury lon",
    "수성 위도 {lat}° · 경도 {lon}°": "Mercury lat {lat}° · lon {lon}°",
    "MESSENGER 모자이크 (2013)": "MESSENGER mosaic (2013)",
    "MESSENGER 모자이크 BDR (고해상)": "MESSENGER BDR mosaic (high resolution)",
    "MESSENGER 강조색 모자이크": "MESSENGER enhanced-color mosaic",
    "MESSENGER 표고 색 음영": "MESSENGER elevation color hillshade",
    "MESSENGER 표고로 세운다": "Raise terrain from MESSENGER elevation",
    "표고 음영 겹치기 — 영상 위에 지형의 그늘을 곱한다": "Overlay hillshade — multiply terrain shading over the imagery",
    "경도 0°·위도 0° 로 — 본초 자오선 둘레(훈 칼 크레이터가 서경 20°)":
        "To 0° lon, 0° lat — around the prime meridian (set by Hun Kal crater at 20° W)",
    "방위 — 바늘이 수성의 북쪽을 가리킨다. 누르면 기울기는 두고 북쪽을 위로 돌린다":
        "Heading — the needle points to Mercury's north. Click to turn north up and keep the tilt",
    "수성의 자전축 — 북극과 남극을 잇는 선을 켜고 끈다": "Mercury's spin axis — show or hide the line through the poles",
    "수성에 얹은 내 것": "My data on Mercury",
    "바깥 자료를 수성에": "Outside data onto Mercury",
    "좌표는 수성의 위도·경도(도, 행성 중심·동경)다. 평면 좌표계는 받지 않는다.":
        "Coordinates are Mercury latitude/longitude (degrees, planetocentric, east-positive). Projected coordinates are not accepted.",
    "영상·표고: NASA Mercury Trek (MESSENGER MDIS — NASA/JHUAPL/Carnegie Institution of Washington, USGS Astrogeology).":
        "Imagery and elevation: NASA Mercury Trek (MESSENGER MDIS — NASA/JHUAPL/Carnegie Institution of Washington, USGS Astrogeology).",
    "좌표·지명으로 이동 — 31.5, 162.7 · Caloris · Rembrandt": "Go to coordinates or a name — 31.5, 162.7 · Caloris · Rembrandt",
    "화면 한가운데 점에서 본 기울기(곧장 내려다봄 0°)와 방위(수성의 북쪽 0°)":
        "Tilt (0° straight down) and heading (0° Mercury's north) seen from the point at screen centre",
    "표고 채우기 — MESSENGER 표고에서 점마다 높이를 읽는다 (반지름 2 439.4 km 구)":
        "Fill elevation — read each point's height from MESSENGER elevation (2,439.4 km sphere)",
    "화성에 얹은 내 것": "Yours on Mars",
    # 화성 크레이터 (067)
    "크레이터 (Robbins 2012)": "Craters (Robbins 2012)",
    "크레이터 — 지름 1 km 넘는 것": "Craters — larger than 1 km",
    "보존 상태": "Preservation state",
    "4 — 갓 생긴 듯하다": "4 — fresh",
    "1 — 많이 닳았다": "1 — heavily degraded",
    "매기지 않음": "not classified",
    "크레이터 파일이 서버에 없다": "The crater file is not on the server",
    # 온 지구 (wetherilli P06·086)
    "온 지구": "Whole Earth",
    "온 지구 지질도 (Macrostrat)": "Whole-Earth geologic map (Macrostrat)",
    "Blue Marble — 지형 음영·바다 깊이": "Blue Marble — shaded relief and bathymetry",
    "Blue Marble — 위성 영상 그대로": "Blue Marble — satellite imagery",
    "Blue Marble — 육지 음영": "Blue Marble — land relief",
    "바깥 자료를 지구에": "Outside data onto the Earth",
    "지구에 얹은 내 것 — 지역 탭과 같다": "Mine on the Earth — the same as in the region tabs",
    "좌표는 WGS84 위도·경도(도)다. 평면 좌표계는 지역 탭의 불러오기에서 받는다.":
        "Coordinates are WGS84 latitude/longitude (degrees). Projected systems are accepted by the loader in the region tabs.",
    "방위 — 바늘이 지구의 북쪽을 가리킨다. 누르면 기울기는 두고 북쪽을 위로 돌린다":
        "Heading — the needle points to the Earth's north. Click to turn north up and keep the tilt",
    "지구의 자전축 — 북극과 남극을 잇는 선을 켜고 끈다": "The Earth's spin axis — show or hide the line from pole to pole",
    "화면 한가운데 점에서 본 기울기(곧장 내려다봄 0°)와 방위(지구의 북쪽 0°)":
        "Tilt (0° straight down) and heading (0° to the Earth's north) seen from the point at the centre of the view",
    "처음 자리로 — 한반도를 멀리서": "Back to the start — the Korean Peninsula from afar",
    "좌표로 이동 — 위도, 경도 (37.57, 126.98)": "Go to coordinates — latitude, longitude (37.57, 126.98)",
    "위도 {lat}° · 경도 {lon}°": "Lat {lat}° · Lon {lon}°",
    "표고 타일로 세운다 (SRTM·GMTED·ETOPO1)": "Raise with elevation tiles (SRTM, GMTED, ETOPO1)",
    "색은 시대의 색이다 — 세·절까지 가른 단위는 조금 다르다":
        "Colours are the colours of the age — units dated to an epoch or stage differ a little",
    "지질도: Macrostrat (CC BY 4.0). 영상: NASA EOSDIS GIBS Blue Marble. 표고: Mapzen/AWS Terrain Tiles.":
        "Geology: Macrostrat (CC BY 4.0). Imagery: NASA EOSDIS GIBS Blue Marble. Elevation: Mapzen/AWS Terrain Tiles.",
    # 그때의 자리 (wetherilli 087)
    "그때의 자리": "Then",
    "그때의 자리 ({age} Ma)": "Then ({age} Ma)",
    "옮긴다": "Carry",
    "PALEOMAP 2016 판 회전으로 셈한 것이다 — 관측이 아니다":
        "Computed with the PALEOMAP 2016 plate rotations — not an observation",
    "바다 밑이다 — 대륙 다각형이 없어 옮기지 못한다": "Ocean floor — no continental polygon to carry it",
    "앞날은 셈하지 않는다": "The future is not computed",
    "이 판은 {reach} Ma 까지만 거슬러 옮긴다": "This plate is carried back to {reach} Ma only",
    "lat·lon·age 가 없다": "lat, lon and age are missing",
    "판 회전 파일이 서버에 없다": "The plate rotation file is not on the server",
    # EarthThruTime3D 로 건너가기 (wetherilli 088)
    "ETT 에서 {age} Ma": "{age} Ma in ETT",
    "EarthThruTime3D 의 고지리 지구본에서 이 자리를 그 연대로 본다 — 새 창":
        "See this place at that age on the EarthThruTime3D palaeogeographic globe — new window",
    # 시간 축 (wetherilli 091)
    "연대": "Age",
    "오늘": "Today",
    "연대를 넣는다 — 250, 20 ka, 1.2 Ga": "Type an age — 250, 20 ka, 1.2 Ga",
    "오늘로 — 연대를 0 으로": "Back to today — age 0",
    "판 조각 (PALEOMAP 2016)": "Plate pieces (PALEOMAP 2016)",
    "판 조각 경계": "Plate piece outlines",
    "PALEOMAP 2016 판 회전으로 셈한 그때의 지구": "The Earth then, computed with the PALEOMAP 2016 plate rotations",
    "PALEOMAP 2016 판 회전으로 셈한 그때의 지구다 — 관측이 아니다. 다른 판 모델과는 100 Ma 에 1 000 km 안팎 다르다. 오늘의 영상·지형·지질도는 오늘에만 뜬다":
        "The Earth then, computed with the PALEOMAP 2016 plate rotations — not an observation. "
        "Other plate models differ by around 1,000 km at 100 Ma. "
        "Today's imagery, terrain and geology appear only at the present",
    "오늘의 지구다 — 1 Ma 안에서 판이 움직인 것은 수십 km 안이다":
        "Today's Earth — within 1 Ma the plates moved a few tens of kilometres at most",
    "그때의 지구 · {age}": "The Earth then · {age}",
    "오늘의 그 자리로": "Go to that place today",
    "오늘 그 자리의 지질 단위": "Geologic units there today",
    "판 조각 밖이다 — 그때 바다였거나, 섭입으로 사라진 곳이다":
        "Outside the plate pieces — ocean then, or crust since lost to subduction",
    "판": "Plate",
    "오늘의 자리": "Today",
    "거슬러 옮기는 끝": "Carried back to",
    "이 조각은 오늘까지 남지 않았다 — 오늘의 자리는 그 판이 가 있을 곳이다":
        "This piece does not survive to the present — 'today' is where its plate would be",
    # 옛 해안선 (wetherilli 097)
    "그때의 지구": "The Earth then",
    "구조·판": "Tectonics", "자원": "Resources", "지구물리": "Geophysics", "화산·지진": "Volcanoes and earthquakes", "화석·고생태": "Fossils and palaeoecology", "지리": "Geography",
    "옛 해안선": "Palaeocoastlines",
    "옛 해안선은 이 연대에 없다 (0–535 Ma, 가까운 시점 10 Myr 안)":
        "No palaeocoastline for this age (0–535 Ma, nearest within 10 Myr)",
    "옛 해안선은 {age} Ma 의 것 — 화석이 가리키는 가장 깊은 바다":
        "Palaeocoastline of {age} Ma — the furthest reach of the sea that fossils indicate",
    # 화석 산지 (wetherilli 098)
    "PBDB 의 옛 자리": "Palaeoposition by PBDB",
    "화석 산지 (PBDB)": "Fossil collections (PBDB)",
    "화석 산지": "Fossil collections",
    "PBDB 에서 보기": "Open in PBDB",
    "산지 {n} 곳 가운데 가까운 것부터": "Nearest of {n} collections",
    # 홀로세 화산 (wetherilli 134)
    "화산 (GVP)": "Volcanoes (GVP)",
    "홀로세 화산": "Holocene volcanoes",
    "플라이스토세 화산": "Pleistocene volcanoes",   # wetherilli 194
    "플라이스토세 화산 — 분화 기록이 없다": "Pleistocene volcano — no eruption on record",   # wetherilli 194
    "플라이스토세": "Pleistocene",   # wetherilli 194
    "세모의 색은 마지막 분화": "Triangle colour is the last eruption",
    "화산 {n} 곳 가운데 가까운 것부터": "Nearest of {n} volcanoes",
    "GVP 에서 보기": "Open in GVP",
    "1900 년부터": "Since 1900",
    "1500–1899 년": "1500–1899",
    "서기 1–1499 년": "1–1499 CE",
    "기원전 (홀로세)": "BCE (Holocene)",
    "분화 기록이 없다": "No recorded eruption",
    "기원전 {n} 년": "{n} BCE",
    "{n} 년": "{n} CE",
    # 지진 (wetherilli 138)
    "지진 (USGS)": "Earthquakes (USGS)",
    "M6 이상": "M6 and above",
    "M5.5–6": "M5.5–6",
    "M5–5.5": "M5–5.5",
    "얕은 지진 (0–70 km)": "Shallow (0–70 km)",
    "중간 깊이 (70–300 km)": "Intermediate (70–300 km)",
    "깊은 지진 (300 km 넘게)": "Deep (over 300 km)",
    "원의 크기는 규모, 색은 진원 깊이": "Circle size is magnitude, colour is focal depth",
    "M{mag} 지진": "M{mag} earthquake",
    "M{mag} 최근 지진": "M{mag} recent earthquake",
    # 앨버타 광물 산지 (wetherilli 321)
    "금속 광물": "Metallic minerals", "산업 광물": "Industrial minerals", "리튬 (지하수·지층수)": "Lithium (groundwater and formation water)",
    "규사": "Silica sand", "비에너지 광물 생산자": "Non-energy mineral producers", "광물 코어": "Mineral cores",
    "앨버타 광물 산지를 받지 못했다": "Could not fetch Alberta mineral occurrences",
    "원본 자료 — USGS 실시간 피드(지난 7 일 M2.5 이상, 매시 받음), 공공 영역": "Source — USGS real-time feed (past 7 days M2.5+, fetched hourly), public domain",
    "최근 지진 피드를 아직 받지 않았다 (fetch_recent_quakes)": "Recent earthquake feed not fetched yet (fetch_recent_quakes)",
    "지난 한 시간": "Past hour", "지난 하루": "Past day", "지난 일주일": "Past week",
    "원본 자료 — IHFC 세계 지열류 자료 2024, CC BY 4.0": "Source — IHFC Global Heat Flow Database 2024, CC BY 4.0",
    "지열류 자료를 아직 굽지 않았다 (build_heatflow)": "Heat flow data not built yet (build_heatflow)",
    "최근 지진 (7 일, M2.5 이상)": "Recent earthquakes (7 days, M2.5+)",
    "속이 빈 고리 — 크기는 규모, 색은 지난 시간 (매시 받음)": "Hollow rings — size is magnitude, colour is time since (fetched hourly)",
    "그 밖의 {n} 지역": "{n} more regions",          # 소개 화면의 지역 칩 (wetherilli 344)
    "범례 {n}": "legends {n}",                   # 관리 화면의 대조 줄 (wetherilli 367)
    "깨진 범례 {n}": "broken legends {n}",
    "산지 수(채집 편향이 든다)": "locality counts (sampling bias included)",   # 온 지구 레이어의 곁말 (wetherilli 360)
    "모의 결과": "model result",
    "명령 {n}": "commands {n}",                 # 관리 화면의 상류 표 (wetherilli 363)
    "괄호 안의 명령은 화면이 아니라 서버의 명령(레이어 대조·미리 데우기·자료 받기)이 낸 호출이다 — 화면 쓰임은 건수에서 그것을 뺀 것이다.":
        "Commands in brackets are calls made by server commands (layer checks, prewarming, data fetches), not by the viewer — viewer use is the count minus that.",
    # 관리 화면의 마지막 레이어 대조 (wetherilli 314)
    "마지막 레이어 대조 {day} — 그림 {drawn} · 빈 그림 {empty} · 오류 {error} · 건너뜀 {skipped}":
        "Last layer check {day} — drawn {drawn} · empty {empty} · error {error} · skipped {skipped}",
    "앞의 대조보다 새로 깨진 것 {n}": "Newly broken since the previous check: {n}", "고쳐진 것 {n}": "Fixed: {n}",
    "자세한 것은 manage.py verify_layers --diff": "Details: manage.py verify_layers --diff",
    "레이어 대조 기록이 아직 없다 (manage.py verify_layers --redo)": "No layer check recorded yet (manage.py verify_layers --redo)",
    # 관리 화면의 상류 응답 시간 (wetherilli 295)
    "상류 응답 시간": "Upstream response times",
    "지난 7 일의 평균이 느린 차례 — 시간은 상류가 응답의 머리를 보내기까지": "Slowest first by the 7-day mean — time until the upstream sends the response headers",
    "상류": "Upstream", "지난 7 일": "Past 7 days", "건수": "Calls", "실패": "Failed", "평균 (초)": "Mean (s)",
    "아직 센 것이 없다": "Nothing counted yet",
    "p95 는 시간 칸(0.5·1·2·3·5·8·13·21·34 초)에서 어림한 위 끝이다. 실패는 차단 조짐을 함께 센다. 서버 쪽에서는 manage.py upstream_stats 로 같은 값을 본다.":
        "p95 is the upper edge of the time band (0.5 · 1 · 2 · 3 · 5 · 8 · 13 · 21 · 34 s) it falls in. Failures include block signs. On the server, manage.py upstream_stats shows the same figures.",
    "지진 {n} 곳 가운데 가까운 것부터": "Nearest of {n} earthquakes",
    "USGS 에서 보기": "Open at USGS",
    # 제4기 고생태 산지 (wetherilli 139)
    "고생태 산지 (Neotoma)": "Paleoecology sites (Neotoma)",
    "꽃가루": "Pollen",
    "척추동물": "Vertebrate fauna",
    "식물 큰화석": "Plant macrofossils",
    "규조·작은 생물": "Diatoms & small organisms",
    "그 밖 (숯·지화학·연대 측정 …)": "Other (charcoal, geochemistry, dating …)",
    "자료 {n} 건 더": "{n} more datasets",
    "점의 색은 자료형 — 옛 연대에는 그 연대를 품은 산지만": "Dot colour is the dataset type — at past ages, only sites spanning that age",
    "산지 {n} 곳 가운데 가까운 것부터 (Neotoma)": "Nearest of {n} sites (Neotoma)",
    "Neotoma 에서 보기": "Open in Neotoma Explorer",
    # 지각 두께 (wetherilli 101)
    "지각 (CRUST 2.0)": "Crust (CRUST 2.0)",
    "지각 두께": "Crustal thickness",
    "약 {km} km — CRUST 2.0, 2° 칸의 모형이다": "About {km} km — CRUST 2.0, a model on 2° cells",
    # 영어판 새는 곳 (wetherilli 341)
    "© 한국지질자원연구원": "© KIGAM",
    "국토지리원": "GSI Japan",
    "(손으로 둔다)": "(placed by hand)",
    # 구운 파일 칸 (wetherilli 312 — 데이터소스 탭에 녹았다)
    "파일": "File",
    "고친 날": "Modified",
    "없다": "Missing",
    "없다 (밖에 연 판에는 두지 않는다)": "Absent (not kept on the public build)",
    "{n} 칸": "{n} entries",
    "남극 자력 이상 ADMAP-2": "Antarctic magnetic anomalies ADMAP-2",
    "남극 GeoMAP": "Antarctic GeoMAP",
    "남극 해저·빙저 지형 IBCSO v2": "Antarctic seafloor and subglacial topography IBCSO v2",
    "얀마옌 지질도": "Jan Mayen geological map",
    "카리브 대앤틸리스 지질도": "Greater Antilles geological map",
    "화석 산지 PBDB": "Fossil localities PBDB",
    "홀로세 화산 GVP": "Holocene volcanoes GVP",
    "플라이스토세 화산 GVP": "Pleistocene volcanoes GVP",
    "지진 USGS M5 이상": "Earthquakes USGS M5+",
    "최근 지진": "Recent earthquakes",
    "제4기 고생태 산지 Neotoma": "Quaternary palaeoecology sites Neotoma",
    "맨틀 슬랩": "Mantle slabs",
    "지각 응력": "Crustal stress",
    "광상": "Mineral deposits",
    "활성 단층 GEM": "Active faults GEM",
    "세계 빙하 RGI 7.0": "World glaciers RGI 7.0",
    "지금의 바람·구름 GFS": "Current wind and clouds GFS",
    "위성 구름 GMGSI": "Satellite clouds GMGSI",
    "지난 바람 ERA5": "Past wind ERA5",
    "해류 ECCO2": "Ocean currents ECCO2",
    "달 지질도 원도": "Lunar geological map originals",
    "남극–에이트켄 분지 지질도": "South Pole–Aitken basin geological map",
    "화성 크레이터": "Mars craters",
    "화성 옛 지질도": "Mars legacy geological maps",
    "수성 지질도": "Mercury geological map",
    "극지연구소 암석 시료": "KOPRI rock samples",
    "극지연구소 KPDC 자료": "KOPRI KPDC datasets",
    "아라온호 지난 1 년": "Araon past year",
    "KIGAM 자료 목록": "KIGAM data list",
    "KIGAM 5만 구조 요소": "KIGAM 1:50k structural elements",
    "브라질 지질 단위 이름표": "Brazil geological unit labels",
    "한반도 지질도 음영판": "Korean Peninsula geological map (shaded)",
    "한반도 지질도 민판": "Korean Peninsula geological map (plain)",
    "중국 USGS geo3al": "China USGS geo3al",
    "대만 지질운 열린자료": "Taiwan Geology Cloud open data",
    # 대만 지질운 열린자료 (wetherilli 305)
    "5만 탄층": "1:50k coal seam",
    "GPS 상시 관측소": "Continuous GPS station",
    "토석류 퇴적 구역": "Debris-flow deposition zone",
    "토석류 선상 구역": "Debris-flow fan zone",
    "토석류 유동 구역": "Debris-flow track zone",
    "등급 {grade}": "Class {grade}",
    "등급 없음": "No class",
    "등급 {grade} — 가장 단단한 쪽 (암상으로 짐작)": "Class {grade} — strongest (inferred from lithology)",   # 대만 암체 강도 등급 (wetherilli 370)
    "등급 {grade} — 가장 무른 쪽 (암상으로 짐작)": "Class {grade} — weakest (inferred from lithology)",
    "I 단단 → VII 무름 (암상으로 짐작)": "I strong → VII weak (inferred from lithology)",
    "활동 적지 않음": "Activity not recorded",
    "대만 지질운 열린자료가 서버에 없다": "Taiwan Geology Cloud open data is not on the server",
    "대만 지질운 열린자료를 읽지 못했다": "Could not read Taiwan Geology Cloud open data",
    # 세계 빙하 RGI 7.0 (wetherilli 289)
    "빙하 하나하나 (RGI 7.0)": "Individual glaciers (RGI 7.0)",
    "바다에서 끝난다 (조수 빙하)": "Marine-terminating (tidewater)",
    "빙하 (끝의 갈래를 가리지 않았다)": "Glacier (terminus type not assigned)",
    "서지 가능": "Possible surge",
    "서지 그럴듯": "Probable surge",
    "서지 관측": "Observed surge",
    "이름 없는 빙하": "Unnamed glacier",
    "여기에는 빙하가 없다": "No glacier here",
    "넓이만 한 점 — 줌 3 부터. 넓게 볼 때는 빙하·빙붕(Natural Earth)": "Dots sized by area — from zoom 3. Zoomed out, see Glaciers and ice shelves (Natural Earth)",
    # 충돌구·거대 화성암 지대 (wetherilli 283)
    "충돌구·거대 화성암 지대": "Impact craters & large igneous provinces", "충돌구": "Impact craters",
    "거대 화성암 지대 (LIP)": "Large igneous provinces (LIP)", "충돌구 — 원의 크기는 지름": "Impact crater — circle size shows diameter",
    "이름 없는 화성암 지대": "Unnamed igneous province", "판 회전으로 옮긴다": "Moved with plate rotation",
    "바다 밑이라 옮기지 않는다": "On the sea floor — not moved", "여기에는 없다": "Nothing here",
    "색은 생긴 때. 대륙 위의 것은 판 회전으로 그때의 자리에 — 계산이지 관측이 아니다":
        "Colour shows emplacement age. Continental ones move with plate rotation — computed, not observed",
    "신생대 (66 Ma 안쪽)": "Cenozoic (under 66 Ma)", "데본기·실루리아기": "Devonian–Silurian", "오르도비스기·캄브리아기": "Ordovician–Cambrian",
    "원생대": "Proterozoic",
    # 화석 산지 밀도 (wetherilli 286)
    "화석 산지 밀도": "Fossil locality density",
    "드물다": "Sparse",
    "몇 곳": "A few",
    "많다": "Many",
    "가장 많은 칸": "Densest cell",
    "1° 칸의 산지 수(로그) — 조사가 몰린 곳이 진하다": "Localities per 1° cell (log) — darker where sampling concentrates",
    # 세계 활성단층 GEM (wetherilli 279)
    "활성단층 (GEM)": "Active faults (GEM)", "역단층·섭입": "Reverse / subduction", "주향이동·변환": "Strike-slip / transform",
    "사교 (주향이동+경사이동)": "Oblique (strike-slip + dip-slip)", "확장 해령": "Spreading ridge", "습곡·갈래 모름": "Fold / unknown",
    "이름 없는 단층": "Unnamed fault", "여기에는 활성단층이 없다": "No active fault here",
    # 세계 광상 USGS (wetherilli 276)
    "세계 광상 (USGS)": "Mineral deposits (USGS)", "이름 없는 곳": "Unnamed site",
    "구리": "Copper", "금·은·백금족": "Gold, silver and PGE", "납·아연": "Lead and zinc", "철·합금 금속": "Iron and ferro-alloy metals",
    "핵심·에너지 광물": "Critical and energy minerals", "산업 광물": "Industrial minerals",
    "USGS 세계 반암동 광상": "USGS global porphyry copper deposits", "USGS 세계 퇴적암 호스트 구리 광상": "USGS global sediment-hosted copper deposits",
    "USGS 세계 화산성 괴상 황화물(VMS) 광상": "USGS global volcanogenic massive sulfide (VMS) deposits",
    "USGS 세계 포디폼 크로마이트 광상": "USGS global podiform chromite deposits", "USGS 세계 희토류 광상": "USGS global rare earth element deposits",
    "USGS 세계 퇴적암 호스트 납·아연 광상": "USGS global sediment-hosted zinc-lead deposits",
    "대규모": "Large", "중규모": "Medium", "소규모": "Small",
    "마름모는 세계 광상 표와 대규모 광산, 큰 원은 생산한 곳, 작은 원은 산지·탐사지(줌 4 부터)":
        "Diamonds: global deposit tables and large mines; large circles: past or current producers; small circles: occurrences and prospects (from zoom 4)",
    "광상 {n} 곳 가운데 크고 가까운 것부터 (USGS)": "Largest and nearest of {n} sites (USGS)",
    # 지각 응력 World Stress Map 2025 (wetherilli 273)
    "지각 응력 (World Stress Map)": "Crustal stress (World Stress Map)", "최대 수평 응력 방향": "Maximum horizontal stress",
    "막대는 최대 수평 응력 방향, 길이는 품질(A–D)": "Bars show S_Hmax orientation; length shows quality (A–D)",
    "응력 N{azi}°E": "Stress N{azi}°E", "측정 {n} 곳 가운데 가까운 것부터 (WSM)": "Nearest of {n} measurements (WSM)",
    "World Stress Map (GFZ)": "World Stress Map (GFZ)",
    "정단층형": "Normal faulting", "정단층·주향이동형": "Normal with strike-slip", "주향이동형": "Strike-slip faulting",
    "역단층·주향이동형": "Thrust with strike-slip", "역단층형": "Thrust faulting", "체제 모름": "Unknown regime",
    "단일 지진 초점 메커니즘": "Single focal mechanism", "평균 초점 메커니즘": "Average focal mechanism",
    "초점 메커니즘 역산": "Focal mechanism inversion", "시추공 붕락": "Borehole breakouts", "시추공 붕락 (캘리퍼)": "Borehole breakouts (caliper)",
    "시추공 붕락 (영상)": "Borehole breakouts (imaging)", "시추공 미끄럼": "Borehole slotter", "시추 유도 인장 균열": "Drilling-induced tensile fractures",
    "수압 파쇄": "Hydraulic fracturing", "수압 파쇄 (지구물리)": "Hydraulic fracturing (geophysical)",
    "수압 파쇄 (탄성 역산)": "Hydraulic fracturing (elastic inversion)", "수압 파쇄 (기존 균열)": "Hydraulic tests on pre-existing fractures",
    "코어 덧씌워 떼기": "Overcoring", "지질 — 단층 미끄럼 역산": "Geology — fault-slip inversion", "지질 — 단층 미끄럼": "Geology — fault slip",
    "지질 — 단층 미끄럼 (단일)": "Geology — single fault slip", "지질 — 화산 배열": "Geology — volcanic vent alignment", "횡파 분리": "Shear-wave splitting",
    # 판 경계·세계 지질구 Hasterok 2022 (wetherilli 272)
    "판·지질구 (Hasterok 2022)": "Plates & provinces (Hasterok 2022)", "판 경계": "Plate boundaries", "세계 지질구": "Geologic provinces",
    "여기에는 지질구가 없다": "No geologic province here",
    "확장 중심 (해령)": "Spreading centre (ridge)", "확장대·열곡": "Extensional zone / rift", "섭입대": "Subduction zone",
    "충상 (대륙 충돌)": "Thrust (continental collision)", "좌수향 변환 단층": "Sinistral transform", "우수향 변환 단층": "Dextral transform",
    "추정 경계": "Inferred boundary",
    "강괴 (크라톤)": "Craton", "순상지": "Shield", "수동형 대륙 연변": "Passive margin", "부가 복합체": "Accretionary complex", "분지": "Basin",
    "전면 분지": "Foredeep basin", "조산대": "Orogenic belt", "좁은 열곡": "Narrow rift", "넓은 열곡": "Wide rift", "화산호": "Volcanic arc",
    "배호 분지": "Back-arc basin", "오피올라이트 복합체": "Ophiolite complex", "거대 화성 구역": "Magmatic province", "해양 고원": "Oceanic plateau",
    "해양 배호 분지": "Oceanic back-arc basin", "해양 지각": "Oceanic crust", "대륙 지각": "Continental crust", "전이 지각": "Transitional crust",
    # 세계 암상 GLiM·지열류 IHFC (wetherilli 267)
    "암상 (GLiM)": "Lithology (GLiM)", "세계 암상": "Global lithology",
    "{name} — GLiM, 0.5° 칸에서 가장 넓은 암상": "{name} — GLiM, the most extensive lithology in the 0.5° cell",
    "0.5° 칸에서 가장 넓은 암상이다": "The most extensive lithology in each 0.5° cell",
    "미고결 퇴적물": "Unconsolidated sediments", "염기성 화산암": "Basic volcanic rocks", "쇄설성 퇴적암": "Siliciclastic sedimentary rocks",
    "염기성 심성암": "Basic plutonic rocks", "혼합 퇴적암": "Mixed sedimentary rocks", "탄산염 퇴적암": "Carbonate sedimentary rocks",
    "산성 화산암": "Acid volcanic rocks", "산성 심성암": "Acid plutonic rocks", "중성 화산암": "Intermediate volcanic rocks",
    "화산쇄설암": "Pyroclastics", "중성 심성암": "Intermediate plutonic rocks", "증발암": "Evaporites", "빙하·만년설": "Ice and glaciers",
    "자료 없음": "No data", "물": "Water bodies",
    "지열류 (IHFC)": "Heat flow (IHFC)", "지열류": "Heat flow",
    "지열류 {q} mW/m²": "Heat flow {q} mW/m²", "측정 {n} 곳 가운데 가까운 것부터 (IHFC)": "Nearest of {n} measurements (IHFC)",
    "IHFC 자료 (GFZ)": "IHFC data (GFZ)",
    "40 mW/m² 아래": "Below 40 mW/m²", "40–60 mW/m²": "40–60 mW/m²", "60–80 mW/m²": "60–80 mW/m²", "80–120 mW/m²": "80–120 mW/m²",
    "120–200 mW/m²": "120–200 mW/m²", "200 mW/m² 넘게": "Above 200 mW/m²",
    # 바다 밑 — 해양 지각 연대·퇴적층 두께 (wetherilli 264)
    "바다 밑 (Seton 2020 · GlobSed)": "Beneath the sea (Seton 2020 · GlobSed)",
    "해양 지각 연대": "Ocean crust age",
    "해저 퇴적층 두께": "Seafloor sediment thickness",
    "여기는 바다 지각이 아니거나 값이 없다": "Not ocean crust here, or no value",
    "약 {ma} Ma — Seton 외 2020, 해령에서 굳은 때": "About {ma} Ma — Seton et al. 2020, when it formed at the ridge",
    "약 {m} m — GlobSed v3, 해저면에서 음향 기반암까지": "About {m} m — GlobSed v3, seafloor to acoustic basement",
    "이 칸에는 값이 없다": "No value in this cell",
    "2° 칸의 모형이다 — 관측이 아니다": "A model on 2° cells — not an observation",
    # 지명·강·호수·빙하 (wetherilli 102)
    "지리 (Natural Earth)": "Geography (Natural Earth)",
    "산맥·바다 이름": "Names of ranges and seas",
    "강·호수": "Rivers and lakes",
    "빙하·빙붕": "Glaciers and ice shelves",
    "좌표·지명으로 이동 — 37.57, 126.98 · 바이칼호 · Andes": "Go to coordinates or a place — 37.57, 126.98 · Baikal · Andes",
    # 빙상 가장자리 (wetherilli 104)
    "최근 빙기": "Last glaciation",
    "빙상 가장자리": "Ice-sheet margins",
    "북미 {ka} ka": "North America {ka} ka",
    "유라시아 {ka} ka": "Eurasia {ka} ka",
    "빙상 가장자리 — {what} (연대 측정을 모은 복원)": "Ice-sheet margins — {what} (a reconstruction from compiled dates)",
    "빙상 가장자리는 25–1 ka 에만 있다": "Ice-sheet margins exist only for 25–1 ka",
    # 맨틀 슬랩 (wetherilli 106)
    "지구 속 (OPT1 모의)": "Earth's interior (OPT1 model)",
    "맨틀 슬랩·하부 더미": "Mantle slabs and basal piles",
    "맨틀 파일이 서버에 없다": "The mantle files are not on the server",
    "맨틀은 OPT1 의 {ma} Ma — 모의 결과이지 관측이 아니다": "Mantle from OPT1 at {ma} Ma — a model result, not an observation",
    "(슬랩 파랑·더미 빨강, 밝을수록 얕다)": "(slabs blue, piles red; lighter is shallower)",
    "(맨틀 기준틀이라 판 조각과 어긋난다)": "(mantle reference frame — offset from the plate pieces)",
    # 그리기가 멈추면 (wetherilli 110)
    "WebGL 문맥을 잃었다": "The WebGL context was lost",
    "구를 더 그리지 못한다": "The globe can no longer be drawn",
    "그래픽 메모리가 모자라거나 GPU 가 다시 시작되면 브라우저가 3D 그리기를 멈춘다. 켠 레이어를 줄이고 다시 연다.":
        "When graphics memory runs out or the GPU restarts, the browser stops 3D drawing. Turn off some layers and reopen.",
    "새로고침": "Reload",
    "지형 세우기와 지구 속을 끄고 다시 연다": "Reopen with terrain and the Earth's interior turned off",
    "지형 세우기를 끄고 다시 연다": "Reopen with terrain turned off",   # 달·화성·수성 (wetherilli 186)
    "지각": "Crust",                                       # 온 지구 높이 그래프의 지각 두께 띠 (wetherilli 186)
    "가볍게 다시 연다": "Reopen lighter",
    "평면 지도는 구와 따로 돈다": "The flat map runs separately from the globe",
    "평면으로": "Go flat",
    # 지구 높이 그래프 (wetherilli 109)
    "국토지리원·AWS 표고 타일에서 읽은 해발 높이 — 바다는 수심(음수)":
        "Height above sea level from GSI and AWS elevation tiles — the sea shows depth (negative)",
    "AWS 표고 타일(SRTM·GMTED)에서 읽은 해발 높이 — 바다는 수심(음수)":
        "Height above sea level from AWS elevation tiles (SRTM, GMTED) — the sea shows depth (negative)",
    # 화성 옛 지질도 (068)
    "화성 USGS 옛 지질도·지역도 (1986–2005)": "Mars USGS original and regional geologic maps (1986–2005)",
    "옛 지질 단위": "Original geologic units",
    "옛 구조선": "Original structures",
    "옛 지질도 파일이 서버에 없다": "The original geologic map file is not on the server",
    "여기에는 지름 1 km 넘는 크레이터가 없다": "No crater larger than 1 km here",
    "바깥 자료를 화성에": "Outside data onto Mars",
    "좌표는 화성의 위도·경도(도, 행성 중심·동경)다. 평면 좌표계는 받지 않는다.":
        "Coordinates are Mars latitude/longitude (degrees, planetocentric, east-positive). Projected systems are not accepted.",
    "영상·지질도·표고: NASA Mars Trek (Viking·MGS MOLA·Mars Odyssey THEMIS·MRO HiRISE·Mars Express HRSC, USGS Astrogeology).":
        "Imagery, geology and elevation: NASA Mars Trek (Viking, MGS MOLA, Mars Odyssey THEMIS, MRO HiRISE, Mars Express HRSC, USGS Astrogeology).",
    "바이킹 색 모자이크": "Viking color mosaic",
    "THEMIS 낮 적외선 (고해상)": "THEMIS day infrared (high resolution)",
    "MOLA 표고 색 음영": "MOLA colored hillshade",
    "MOLA 음영 겹치기 — 영상 위에 지형의 그늘을 곱한다": "Overlay MOLA hillshade — multiply terrain shading onto the image",
    "MOLA–HRSC 표고로 세운다": "Raise with MOLA–HRSC elevation",
    "처음": "Home",
    "경도 0°·위도 0° 로 — 본초 자오선(에어리-0 크레이터) 둘레": "To 0° lon, 0° lat — around the prime meridian (Airy-0 crater)",
    "방위 — 바늘이 화성의 북쪽을 가리킨다. 누르면 기울기는 두고 북쪽을 위로 돌린다":
        "Heading — the needle points to Martian north. Click to turn north up, keeping the tilt",
    "화성의 자전축 — 북극과 남극을 잇는 선을 켜고 끈다": "Mars's rotation axis — show or hide the line through both poles",
    "좌표·지명·착륙지로 이동 — -4.59, 137.44 · Gale · Curiosity":
        "Go to coordinates, a place name or landing site — -4.59, 137.44 · Gale · Curiosity",
    "화면 한가운데 점에서 본 기울기(곧장 내려다봄 0°)와 방위(화성의 북쪽 0°)":
        "Tilt (0° looking straight down) and heading (0° = Martian north) at the centre of the view",
    "표고 채우기 — MOLA–HRSC 표고에서 점마다 높이를 읽는다 (화성 기준면)":
        "Fill elevation — read each point's height from MOLA–HRSC elevation (Mars areoid)",
    "화성 지질 (USGS 1:2000만, 2014)": "Mars geology (USGS 1:20M, 2014)",
    "수성 지질 (USGS 1:500만 도폭, 1980–1990)": "Mercury geology (USGS 1:5M quadrangles, 1980–1990)",
    "구조선 — 급사면·능선·단층·분지 고리": "Structures — scarps, ridges, faults, basin rings",
    "도폭 경계 (H-1 … H-15)": "Quadrangle boundaries (H-1 … H-15)",
    "도폭 경계 — 원도가 있는 아홉에 원도 번호": "Quadrangle boundary — the nine with a map carry its number",
    "c{n} — c1 가장 닳음, c5 가장 또렷함": "c{n} — c1 most degraded, c5 freshest",
    "마리너 10 이 찍지 못해 지질도가 없는 곳이다": "No geologic map here — Mariner 10 did not image this area",
    "수성 지질도 파일이 서버에 없다": "The Mercury geologic map file is not on the server",
    "착륙선·로버 지점": "Lander and rover sites",
    "로버 주행 경로": "Rover traverses",
    "{name} 주행 경로": "{name} traverse",
    "착륙지 고해상 사진 (MRO HiRISE)": "Landing-site close-ups (MRO HiRISE)",
    "착륙선": "Lander",
    # 달 그림으로 내려받기 (048)
    "그림으로 내려받기 — 지금 보는 화면을 PNG 한 장으로. 배경·레이어·가운데·출처를 아래에 적는다":
        "Download as image — the current view as one PNG, with basemap, layers, centre and sources noted below",
    "음영": "hillshade",
    # 달 극 평면 (052)
    "북극 평사도법": "north polar stereographic",
    "남극 평사도법": "south polar stereographic",
    # 달 자세 (045)
    "방위": "Heading",
    "방위 — 바늘이 달의 북쪽을 가리킨다. 누르면 기울기는 두고 북쪽을 위로 돌린다":
        "Heading — the needle points to lunar north. Click to turn north up, keeping the tilt",
    "기울기 {tilt}° · 방위 {heading}°": "Tilt {tilt}° · heading {heading}°",
    # 2D 지도의 방위 (wetherilli 114)
    "방위 — 바늘이 지도의 본래 위쪽을 가리킨다. 우클릭한 채 끌면 지도가 돌고, 누르면 처음 방위로 되돌린다":
        "Heading — the needle points to the map's original up. Right-drag to rotate the map; click to restore the original heading",
    "평면에서 그렇게 끌면 구로 넘어가며 기울어진다.": "Doing so on the flat map switches to the globe and tilts.",
    "화면 한가운데 점에서 본 기울기(곧장 내려다봄 0°)와 방위(달의 북쪽 0°)":
        "Tilt (0° looking straight down) and heading (0° lunar north) at the point in the middle of the screen",
    "북극점": "North pole", "남극점": "South pole",
    "달의 자전축 — 북극과 남극을 잇는 선을 켜고 끈다": "The Moon's spin axis — show or hide the line through the poles",
    # 달 점묶음 (037)
    "올리기": "Upload",
    "올리는 중": "Uploading…",
    "올릴 파일": "File to upload",
    "이름 (비우면 파일 이름)": "Name (the file name if empty)",
    "아직 없다 — 아래에서 CSV·GeoJSON 을 올린다": "None yet — upload a CSV or GeoJSON below",
    "CSV(위도·경도 열) 또는 GeoJSON. 좌표는 달의 위도·경도(도)다.":
        "CSV (latitude and longitude columns) or GeoJSON. Coordinates are lunar latitude and longitude in degrees.",
    "표고 채우기 — LOLA 표고에서 점마다 높이를 읽는다 (달 기준구 1737.4 km)":
        "Fill elevation — read each point's height from LOLA (lunar reference sphere 1737.4 km)",
    "지질 레이어": "Geology layer",
    "투명도": "Opacity",
    "지형 과장": "Terrain exaggeration",
    "올린 점묶음이 없다 — 2D 에서 올린다": "No point sets yet — upload them in 2D",
    "켠 점이 {n}개다 — 지형과 함께 그리면 느릴 수 있다": "{n} points shown — drawing them over terrain may be slow",
    "그림": "Image",
    "그림으로 내려받기 — 지금 보는 지도를 PNG 한 장으로. 레이어·축척·출처를 아래에 적는다":
        "Download as image — the current map as one PNG, with layers, scale and credits below",
    "그림으로 내려받기": "Download as image",
    "그림으로 내려받기 — 지금 보는 3D 화면을 PNG 한 장으로. 레이어·자리·출처를 아래에 적는다":
        "Download as image — the current 3D view as one PNG, with layers, position and credits below",
    "기울기 {pitch}° · 방위 {bearing}° · 지형 과장 ×{x}": "Pitch {pitch}° · bearing {bearing}° · terrain ×{x}",
    "그림을 만들지 못했다": "Could not make the image",
    "배경지도가 그림으로 뽑는 것을 막았다 — 배경을 '없음' 으로 두고 다시 한다":
        "The basemap blocked the export — set the basemap to 'None' and try again",
    "가운데": "Centre",
    "한국지질자원연구원": "Korea Institute of Geoscience and Mineral Resources (KIGAM)",
    "출처": "Source",
    "도폭 {code}": "Sheet {code}",
    "도폭 {code} {name}": "Sheet {code} {name}",
    "스캔": "Scan",
    "이 도폭만 켜기": "Show only this sheet",
    "커스텀 지질도": "Custom geological maps",
    # 시료 고도 (P03, devlog 031)
    "표고 채우기 — 표고 타일에서 점마다 고도를 읽는다 (극지 PGC · 일본 국토지리원 · 그 밖 SRTM)":
        "Fill elevation — read each point's elevation from DEM tiles (polar PGC · Japan GSI · elsewhere SRTM)",
    "{n}점 채움 · {m}점은 자료 밖": "{n} points filled · {m} outside the data",
    "고도 {n}": "elevation {n}",
    "그런 점묶음이 없다": "No such point set",
    # 시료 지점의 VWorld 둘레 (074)
    "VWorld 열쇠가 없다": "No VWorld key",
    "VWorld 에서 받지 못했다": "Could not get it from VWorld",
    "점이 많아 화면에서 채우지 않는다 — 서버에서 manage.py fill_places {id} 를 부른다":
        "Too many points to fill here — run manage.py fill_places {id} on the server",
    "둘레 채우기 — VWorld 에서 점마다 주소·읍면동·가까운 단층·둘레 지명·보호구역·지목·소유구분을 읽는다 ({n}/{m}점 채움)":
        "Fill surroundings — read address, district, nearest fault, nearby place name, protected area, land category and ownership from VWorld ({n}/{m} filled)",
    "{n}점 채움 · {m}점은 받지 못했다": "{n} filled · {m} not received",
    "점이 많아 화면에서 채우지 않는다 — 서버에서 manage.py fill_elevation {id} 를 부른다":
        "Too many points to fill here — run manage.py fill_elevation {id} on the server",
    "표고를 받지 못했다": "Could not get the elevation",
    "음영 보이기": "Show hillshade",
    "오른쪽 단추를 누른 채 끌면(또는 Ctrl+끌기) 기울이고 돌린다.":
        "Drag with the right button (or Ctrl+drag) to tilt and rotate.",
    "두 손가락을 위아래로 끌면 기울이고, 비틀면 돌린다.":
        "Drag two fingers up or down to tilt; twist them to rotate.",
    "표고: AWS Terrain Tiles (SRTM 등, 약 30 m) · 일본 국토지리원 (10 m) · 극지 PGC ArcticDEM·REMA (2 m) · 남빙양 IBCSO v2 (500 m). 지질도: 한국지질자원연구원 등.":
        "Elevation: AWS Terrain Tiles (SRTM etc., ~30 m) · Japan GSI (10 m) · polar PGC ArcticDEM/REMA (2 m) · Southern Ocean IBCSO v2 (500 m). Geology: KIGAM and others.",
    # 3D 남극 IBCSO (051)
    "빙저 지형을 고르면 3D 의 땅도 얼음을 걷어 낸 기반암이 된다.":
        "With the subglacial bed, the 3D terrain also drops the ice down to bedrock.",
    "2D 로 돌아간다": "Back to 2D",
    "지역": "Regions",
    "한국": "Korea",
    "그린란드": "Greenland",
    "남극": "Antarctica",
    "얀마옌": "Jan Mayen",
    # 스발바르와, 그린란드·스발바르·얀마옌을 한 화면에 모은 북극 탭 (devlog 021)
    "스발바르": "Svalbard",
    "북극": "Arctic",
    "웹 메르카토르": "Web Mercator",
    # 일본과, 한국·일본을 한 화면에 모은 동아시아 탭 (devlog 024)
    "일본": "Japan",
    "동아시아": "East Asia",
    # 중국 — USGS geo3al 을 우리가 그린다 (devlog 025)
    "중국": "China",
    "대만": "Taiwan",
    # 북극해 — 스발바르·그린란드 밖의 북극 (devlog 076)
    "북극해": "Arctic Ocean",
    # 노르웨이·핀란드 — NGU·GTK 기반암 지질도 (wetherilli 140). 스웨덴 SGU 가 들어 탭 이름이 셋이 됐다 (213)
    "노르웨이·핀란드": "Norway & Finland",
    "노르웨이·스웨덴·핀란드": "Norway, Sweden & Finland",
    # 영국·프랑스·유럽 — BGS·BRGM·EGDI 지질도 (wetherilli 143)
    "영국": "United Kingdom",
    "프랑스": "France",
    "유럽": "Europe", "아시아": "Asia", "아메리카": "Americas",
    # 독일·스페인·아일랜드 (wetherilli 147)
    "독일": "Germany",
    "스페인": "Spain",
    "아일랜드": "Ireland",
    "독일 연방 지구과학·자원청": "BGR (Federal Institute for Geosciences and Natural Resources)",
    "스페인 지질광물연구소": "IGME (Geological and Mining Institute of Spain)",
    "아일랜드 지질조사소": "Geological Survey Ireland",
    # 남미 (wetherilli 188)
    "남미": "South America",
    "콜롬비아 지질조사소": "Colombian Geological Survey (SGC)",
    # 남미의 나라 탭 (wetherilli 191)
    "콜롬비아": "Colombia",
    "브라질": "Brazil",
    "브라질 지질조사소": "Geological Survey of Brazil (SGB)",
    # 페루 (wetherilli 195)
    "페루": "Peru",
    "페루 지질광업야금연구소": "INGEMMET (Geological, Mining and Metallurgical Institute of Peru)",
    # 아르헨티나·우루과이 (wetherilli 196)
    "아르헨티나": "Argentina",
    "우루과이": "Uruguay",
    "아르헨티나 지질광업조사소": "Argentine Geological-Mining Survey (SEGEMAR)",
    "퀸즐랜드 지질조사소": "Geological Survey of Queensland", "빅토리아 지질조사소": "Geological Survey of Victoria",
    "남호주 지질조사소": "Geological Survey of South Australia", "태즈메이니아 광물자원청": "Mineral Resources Tasmania", "뉴사우스웨일스 지질조사소": "Geological Survey of New South Wales",
    # 아프리카 (wetherilli 207)
    "아프리카": "Africa",
    "세계지질도위원회·프랑스 지질광물조사소": "Commission for the Geological Map of the World · BRGM (CGMW–BRGM)",
    "영국 지질조사소 — 아프리카 지하수 지도책": "British Geological Survey — Africa Groundwater Atlas",
    "남아프리카공화국 지질조사소": "Council for Geoscience (South Africa)",
    "나미비아 지질조사소": "Geological Survey of Namibia",
    "부르키나파소 지질광업국": "Bureau of Mines and Geology of Burkina Faso (BUMIGEB)",
    "카메룬 지질광업연구소": "Institute for Geological and Mining Research of Cameroon (IRGM)",
    "우루과이 광업지질국": "Uruguay National Directorate of Mining and Geology (DINAMIGE)",
    # 에콰도르 (wetherilli 198)
    "에콰도르": "Ecuador",
    "에콰도르 지질·에너지 연구소": "IIGE (Geological and Energy Research Institute of Ecuador)",
    # 미국 (wetherilli 205)
    "미국": "United States",
    # 멕시코 (wetherilli 206)
    "멕시코": "Mexico",
    # 호주 (wetherilli 212)
    "호주": "Australia",
    "멕시코 지질조사소": "Mexican Geological Survey (SGM)",
    "북아일랜드 지질조사소": "Geological Survey of Northern Ireland",
    "영국 지질조사소": "British Geological Survey",
    "프랑스 지질광물조사소": "BRGM (French Geological Survey)",
    "노르웨이 지질조사소": "Geological Survey of Norway",
    "핀란드 지질조사소": "Geological Survey of Finland",
    "스웨덴 지질조사소": "Geological Survey of Sweden",
    "추가 지역": "Add region",
    "그 외": "More",
    "준비 중": "coming soon",
    "이 지역을 탭에서 뺀다": "Remove this region from the tabs",
    "<b>남극 지질도는 준비 중이다.</b> 남극점을 가운데 둔 평사도법 화면과 배경지도를 먼저 띄워 둔다. GeoMAP 레이어는 곧 붙인다.":
        "<b>Antarctic geology is coming soon.</b> For now the map opens in a South-Pole-centred polar stereographic view with basemaps. GeoMAP layers will follow.",
    # 극지 투영·배경 (017)
    "Sentinel-2 위성 (EOX)": "Sentinel-2 satellite (EOX)",
    "EOX · Copernicus Sentinel-2 (2023). 비상업 이용만 된다. 북위 82° 위는 해안선이 거칠다 — ArcticDEM 을 쓴다":
        "EOX · Copernicus Sentinel-2 (2023). Non-commercial use only. The coastline is rough north of 82°N — use ArcticDEM",
    "지형 음영 (EOX)": "Terrain shading (EOX)",
    "EOX · OpenStreetMap. 비상업 이용만 된다. 북위 82° 위는 해안선이 거칠다 — ArcticDEM 을 쓴다":
        "EOX · OpenStreetMap. Non-commercial use only. The coastline is rough north of 82°N — use ArcticDEM",
    "ArcticDEM 음영": "ArcticDEM hillshade",
    "REMA 음영": "REMA hillshade",
    "ArcticDEM 음영 (여러 방향)": "ArcticDEM hillshade (multidirectional)",
    "REMA 음영 (여러 방향)": "REMA hillshade (multidirectional)",
    "ArcticDEM 높이 색 음영": "ArcticDEM elevation-tinted hillshade",
    "REMA 높이 색 음영": "REMA elevation-tinted hillshade",
    "Polar Geospatial Center. 여러 방향에서 비춘 음영 — 한 방향 음영에서 그늘진 사면이 살아난다":
        "Polar Geospatial Center. Hillshade lit from several directions — slopes hidden in a single-light shadow show up",
    "Polar Geospatial Center. 높이를 색으로 칠한 음영": "Polar Geospatial Center. Hillshade tinted by elevation",
    "세종·장보고 기지 위성 (VWorld)": "King Sejong & Jang Bogo station imagery (VWorld)",
    "VWorld · 2013 년 위성영상. 두 기지 둘레 10 km 남짓에만 있고 그 밖은 REMA 음영이다":
        "VWorld · 2013 satellite imagery. Only about 10 km around the two stations; REMA hillshade elsewhere",
    "GEBCO 해저 지형": "GEBCO bathymetry",
    # 국토지리원 주제 타일·AWS 법선 음영 (wetherilli 156)
    "일본 경사량도 (국토지리원)": "Japan slope map (GSI)",
    "일본 국토지리원. 기울기를 색으로 — 단층애·산사태 지형을 지질도와 견줄 때. 줌 15 까지":
        "GSI Japan. Slope in colour — compare fault scarps and landslides with the geology. Up to zoom 15",
    "일본 토지조건도 (국토지리원)": "Japan land condition map (GSI)",
    "일본 국토지리원. 산지·대지·저지·인공 지형을 가른 1:2만 5천 — 평야와 도시 둘레만 있다. 줌 16 까지":
        "GSI Japan. 1:25,000 landform classes (mountain, terrace, lowland, artificial) — plains and cities only. Up to zoom 16",
    "일본 화산기본도 (국토지리원)": "Japan volcano base map (GSI)",
    "일본 국토지리원. 활화산 둘레만 있는 정밀 지형도 — 그 밖은 빈다. 줌 17 까지":
        "GSI Japan. Detailed topography around active volcanoes only — blank elsewhere. Up to zoom 17",
    "지형 음영 (AWS)": "Hillshade (AWS)",
    "AWS 표고 타일의 법선으로 그린 음영 — 북서에서 비춘다. 줌 15 까지":
        "Hillshade from AWS terrain-tile normals, lit from the northwest. Up to zoom 15",
    "경사 (AWS)": "Slope (AWS)",
    "AWS 표고 타일의 법선으로 칠한 기울기 — 흰 평지에서 붉은 낭떠러지까지. 줌 15 까지":
        "Slope from AWS terrain-tile normals — white flats to red cliffs. Up to zoom 15",
    "GEBCO — 해저 지형": "GEBCO — bathymetry",
    "GEBCO 2026 (약 450 m). 바다의 수심과 땅의 높이를 음영으로. 공공 도메인. 항해에 쓰지 않는다":
        "GEBCO 2026 (about 450 m). Ocean depth and land height as shaded relief. Public domain. Not for navigation",
    "GEBCO 해저·얼음 밑 지형": "GEBCO bathymetry and subglacial bed",
    "GEBCO 2026 (약 450 m). 빙상을 걷어 낸 얼음 밑 기반암과 해저. 공공 도메인":
        "GEBCO 2026 (about 450 m). Seafloor and the bed beneath the ice sheets. Public domain",
    "IBCSO 해저·빙저 지형": "IBCSO seafloor and subglacial bed",
    "IBCSO v2 (500 m). 빙붕·빙상을 걷어 낸 얼음 밑 기반암과 해저. CC BY 4.0":
        "IBCSO v2 (500 m). Seafloor and the bed beneath ice shelves and the ice sheet. CC BY 4.0",
    "IBCSO 해저·얼음 위 지형": "IBCSO seafloor and ice surface",
    "IBCSO v2 (500 m). 빙붕·빙상의 윗면과 해저. CC BY 4.0":
        "IBCSO v2 (500 m). Seafloor and the top of ice shelves and the ice sheet. CC BY 4.0",
    # 누른 자리의 IBCSO 수심·표고 (070)
    "lat·lon 이 없다": "lat and lon are missing",
    "얼음 위 {m}": "ice surface {m}",
    "해저·빙저 {m}": "bed {m}",
    "얼음 두께 {m}": "ice thickness {m}",
    "수심 {m}": "depth {m}",
    "표고 {m}": "elevation {m}",
    # IBCSO 자료 출처(TID) — GEBCO 의 갈래 이름 (071)
    "직접 측정": "Direct measurements",
    "간접 측정": "Indirect measurements",
    "출처가 섞였거나 모름": "Mixed or unknown source",
    "육지": "Land",
    "싱글빔 측심": "Singlebeam",
    "멀티빔 측심": "Multibeam",
    "탄성파 탐사": "Seismic",
    "따로 잰 측심점": "Isolated sounding",
    "전자해도(ENC) 측심": "ENC sounding",
    "라이다 측심": "Lidar",
    "광학 센서 측심": "Optical light sensor",
    "여러 직접 측정": "Combination of direct measurements",
    "위성 중력으로 예측": "Predicted from satellite-derived gravity",
    "계산으로 보간": "Interpolated by computer algorithm",
    "해도 등심선": "Bathymetric contours from charts",
    "전자해도 등심선": "Bathymetric contours from ENCs",
    "측심에 묶인 격자": "Grid constrained by soundings",
    "항공 중력으로 예측": "Predicted from flight-derived gravity",
    "좌초 빙산의 흘수": "Draft of a grounded iceberg",
    "미리 만든 격자": "Pre-generated grid",
    "출처 모름": "Unknown source",
    "조정점": "Steering points",
    "Polar Geospatial Center. 2 m 표고에서 그린 음영":
        "Polar Geospatial Center. Hillshade drawn from 2 m elevation",
    "Blue Marble 위성 (NASA)": "Blue Marble satellite (NASA)",
    "NASA GIBS. 500 m 해상도라 넓게 볼 때 쓴다": "NASA GIBS. 500 m resolution, for wide views",
    "남극 위성 (Esri)": "Antarctic satellite (Esri)",
    "Esri · Earthstar Geographics TerraColor 15 m. 줌 13 까지 영상이 있고 그 위는 늘려 보인다. Esri 이용 조건을 따른다":
        "Esri · Earthstar Geographics TerraColor 15 m. Imagery up to zoom 13, stretched beyond. Esri terms of use apply",
    "왼쪽 위": "Top left",
    "오른쪽 위": "Top right",
    "오른쪽 아래": "Bottom right",
    "왼쪽 아래": "Bottom left",
    "주제도 비교": "Compare maps",
    "끔": "Off",
    "밀어 보기": "Swipe",
    "나란히": "Side by side",
    "끌어서 견준다": "Drag to compare",
    "막대 왼쪽": "Left of bar",
    "오른쪽": "Right",
    "고른 레이어가 막대 왼쪽에만 보인다. 막대를 끌어 견준다.":
        "The chosen layer shows only left of the bar. Drag the bar to compare.",
    "왼쪽은 켠 레이어, 오른쪽은 고른 레이어. 두 지도가 함께 움직인다.":
        "Left: your active layers. Right: the chosen layer. Both maps move together.",
    "먼저 레이어를 둘 이상 켠다.": "Turn on two or more layers first.",

    # 배경지도
    "없음 (바탕만)": "None (plain)",
    "VWorld 배경지도": "VWorld basemap",
    "VWorld 백지도": "VWorld white",
    "VWorld 야간": "VWorld night",
    "VWorld 위성": "VWorld satellite",
    "국토지리정보원": "National Geographic Information Institute",
    "구분 {value}": "Class {value}",
    "등치선 ({unit}) — 줌 {n} 부터 값을 적는다": "Contours ({unit}) — values labelled from zoom {n}",
    "국토지리정보원. 지질도 밑에 깔기 좋다":
        "National Geographic Information Institute. Good under geological maps",
    "국토지리정보원. 지명을 끄고 켤 수 있다":
        "National Geographic Information Institute. Place names can be toggled",

    # 그리기
    "그리기": "Drawing",
    "지도에 얹은 내 것": "your things on the map",
    "찍고 잰 것": "Points & measurements",
    "저장 전까지 임시": "temporary until saved",
    "아직 잰 것이 없다": "Nothing measured yet",
    # 달 — 높이 그래프 (wetherilli 100)
    "높이 그래프": "Elevation profile",
    "여기에는 값이 없다": "No value here",
    "높이를 읽는 중…": "Reading elevations…",
    "높이를 읽지 못했다": "Could not read the elevations",
    "최저 {lo} · 최고 {hi} · 오르막 {up} · 내리막 {down}": "low {lo} · high {hi} · ascent {up} · descent {down}",
    "LOLA 256 ppd · 달 기준구 1737.4 km 에서 잰 높이": "LOLA 256 ppd · height above the 1737.4 km lunar sphere",
    "MOLA–HRSC 200 m · 화성 기준면(아레오이드)에서 잰 높이": "MOLA–HRSC 200 m · height above the Mars areoid",
    "MESSENGER 665 m · 수성 기준구 2439.4 km 에서 잰 높이": "MESSENGER 665 m · height above the 2,439.4 km Mercury sphere",
    "거리 {d} · 높이 {h}": "distance {d} · elevation {h}",
    "선이 없다": "No line given",
    # 공유 링크 (wetherilli 189)
    "링크 복사 — 보던 자리·켠 레이어·배경을 주소에 담는다": "Copy link — puts the view, the layers you have on and the basemap in the address",
    "링크": "Link",
    "이 링크를 복사한다": "Copy this link",
    "링크로 연 화면이다 — 여기서 바꾼 것은 이 브라우저에 기억하지 않는다": "Opened from a link — changes here are not remembered in this browser",
    "내 화면으로": "Back to my view",
    # 높이 그래프 밑의 지질 띠 (wetherilli 180)
    "거리 {d} · 높이 {h} · {unit}": "distance {d} · elevation {h} · {unit}",
    "{read} · 지질 띠 — {layer}": "{read} · geology strip — {layer}",
    "띠를 그리지 않는 레이어다": "This layer has no geology strip",
    "지질 띠를 그릴 자료가 서버에 없다": "The data for the geology strip is not on the server",
    "지질 띠를 읽지 못했다": "Could not read the geology strip",
    "지도 오른쪽 위 <b>점</b> 도구로 찍는다": "Use the <b>Point</b> tool at the top right of the map",
    "점묶음으로 저장": "Save as point set",
    "찍은 점과 잰 것을 모두 지운다": "Clear all points and measurements",
    "모두 지운다": "Clear all",
    "점묶음": "Point sets",
    "불러오거나 저장한 자료": "imported or saved",
    "왼쪽 위 <b>불러오기</b> 탭에서 올린다": "Upload from the <b>Import</b> tab at the top left",
    "{n}점": "{n} pts",
    "이 자료로 범위를 맞춘다": "Zoom to this data",
    "GeoJSON 으로 내려받는다": "Download as GeoJSON",
    "지운다": "Delete",
    "'{name}' 을 지운다.": "Delete '{name}'?",
    "이 점으로 이동": "Go to this point",
    "눌러서 복사한다": "Click to copy",
    "복사": "Copy",
    "복사했다": "Copied",
    "저장할 점이 없다.": "No points to save.",
    "목록 이름": "Name for the list",
    "찍은 점 {date}": "Points {date}",
    "저장하는 중…": "Saving…",
    "점 {n}": "Point {n}",
    "저장하지 못했다": "Could not save",
    "'{name}' 으로 저장했다.": "Saved as '{name}'.",

    # 도구
    "그리기 도구": "Drawing tools",
    "범위": "Extent",
    "범위 {n}": "Extent {n}",
    "범위잡기 — 누른 채 끌어 네모를 그리면 꼭짓점·중앙·넓이가 뜬다":
        "Extent — press and drag a rectangle to get its corners, centre and area",
    "누른 채 끌어 네모를 그린다. 손을 떼면 꼭짓점·중앙·넓이가 뜬다.":
        "Press and drag to draw a rectangle. Release to see its corners, centre and area.",
    "누른 채 끌어 네모를 그린다": "Press and drag a rectangle",
    "북서": "NW", "북동": "NE", "남동": "SE", "남서": "SW",
    "중앙": "Centre",
    "가로 × 세로": "Width × height",
    "눌러서 꼭짓점·중앙·넓이를 복사한다": "Click to copy corners, centre and area",
    "이 범위로 가서 수치를 본다": "Go to this extent and show its figures",
    "점": "Point",
    "거리": "Distance",
    "넓이": "Area",
    "지우기": "Clear",
    "점 찍기 — 누른 자리에 점을 찍고 위경도를 적는다":
        "Point — drop a point where you click and note its coordinates",
    "거리 재기 — 눌러 가며 잇고, 두 번 누르면 끝난다":
        "Distance — click to add vertices, double-click to finish",
    "넓이 재기 — 눌러 가며 두르고, 두 번 누르면 끝난다":
        "Area — click to outline, double-click to finish",
    "지도를 누르면 그 지점의 지질 속성이 뜬다.": "Click the map to read the geology there.",
    "지도를 누르면 점이 찍히고 위경도가 적힌다. 점을 눌러 지운다.":
        "Click the map to drop a point with its coordinates. Click a point to remove it.",
    "눌러 가며 선을 잇는다. 두 번 누르면 끝난다.": "Click to draw a line. Double-click to finish.",
    "눌러 가며 둘레를 두른다. 두 번 누르면 끝난다.": "Click to outline an area. Double-click to finish.",
    "점 {n}개": "{n} points",
    "지도를 눌러 점을 찍는다": "Click the map to drop a point",
    "눌러 가며 잇는다 · 두 번 누르면 끝": "Click to draw · double-click to finish",
    "눌러 가며 두른다 · 두 번 누르면 끝": "Click to outline · double-click to finish",

    # 팝업
    "내 자료": "My data",
    "찍은 점 {n}": "Point {n}",
    "켠 레이어가 없다": "No layers are on",
    "읽는 중…": "Reading…",
    "이 자리에는 아무것도 없다": "Nothing here",
    "위도": "Latitude",
    "경도": "Longitude",
    "도분초": "DMS",
    "접기": "Collapse",
    "모두 표시 ({n})": "Show all ({n})",
    "닫는다": "Close",

    # 불러오기
    "바깥 자료를 지도에": "bring outside data onto the map",
    "CSV · GeoJSON 고르기": "Choose CSV · GeoJSON",
    "점묶음 이름 (비우면 파일 이름)": "Point set name (file name if empty)",
    "점 색": "Point colour",
    "올린다": "Upload",
    "위경도 열은 이름으로 알아낸다 — <code>lat</code>·<code>위도</code>·<code>y</code>, <code>lon</code>·<code>경도</code>·<code>x</code>. 나머지 열은 점을 누르면 뜬다.":
        "Coordinate columns are found by name — <code>lat</code>·<code>위도</code>·<code>y</code>, <code>lon</code>·<code>경도</code>·<code>x</code>. Other columns appear when you click a point.",
    "올렸다 — {what}.": "Uploaded — {what}.",
    "GeoJSON 은 점·선·면을 다 받는다.": "GeoJSON may hold points, lines and polygons.",
    "선 {n}": "{n} lines",
    "면 {n}": "{n} polygons",
    "올리지 못했다": "Upload failed",
    # 주소만 적힌 CSV (wetherilli 152)
    "주소로 좌표를 찾는 중… {done} / {all}줄": "Finding coordinates from addresses… {done} / {all} rows",
    "찾은 주소": "Matched address",
    "주소로 좌표를 하나도 찾지 못했다 — 도로명·지번 주소인지 본다.":
        "No address could be located — check that they are Korean road or parcel addresses.",
    "주소를 못 찾은 줄 {n}개 — {lines}": "{n} rows not located — {lines}",
    "주소 열({col})이 모두 비어 있다.": "The address column ({col}) is empty.",
    "주소로 찾는 것은 지구의 점묶음뿐이다.": "Addresses can only be located for Earth point sets.",
    "VWorld 열쇠가 없어 주소로 좌표를 찾지 못한다. 위경도 열을 넣어 올린다.":
        "No VWorld key, so addresses cannot be located. Add latitude/longitude columns and upload again.",
    "주소로 찾는 것은 한 번에 {n}줄까지다. 나눠 올린다.": "Up to {n} address rows at a time. Split the file and upload again.",
    "주소는 한 번에 {n}줄까지 보낸다": "Send up to {n} addresses at a time",
    "VWorld 열쇠가 없다": "No VWorld key",
    "상류가 바빠 잠시 멈췄다. 조금 뒤에 다시 올린다.": "The source is busy, so we paused. Upload again shortly.",

    # 좌표 막대
    "좌표·주소·장소로 이동 — 36.378, 127.362 · 과학로 124 · 가정동":
        "Go to coordinates, address or place — 36.378, 127.362 · a Korean address or place name",
    "행정구역": "District",
    "도로명": "Road address",
    "지번": "Parcel",
    "장소": "Place",
    "찾는 중…": "Searching…",
    "찾지 못했다": "Search failed",
    "찾은 것이 없다 — 주소·장소·행정구역을 넣어 본다": "Nothing found — try an address, place or district",
    "주소 검색: VWorld (국토지리정보원)": "Address search: VWorld (National Geographic Information Institute)",
    "간다": "Go",
    "십진도와 도분초를 오간다": "Switch between decimal degrees and DMS",
    "좌표로 읽지 못했다": "Not a coordinate I can read",
    "보이는 지도의 북쪽 끝": "Northern edge of the visible map",
    "보이는 지도의 남쪽 끝": "Southern edge of the visible map",
    "보이는 지도의 서쪽 끝": "Western edge of the visible map",
    "보이는 지도의 동쪽 끝": "Eastern edge of the visible map",

    # 설정
    "설정": "Settings",
    "설정과 판 이력": "Settings and release notes",
    "모양": "Look",
    "판 이력": "Release notes",
    "지금 상태": "Status",
    "화면": "Theme",
    "먹갈색": "Ink brown",
    "한지": "Hanji",
    "먹갈색이 기본이다. 한지는 밝은 바탕에 갈색 글자다.":
        "Ink brown is the default. Hanji is brown text on a light background.",
    "글꼴": "Font",
    "고딕": "Sans",
    "명조": "Serif",
    "기기 기본": "System",
    "지질도 위의 글자는 상류가 그린 것이라 바뀌지 않는다.":
        "Text drawn on the geological maps comes from the source and does not change.",
    "글자 크기": "Text size",
    "작게": "Small",
    "보통": "Medium",
    "크게": "Large",
    "속성 값(지층명·암석명)은 상류가 한국어로 주는 것이라 그대로 둔다. 지질시대만 영어로 옮긴다.":
        "Attribute values (formation and rock names) come from the source in Korean and are left as they are. Only geologic ages are translated.",
    "고른 것은 이 브라우저에만 남는다. 서버로 가지 않는다.":
        "Choices stay in this browser only. Nothing is sent to the server.",
    "판 이력은 한국어로만 적는다.": "Release notes are written in Korean only.",
    "판 이력을 읽지 못했다.": "Could not load the release notes.",
    "아직 적힌 판이 없다.": "No releases yet.",
    "배경지도": "Basemap",
    "없음": "None",
    "켠 레이어": "Active layers",
    "찍은 점": "Points",
    "{n}개": "{n}",
    "올린 자료": "Uploads",
    "{n}묶음": "{n} sets",
    "좌표 표기": "Coordinates",
    "십진도": "Decimal",

    # 서버 메시지 (views.py)
    "인증키가 없다": "No API key",
    "layer 가 없다": "No layer given",
    "올린 파일이 없다": "No file uploaded",
    "읽지 못했다": "Could not read the request",
    "저장할 점이 없다": "No points to save",
    "한 번에 {n}점까지 저장한다": "Up to {n} points can be saved at once",
    "쓸 만한 좌표가 없다": "No usable coordinates",
    "상류에서 받지 못했다": "Could not get it from the source",
    "이미 되살렸다": "Already restored",
    "최근 지운 점묶음": "Recently deleted point sets",
    "지울 때 사본을 남겨 둔다. 잘못 지웠으면 되살린다.":
        "A copy is kept when a point set is deleted. Restore it if it was a mistake.",
    "지운 것이 없다": "Nothing deleted",
    "되살림": "restored",
    "되살리기": "Restore",
    "되살리지 못했다": "Could not restore",
    "주소 검색이 꺼져 있다 — VWorld 열쇠가 없다": "Address search is off — no VWorld key",
    "VWorld 가 답하지 않는다": "VWorld is not responding",

    # 업로드 알림 (pointsets.py)
    "글자를 읽지 못했다. UTF-8 이나 CP949 로 저장해 다시 올린다.":
        "Could not read the text. Save it as UTF-8 or CP949 and upload again.",
    "첫 줄에 열 이름이 없다.": "The first row has no column names.",
    "위경도 열을 찾지 못했다. 열 이름을 {lat} / {lon} 가운데 하나로 두고 다시 올린다. (읽은 열: {cols})":
        "No coordinate columns found. Name them one of {lat} / {lon} and upload again. (Columns read: {cols})",
    "{line}째 줄 — 좌표를 읽지 못해 건너뛰었다": "Row {line} — skipped, coordinates unreadable",
    "좌표를 하나도 읽지 못했다.": "No coordinates could be read.",
    "…모두 {n}줄을 건너뛰었다": "…{n} rows skipped in all",
    "GeoJSON 이 깨져 있다: {err}": "The GeoJSON is broken: {err}",
    "GeoJSON 에 features 가 없다.": "The GeoJSON has no features.",
    "점·선·면을 하나도 찾지 못했다.": "No points, lines or polygons found.",
    "'{n}' 를 북쪽, '{e}' 를 동쪽으로 읽었다 (측량 관례).":
        "Read '{n}' as northing and '{e}' as easting (surveying convention).",
    "'{e}' 를 동쪽, '{n}' 를 북쪽으로 읽었다. 측량 관례(X=북)면 열 이름을 X좌표·Y좌표 로 바꿔 다시 올린다.":
        "Read '{e}' as easting and '{n}' as northing. If the file uses the surveying convention (X = north), rename the columns to X좌표·Y좌표 and upload again.",
    "{line}째 줄 — {name} 좌표로 읽지 못해 건너뛰었다": "Row {line} — skipped, not a readable {name} coordinate",
    "{name} 좌표로 읽지 못했다 — 한반도 밖으로 간다": "Not a readable {name} coordinate — it lands outside Korea",
    "{name} 좌표로 읽히는 줄이 없다. 좌표계를 다시 고른다.":
        "No rows read as {name} coordinates. Choose the coordinate system again.",
    "좌표가 위경도 범위를 벗어난다. TM 좌표면 올리기 전에 좌표계를 고른다.":
        "Coordinates are outside latitude/longitude range. If they are TM, choose the coordinate system before uploading.",
    "평면 좌표 열을 찾지 못했다. 열 이름을 {east} / {north} 가운데 하나로 두고 다시 올린다. (읽은 열: {cols})":
        "No planar coordinate columns found. Name them one of {east} / {north} and upload again. (Columns read: {cols})",
    # 좌표계 이름 (crs.SYSTEMS)
    "위경도 (WGS84)": "Lat/lon (WGS84)",
    "중부원점 (GRS80)": "Korea Central Belt (GRS80)",
    "서부원점 (GRS80)": "Korea West Belt (GRS80)",
    "동부원점 (GRS80)": "Korea East Belt (GRS80)",
    "동해원점 (GRS80)": "Korea East Sea Belt (GRS80)",
    "UTM-K (GRS80)": "UTM-K (GRS80)",
    "UTM 52N (WGS84)": "UTM 52N (WGS84)",
    "옛 중부원점 (Bessel, 보정)": "Old Central Belt (Bessel, modified)",
    "옛 중부원점 (Bessel)": "Old Central Belt (Bessel)",
    "좌표계": "Coordinates",
    "좌표 칸이 받는 좌표계. 평면 좌표계면 팝업에도 그 좌표가 뜬다":
        "Coordinate system for the search box. For planar systems the popup also shows those coordinates",
    "{name} — 동 북 두 수, 또는 N 420005 E 232509 · 주소·장소도 된다":
        "{name} — easting northing, or N 420005 E 232509 · addresses and places work too",
    "동 {e} · 북 {n}": "E {e} · N {n}",
    "적은 차례": "as typed",
    "좌표": "Coordinate",
    "두 차례 모두 한반도 안이다 — 고른다. 이름을 붙여 적으면(N 420005 E 232509) 곧장 간다.":
        "Both orders land in Korea — pick one. Label them (N 420005 E 232509) to go straight there.",
    "동": "E",
    "북": "N",
    "읽지 못한 것 {n}개를 건너뛰었다 (기하가 없거나 깨졌거나 GeometryCollection)":
        "Skipped {n} unreadable features (no geometry, broken, or GeometryCollection)",
    "모양 하나의 꼭짓점이 {n}개로 너무 많다 (한도 {max}개).":
        "One shape has {n} vertices — too many (limit {max}).",
    "꼭짓점이 모두 {max}개를 넘는다. 파일을 나눠 올린다.":
        "More than {max} vertices in total. Split the file and upload again.",
    # 점 레이어 — 그린란드 정부 포털 (grportal.py, map.js 의 vectorLayerFor)
    "그런 점 레이어가 없다": "No such point layer",
    "그린란드 정부 광물자원 포털": "Government of Greenland mineral portal",
    "포털의 원본 항목 — 이용 조건 표시 없음": "Source item on the portal — no licence stated",
    "포털의 원본 항목 — CC BY 4.0, Hutchison (2020)": "Source item on the portal — CC BY 4.0, Hutchison (2020)",
    "이용 조건 표시 없음": "no licence stated",
    "색은 포털이 시료 갈래마다 매긴 것이다": "Colours are the portal's, one per sample type",
    "점을 받지 못했다": "Could not load the points",
    "받는 중…": "Loading…",
    "열기": "open",
    # 연대 갈래 (map.js 의 AGE_CLASSES) — ICS 국제층서표의 이름
    "신생대": "Cenozoic",
    "중생대": "Mesozoic",
    "고생대": "Paleozoic",
    "신원생대": "Neoproterozoic",
    "중원생대": "Mesoproterozoic",
    "고원생대": "Paleoproterozoic",
    "신시생대": "Neoarchean",
    "중시생대 이전": "Mesoarchean and older",
    # 남극 지질도 (geomap.py)
    "남극 지질도 자료(GeoMAP)가 서버에 없다": "The Antarctic geology data (GeoMAP) is not on the server",
    # 얀마옌 지질도 (janmayen.py, map.js 의 dataLegend)
    "얀마옌 지질도 자료(NPI)가 서버에 없다": "The Jan Mayen geology data (NPI) is not on the server",
    "노던테리토리 지질도 자료(NTGS)가 서버에 없다": "The Northern Territory geology data (NTGS) is not on the server",
    "노던테리토리 지질도 자료(NTGS)를 읽지 못했다": "Could not read the Northern Territory geology data (NTGS)",
    "해석 단층 (지구물리)": "Interpreted fault (geophysics)",
    "지도의 단층": "Mapped fault",
    "얀마옌 지질도 자료(NPI)를 읽지 못했다": "Could not read the Jan Mayen geology data (NPI)",
    "원본 자료 — Norsk Polarinstitutt, CC BY 4.0": "Source dataset — Norsk Polarinstitutt, CC BY 4.0",
    "그런 타일은 없다": "No such tile",
    # 스발바르 — 노르웨이 극지연구소 (npolar.py·map.js, devlog 021)
    "Sentinel-2 위성 (NPI)": "Sentinel-2 satellite (NPI)",
    "노르웨이 극지연구소 · Copernicus Sentinel-2. CC BY 4.0":
        "Norwegian Polar Institute · Copernicus Sentinel-2. CC BY 4.0",
    "스발바르 지형도 (NPI)": "Svalbard topographic map (NPI)",
    "노르웨이 극지연구소. CC BY 4.0": "Norwegian Polar Institute. CC BY 4.0",
    "이 지역에서는 좌표로 간다 — 주소·장소는 한국·일본, 지명은 스발바르·그린란드·북극·남극 탭에서 찾는다":
        "Coordinates only here — addresses and places in Korea and Japan, place names in the Svalbard, Greenland, Arctic and Antarctica tabs",
    "좌표·지명으로 이동 — {example}": "Go to coordinates or a place name — {example}",
    # 일본 찾기 칸 — 국토지리원 (wetherilli 155)
    "좌표·주소·지명으로 이동 — {example}": "Go to coordinates, an address or a place name — {example}",
    "주소·지명": "Address/place",
    "주소·지명 검색: 국토지리원 (지리원 지도)": "Address & place search: GSI Japan (GSI Maps)",
    "주소: 국토지리원 (지리원 지도)": "Address: GSI Japan (GSI Maps)",
    "좌표로 이동 — 위도, 경도 (예: {example})": "Go to coordinates — latitude, longitude (e.g. {example})",
    "지명 검색: 노르웨이 극지연구소 (스발바르)": "Place names: Norwegian Polar Institute (Svalbard)",
    "찾은 것이 없다 — 이 지역의 지명을 넣어 본다": "Nothing found — try a place name in this region",
    "지명 검색: 그린란드 정부 (Nunat Aqqi)": "Place names: Government of Greenland (Nunat Aqqi)",
    "지명 검색: 노르웨이 극지연구소 (드로닝모드랜드)": "Place names: Norwegian Polar Institute (Dronning Maud Land)",
    "지명 검색: 노르웨이 극지연구소 · 그린란드 정부": "Place names: Norwegian Polar Institute · Government of Greenland",
    "지명 검색": "Place names",
    "지명": "Place name",
    # 온 지구의 찾기 칸 — 결과의 갈래 딱지 (wetherilli 187)
    "화산": "Volcano",
    "지층": "Formation",
    "화석": "Fossil",
    "화석 산지 {n} 곳": "{n} fossil collections",
    "마지막 분화 {year}": "last eruption {year}",
    # 일본 — GSJ 심리스 지질도·국토지리원 배경 (gsj.py·map.js, devlog 024)
    "일본 담색 지도 (국토지리원)": "Japan pale map (GSI)",
    "일본 국토지리원. 지질도 밑에 깔기 좋다": "Geospatial Information Authority of Japan. Good under a geological map",
    "일본 표준 지도 (국토지리원)": "Japan standard map (GSI)",
    "일본 국토지리원": "Geospatial Information Authority of Japan",
    "일본 항공사진 (국토지리원)": "Japan aerial photos (GSI)",
    "일본 국토지리원. 일본 밖은 줌 8 까지만 그린다":
        "Geospatial Information Authority of Japan. Outside Japan it draws only up to zoom 8",
    "일본 음영기복 (국토지리원)": "Japan hillshade (GSI)",
    "일본 국토지리원. 지형을 지질도와 견줄 때":
        "Geospatial Information Authority of Japan. For comparing terrain with geology",
    # 대만 — 국토측회중심 배경 (map.js, wetherilli 141)
    "범위가 넓다 — 더 들어오면 범례가 뜬다": "The extent is too wide — zoom in to see the legend",
    # 정적 판 — 각자 넣는 KIGAM 키 (map.js, wetherilli P11·162)
    "KIGAM 인증키를 넣었다 — 이 브라우저에만 있다": "KIGAM API key set — kept only in this browser",
    "키 지우기": "Clear key",
    "<b>한국 지질도는 각자의 KIGAM 인증키로 본다.</b> 지오빅데이터 오픈플랫폼에서 받은 키를 넣는다 — 이 브라우저에만 남고 KIGAM 에만 간다.":
        "<b>Korean geological maps use your own KIGAM API key.</b> Enter the key issued by the Geo Big Data Open Platform — it stays in this browser and goes only to KIGAM.",
    "인증키": "API key",
    "이 PC 에 기억하지 않기": "Don't remember on this computer",
    "넣기": "Save",
    # 정적 판 — KIGAM·VWorld 키를 처음 열 때 받는다 (map.js, wetherilli 174)
    "KIGAM 인증키": "KIGAM API key",
    "VWorld 인증키": "VWorld API key",
    "한국 지질도": "Korean geological maps",
    "배경지도·주소 찾기·지질 참고": "Basemaps, address search, geology references",
    "지오빅데이터 오픈플랫폼에서 받기": "Get one from the Geo Big Data Open Platform",
    "VWorld 에서 받기": "Get one from VWorld",
    "인증키 둘을 넣었다 — 이 브라우저에만 있다": "Both API keys are set — kept only in this browser",
    "KIGAM 에 키를 물어 보는 중…": "Checking the key with KIGAM…",
    "그래도 연다": "Open anyway",
    "KIGAM 이 이 키로 지질도를 주지 않았다. 키를 다시 붙여 넣어 본다 — 휴대폰에서 손으로 옮겨 적으면 한 글자만 틀려도 안 된다. 키를 받을 때 쓸 곳(IP·주소)을 적었다면 이 기기가 그 밖인지도 본다.":
        "KIGAM did not return a map for this key. Try pasting the key again — one wrong character typed by hand on a phone is enough to fail. If you gave a place of use (IP or address) when you got the key, check whether this device is outside it.",
    "KIGAM(data.kigam.re.kr)에 닿지 못했다. 이 망(회사·학교 Wi-Fi, VPN, 광고 차단)이 막거나 기기가 인증서를 받지 않는다 — 다른 망(모바일 데이터)에서 열어 본다.":
        "Could not reach KIGAM (data.kigam.re.kr). This network (office or school Wi-Fi, a VPN, an ad blocker) may block it, or the device may not accept its certificate — try another network such as mobile data.",
    "{name} 만 넣었다": "Only the {name} is set",
    "인증키를 넣어야 한국 지질도와 배경지도가 보인다": "Enter API keys to see Korean geological maps and basemaps",
    "키 바꾸기": "Change keys",
    "키 넣기": "Enter keys",
    "인증키 넣기": "Enter API keys",
    "이 판은 연구소 밖에서 서버 없이 돈다. <b>지질도와 배경지도는 각자 받은 인증키로 본다.</b> 키는 이 브라우저에만 남고 그 키를 준 곳(KIGAM·VWorld)에만 간다.":
        "This edition runs outside the institute without a server. <b>Geological maps and basemaps use your own API keys.</b> The keys stay in this browser and go only to the services that issued them (KIGAM, VWorld).",
    "넣어 두었다 — 바꾸려면 새로 적는다": "Already set — type a new one to change it",
    "VWorld 키를 받을 때 서비스 URL 에 이 판의 주소({url})를 적는다.": "When applying for a VWorld key, enter this site's address ({url}) as the service URL.",
    "나중에": "Later",
    "저장": "Save",
    "키 받기": "Get a key",
    "대만 회색 지도 (국토측회중심)": "Taiwan grey map (NLSC)",
    "대만 내정부 국토측회중심. 지질도 밑에 깔기 좋다": "National Land Surveying and Mapping Center, Taiwan. Good under a geological map",
    "대만 전자지도 (국토측회중심)": "Taiwan e-Map (NLSC)",
    "대만 내정부 국토측회중심": "National Land Surveying and Mapping Center, Taiwan",
    "대만 정사영상 (국토측회중심)": "Taiwan orthophotos (NLSC)",
    "대만 내정부 국토측회중심. 대만 밖은 비어 있다": "National Land Surveying and Mapping Center, Taiwan. Empty outside Taiwan",
    "대만 음영기복 (국토측회중심)": "Taiwan hillshade (NLSC)",
    "대만 내정부 국토측회중심. 지형을 지질도와 견줄 때":
        "National Land Surveying and Mapping Center, Taiwan. For comparing terrain with geology",
    "줌 {n} 부터 그려진다": "Drawn from zoom {n}",
    "선·기호의 범례는 GSJ 가 따로 주지 않는다": "GSJ gives no separate legend for lines and symbols",
    "원본 뷰어에서 본다 — GSJ": "See it in the original viewer — GSJ",
    # 중국 — USGS geo3al (geo3al.py·views.py·map.js, devlog 025)
    "중국 지질도 자료(USGS geo3al)가 서버에 없다": "The China geology data (USGS geo3al) is not on the server",
    "중국 지질도 자료(USGS geo3al)를 읽지 못했다": "Could not read the China geology data (USGS geo3al)",
    "원본 자료 — USGS geo3al (OFR 97-470F). 연구실 내부용, 재배포 금지":
        "Source dataset — USGS geo3al (OFR 97-470F). Internal lab use only, no redistribution",
    "관입 화성암": "Intrusive igneous rock",
    "분출 화성암": "Extrusive igneous rock",
    "초염기성암·오피올라이트": "Ultrabasic rock or ophiolite",
    "풍성 퇴적물": "Eolian deposits",
    "기호 풀이 없음 (x)": "Code not explained (x)",
    "지금 보는 범위에 든 것 {n}칸": "{n} units in the current extent",
    "지금 보는 범위에는 칠해진 것이 없다": "Nothing is mapped in the current extent",
    "…그 밖 {n}칸 — 더 들어가면 줄어든다": "…and {n} more — zoom in to narrow it down",
    "layer·lat·lon 이 없다": "layer, lat or lon is missing",
    # 남극 자력 이상 ADMAP-2 (wetherilli 262)
    "자력 이상": "Magnetic anomaly",
    "자력 이상 자료(ADMAP-2)가 서버에 없다": "The magnetic anomaly data (ADMAP-2) is not on the server",
    "영국 남극조사소": "British Antarctic Survey",
    # 대앤틸리스 — USGS SIM 3534 를 우리가 굽는다 (wetherilli 254)
    "대앤틸리스 지질도 파일이 서버에 없다": "The Greater Antilles geologic map file is not on the server",
    "덮인 단층": "Concealed fault",
    "단층 (변위 모름)": "Fault (displacement uncertain)",
    "범례가 없는 레이어다": "This layer has no legend",
    "범례 열기": "Open legend",
    "bbox 가 없다": "bbox is missing",
    # 데이터소스 명세의 검사 (jikhanjung P02)
    "줄이 객체가 아니다": "The row is not an object",
    "id 가 없거나 꼴이 틀렸다 (영어 소문자·숫자·밑줄)": "id is missing or malformed (lowercase letters, digits, underscore)",
    "name 에 ko·en 이 다 있어야 한다": "name needs both ko and en",
    "{key} 는 {allowed} 가운데 하나다": "{key} must be one of {allowed}",
    "commands 는 명령 이름의 목록이다": "commands must be a list of command names",
    "받거나 굽는 데이터소스인데 commands 가 비었다": "A fetched or built source has no commands",
    "license 가 없다": "license is missing",
    "flags 는 {allowed} 가운데서 고른다": "flags must be chosen from {allowed}",
    "{key} 는 글의 목록이다": "{key} must be a list of strings",
    "{key} 는 글이다": "{key} must be a string",
    "id 가 겹친다": "Duplicate id",
    "맨 위에 sources 목록이 있어야 한다": "The top level needs a sources list",
    "명세 파일을 JSON 으로 읽지 못했다 — 마지막으로 떠 둔 판을 쓴다": "Could not read the spec file as JSON — using the last saved copy",
    "명세도 씨앗도 없다": "Neither the spec nor the seed exists",
    # 관리 화면 "데이터소스" 탭 (jikhanjung P02 3 단계)
    "데이터소스": "Sources",
    "받아 두는 데이터소스": "Collected sources",
    "조건·주기·마지막으로 받은 때·결과·산출물 — 줄을 누르면 지난 차례": "Terms · schedule · last run · result · outputs — tap a row for past runs",
    "조건": "Terms",
    "주기": "Schedule",
    "마지막 실행": "Last run",
    "마지막 성공": "Last success",
    "결과": "Result",
    "앞 판과 같다": "same as the previous copy",
    "바뀐 것 {n}": "{n} changed",
    "상류 판": "upstream version",
    "씨앗과 다른 줄 {n}": "Differs from the seed: {n}",
    "씨앗과 다름": "differs from seed",
    "씨앗과 다른 칸 — 판을 올려도 덮지 않는다. 옮길지는 사람이 정한다": "Fields that differ from the repository seed — releases do not overwrite them; a person decides whether to copy them over",
    "산출물": "Outputs",
    "저장소": "repository",
    "기록 없음": "no record",
    "기록 없음 {n}": "No record {n}",
    "늦음": "late",
    "늦음 {n}": "Late {n}",
    "깨짐 {n}": "Failed {n}",
    "명세를 고친 때 {when}": "Spec changed {when}",
    "명세에서 건너뛴 줄": "Skipped spec row",
    "운영 명세가 아니라 {origin} 을 읽었다": "Read the {origin} copy, not the live spec",
    "데이터소스 장부를 읽지 못했다 — 서버 기록을 본다": "Could not read the source register — see the server log",
    "산출물 파일의 고친 날로 어림했다": "Estimated from the output file's modification time",
    # 장부의 코드 값과 장부가 스스로 적는 문장 (#373 검토 4)
    "성공": "ok",
    "실패": "failed",
    "건너뜀": "skipped",
    "매시 차례": "hourly run",
    "어림": "estimate",
    "명세": "spec",
    "저장소의 씨앗": "the repository seed",
    "마지막으로 떠 둔 판": "the last saved copy",
    "빈 명세": "an empty spec",
    "명세가 없다 — 서버에서 manage.py sources_seed 를 부르면 저장소의 씨앗을 놓는다": "No spec — run manage.py sources_seed on the server to place the repository seed",
    "마지막으로 된 차례": "Last successful run",
    "마지막으로 된 차례 — 끝난 때 (걸린 초는 모른다)": "Last successful run — time it ended (duration unknown)",
    "명세가 바뀌었다 — {name}": "Spec changed — {name}",
    "센 수 {e} · 받은 수 {n}": "counted {e} · received {n}",
    "받은 차례가 아직 없다": "No runs recorded yet",
    "명세는 서버의 sources.json 을 손으로 고친다. 받은 차례는 명령이 끝날 때 저절로 쌓이고, 서버 쪽에서는 manage.py sources_log 로 같은 것을 본다.":
        "The spec is edited by hand in sources.json on the server. Runs are recorded when each command finishes; on the server, manage.py sources_log shows the same.",
    "매시": "hourly",
    "매주": "weekly",
    "매달 첫 월요일": "first Monday monthly",
    "사람이": "by hand",
    "한 번": "once",
    "컨테이너": "container",
    "호스트": "host",
    "사람 손": "person",
    "비상업": "non-commercial",
    "판매": "sold",
    "내부용": "lab only",
    "담지 않음": "not cached",
    # 5만 지질도의 자세 기호 — 커서와 팝업 (jikhanjung 004)
    "미상": "unknown",
    "경사 방향과 원문 사분면이 맞지 않는다 — 기호는 경사 방향대로 그렸다":
        "Dip direction disagrees with the original quadrant — the symbol follows the dip direction",
    "KIGAM 5만 지질도 · {date} 받음": "KIGAM 1:50K geological map · fetched {date}",
    "패널을 접는다": "Collapse the panel",
    "패널을 편다": "Expand the panel",
    "줌 {z}": "Zoom {z}",
    "줌 수준 — 한 단계 오를 때마다 두 배로 가까워진다": "Zoom level — each step is twice as close",
    "켜면 늘 그리고, 끄면 커서를 올릴 때만 그린다 — 줌 {n} 부터":
        "Checked: always drawn. Unchecked: drawn only under the cursor — from zoom {n}",
    "층리": "Bedding", "수직층리": "Vertical bedding", "역전층리": "Overturned bedding", "수평층리": "Horizontal bedding",
    "엽리": "Foliation", "수직엽리": "Vertical foliation",
    "1차엽리": "Primary foliation", "2차엽리": "Secondary foliation", "3차엽리": "Tertiary foliation",
    "편리": "Schistosity", "경사미상 편리": "Schistosity (dip unknown)",
    "1차편리": "Primary schistosity", "2차편리": "Secondary schistosity", "3차편리": "Tertiary schistosity",
    "절리": "Joint", "수직절리": "Vertical joint",
    # 암맥 기록 — phyloserver (devlog 026)
    "산성암맥": "Felsic dikes",
    "중성암맥": "Intermediate dikes",
    "염기성암맥": "Mafic dikes",
    "석영맥·광맥": "Quartz & ore veins",
    "그 밖·미상": "Other / unknown",
    "암맥 {n}건 · 줌 {z} 아래에서는 도폭 {m}곳의 로즈": "{n} dikes · below zoom {z}, rose diagrams for {m} map sheets",
    "갈래는 적힌 암석 이름에서 GSM 이 가른 것이다": "Classes are GSM's grouping of the recorded rock names",
    "원본 기록 — phyloserver": "Original records — phyloserver",
    # 극지연구소 (053–057)
    "극지연구소 자료를 아직 모으지 않았다 (fetch_kopri)": "KOPRI data has not been harvested yet (fetch_kopri)",
    "극지연구소 자료를 읽지 못했다": "Could not read the KOPRI data",
    "남극 전체처럼 넓은 범위의 자료 {n}건은 그리지 않았다": "{n} datasets with continent-wide extents are not drawn",
    "원본 자료 — 극지연구소 KPDC": "Source — Korea Polar Data Center (KOPRI)",
    "퇴적암": "Sedimentary",
    "화산암": "Volcanic",
    "화성암·심성암": "Igneous / plutonic",
    "변성암": "Metamorphic",
    "해양 퇴적물·코어": "Marine sediments & cores",
    "고체지구": "Solid Earth",
    "고기후": "Paleoclimate",
    "빙권": "Cryosphere",
    "해양": "Oceans",
    "대기": "Atmosphere",
    "생물": "Biosphere",
    "그 밖": "Other",
    "운석 발견 지점": "Meteorite find",
    "대한민국 기지": "Korean station",
    "상주 기지": "Year-round station",
    "하계 기지": "Seasonal station",
    "그 밖 시설": "Other facility",
    # 아라온호 항적 (koprifossillab 006)
    "아라온호 마지막 자리": "Araon, latest position",
    "아라온호 항적": "Araon track",
    "지난 항적 (날짜는 하루 단위)": "Past track (dated to the day)",
    "쇄빙연구선 아라온호": "Icebreaker RV Araon",

    # ── 소개 (wetherilli 113) ──
    "대돌여지도 소개": "About Great Stone Map",
    "지질도를 겹쳐 보고, 눌러 속성을 읽고, 내 좌표를 얹는 지도 — 한국·극지·일본, 그리고 달과 화성까지.":
        "Overlay geological maps, click to read attributes, drop your own coordinates on top — Korea, the poles, Japan, and on to the Moon and Mars.",
    "언어": "Language",
    "지도로 바로 가기": "Go to the map",
    "한국 지도": "Korea map",
    "장면": "Scenes",
    "불편": "The problem",
    "극지": "Polar",
    "우주": "Space",
    "시작": "Start",
    "자동 재생": "Autoplay",
    "멈춤": "Pause",
    "도폭은 PDF 한 장씩 — 경계를 넘으면 다른 파일을 엽니다": "One PDF per map sheet — cross the edge and you open another file",
    "기관마다 사이트도, 쓰는 법도 다릅니다": "Every agency has its own site, and its own way of using it",
    "좌표계와 투영이 제각각이라 내 좌표부터 바꿔야 합니다": "Datums and projections all differ, so you convert your own coordinates first",
    "이 색이 무슨 지층인지, 범례를 따로 찾아야 합니다": "Which formation is this colour? You go hunting for the legend",
    "극지 자료는 어디에 있는지부터 모릅니다": "Polar data — you don't even know where it lives",
    "지질도를 볼 때,<br>불편한 점이 많지 않았나요?": "Reading geological maps —<br>hasn't it been a hassle?",
    "그래서 한 화면에 모았습니다.": "So we put it all on one screen.",
    "지질도를 겹쳐 보고, 눌러 속성을 읽고, 내 좌표를 얹는 지도 — 대돌여지도입니다.":
        "A map for overlaying geological maps, clicking to read attributes and adding your own coordinates — Great Stone Map.",
    "남극 지도": "Antarctica map",
    "그래서": "So",
    "우리가 일하는 <b>극지</b>부터 보여 드립니다.":
        "We start where we work — <b>the poles</b>.",
    "가는 길": "Route",
    "남극은 남극점을 가운데 두고 봅니다.": "Antarctica, seen with the South Pole at the centre.",
    "메르카토르에서 찢어지던 대륙이 <b>제 모양</b>으로 섭니다. SCAR GeoMAP 지질도는 <b>우리 서버가 직접</b> 그립니다.":
        "The continent that Mercator tears apart stands in its <b>true shape</b>. <b>Our server draws</b> the SCAR GeoMAP geology itself.",
    "가까이 가면 <b>극지연구소가 모은 암석 시료</b>의 자리가 뜹니다. 장보고기지가 있는 빅토리아랜드입니다.":
        "Zoom in and the locations of <b>KOPRI's rock samples</b> appear. This is Victoria Land, home of Jang Bogo Station.",
    "남극 지역 화면 — 남극 평사도법의 대륙 전체에 GeoMAP 지질도와 암석 시료":
        "Antarctica tab — GeoMAP geology and rock samples over the whole continent in polar stereographic",
    "빅토리아랜드를 가까이 본 화면 — 지질도 위의 극지연구소 암석 시료 점":
        "Close-up of Victoria Land — KOPRI rock sample points over the geology",
    "그린란드 지도": "Greenland map",
    "그린란드는 GEUS의 50만 지질도로.": "Greenland, with the GEUS 1:500,000 geological map.",
    "동그린란드 화면 — GEUS 50만 지질도": "East Greenland — GEUS 1:500,000 geology",
    "스발바르 지도": "Svalbard map",
    "스발바르 · 다산기지가 있는 곳": "Svalbard · home of Dasan Station",
    "스발바르는 노르웨이 극지연구소의 지질도로.": "Svalbard, with the Norwegian Polar Institute's geological maps.",
    "흩어진 극지 자료를 한 자리에": "Scattered polar data, in one place",
    "<b>남극</b> — SCAR GeoMAP, IBCSO 해저지형, 드로닝모드랜드(NPI), 기지·운석 발견 지점":
        "<b>Antarctica</b> — SCAR GeoMAP, IBCSO bathymetry, Dronning Maud Land (NPI), stations and meteorite finds",
    "<b>그린란드</b> — GEUS 지질도·지화학, 정부 포털의 시료·광물 산출지":
        "<b>Greenland</b> — GEUS geology and geochemistry, samples and mineral occurrences from the government portal",
    "<b>스발바르·얀마옌</b> — NPI 지질도·도폭·빙하 전면 변화":
        "<b>Svalbard &amp; Jan Mayen</b> — NPI geology, map sheets and glacier front changes",
    "<b>북극해</b> — KPDC 관측 자료": "<b>Arctic Ocean</b> — KPDC observation data",
    "기관마다 다른 투영과 서버를 <b>극 평사도법(3031·3413) 하나</b>로 맞췄습니다.":
        "Each agency's projection and server, aligned into <b>one polar stereographic</b> (3031 · 3413).",
    "스발바르 화면 — NPI 지질 단위와 단층, 극지연구소 암석 시료":
        "Svalbard tab — NPI geological units and faults, KOPRI rock samples",
    "다시 한국으로": "Back to Korea",
    "지질도를 지형 위에 얹습니다.": "Geology draped over the terrain.",
    "보던 자리에서 <b>3D 단추 하나</b>면 됩니다. 25만 지질도가 태백산맥을 따라 접힙니다.":
        "<b>One 3D button</b> from wherever you are. The 1:250,000 geology folds along the Taebaek Mountains.",
    "가까이 가면 5만 지질도입니다. 기울이고 돌려 가며 <b>지층과 단층</b>이 산줄기 어디로 이어지는지 봅니다. 설악산입니다.":
        "Closer in, the 1:50,000 map. Tilt and turn to follow <b>strata and faults</b> across the ridges. This is Seoraksan.",
    "3D 화면 — 지형 위에 얹은 25만 지질도": "3D view — 1:250,000 geology draped over the terrain",
    "3D 화면 — 설악산 지형 위의 5만 지질도": "3D view — 1:50,000 geology over Seoraksan",
    "야외에서 쓰는 도구": "Tools for the field",
    "찍고, 재고, 남깁니다.": "Mark, measure, keep.",
    "<b>점 찍기</b> — 누른 자리의 위경도를 적고, 목록으로 저장합니다.":
        "<b>Points</b> — note the latitude and longitude where you click, and save them as a list.",
    "<b>거리와 높이</b> — 선을 그으면 거리와 함께 높이 그래프가 뜹니다.":
        "<b>Distance and elevation</b> — draw a line and an elevation graph appears with the distance.",
    "<b>넓이</b> — 면을 두르면 넓이가 km²와 ha로 뜹니다.":
        "<b>Area</b> — outline a polygon and its area appears in km² and ha.",
    "<b>그림으로 내려받기</b> — 지금 보는 지도를 축척·좌표·출처가 붙은 PNG 한 장으로 받습니다.":
        "<b>Save as image</b> — download the current map as a PNG with scale bar, coordinates and sources.",
    "내 CSV·GeoJSON을 올리면 <b>점묶음</b>으로 지도에 얹힙니다.":
        "Upload your CSV or GeoJSON and it lands on the map as a <b>point set</b>.",
    "점을 찍은 화면 — 번호가 붙은 점 둘": "Marked points — two numbered points",
    "거리를 잰 화면 — 선 아래에 높이 그래프": "Measured distance — an elevation graph beneath the line",
    "넓이를 잰 화면 — 두른 면에 넓이가 적혀 있다": "Measured area — the area written on the outlined polygon",
    "내려받은 PNG — 지도 아래에 레이어·가운데 좌표·출처·축척 막대":
        "Downloaded PNG — layers, centre coordinates, sources and scale bar beneath the map",
    "여러 출처, 한 화면": "Many sources, one screen",
    "기관마다 다른 지도를 한 화면에서.": "Different agencies' maps, on a single screen.",
    "<b>한국지질자원연구원</b> — 5만·25만·100만 지질도부터 지화학도·해저지질도까지, 지오빅데이터 오픈플랫폼의 주제도.":
        "<b>KIGAM</b> — from 1:50,000, 1:250,000 and 1:1,000,000 geology to geochemical and marine geology maps, the thematic maps of the Geo Big Data Open Platform.",
    "<b>국토교통부 VWorld</b> — 단층·수문지질·보호구역·행정경계. 국가 공간정보를 같은 자리에 겹칩니다.":
        "<b>VWorld (Ministry of Land, Infrastructure and Transport)</b> — faults, hydrogeology, protected areas, boundaries: national spatial data in the same place.",
    "일본 지도": "Japan map",
    "그 밖에 GEUS · NPI · SCAR · USGS · NASA · Macrostrat …": "Plus GEUS · NPI · SCAR · USGS · NASA · Macrostrat …",
    "한국 지역 화면 — 설악산 둘레의 KIGAM 5만 지질도": "Korea tab — KIGAM 1:50,000 geology around Seoraksan",
    "같은 자리에 VWorld 위성 배경과 단층·수문지질단위": "The same place with the VWorld satellite basemap, faults and hydrogeological units",
    "일본 지역 화면 — 후지산 둘레의 GSJ 20만 심리스 지질도": "Japan tab — GSJ 1:200,000 seamless geology around Mount Fuji",
    "그리고": "And then",
    "지구를 넘어, 우주로.": "Beyond Earth, into space.",
    "둥근 달 위의 지질도.": "Geology on a round Moon.",
    "USGS 달 통합 지질도와 LOLA 지형. <b>아폴로 착륙지</b>와 1970년대 <b>원도 여섯 장</b>도 있습니다.":
        "The USGS Unified Geologic Map of the Moon and LOLA terrain, with the <b>Apollo landing sites</b> and <b>six original 1970s maps</b>.",
    "붉은 행성의 지층까지.": "Down to the strata of the red planet.",
    "USGS 화성 지질도와 MOLA–HRSC 지형, <b>크레이터 38만 개</b>.":
        "The USGS geologic map of Mars, MOLA–HRSC terrain and <b>380,000 craters</b>.",
    "지질도 USGS · 지형·영상 NASA Trek": "Geology USGS · Terrain and imagery NASA Trek",
    "달 화면 — 둥근 달 위의 USGS 지질도": "Moon view — USGS geology on the globe",
    "화성 화면 — 둥근 화성 위의 USGS 지질도": "Mars view — USGS geology on the globe",
    "수성 화면 — 둥근 수성 위의 USGS 지질도": "Mercury view — USGS geology on the globe",
    "둥근 지구와 달, 화성, 수성": "The Earth, the Moon, Mars and Mercury as globes",
    "둥근 지구": "The Earth as a globe",
    "해에 가장 가까운 행성의 지질도.": "A geologic map of the planet nearest the Sun.",
    "마리너 10 시절의 USGS 1:500만 지질도 아홉 장을 MESSENGER 영상 위에. <b>엽상 급사면</b>과 칼로리스 분지의 고리까지.":
        "Nine USGS 1:5M geologic maps from the Mariner 10 era over MESSENGER imagery — down to <b>lobate scarps</b> and the rings of the Caloris basin.",
    "지질도 USGS · 영상·지형 MESSENGER(NASA Trek)": "Geology USGS · imagery and terrain MESSENGER (NASA Trek)",
    "USGS 1:500만 지질도 · MESSENGER 영상·지형": "USGS 1:5M geology · MESSENGER imagery and terrain",
    "이제 직접 볼 차례입니다": "Your turn",
    "어디부터 볼까요?": "Where would you like to start?",
    "KIGAM 지질도와 VWorld": "KIGAM geology and VWorld",
    "남극점을 가운데 둔 GeoMAP": "GeoMAP centred on the South Pole",
    "그린란드·스발바르·얀마옌을 한 화면에": "Greenland, Svalbard and Jan Mayen on one screen",
    "GSJ 심리스 지질도": "GSJ seamless geology",
    "지형 위의 지질도": "Geology on terrain",
    "Macrostrat 지질도와 판의 옛 자리": "Macrostrat geology and where the plates once were",
    "자료의 주인은 저마다의 기관입니다 — 한국지질자원연구원, 국토교통부(VWorld), GEUS, 노르웨이 극지연구소, SCAR GeoMAP, 일본 산업기술종합연구소, USGS, NASA, 극지연구소 KPDC 등. 이 쪽의 그림은 대돌여지도 화면을 찍은 것입니다.":
        "The data belong to their agencies — KIGAM, the Ministry of Land, Infrastructure and Transport (VWorld), GEUS, the Norwegian Polar Institute, SCAR GeoMAP, AIST, USGS, NASA, KOPRI KPDC and others. The pictures on this page are screenshots of Great Stone Map.",
    "만든 곳 — 극지연구소 고생물진화연구실": "Made by the Lab. of Paleontology &amp; Evolution in KOPRI",
    "코드는 AGPL-3.0": "Code under AGPL-3.0",
    "소스": "Source",
    # ── 소개 다듬기 (wetherilli 115) ──
    "극지연구소 고생물진화연구실": "Lab. of Paleontology &amp; Evolution in KOPRI",
    "지질도를 겹쳐 보고, 눌러 속성을 읽고, 내 좌표를 얹는 지도.":
        "A map for overlaying geological maps, clicking to read attributes and adding your own coordinates.",
    "다루는 곳": "Where it covers",
    "할 수 있는 것": "What it does",
    "지질도 겹쳐 보기": "Overlay geological maps",
    "눌러 속성 읽기": "Click to read attributes",
    "극 평사도법": "Polar stereographic",
    "3D 지형": "3D terrain",
    "거리·넓이·단면": "Distance, area, profile",
    "CSV·GeoJSON 올리기": "Upload CSV and GeoJSON",
    "둘러보기": "Take the tour",
    "대돌여지도의 한국 지역 화면": "Great Stone Map's Korea tab",
    "극지연구소": "Korea Polar Research Institute (KOPRI)",
    "에서 만들었습니다.": "made this map.",
    "만든 이 — 극지연구소 이승찬 · 극지연구소 정직한": "Made by Seungchan Lee (KOPRI) · Jikhan Jung (KOPRI)",
    "드로닝모드랜드는 노르웨이 극지연구소의 <b>1:25만 지질도</b>와 구조선으로.":
        "Dronning Maud Land, with the Norwegian Polar Institute's <b>1:250,000 geology</b> and structural lines.",
    "<b>빙상 밑의 땅</b>(IBCSO)을 배경으로 깔고, 남극의 <b>기지와 운석 발견 지점</b>을 얹습니다.":
        "With <b>the land beneath the ice sheet</b> (IBCSO) as the basemap, add <b>Antarctic stations and meteorite finds</b>.",
    "지질도 SCAR GeoMAP·NPI · 시료·기지·운석 위치 극지연구소 KPDC · 배경 PGC REMA·IBCSO":
        "Geology SCAR GeoMAP · NPI · Sample, station and meteorite locations KOPRI KPDC · Basemap PGC REMA · IBCSO",
    "드로닝모드랜드 — NPI 지질 단위와 구조선": "Dronning Maud Land — NPI geological units and structural lines",
    "IBCSO 빙저 지형 위의 남극 기지와 운석 발견 지점": "Antarctic stations and meteorite finds over IBCSO bed topography",
    "덴마크·그린란드 지질조사소(GEUS)의 지질도. 동그린란드의 <b>퇴적분지</b>가 색으로 드러납니다.":
        "The Geological Survey of Denmark and Greenland (GEUS) map — East Greenland's <b>sedimentary basins</b> stand out in colour.",
    "GEUS의 <b>하천 퇴적물 지화학도</b>도 같은 화면에서 켭니다.":
        "GEUS <b>stream-sediment geochemistry</b> switches on in the same view.",
    "그린란드 정부 포털의 <b>연대측정 지점</b>과 극지연구소 시료를 겹쳐 봅니다.":
        "Overlay <b>dating sites</b> from the Greenland government portal and KOPRI's samples.",
    "지질도·지화학 GEUS · 연대측정 그린란드 정부 포털 · 시료 위치 극지연구소 KPDC · 배경 PGC ArcticDEM":
        "Geology and geochemistry GEUS · Dating Greenland government portal · Sample locations KOPRI KPDC · Basemap PGC ArcticDEM",
    "남서 그린란드 — 하천 퇴적물 지화학도": "Southwest Greenland — stream-sediment geochemistry",
    "그린란드 전체 — 정부 포털의 연대측정 지점": "All of Greenland — dating sites from the government portal",
    "NPI의 지질 단위·단층을 그대로 받아 오고, <b>극지연구소 암석 시료</b>를 함께 얹습니다.":
        "NPI's geological units and faults come straight through, with <b>KOPRI's rock samples</b> on top.",
    "<b>종이로 찍었던 지질도</b>도 음영째 그대로 볼 수 있습니다.":
        "<b>The printed paper maps</b> are there too, hill shading and all.",
    "다산기지가 있는 뉘올레순 — <b>1936년부터 2025년까지</b> 빙하 전면이 물러난 자리.":
        "Ny-Ålesund, home of Dasan Station — where the glacier fronts retreated <b>from 1936 to 2025</b>.",
    "얀마옌 지도": "Jan Mayen map",
    "얀마옌 — 북대서양의 화산섬. NPI 지질도를 모양째 받아 <b>우리가 그립니다</b>.":
        "Jan Mayen — a volcanic island in the North Atlantic. We take NPI's geology as shapes and <b>draw it ourselves</b>.",
    "지질도·빙하 NPI · 시료 위치 극지연구소 KPDC · 배경 NPI Sentinel-2·PGC ArcticDEM":
        "Geology and glaciers NPI · Sample locations KOPRI KPDC · Basemap NPI Sentinel-2 · PGC ArcticDEM",
    "롱위에아르뷔엔 둘레의 NPI 종이 지질도(음영)": "NPI paper geological map (shaded) around Longyearbyen",
    "뉘올레순 둘레의 빙하 전면 변화 선": "Glacier front change lines around Ny-Ålesund",
    "얀마옌 지질도 — 지질 단위와 분화구": "Jan Mayen geology — units and vents",
    "<b>극지도 3D로</b> — 스발바르의 NPI 지질 단위를 ArcticDEM 지형 위에.":
        "<b>The poles in 3D too</b> — Svalbard's NPI geological units on ArcticDEM terrain.",
    "지질도 한국지질자원연구원·NPI · 지형 AWS Terrain Tiles·ArcticDEM · 배경 VWorld":
        "Geology KIGAM · NPI · Terrain AWS Terrain Tiles · ArcticDEM · Basemap VWorld",
    "3D 화면 — 스발바르 지형 위의 NPI 지질 단위": "3D view — NPI geological units over Svalbard terrain",
    "<b>일본 지질조사종합센터(GSJ)</b> — 20만 심리스 지질도.": "<b>Geological Survey of Japan (GSJ)</b> — the 1:200,000 seamless geological map.",
    "동아시아 지도": "East Asia map",
    "<b>동아시아</b> — 한국과 일본의 지질도가 한 화면에 이어집니다.": "<b>East Asia</b> — Korean and Japanese geology join on one screen.",
    "KIGAM 지화학도 — 하천 퇴적물의 구리": "KIGAM geochemical map — copper in stream sediments",
    "KIGAM 해저지질도 — 표층퇴적물 유형": "KIGAM marine geology — surface sediment types",
    "동아시아 화면 — 한반도 남부의 KIGAM 25만과 규슈의 GSJ 지질도": "East Asia tab — KIGAM 1:250,000 in southern Korea and GSJ geology in Kyushu",
    "한국과 일본을 한 화면에": "Korea and Japan on one screen",
    "USGS 달 통합 지질도 · LOLA 지형 · 원도 여섯 장 · 아폴로 착륙지":
        "USGS Unified Geologic Map · LOLA terrain · six original maps · Apollo landing sites",
    "USGS 화성 지질도 · MOLA–HRSC 지형 · 크레이터 38만 개": "USGS geologic map · MOLA–HRSC terrain · 380,000 craters",
    # (wetherilli 119) 극지 정리를 스발바르에서 떼어 따로 세웠다
    "북극 지도": "Arctic map",
    "극지 정리": "The poles, together",
    "극지 화면 여섯 장": "Six polar views",
    # (wetherilli 123) 극지 표지 — 극지 대기 화면
    "대돌여지도 · 극지": "Great Stone Map · Polar",
    # 개인 레이어·관리 화면 (wetherilli P08·118)
    "대돌여지도 관리": "Great Stone Map — manage",
    "관리": "Manage",
    "관리 화면": "Manage page",
    "관리 화면 — 개인 레이어 반입, 저장 자료 관리": "Manage page — import personal layers, manage stored data",
    "지도": "Map",
    "지도로 돌아간다": "Back to the map",
    "개인 레이어": "Personal layers",
    "개인 레이어 반입": "Import personal layer",
    "저장 자료 관리": "Stored data",
    "이 브라우저에만": "this browser only",
    "이 브라우저에만 남는다 — 서버로 보내지 않는다": "Kept in this browser only — never sent to the server",
    "반입·관리": "Import & manage",
    "{name} 외 {n}건": "{name} and {n} more",
    "{name} — 이 자리 {i}/{n}": "{name} — {i} of {n} here",
    # 연결 레이어 (wetherilli P09·122)
    "API 로 잇기": "Link an API",
    "지도를 열 때마다 새로 받는다 — 주소와 인증키는 이 브라우저에만":
        "Fetched afresh each time the map opens — address and key stay in this browser",
    "상대 사이트가 이 양식(JSON·CSV)으로 내주는 주소와 인증키를 넣는다. 브라우저가 곧장 받고, 상대가 CORS 를 열지 않아 막히면 우리 서버를 거친다 — 서버는 받은 것을 넘겨줄 뿐 주소·키를 적지 않는다.":
        "Enter the address and key of an API that serves this format (JSON or CSV). The browser fetches it directly; if the other site does not allow CORS, it goes through our server — which only passes the data along and records neither address nor key.",
    "API 주소": "API address",
    "인증 방식": "Authentication",
    "머리(이름을 적는다)": "Header (enter its name)",
    "주소 뒤 ?이름=키": "Query ?name=key",
    "싣는 이름": "Name",
    "인증키": "API key",
    "받아 본다": "Fetch and preview",
    "'{name}' 의 연결을 고친다": "Editing the link of '{name}'",
    "곧장 받았다": "fetched directly",
    "우리 서버를 거쳐 받았다": "fetched via our server",
    "받지 못했다 — {why}": "Could not fetch — {why}",
    "받지 못했다 ({when}) — {why} · 마지막으로 받은 것을 보인다":
        "Could not fetch ({when}) — {why} · showing the last copy",
    "연결": "Link",
    "지금 새로 받는다": "Fetch now",
    "주소·인증키를 고친다": "Edit address and key",
    "받지 못해 옛것": "stale — fetch failed",
    "마지막으로 받은 때 {when}": "Last fetched {when}",
    "곧장 받지 못했다 — 상대 서버가 CORS 를 열어야 한다": "Could not fetch directly — the other server must allow CORS",
    "우리 서버가 받지 못했다 ({status})": "Our server could not fetch it ({status})",
    "너무 자주 부른다 — 1 분 뒤에 다시": "Too many requests — try again in a minute",
    "요청을 읽지 못했다": "Could not read the request",
    "인증 방식을 모른다": "Unknown authentication method",
    "인증키를 싣는 이름이 없다": "No name to carry the key",
    "쓸 수 없는 머리 이름이다": "That header name cannot be used",
    "인증키가 비었다": "The key is empty",
    "인증키에 줄바꿈이 들었다": "The key contains a line break",
    "주소를 읽지 못했다": "Could not read the address",
    "http·https 주소만 부른다": "Only http and https addresses",
    "주소에 계정을 적지 않는다 — 인증키 칸을 쓴다": "Do not put credentials in the address — use the key field",
    "포트를 읽지 못했다": "Could not read the port",
    "80·443 과 1024 위의 포트만 부른다": "Only ports 80, 443 and above 1024",
    "연구실 망·자기 자신의 주소는 서버가 부르지 않는다": "The server does not call private-network or local addresses",
    "호스트를 찾지 못했다": "Host not found",
    "상대 서버에 닿지 못했다": "Could not reach the other server",
    "상대 서버가 빈 곳으로 넘겼다": "The other server redirected to nowhere",
    "상대 서버가 거절했다 ({status}) — 인증키를 본다": "The other server refused ({status}) — check the key",
    "상대 서버가 주지 않았다 ({status})": "The other server did not return it ({status})",
    "너무 크다 — {mb} MB 까지 받는다": "Too large — up to {mb} MB",
    "받다가 끊겼다": "The connection dropped while fetching",
    "넘겨주기가 너무 많다": "Too many redirects",
    "API 의 목차라 자료 주소를 찾아 이었다 — {url}": "That was the API index — linked to the data address found there: {url}",
    "API 의 목차다 — 자료 주소를 찾지 못했다 ({urls})": "That is the API index — no data address worked ({urls})",
    # 레이어 목록 줄 (wetherilli 133)
    "모두 켜기": "All on",
    "이 묶음의 레이어를 모두 켠다": "Turn on every layer in this group",
    "이 묶음의 레이어를 모두 끈다": "Turn off every layer in this group",
    "그린란드 정부 포털": "Government of Greenland portal",
    "노르웨이 극지연구소": "Norwegian Polar Institute",
    "덴마크·그린란드 지질조사소": "Geological Survey of Denmark and Greenland",
    "미국 지질조사국": "U.S. Geological Survey",
    "미네소타대 극지공간정보센터": "Polar Geospatial Center, University of Minnesota",
    "브이월드(국토교통부)": "VWorld (Ministry of Land, Infrastructure and Transport)",
    "연구실 자료": "Lab data",
    "일본 지질조사종합센터": "Geological Survey of Japan",
    "대만 지질조사·광업관리중심": "Geological Survey and Mining Management Agency (Taiwan)",
    # 꾸밈·용량·모두 끄기 (wetherilli 131)
    "꾸밈": "Style",
    "색·모양을 바꾼다": "Change colour and shape",
    "다른 색": "Other colour",
    "동그라미": "Circle",
    "네모": "Square",
    "마름모": "Diamond",
    "세모": "Triangle",
    "별": "Star",
    "육각": "Hexagon",
    "굵기": "Width",
    "테두리": "Outline",
    "실선": "Solid",
    "파선": "Dashed",
    "점선": "Dotted",
    "채움": "Fill",
    "모양을 처음대로": "Reset style",
    "모두 끄기": "All off",
    "켠 지질 레이어를 모두 끈다": "Turn off every geology layer that is on",
    "용량": "Storage",
    "저장하면 {size}": "Saving takes {size}",
    "지도가 느려질 수 있다": "May slow the map down",
    "'{name}' 이 {size} 다 — 지도가 느려질 수 있다": "'{name}' is {size} — it may slow the map down",
    "개인 레이어가 모두 {size} 다 — 쓰지 않는 것은 지우는 편이 낫다": "Personal layers total {size} — consider deleting unused ones",
    "개인 레이어 {total} · 레이어 하나 {layer} 넘으면, 모두 {all} 넘으면 알린다":
        "Personal layers {total} · warns above {layer} per layer or {all} in total",
    "이 브라우저의 저장소가 거의 찼다 ({used} / {quota}) — 새로 저장하지 못하거나 브라우저가 지울 수 있다":
        "This browser's storage is nearly full ({used} / {quota}) — saving may fail or the browser may evict data",
    "이 브라우저의 저장소를 {pct}% 썼다 ({used} / {quota})": "{pct}% of this browser's storage used ({used} / {quota})",
    "자리가 모자라다 — {need} 가 더 들어야 하는데 남은 것은 {left} 다": "Not enough room — needs {need}, only {left} left",
    "저장하면 이 브라우저의 저장소를 {pct}% 쓴다": "Saving would use {pct}% of this browser's storage",
    "관리 화면에서 정리한다": "Tidy up on the manage page",
    # 양식 예시 (wetherilli 130)
    "양식은 <b>개인 레이어 양식 v1</b> 이다 — GeoJSON 에 <code>gsm</code> 머리를 더한 JSON, 또는 맨 위 <code>#</code> 줄에 머리를 적은 CSV. 점·선·면은 좌표 값의 꼴이 정한다 — <code>lon</code>·<code>lat</code> 이나 Point 면 점, LineString 이면 선, Polygon 이면 면. 섞여 오면 모양마다 레이어로 나눈다. 아래 예시를 본다.":
        "The format is <b>personal layer format v1</b> — GeoJSON with a <code>gsm</code> header, or CSV with the header on leading <code>#</code> lines. The coordinate form decides point, line or polygon — <code>lon</code>/<code>lat</code> or Point is a point, LineString a line, Polygon a polygon. Mixed input is split into one layer per geometry. See the examples below.",
    "양식 예시": "Format examples",
    "이대로 적어 저장하면 반입된다": "Write it like this and it imports",
    "내려받기": "Download",
    "이 예시로 읽어 본다": "Read this example",
    "API 양식 예시": "API format example",
    "노두 단면 1": "Outcrop section 1",
    "석회암": "limestone",
    "맨 위 <code>#열쇠: 값</code> 줄이 머리다 — <code>name</code>(레이어 이름)·<code>source</code>(출처)·<code>label</code>(이름표로 쓸 열)·<code>color</code> 따위. 없어도 읽는다":
        "Leading <code>#key: value</code> lines are the header — <code>name</code> (layer name), <code>source</code>, <code>label</code> (column used for labels), <code>color</code> and so on. Optional",
    "<code>#column: 열 | 화면 이름 | 형식 | 설명</code> — 형식은 <code>string</code>·<code>integer</code>·<code>number</code>":
        "<code>#column: key | display name | type | note</code> — type is <code>string</code>, <code>integer</code> or <code>number</code>",
    "그다음 줄이 열 이름이다. 점은 <code>lon</code>·<code>lat</code>(WGS84 십진도), 선·면은 <code>geometry</code> 칸에 WKT":
        "The next line holds the column names. Points use <code>lon</code>/<code>lat</code> (WGS84 decimal degrees), lines and polygons a WKT <code>geometry</code> column",
    "빈 칸은 값이 없는 것이다. 좌표가 빈 행도 버리지 않는다 — 지도에만 안 뜬다":
        "An empty cell means no value. Rows without coordinates are kept — they just are not drawn",
    "UTF-8 로 저장한다. 한국어 엑셀의 EUC-KR 도 읽는다": "Save as UTF-8. EUC-KR from Korean Excel is read too",
    "GeoJSON <code>FeatureCollection</code> 에 <code>gsm</code> 머리를 더한 것이다. QGIS 따위는 <code>gsm</code> 을 모르고 넘긴다":
        "A GeoJSON <code>FeatureCollection</code> with a <code>gsm</code> header. Tools such as QGIS simply ignore <code>gsm</code>",
    "<code>gsm.columns</code> 는 열마다 <code>key</code>·<code>label</code>·<code>type</code>·<code>note</code>":
        "<code>gsm.columns</code> lists <code>key</code>, <code>label</code>, <code>type</code> and <code>note</code> for each column",
    "좌표는 <code>[경도, 위도]</code> 차례다. <code>geometry</code> 가 <code>null</code> 이면 좌표를 모르는 행이다":
        "Coordinates are <code>[longitude, latitude]</code>. A <code>null</code> <code>geometry</code> marks a row without coordinates",
    "<code>id</code> 는 원본의 번호다 — 있으면 내려받을 때 그대로 나간다": "<code>id</code> is the source record number — kept on download",
    "요청 — 우리가 보낸다. 인증키는 연결할 때 고른 꼴 하나로 싣는다": "Request — we send it. The key goes in the one form chosen when linking",
    "머리 — 이름은 상대가 정한다": "header — the other site names it",
    "주소 뒤": "query string",
    "응답 — 상대가 돌려준다. 본문은 양식 그대로(JSON 또는 CSV)": "Response — the other site returns it. The body is the format as is (JSON or CSV)",
    "열어 주면 브라우저가 곧장 받는다(권함)": "lets the browser fetch directly (recommended)",
    "<code>GET</code> 한 번에 이 양식의 JSON(또는 CSV)을 통째로 준다. 200 이 아니면 받지 못한 것으로 본다 — 401·403 이면 인증키를 보라고 알린다":
        "One <code>GET</code> returns the whole layer in this format (JSON or CSV). Anything but 200 counts as a failure — 401/403 prompt a key check",
    "인증키는 넷 가운데 하나 — 없음, <code>Authorization: Bearer</code>, 머리(이름은 상대가 정한다), 주소 뒤 <code>?이름=키</code>":
        "The key goes one of four ways — none, <code>Authorization: Bearer</code>, a header (named by the other site), or <code>?name=key</code> in the query",
    "CORS 를 열어 주면(<code>Access-Control-Allow-Origin</code>, 머리로 키를 받으면 <code>Access-Control-Allow-Headers</code> 에 그 이름) 보는 사람의 브라우저가 곧장 받는다. 열지 않으면 우리 서버가 대신 받는다":
        "With CORS open (<code>Access-Control-Allow-Origin</code>, plus the header name in <code>Access-Control-Allow-Headers</code> if the key goes in a header) the viewer's browser fetches directly. Otherwise our server fetches on its behalf",
    "IP 로 막는 API 는 우리 서버(극지연구소)의 IP 를 열어 준다 — 그때는 늘 우리 서버가 받는다":
        "For IP-restricted APIs, allow our server's IP (KOPRI) — our server then always does the fetching",
    "20 MB · 20 초 안에 끝나야 한다. 넘겨주기는 세 번까지, 다른 호스트로 넘기면 키를 싣지 않는다":
        "Must finish within 20 MB and 20 seconds. Up to three redirects; the key is not sent to another host",
    "목차(<code>endpoints</code> 의 <code>url</code>)를 주는 주소를 넣어도 같은 호스트의 자료 주소를 찾아간다. 피처 하나(<code>Feature</code>)도 받는다":
        "An index address (<code>url</code> entries under <code>endpoints</code>) works too — the data address on the same host is followed. A single <code>Feature</code> is accepted",
    "너무 오래 걸린다 — {s} 초 안에 받는다": "Taking too long — must finish within {s} seconds",
    "같은 자리에 {n}건 더 있다 — 관리 화면에서 내려받아 본다":
        "{n} more at this spot — download from the manage page to see them",
    "좌표 없음 {n}": "{n} without coordinates",
    "JSON·CSV 파일을 끌어 놓거나 눌러서 고른다": "Drop a JSON or CSV file here, or click to choose",
    "읽은 것": "What was read",
    "이름": "Name",
    "색": "Color",
    "이름표 열": "Label column",
    "열": "Columns",
    "앞의 몇 행": "First rows",
    "이 브라우저에 저장한다": "Save in this browser",
    "버린다": "Discard",
    "읽지 못했다 — {why}": "Could not read — {why}",
    "{kind} 레이어": "{kind} layer",
    "면": "Polygon",
    "행": "Rows",
    "지도에 뜨는 것": "Drawn on the map",
    "좌표가 없는 것": "Without coordinates",
    "{n}행 — 속성은 남긴다": "{n} rows — attributes are kept",
    "이용 조건": "Terms of use",
    "설명": "Description",
    "경고": "Warnings",
    "읽지 못한 것 {n}건": "{n} problems",
    "…외 {n}건": "…and {n} more",
    "형식": "Type",
    "'{name}' 을 저장했다. 지도의 개인 레이어에 뜬다.": "Saved '{name}'. It appears under personal layers on the map.",
    "저장하지 못했다 — {why}": "Could not save — {why}",
    "예시 — 내 시료 위치": "Sample — my sample sites",
    "손으로 적은 예시": "Hand-written sample",
    "시료 번호": "Sample no.",
    "암석": "Rock",
    "연대 (Ma)": "Age (Ma)",
    "U-Pb 저어콘": "U-Pb zircon",
    "화강암": "granite",
    "편마암": "gneiss",
    "사암": "sandstone",
    "저장한 개인 레이어가 없다": "No personal layers stored",
    "원본 파일": "Source file",
    "반입한 날": "Imported",
    "크기": "Size",
    "지도에 보인다": "Shown on the map",
    "이름을 고친다": "Rename",
    "{n} (좌표 {m})": "{n} ({m} with coordinates)",
    "양식 그대로 내려받는다": "Download in the format",
    "'{name}' 을 이 브라우저에서 지운다. 되살릴 수 없다.": "Delete '{name}' from this browser. This cannot be undone.",
    "이 사이트가 쓰는 저장소 {used} / 한도 {quota}": "Storage used by this site {used} / quota {quota}",
    "지우지 않게 해 두었다": "Protected from eviction",
    "공간이 모자라면 브라우저가 지울 수 있다": "The browser may evict it when space runs low",
    "이 브라우저는 청할 수 없다": "This browser cannot request it",
    "브라우저가 받아 주지 않았다 — 즐겨찾기에 넣거나 자주 들어오면 받아 준다":
        "The browser declined — bookmarking the site or visiting often usually helps",
    "브라우저가 지우지 않게 청한다": "Ask the browser not to evict",
    "개인 레이어를 모두 지운다": "Delete all personal layers",
    "개인 레이어를 모두 이 브라우저에서 지운다. 되살릴 수 없다.":
        "Delete all personal layers from this browser. This cannot be undone.",
    "이 브라우저의 설정": "Settings in this browser",
    "지역·켠 레이어·보던 자리·모양 고르기": "regions, layers on, last view, look",
    "설정을 모두 지운다": "Delete all settings",
    "남긴 설정이 없다": "No settings stored",
    "무엇": "What",
    "열쇠": "Key",
    "값": "Value",
    "모양 고르기": "Look",
    "지역 탭": "Region tabs",
    "보던 자리": "Last view",
    "끈 점묶음": "Hidden point sets",
    "패널 접기": "Folded panel",
    "자세 기호": "Attitude symbols",
    "이 브라우저에 남긴 대돌여지도 설정을 모두 지운다. 지도는 처음 모습으로 뜬다.":
        "Delete all Great Stone Map settings in this browser. The map will open as on a first visit.",
    "머리줄이 없다": "No header row",
    "좌표 칸이 없다 — 점은 lon·lat, 면은 geometry(WKT)": "No coordinate columns — lon/lat for points, geometry (WKT) for polygons",
    "좌표 칸 이름이 양식과 다르다 ({lon}·{lat}) — lon·lat 으로 읽었다":
        "Coordinate column names differ from the format ({lon}, {lat}) — read as lon/lat",
    "{line}째 줄 — 칸 수가 머리줄과 다르다 ({n}/{m})": "Line {line} — cell count differs from the header ({n}/{m})",
    "{line}째 줄 — {why}": "Line {line} — {why}",
    "좌표를 읽지 못했다 ({lon}, {lat})": "Could not read coordinates ({lon}, {lat})",
    "위경도 범위 밖이다 ({lon}, {lat}) — 십진도 WGS84 만 받는다":
        "Out of range ({lon}, {lat}) — only WGS84 decimal degrees are accepted",
    "WKT 를 읽지 못했다 — POINT·LINESTRING·POLYGON 과 그 MULTI 만 받는다":
        "Could not read WKT — only POINT, LINESTRING, POLYGON and their MULTI forms",
    "WKT 좌표를 읽지 못했다": "Could not read WKT coordinates",
    "WKT 괄호가 맞지 않는다": "Unbalanced WKT parentheses",
    "JSON 을 읽지 못했다 — {why}": "Could not read JSON — {why}",
    "GeoJSON FeatureCollection 이 아니다": "Not a GeoJSON FeatureCollection",
    "gsm 머리가 없다 — 이름·열 설명 없이 읽었다": "No gsm header — read without a name or column descriptions",
    "{n}째 피처 — {why}": "Feature {n} — {why}",
    "{type} 은 받지 않는다 — 점·선·면만": "{type} is not accepted — points, lines and polygons only",
    "좌표를 읽지 못했다": "Could not read coordinates",
    "그릴 좌표가 하나도 없다": "Nothing has coordinates to draw",
    "{kinds} — 모양마다 레이어 {n}개로 나눈다": "{kinds} — split into {n} layers, one per geometry",
    "'{name}' 을 레이어 {n}개로 저장했다. 지도의 개인 레이어에 뜬다.": "Saved '{name}' as {n} layers. They appear under personal layers on the map.",
    "선": "Line",
    "양식 이름이 다르다 ({name})": "Different format name ({name})",
    "더 새 판의 양식이다 (v{v}) — 아는 것만 읽었다": "A newer format version (v{v}) — read what is known",
    "이 브라우저는 저장소(IndexedDB)를 쓰지 못한다": "This browser cannot use storage (IndexedDB)",
    "저장하지 못했다 — 저장소가 찼을 수 있다": "Could not save — storage may be full",
    "이름 없는 레이어": "Untitled layer",
}


# ── 속성 이름 ────────────────────────────────────────────────────────
#
# 상류가 팝업에 주는 열 이름. 2026-09-27 에 레이어 61 개를 두세 곳씩 눌러
# 모았다. 영문 열(`symnum`·`GRAY_INDEX` …)은 그대로 둔다.

PROP_EN = {
    "특성": "Characteristics",                 # 대만 암체 강도 등급의 지층 특성 (wetherilli 370)
    "등급의 차례": "Class order",
    # 호주 확인 자원·수리지질도 (wetherilli 325)
    "자원량 칸": "Resource size class",
    "대수층": "Aquifer",
    "분포": "Distribution",
    "생산성": "Productivity",
    # 노르웨이 광물 (wetherilli 326)
    "자원 중요도": "Resource importance",
    "등록 갈래": "Registration type",
    "광석": "Ore",
    # GSJ 1:200만·중력 (wetherilli 316)
    "설명 (원문)": "Description (original)",
    "부게 이상 (mGal, 둘레 등치선)": "Bouguer anomaly (mGal, nearby contours)",
    # 대만 지질운 열린자료 (wetherilli 305)
    "선상지 넓이": "Fan area",
    "보호 대상": "Protected targets",
    "하도 폭": "Channel width",
    "하도 경사": "Channel slope",
    "하도 식생": "Channel vegetation",
    "정비": "Works",
    "정비 상태": "Works condition",
    "교통 영향": "Affects traffic",
    "현장 확인": "Site check",
    "활동": "Activity",
    "시군": "County",
    "판독일": "Interpreted on",
    "넓이 (m²)": "Area (m²)",
    "관측소": "Station",
    "기관": "Agency",
    "강도 등급": "Strength class",
    # 세계 빙하 (wetherilli 289)
    "넓이 (km²)": "Area (km²)",
    "가운데 높이 (m)": "Median elevation (m)",
    "끝": "Terminus",
    "서지": "Surge",
    "윤곽의 날": "Outline date",
    "RGI": "RGI",
    # 충돌구·LIP (wetherilli 283)
    "생긴 때 (Ma)": "Age (Ma)", "그때의 지구": "Past positions", "지름 (km)": "Diameter (km)",
    # 세계 활성단층 (wetherilli 279)
    "미끄럼 (원문)": "Slip type (source)", "레이크 (°)": "Rake (°)", "미끄럼 속도 (mm/yr)": "Slip rate (mm/yr)",
    "지진 발생 깊이 (km)": "Seismogenic depth (km)", "원 목록": "Source catalogue",
    # 세계 광상 (wetherilli 276)
    "딸린 광종": "Secondary commodities", "생산 규모": "Production size", "광상 유형": "Deposit type",
    "광석 광물": "Ore minerals", "총 광량 (Mt)": "Tonnage (Mt)", "품위": "Grade",
    # 지각 응력 (wetherilli 273)
    "응력 체제": "Stress regime", "최대 수평 응력 방향": "S_Hmax azimuth", "일시": "Date",
    # 세계 지질구 (wetherilli 272)
    "묶음": "Group", "마지막 조산 운동": "Last orogeny", "대륙": "Continent", "지각": "Crust",
    # 지열류 (wetherilli 267)
    "지열류 (mW/m²)": "Heat flow (mW/m²)", "환경": "Setting", "품질": "Quality",
    "오차 (mW/m²)": "Uncertainty (mW/m²)", "잰 법": "Method", "자리": "Site",
    "시대별 암석": "Rock by age", "변성 정도": "Metamorphic grade", "지질구": "Geological province", "주기": "Cycle", "영역": "Domain",
    "편집": "Compiled by", "층서": "Stratigraphy", "물질": "Material",
    "심성암": "Plutonic intrusion", "원 설명": "Original description", "조산 주기": "Orogenic cycle",
    "초층군": "Supergroup", "지구조 대구역": "Tectonic megazone", "편집 연도": "Compilation year", "빙하 층서": "Glacial stratigraphy", "층서 명명집": "Stratigraphic nomenclator",
    "부층": "Member", "단면": "Profile", "층 설명": "Unit notes",
    "고지자기": "Magnetic polarity",                     # 아이슬란드 1:10만의 `segultimatal`(BRUN 따위, wetherilli 216)
    "광종 기호": "Commodity symbol", "지층 기호": "Unit symbol", "대표 암상": "Representative lithology",
    "조사연도": "Survey year",
    "암석 분류": "Rock classification",   # 남미 1:500만 (wetherilli 188)
    "경제적 쓰임": "Economic interest",    # 에콰도르 IIGE (wetherilli 198)
    "주": "State", "단위 설명": "Unit description",   # 미국 USGS (wetherilli 205)
    "위계": "Rank",                        # 브라질 SGB — 층군·층·암상 따위 (wetherilli 191)
    # 지역 탭의 지구 자료 점 — 링크 열 (wetherilli 185)
    "PBDB 산지 페이지": "PBDB collection page", "GVP 화산 페이지": "GVP volcano page",
    "USGS 지진 페이지": "USGS event page", "Neotoma 산지 페이지": "Neotoma site page",
    # 점묶음 CSV 의 열 (wetherilli 190)
    "위도": "Latitude", "경도": "Longitude",
    "지질 단위(GeoMAP)": "Geological unit (GeoMAP)", "지질기호(GeoMAP)": "Map symbol (GeoMAP)",
    "연대 Ma(GeoMAP)": "Age Ma (GeoMAP)", "지각 두께 km(CRUST 2.0)": "Crustal thickness km (CRUST 2.0)",
    "가까운 화석 산지(PBDB)": "Nearest fossil collection (PBDB)", "산지 번호(PBDB)": "Collection no. (PBDB)",
    "산지의 시대(PBDB)": "Collection age (PBDB)", "산지까지 km(PBDB)": "Distance to collection km (PBDB)",
    "지질 단위(원도)": "Geological unit (original map)", "단위 이름(원도)": "Unit name (original map)",
    "시대(원도)": "Age (original map)",
    "지질 단위(화성 지질도)": "Geological unit (Mars map)", "단위 이름(화성 지질도)": "Unit name (Mars map)",
    "시대(화성 지질도)": "Age (Mars map)", "화성 지질도": "Mars geologic map",
    "지질 단위(수성 지질도)": "Geological unit (Mercury map)", "단위 무리(수성 지질도)": "Unit group (Mercury map)",
    "도폭(수성 지질도)": "Quadrangle (Mercury map)",
    # 대만 — 지질운의 온천·시추·순향사면 (gsmma.py, wetherilli 141)
    "온천명": "Hot spring", "수질": "Water type", "수온 (°C)": "Water temperature (°C)", "pH": "pH",
    "조사 사업": "Survey project", "공번": "Borehole no.", "심도 (m)": "Depth (m)",
    "사면 방향": "Slope direction", "시·현": "City / county",
    # 달 — 누른 자리의 값 (wetherilli 103)
    "감람석": "Olivine",
    "단사휘석": "Clinopyroxene",
    "사방휘석": "Orthopyroxene",
    "사장석": "Plagioclase",
    "토륨": "Thorium",
    # 다누리 KGRS·북극 판 (wetherilli 150)
    "칼륨 상대값 (단위 미확인)": "Potassium, relative (unit unconfirmed)",
    "우라늄 상대값 (단위 미확인)": "Uranium, relative (unit unconfirmed)",
    "토륨 상대값 (단위 미확인)": "Thorium, relative (unit unconfirmed)",
    "열중성자 상대값 (단위 미확인)": "Thermal neutrons, relative (unit unconfirmed)",
    "FeO (북극)": "FeO (north pole)",
    "얼음이 버틸 깊이 — 오늘의 자전축": "Ice stability depth — today's spin axis",
    "얼음이 버틸 깊이 — 옛 자전축": "Ice stability depth — paleo spin axis",
    "높이 — 화성 기준면(아레오이드)": "Elevation — above the Mars areoid",   # 화성 표고 판의 값 (wetherilli 192)
    "높이 — 수성 기준구 2439.4 km": "Elevation — above the 2,439.4 km Mercury sphere",   # 수성 (wetherilli 194)
    "티타늄": "Titanium",
    "지각 두께": "Crustal thickness",
    # 화석 산지 (wetherilli 098)
    "산지": "Collection",
    "퇴적 환경": "Environment",
    "화석 수": "Occurrences",
    "첫 문헌": "Primary reference",
    # 홀로세 화산 (wetherilli 134)
    "화산": "Volcano",
    "화산 종류": "Volcano type",
    "마지막 분화": "Last eruption",
    "표고 (m)": "Elevation (m)",
    "광산 이름": "Mine name", "상태": "Status", "조사 방법": "Observation method",
    "같은 칸에 모인 수": "Points merged in this cell", "측점": "Station", "조사": "Survey", "프리에어 이상 (mGal)": "Free-air anomaly (mGal)", "부게 이상 (mGal)": "Bouguer anomaly (mGal)",
    "지구조 환경": "Tectonic setting",
    "주 암석": "Major rock type",
    "근거": "Evidence",
    "지질 개요": "Geological summary",
    # 지진 (wetherilli 138)
    "규모": "Magnitude",
    "일시 (UTC)": "Time (UTC)",
    "깊이 (km)": "Depth (km)",
    "곳": "Place",
    # 제4기 고생태 산지 (wetherilli 139)
    "연구자": "Investigators",
    "지질시대": "Geologic age",
    "자력 이상 (nT)": "Magnetic anomaly (nT)",
    "변형대": "Deformation zone",
    "장소": "Locality",
    "지구조 요소": "Tectonic element",
    "칼륨 K (%)": "Potassium K (%)",
    "토륨 eTh (ppm)": "Thorium eTh (ppm)",
    "우라늄 eU (ppm)": "Uranium eU (ppm)",
    "시대": "Age",
    "도폭": "Map sheet",
    "도폭명": "Sheet name",
    "도첩명": "Map series",
    "도곽": "Map frame",
    "지층명": "Formation",
    "지층": "Formation",
    "지질기호": "Symbol",
    "기호": "Symbol",
    "대표암석": "Main rocks",
    "대표암상": "Main lithology",
    "암석명": "Rock name",
    "정보": "Info",
    "설명": "Description",
    "영문지층명": "Formation (English)",
    "영문지질시대": "Geologic age (English)",
    "영문도곽": "Map frame (English)",
    "제작연도": "Year made",
    "발행년도": "Year published",
    "연도": "Year",
    "조사자": "Surveyed by",
    "작성자": "Compiled by",
    "저자": "Author",
    "축척": "Scale",
    "표고(DEM)": "Elevation (DEM, m)",
    "표고 출처": "Elevation source",
    "해저·빙저(IBCSO)": "Bed (IBCSO, m)",
    "도로명(VWorld)": "Road address (VWorld)",
    "지번(VWorld)": "Parcel address (VWorld)",
    "보호구역(VWorld)": "Protected area (VWorld)",
    "지목(VWorld)": "Land category (VWorld)",
    "소유구분(VWorld)": "Ownership (VWorld)",
    "지정 구분": "Designation",
    "읍면동(VWorld)": "District (VWorld)",
    "가까운 단층(VWorld, m)": "Nearest fault (VWorld, m)",
    "둘레 지명(VWorld)": "Nearby place name (VWorld)",
    "얼음 두께(IBCSO)": "Ice thickness (IBCSO, m)",
    "자료 출처": "Data source",
    "해저·빙저 (m)": "Bed (m)",
    # KPDC 지도 서버 (073)
    "그린 근거": "Source of the line",
    "고친 날": "Revised",
    # KPDC 기본도 (wetherilli 095)
    "표면": "Surface",
    "확실성": "Certainty",
    "HSM 번호": "HSM no.",
    "제안국": "Proposed by",
    "관리국": "Managed by",
    "수심 (m)": "Depth (m)",
    "바닥": "Bed type",
    "도폭 (IMW)": "IMW sheet",
    "출처 날짜": "Source date",
    "밑": "Subsurface",
    # 스발바르 도폭 경계 (npolar.POINTS, P01 6 단계)
    "도폭 번호": "Sheet number",
    "발행": "Printed",
    "야외 조사": "Fieldwork",
    "수치화": "Digitised",
    "출판물": "Publication",
    "지도 보관소": "Map archive",
    "출처": "Source",
    "링크": "Link",
    "키워드": "Keywords",
    "위치": "Location",
    "지질노두명": "Outcrop",
    "지질노두명_영문": "Outcrop (English)",
    "지질분포": "Distribution",
    "지체구조구": "Tectonic province",
    "지체구조운동": "Tectonic event",
    "심도": "Depth",
    "유기탄소량": "Organic carbon",
    "퇴적물명": "Sediment",
    "퇴적물시기": "Sediment age",
    "표층퇴적물": "Surface sediment",
    "평균입도1": "Mean grain size 1",
    "평균입도2": "Mean grain size 2",
    "평균입도3": "Mean grain size 3",
    "등층후유형": "Isopach type",
    "해안선유형": "Coastline type",
    "물탐측선명": "Survey line",
    "이름표": "Label",
    # GEUS 속성 (geus.FRIENDLY)
    "지질 단위": "Geological unit",
    "최소 연대 (Ma)": "Minimum age (Ma)",
    "최대 연대 (Ma)": "Maximum age (Ma)",
    # VWorld 속성 (vworld.FRIENDLY) — "지질 참고" 레이어군, devlog 020
    "구분": "Class",
    "길이 (m)": "Length (m)",
    "수문지질단위": "Hydrogeologic unit",
    "지하수위 표고 (m)": "Groundwater level elevation (m)",
    "전기전도도 (µS/cm)": "Electrical conductivity (µS/cm)",
    "지하수 등수심 (m)": "Groundwater depth (m)",
    "시도": "Province",
    "시군구": "City / county",
    "읍면동": "Town / township",
    "리": "Village (ri)",
    "행정구역": "Administrative area",
    "지구": "Zone",
    "산": "Mountain",
    "구간": "Section",
    "난이도": "Difficulty",
    "지명": "Place name",
    "하천명": "River",
    "하천 등급": "River class",
    # VWorld 보호구역·토양·공역 (wetherilli 084)
    "세부": "Detail",
    "지정 연도": "Year designated",
    "공원": "Park",
    "보호구역": "Protected area",
    "고시": "Official notice",
    "고시일": "Notice date",
    "근거 법": "Legal basis",
    "관리 기관": "Managing agency",
    "면적 (km²)": "Area (km²)",
    "공역": "Airspace",
    "상한 고도": "Upper limit",
    "하한 고도": "Lower limit",
    "대권역": "Major basin",
    "중권역": "Mid-size basin",
    "표준유역": "Standard sub-basin",
    "유효토심 (cm)": "Effective soil depth (cm)",
    "자갈 함량 (%)": "Gravel content (%)",
    "심토 토성": "Subsoil texture",
    "배수 등급": "Drainage class",
    "산림토양": "Forest soil",
    "토양형 기호": "Soil type symbol",
    # 그린란드 정부 포털의 점 레이어 (grportal.LAYERS 의 label)
    # 광물 잠재 구역·불안정 사면·매스무브먼트·다이아몬드 산출지 (wetherilli 089)
    "구역": "Tract",
    "평가 광종": "Assessed commodity",
    "평가 연도": "Assessment year",
    "광상 모델": "Deposit model",
    "알려진 광상 수": "Known deposits",
    "미발견 광상 수 (추정)": "Undiscovered deposits (estimate)",
    "미발견 광상 수 (90%)": "Undiscovered deposits (90%)",
    "미발견 광상 수 (50%)": "Undiscovered deposits (50%)",
    "미발견 광상 수 (10%)": "Undiscovered deposits (10%)",
    "미발견 광상 수 (5%)": "Undiscovered deposits (5%)",
    "미발견 광상 수 (1%)": "Undiscovered deposits (1%)",
    "지질 해설": "Geology notes",
    "구리": "Copper",
    "금": "Gold",
    "니켈": "Nickel",
    "희토류": "Rare earth elements",
    "텅스텐": "Tungsten",
    "아연": "Zinc",
    "불안정 사면": "Unstable slope",
    "매스무브먼트": "Mass movement",
    "매스무브먼트 — 쓰나미를 일으켰다": "Mass movement — generated a tsunami",
    "가까운 마을": "Nearest settlement",
    "마을까지 (km)": "Distance to settlement (km)",
    "최소 부피 (m³)": "Minimum volume (m³)",
    "부피 (m³)": "Volume (m³)",
    "면적 (m²)": "Area (m²)",
    "높이 (m)": "Height (m)",
    "낙차 (m)": "Drop height (m)",
    "도달 거리 (m)": "Runout (m)",
    "원자료": "Source data",
    "관측일": "Date observed",
    "원자료 (영상)": "Source image",
    "전면 길이 (km)": "Front length (km)",
    "일어난 때": "When",
    "쓰나미 (1 = 일으켰다)": "Tsunami (1 = generated)",
    "킴벌라이트질": "Kimberlitic",
    "카보나타이트": "Carbonatite",
    "램프로아이트": "Lamproite",
    "램프로파이어": "Lamprophyre",
    "암석군": "Rock group",
    "산상": "Morphology",
    "주향 (°)": "Strike (°)",
    "경사 방향": "Dip direction",
    "경사": "Dip",
    "주향": "Strike",
    "원문 사분면": "Original quadrant",
    "알림": "Note",
    "너비 (m)": "Width (m)",
    "다이아몬드 품위": "Diamond grade",
    "출처 갈래": "Source type",
    "보고한 곳": "Reported by",
    # 다이아몬드 탐사 자료 — 시추공·지시광물·석류석·탐사 구역 (wetherilli 157)
    "시추공": "Drill hole",
    "탐사지": "Prospect",
    "이상대": "Anomaly",
    "이상대 갈래": "Anomaly type",
    "킴벌라이트": "Kimberlite",
    "킴벌라이트 두께 (m)": "Kimberlite thickness (m)",
    "시추 길이 (m)": "End of hole (m)",
    "방위 (°)": "Azimuth (°)",
    "주변 지질": "Host geology",
    "시추한 곳": "Operator",
    "보고 연도": "Report year",
    "나눈 시료": "Sub-sample",
    "지시광물 (낟알/kg)": "Indicator minerals (grains/kg)",
    "다이아몬드 (개/kg)": "Diamonds (stones/kg)",
    "G10D 낟알": "G10D grains",
    "G10 낟알": "G10 grains",
    "G9 낟알": "G9 grains",
    "G11 낟알": "G11 grains",
    "G12 낟알": "G12 grains",
    "G1 낟알": "G1 grains",
    "G3 낟알": "G3 grains",
    "G4 낟알": "G4 grains",
    "G5 낟알": "G5 grains",
    "킴벌라이트를 만났다": "Kimberlite intersected",
    "만나지 못했다": "Not intersected",
    "보고 없음": "Not reported",
    "100 낟알/kg 넘게": "Over 100 grains/kg",
    "10–100 낟알/kg": "10–100 grains/kg",
    "1–10 낟알/kg": "1–10 grains/kg",
    "1 낟알/kg 밑": "Under 1 grain/kg",
    "1 개/kg 넘게": "Over 1 stone/kg",
    "0.25–1 개/kg": "0.25–1 stones/kg",
    "0.05–0.25 개/kg": "0.05–0.25 stones/kg",
    "0.05 개/kg 밑": "Under 0.05 stones/kg",
    "G10D 가 있다 (다이아몬드 안정역)": "G10D present (diamond stability field)",
    "G10 이 있다": "G10 present",
    "G9 만 (러졸라이트질)": "G9 only (lherzolitic)",
    "그 밖의 석류석": "Other garnets",
    "탐사된 곳": "Explored",
    "탐사되지 않은 곳 (가능성 있음)": "Unexplored (with potential)",
    # 다이아몬드 탐사 자료의 둘째 몫 (wetherilli 178) — 갈래 이름(CGP·KIM …)은 DED 의 것 그대로
    "CPX_CGP 가 가장 많다": "Mostly CPX_CGP",
    "CPX_CPP 가 가장 많다": "Mostly CPX_CPP",
    "ILM_KIM 이 가장 많다": "Mostly ILM_KIM",
    "ILM_INTER 가 가장 많다": "Mostly ILM_INTER",
    "SP_CID 가 가장 많다": "Mostly SP_CID",
    "SP_GT_PER 가 가장 많다": "Mostly SP_GT_PER",
    "가르지 못한 첨정석이 가장 많다": "Mostly unclassified spinel",
    "OPX_OGM 이 가장 많다": "Mostly OPX_OGM",
    "OPX_OGP 가 가장 많다": "Mostly OPX_OGP",
    "OPX_ODH 가 가장 많다": "Mostly OPX_ODH",
    "OPX_ODL 이 가장 많다": "Mostly OPX_ODL",
    "갈래 낟알 없음": "No classified grains",
    "CPX_CGP 낟알": "CPX_CGP grains",
    "CPX_CPP 낟알": "CPX_CPP grains",
    "ILM_KIM 낟알": "ILM_KIM grains",
    "ILM_INTER 낟알": "ILM_INTER grains",
    "SP_CID 낟알": "SP_CID grains",
    "SP_GT_PER 낟알": "SP_GT_PER grains",
    "가르지 못한 낟알": "Unclassified grains",
    "OPX_OGM 낟알": "OPX_OGM grains",
    "OPX_OGP 낟알": "OPX_OGP grains",
    "OPX_ODH 낟알": "OPX_ODH grains",
    "OPX_ODL 낟알": "OPX_ODL grains",
    "100 개 넘게": "Over 100",
    "10–99 개": "10–99",
    "2–9 개": "2–9",
    "1 개": "1",
    "큰 다이아몬드 (개)": "Macrodiamonds",
    "작은 다이아몬드 (개)": "Microdiamonds",
    "잰 것": "Dated material",
    "문헌 저자": "Reference authors",
    "문헌 연도": "Reference year",
    "면적 (ha)": "Area (ha)",
    "산출지 면 (관입체)": "Occurrence bodies",
    "아일리카이트": "Aillikite",
    "킴벌라이트 (추정)": "Kimberlite (inferred)",
    "카보나타이트 (추정)": "Carbonatite (inferred)",
    "램프로파이어 (추정)": "Lamprophyre (inferred)",
    "그 밖 (추정)": "Other (inferred)",
    # 그린란드 지명 (wetherilli 096)
    "옛 철자": "Old spelling",
    "덴마크어 이름": "Danish name",
    "지자체": "Municipality",
    # PGC 경사 (wetherilli 099) — "경사 (°)" 는 지층의 경사(dip)다
    "사면 경사 (°)": "Slope (°)",
    "지질": "Geology",
    "시료 번호": "Sample no.",
    "연대 (Ma)": "Age (Ma)",
    "오차 (Ma)": "Uncertainty (Ma)",
    "해석": "Interpretation",
    "광물": "Mineral",
    "측정법": "Technique",
    # 달의 누른 자리 값 — 남은 판 (wetherilli 236)
    "광학 성숙도 지수 (OMAT)": "Optical maturity index (OMAT)",
    "사장석 알갱이 크기": "Plagioclase grain size",
    "미세 금속철(SMFe) 상대값 (단위 미확인)": "Submicroscopic iron (SMFe), relative (unit unconfirmed)",
    "지각–맨틀 경계 (기준 반지름 대비 높이)": "Crust–mantle interface (height relative to reference radius)",
    "지각 알갱이 밀도": "Crustal grain density",
    "표면 기복 (기준 반지름 대비)": "Surface relief (relative to reference radius)",
    "크리스티안센 특성 파장": "Christiansen feature position",
    "가장 높은 온도": "Maximum temperature",
    "가장 낮은 온도": "Minimum temperature",
    "자정의 온도": "Midnight temperature",
    "정오의 온도": "Noon temperature",
    "가장 높은 온도의 이상": "Maximum temperature anomaly",
    "가장 낮은 온도의 이상": "Minimum temperature anomaly",
    "온도 이상의 차": "Temperature anomaly difference",
    "온도 이상의 비": "Temperature anomaly ratio",
    "원편광 비 (CPR)": "Circular polarization ratio (CPR)",
    "높이 — 달 기준구 1737.4 km": "Height — lunar sphere 1737.4 km",
    "경사도": "Slope",
    "부게 중력 교란": "Bouguer gravity disturbance",
    "프리에어 중력 이상": "Free-air gravity anomaly",
    "중력 교란": "Gravity disturbance",
    "지오이드 높이": "Geoid height",
    "중력 이상 오차": "Gravity anomaly error",
    "중력 차수 강도": "Gravity degree strength",
    # 호주의 주 판 (wetherilli 225)
    "지질 이력": "Geologic history",
    # 아르헨티나 SEGEMAR 의 제4기 변형·화산 위험도·구조선 (wetherilli 220)
    "구조 갈래": "Structure type", "세부 갈래": "Subtype", "활동성": "Activity", "마지막 움직임": "Last movement",
    "움직임 속도": "Slip rate", "재발 간격 (년)": "Recurrence (years)", "위험도": "Hazard level", "위험 지수": "Hazard index",
    "평가일": "Assessed", "화석": "Fossils",
    # 5만 선구조의 팝업 (wetherilli 223)
    "침강 방향": "Plunge direction", "침강각": "Plunge", "방향 (사분면)": "Trend (quadrant)", "침강 방향 (사분면)": "Plunge direction (quadrant)",
    # 브라질 SGB 의 노두·연대측정·화석 산지 (wetherilli 215)
    "야외 번호": "Field number", "과제": "Project", "분석 재료": "Material analysed", "자료 공개": "Access level",
    "분류": "Systematics", "분류군": "Taxon", "재료": "Material", "암층서 단위": "Lithostratigraphic unit",
    "층서 시대": "Chronostratigraphy", "산출 양상": "Mode of occurrence",
    "계산법": "Approach",
    "암상": "Lithology",
    # 남아공 CGS·나미비아 GSN (wetherilli 209)
    "층서 이름": "Stratigraphic unit",
    "상위 층서": "Parent unit",
    "누층군": "Sequence",
    "아층군": "Subgroup",
    "연대": "Age",                      # 아프리카 CGMW 의 `AGE`("23 - 2.6 Ma") (wetherilli 207)
    "제공 기관": "Provider",
    "암석 갈래": "Rock type",
    "지괴": "Terrane",
    "단위": "Unit",
    "원도": "Source map",
    "무리": "Group",
    "크레이터 등급": "Crater class",
    "지표 특징": "Surface feature",
    "문헌": "Reference",
    "GEUS 상세": "GEUS details",
    "이름": "Name",
    # 얀마옌 지질도 (janmayen.LABELS)
    "노르웨이어 이름": "Norwegian name",
    "층서 계통": "Lithostratigraphic hierarchy",
    "암층 코드": "Unit code (geo_code)",
    # 노르웨이 극지연구소 — 스발바르·드로닝모드랜드 (npolar.FRIENDLY·POINTS, devlog 021)
    "주 암상": "Main lithology",
    "시대 하한": "Age (base)",
    "시대 상한": "Age (top)",
    "상위 단위": "Superior unit",
    "갈래": "Type",
    "연대 근거": "Dating method",
    "정확도": "Accuracy",
    "범례 번호": "Legend code",
    "층서명": "Stratigraphic unit",
    "모식지": "Type section / area",
    "모식지 갈래": "Nature of section",
    "UTM 위치": "UTM position",
    "번호": "ID",
    "옛 이름": "Former name",
    "비고": "Remarks",
    "층서 사전": "Stratigraphic lexicon",
    "채취 연도": "Year collected",
    "탐사": "Expedition",
    "위치 정확도": "Position accuracy",
    "보관함": "Cabinet",
    "시료 보관소": "Sample archive",
    "사진": "Photo",
    "연대 갈래": "Age type",
    "암석": "Rock",
    "문헌 번호": "Reference no.",
    # 일본 — GSJ 심리스 지질도 (gsj.friendly, devlog 024)
    "암상 (원문)": "Lithology (original)",
    "위치 근거": "Location basis",
    "기재": "Description",
    "지점": "Locality",
    "시료": "Samples",
    "광종": "Commodity",
    "광종 무리": "Commodity group",
    "경제성": "Economic status",
    "보고서": "Report",
    "시료 갈래": "Sample type",
    "해": "Year",
    "분석 번호": "Analysis no.",
    "채취·보고": "Collected / reported by",
    "시료 기재": "Sample description",
    "채취 지점": "Locality",
    "채취자": "Collector",
    "채취일": "Collected",
    # 중국 — USGS geo3al (geo3al.LABELS)
    "암종": "Rock type",
    "원도 기호": "Source map code",
    # 남극 GeoMAP 속성 (geomap.PROPS)
    "간추린 지질": "Simplified geology",
    "노두 갈래": "Outcrop type",
    "층서 단위": "Stratigraphic rank",
    "지역": "Region",
    "신뢰도": "Confidence",
    "관찰 방법": "Observation method",
    "위치 정확도 (m)": "Positional accuracy (m)",
    "출처 문헌": "Reference",
    "단층 갈래": "Fault type",
    "노출": "Exposure",
    "위치 정확성": "Location accuracy",
    "운동 갈래": "Movement type",
    "경사 (°)": "Dip (°)",
    "경사 방향 (°)": "Dip direction (°)",
    "자료 품질 (1–5)": "Data quality (1–5)",
    "노두": "Outcrop",
    "자료": "Dataset",
    # 암맥 기록 — phyloserver (devlog 026)
    "주향 (끝점에서 잰 값)": "Strike (from endpoints)",
    "메모": "Memo",
    "기록 번호": "Record ID",
    "phyloserver 기록": "phyloserver record",
    "암맥 수": "Dikes",
    "평균 주향": "Mean strike",
    # 극지연구소 (053–056)
    "제목": "Title",
    "자료 번호": "Entry ID",
    "과학 키워드": "Science keywords",
    "연구 기간": "Research period",
    "고기후 시기": "Paleo age",
    "장비": "Platform / instrument",
    "KPDC 자료 페이지": "KPDC entry",
    "DOI": "DOI",
    "운석": "Meteorite",
    "찾은 날": "Found",
    "운석 기록 (KoreaMet)": "Meteorite record (KoreaMet)",
    "기지": "Station",
    "나라": "Country",
    "운영": "Operation",
    "처음 연 해": "Opened",
    "월동 인원": "Winter population",
    # 아라온호 (koprifossillab 006)
    "배": "Vessel",
    "시각 (UTC)": "Time (UTC)",
    "속력 (kn)": "Speed (kn)",
    "침로 (°)": "Course (°)",
    "선수방위 (°)": "Heading (°)",
    "기온 (°C)": "Air temperature (°C)",
    "습도 (%)": "Humidity (%)",
    "첫 기록": "First fix",
    "마지막 기록": "Latest fix",
    "자리 수": "Fixes",
    "날짜 (하루 창, UTC)": "Date (24 h window, UTC)",
    "받은 때": "Harvested",
    "여름 최대 인원": "Peak population",
    "고도": "Altitude",
    "다른 이름": "Other names",
    # 화성 크레이터 (067)
    "지름": "Diameter",
    "깊이": "Depth",
    "안쪽 형태": "Interior morphology",
    "분출물 형태": "Ejecta morphology",
    "보존 상태": "Preservation state",
    "가운데": "Centre",
    "지은이": "Authors",
    "지형구": "Province",
    # VWorld 수질·지하수 측정망 (wetherilli 156)
    "측정소": "Station",
    "수계": "River system",
    "단위유역": "Unit watershed",
    "환경 기준": "Environmental standard",
    "용도": "Use",
    "측정 기관": "Monitoring agency",
    "설치 연도": "Year installed",
    "폐쇄 연도": "Year closed",
    "측정소 코드": "Station code",
    "주소": "Address",
    "음용": "Drinking",
    "관정 번호": "Well number",
    # 독일 BGR·스페인 IGME (wetherilli 147)
    "대": "Era",
    "성인": "Genesis",
    "밀도 구간": "Density class",
    # 민감구역·지구물리 격자의 값 (wetherilli 336)
    "구역 번호": "Area code", "향·진·구": "Township", "공고일": "Announced", "공고 문호": "Notice no.",
    "완전 부게 중력 이상 (µm/s²)": "Complete Bouguer anomaly (µm/s²)", "총자력 이상 (nT)": "Total magnetic intensity (nT)",
    "칼륨 (%)": "Potassium (%)", "토륨 (ppm)": "Thorium (ppm)", "우라늄 (ppm)": "Uranium (ppm)",
    "함량 (%)": "Content (%)", "함량 (mg/kg)": "Content (mg/kg)", "대수층": "Aquifer", "흐름": "Flow", "요약": "Summary", "분석 원소": "Analytes", "사업": "Project",
    "핵심 광물": "Critical minerals", "과거 생산": "Past producer", "자원량 공개": "Public resource", "광업 지구": "Mining district", "권역": "Region",
    "이상": "Anomaly", "함량": "Concentration", "광상": "Deposit", "리튬 (ppm)": "Lithium (ppm)", "채굴": "Mined",
    "회사": "Company",
    "생산": "Production", "발견": "Discovery", "발견 연도": "Year discovered", "산물": "Product",
    "생산량": "Production", "잠재량": "Potential", "채굴 형태": "Working type", "쓰임": "Uses", "지질시대 (원문)": "Age (original)",
    "원료": "Raw material", "원료 갈래": "Raw material group", "딸린 원료": "Secondary raw material", "중력 이상 (mGal)": "Gravity anomaly (mGal)",
    "총 감마선": "Total gamma",
    "광종 (태국어)": "Commodity (Thai)", "군": "District", "탐사 단계": "Exploration status", "광종 갈래": "Commodity group", "조사 단계": "Survey stage",
    "광업 지역": "Mining area",
    "딸린 광종": "Other commodities", "채굴 기간": "Years mined", "총 광량 (Mt)": "Total tonnage (Mt)", "광석 광물": "Ore minerals",
    "광화 시기": "Age of mineralisation", "광상 유형": "Deposit type", "생산 끝": "Production ended",
    "시대 기호": "Age code", "자원량": "Resources",
    "영국 격자": "British National Grid",
    # 남미 광물 자원 (wetherilli 265)
    "중요도": "Importance", "광산": "Mine status", "모암": "Host rock", "광체 형태": "Ore body form", "광화 지역": "Mineral province",
    "광화 양식": "Mineralization style", "광물 조합": "Mineral association", "모암 단위": "Host unit", "광상 규모": "Deposit size",
    "위치 정확도": "Location accuracy", "모든 광종": "All commodities",
    # 미국 광물·연대 (wetherilli 247)
    "개발 단계": "Development status", "다른 광종": "Other commodities", "지형도": "Topographic map", "상세": "Details",
    # 캐나다 핵심 광물 (wetherilli 250)
    "운영사": "Operator", "누리집": "Website",
    # 하와이 (wetherilli 238)
    "조성": "Composition", "섬": "Island", "화산 성장 단계": "Volcano stage",
    "서열": "Rank",
    "변성암": "Metamorphic rock",
    "화성암": "Igneous rock",
    "해양 지질": "Marine geology",
    "경계·구조선": "Boundary or structure line",
    # 멕시코 광상 (wetherilli 219)
    "광화 유형": "Mineralization type", "구조": "Structure", "변질": "Alteration", "광상 형태": "Deposit form",
    "광산 지구": "Mining district",
    # 멕시코 지화학 (wetherilli 233)
    "원소": "Element", "함량 (ppm)": "Content (ppm)",
    # 영국 BGS (wetherilli 143)
    "세": "Epoch",
    "가장 오랜 시기": "Oldest age",
    "가장 젊은 시기": "Youngest age",
    "선 구조": "Linear feature",
    "어휘집": "BGS Lexicon",
    # 노르웨이 NGU·핀란드 GTK 기반암 (wetherilli 140)
    "암석 단위": "Rock unit",
    "암석 단위 (영문)": "Rock unit (English)",
    "딸린 암석": "Subordinate rock",
    "딸린 암석 2": "Subordinate rock 2",
    "형성 연대": "Age of formation",
    "변성상": "Metamorphic facies",
    "변성 연대": "Age of metamorphism",
    "지구조 구분": "Tectonic division",
    "지구조 단위": "Tectonic unit",
    # 스웨덴 SGU (wetherilli 213)
    "암층서 단위": "Lithostratigraphic unit",
    "하위 단위": "Subunit",
    "광물 조성": "Mineral composition",
    "생성": "Genesis",
    "원 이름": "Original name",
    "층": "Formation",
    "층군": "Group",
    "초암석군": "Supersuite",
    "암체": "Lithodeme",
    "지구조 구역": "Tectonic province",
    "생성 환경": "Environment",
    # EMODnet 해저 지질 (wetherilli 135)
    "해저 퇴적물 (Folk 7)": "Seabed substrate (Folk 7)",
    "해저 퇴적물 (Folk 16)": "Seabed substrate (Folk 16)",
    "원 분류": "Original classification",
    "단층 종류": "Fault type",
    "단층 이름": "Fault name", "단층 분류": "Fault category", "확인 여부": "Observed or inferred",
    "원 범례": "Original legend",
    "자료 보유 기관": "Data holder",
    "해저 사태": "Submarine landslides",
    "해저 화산": "Submarine volcanoes",
    "제4기 구조운동": "Quaternary tectonics",
    "지진해일": "Tsunamis",
    "해저 유체 분출": "Submarine fluid emissions",
    "참고 문헌": "Reference",
}


# ── 지질시대 ────────────────────────────────────────────────────────
#
# 상류의 값은 낱말을 겹쳐 쓴다 — `현생누대 고생대 석탄기~페름기`,
# `트라이아스기 후기~쥐라기 전기`. 낱말마다 옮기고 차례는 둔다. 옛 표기
# (오오도비스기·쥬라기·고제3기 — 100만 지질도)도 받는다. 모르는 낱말이
# 하나라도 있으면 **통째로 원문을 둔다** — 반만 옮긴 것은 틀린 것보다 나쁘다.

AGE_WORDS = {
    "선캄브리아시대": "Precambrian",
    "시생누대": "Archean", "시생대": "Archean",
    "고시생대": "Paleoarchean", "중시생대": "Mesoarchean", "신시생대": "Neoarchean",
    "원생누대": "Proterozoic", "원생대": "Proterozoic",
    "고원생대": "Paleoproterozoic", "중원생대": "Mesoproterozoic", "신원생대": "Neoproterozoic",
    # 원생누대의 기 — 앞의 것이 국제지질연대층서표 한글판(아래 AGE_STAGES)의 표기,
    # 뒤의 것은 전에 쓰던 음역이다. 옛것도 받고, 거꾸로 옮길 때는 앞의 것을 쓴다
    "시데로스기": "Siderian", "시데리아기": "Siderian",
    "라이악스기": "Rhyacian", "리아시아기": "Rhyacian",
    "오로세이라기": "Orosirian", "스타테로스기": "Statherian",
    "칼리마기": "Calymmian", "칼리미아기": "Calymmian",
    "엑타시스기": "Ectasian", "스테노스기": "Stenian", "토노스기": "Tonian",
    "크리오스진기": "Cryogenian", "크라이오제니아기": "Cryogenian", "에디아카라기": "Ediacaran",
    "명왕누대": "Hadean", "초시생대": "Eoarchean",
    "현생누대": "Phanerozoic",
    "고생대": "Paleozoic",
    "캄브리아기": "Cambrian", "캠브리아기": "Cambrian",
    "오르도비스기": "Ordovician", "오오도비스기": "Ordovician",
    "실루리아기": "Silurian", "사일루리아기": "Silurian",
    "데본기": "Devonian", "석탄기": "Carboniferous", "페름기": "Permian",
    "중생대": "Mesozoic",
    "트라이아스기": "Triassic", "쥐라기": "Jurassic", "쥬라기": "Jurassic",
    "백악기": "Cretaceous",
    "신생대": "Cenozoic",
    "고진기": "Paleogene", "고제3기": "Paleogene",
    "신진기": "Neogene", "신제3기": "Neogene",
    "제3기": "Tertiary", "제4기": "Quaternary",
    "팔레오세": "Paleocene", "에오세": "Eocene", "올리고세": "Oligocene",
    "마이오세": "Miocene", "플라이오세": "Pliocene",
    "플라이스토세": "Pleistocene", "홀로세": "Holocene",
    # 석탄기의 아기, 고생대의 세(통) — 한글판의 표기
    "미시시피아기": "Mississippian", "펜실베니아아기": "Pennsylvanian", "펜실베니아기": "Pennsylvanian",
    "시스우랄세": "Cisuralian", "과달루페세": "Guadalupian", "러핑세": "Lopingian",
    "란도베리세": "Llandovery", "웬록세": "Wenlock", "러들로세": "Ludlow", "프리돌리세": "Pridoli",
    "테레누브세": "Terreneuvian", "미아오링세": "Miaolingian", "푸롱세": "Furongian",
}

#: 절(Age) — **국제지질연대층서표 한글판**(ICS v2024/12, 대한지질학회 지질과학용어위원회
#: 옮김, stratigraphy.org/ICSchart/ChronostratChart2024-12Korean.pdf)의 표기 그대로다.
#: 전에는 한국어 표기가 하나로 굳지 않았다며 넣지 않았는데(021), ICS 가 싣는 한글판이
#: 학회의 승인을 거친 것이라 그것을 따른다. 캄브리아기의 이름 없는 절(Stage 2·3·4·10)은
#: 한글판이 `제2절` 처럼 적는다. 판이 오르면 이 표를 그 판과 대조한다.
AGE_STAGES = {
    # 제4기
    "메갈라야절": "Meghalayan", "노스그립절": "Northgrippian", "그린란드절": "Greenlandian",
    "지바절": "Chibanian", "칼라브리아절": "Calabrian", "젤라절": "Gelasian",
    # 신진기
    "피아첸차절": "Piacenzian", "장클레절": "Zanclean", "메시나절": "Messinian",
    "토르토나절": "Tortonian", "세라발레절": "Serravallian", "랑게절": "Langhian",
    "부르디갈라절": "Burdigalian", "아킨텐절": "Aquitanian",
    # 고진기
    "카티절": "Chattian", "루펠절": "Rupelian", "프리아보나절": "Priabonian",
    "바턴절": "Bartonian", "루테티아절": "Lutetian", "이퍼르절": "Ypresian",
    "타넷절": "Thanetian", "셀란절": "Selandian", "다니아절": "Danian",
    # 백악기
    "마스트리히트절": "Maastrichtian", "캄파이나절": "Campanian", "산토눔절": "Santonian",
    "코냑절": "Coniacian", "투로니아절": "Turonian", "세노마눔절": "Cenomanian",
    "알바절": "Albian", "압트절": "Aptian", "바렘절": "Barremian",
    "오트리브절": "Hauterivian", "발랑절": "Valanginian", "베리아절": "Berriasian",
    # 쥐라기
    "티토누스절": "Tithonian", "킴머리지절": "Kimmeridgian", "옥스퍼드절": "Oxfordian",
    "칼로비움절": "Callovian", "바토니움절": "Bathonian", "바조카에절": "Bajocian",
    "알렌절": "Aalenian", "토아르시움절": "Toarcian", "플린스바흐절": "Pliensbachian",
    "시네무룸절": "Sinemurian", "에탕주절": "Hettangian",
    # 트라이아스기
    "래티아절": "Rhaetian", "노릭절": "Norian", "카닉절": "Carnian", "라딘절": "Ladinian",
    "아니수스절": "Anisian", "올레네크절": "Olenekian", "인더스절": "Induan",
    # 페름기
    "창싱절": "Changhsingian", "우지아핑절": "Wuchiapingian", "캐피탄절": "Capitanian",
    "워드절": "Wordian", "로드절": "Roadian", "쿤구르절": "Kungurian",
    "아르틴스크절": "Artinskian", "사크마라절": "Sakmarian", "아셀절": "Asselian",
    # 석탄기
    "그젤절": "Gzhelian", "카시모프절": "Kasimovian", "모스코바절": "Moscovian",
    "바시키르절": "Bashkirian", "세르푸호프절": "Serpukhovian", "비제절": "Visean",
    "투르네절": "Tournaisian",
    # 데본기
    "파멘절": "Famennian", "프랜절": "Frasnian", "지베절": "Givetian", "아이펠절": "Eifelian",
    "엠즈절": "Emsian", "프라하절": "Pragian", "로치코프절": "Lochkovian",
    # 실루리아기
    "로드포드절": "Ludfordian", "고스티절": "Gorstian", "호머절": "Homerian",
    "셰인우드절": "Sheinwoodian", "텔리치절": "Telychian", "에어론절": "Aeronian",
    "루단절": "Rhuddanian",
    # 오르도비스기
    "허난트절": "Hirnantian", "케이티절": "Katian", "샌드비절": "Sandbian",
    "다리윌절": "Darriwilian", "다핑절": "Dapingian", "플로절": "Floian",
    "트레마독절": "Tremadocian",
    # 캄브리아기
    "지앙샨절": "Jiangshanian", "파이비절": "Paibian", "구장절": "Guzhangian",
    "드럼절": "Drumian", "울리우절": "Wuliuan", "포츈절": "Fortunian",
}
AGE_WORDS.update(AGE_STAGES)
#: 앞 낱말을 꾸미는 말. 영어는 앞에 둔다 — `트라이아스기 후기` → `Late Triassic`.
AGE_MODIFIERS = {"전기": "Early", "중기": "Middle", "후기": "Late"}
#: 통째로 옮기는 값.
AGE_WHOLE = {"미분류": "Unclassified", "시대 미상": "Age unknown", "시대미상": "Age unknown",
             # 지체구조도(`L_1M_tectonic_litho`)
             "고생대화성활동": "Paleozoic igneous activity"}


def age_en(value: str) -> str:
    """지질시대 값 하나를 영어로. 못 옮기면 원문을 그대로 돌려준다."""
    text = str(value or "").strip()
    if not text:
        return value
    if text in AGE_WHOLE:
        return AGE_WHOLE[text]
    parts, last_noun = [], ""
    for part in re.split(r"\s*[~\-]\s*", text):
        words = []
        for word in part.replace("시대 미상", "시대미상").split():
            if word in AGE_MODIFIERS and not words and last_noun:
                # `원생대 후기-전기` 의 뒤쪽처럼 꾸밈말만 오면 앞의 낱말을 잇는다
                words.append(f"{AGE_MODIFIERS[word]} {last_noun}")
            elif word in AGE_MODIFIERS and words:
                words[-1] = f"{AGE_MODIFIERS[word]} {words[-1]}"
            elif word in AGE_WORDS:
                words.append(AGE_WORDS[word])
                last_noun = AGE_WORDS[word]
            elif word in AGE_WHOLE:
                words.append(AGE_WHOLE[word])
            else:
                return value
        parts.append(" ".join(words))
    return " – ".join(parts)


# ── 지질시대 — 거꾸로 (영어 → 한국어) ──
#
# 노르웨이 극지연구소(NPI)의 지질도는 시대를 **영문 ICS 명칭**으로 준다 —
# `late Paleocene`·`Early - Middle Triassic`·`Carboniferous - Permian`. 한국어판에서는
# 위의 표를 거꾸로 써서 옮긴다(devlog 021). 규칙은 `age_en` 과 같다 — 모르는
# 낱말이 하나라도 있으면 **통째로 원문을 둔다.** 절(Age) 이름(`Bashkirian`·
# `Aptian`)은 국제지질연대층서표 한글판을 따른다(`AGE_STAGES`).

#: 영어 → 한국어. `AGE_WORDS` 에서 먼저 나온 한국어를 고른다(`시생누대`·`고진기`).
AGE_WORDS_KO = {}
for _ko, _en in AGE_WORDS.items():
    AGE_WORDS_KO.setdefault(_en.lower(), _ko)
# 영국식 철자 — NPI 가 섞어 쓴다(`Palaeoproterozoic`·`Early Palaeozoic`)
for _en in list(AGE_WORDS_KO):
    if "paleo" in _en:
        AGE_WORDS_KO.setdefault(_en.replace("paleo", "palaeo"), AGE_WORDS_KO[_en])
AGE_WORDS_KO.setdefault("archaean", AGE_WORDS_KO["archean"])
AGE_MODIFIERS_KO = {"early": "전기", "middle": "중기", "late": "후기"}
#: 사이를 잇는 말. 범위는 상류(KIGAM)처럼 `~` 로 붙여 적는다
AGE_JOINERS_KO = {"-": "~", "–": "~", "and/or": " 및/또는 ", "or": " 또는 ", "and": " 및 ",
                  ",": ", ", ";": ", "}
_AGE_TOKEN = re.compile(r"and/or|[A-Za-z]+|\?|[-–,;]")


#: 에스파냐어 시대 이름 → ICS 영문 (페루 INGEMMET wetherilli 195, 멕시코 SGM 206). 덧붙임표를 떼고 작은 글자로 견준다.
#: 절(Age)은 대개 `-iano` → `-ian`(Albiano → Albian)이라 표 없이 규칙으로 옮긴다(`age_es`)
AGES_ES = {
    "arqueano": "Archean", "arcaico": "Archean", "proterozoico": "Proterozoic", "paleoproterozoico": "Paleoproterozoic",
    "mesoproterozoico": "Mesoproterozoic", "neoproterozoico": "Neoproterozoic", "fanerozoico": "Phanerozoic",
    "paleozoico": "Paleozoic", "mesozoico": "Mesozoic", "cenozoico": "Cenozoic",
    "cambrico": "Cambrian", "ordovicico": "Ordovician", "silurico": "Silurian", "devonico": "Devonian",
    "carbonifero": "Carboniferous", "permico": "Permian", "triasico": "Triassic", "jurasico": "Jurassic",
    "cretacico": "Cretaceous", "cretaceo": "Cretaceous", "paleogeno": "Paleogene", "neogeno": "Neogene",
    "cuaternario": "Quaternary", "terciario": "Tertiary",
    "paleoceno": "Paleocene", "eoceno": "Eocene", "oligoceno": "Oligocene", "mioceno": "Miocene", "plioceno": "Pliocene",
    "pleistoceno": "Pleistocene", "holoceno": "Holocene",
    # 멕시코 지질 연대 점(wetherilli 219)
    "hadeano": "Hadean", "eoarqueano": "Eoarchean", "paleoarqueano": "Paleoarchean", "mesoarqueano": "Mesoarchean",
    "neoarqueano": "Neoarchean", "titoniano": "Tithonian", "precambrico": "Precambrian",
}
#: `Triásico Superior` 의 뒤 낱말 → ICS 의 앞 낱말 (wetherilli 219)
_ES_PART = {"superior": "Late", "medio": "Middle", "inferior": "Early", "tardio": "Late", "temprano": "Early"}


#: 프랑스어 시대 이름(악센트를 뗀 소문자) → ICS 영문 — 퀘벡 SIGÉOM (wetherilli 224)
AGES_FR = {
    "hadeen": "Hadean", "archeen": "Archean", "eoarcheen": "Eoarchean", "paleoarcheen": "Paleoarchean",
    "mesoarcheen": "Mesoarchean", "neoarcheen": "Neoarchean", "proterozoique": "Proterozoic",
    "paleoproterozoique": "Paleoproterozoic", "mesoproterozoique": "Mesoproterozoic", "neoproterozoique": "Neoproterozoic",
    "precambrien": "Precambrian", "phanerozoique": "Phanerozoic", "paleozoique": "Paleozoic", "mesozoique": "Mesozoic",
    "cenozoique": "Cenozoic", "cambrien": "Cambrian", "ordovicien": "Ordovician", "silurien": "Silurian", "devonien": "Devonian",
    "carbonifere": "Carboniferous", "mississippien": "Mississippian", "pennsylvanien": "Pennsylvanian", "permien": "Permian",
    "trias": "Triassic", "triasique": "Triassic", "jurassique": "Jurassic", "cretace": "Cretaceous", "paleogene": "Paleogene",
    "neogene": "Neogene", "quaternaire": "Quaternary", "tertiaire": "Tertiary", "paleocene": "Paleocene", "eocene": "Eocene",
    "oligocene": "Oligocene", "miocene": "Miocene", "pliocene": "Pliocene", "pleistocene": "Pleistocene", "holocene": "Holocene",
    "visean": "Visean",
}
#: `Ordovicien supérieur` 의 뒤 낱말 → ICS 의 앞 낱말
_FR_PART = {"inferieur": "Early", "precoce": "Early", "moyen": "Middle", "superieur": "Late", "tardif": "Late"}


def _fold(text: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", str(text).lower()) if not unicodedata.combining(c)).strip()


def _age_fr_one(text: str) -> str:
    folded = _fold(text)
    if folded in AGES_FR:
        return AGES_FR[folded]
    head, _, part = folded.rpartition(" ")
    if head in AGES_FR and part in _FR_PART:
        return f"{_FR_PART[part]} {AGES_FR[head]}"
    if folded.endswith("ien") and folded.isalpha():      # 절 이름 — Darriwilien → Darriwilian
        return folded[:-3].capitalize() + "ian"
    return ""


def age_fr(value: str) -> str:
    """프랑스어 시대 값 → ICS 영문 (wetherilli 224). `A à B`·`A ? B` 는 범위(`A - B`, 뒤는 물음표를 단다), `A ou B` 는 `A or B`.
    한 마디라도 모르면 원문 그대로 돌려준다 — 반쯤 옮긴 것을 내지 않는다."""
    import re
    text = str(value or "").strip()
    if not text:
        return text
    out = []
    for alt in re.split(r"\s+ou\s+", text):
        parts = re.split(r"\s+(à|\?)\s+", alt)
        names = [_age_fr_one(p) for p in parts[::2]]
        if not all(names):
            return text
        joined = names[0]
        for sep, name in zip(parts[1::2], names[1:]):
            joined += " - " + name + (" (?)" if sep == "?" else "")
        out.append(joined)
    return " or ".join(out)


def age_es(value: str) -> str:
    """에스파냐어 시대 이름 하나 → ICS 영문. 표에 없고 `-iano` 로 끝나면 절 이름으로 보고 `-ian` 으로 바꾼다. 모르면 원문 그대로."""
    import unicodedata
    text = str(value or "").strip()
    folded = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    if folded in AGES_ES:
        return AGES_ES[folded]
    head, _, part = folded.rpartition(" ")
    if head in AGES_ES and part in _ES_PART:
        return f"{_ES_PART[part]} {AGES_ES[head]}"
    if folded.endswith("iano") and folded.isalpha():
        return folded[:-1].capitalize()
    return text


#: 상류의 영어 시대 값에 섞인 오탈자·옛 말 (wetherilli 228) — 말레이시아 `Caroboniferous`, 필리핀 `Pliestocene`
#: 유럽 나라 지질도의 시대 낱말(독일어·네덜란드어·폴란드어·프랑스어) → ICS 영어 (wetherilli 237). 소문자·악센트 그대로 찾는다
AGE_LOCAL_WORDS = {
    # 대·기·세
    "quartär": "Quaternary", "kwartair": "Quaternary", "czwartorzęd": "Quaternary", "quaternaire": "Quaternary",
    "holozän": "Holocene", "holoceen": "Holocene", "holocen": "Holocene", "holocène": "Holocene",
    "pleistozän": "Pleistocene", "pleistoceen": "Pleistocene", "plejstocen": "Pleistocene", "pléistocène": "Pleistocene",
    "neogen": "Neogene", "néogène": "Neogene", "paläogen": "Paleogene", "paleogen": "Paleogene", "paléogène": "Paleogene",
    "tertiär": "Tertiary", "tertiair": "Tertiary", "trzeciorzęd": "Tertiary", "tertiaire": "Tertiary",
    "pliozän": "Pliocene", "plioceen": "Pliocene", "pliocen": "Pliocene", "pliocène": "Pliocene",
    "miozän": "Miocene", "mioceen": "Miocene", "miocen": "Miocene", "miocène": "Miocene",
    "oligozän": "Oligocene", "oligoceen": "Oligocene", "oligocen": "Oligocene", "oligocène": "Oligocene",
    "eozän": "Eocene", "eoceen": "Eocene", "eocen": "Eocene", "éocène": "Eocene",
    "paläozän": "Paleocene", "paleoceen": "Paleocene", "paleocen": "Paleocene", "paléocène": "Paleocene",
    "kreide": "Cretaceous", "krijt": "Cretaceous", "kreda": "Cretaceous", "crétacé": "Cretaceous",
    "jura": "Jurassic", "jurassique": "Jurassic", "trias": "Triassic", "perm": "Permian", "permien": "Permian",
    "karbon": "Carboniferous", "carboon": "Carboniferous", "carbonifère": "Carboniferous",
    "devon": "Devonian", "devoon": "Devonian", "dewon": "Devonian", "dévonien": "Devonian",
    "silur": "Silurian", "siluur": "Silurian", "sylur": "Silurian", "silurien": "Silurian",
    "ordovizium": "Ordovician", "ordovicium": "Ordovician", "ordowik": "Ordovician", "ordovicien": "Ordovician",
    "kambrium": "Cambrian", "cambrium": "Cambrian", "kambr": "Cambrian", "cambrien": "Cambrian",
    "känozoikum": "Cenozoic", "kenozoik": "Cenozoic", "mesozoikum": "Mesozoic", "mezozoik": "Mesozoic",
    "paläozoikum": "Paleozoic", "paleozoik": "Paleozoic", "paléozoïque": "Paleozoic",
    "proterozoikum": "Proterozoic", "proterozoik": "Proterozoic", "protérozoïque": "Proterozoic",
    "neoproterozoikum": "Neoproterozoic", "neoproterozoik": "Neoproterozoic",
    "präkambrium": "Precambrian", "prekambr": "Precambrian", "précambrien": "Precambrian",
    # 폴란드 MGP 의 절(Stage) — ICS 절 이름을 폴란드어로 적었다
    "mastrycht": "Maastrichtian", "kampan": "Campanian", "santon": "Santonian", "koniak": "Coniacian", "turon": "Turonian",
    "cenoman": "Cenomanian", "alb": "Albian", "apt": "Aptian", "barrem": "Barremian", "hoteryw": "Hauterivian",
    "walanżyn": "Valanginian", "berias": "Berriasian", "tyton": "Tithonian", "kimeryd": "Kimmeridgian", "oksford": "Oxfordian",
    "kelowej": "Callovian", "baton": "Bathonian", "bajos": "Bajocian", "aalen": "Aalenian", "toark": "Toarcian",
    "pliensbach": "Pliensbachian", "synemur": "Sinemurian", "hetang": "Hettangian", "retyk": "Rhaetian", "noryk": "Norian",
    "karnik": "Carnian", "ladyn": "Ladinian", "anizyk": "Anisian",
    # 왈로니아의 통·절(프랑스어)
    "famennien": "Famennian", "frasnien": "Frasnian", "givétien": "Givetian", "eifelien": "Eifelian", "emsien": "Emsian",
    "praguien": "Pragian", "lochkovien": "Lochkovian", "tournaisien": "Tournaisian", "viséen": "Visean",
    "yprésien": "Ypresian", "lutétien": "Lutetian", "rupélien": "Rupelian",
}
#: 꾸밈말 — 앞에 오든(독·네·프 — `frühe Kreide`) 뒤에 오든(폴·프 — `jura górna`·`Dévonien inférieur`) 받는다
AGE_LOCAL_MODIFIERS = {
    "früh": "Early", "frühe": "Early", "früher": "Early", "unter": "Early", "vroeg": "Early", "dolny": "Early", "dolna": "Early",
    "inférieur": "Early", "inférieure": "Early",
    "mittel": "Middle", "mittlere": "Middle", "midden": "Middle", "środkowy": "Middle", "środkowa": "Middle", "moyen": "Middle",
    "moyenne": "Middle",
    "spät": "Late", "späte": "Late", "später": "Late", "ober": "Late", "laat": "Late", "górny": "Late", "górna": "Late",
    "supérieur": "Late", "supérieure": "Late",
}


#: 붙여 쓰는 꾸밈말 — 긴 것부터 (wetherilli 239)
_AGE_GLUED = ("mittel", "unter", "ober", "früh", "spät")


def age_local(value: str) -> str:
    """독일어·네덜란드어·폴란드어·프랑스어 시대(`Perm - frühe Kreide`·`jura górna`·`Dévonien inférieur`·`Holoceen`) → ICS 영어
    (`Permian – Early Cretaceous`). 낱말 하나라도 모르면 빈 글 — 부르는 쪽이 원문을 보인다 (wetherilli 237)"""
    text = str(value or "").strip()
    if not text or text.lower() == "null":
        return ""
    parts = []
    for part in re.split(r"\s+(?:-|–|bis|tot|do|à)\s+|\s*–\s*|\s*,\s*", text):
        words = [w for w in re.split(r"[\s\-]+", part.strip().lower()) if w]
        if not words:
            continue
        noun, mod = "", ""
        for w in words:
            if w in AGE_LOCAL_WORDS and not noun:
                noun = AGE_LOCAL_WORDS[w]
            elif w in AGE_LOCAL_MODIFIERS and not mod:
                mod = AGE_LOCAL_MODIFIERS[w]
            else:
                # 독일어는 꾸밈말을 붙여 쓴다 — `Obertrias`·`Unterkreide`·`Mitteleozän` (wetherilli 239)
                glued = next(((m, w[len(m):]) for m in _AGE_GLUED if w.startswith(m) and w[len(m):] in AGE_LOCAL_WORDS), None)
                if glued is None or noun or mod:
                    return ""
                mod, noun = AGE_LOCAL_MODIFIERS[glued[0]], AGE_LOCAL_WORDS[glued[1]]
        if not noun:
            return ""
        parts.append(f"{mod} {noun}" if mod else noun)
    if not parts:
        return ""
    return parts[0] if len(set(parts)) == 1 else f"{parts[0]} – {parts[-1]}"


_AGE_TYPOS = {"caroboniferous": "Carboniferous", "pliestocene": "Pleistocene", "neoproteozoic": "Neoproterozoic"}


def age_tidy(value: str) -> str:
    """영어 시대 값을 `age_ko` 가 읽는 꼴로 — 대문자를 낱말 꼴로, `Upper`·`Lower` 를 `Late`·`Early` 로, `-`·`TO` 를 ` – ` 로,
    오탈자를 고친다. `Quaternary [Holocene]` 처럼 괄호 안이 더 자세하면 그쪽을 쓴다. `CRETACEOUS, JURASSIC`(젊은, 오랜)은 `오랜 – 젊은`."""
    text = str(value or "").strip()
    if not text:
        return ""
    inner = re.search(r"\[([^\]]+)\]", text)
    if inner:
        text = inner.group(1).strip()
    if "," in text:
        young, _, old = (p.strip() for p in text.partition(","))
        text = young if young.lower() == old.lower() or not old else f"{old} - {young}"
    text = re.sub(r"\s+(?:TO|to|To)\s+", " - ", text)
    text = re.sub(r"(?<![Pp]re)(?<!PRE)\s*-\s*", " – ", text)        # `Pre-Jurassic` 의 붙임표는 둔다
    words = []
    for word in text.split():
        if word == "–":
            words.append(word)
            continue
        low = word.lower()
        word = _AGE_TYPOS.get(low) or {"upper": "Late", "lower": "Early"}.get(low) or (word.title() if word.isupper() else word)
        words.append(word.replace("Palaeo", "Paleo").replace("Archaean", "Archean"))
    return " ".join(words)


def age_ko(value: str) -> str:
    """영문 지질시대 값 하나를 한국어로. 못 옮기면 원문을 그대로 돌려준다.

        late Paleocene              → 팔레오세 후기
        Early - Middle Triassic     → 트라이아스기 전기~중기
        Carboniferous - Permian     → 석탄기~페름기
        Neoproterozoic (?)          → 신원생대(?)
    """
    text = str(value or "").strip()
    if not text:
        return value
    rest = _AGE_TOKEN.sub("", text.replace("(?)", "?"))
    if rest.replace("(", "").replace(")", "").strip():
        return value                                   # 숫자·괄호 말 같은 모르는 것이 섞였다
    segments, joiners, current = [], [], {"mods": [], "noun": None, "doubt": False}
    for token in _AGE_TOKEN.findall(text.replace("(?)", "?")):
        low = token.lower()
        if low in AGE_JOINERS_KO:
            if not (current["mods"] or current["noun"]):
                return value
            segments.append(current)
            joiners.append(AGE_JOINERS_KO[low])
            current = {"mods": [], "noun": None, "doubt": False}
        elif token == "?":
            # 뒤에 붙은 것(`Paleocene ?`)도, 앞에 붙은 것(`- ? Oligocene`)도 지금 조각의 것이다
            current["doubt"] = True
        elif low in AGE_MODIFIERS_KO and not current["noun"]:
            current["mods"].append(AGE_MODIFIERS_KO[low])
        elif low in AGE_WORDS_KO and not current["noun"]:
            current["noun"] = AGE_WORDS_KO[low]
        else:
            return value
    if not (current["mods"] or current["noun"]):
        return value
    segments.append(current)
    # 꾸밈말만 있는 조각(`Early - Middle Triassic` 의 앞)은 뒤 조각의 낱말을 빌린다
    out, shown = [], None
    for index, seg in enumerate(segments):
        noun = seg["noun"]
        if noun is None:
            noun = next((s["noun"] for s in segments[index + 1:] if s["noun"]), None)
            if noun is None or not seg["mods"]:
                return value
        mods = " ".join(seg["mods"])
        if noun == shown and mods:
            piece = mods                               # 앞에서 적은 낱말은 되풀이하지 않는다
        else:
            piece = f"{noun} {mods}".strip()
        shown = noun
        out.append(piece + ("(?)" if seg["doubt"] else ""))
    return "".join(p + (joiners[i] if i < len(joiners) else "") for i, p in enumerate(out))


def age_ko_stacked(value: str) -> str:
    """위 단위부터 겹쳐 적은 영문 지질시대(일본 GSJ, devlog 024)를 한국어로.

        Cenozoic Quaternary Holocene              → 신생대 제4기 홀로세
        Mesozoic Early Triassic - Late Triassic   → 중생대 트라이아스기 전기~트라이아스기 후기
        Mesozoic Jurassic Early - Middle          → 중생대 쥐라기 전기~중기
        Neogene and Paleogene                     → 신진기 및 고진기

    `age_ko` 는 한 조각에 낱말 하나를 받아 이 꼴을 못 옮긴다. 꾸밈말은 뒤 낱말에
    붙이고(`Early Triassic`), 뒤에 낱말이 없으면 앞 낱말 뒤에 둔다(`Jurassic Early`).
    규칙은 같다 — 절(Age) 이름 같은 **모르는 낱말이 하나라도 있으면 원문**이다.
    꾸밈말이 겹친 것(`late Late Pleistocene` — 후기 플라이스토세를 다시 나눈 것)도
    원문이다. "플라이스토세 후기 후기" 는 읽히지 않는다.
    """
    text = str(value or "").strip()
    if not text:
        return value
    out = []
    for index, piece in enumerate(re.split(r"\s+(-|–|and)\s+", text)):
        if index % 2:
            out.append("~" if piece in "-–" else " 및 ")
            continue
        words, pending = [], []
        for word in piece.split():
            low = word.lower()
            if low in AGE_MODIFIERS_KO:
                pending.append(AGE_MODIFIERS_KO[low])
            elif low in AGE_WORDS_KO:
                words.append(" ".join([AGE_WORDS_KO[low]] + pending))
                pending = []
            else:
                return value
            if len(pending) > 1:
                return value
        words.extend(pending)
        if not words:
            return value
        out.append(" ".join(words))
    return "".join(out)


# ── 지질시대 — 중국어(번체) → 한국어·영어 ──
#
# 대만 지질운(wetherilli 136)은 시대를 번체 중국어로 준다 — `中新世晚期`·`上新世－更新世`·`早期至中期始新世`·
# `晚古生代至中生代（？）`. 낱말을 영어로 옮겨 조각을 세운 뒤 한국어는 `AGE_WORDS_KO` 로 적는다. 꾸밈말은 낱말
# 뒤(`中新世晚期`)에도 앞(`晚更新世`·`早期至中期始新世`)에도 온다. 규칙은 같다 — 모르는 글자가 남으면 원문이다.

AGE_ZH = {"全新世": "Holocene", "更新世": "Pleistocene", "上新世": "Pliocene", "中新世": "Miocene",
          "漸新世": "Oligocene", "始新世": "Eocene", "古新世": "Paleocene",
          "第四紀": "Quaternary", "第三紀": "Tertiary",
          "白堊紀": "Cretaceous", "侏羅紀": "Jurassic", "三疊紀": "Triassic", "二疊紀": "Permian",
          "石炭紀": "Carboniferous", "泥盆紀": "Devonian",
          "新生代": "Cenozoic", "中生代": "Mesozoic", "古生代": "Paleozoic"}
#: 통째로 받는 낱말 — 한국어·영어
AGE_ZH_WHOLE = {"現代": ("현세", "Recent"), "時代不詳": ("시대 미상", "Age unknown"),
                "先第三紀": ("선제3기", "Pre-Tertiary")}
AGE_ZH_MODS = {"早中期": ("early", "middle"), "中晚期": ("middle", "late"),
               "早期": ("early",), "中期": ("middle",), "晚期": ("late",),
               "早": ("early",), "中": ("middle",), "晚": ("late",)}
_AGE_ZH_TOKEN = re.compile("|".join(map(re.escape, sorted(
    [*AGE_ZH, *AGE_ZH_WHOLE, *AGE_ZH_MODS, "或更早", "或", "至", "－", "─", "-", "—", "～", "~",
     "（？）", "(？)", "（?）", "(?)", "？", "?"], key=len, reverse=True))))


def _age_zh_segments(text: str):
    """중국어 시대 값 → (조각들, 잇는 말들). 조각은 {"mods", "noun", "doubt", "whole"}. 못 읽으면 None."""
    if _AGE_ZH_TOKEN.sub("", text).strip():
        return None
    segments, joiners = [], []
    seg = {"mods": [], "noun": None, "doubt": False, "whole": None}
    for token in _AGE_ZH_TOKEN.findall(text):
        if token in AGE_ZH or token in AGE_ZH_WHOLE:
            if seg["noun"] or seg["whole"]:
                return None                                  # 낱말 둘이 잇는 말 없이 붙었다
            seg["noun" if token in AGE_ZH else "whole"] = token
        elif token in AGE_ZH_MODS:
            seg["mods"].extend(AGE_ZH_MODS[token])
        elif token.strip("（()）") in ("？", "?"):
            seg["doubt"] = True
        else:
            segments.append(seg)
            joiners.append({"或更早": "earlier", "或": "or"}.get(token, "-"))
            seg = {"mods": [], "noun": None, "doubt": False, "whole": None}
    segments.append(seg)
    if joiners and joiners[-1] == "earlier":                 # `始新世或更早` — 끝의 빈 조각은 말로 쓴다
        segments.pop()
    # 꾸밈말만 있는 조각은 뒤 조각의 낱말을 빌린다 — `早期至中期始新世` → 에오세 전기~에오세 중기
    for index in range(len(segments) - 2, -1, -1):
        if not segments[index]["noun"] and not segments[index]["whole"] and segments[index]["mods"]:
            segments[index]["noun"] = segments[index + 1]["noun"]
    # 끝 조각이 꾸밈말뿐이면 앞 조각의 낱말을 빌린다 — `中新世早期至中期` → 마이오세 전기~중기
    for index in range(1, len(segments)):
        if not segments[index]["noun"] and not segments[index]["whole"] and segments[index]["mods"]:
            segments[index]["noun"] = segments[index - 1]["noun"]
    if any(not (s["noun"] or s["whole"]) for s in segments):
        return None
    return segments, joiners


def age_zh(value: str, lang: str = "ko") -> str:
    """번체 중국어 지질시대 값 하나를 한국어(또는 영어)로. 못 옮기면 원문을 그대로 돌려준다.

        中新世晚期                 → 마이오세 후기          (Late Miocene)
        上新世－更新世             → 플라이오세~플라이스토세
        早期至中期始新世           → 에오세 전기~중기
        晚古生代至中生代（？）     → 고생대 후기~중생대(?)
        始新世或更早               → 에오세 또는 그 이전
    """
    text = str(value or "").strip()
    if not text:
        return value
    parsed = _age_zh_segments(text)
    if parsed is None:
        return value
    segments, joiners = parsed
    out, last_noun = [], None
    for index, seg in enumerate(segments):
        if seg["whole"]:
            word = AGE_ZH_WHOLE[seg["whole"]][0 if lang == "ko" else 1]
            last_noun = None
        elif lang == "ko":
            noun = AGE_WORDS_KO[AGE_ZH[seg["noun"]].lower()]
            mods = "·".join(AGE_MODIFIERS_KO[m] for m in seg["mods"])
            # 앞 조각과 낱말이 같으면 낱말을 되풀이하지 않는다 — `에오세 전기~중기`
            word = mods if (mods and noun == last_noun) else " ".join(filter(None, [noun, mods]))
            last_noun = noun
        else:
            mods = "–".join(m.capitalize() for m in seg["mods"])
            word = " ".join(filter(None, [mods, AGE_ZH[seg["noun"]]]))
        if seg["doubt"]:
            word += "(?)" if lang == "ko" else " (?)"
        out.append(word)
        if index < len(joiners):
            joiner = joiners[index]
            if joiner == "earlier":
                out.append(" 또는 그 이전" if lang == "ko" else " or earlier")
            elif joiner == "or":
                out.append(" 또는 " if lang == "ko" else " or ")
            else:
                out.append("~" if lang == "ko" else " – ")
    return "".join(out)


#: 값을 지질시대로 읽는 속성 이름.
AGE_PROPS =("지질시대", "시대", "퇴적물시기")


#: 5만 도폭 칸에 딸려 오는 링크의 이름표. 상류가 붙이는 고정된 말이다.
LINK_EN = {"(원도)": "(original map)", "(수치지질도)": "(digital map)", "열기": "open"}


#: 상류가 영어 짝을 따로 주는 열. 영어판에서는 **영어 짝을 제자리에 올리고**
#: 한국어 원문을 `(Korean)` 줄로 곁에 둔다 — 전에는 한국어 값이 `Formation`,
#: 영어 값이 `Formation (English)` 로 둘 다 떠서 영어판의 첫 줄이 한글이었다.
#: 원문을 버리지 않는 것은 한국어 문헌과 맞춰 볼 때 그 이름이 필요해서다.
ENGLISH_TWINS = {"지층명": "영문지층명", "도곽": "영문도곽", "지질노두명": "지질노두명_영문"}

#: 지체구조도(`L_1M_tectonic_litho`)의 `지체구조운동` — 다섯 가지뿐인 닫힌 낱말이라
#: 지질시대처럼 옮긴다. 지체구조구(경기육괴 …)는 고유명사라 옮기지 않는다.
TECTONIC_EN = {
    "마그마작용": "Magmatism",
    "변형기반암": "Deformed basement",
    "변형퇴적암": "Deformed sedimentary rocks",
    "중첩퇴적암": "Overlap sedimentary rocks",
    "구조동시성 대륙내 열곡": "Syntectonic intracontinental rift",
}


# GSJ 1:200만 일본 지질도(wetherilli 316)는 범례의 설명이 일본어다 — `後期更新世後期より完新世`·`中期始新世より中期中新世前期`·`時代未詳`.
# 조각은 `[앞 꾸밈]낱말[뒤 꾸밈]` 이고 `より`(부터)로 잇는다. 앞 꾸밈은 ICS 의 세(前期 = Early), 뒤 꾸밈은 그 세 안의 앞·가운데·뒤다.
# 모르는 글자가 남으면 원문이다 — `age_zh` 와 같은 규칙.
AGE_JA = {"完新世": "Holocene", "更新世": "Pleistocene", "鮮新世": "Pliocene", "中新世": "Miocene", "漸新世": "Oligocene",
          "始新世": "Eocene", "暁新世": "Paleocene", "古第三紀": "Paleogene", "新第三紀": "Neogene", "第四紀": "Quaternary",
          "白亜紀": "Cretaceous", "ジュラ紀": "Jurassic", "三畳紀": "Triassic", "二畳紀": "Permian", "石炭紀": "Carboniferous",
          "デボン紀": "Devonian", "シルル紀": "Silurian", "オルドビス紀": "Ordovician", "カンブリア紀": "Cambrian"}
AGE_JA_WHOLE = {"時代未詳": ("시대 미상", "Age unknown"), "先シルル紀": ("실루리아기 이전", "Pre-Silurian")}
AGE_JA_MODS = {"前期": "early", "中期": "middle", "後期": "late"}
#: 뒤 꾸밈(세 안의 앞·가운데·뒤) — 한국어
AGE_JA_PART_KO = {"early": "전반", "middle": "중반", "late": "후반"}
_AGE_JA_SEG = re.compile("^(前期|中期|後期)?(" + "|".join(map(re.escape, sorted(AGE_JA, key=len, reverse=True))) + ")(前期|中期|後期)?$")


def age_ja(value: str, lang: str = "ko") -> str:
    """일본어 지질시대 값 하나를 한국어(또는 영어)로. 못 옮기면 원문을 그대로 돌려준다.

        後期更新世後期より完新世   → 플라이스토세 후기 후반~홀로세     (late Late Pleistocene – Holocene)
        中期始新世より中期中新世前期 → 에오세 중기~마이오세 중기 전반
        二畳紀                     → 페름기
        時代未詳                   → 시대 미상
    """
    text = str(value or "").strip()
    if not text:
        return value
    out = []
    for part in text.split("より"):
        if part in AGE_JA_WHOLE:
            out.append(AGE_JA_WHOLE[part][0 if lang == "ko" else 1])
            continue
        found = _AGE_JA_SEG.match(part)
        if not found:
            return value
        pre, noun, post = found.group(1), AGE_JA[found.group(2)], found.group(3)
        if lang == "ko":
            words = [AGE_WORDS_KO[noun.lower()]]
            if pre:
                words.append(AGE_MODIFIERS_KO[AGE_JA_MODS[pre]])
            if post:
                words.append(AGE_JA_PART_KO[AGE_JA_MODS[post]])
        else:
            words = ([AGE_JA_MODS[post]] if post else []) + ([AGE_JA_MODS[pre].capitalize()] if pre else []) + [noun]
        out.append(" ".join(words))
    return ("~" if lang == "ko" else " – ").join(out)


def props_en(props: dict) -> dict:
    """팝업에 보일 속성을 영어로. 이름은 표로, 지질시대 값은 `age_en` 으로,
    링크 이름표는 `LINK_EN` 으로. 나머지 값은 상류가 준 그대로다."""
    out = {}
    twins = {main: props[twin] for main, twin in ENGLISH_TWINS.items()
             if main in props and twin in props and str(props[twin]).strip()}
    moved = {ENGLISH_TWINS[main] for main in twins}
    for key, value in props.items():
        if key in twins:
            name = PROP_EN.get(key, key)
            out[name] = twins[key]
            out[f"{name} (Korean)"] = value
            continue
        if key in moved:
            continue
        if key == "지체구조운동" and isinstance(value, str):
            value = TECTONIC_EN.get(value.strip(), value)
        if key in AGE_PROPS and isinstance(value, str):
            value = age_en(value)
        elif isinstance(value, dict) and value.get("links"):
            value = dict(value, links=[dict(link, label=LINK_EN.get(link["label"], link["label"]))
                                       for link in value["links"]])
        out[PROP_EN.get(key, key)] = value
    return out


# ── 레이어 ──────────────────────────────────────────────────────────
#
# 제목은 DB(`Layer.title`)에 한국어로 있고 사람이 손질한다. 영어 제목은
# 레이어 이름을 열쇠로 여기 둔다. 없으면 한국어 제목이 뜬다.

GROUP_EN = {
    "영국 수리지질·G-BASE (BGS)": "UK hydrogeology and G-BASE (BGS)", "영국 하천 퇴적물 지화학 (BGS CMIC)": "UK stream sediment geochemistry (BGS CMIC)",
    "알래스카 광물 (DGGS)": "Alaska minerals (DGGS)",
    "페루 지화학 지도첩 (INGEMMET)": "Peru geochemical atlas (INGEMMET)",
    "캐나다 주 광물 산지": "Canadian provincial mineral occurrences",
    "네바다 지질도 (NBMG 1:50만)": "Nevada geology (NBMG 1:500k)", "워싱턴 지질도 (DNR)": "Washington geology (DNR)",
    "오리건 지질도 (DOGAMI OGDC-6)": "Oregon geology (DOGAMI OGDC-6)",
    "프랑스 광상 (BRGM)": "France mineral deposits (BRGM)", "스페인 광물 (IGME)": "Spain minerals (IGME)",
    "독일 원료 (BGR)": "Germany raw materials (BGR)", "포르투갈 광상·지구물리 (LNEG)": "Portugal deposits and geophysics (LNEG)",
    "인도네시아 광물 자원 (ESDM)": "Indonesia mineral resources (ESDM)", "필리핀 광물 자원 (MGB)": "Philippines mineral resources (MGB)",
    "태국 광물 (DMR)": "Thailand minerals (DMR)", "사우디 광물 (SGS)": "Saudi Arabia minerals (SGS)", "몽골 광물 (MRIS)": "Mongolia minerals (MRIS)",
    "남아공 광업·자원 지역 (CGS)": "South Africa mining and resource areas (CGS)",
    "핀란드 지구물리 (GTK)": "Finland geophysics (GTK)", "북유럽 광상 (FODD)": "Fennoscandian ore deposits (FODD)",
    "스웨덴 광물·지구물리 (SGU)": "Sweden minerals and geophysics (SGU)",
    "페루 광물 자원 (INGEMMET)": "Peru mineral resources (INGEMMET)", "페루 지구물리 (INGEMMET)": "Peru geophysics (INGEMMET)",
    "영국 지구물리 (BGS)": "UK geophysics (BGS)", "영국 광물 자원 (BGS)": "UK mineral resources (BGS)",
    "그린란드 지구물리·지질구 (GEUS)": "Greenland geophysics and provinces (GEUS)", "그린란드 지질도 1:250만·1:10만 (GEUS)": "Greenland geological maps 1:2.5M and 1:100k (GEUS)",
    "브라질 광물 자원 (SGB)": "Brazil mineral resources (SGB)", "콜롬비아 금속광상·지구물리 (SGC)": "Colombia metallogeny and geophysics (SGC)",
    "아르헨티나 광상 (SEGEMAR 1:25만)": "Argentina mineral deposits (SEGEMAR 1:250k)",
    "퀸즐랜드 광물·지구물리 (GSQ)": "Queensland minerals and geophysics (GSQ)", "빅토리아 광상 (GSV)": "Victoria mineral deposits (GSV)", "빅토리아 지구물리 (GSV)": "Victoria geophysics (GSV)",
    "태즈메이니아 지질도 (MRT)": "Tasmania geology (MRT)", "뉴사우스웨일스 광물 (GSNSW)": "New South Wales minerals (GSNSW)", "노던테리토리 지질도 (NTGS)": "Northern Territory geology (NTGS)",
    "남호주 광물 산지 (GSSA)": "South Australia mineral occurrences (GSSA)", "남호주 지구물리 (SARIG)": "South Australia geophysics (SARIG)", "뉴질랜드 지구물리 (GNS)": "New Zealand geophysics (GNS)",
    "일본 지질도·중력 (GSJ)": "Japan geology and gravity (GSJ)", "일본 지구화학도 (GSJ, 하천 퇴적물)": "Japan geochemical map (GSJ, stream sediments)",
    "일본 지구화학도 — 나머지 원소 (GSJ)": "Japan geochemical map — other elements (GSJ)", "일본 자기 이상도 (GSJ 지질도Navi)": "Japan magnetic anomaly maps (GSJ Geological Map Navi)",
    "미국 광물 자원 (USGS)": "US mineral resources (USGS)", "미국 지구물리 (USGS)": "US geophysics (USGS)",
    "미국 지질 연대 측정 (USGS)": "US geochronology (USGS)",
    "캐나다 지질도 편찬 (NRCan CGMC)": "Canada geological compilation (NRCan CGMC)", "캐나다 광물 자원 (NRCan)": "Canada mineral resources (NRCan)",
    "하와이 지질도 (USGS)": "Hawaii geology (USGS)", "푸에르토리코 지질도 (USGS)": "Puerto Rico geology (USGS)",
    "호주 지질구 (GA)": "Australia geological provinces (GA)", "호주 핵심 광물 (GA 2025)": "Australia critical minerals (GA 2025)",
    "호주 지구물리 (GA)": "Australia geophysics (GA)",
    "호주 확인 자원 (GA 2025)": "Australia identified mineral resources (GA 2025)",
    "호주 지하수 (GA)": "Australia groundwater (GA)",
    "캐나다 지질도 (NRCan 1:500만)": "Geological Map of Canada (NRCan 1:5M)",
    "온타리오 지질도 (OGS 1:25만)": "Geology of Ontario (OGS 1:250k)",
    "퀘벡 지질도 (SIGÉOM)": "Geology of Québec (SIGÉOM)", "퀘벡 광물 산지 (SIGÉOM)": "Québec mineral showings (SIGÉOM)",
    "유콘 지질도 (YGS 1:25만)": "Yukon geology (YGS 1:250k)",
    "사스카치원 지질도 (SGS)": "Saskatchewan geology (SGS)", "노바스코샤 지질도 (1:50만)": "Nova Scotia geology (1:500k)",
    "앨버타 지질도 (AGS 1:100만)": "Alberta geology (AGS 1:1M)", "앨버타 광물 산지 (AGS)": "Alberta mineral occurrences (AGS)",
    "이탈리아 지질도 (ISPRA)": "Geology of Italy (ISPRA)", "포르투갈 지질도 (LNEG 1:50만)": "Geology of Portugal (LNEG 1:500k)",
    "스위스 지질도 (swisstopo)": "Geology of Switzerland (swisstopo)",
    "아이슬란드 기반암 1:60만 (NÍ)": "Bedrock of Iceland 1:600k (NÍ)", "아이슬란드 1:10만 (NÍ)": "Iceland 1:100k (NÍ)",
    "뉴질랜드 지질도 (GNS)": "Geology of New Zealand (GNS)", "뉴질랜드 구조 (GNS 1:25만)": "New Zealand structures (GNS 1:250k)",
    "남빅토리아랜드 1:25만 (GNS)": "Southern Victoria Land 1:250k (GNS)",
    "몽골 지질도 (MonGeoCat)": "Geology of Mongolia (MonGeoCat)",
    "인도 지질도 1:200만 (GSI)": "Geological Map of India 1:2M (GSI)",
    "사우디 지질도 1:25만 (SGS)": "Geology of Saudi Arabia 1:250k (SGS)",
    "카리브 지질도 (USGS 1:250만)": "Geology of the Caribbean (USGS 1:2.5M)",
    "빙하 아래 (Bedmap3)": "Beneath the ice (Bedmap3)",
    "대앤틸리스 지질도 (USGS SIM 3534)": "Geology of the Greater Antilles (USGS SIM 3534)",
    "파나마 지질도 (STRI·MICI 1:25만)": "Geology of Panama (STRI · MICI 1:250k)",
    "파라과이 지질도 (VMME)": "Geology of Paraguay (VMME)",
    "누벨칼레도니 지질도 (DIMENC)": "Geology of New Caledonia (DIMENC)",
    "프랑스령 앤틸리스 지질도 (BRGM)": "Geology of the French Antilles (BRGM)",
    "프랑스령 폴리네시아 지질도 (BRGM)": "Geology of French Polynesia (BRGM)",
    "레위니옹·마요트 지질도 (BRGM)": "Geology of Réunion and Mayotte (BRGM)",
    "생피에르 미클롱 지질도 (BRGM)": "Geology of Saint-Pierre-et-Miquelon (BRGM)", "남미 지질도 (USGS)": "Geology of South America (USGS)",
    "니카라과 지질도 (INETER)": "Geology of Nicaragua (INETER)", "도미니카공화국 지질도 (SGN 1:25만)": "Geology of the Dominican Republic (SGN 1:250k)",
    "오스트리아 지질도 (GeoSphere 1:100만)": "Geology of Austria (GeoSphere 1:1M)", "폴란드 지질도 (PIG-PIB 1:50만)": "Geology of Poland (PIG-PIB 1:500k)",
    "오스트리아 지질도 1:5만 (GeoSphere)": "Geology of Austria 1:50k (GeoSphere)",
    "폴란드 지질도 1:5만 (PIG-PIB SMGP)": "Geology of Poland 1:50k (PIG-PIB SMGP)",
    "네덜란드 지질도 (TNO)": "Geology of the Netherlands (TNO)", "플랑드르 지질도 (DOV)": "Geology of Flanders (DOV)",
    "왈로니아 지질도 (SPW 1:2.5만)": "Geology of Wallonia (SPW 1:25k)",
    "브리티시컬럼비아 지질도 (BCGS)": "Geology of British Columbia (BCGS)", "캘리포니아 지질도 (CGS 1:75만)": "Geologic Map of California (CGS 1:750k)",
    "인도네시아 지질도 (ESDM)": "Geology of Indonesia (ESDM)", "말레이시아 지질도 (JMG)": "Geology of Malaysia (JMG)",
    "필리핀 지질도 (MGB)": "Geology of the Philippines (MGB)", "태국 지질도 (DMR)": "Geology of Thailand (DMR)",
    "지질 구조 (5만)": "Geological structures (1:50k)",
    "화석·화산·지진": "Fossils, volcanoes, earthquakes",
    "국토지리원 주제도": "GSI thematic maps",
    "쇄빙연구선 아라온호": "Icebreaker RV Araon",
    "동·동남아시아 지질도 (CCOP)": "East & Southeast Asia geology (CCOP)",
    # 대만 (wetherilli 136)
    "대만 지질도 (GSMMA)": "Taiwan geology (GSMMA)",
    "대만 5만 유역 지질도 (GSMMA)": "Taiwan 1:50k drainage-basin geology (GSMMA)", "대만 광상 (GSMMA)": "Taiwan ore deposits (GSMMA)", "대만 지구물리 (GSMMA)": "Taiwan geophysics (GSMMA)",
    "대만 구조 (GSMMA)": "Taiwan structure (GSMMA)",
    "대만 환경지질 (GSMMA)": "Taiwan environmental geology (GSMMA)",
    "대만 지질 민감구역 (GSMMA)": "Taiwan geologically sensitive areas (GSMMA)",
    "대만 시추·온천 (GSMMA)": "Taiwan boreholes & hot springs (GSMMA)",
    "IBCSO 해저지형": "IBCSO bathymetry",
    "지질도": "Geological maps",
    "탄전지질도": "Coalfield geological maps",
    "지구물리이상도": "Geophysical anomaly maps", "움직이는 지구": "Earth in flux", "지구물리": "Geophysics",
    "지구물리 (ADMAP-2)": "Geophysics (ADMAP-2)",
    "지화학도": "Geochemical maps",
    "좋은물지도": "Groundwater quality maps",
    "해저지질도": "Marine geological maps",
    "동위원소 연대지도": "Isotope age maps",
    "그 밖": "Other",
    "지질 참고": "Geological reference",
    "수질·지하수 측정망": "Water quality & groundwater monitoring",
    "보호구역": "Protected areas",
    "토양·산림": "Soils & forests",
    "재해·공역": "Hazards & airspace",
    # 그린란드 (GEUS)
    "야외 관찰": "Field observations",
    "지화학": "Geochemistry",
    "탄성파 탐사": "Seismic surveys",
    # 그린란드 정부 포털
    "시료·연대 (정부 포털)": "Samples & ages (government portal)",
    "광물 자원 (정부 포털)": "Mineral resources (government portal)",
    "지화학 (정부 포털)": "Geochemistry (government portal)",
    "사면 재해 (정부 포털)": "Slope hazards (government portal)",
    # 남극 (GeoMAP)
    "GeoMAP 지질도": "GeoMAP geological maps",
    # 얀마옌 (NPI)
    "얀마옌 지질 (NPI)": "Jan Mayen geology (NPI)",
    # 노르웨이 극지연구소 (npolar.py, devlog 021)
    "스발바르 지질 (NPI)": "Svalbard geology (NPI)",
    "스발바르 시료·층서 (NPI)": "Svalbard samples & stratigraphy (NPI)",
    "스발바르 빙하 (NPI)": "Svalbard glaciers (NPI)",
    "드로닝모드랜드 (NPI)": "Dronning Maud Land (NPI)",
    # 일본 (gsj.py, devlog 024)
    "심리스 지질도 (GSJ)": "Seamless geological map (GSJ)",
    # 중국 (geo3al.py, devlog 025)
    "중국·동아시아 지질 (USGS)": "China & East Asia geology (USGS)",
    # 우리가 모은 자료로 그린 레이어 — 첫째가 phyloserver 의 암맥 (devlog 026)
    "커스텀 지질도": "Custom geological maps",
    "극지연구소 시료": "KOPRI samples",
    "KPDC 자료": "KPDC datasets",
    "KPDC 기본도": "KPDC base map",
    "지형 (PGC)": "Terrain (PGC)",
    "해저 지질 (EMODnet)": "Seabed geology (EMODnet)",
    "노르웨이 기반암 (NGU)": "Norway bedrock (NGU)",
    "노르웨이 광물 (NGU)": "Norway minerals (NGU)",
    "노르웨이 지구물리 (NGU)": "Norway geophysics (NGU)",
    "핀란드 기반암 (GTK)": "Finland bedrock (GTK)",
    "스웨덴 기반암 (SGU)": "Sweden bedrock (SGU)",
    "영국 지질 (BGS)": "Great Britain geology (BGS)",
    "프랑스 지질 (BRGM)": "France geology (BRGM)",
    "유럽 지질 (EGDI 1:100만)": "Europe geology (EGDI 1:1M)",
    "독일 지질 (BGR)": "Germany geology (BGR)",
    "유럽 1:500만 (IGME5000)": "Europe 1:5M (IGME5000)",
    "스페인 지질 (IGME)": "Spain geology (IGME)",
    "아일랜드 기반암 (GSI·GSNI)": "Ireland bedrock (GSI · GSNI)",
    "남미 지질도 (CGMW 1:500만)": "South America geology (CGMW 1:5M)",
    "콜롬비아 지질도 (SGC 1:50만)": "Colombia geology (SGC 1:500k)",
    "브라질 지질도 (SGB 1:250만, 2025)": "Brazil geology (SGB 1:2.5M, 2025)",
    "브라질 지질도 (SGB 1:100만·1:25만)": "Brazil geology (SGB 1:1M · 1:250k)",
    "브라질 지질 자료 점 (SGB)": "Brazil geological data points (SGB)",
    "페루 지질도 (INGEMMET)": "Peru geology (INGEMMET)",
    "페루 단층·습곡 (INGEMMET)": "Peru faults & folds (INGEMMET)",
    "아르헨티나 지질도 (SEGEMAR 1:250만)": "Argentina geology (SEGEMAR 1:2.5M)",
    "아르헨티나 지질도 (SEGEMAR 1:25만, 간행 도폭)": "Argentina geology (SEGEMAR 1:250k, published sheets)",
    "아르헨티나 지역 지질도 (SEGEMAR 1:100만·1:75만·1:50만)": "Argentina regional geology (SEGEMAR 1:1M · 1:750k · 1:500k)",
    "아르헨티나 지질 위험 (SEGEMAR)": "Argentina geohazards (SEGEMAR)",
    "퀸즐랜드 지질도 (GSQ)": "Queensland geology (GSQ)", "빅토리아 지질도 (GSV)": "Victoria geology (GSV)",
    "남호주 지질도 (GSSA)": "South Australia geology (GSSA)",
    "우루과이 지질도 (DINAMIGE 1:50만)": "Uruguay geology (DINAMIGE 1:500k)",
    "아프리카 지질도 (CGMW–BRGM 1:1000만)": "Africa geology (CGMW–BRGM 1:10M)",
    "아프리카 나라별 지질 (BGS 지하수 지도책 1:500만)": "Africa country geology (BGS Groundwater Atlas 1:5M)",
    "남아프리카공화국 지질도 (CGS 1:100만)": "South Africa geology (CGS 1:1M)",
    "나미비아 지질도 (GSN 1:100만)": "Namibia geology (GSN 1:1M)",
    "부르키나파소 지질도 (BUMIGEB 1:100만)": "Burkina Faso geology (BUMIGEB 1:1M)", "카메룬 지질도 (IRGM 1:100만)": "Cameroon geology (IRGM 1:1M)",
    "에콰도르 지질도 (IIGE)": "Ecuador geology (IIGE)",
    "미국 본토 지질도 (USGS SGMC)": "Conterminous US geology (USGS SGMC)",
    "알래스카 지질도 (USGS SIM 3340)": "Alaska geology (USGS SIM 3340)",
    "멕시코 지질도 (SGM 1:25만)": "Mexico geology (SGM 1:250k)",
    "호주 지표 지질도 (GA 1:250만·1:100만)": "Australia surface geology (GA 1:2.5M · 1:1M)",
    "멕시코 지질도 (SGM 1:5만, 광업 지구)": "Mexico geology (SGM 1:50k, mining districts)",
    "멕시코 지질 연대·화석 (SGM)": "Mexico geochronology and fossils (SGM)", "멕시코 광상 (SGM 1:25만)": "Mexico mineral deposits (SGM 1:250k)", "멕시코 지화학 (SGM)": "Mexico geochemistry (SGM)", "멕시코 지구물리 (SGM)": "Mexico geophysics (SGM)",
}

LAYER_EN = {
    # VWorld — Capabilities 와 다시 견주어 더한 것 (wetherilli 350)
    "lt_c_gimslinea": "Lineament density", "lt_c_gimsstiff": "Groundwater quality diagrams", "lt_l_gimsdirec": "Groundwater flow direction",
    "lt_l_toisdepcntah": "Coastline", "lt_c_wgisrecomp": "Reclaimed land (completed)", "lt_c_uq125": "Disaster prevention districts",
    # 영국 수리지질·G-BASE·CMIC 하천 퇴적물 (wetherilli 324)
    "bgsgi:hydrogeology": "Hydrogeology (1:625k)", "bgsgi:gbase_streamsed": "G-BASE stream sediment sample sites",
    "bgsgi:gq:CaO": "Calcium (CaO)",
    "bgsgi:gq:Fe2O3": "Iron (Fe₂O₃)",
    "bgsgi:gq:K2O": "Potassium (K₂O)",
    "bgsgi:gq:MgO": "Magnesium (MgO)",
    "bgsgi:gq:MnO": "Manganese (MnO)",
    "bgsgi:gq:TiO2": "Titanium (TiO₂)",
    "bgsgi:gq:Sb": "Antimony (Sb)",
    "bgsgi:gq:As": "Arsenic (As)",
    "bgsgi:gq:Ba": "Barium (Ba)",
    "bgsgi:gq:Be": "Beryllium (Be)",
    "bgsgi:gq:Bi": "Bismuth (Bi)",
    "bgsgi:gq:Cd": "Cadmium (Cd)",
    "bgsgi:gq:Ce": "Cerium (Ce)",
    "bgsgi:gq:Cr": "Chromium (Cr)",
    "bgsgi:gq:Co": "Cobalt (Co)",
    "bgsgi:gq:Cu": "Copper (Cu)",
    "bgsgi:gq:Ga": "Gallium (Ga)",
    "bgsgi:gq:La": "Lanthanum (La)",
    "bgsgi:gq:Pb": "Lead (Pb)",
    "bgsgi:gq:Li": "Lithium (Li)",
    "bgsgi:gq:Mo": "Molybdenum (Mo)",
    "bgsgi:gq:Ni": "Nickel (Ni)",
    "bgsgi:gq:Rb": "Rubidium (Rb)",
    "bgsgi:gq:Sr": "Strontium (Sr)",
    "bgsgi:gq:Sn": "Tin (Sn)",
    "bgsgi:gq:W": "Tungsten (W)",
    "bgsgi:gq:U": "Uranium (U)",
    "bgsgi:gq:V": "Vanadium (V)",
    "bgsgi:gq:Y": "Yttrium (Y)",
    "bgsgi:gq:Zn": "Zinc (Zn)",
    "bgsgi:gq:Zr": "Zirconium (Zr)",
    # 알래스카 광물 (wetherilli 322)
    "dggs:minerals": "Significant mines and occurrences (DDS 18)", "dggs:districts": "Mining districts",
    # 페루 지화학 지도첩·산업 광물 (wetherilli 303)
    "ingemmet:gq_au": "Gold (Au) dispersion and anomalies",
    "ingemmet:gq_ag": "Silver (Ag) dispersion and anomalies",
    "ingemmet:gq_cu": "Copper (Cu) dispersion and anomalies",
    "ingemmet:gq_mo": "Molybdenum (Mo) dispersion and anomalies",
    "ingemmet:gq_pb": "Lead (Pb) dispersion and anomalies",
    "ingemmet:gq_zn": "Zinc (Zn) dispersion and anomalies",
    "ingemmet:gq_as": "Arsenic (As) dispersion and anomalies",
    "ingemmet:gq_hg": "Mercury (Hg) dispersion and anomalies",
    "ingemmet:gq_co": "Cobalt (Co) dispersion and anomalies",
    "ingemmet:gq_ni": "Nickel (Ni) dispersion and anomalies",
    "ingemmet:gq_cr": "Chromium (Cr) dispersion and anomalies",
    "ingemmet:rmi": "Industrial rocks and minerals", "ingemmet:lithium": "Lithium occurrences",
    # 캐나다 주 광물 산지 (wetherilli 288)
    "bcgs:minfile": "British Columbia MINFILE mineral occurrences", "ygs:57": "Yukon MINFILE mineral occurrences",
    "ogs:11": "Ontario mineral deposit inventory (MDI)", "sigeom:mines": "Québec active mines and advanced projects", "sigeom:gites_metal": "Metallic mineral showings", "sigeom:gites_nonmetal": "Non-metallic mineral showings", "sigeom:gites_stone": "Building and industrial stone showings",
    "skgs:smdi": "Saskatchewan mineral deposits index (SMDI)", "skgs:mines": "Saskatchewan mine locations",
    # 미국 주 지질도 (wetherilli 291)
    "nbmg:geology": "Geologic map (1:500,000)", "wadnr:500k": "Geologic map (1:500,000)", "wadnr:100k": "Geologic map (1:100,000 GeMS)",
    "dogami:ogdc": "Oregon Geologic Data Compilation (OGDC-6)",
    # 유럽 광물 (wetherilli 296)
    "brgm:GITES_PT": "Deposits and showings (BD Gîtes)", "brgm:MINES_PT": "Mines (main commodities)",
    "igme:bdmin:0+1": "Mineral occurrences (BDMIN)", "igme:bdminexp:0+1": "Industrial rock and mineral workings (BDMIN)",
    "bgr:kor250:2+3+4": "Deposits and workings (KOR250 1:250k)", "bgr:kor250:0+1": "Raw material occurrences and prospective areas (KOR250)",
    "bgr:bsk1000:0+1+2+3+4": "Mineral resources (BSK1000 1:1M)",
    "lneg:dep200k:4": "Mineral deposits (1:200k)", "lneg:mag:0": "Magnetic anomaly", "lneg:grav:0": "Gravity anomaly (southern part)",
    "lneg:rad:Radiometria": "Radiometry (total gamma)",
    # 아시아 광물 (wetherilli 280)
    "esdm:metal": "Metallic mineral potential", "esdm:nonmetal": "Non-metallic mineral and rock potential",
    "mgb:metallic": "Metallic mineral resources", "mgb:nonmetallic": "Non-metallic mineral resources",
    "dmr:min_occ": "Mineral occurrences", "dmr:critical": "Critical mineral occurrences",
    "sgs:mods": "Mineral occurrences (MODS)", "sgs:belts": "Mineralization belts (gold, nickel, zinc, VMS)",
    "mris:ree": "Rare earth deposits, mineralized points and occurrences",
    # 남아공 광업·자원 지역 (wetherilli 285)
    "cgs:mining_areas": "Main mining areas (CSIR)", "cgs:coal": "Main coal resource areas", "cgs:uranium": "Uranium areas",
    # 북유럽 광물·지구물리 (wetherilli 270)
    "gtk:aeromagneettinen_anomaliakartta": "Aeromagnetic anomaly", "gtk:aeroradiometrinen_yhdistelmakartta": "Aeroradiometric ternary (K·Th·U)",
    "gtk:fennoscandia_mineral_deposit": "Ore deposits (Norway, Sweden, Finland, NW Russia)",
    "sgu:minerals": "Mineral and rock occurrences", "sgu:magnetic": "Magnetic anomaly",
    # 페루 광물·지구물리 (wetherilli 277)
    "ingemmet:deposits": "Mineral deposits (Yacimientos mineros)", "ingemmet:projects": "Mining projects and operations",
    "ingemmet:occ_metal": "Metallic mineral occurrences (10–18° S)", "ingemmet:occ_nonmetal": "Non-metallic mineral occurrences (10–18° S)",
    "ingemmet:belts": "Metallogenic belts (Franjas metalogenéticas)", "ingemmet:bouguer": "Bouguer gravity anomaly",
    "ingemmet:aeromag": "Aeromagnetics",
    # 영국 GeoIndex (wetherilli 258)
    "bgsgi:magnetic": "Magnetic anomalies (colour shaded)", "bgsgi:gravity": "Gravity anomalies (colour shaded)",
    "bgsgi:mines": "Mines and quarries (BritPits)", "bgsgi:occurrences": "Mineral occurrences (MINGOL)",
    # GEUS ArcGIS (wetherilli 259)
    "geusarc:magnetic": "Magnetic anomaly compilation", "geusarc:bouguer": "Bouguer gravity anomaly (DTU)",
    "geusarc:provinces": "Geological provinces (1:2.5M)",
    "geusarc:aeromag": "Airborne magnetics AEROMAG 1992–2013", "geusarc:aeromag_tilt": "Airborne magnetics tilt derivative",
    "geusarc:awi": "Airborne magnetics AWI 1993–96 (east)", "geusarc:aem": "Helicopter magnetic surveys (local)",
    "geusarc:g2500k": "Geological map 1:2.5M", "geusarc:g100k_ssw": "South-West Greenland geological map 1:100k",
    "geusarc:g100k_karrat": "Karrat geological map 1:100k",
    # 남미 광물·지구물리 (wetherilli 265)
    "sgb:mineral_occurrences": "Mineral occurrences (SGB)",
    "sgc:met:11": "Mineral deposits (Metallogenic map 2022)", "sgc:met:10": "Metallogenic belts (2022)", "sgc:met:8": "Metallogenic districts (2022)",
    "sgc:geof:8": "Total magnetic intensity (airborne geophysics 2022)", "sgc:geof:1": "Gamma-ray ternary (K·Th·U, 2022)",
    "segemar:e250K.DepositMetalif": "Metallic mineral deposits (1:250k)", "segemar:e250K.DepositMinIndust": "Industrial mineral deposits (1:250k)",
    # 오세아니아 광물·지구물리 (wetherilli 269)
    "gsq:mines": "Mines and mineral occurrences (MINOCC)", "gsq:tmi": "Total magnetic intensity (TMI)", "gsq:radiometric": "Radiometric ternary",
    "gsq:gravity": "Complete Bouguer gravity anomaly", "gsv:mineral": "Mineral deposits (polygons)", "gsv:mineralp": "Mineral deposits (points)",
    "gsv:gravity": "Gravity stations",
    "mrt:250k": "Tasmania geology (1:250k compilation)", "mrt:25k": "Tasmania geology (1:25k)",
    "ntgs:geology": "Northern Territory geology 1:2.5M (interpreted)", "ntgs:faults": "Northern Territory faults 1:2.5M",
    "gsnsw:minocc": "New South Wales mineral occurrences", "gsnsw:mines": "New South Wales mines", "gsv:lin_tmi": "Magnetic lineaments (TMI)", "gsv:lin_gravity": "Gravity lineaments",
    "gsv:lin_radio": "Radiometric lineaments",
    "gssa:minocc": "Mineral occurrences (SARIG)", "gssa:tmi_rtp": "Total magnetic intensity (reduced to pole)", "gssa:tmi_rtp_1vd": "TMI first vertical derivative",
    "gssa:tmi_tilt": "TMI tilt derivative", "gssa:grav": "Bouguer gravity", "gssa:grav_1vd": "Gravity first vertical derivative",
    "gssa:rad_rgb": "Radiometric ternary (K·Th·U)", "gssa:rad_k": "Radiometric potassium (K)", "gssa:rad_th": "Radiometric thorium (eTh)",
    "gssa:rad_u": "Radiometric uranium (eU)", "gssa:rad_tc": "Radiometric total count", "gns:gravity": "Gravity anomaly",
    # GSJ 의 다른 WMS (wetherilli 255)
    "gsjows:japan2m": "Geological map of Japan (1:2M)", "gsjows:gravity": "Bouguer gravity anomaly (density 2.67)",
    "gsjows:geochem:Al2O3": "Aluminium (Al₂O₃) — geochemical map",
    "gsjows:geochem:CaO": "Calcium (CaO) — geochemical map",
    "gsjows:geochem:MgO": "Magnesium (MgO) — geochemical map",
    "gsjows:geochem:MnO": "Manganese (MnO) — geochemical map",
    "gsjows:geochem:Na2O": "Sodium (Na₂O) — geochemical map",
    "gsjows:geochem:P2O5": "Phosphorus (P₂O₅) — geochemical map",
    "gsjows:geochem:TiO2": "Titanium (TiO₂) — geochemical map",
    "gsjows:geochem:Ba": "Barium — geochemical map",
    "gsjows:geochem:Be": "Beryllium — geochemical map",
    "gsjows:geochem:Bi": "Bismuth — geochemical map",
    "gsjows:geochem:Cd": "Cadmium — geochemical map",
    "gsjows:geochem:Ce": "Cerium — geochemical map",
    "gsjows:geochem:Co": "Cobalt — geochemical map",
    "gsjows:geochem:Cs": "Caesium — geochemical map",
    "gsjows:geochem:Dy": "Dysprosium — geochemical map",
    "gsjows:geochem:Er": "Erbium — geochemical map",
    "gsjows:geochem:Eu": "Europium — geochemical map",
    "gsjows:geochem:Ga": "Gallium — geochemical map",
    "gsjows:geochem:Gd": "Gadolinium — geochemical map",
    "gsjows:geochem:Hf": "Hafnium — geochemical map",
    "gsjows:geochem:Ho": "Holmium — geochemical map",
    "gsjows:geochem:La": "Lanthanum — geochemical map",
    "gsjows:geochem:Li": "Lithium — geochemical map",
    "gsjows:geochem:Lu": "Lutetium — geochemical map",
    "gsjows:geochem:Mo": "Molybdenum — geochemical map",
    "gsjows:geochem:Nb": "Niobium — geochemical map",
    "gsjows:geochem:Nd": "Neodymium — geochemical map",
    "gsjows:geochem:Pr": "Praseodymium — geochemical map",
    "gsjows:geochem:Rb": "Rubidium — geochemical map",
    "gsjows:geochem:Sb": "Antimony — geochemical map",
    "gsjows:geochem:Sc": "Scandium — geochemical map",
    "gsjows:geochem:Sm": "Samarium — geochemical map",
    "gsjows:geochem:Sn": "Tin — geochemical map",
    "gsjows:geochem:Sr": "Strontium — geochemical map",
    "gsjows:geochem:Ta": "Tantalum — geochemical map",
    "gsjows:geochem:Tb": "Terbium — geochemical map",
    "gsjows:geochem:Tl": "Thallium — geochemical map",
    "gsjows:geochem:Tm": "Thulium — geochemical map",
    "gsjows:geochem:V": "Vanadium — geochemical map",
    "gsjows:geochem:Y": "Yttrium — geochemical map",
    "gsjows:geochem:Yb": "Ytterbium — geochemical map",
    "gsjows:geochem:Zr": "Zirconium — geochemical map",
    "gsjows:magnetic_japan": "Magnetic map of Japan (1:2M, 1992)", "gsjows:magnetic_eastasia_1994": "Magnetic anomaly map of East Asia (1:4M, 1994)",
    "gsjows:magnetic_eastasia_2021": "Magnetic anomaly map of East and Southeast Asia (3rd ed., 2021)",
    "gsjows:geochem:Cu": "Copper — geochemical map",
    "gsjows:geochem:Pb": "Lead — geochemical map",
    "gsjows:geochem:Zn": "Zinc — geochemical map",
    "gsjows:geochem:As": "Arsenic — geochemical map",
    "gsjows:geochem:Hg": "Mercury — geochemical map",
    "gsjows:geochem:Cr": "Chromium — geochemical map",
    "gsjows:geochem:Ni": "Nickel — geochemical map",
    "gsjows:geochem:Fe2O3": "Iron (Fe₂O₃) — geochemical map",
    "gsjows:geochem:K2O": "Potassium (K₂O) — geochemical map",
    "gsjows:geochem:U": "Uranium — geochemical map",
    "gsjows:geochem:Th": "Thorium — geochemical map",
    # 캐나다 (wetherilli 204)
    "nrcan:wheeler": "Geological Map of Canada (1:5M, Wheeler)", "ogs:3": "Ontario bedrock (1:250k)",
    # NRCan 의 다른 서비스 (wetherilli 250)
    "nrcan:cgmc": "Canada Geological Map Compilation (CGMC)", "nrcan:critical": "Critical minerals sites (mines, processing, exploration)",
    "nrcan:ree": "Carbonatite REE–Nb prospectivity", "nrcan:lithium": "LCT pegmatite lithium prospectivity",
    "ogs:1": "Ontario Quaternary geology",
    "sigeom:generale": "General geology (Québec)", "sigeom:regionale": "Regional geology (Québec, 1:20k–1:250k)",
    "sigeom:failles": "Faults (Québec)", "ygs:47": "Bedrock (Yukon 1:250k)", "ygs:50": "Faults (Yukon)",
    # 캐나다 주 판 둘째 (wetherilli 235)
    "skgs:2": "Bedrock (Saskatchewan 1:1M)", "skgs:3": "Bedrock (Saskatchewan 1:250k, Shield)",
    "skgs:11": "Major faults and shear zones (Saskatchewan 1:1M)", "nsgs:11": "Bedrock (Nova Scotia 1:500k)",
    "nsgs:9": "Faults (Nova Scotia 1:500k)", "ags:bedrock": "Bedrock (Alberta 1:1M, Map 600)", "ags:minocc": "Alberta mineral occurrences",
    "ogs:6": "Ontario faults", "ogs:4": "Ontario dikes", "ogs:5": "Ontario iron formations",
    # 이탈리아·포르투갈·스위스 (wetherilli 211)
    "ispra:1m:0": "Italy geological units (1:1M)", "ispra:1m:1": "Italy faults (1:1M)",
    "ispra:100k:1": "Italy geological units (1:100k)", "ispra:100k:2": "Italy tectonics (1:100k)",
    "lneg:500k:2": "Portugal geology (1:500k)", "lneg:500k:1": "Portugal structures (1:500k)",
    "lneg:500k:4": "Portugal shelf geology (1:500k)", "lneg:500k:3": "Portugal shelf structures (1:500k)",
    "swisstopo:geologische_karte": "Geological map of Switzerland (1:500k)", "swisstopo:geocover": "GeoCover (1:25k)",
    # 아이슬란드 (wetherilli 216)
    "ni:ni_j600v_berg_2_jardlog_2utg_fl": "Bedrock units (1:600k)", "ni:ni_j600v_berg_2_jardlogMork_2utg_li": "Unit boundaries (1:600k)",
    "ni:ni_j600v_berg_2_brotalina_1utg_li": "Faults (1:600k)", "ni:ni_j600v_berg_2_gosspr_1utg_li": "Eruptive fissures (1:600k)",
    "ni:ni_j600v_berg_2_gigar_1utg_p": "Craters (1:600k)", "ni:ni_j600v_hoggun_eldstodvakerfi_li": "Volcanic systems (1:600k)",
    "ni:ni_j100v_vesturgosbelti_berggrunnur_1utg_fl": "Western Volcanic Zone bedrock (1:100k)",
    "ni:ni_j100v_vesturgosbelti_jardgrunnur_1utg_fl": "Western Volcanic Zone superficial deposits (1:100k)",
    "ni:ni_j100v_austurland_berggrunnur_1utg_fl": "East Iceland bedrock (1:100k)",
    # 뉴질랜드·남빅토리아랜드 (wetherilli 218)
    "gns:qmap": "QMAP geological map (1:250k)", "gns:NZL_GNS_1M_geological_units": "Geological units (1:1M)",
    "gns:NZL_GNS_1M_faults": "Faults (1:1M)", "gns:NZL_GNS_250K_faults": "Faults (1:250k)",
    "gns:NZL_GNS_250K_folds": "Fold axes (1:250k)", "gns:NZL_GNS_250K_metamorphic_zones": "Metamorphic zones (1:250k)",
    "gns:ATA_SVL_GNS_250K_geological_units": "Southern Victoria Land geological units (1:250k)",
    "gns:ATA_SVL_GNS_250K_faults": "Southern Victoria Land faults (1:250k)",
    # 몽골 (wetherilli 221)
    "mris:geology:1": "Geological map (National Geological Atlas)", "mris:faults:0": "Faults (1:500k)",
    # 인도 (wetherilli 226)
    "gsiindia:geology": "Geology (1:2M)", "gsiindia:faults": "Faults (1:2M)", "gsiindia:thrusts": "Thrusts (1:2M)",
    # 사우디아라비아 (wetherilli 227)
    "sgs:geology": "Geology (1:250k compilation)",
    # 동남아 (wetherilli 228)
    "admap:anomaly": "Magnetic anomaly",
    "bas:bedmap3_bed": "Bed topography", "bas:bedmap3_thickness": "Ice thickness", "bas:bedmap3_surface": "Ice surface",
    "usgscarib:geology": "Geology (1:2.5M)", "stri:geology": "Geology (1:250k)", "stri:faults": "Faults (1:250k)",
    "sim3534:units": "Geologic units",
    "sim3534:faults": "Faults",
    "vmme:geology": "Geology (overview)", "usgscarib:sa:geology": "Geology (USGS, public domain)",
    "georep:geology": "Geology (1:1M · 1:200k · 1:50k)",
    "brgm:GEOL_MART": "Martinique 1:50k (scan)", "brgm:GEOL_GUAD_ANNE": "Guadeloupe 1:50k (scan)",
    "brgm:GEOL_GUAD_MAR": "Saint-Martin · Saint-Barthélemy 1:50k (scan)",
    "brgm:GEOL_PYF_6S": "Geological scans — UTM 6S (Tahiti, western Tuamotu)",
    "brgm:GEOL_PYF_5S": "Geological scans — UTM 5S (Moorea, Leeward Islands, western Austral)",
    "brgm:GEOL_PYF_7S": "Geological scans — UTM 7S (Marquesas, eastern Tuamotu, Gambier)",
    "brgm:GEOL_REU_100K": "Réunion 1:100k (scan)", "brgm:GEOL_REU_50K": "Réunion 1:50k (scan)",
    "brgm:GEOL_MYT_30K": "Mayotte 1:30k (scan)", "brgm:GEOL_SPM_50K": "Saint-Pierre-et-Miquelon 1:50k (scan)",
    "ineter:geology": "Geology", "ineter:faults": "Faults", "igme:sgnrd:0": "Geological units (1:250k)",
    "igme:sgnrd:1": "Structures (1:250k)",
    "geosphere:geology": "Geology (1:1M)", "geosphere:faults": "Faults and nappe boundaries (1:1M)",
    "pig:mgp500k": "Geology (1:500k, 2022)", "pig:faults": "Faults (1:500k)",
    "geosphere:units50k": "Geological units (1:50k)", "pig:smgp50k": "Detailed geology (1:50k)",
    "pig:smgp50k_lines": "Boundaries and line symbols (1:50k)", "tno:geology": "Surface geology",
    "dov:tertiair_50k": "Tertiary geology (1:50k)", "dov:quartair_200k": "Quaternary profile-type map (1:200k)",
    "spw:geology": "Geology (1:25k compilation)", "spw:faults": "Faults",
    "bcgs:bedrock": "Bedrock (BC Digital Geology)", "calgs:geology": "Geologic map (1:750k)",
    "esdm:geology": "Geology (1:100k compilation 2018)", "jmg:lithology": "Lithology (by state)", "jmg:age": "Rock age (by state)",
    "mgb:geology": "Regional geology", "dmr:rock_units": "Rock units (1:250k)",
    # KIGAM 5만 단층·습곡·광종·변질대 (wetherilli 202)
    "kigam50k:fault": "Faults (1:50k)", "kigam50k:fold": "Folds (1:50k)",
    "kigam50k:zones": "Alteration and metamorphic zones (1:50k)", "kigam50k:oretype": "Ore commodities (1:50k)",
    # KIGAM 5만 구조 요소 (wetherilli 199). 열쇠는 레이어 이름이다
    "kigam50k:frame": "1:50k map sheet frames", "kigam50k:fossil": "Fossil localities (1:50k)",
    "kigam50k:sample": "Dating and geochemistry samples (1:50k)", "kigam50k:mine": "Mines (1:50k)",
    "kigam50k:lineation": "Lineations (1:50k)", "kigam50k:mineralarray": "Stretched minerals (1:50k)",
    "kigam50k:foldaxis": "Fold axes (1:50k)", "kigam50k:flowstructure": "Flow structures (1:50k)",
    # 지구 자료 점 (wetherilli 185) — 처음에 제목을 열쇠로 적어 영어판에 한국어가 나왔다(199 에서 이름으로 고쳤다)
    "earth:pbdb_korea": "Fossil collections (PBDB)", "earth:pbdb_antarctica": "Fossil collections (PBDB)", "earth:pbdb_arctic": "Fossil collections (PBDB)",
    "earth:gvp_korea": "Holocene volcanoes (GVP)", "earth:gvp_antarctica": "Holocene volcanoes (GVP)", "earth:gvp_arctic": "Holocene volcanoes (GVP)",
    "earth:recentquakes_korea": "Recent earthquakes (7 days, M2.5+)", "earth:recentquakes_antarctica": "Recent earthquakes (7 days, M2.5+)",
    "earth:recentquakes_arctic": "Recent earthquakes (7 days, M2.5+)",
    "earth:heatflow_korea": "Heat flow (IHFC)", "earth:heatflow_antarctica": "Heat flow (IHFC)", "earth:heatflow_arctic": "Heat flow (IHFC)",
    "earth:quakes_korea": "Earthquakes M5+ (USGS)", "earth:quakes_antarctica": "Earthquakes M5+ (USGS)", "earth:quakes_arctic": "Earthquakes M5+ (USGS)",
    "earth:neotoma_korea": "Quaternary paleoecology sites (Neotoma)", "earth:neotoma_antarctica": "Quaternary paleoecology sites (Neotoma)", "earth:neotoma_arctic": "Quaternary paleoecology sites (Neotoma)",
    # 국토지리원 주제 타일 (wetherilli 172)
    "gsitile:afm": "Active fault map (urban areas)",
    "gsitile:vlcd": "Volcanic land condition map",
    # VWorld 수질·지하수 측정망 (wetherilli 156)
    "lt_p_weissitema": "Water quality network — rivers",
    "lt_p_weissitemb": "Water quality network — lakes & reservoirs",
    "lt_p_weissitemd": "Water quality network — agricultural water",
    "lt_p_weissiteme": "Water quality network — industrial discharge",
    "lt_p_weissitemf": "Water quality network — urban streams",
    "lt_p_sgisgwchg": "Groundwater network — contamination-risk areas",
    # 영국·프랑스·유럽 (wetherilli 143)
    "bgs:BGS.50k.Bedrock": "Bedrock (1:50k)",
    "bgs:BGS.50k.Superficial.deposits": "Superficial deposits (1:50k)",
    "bgs:BGS.50k.Linear.features": "Linear features (1:50k)",
    "brgm:SCAN_F_GEOL1M": "Geological map 1:1M (scan)",
    "brgm:SCAN_F_GEOL250": "Geological map 1:250k (scan)",
    "brgm:SCAN_H_GEOL50": "Geological map 1:50k harmonised (scan)",
    "brgm:LITHO_1M_SIMPLIFIEE": "Simplified lithology (1:1M)",
    "egdi:GeologicUnitView_Age": "Surface geology — age",
    "egdi:GeologicUnitView_Lithology": "Surface geology — lithology",
    # 독일·스페인·아일랜드 (wetherilli 147)
    "bgr:gk1000:0": "Geological map (1:1M)", "bgr:gk2000:0": "Germany geology (1:2M, GK2000)", "bgr:gk2000:2": "Faults and thrusts (1:2M)", "bgr:gk2000:4": "Ice-margin positions (1:2M)",
    "bgr:guek250:7": "Stratigraphy (1:250k)",
    "bgr:guek250:4": "Lithology (1:250k)",
    "bgr:guek250:11": "Structural lines (1:250k)",
    "bgr:igme5000:37": "Geology — age, onshore (1:5M)",
    "bgr:igme5000:3": "Seafloor geology — age (1:5M)",
    "bgr:igme5000:43+44": "Metamorphic rocks (1:5M)",
    "bgr:igme5000:39": "Igneous rocks (1:5M)",
    "bgr:igme5000:41": "Ophiolite complexes (1:5M)",
    "bgr:igme5000:46+47+48": "Faults and geological boundaries (1:5M)",
    "bgr:igme5000:51+53+55+57": "Age symbols (1:5M)",
    "igme:geologico1m:0": "Lithology (1:1M)",
    "igme:magna50:0": "MAGNA lithology (1:50k)",
    "igme:magna50:2": "MAGNA contacts & faults (1:50k)",
    "gsi:1m:IE_GSI_GSNI_Bedrock_Geology_1M_IE32_ITM": "Bedrock (1:1M, whole island)",
    "gsi:1m:IE_GSI_GSNI_Faults_1M_IE32_ITM": "Faults (1:1M)",
    "gsi:100k:IE_GSI_Bedrock_Geology_100K_IE26_ITM": "Bedrock (1:100k, Republic)",
    "gsni:5": "Bedrock (1:250k, Northern Ireland)",
    # 남미 (wetherilli 188)
    "sgc:sa:8": "Chronostratigraphic units (1:5M)",
    "sgc:sa:10": "Faults (1:5M)",
    "sgc:sa:3": "Oceanic crust ages",
    "sgc:sa:31": "Plate boundaries",
    "sgc:sa:15": "Volcanoes",
    "sgc:sa:16": "Kimberlites",
    "sgc:sa:19": "Impact craters",
    "sgc:co:3": "Chronostratigraphic units (1:500k)",
    "sgc:co:60": "Faults (1:500k)",
    "sgc:co:61": "Folds (1:500k)",
    "sgc:co:66": "Volcanoes (Colombia)",
    "sgc:co:65": "Mud volcanoes",
    # 브라질 (wetherilli 191)
    "sgb:2500k": "Lithostratigraphic units (1:2.5M, 2025)",
    "sgb:2500k_structures": "Structures (1:2.5M, 2025)",
    "sgb:1m": "Lithostratigraphic units (1:1M)",
    "sgb:250k": "Lithostratigraphic units (1:250k, published sheets)",
    "sgb:outcrops": "Outcrops (close zooms only)",
    "sgb:geochronology": "Geochronology samples",
    "sgb:fossils": "Fossil occurrences",
    # 페루 (wetherilli 195)
    "ingemmet:50k": "Geological map 1:50k (integrated)",
    "ingemmet:50k_units": "Geological units only 1:50k (no faults or folds, from zoom 9)",
    "ingemmet:100k": "Geological map 1:100k (integrated)",
    "ingemmet:faults_1m": "Faults (1:1M)",
    "ingemmet:faults_100k": "Faults (1:100k)",
    "ingemmet:folds_100k": "Folds (1:100k)",
    "ingemmet:faults_50k": "Faults (1:50k)",
    "ingemmet:folds_50k": "Folds (1:50k)",
    # 아르헨티나·우루과이 (wetherilli 196)
    "segemar:e2.5M.UnidadesGeologicas": "Geological units (1:2.5M)",
    "segemar:e2.5M.Estructuras": "Structures (1:2.5M)",
    "segemar:e2.5M.VolcanesInventario": "Volcano inventory",
    "segemar:e250K_UnidadGeologica": "Geological units (1:250k sheets)",
    "segemar:e250K.Fallas": "Faults (1:250k sheets)",
    "gsq:state": "Queensland geology (1:2M)", "gsq:detailed": "Queensland detailed geology (1:100k)",
    "gsv:250k": "Victoria geology (1:250k, seamless)", "gsv:50k": "Victoria geology (1:50k, seamless)",
    "gssa:units": "South Australia geological units",
    "gsq:state_structure": "Queensland faults and folds (1:2M)", "gsq:faults": "Queensland faults and shear zones (1:100k)",
    "gsq:folds": "Queensland folds (1:100k)", "gssa:faults": "South Australia faults",
    "segemar:e1M.NOA.Geol": "Northwest — geological units (1:1M)",
    "segemar:e1M.NOA.Fallas": "Northwest — faults (1:1M)",
    "segemar:e1M.SH21.Geol": "Corrientes — geological units (1:1M, SH21)",
    "segemar:e1M.SH21.Fallas": "Corrientes — structures (1:1M, SH21)",
    "segemar:e750K.ProvChacoUGeol": "Chaco Province — geological units (1:750k)",
    "segemar:e750K.ProvChubutGeol": "Chubut Province — geological units (1:750k)",
    "segemar:e750K.ProvJujuyGeol": "Jujuy Province — geological units (1:750k)",
    "segemar:e750K.ProvMendozaGeol": "Mendoza Province — geological units (1:750k)",
    "segemar:e750K.ProvSantaFeGeol": "Santa Fe Province — geological units (1:750k)",
    "segemar:e750K.ProvTucumanGeol": "Tucumán Province — geological units (1:750k)",
    "segemar:e750K.ProvEstr": "Provincial structures (1:750k, six provinces)",
    "segemar:e500K.Front.ArCh.Geol": "Argentina–Chile border — geological units (1:500k)",
    "segemar:e500K.Front.ArCh.Fallas": "Argentina–Chile border — faults (1:500k)",
    "segemar:e250K.IslasMalvinasGeol": "Falkland Islands (Malvinas) — geological units (1:250k)",
    "segemar:e250K.IslasMalvinasFallas": "Falkland Islands (Malvinas) — faults (1:250k)",
    "segemar:DeformacionesCuaternarias_250K": "Quaternary deformation (faults & folds)",
    "segemar:e2.5M.VolcanesEvaluacionPeligrosidad": "Volcanic hazard (by volcano)",
    "dinamige:0": "Geological units (1:500k)",
    "dinamige:1": "Faults, contacts and lineaments (1:500k)",
    "dinamige:2": "Dykes (1:500k)",
    # 아프리카 (wetherilli 207)
    "cgmw:AFR_CGMW_BRGM_10M_GeologicUnits": "Geological units (1:10M)",
    "cgmw:AFR_CGMW_BRGM_10M_Faults": "Faults (1:10M)",
    "cgmw:AFR_CGMW_BRGM_10M_Oceanic_crust_domain": "Oceanic crust (1:10M)",
    "aga:geology": "Country lithology (1:5M, 38 countries)",
    # 아프리카 나라 판 (wetherilli 209)
    "cgs:geology_1m": "Geology (1:1M)",
    "gsn:NAM_GSN_1M_BLS": "Lithostratigraphy (1:1M)",
    "bumigeb:BFA_BUMIGEB_FR_1M_BLS": "Lithology (1:1M)", "bumigeb:BFA_BUMIGEB_FR_1M_MSF": "Major structures (1:1M)",
    "irgm:CMR_IRGM_1M_UnitesGeologiques": "Geological units (1:1M)", "irgm:CMR_IRGM_1M_Failles": "Faults (1:1M)",
    "gsn:NAM_GSN_1M_BA": "Age (1:1M)",
    "iige:geologia_general": "General geological map",
    # 미국 (wetherilli 205)
    "mrdata:sgmc2:sgmc2": "Geologic units (state map compilation)",
    "mrdata:sgmc2:sgmc2structure": "Structures (state map compilation)",
    "mrdata:sim3340:units": "Geologic units (Alaska 1:1.58M)",
    "mrdata:sim3340:faults": "Faults (Alaska 1:1.58M)",
    # 하와이·푸에르토리코 (wetherilli 238)
    "mrdata:hi:units": "Geologic units (Hawaii)", "mrdata:hi:faults": "Faults (Hawaii)", "mrdata:hi:dikes": "Dikes (Hawaii)",
    "mrdata:pr:geol": "Geologic units (Puerto Rico)", "mrdata:pr:fault": "Thrust faults (Puerto Rico)", "mrdata:pr:faultn": "Normal faults (Puerto Rico)",
    # USGS 의 다른 자료 (wetherilli 247)
    "mrdata:mrds:mrds": "Mineral resources (MRDS)", "mrdata:usmin:points": "Mine features — points (USMIN)",
    "mrdata:usmin:polygons": "Mine features — polygons (USMIN)", "mrdata:aeromag:namag": "Magnetic anomalies of North America (NAMAG)",
    "mrdata:gravity:isostatic": "Isostatic residual gravity anomaly", "mrdata:gravity:bouguer": "Bouguer gravity anomaly",
    "mrdata:geochron:geochron": "Geochronology (National Geochronological Database)",
    # 멕시코 (wetherilli 206)
    "sgm:8": "Lithology (1:250k)",
    # 호주 (wetherilli 212)
    "ga:lithostratigraphy": "Geologic units — lithostratigraphy",
    "ga:age": "Geologic units — age",
    "ga:lithology": "Geologic units — lithology",
    "ga:faults": "Faults",
    # GA 의 다른 서비스 (wetherilli 241)
    "ga:crustal": "Crustal elements", "ga:provinces": "Geological provinces (all)", "ga:mines": "Critical minerals mines",
    "ga:deposits": "Critical minerals deposits", "ga:tmi": "Total magnetic intensity (2019)",
    "ga:gravity": "Complete Bouguer gravity anomaly (2019)", "ga:radiometric": "Radiometric ternary (K·Th·U, 2019)",
    # 호주 확인 자원·수리지질도 (wetherilli 325)
    "ga:resource:Antimony": "Antimony",
    "ga:resource:Bauxite": "Bauxite",
    "ga:resource:BlackCoal": "Black coal",
    "ga:resource:BrownCoal": "Brown coal",
    "ga:resource:Cobalt": "Cobalt",
    "ga:resource:Copper": "Copper",
    "ga:resource:Diamond": "Diamond",
    "ga:resource:Fluorine": "Fluorine",
    "ga:resource:Gold": "Gold",
    "ga:resource:Graphite": "Graphite",
    "ga:resource:HighPurityAluminaOre": "High-purity alumina ore",
    "ga:resource:IronOre": "Iron ore",
    "ga:resource:LeadAndZinc": "Lead and zinc",
    "ga:resource:LithiumTantalumAndNiobium": "Lithium, tantalum and niobium",
    "ga:resource:Magnesite": "Magnesite",
    "ga:resource:ManganeseOre": "Manganese ore",
    "ga:resource:MineralSands": "Mineral sands",
    "ga:resource:Molybdenum": "Molybdenum",
    "ga:resource:Nickel": "Nickel",
    "ga:resource:Phosphate": "Phosphate",
    "ga:resource:PlatinumGroupElements": "Platinum-group elements",
    "ga:resource:Potash": "Potash",
    "ga:resource:RareEarthElements": "Rare-earth elements",
    "ga:resource:Scandium": "Scandium",
    "ga:resource:Silver": "Silver",
    "ga:resource:Tin": "Tin",
    "ga:resource:Tungsten": "Tungsten",
    "ga:resource:Uranium": "Uranium",
    "ga:resource:Vanadium": "Vanadium",
    "ga:hydrogeology": "Hydrogeology (1:5M)",
    "sgm:6": "Structures (1:250k)",
    "sgm:7": "Lithology (1:50k)",
    "sgm:5": "Structures (1:50k)",
    # 멕시코 SGM 의 다른 서비스 (wetherilli 219)
    "sgm:edades:0": "Geochronology samples", "sgm:paleo:0": "Fossil localities", "sgm:yac:0": "Mines and deposits (1:250k)",
    "sgm:yac:3": "Mineralized regions", "sgm:yac:2": "Mining districts",
    # 멕시코 지화학·광상 나머지 (wetherilli 233)
    "sgm:datos:7": "Magnetic field 1:250k (colour classes)",
    "sgm:geoq:0": "Stream-sediment geochemistry samples",
    "sgm:anom250:0": "Silver (Ag) anomalies (1:250k)", "sgm:anom250:1": "Cobalt (Co) anomalies (1:250k)", "sgm:anom250:2": "Copper (Cu) anomalies (1:250k)", "sgm:anom250:3": "Manganese (Mn) anomalies (1:250k)", "sgm:anom250:4": "Lead (Pb) anomalies (1:250k)", "sgm:anom250:5": "Zinc (Zn) anomalies (1:250k)",
    "sgm:anom50:0": "Silver (Ag) anomalies (1:50k)", "sgm:anom50:1": "Cobalt (Co) anomalies (1:50k)", "sgm:anom50:2": "Copper (Cu) anomalies (1:50k)", "sgm:anom50:3": "Manganese (Mn) anomalies (1:50k)", "sgm:anom50:4": "Lead (Pb) anomalies (1:50k)", "sgm:anom50:5": "Zinc (Zn) anomalies (1:50k)",
    "sgm:yac:1": "Alteration zones", "sgm:yac:4": "Non-metallic mineralized regions", "sgm:yac50:0": "Mines and deposits (1:50k)",
    # 스웨덴 기반암 (wetherilli 213)
    "sgu:bedrock": "Bedrock (1:1M · 1:50k–250k when zoomed in)",
    "sgu:deformation": "Deformation zones (1:1M)",
    # 노르웨이·핀란드 기반암 (wetherilli 140)
    "ngu:Berggrunn_nasjonal_bergartsenheter": "Rock units (1:1.35M)",
    # 노르웨이 광물·지구물리 (wetherilli 326)
    "ngu:metals": "Metal occurrences",
    "ngu:metal_provinces": "Metal provinces",
    "ngu:industrial": "Industrial mineral occurrences",
    "ngu:industrial_provinces": "Industrial mineral provinces",
    "ngu:critical_metals": "Critical metals (metal groups)",
    "ngu:magnetic": "Magnetic anomaly compilation",
    "ngu:gravity": "Gravity anomaly compilation",
    "ngu:density": "Rock density (mean)",
    "ngu:Berggrunn_regional_hovedbergarter": "Main rock types (1:250k)",
    "ngu:Berggrunn_lokal_bergartsenheter_fullzoom": "Rock units (1:50k)",
    "ngu:Berggrunn_regional_linjer_fullzoom": "Rock boundaries & structural lines (1:250k)",
    "gtk:kalliopera_1m_kivilajiseurueet": "Rock suites (1:1M)",
    "gtk:Litologiset_yksiköt_200k25132": "Lithological units (1:200k)",
    "gtk:kalliopera_1m_siirrosrakenteet": "Faults (1:1M)",
    # EMODnet 해저 지질 (wetherilli 135)
    "emodnet:cp_wp4_pre_quaternary_geology_lithology": "Pre-Quaternary geology — lithology",
    "emodnet:cp_wp4_pre_quaternary_geology_age": "Pre-Quaternary geology — age",
    "emodnet:bgr:pre_quaternary_faults": "Pre-Quaternary faults",
    "emodnet:cp_wp3_seabed_substrate_folk_7": "Seabed substrate (Folk 7)",
    # 유럽 바다 (wetherilli 176)
    "emodnet:bgr:quaternary_lithology": "Quaternary deposits — lithology",
    "emodnet:bgr:quaternary_age": "Quaternary deposits — age",
    "emodnet:cp_wp6_geological_event_distribution_250k": "Geological event distribution (coloured by submarine landslides)",
    "EASIA_CCOP_2M_Combined_BLT_SLT_BA": "CCOP 1:2M geology (bedrock, superficial, age)",
    # 대만 (wetherilli 136)
    "gsmma:geology_50k": "1:50k geological map",
    "gsmma:geology_250k": "1:250k geological map (1974)",
    "gsmma:geology_500k": "1:500k geological map (2000)",
    "gsmma:geology_1m": "1:1M geological map (1986)",
    "gsmma:labels_50k": "1:50k formation names",
    "gsmma:sheets_50k": "1:50k map sheets",
    "gsmma:active_faults": "Active faults (2021)",
    "gsmma:attitude_50k": "1:50k bedding attitude",
    "gsmma:tectonic_500k": "1:500k tectonic map (1978)",
    "gsmma:fossils_50k": "1:50k fossil localities",
    "gsmma:landslide_inventory": "Landslide inventory (2006–2013)",
    "gsmma:dip_slope": "Dip slopes (2013)",
    "gsmma:dip_slope_class": "Dip-slope rock sliding classes",
    "gsmma:rock_slide": "Rock-slide susceptibility (2013)",
    "gsmma:debris_slide": "Debris-slide susceptibility (2013)",
    "gsmma:liquefaction": "Soil liquefaction potential (2021)",
    "gsmma:sensitive_fault": "Active-fault sensitive areas",
    "gsmma:sensitive_landslide": "Landslide sensitive areas",
    "gsmma:sensitive_groundwater": "Groundwater recharge sensitive areas",
    "gsmma:sensitive_landscape": "Geoheritage sensitive areas",
    "gsmma:hot_springs": "Hot springs (2014)",
    "gsmma:boreholes": "Engineering geology boreholes",
    "gsmma:drainage_50k": "1:50k drainage-basin geology (2013)", "gsmma:drainage_labels_50k": "1:50k drainage-basin geology names",
    "gsmma:discontinuity_50k": "1:50k discontinuity attitudes", "gsmma:ore_50k": "1:50k ore deposits",
    "gsmma:ore_250k": "1:250k ore deposits (1974)",
    # 지질운 열린자료 (wetherilli 305)
    "gsmma:open:coal": "1:50k coal seams",
    "gsmma:open:debris": "Debris-flow deposition, fan and track zones",
    "gsmma:open:rockfall": "Rockfall",
    "gsmma:open:rockmass": "Rock mass strength classes",
    "gsmma:open:cgps": "Continuous GPS stations",
    "gsmma:hydro_wells": "Hydrogeological wells",
    "ibcso:tid": "Bathymetry data source (TID)",
    "L_1M_Geology_Map": "1:1M geology",
    "L_250K_Geology_Map": "1:250K geology",
    "L_50K_Geology_Map": "1:50K geology",
    "L_50K_Geology_Map_NoAttitude": "1:50K geology (without bedding etc.)",
    "l_50k_geology_frame_latest": "1:50K sheet index",
    "L_10k_coalfield_geologic_map": "1:10K coalfield geology",
    "L_25k_coalfield_geologic_map": "1:25K coalfield geology",
    "Bouguer_Gravity_Raster_2018": "Bouguer gravity anomaly",
    "Magnetic_Raster_2018": "Magnetic anomaly",
    "Isostatic_Gravity_Raster_2018": "Isostatic gravity anomaly",
    "L_geochemMP_CU": "Copper (Cu)",
    "L_geochemMP_PB": "Lead (Pb)",
    "L_geochemMP_NI": "Nickel (Ni)",
    "L_geochemMP_RB": "Rubidium (Rb)",
    "L_geochemMP_LI": "Lithium (Li)",
    "L_geochemMP_MGO": "Magnesium (MgO)",
    "L_geochemMP_MNO": "Manganese (MnO)",
    "L_geochemMP_V": "Vanadium (V)",
    "L_geochemMP_BA": "Barium (Ba)",
    "L_geochemMP_SW_PH": "Stream water pH",
    "L_geochemMP_SR": "Strontium (Sr)",
    "L_geochemMP_ZN": "Zinc (Zn)",
    "L_geochemMP_SW_EC": "Stream water conductivity",
    "L_geochemMP_ZR": "Zirconium (Zr)",
    "L_geochemMP_FE2O3": "Iron (Fe₂O₃)",
    "L_geochemMP_K2O": "Potassium (K₂O)",
    "L_geochemMP_CAO": "Calcium (CaO)",
    "L_geochemMP_CO": "Cobalt (Co)",
    "L_geochemMP_CR": "Chromium (Cr)",
    "L_geochemMP_TIO2": "Titanium (TiO₂)",
    "gw_loct_att": "Water source information",
    "good_water_rgb_th": "Groundwater — hardness",
    "good_water_rgb_si": "Groundwater — silicon",
    "good_water_rgb_na": "Groundwater — sodium",
    "good_water_rgb_mg": "Groundwater — magnesium",
    "good_water_rgb_f": "Groundwater — fluoride",
    "good_water_rgb_ph": "Groundwater — pH",
    "good_water_rgb_cl": "Groundwater — chloride",
    "good_water_rgb_ec": "Groundwater — conductivity",
    "good_water_rgb_hco3": "Groundwater — bicarbonate",
    "good_water_rgb_no3": "Groundwater — nitrate",
    "good_water_rgb_tds": "Groundwater — total dissolved solids",
    "good_water_rgb_k": "Groundwater — potassium",
    "good_water_rgb_ca": "Groundwater — calcium",
    "good_water_rgb_so4": "Groundwater — sulfate",
    "M_geology_sample_location": "Sampling locations",
    "M_geology_organic_carbon": "Organic carbon content",
    "M_geology_magnetic": "Magnetic properties",
    "M_geology_gravity": "Gravity properties",
    "M_geology_seismic_sections": "Seismic section interpretation",
    "Marine_geology_prospect": "Survey track lines",
    "M_geology_deposits_type": "Surface sediment types",
    "M_geology_deposits_mean_particle": "Surface sediment mean grain size",
    "M_geology_topography": "Seafloor topography",
    "M_geology_deposits_isopach": "Seafloor sediment isopach",
    "L_1M_isotope_ore": "Isotope ages — ore deposits",
    "L_1M_isotope_metamorphic": "Isotope ages — metamorphic rocks",
    "L_1M_isotope_plutonic": "Isotope ages — plutonic rocks",
    "L_1M_isotope_volcanic": "Isotope ages — volcanic rocks",
    "medical_clay": "Medical clay",
    "G_tectonic": "Tectonic map",
    "outcrop_korea": "Geological outcrops of Korea",
    # 지질 참고 (VWorld)
    "lt_l_gimsfault": "Faults",
    "lt_l_gimslinea": "Geological lineaments",
    "lt_c_gimshydro": "Hydrogeologic units",
    "lt_l_gimspoten": "Groundwater level contours",
    "lt_l_gimsec": "Groundwater electrical conductivity",
    "lt_l_gimsdepth": "Groundwater depth contours",
    "lt_c_uj401": "Hot spring zones",
    "lt_l_frstclimb": "Hiking trails",
    "lt_p_nsnmssitenm": "National place names",
    "lt_c_wkmstrm": "Stream network",
    "lt_c_adsido": "Boundaries — provinces",
    "lt_c_adsigg": "Boundaries — cities & counties",
    "lt_c_ademd": "Boundaries — towns & townships",
    "lt_c_adri": "Boundaries — villages (ri)",
    "lt_c_wkmbbsn": "Basins — major",
    "lt_c_wkmmbsn": "Basins — mid-size",
    "lt_c_wkmsbsn": "Basins — standard",
    "lt_c_uo301": "National heritage designated & protected areas",
    "lt_c_wgisnpgug": "National parks",
    "lt_c_wgisnpdo": "Provincial parks",
    "lt_c_wgisnpgun": "County parks",
    "lt_c_uf901": "Baekdudaegan protected area",
    "lt_c_uf151": "Forest protection areas",
    "lt_c_uq114": "Natural environment conservation areas",
    "lt_c_um221": "Wildlife protection areas",
    "lt_c_wgisarwet": "Wetland protected areas",
    "lt_c_tfismpa": "Marine protected areas",
    "lt_c_um710": "Water source protection areas",
    "lt_c_asitsoildep": "Effective soil depth",
    "lt_c_asitsurston": "Gravel content",
    "lt_c_asitdeepsoil": "Subsoil texture",
    "lt_c_asitsoildra": "Soil drainage class",
    "lt_c_fsdifrsts": "Forest site map",
    "lt_c_up401": "Steep-slope collapse hazard areas",
    "lt_c_up201": "Natural disaster hazard districts",
    "lt_c_aisprhc": "Prohibited airspace",
    "lt_c_aisresc": "Restricted airspace",
    "lt_c_aisdngc": "Danger areas (airspace)",
    "lt_c_aisctrc": "Control zones",
    "lt_c_aisuac": "Ultralight vehicle airspace",
    # 그린란드 (GEUS)
    "grl_g500_lithostr_search": "1:500K geology (lithostratigraphy)",
    "lithologies": "Field lithology observations",
    "geochemistry_greenland_v2_external": "Stream sediment geochemistry",
    "geochemistry_greenland_ss_sw": "Stream sediment atlas — South & West",
    "geochemistry_greenland_ss_n": "Stream sediment atlas — North",
    "geochemistry_greenland_soil": "Soil geochemistry",
    "seismic_surveys_grl": "Seismic survey areas",
    "seismic_lines_grl": "Seismic lines",
    "seismic_3d_surveys_grl": "3D seismic surveys",
    "seismic_csem_grl": "CSEM lines",
    # 그린란드 정부 포털 (grportal.py)
    "grportal:geochron": "Geochronology",
    "grportal:mineral_occurrences": "Mineral occurrences",
    "grportal:intrusions": "Intrusions",
    "grportal:samples": "Rock & sediment samples",
    "grportal:mineral_tracts": "Mineral potential tracts",
    "grportal:diamond_occurrences": "Diamond-related occurrences (kimberlite etc.)",
    "grportal:diamond_drillholes": "Diamond exploration drill holes",
    "grportal:diamond_indicators": "Indicator mineral concentration (grains/kg)",
    "grportal:diamond_per_kg": "Diamond concentration (stones/kg)",
    "grportal:garnet_classes": "Garnet classes (G10·G9)",
    "grportal:diamond_explored": "Diamond exploration — explored",
    "grportal:diamond_unexplored": "Diamond exploration — unexplored",
    "grportal:cpx_classes": "Clinopyroxene classes",
    "grportal:ilm_classes": "Ilmenite classes",
    "grportal:spinel_classes": "Spinel classes",
    "grportal:opx_classes": "Orthopyroxene classes",
    "grportal:diamond_macro": "Macrodiamonds recovered",
    "grportal:diamond_micro": "Microdiamonds recovered",
    "grportal:diamond_ages": "Emplacement ages of occurrences",
    "grportal:diamond_bodies": "Occurrence bodies",
    "grportal:diamond_dykes": "Occurrence dykes",
    "grportal:diamond_inferred": "Inferred dykes",
    "grportal:unstable_slopes": "Unstable slopes",
    "grportal:mass_movements": "Registered mass movements",
    "grportal:geochem_soil": "Soil geochemistry",
    "grportal:geochem_heavy": "Heavy-mineral concentrate geochemistry",
    "grportal:geochem_companies": "Company exploration geochemistry",
    "grportal:geochem_scree": "Scree geochemistry",
    "grportal:whole_rock": "Whole-rock chemistry",
    # 남극 (SCAR GeoMAP)
    "geomap_simple_geology": "Geology (simplified)",
    "geomap_chronostratigraphic": "Chronostratigraphy",
    "geomap_simple_lithology": "Lithology (simplified)",
    "geomap_lithostratigraphic": "Lithostratigraphy",
    "geomap_faults": "Faults",
    "geomap_quality": "Data quality",
    # 얀마옌 (NPI 지질도, janmayen.py)
    "janmayen:units": "Geological units (1:250K)",
    "janmayen:lines": "Eruptive fissures, lava fronts & caldera",
    "janmayen:vents": "Eruptive centres & fumaroles",
    # 노르웨이 극지연구소 — 스발바르·드로닝모드랜드 (npolar.py)
    "npolar:svalbard_units": "Geological units (1:250K · 1:750K)",
    "npolar:svalbard_faults": "Faults & folds",
    "npolar:svalbard_paper": "Printed geological map (hillshade)",
    "npolar:svalbard_sheets": "Map sheet scans (1:100 000 etc., all)",
    "npolar:svalbard_sheet_index": "Map sheet index",
    "npolar:svalbard_type_localities": "Lithostratigraphic type localities",
    "npolar:svalbard_glacier_fronts": "Glacier fronts 1936–2025",
    "npolar:rock_archive": "Rock sample archive",
    "npolar:dml_units": "Geological units (1:250K · 1:5M)",
    "npolar:dml_structures": "Structures",
    "npolar:dml_tectonic": "Major tectonic boundaries",
    "npolar:dml_geochron": "Geochronology",
    "npolar:dml_samples": "Rock sample archive (Antarctica)",
    "npolar:dml_sites": "Field sites",
    # 일본 — GSJ 심리스 지질도 V2 (gsj.py)
    "gsj:geology": "1:200K seamless geology",
    "gsj:geology_level2": "1:200K seamless geology — simplified (14 classes)",
    "gsj:boundaries": "Geological boundaries",
    "gsj:faults": "Faults & flexures",
    "gsj:symbols": "Legend symbols",
    # 중국 — USGS geo3al (geo3al.py)
    "geo3al:age": "Geologic age (1:5M)",
    "geo3al:rock": "Igneous rocks & eolian deposits",
    # 연구실의 암맥 기록 — phyloserver (devlog 026)
    "phyloserver:dikes": "Dike records",
    "phyloserver:peninsula": "Korean Peninsula geology (scan)",
    # 한반도 지질도 음영판·민판 (devlog 027·028)
    "peninsula:shaded": "Korean Peninsula geology (shaded relief)",
    "peninsula:plain": "Korean Peninsula geology (no relief)",
    "kopri:rock_antarctica": "Rock samples (KOPRI)",
    "kopri:rock_svalbard": "Rock samples (KOPRI)",
    "kopri:rock_greenland": "Rock samples (KOPRI)",
    "kopri:meteorites": "Meteorite finds (KoreaMet)",
    "kopri:araon_antarctica": "Araon track",
    "kopri:araon_arctic_ocean": "Araon track",
    "kopri:kpdc_sediment": "Marine sediments & cores",
    "kopri:kpdc_solid": "Solid Earth",
    "kopri:kpdc_paleo": "Paleoclimate",
    "kopri:kpdc_cryo": "Cryosphere",
    "kopri:kpdc_ocean": "Oceans",
    "kopri:kpdc_atmo": "Atmosphere",
    "kopri:kpdc_bio": "Biosphere",
    "kopri:kpdc_other": "Other topics",
    # KPDC 자료 — 스발바르·그린란드 (075)
    "kopri:kpdc_sediment_svalbard": "Marine sediments & cores",
    "kopri:kpdc_paleo_svalbard": "Paleoclimate",
    "kopri:kpdc_ocean_svalbard": "Oceans",
    "kopri:kpdc_atmo_svalbard": "Atmosphere",
    "kopri:kpdc_bio_svalbard": "Biosphere",
    "kopri:kpdc_other_svalbard": "Other topics",
    "kopri:kpdc_paleo_greenland": "Paleoclimate",
    "kopri:kpdc_cryo_greenland": "Cryosphere",
    "kopri:kpdc_ocean_greenland": "Oceans",
    "kopri:kpdc_atmo_greenland": "Atmosphere",
    "kopri:kpdc_bio_greenland": "Biosphere",
    "kopri:kpdc_other_greenland": "Other topics",
    "kopri:kpdc_sediment_arctic_ocean": "Marine sediments & cores",
    "kopri:kpdc_solid_arctic_ocean": "Solid Earth",
    "kopri:kpdc_paleo_arctic_ocean": "Paleoclimate",
    "kopri:kpdc_cryo_arctic_ocean": "Cryosphere",
    "kopri:kpdc_ocean_arctic_ocean": "Oceans",
    "kopri:kpdc_atmo_arctic_ocean": "Atmosphere",
    "kopri:kpdc_bio_arctic_ocean": "Biosphere",
    "kopri:kpdc_other_arctic_ocean": "Other topics",
    "kopri:stations": "Antarctic stations (COMNAP)",
    "kopri:coast_change": "Coastline change (Antarctic Peninsula)",
    "kopri:lakes": "Lakes",
    "kopri:streams": "Streams (Antarctic Peninsula)",
    "kopri:moraines": "Moraines",
    "pgc:greenland_slope": "Slope",
    "pgc:greenland_contours": "Contours (25 m)",
    "pgc:svalbard_slope": "Slope",
    "pgc:svalbard_contours": "Contours (25 m)",
    "pgc:antarctica_slope": "Slope",
    "pgc:antarctica_contours": "Contours (25 m)",
    "kopri:rock_outcrops": "Rock outcrops",
    "kopri:contours": "Contours",
    "kopri:historic": "Historic sites & monuments (HSM)",
    "kopri:arctic_depth_contours": "Arctic Ocean depth contours",
    "kopri:greenland_ice_contours": "Ice sheet contours",
}

#: 레이어 설명(`abstract`)의 영어 — 이름으로 찾는다. 한국어가 든 설명만 적는다(wetherilli 333). 원어 제목(독일어·프랑스어·일본어 …)은 그대로 두고
#: 한국어로 적은 덧말만 옮겼다. 표에 없고 한국어가 든 설명은 영어판에서 숨긴다(`views._catalog`). `manage.py i18n_missing` 이 빠진 것을 센다
ABSTRACT_EN = {
    "admap:anomaly": "Magnetic anomaly (nT) joining airborne and marine magnetic surveys of Antarctica — 1.5 km grid. Red is positive, blue negative. Click for the nT value there",
    "ags:minocc": "Mineral Occurrences — metallic minerals (DIG 2019-0026), industrial minerals (DIG 2019-0027), lithium, silica sand, producers and mineral cores; 5,454 points",
    "bas:bedmap3_bed": "Height of the bedrock and seabed with the ice removed (relative to sea level) — Bedmap3 500 m grid, 2025",
    "bas:bedmap3_surface": "Height of the ice-sheet surface — Bedmap3 500 m grid, 2025",
    "bas:bedmap3_thickness": "Thickness of the ice sheet and ice shelves — Bedmap3 500 m grid, 2025",
    "bcgs:bedrock": "GEOL_BEDROCK_UNIT_POLY_SVW — compiled 1:50k–1:250k. From zoom 5; wider than 1:500k we send our own condensed style",
    "bcgs:minfile": "MINFILE — 16,261 sites (OGL–BC)",
    "bgr:gk1000:0": "GK1000 — Geologische Schichten. Zoom 9–10",
    "bgr:gk2000:0": "Geowissenschaftliche Karte 1:2.000.000 — Stratigraphie, 30 units. From the widest zoom to zoom 10",
    "bgr:gk2000:4": "GK2000 — Eisrandlagen (Weichselian, Saalian and Elsterian glaciations)",
    "bgr:guek250:11": "GÜK250 — Tektonik: faults and similar. Zoom 10–14",
    "bgr:guek250:4": "GÜK250 — Basislayer Petrographie. Zoom 10–14",
    "bgr:guek250:7": "GÜK250 — Basislayer Stratigraphie. Surface geology down to 2 m depth, by age. Zoom 10–14",
    "bgr:igme5000:3": "IGME5000 offshore — age (chronostratigraphic). Continental shelves and ocean floor",
    "bgr:igme5000:37": "IGME5000 onshore — age (chronostratigraphic). Age colours with lithological, metamorphic and igneous attributes. Up to zoom 11",
    "bgr:igme5000:43+44": "IGME5000 onshore — metamorphic rocks. Joins the two layers the upstream splits by scale (above and below 1:5M)",
    "bgr:igme5000:46+47+48": "IGME5000 onshore — faults. Joins the three layers split by scale",
    "bgr:igme5000:51+53+55+57": "IGME5000 onshore — text symbol (age). Joins the four layers split by scale",
    "bgs:BGS.50k.Bedrock": "GBR BGS 1:50k Bedrock — strata, rocks and ages. Drawn from zoom 13",
    "bgs:BGS.50k.Linear.features": "GBR BGS 1:50k Linear features — faults, coal seams, marine bands and similar. From zoom 13",
    "bgs:BGS.50k.Superficial.deposits": "GBR BGS 1:50k Superficial deposits — glacial deposits, alluvium and similar. From zoom 13",
    "bgsgi:gbase_streamsed": "Stream sediment samples — from zoom 12",
    "bgsgi:gravity": "BGS Gravity anomalies colour shaded (1:625 000; Bouguer on land, free-air at sea) — up to zoom 9",
    "bgsgi:hydrogeology": "Hydrogeology 625k — aquifer productivity",
    "bgsgi:magnetic": "BGS Magnetic anomalies colour shaded (1:625 000) — up to zoom 9",
    "bgsgi:mines": "Mines and quarries — from zoom 10",
    "brgm:GEOL_GUAD_ANNE": "Cartes géologiques Guadeloupe (Sainte-Anne) — from zoom 12",
    "brgm:GEOL_GUAD_MAR": "Cartes géologiques Guadeloupe (Marigot) — from zoom 12",
    "brgm:GEOL_MART": "Carte géologique Martinique 1/50 000 — from zoom 12",
    "brgm:GEOL_MYT_30K": "Carte géologique Mayotte 1/30 000 — from zoom 13",
    "brgm:GEOL_PYF_5S": "Cartes géologiques Polynésie (5 Sud) — 158°–149.7° W, from zoom 11",
    "brgm:GEOL_PYF_6S": "Cartes géologiques Polynésie (6 Sud) — 150°–143.5° W, from zoom 11",
    "brgm:GEOL_PYF_7S": "Cartes géologiques Polynésie (7 Sud) — 144°–137.5° W, from zoom 11",
    "brgm:GEOL_REU_100K": "Carte géologique Réunion 1/100 000 — zoom 11–12",
    "brgm:GEOL_REU_50K": "Carte géologique Réunion 1/50 000 — from zoom 13",
    "brgm:GEOL_SPM_50K": "Carte géologique Saint-Pierre-et-Miquelon 1/50 000 — from zoom 12",
    "brgm:GITES_PT": "Gisements, gîtes, indices — points",
    "brgm:LITHO_1M_SIMPLIFIEE": "Carte lithologique simplifiée au 1/1 000 000 — click for the lithology. Zoom 6–14",
    "brgm:SCAN_F_GEOL1M": "Carte géologique image de la France au million — zoom 6–11",
    "brgm:SCAN_F_GEOL250": "Carte géologique image de la France au 1/250 000 — zoom 11–12",
    "brgm:SCAN_H_GEOL50": "Carte géologique 50 000e — harmonisé. Sheets joined into one map, from zoom 12",
    "calgs:geology": "Geologic Map of California 2010 — rock-type areas, contacts and faults in one image (the upstream ignores layer selection). Enlarged beyond zoom 12",
    "cgs:coal": "Main Coal resource areas (CGS) — 86 areas",
    "cgs:mining_areas": "Main Mining areas — 8 areas (new, declining and producing mining)",
    "cgs:uranium": "Uranium areas (CGS) — 19 areas",
    "dggs:minerals": "Alaska Minerals Database — 335 sites, coloured by development stage",
    "dmr:critical": "ตำแหน่งแร่ที่มีความสำคัญ (MINERAL/CRITICAL_MINERAL) — 249 sites",
    "dmr:min_occ": "จุดพบแร่ (MINERAL/MIN_OCC) — 5,597 sites",
    "dogami:ogdc": "Oregon Geologic Data Compilation, release 6 — from zoom 7",
    "egdi:GeologicUnitView_Age": "EGDI 1:1M Surface Geologic Units Age — 1:1M surface geology of many European countries, coloured by age",
    "emodnet:bgr:pre_quaternary_faults": "Faults in the seabed bedrock. On the Norwegian side this is NGU's Nordic 1:4M geological map",
    "emodnet:bgr:quaternary_age": "The same areas coloured by geological age — divided down to glacial units such as the Weichselian and the Holocene",
    "emodnet:bgr:quaternary_lithology": "Lithology of the Quaternary (since 2.58 Ma) strata below the seabed surface. BGR joined each country's seabed Quaternary maps — around Britain it is BGS's 1:1M edition",
    "emodnet:cp_wp3_seabed_substrate_folk_7": "Grain size of seabed surface sediments — mud, sand, gravel and mixtures in Folk's seven classes. The upstream picks a more detailed edition as you zoom in",
    "emodnet:cp_wp4_pre_quaternary_geology_age": "The same areas coloured by geological age",
    "emodnet:cp_wp4_pre_quaternary_geology_lithology": "Lithology of the bedrock below the seabed (beneath the Quaternary). EMODnet joined each country's seabed geological maps — the Barents Sea is BGR's European 1:5M map",
    "emodnet:cp_wp6_geological_event_distribution_250k": "An index map dividing the sea into cells, marking each event as reported, absent or no data. Colour shows submarine landslides only — click to see all five for that cell: submarine landslides, volcanoes, Quaternary tectonics, tsunamis and fluid seepage",
    "esdm:geology": "Peta Geologi — GEOLOGIINDONESIA_AR_100K_2018. Drawn only up to zoom 10 (upstream maxScale 1:577,790)",
    "esdm:metal": "Potensi Sumber Daya dan Cadangan Mineral Logam — 3,214 sites",
    "esdm:nonmetal": "Potensi Mineral Bukan Logam dan Batuan — 6,738 sites",
    "ga:provinces": "Australian Geological Provinces — AllProvinces. Overlapping provinces drawn as outlines",
    "geomap_chronostratigraphic": "GeoMAP geological units coloured by age (MAPSYMBOL) — GNS's Chronostratigraphic style",
    "geomap_faults": "GeoMAP's 1,784 faults — line style varies with exposure and positional accuracy (GNS's Mapped faults style)",
    "geomap_lithostratigraphic": "GeoMAP geological units coloured by rock type per age (MAPSYMBOL), keeping GNS's hatch and dot patterns (GNS's Lithostratigraphic style)",
    "geomap_quality": "Data quality 1–5 assigned by GNS to each cell of 1° longitude × 30′ latitude",
    "geomap_simple_geology": "GeoMAP geological units coloured by the 21 SIMPCODE classes (GNS's Simple geology style)",
    "geomap_simple_lithology": "GeoMAP geological units coloured by lithology (LITHCODE) (GNS's Simple lithology style)",
    "georep:geology": "Géologie de la Nouvelle-Calédonie — 1:1M when wider than 1:300k, 1:200k down to 1:100k, 1:50k closer in (under revision)",
    "geosphere:geology": "geologie_1m 0·1 — basement and post-Middle-Eocene basins. Enlarged beyond zoom 11",
    "geosphere:units50k": "geologie/einheiten_50 — the 1:50k sheets joined as GeoSciML-Lite. No WMS, so REST export. From zoom 11, only where sheets are published",
    "geusarc:aem": "Magnetics from ten AEM surveys — Inglefield, Maniitsoq–Nuuk, Jameson Land and others",
    "geusarc:aeromag": "GEUS AEROMAG total magnetic field — surveyed areas only",
    "geusarc:aeromag_tilt": "AEROMAG tilt derivative — structures stand out",
    "geusarc:awi": "AWI East Greenland airborne magnetics — 300–600 nT colour scale",
    "geusarc:bouguer": "DTU Space Bouguer anomaly — observation points left out",
    "geusarc:g100k_karrat": "Karrat 1:100 000 — geology, contacts and structures",
    "geusarc:g100k_ssw": "South-West Greenland 1:100 000 — geology, contacts and structures",
    "geusarc:g2500k": "Geological map of Greenland 1:2 500 000 — geology, contacts and structures",
    "geusarc:magnetic": "GEUS Magnetic compilation — flight lines left out",
    "geusarc:provinces": "Geological provinces 2500k — Quaternary, sedimentary basins, supracrustals, igneous provinces and Precambrian basement",
    "gns:ATA_SVL_GNS_250K_geological_units": "ATA SVL GNS 1:250K geological units — McMurdo Dry Valleys and around Ross Island",
    "gns:NZL_GNS_1M_geological_units": "Geological Map of New Zealand 1:1 000 000 (GMNZ 2014) — the base for wide views",
    "gns:NZL_GNS_250K_faults": "NZL GNS 1:250K faults. From zoom 7",
    "gns:NZL_GNS_250K_folds": "NZL GNS 1:250K fold axes. From zoom 8",
    "gns:NZL_GNS_250K_metamorphic_zones": "NZL GNS 1:250K metamorphic zones. From zoom 7",
    "gns:gravity": "NZ Gravity Anomaly — from the full GNS service (/gns/wms)",
    "gns:qmap": "NZL_GNS_250K_seamless_qmap_geological_map_current_view — the 21 QMAP sheets combined (2023 edition), faults and contacts in one image. From zoom 7",
    "grportal:cpx_classes": "Diamond Exploration Database (DED) — clinopyroxene grain chemistry classes (CPX_CGP, CPX_CPP) counted per sample, 2,824 sites. Colour of the most common class",
    "grportal:diamond_ages": "Diamond Exploration Database (DED) — 56 intrusion ages of kimberlite and other occurrences (150–3,007 Ma), with method and reference",
    "grportal:diamond_bodies": "Diamond Exploration Database (DED) — 32 mapped intrusive bodies",
    "grportal:diamond_drillholes": "Diamond Exploration Database (DED) — 202 drillholes: whether kimberlite was hit, anomaly, length, lithology",
    "grportal:diamond_dykes": "Diamond Exploration Database (DED) — 239 confirmed dykes (137 kimberlite)",
    "grportal:diamond_explored": "Diamond Exploration Database (DED) — areas around collected samples",
    "grportal:diamond_indicators": "Diamond Exploration Database (DED) — indicator mineral grains per 1 kg of sample, 1,048 sites",
    "grportal:diamond_inferred": "Diamond Exploration Database (DED) — 144 inferred dykes",
    "grportal:diamond_macro": "Diamond Exploration Database (DED) — number of macrodiamonds recovered from samples, 49 sites",
    "grportal:diamond_micro": "Diamond Exploration Database (DED) — number of microdiamonds recovered from samples, 163 sites",
    "grportal:diamond_occurrences": "Diamond Exploration Database (DED) — 3,029 occurrences: rock group, mode of occurrence, strike and dip, description",
    "grportal:diamond_per_kg": "Diamond Exploration Database (DED) — diamonds per 1 kg of sample, 178 sites",
    "grportal:diamond_unexplored": "Diamond Exploration Database (DED) — areas that could host diamonds but have not been explored",
    "grportal:garnet_classes": "Diamond Exploration Database (DED) — garnet grain chemistry classes (G1–G12) counted per sample, 2,468 sites. G10 indicates diamond",
    "grportal:geochem_companies": "971 samples submitted by exploration companies (around Disko Island) — pick an element to colour by value quantiles",
    "grportal:geochem_heavy": "GEUS heavy-mineral concentrate samples, 1,211 — pick an element to colour by value quantiles",
    "grportal:geochem_scree": "GEUS scree (talus) samples, 49 — pick an element to colour by value quantiles",
    "grportal:geochem_soil": "GEUS soil samples, 2,096 — major oxides and about 60 trace elements. Pick an element to colour by value quantiles",
    "grportal:ilm_classes": "Diamond Exploration Database (DED) — ilmenite grain chemistry classes (ILM_KIM, ILM_INTER), 2,933 sites",
    "grportal:mass_movements": "42 recorded landslides and rock avalanches — when, volume, whether they caused a tsunami. Refreshed every 30 days",
    "grportal:mineral_tracts": "162 permissive tracts drawn by the GEUS–Government of Greenland commodity assessment workshops (2009–2014) — deposit model, number of undiscovered deposits by probability, reports",
    "grportal:opx_classes": "Diamond Exploration Database (DED) — orthopyroxene grain chemistry classes (OPX_OGM, OGP, ODH, ODL), 154 sites",
    "grportal:spinel_classes": "Diamond Exploration Database (DED) — spinel grain chemistry classes (SP_CID, SP_GT_PER, unclassified), 2,790 sites",
    "grportal:unstable_slopes": "Map being compiled by the Government of Greenland geology section (updated 2026-02) — volume, height, run-out, nearest settlement. Refreshed every 30 days",
    "grportal:whole_rock": "GEUS whole-rock analyses of rock samples, 31,769 — pick an element; only points analysed for it are fetched and coloured by value quantiles. No attributes besides the sample number",
    "gsi:100k:IE_GSI_Bedrock_Geology_100K_IE26_ITM": "IE GSI Bedrock Geology 1:100k — Republic only. Zoom 6–14",
    "gsi:1m:IE_GSI_GSNI_Bedrock_Geology_1M_IE32_ITM": "IE GSI GSNI Bedrock Geology 1:1M — the Republic and Northern Ireland joined",
    "gsiindia:geology": "Geological Map of India 1:2M — image from BGS's OneGeology WMS (IND_GSI_2M_Geology), attributes from GSI's feature service",
    "gsitile:afm": "活断層図 (都市圏活断層図) — active faults and fault-displaced landforms around urban areas. Zoom 3–16. The map includes its own terrain base, so lower its opacity over geological maps",
    "gsitile:vlcd": "火山土地条件図 — lava flows, pyroclastic flows, craters and other volcanic landforms around active volcanoes. Zoom 5–16. The map includes its own terrain base, so lower its opacity over geological maps",
    "gsjows:geochem:Al2O3": "日本の地球化学図 — Al2O3 (stream sediments)",
    "gsjows:geochem:As": "日本の地球化学図 — As (stream sediments)",
    "gsjows:geochem:Ba": "日本の地球化学図 — Ba (stream sediments)",
    "gsjows:geochem:Be": "日本の地球化学図 — Be (stream sediments)",
    "gsjows:geochem:Bi": "日本の地球化学図 — Bi (stream sediments)",
    "gsjows:geochem:CaO": "日本の地球化学図 — CaO (stream sediments)",
    "gsjows:geochem:Cd": "日本の地球化学図 — Cd (stream sediments)",
    "gsjows:geochem:Ce": "日本の地球化学図 — Ce (stream sediments)",
    "gsjows:geochem:Co": "日本の地球化学図 — Co (stream sediments)",
    "gsjows:geochem:Cr": "日本の地球化学図 — Cr (stream sediments)",
    "gsjows:geochem:Cs": "日本の地球化学図 — Cs (stream sediments)",
    "gsjows:geochem:Cu": "日本の地球化学図 — Cu (stream sediments)",
    "gsjows:geochem:Dy": "日本の地球化学図 — Dy (stream sediments)",
    "gsjows:geochem:Er": "日本の地球化学図 — Er (stream sediments)",
    "gsjows:geochem:Eu": "日本の地球化学図 — Eu (stream sediments)",
    "gsjows:geochem:Fe2O3": "日本の地球化学図 — Fe2O3 (stream sediments)",
    "gsjows:geochem:Ga": "日本の地球化学図 — Ga (stream sediments)",
    "gsjows:geochem:Gd": "日本の地球化学図 — Gd (stream sediments)",
    "gsjows:geochem:Hf": "日本の地球化学図 — Hf (stream sediments)",
    "gsjows:geochem:Hg": "日本の地球化学図 — Hg (stream sediments)",
    "gsjows:geochem:Ho": "日本の地球化学図 — Ho (stream sediments)",
    "gsjows:geochem:K2O": "日本の地球化学図 — K2O (stream sediments)",
    "gsjows:geochem:La": "日本の地球化学図 — La (stream sediments)",
    "gsjows:geochem:Li": "日本の地球化学図 — Li (stream sediments)",
    "gsjows:geochem:Lu": "日本の地球化学図 — Lu (stream sediments)",
    "gsjows:geochem:MgO": "日本の地球化学図 — MgO (stream sediments)",
    "gsjows:geochem:MnO": "日本の地球化学図 — MnO (stream sediments)",
    "gsjows:geochem:Mo": "日本の地球化学図 — Mo (stream sediments)",
    "gsjows:geochem:Na2O": "日本の地球化学図 — Na2O (stream sediments)",
    "gsjows:geochem:Nb": "日本の地球化学図 — Nb (stream sediments)",
    "gsjows:geochem:Nd": "日本の地球化学図 — Nd (stream sediments)",
    "gsjows:geochem:Ni": "日本の地球化学図 — Ni (stream sediments)",
    "gsjows:geochem:P2O5": "日本の地球化学図 — P2O5 (stream sediments)",
    "gsjows:geochem:Pb": "日本の地球化学図 — Pb (stream sediments)",
    "gsjows:geochem:Pr": "日本の地球化学図 — Pr (stream sediments)",
    "gsjows:geochem:Rb": "日本の地球化学図 — Rb (stream sediments)",
    "gsjows:geochem:Sb": "日本の地球化学図 — Sb (stream sediments)",
    "gsjows:geochem:Sc": "日本の地球化学図 — Sc (stream sediments)",
    "gsjows:geochem:Sm": "日本の地球化学図 — Sm (stream sediments)",
    "gsjows:geochem:Sn": "日本の地球化学図 — Sn (stream sediments)",
    "gsjows:geochem:Sr": "日本の地球化学図 — Sr (stream sediments)",
    "gsjows:geochem:Ta": "日本の地球化学図 — Ta (stream sediments)",
    "gsjows:geochem:Tb": "日本の地球化学図 — Tb (stream sediments)",
    "gsjows:geochem:Th": "日本の地球化学図 — Th (stream sediments)",
    "gsjows:geochem:TiO2": "日本の地球化学図 — TiO2 (stream sediments)",
    "gsjows:geochem:Tl": "日本の地球化学図 — Tl (stream sediments)",
    "gsjows:geochem:Tm": "日本の地球化学図 — Tm (stream sediments)",
    "gsjows:geochem:U": "日本の地球化学図 — U (stream sediments)",
    "gsjows:geochem:V": "日本の地球化学図 — V (stream sediments)",
    "gsjows:geochem:Y": "日本の地球化学図 — Y (stream sediments)",
    "gsjows:geochem:Yb": "日本の地球化学図 — Yb (stream sediments)",
    "gsjows:geochem:Zn": "日本の地球化学図 — Zn (stream sediments)",
    "gsjows:geochem:Zr": "日本の地球化学図 — Zr (stream sediments)",
    "gsjows:gravity": "日本重力データベース — 重力図 (ブーゲー異常), 2.67 g/cm³ contours",
    "gsjows:japan2m": "200万分の1日本地質図 (2012) — areas and lines",
    "gsjows:magnetic_eastasia_1994": "東アジア磁気異常図 (MISC_32) — up to zoom 9",
    "gsjows:magnetic_eastasia_2021": "東・東南アジア磁気異常図 第3版 (DGM_P3_2021) — up to zoom 7",
    "gsjows:magnetic_japan": "200万分の1地質編集図 日本の磁気図 (TH_23magne) — up to zoom 8, enlarged beyond",
    "gsmma:discontinuity_50k": "不連續面位態·傾角 — foliation and similar",
    "gsmma:drainage_50k": "臺灣流域地質圖 — the 1:50k edition redrawn per drainage basin (strata, contacts, faults, folds)",
    "gsmma:drainage_labels_50k": "Names of strata, faults and folds",
    "gsmma:ore_50k": "1/50,000 臺灣地質圖-礦床 (points and lines)",
    "gsmma:sensitive_fault": "活動斷層地質敏感區 — agency caveat: for survey, research, analysis and planning only, not for statutory work.",
    "gsmma:sensitive_groundwater": "地下水補注地質敏感區 — agency caveat: for survey, research, analysis and planning only, not for statutory work.",
    "gsmma:sensitive_landscape": "地質遺跡地質敏感區 — agency caveat: for survey, research, analysis and planning only, not for statutory work.",
    "gsmma:sensitive_landslide": "山崩與地滑地質敏感區 — agency caveat: for survey, research, analysis and planning only, not for statutory work.",
    "gsnsw:mines": "Mines (EarthResourceML-Lite) — name and status",
    "gsnsw:minocc": "Mineral occurrences (EarthResourceML-Lite) — commodity and mine name",
    "gsq:mines": "Mines and mineral occurrence by status — from zoom 7",
    "gssa:minocc": "Mineral Occurrences of South Australia (EarthResourceML Lite) — from zoom 7",
    "gsv:gravity": "Victoria gravity stations — free-air and Bouguer anomaly (mGal). From zoom 9",
    "gsv:mineral": "Mineral deposits — 237 areas. From zoom 7",
    "gsv:mineralp": "Mineral deposits — 620 points. From zoom 7",
    "gtk:fennoscandia_mineral_deposit": "Fennoscandian Ore Deposit Database (GTK, NGU, SGU and Russia) — kokoavaWMS",
    "gtk:kalliopera_1m_kivilajiseurueet": "Kallioperä 1:1 000 000 — kivilajiseurueet. The wide edition covering all of Finland",
    "ibcso:tid": "What each IBCSO v2 grid cell (500 m) depth came from — measured (multibeam, single-beam) versus filled by interpolation or gravity prediction",
    "igme:magna50:0": "MAGNA 50 — Litologías color. The 1972–2003 sheets joined. From zoom 11",
    "igme:magna50:2": "MAGNA 50 — Contactos y fallas. From zoom 11",
    "igme:sgnrd:0": "PSysmin/IGME_SGN_EN_Geology 0 — DOM SGN 1:250k GeologicalUnits (SYSMIN, English edition)",
    "igme:sgnrd:1": "PSysmin/IGME_SGN_EN_Geology 1 — faults and contacts",
    "ineter:geology": "wsINETER-DGGG:Geologia_Nicaragua — the whole country",
    "ingemmet:aeromag": "SERV_AEROMAGNETIICO (ImageServer) — surveyed areas only",
    "ingemmet:belts": "SERV_METALOGENETICO 4 — 66 areas",
    "ingemmet:bouguer": "SERV_GEOFISICA 5 — Anomalía de Bouguer (raster)",
    "ingemmet:deposits": "SERV_METALOGENETICO 1 — 1,672 deposits. From zoom 7",
    "ingemmet:lithium": "Litio — from zoom 7",
    "ingemmet:occ_metal": "SERV_OCURRENCIA_MINERAL 0 — 1,859 sites, study belts only. From zoom 7",
    "ingemmet:occ_nonmetal": "SERV_OCURRENCIA_MINERAL 1 — 686 sites, study belts only. From zoom 7",
    "ingemmet:projects": "SERV_METALOGENETICO 0 — Proyectos y Operaciones, 532 sites. From zoom 7",
    "ingemmet:rmi": "Rocas y Minerales Industriales — from zoom 7",
    "jmg:age": "Rock age of … — 13 states and two federal territories",
    "jmg:lithology": "Lithology of … — 13 states and two federal territories, fifteen layers in one image",
    "G_tectonic": "Tectonic map",
    "L_10k_coalfield_geologic_map": "1:10k coalfield geological map",
    "L_1M_Geology_Map": "1:1M geological map",
    "L_1M_isotope_metamorphic": "Isotopic age map of metamorphic rocks",
    "L_1M_isotope_ore": "Isotopic age map of ore deposits",
    "L_1M_isotope_plutonic": "Isotopic age map of plutonic rocks",
    "L_1M_isotope_volcanic": "Isotopic age map of volcanic rocks",
    "L_250K_Geology_Map": "1:250k geological map",
    "L_25k_coalfield_geologic_map": "1:25k coalfield geological map",
    "L_50K_Geology_Map": "1:50k geological map",
    "L_50K_Geology_Map_NoAttitude": "The 1:50k geological map without attitude symbols (bedding, foliation, joints) and dip numbers — lithology, contacts, faults and folds remain. District boundaries and waterways are also dropped",
    "Marine_geology_prospect": "Marine survey tracks",
    "medical_clay": "Medical clay",
    "outcrop_korea": "Geological outcrops of Korea",
    "kopri:arctic_depth_contours": "KPDC Arctic base map — depth contours (m)",
    "kopri:contours": "SCAR Antarctic base map — contours on ice and rock (m). The edition changes with scale",
    "kopri:greenland_ice_contours": "KPDC Arctic base map — Greenland ice-sheet surface contours (m)",
    "kopri:historic": "85 historic sites and monuments designated by the Antarctic Treaty Consultative Meeting — number, description, managing party",
    "kopri:rock_outcrops": "SCAR Antarctic base map — rock exposed above the ice. Medium resolution from afar, high resolution up close",
    "mgb:geology": "Regional Geology (GeospatialDataInventory_Public) — scale not stated (about 1:1M)",
    "mgb:metallic": "GDI Metallic Mineral Resources — 655 sites",
    "mgb:nonmetallic": "GDI Non Metallic Mineral Resources — 52 sites",
    "mrdata:geochron:geochron": "National Geochronological Database — dated samples. Values on the detail page",
    "mrdata:mrds:mrds": "Mineral Resources Data System — mines, deposits and occurrences. From zoom 7",
    "mrdata:usmin:points": "Prospect- and mine-related features from USGS topographic maps — adits, shafts, quarries. From zoom 9",
    "mrdata:usmin:polygons": "USMIN — open pits, tailings and similar areas. From zoom 9",
    "mris:geology:1": "Atlas/1_Geology — Geological map of National Geological Atlas. Scale not stated (about 1:1M). WMS number 1 (REST 0)",
    "mris:ree": "Atlas 12_REE — 6 deposits, 280 mineralised points, 85 occurrences",
    "mrt:250k": "Geological polygons and lines 250K — statewide edition compiling the 1:50k and 1:63k map series at 1:250k",
    "mrt:25k": "Geological polygons and lines 25K — surveyed areas only",
    "ntgs:geology": "Northern Territory Geological Map (Interp) 2500K — 1 975 polygons; symbol, stratigraphic unit, rock, region and age",
    "ntgs:faults": "Northern Territory Geological Faults 2500K — 849; interpreted (geophysics) and mapped faults",
    "ni:ni_j100v_austurland_berggrunnur_1utg_fl": "Jarðfræði Austurland berggrunnur — the Eastern Fjords",
    "ni:ni_j100v_vesturgosbelti_berggrunnur_1utg_fl": "Jarðfræði Vesturgosbelti berggrunnur — around Langjökull",
    "ni:ni_j600v_berg_2_jardlog_2utg_fl": "Berggrunnur jarðlög — 1:600 000, 2. útgáfa (Haukur Jóhannesson 2014). The whole island",
    "ni:ni_j600v_hoggun_eldstodvakerfi_li": "Höggun eldstöðvakerfi — volcanic systems of the tectonic map (central volcanoes and fissure swarms)",
    "nbmg:geology": "Geologic map of Nevada 1:500,000 (Stewart & Carlson) — units and faults",
    "ngu:Berggrunn_lokal_bergartsenheter_fullzoom": "Berggrunn — lokalt nivå, bergartsenheter (1:50 000). Only where sheets are published — elsewhere white cells (IKKE KARTLAGT)",
    "ngu:Berggrunn_nasjonal_bergartsenheter": "Berggrunn — nasjonalt nivå, bergartsenheter (1:1 350 000). The widest edition, covering all of mainland Norway",
    "ngu:Berggrunn_regional_linjer_fullzoom": "Berggrunn — regionalt nivå, linjelag: rock contacts, faults, fold axes and thrusts",
    "nrcan:cgmc": "Canada Geological Map Compilation — a raster combining provincial and territorial bedrock maps. Click for the lithology",
    "nrcan:critical": "Critical minerals — mines, processing facilities, advanced exploration and planned processing",
    "nrcan:lithium": "Li-Cs-Ta pegmatite prospectivity (deep-learning model)",
    "nrcan:ree": "Prospectivity of carbonatites for REE and Nb (deep-learning model)",
    "nsgs:9": "Faults — from zoom 8",
    "ogs:11": "OMEIS Mineral Inventory — 18,697 sites",
    "peninsula:plain": "The Korean Peninsula geological map (shaded) without hillshade — 85 m per pixel; the flat colours overlay well on other basemaps. Jeju is not included",
    "peninsula:shaded": "The same map as the Korean Peninsula geological map (scan) blended with hillshade — 59 m per pixel; up close the scan is more detailed",
    "pgc:antarctica_contours": "25 m contours from REMA 2 m elevation. Drawn from zoom 10. Click for the elevation",
    "pgc:antarctica_slope": "Slope from REMA 2 m elevation — flat ground grey, steeper yellow, orange and red. Click for the slope in degrees",
    "pgc:greenland_contours": "25 m contours from ArcticDEM 2 m elevation. Drawn from zoom 10. Click for the elevation",
    "pgc:greenland_slope": "Slope from ArcticDEM 2 m elevation — flat ground grey, steeper yellow, orange and red. Click for the slope in degrees",
    "pgc:svalbard_contours": "25 m contours from ArcticDEM 2 m elevation. Drawn from zoom 10. Click for the elevation",
    "pgc:svalbard_slope": "Slope from ArcticDEM 2 m elevation — flat ground grey, steeper yellow, orange and red. Click for the slope in degrees",
    "phyloserver:dikes": "Dyke records on phyloserver — a line when both ends are known, a point when one. Rose diagrams per sheet when zoomed out",
    "phyloserver:peninsula": "The Korean Peninsula (including North Korea) geological map held by phyloserver — Kakao Map grid (EPSG:5181) tiles reprojected",
    "pig:faults": "MGP500k 3·9 — faults in the basement and Tertiary. From zoom 10",
    "pig:mgp500k": "MGP500k 1·6·11 — sub-Cenozoic basement, Paleogene–Neogene and Quaternary overlaid. Enlarged beyond zoom 12",
    "pig:smgp50k": "smgp50k 0 — Szczegółowa Mapa Geologiczna Polski. From zoom 13, digitised sheets only",
    "pig:smgp50k_lines": "smgp50k 2·3 — granice geologiczne, obiekty liniowe. From zoom 13",
    "segemar:e250K.DepositMetalif": "Depósitos minerales metalíferos 250K — from zoom 7",
    "segemar:e250K.DepositMinIndust": "Depósitos minerales industriales 250K — from zoom 7",
    "sgb:mineral_occurrences": "Ocorrências de Recursos Minerais (GeoSGB) — from zoom 6",
    "sgm:anom250:0": "Anomalías de Ag esc 1:250,000 — five concentration classes. From zoom 8",
    "sgm:anom250:1": "Anomalías de Co esc 1:250,000 — five concentration classes. From zoom 8",
    "sgm:anom250:2": "Anomalías de Cu esc 1:250,000 — five concentration classes. From zoom 8",
    "sgm:anom250:3": "Anomalías de Mn esc 1:250,000 — five concentration classes. From zoom 8",
    "sgm:anom250:4": "Anomalías de Pb esc 1:250,000 — five concentration classes. From zoom 8",
    "sgm:anom250:5": "Anomalías de Zn esc 1:250,000 — five concentration classes. From zoom 8",
    "sgm:anom50:0": "Anomalías de Ag esc 1:50,000 — five concentration classes. From zoom 10",
    "sgm:anom50:1": "Anomalías de Co esc 1:50,000 — five concentration classes. From zoom 10",
    "sgm:anom50:2": "Anomalías de Cu esc 1:50,000 — five concentration classes. From zoom 10",
    "sgm:anom50:3": "Anomalías de Mn esc 1:50,000 — five concentration classes. From zoom 10",
    "sgm:anom50:4": "Anomalías de Pb esc 1:50,000 — five concentration classes. From zoom 10",
    "sgm:anom50:5": "Anomalías de Zn esc 1:50,000 — five concentration classes. From zoom 10",
    "sgm:datos:7": "Campo magnético esc 1:250,000 (DatosAbiertos 7) — 17 colour classes, no nT values. From zoom 8, fetched as metatiles",
    "sgm:edades:0": "Carta geocronológica — 7,740 points. Dated samples (U-Pb, K-Ar, Ar-Ar and others), coloured by age",
    "sgm:geoq:0": "Geoquímica — 215,000 points, 34 elements. From zoom 9",
    "sgm:paleo:0": "Paleontología — 105 fossil localities surveyed by SGM. The popup links to SGM's photo page",
    "sgm:yac50:0": "Yacimientos minerales — Minas, 45,878 points. From zoom 10",
    "sgm:yac:0": "Yacimientos minerales 1:250,000 — Minas, 9,465 points. From zoom 8",
    "sgm:yac:1": "Alteraciones — 2,262 areas",
    "sgm:yac:2": "Distritos mineros — 305 areas",
    "sgm:yac:3": "Regiones mineralizadas — 248 areas",
    "sgm:yac:4": "Regiones no metálicas — 179 areas",
    "sgs:belts": "Mineralization Belts — 16 areas",
    "sgs:geology": "Saudi Arabian Standard Geological Map at 250K Scale — the western sheets (Arabian Shield) and surroundings joined",
    "sgs:mods": "Mineral Occurrence Documentation System — 5,751 sites",
    "sgu:bedrock": "Berggrund 1:1 miljon + Berggrund 1:50 000–1:250 000. Up close (from about 1:500k) areas covered by the 1:50k edition are drawn from it",
    "sgu:magnetic": "Magnetfält (fysik workspace) — click for the value there (nT)",
    "sgu:minerals": "Mineral- och bergartsförekomster — from zoom 6",
    "sigeom:mines": "Mines et projets — mines and development and ongoing projects",
    "sim3534:faults": "40,000 faults from the same map — reverse, normal, strike-slip and concealed faults by colour",
    "sim3534:units": "Geologic map of the Greater Antilles and the Virgin Islands — Cuba, Hispaniola, Jamaica, Puerto Rico and the Virgin Islands; 23,000 areas with symbol, name, age and English description",
    "skgs:3": "Bedrock Geology 250K — Precambrian Shield only",
    "skgs:smdi": "Saskatchewan Mineral Deposits Index — 6,012 sites",
    "spw:faults": "CARTE_GEOLOGIQUE_SIMPLE 7 — Failles. From zoom 13",
    "spw:geology": "CARTE_GEOLOGIQUE_SIMPLE 1·2 — units of two scale bands. From zoom 9",
    "stri:geology": "Símbolo — 1,608 areas: symbol (SIMBOLO), group, formation, rock type, description",
    "usgscarib:geology": "Geologic map of the Caribbean region (French & Schenk 2004) — 6,343 areas, age and lithology symbol (AGE) with English description",
    "usgscarib:sa:geology": "South America geology (Schenk et al. 1999) — 4,960 areas, 33 symbols (GLG)",
    "vmme:geology": "Geología — 61 areas, 13 units, symbol (Cod_) and group name (Descrip_)",
    "lt_c_aisctrc": "VWorld. Around airports",
    "lt_c_aisprhc": "VWorld. Check before flying a drone. Attributes give the upper and lower altitude limits",
    "lt_c_aisuac": "VWorld. Airspace where drones and paragliders may fly",
    "lt_c_asitdeepsoil": "VWorld. Detailed soil map of the Rural Development Administration. Drawn from zoom 12",
    "lt_c_asitsoildep": "VWorld. Detailed soil map of the Rural Development Administration. Drawn from zoom 12",
    "lt_c_asitsoildra": "VWorld. Detailed soil map of the Rural Development Administration. Drawn from zoom 12",
    "lt_c_asitsurston": "VWorld. Detailed soil map of the Rural Development Administration. Drawn from zoom 12",
    "lt_c_fsdifrsts": "VWorld. Forest soil types. Drawn from zoom 12",
    "lt_c_tfismpa": "VWorld. Marine life and wetland protected areas. Notice, legal basis and managing agency are in the attributes",
    "lt_c_uf901": "VWorld. Core and buffer zones",
    "lt_c_uo301": "VWorld. Places that need a permit to disturb, such as natural-monument fossil sites. Drawn from zoom 10",
    "lt_c_up201": "VWorld. Flood and collapse hazard districts",
    "lt_c_gimslinea": "VWorld. Lineament density class per district — from zoom 11",
    "lt_c_gimsstiff": "VWorld. Stiff diagrams of groundwater quality at wells — from zoom 12",
    "lt_l_gimsdirec": "VWorld. Arrows of groundwater flow direction — from zoom 12",
    "lt_l_toisdepcntah": "VWorld. KHOA coastline",
    "lt_c_wgisrecomp": "VWorld. Completed reclamation of public waters — for soft ground and liquefaction",
    "lt_c_uq125": "VWorld. Disaster prevention districts of urban plans",
    "lt_c_up401": "VWorld. Small areas, visible up close",
    "lt_c_wkmbbsn": "VWorld. Ministry of Environment basin divisions. Only the boundaries are drawn",
    "lt_c_wkmmbsn": "VWorld. Only the boundaries are drawn",
    "lt_c_wkmsbsn": "VWorld. Only the boundaries are drawn",
    "lt_l_frstclimb": "VWorld. Paths leading to outcrops",
    "lt_l_gimsdepth": "VWorld. Contours of groundwater depth (m). The lines are dense, so fetched in 0.125° cells and drawn from zoom 11",
    "lt_l_gimsec": "VWorld. Contours of electrical conductivity (µS/cm). Fetched by WFS and drawn by us",
    "lt_l_gimsfault": "VWorld. Fetched by WFS and drawn by us",
    "lt_l_gimslinea": "VWorld. Drawn from zoom 12",
    "lt_l_gimspoten": "VWorld. Contours of groundwater level elevation (m). Fetched by WFS and drawn by us",
    "lt_p_nsnmssitenm": "VWorld. Drawn from zoom 14",
    "lt_p_sgisgwchg": "VWorld. Groundwater wells where contamination is a concern, 444 sites. Fetched by WFS and drawn as points — all of South Korea is under 1,000 points, so 1° cells are not truncated (wetherilli 156)",
    "lt_p_weissitema": "VWorld. River water-quality stations (Ministry of Environment), 918 in South Korea. Fetched by WFS and drawn as points — all of South Korea is under 1,000 points, so 1° cells are not truncated (wetherilli 156)",
    "lt_p_weissitemb": "VWorld. Lake, reservoir and dam water-quality stations, 192 sites. Fetched by WFS and drawn as points — all of South Korea is under 1,000 points, so 1° cells are not truncated (wetherilli 156)",
    "lt_p_weissitemd": "VWorld. Agricultural reservoir and stream water-quality stations (Korea Rural Community Corporation), 955 sites. Fetched by WFS and drawn as points — all of South Korea is under 1,000 points, so 1° cells are not truncated (wetherilli 156)",
    "lt_p_weissiteme": "VWorld. Industrial-complex discharge points, 70 sites. Fetched by WFS and drawn as points — all of South Korea is under 1,000 points, so 1° cells are not truncated (wetherilli 156)",
    "lt_p_weissitemf": "VWorld. Urban stream stations, 37 sites. Fetched by WFS and drawn as points — all of South Korea is under 1,000 points, so 1° cells are not truncated (wetherilli 156)",
    "wadnr:100k": "Surface geology 1:100,000 GeMS (2026) — from zoom 8",
    "wadnr:500k": "Surface geology 1:500,000 (2022) — units, faults and folds",
    "ygs:57": "Mineral Occurrences 250k — 3,223 sites",
}
# 지역 탭의 화석·화산·지진·고생태 점 (wetherilli 185) — 지역마다 이름이 갈려 열둘이다. 열쇠가 레이어 이름이라 제목으로는 찾지 못했다
# (영어판에 한국어 제목이 뜨던 것, wetherilli 203)
LAYER_EN.update({f"earth:{kind}_{region}": title
                 for region in ("korea", "antarctica", "arctic")
                 for kind, title in (("pbdb", "Fossil collections (PBDB)"), ("gvp", "Holocene volcanoes (GVP)"),
                                     ("quakes", "Earthquakes M5+ (USGS)"),
                                     ("neotoma", "Quaternary palaeoecology sites (Neotoma)"))})
# 묶음마다 네모 하나 (wetherilli 331) — 제목에 묶음의 이름이 붙는다
LAYER_EN.update({f"earth:{kind}_{box}": f"{title} — {area}"
                 for box, area in {'eastasia': 'East Asia', 'southeast_asia': 'Southeast Asia', 'southasia': 'South and West Asia', 'europe': 'Europe', 'north_america': 'North America', 'central_america': 'Central America and Caribbean', 'south_america': 'South America', 'oceania': 'Oceania', 'africa': 'Africa'}.items()
                 for kind, title in (("pbdb", "Fossil collections (PBDB)"), ("gvp", "Holocene volcanoes (GVP)"),
                                     ("quakes", "Earthquakes M5+ (USGS)"), ("neotoma", "Quaternary palaeoecology sites (Neotoma)"),
                                     ("heatflow", "Heat flow (IHFC)"), ("recentquakes", "Recent earthquakes (7 days, M2.5+)"))})
