"""ICS 국제층서표 — 온 지구 시간 축의 지질시대 띠 (wetherilli 373). 문이 아니다.

시간 축이 덮는 1 100 Ma 부터 오늘까지의 누대·대·기·세, 그리고 제4기의 절. 경계는 ICS v2024/12
(https://stratigraphy.org/chart), 이름은 그 한글판(대한지질학회 옮김 — `i18n.AGE_STAGES` 와 같은 판)이다.
색은 ICS 표의 CGMW 색이다. Macrostrat 의 기(period) 범례도 같은 경계라 두 곳이 어긋나지 않는다
— 원생누대의 색만은 Macrostrat 이 분홍으로 칠해 ICS 의 것을 따랐다.

판이 오르면 이 표를 그 판과 대조한다. 상류를 타지 않는다 — 화면이 열릴 때 그대로 싣는다.
"""

#: (갈래, 한국어, 영어, 줄인 한국어, 줄인 영어, 밑 Ma, 위 Ma, 색). 갈래는 eon·era·period·epoch·stage.
#: 줄인 것은 칸이 좁을 때 쓴다 — 기는 ICS 기호, 세의 전기·중기·후기는 그 말만.
UNITS = (
    ("eon", "원생누대", "Proterozoic", "원생", "PR", 2500, 538.8, "#F73563"),
    ("eon", "현생누대", "Phanerozoic", "현생", "PH", 538.8, 0, "#9AD9DD"),

    ("era", "중원생대", "Mesoproterozoic", "중원", "MP", 1600, 1000, "#FDB462"),
    ("era", "신원생대", "Neoproterozoic", "신원", "NP", 1000, 538.8, "#FEB342"),
    ("era", "고생대", "Paleozoic", "고", "Pz", 538.8, 251.902, "#99C08D"),
    ("era", "중생대", "Mesozoic", "중", "Mz", 251.902, 66, "#67C5CA"),
    ("era", "신생대", "Cenozoic", "신", "Cz", 66, 0, "#F2F91D"),

    ("period", "스테노스기", "Stenian", "St", "St", 1200, 1000, "#FED99A"),
    ("period", "토노스기", "Tonian", "To", "To", 1000, 720, "#FEBF4E"),
    ("period", "크리오스진기", "Cryogenian", "Cr", "Cr", 720, 635, "#FECC5C"),
    ("period", "에디아카라기", "Ediacaran", "Ed", "Ed", 635, 538.8, "#FED96A"),
    ("period", "캄브리아기", "Cambrian", "Є", "Є", 538.8, 486.85, "#7FA056"),
    ("period", "오르도비스기", "Ordovician", "O", "O", 486.85, 443.1, "#009270"),
    ("period", "실루리아기", "Silurian", "S", "S", 443.1, 419.62, "#B3E1B6"),
    ("period", "데본기", "Devonian", "D", "D", 419.62, 358.86, "#CB8C37"),
    ("period", "석탄기", "Carboniferous", "C", "C", 358.86, 298.9, "#67A599"),
    ("period", "페름기", "Permian", "P", "P", 298.9, 251.902, "#F04028"),
    ("period", "트라이아스기", "Triassic", "T", "T", 251.902, 201.4, "#812B92"),
    ("period", "쥐라기", "Jurassic", "J", "J", 201.4, 143.1, "#34B2C9"),
    ("period", "백악기", "Cretaceous", "K", "K", 143.1, 66, "#7FC64E"),
    ("period", "고진기", "Paleogene", "Pg", "Pg", 66, 23.04, "#FD9A52"),
    ("period", "신진기", "Neogene", "N", "N", 23.04, 2.58, "#FFE619"),
    ("period", "제4기", "Quaternary", "Q", "Q", 2.58, 0, "#F9F97F"),

    ("epoch", "테레누브세", "Terreneuvian", "테레", "Ter", 538.8, 521, "#8CB06C"),
    ("epoch", "캄브리아기 제2세", "Cambrian Series 2", "2세", "S2", 521, 506.5, "#99C078"),
    ("epoch", "미아오링세", "Miaolingian", "미아", "Mia", 506.5, 497, "#A6CF86"),
    ("epoch", "푸롱세", "Furongian", "푸롱", "Fur", 497, 486.85, "#B3E095"),
    ("epoch", "전기 오르도비스기", "Early Ordovician", "전기", "Early", 486.85, 471.3, "#1A9D6F"),
    ("epoch", "중기 오르도비스기", "Middle Ordovician", "중기", "Mid", 471.3, 458.2, "#4DB47E"),
    ("epoch", "후기 오르도비스기", "Late Ordovician", "후기", "Late", 458.2, 443.1, "#7FCA93"),
    ("epoch", "란도베리세", "Llandovery", "란도", "Lla", 443.1, 432.9, "#99D7B3"),
    ("epoch", "웬록세", "Wenlock", "웬록", "Wen", 432.9, 426.7, "#B3E1C2"),
    ("epoch", "러들로세", "Ludlow", "러들", "Lud", 426.7, 422.7, "#BFE6CF"),
    ("epoch", "프리돌리세", "Pridoli", "프", "Pri", 422.7, 419.62, "#E6F5E1"),
    ("epoch", "전기 데본기", "Early Devonian", "전기", "Early", 419.62, 393.47, "#E5AC4D"),
    ("epoch", "중기 데본기", "Middle Devonian", "중기", "Mid", 393.47, 382.31, "#F1C868"),
    ("epoch", "후기 데본기", "Late Devonian", "후기", "Late", 382.31, 358.86, "#F1E19D"),
    ("epoch", "미시시피아기", "Mississippian", "미시시피", "Miss", 358.86, 323.4, "#678F66"),
    ("epoch", "펜실베니아아기", "Pennsylvanian", "펜실", "Penn", 323.4, 298.9, "#99C2B5"),
    ("epoch", "시스우랄세", "Cisuralian", "시스", "Cis", 298.9, 274.4, "#EF5845"),
    ("epoch", "과달루페세", "Guadalupian", "과달", "Gua", 274.4, 259.51, "#FB745C"),
    ("epoch", "러핑세", "Lopingian", "러핑", "Lop", 259.51, 251.902, "#FBA794"),
    ("epoch", "전기 트라이아스기", "Early Triassic", "전기", "Early", 251.902, 246.7, "#983999"),
    ("epoch", "중기 트라이아스기", "Middle Triassic", "중기", "Mid", 246.7, 237, "#B168B1"),
    ("epoch", "후기 트라이아스기", "Late Triassic", "후기", "Late", 237, 201.4, "#BD8CC3"),
    ("epoch", "전기 쥐라기", "Early Jurassic", "전기", "Early", 201.4, 174.7, "#42AED0"),
    ("epoch", "중기 쥐라기", "Middle Jurassic", "중기", "Mid", 174.7, 161.5, "#80CFD8"),
    ("epoch", "후기 쥐라기", "Late Jurassic", "후기", "Late", 161.5, 143.1, "#B3E3EE"),
    ("epoch", "전기 백악기", "Early Cretaceous", "전기", "Early", 143.1, 100.5, "#8CCD57"),
    ("epoch", "후기 백악기", "Late Cretaceous", "후기", "Late", 100.5, 66, "#A6D84A"),
    ("epoch", "팔레오세", "Paleocene", "팔레", "Pal", 66, 56, "#FDA75F"),
    ("epoch", "에오세", "Eocene", "에오", "Eo", 56, 33.9, "#FDB46C"),
    ("epoch", "올리고세", "Oligocene", "올리", "Ol", 33.9, 23.04, "#FDC07A"),
    ("epoch", "마이오세", "Miocene", "마이", "Mio", 23.04, 5.333, "#FFFF00"),
    ("epoch", "플라이오세", "Pliocene", "플라", "Pli", 5.333, 2.58, "#FFFF99"),
    ("epoch", "플라이스토세", "Pleistocene", "플라이스토", "Ple", 2.58, 0.0117, "#FFF2AE"),
    ("epoch", "홀로세", "Holocene", "홀로", "Hol", 0.0117, 0, "#FEF2E0"),

    # 제4기의 절 — 시간 축에서 제4기만 넓게 펴서 이것만 싣는다
    ("stage", "젤라절", "Gelasian", "젤라", "Gel", 2.58, 1.8, "#FFEDB3"),
    ("stage", "칼라브리아절", "Calabrian", "칼라", "Cal", 1.8, 0.774, "#FFF2BA"),
    ("stage", "지바절", "Chibanian", "지바", "Chi", 0.774, 0.129, "#FFF2C7"),
    ("stage", "후기 플라이스토세", "Upper Pleistocene", "후기", "Upper", 0.129, 0.0117, "#FFF2D3"),
    ("stage", "그린란드절", "Greenlandian", "그린", "Grn", 0.0117, 0.0082, "#FDEDEC"),
    ("stage", "노스그립절", "Northgrippian", "노스", "Ngr", 0.0082, 0.0042, "#FDECE4"),
    ("stage", "메갈라야절", "Meghalayan", "메갈", "Meg", 0.0042, 0, "#FDEBEA"),
)

RANKS = ("eon", "era", "period", "epoch", "stage")


def units(lang: str = "ko") -> list:
    """화면이 싣는 꼴 — 갈래 차례, 갈래 안에서는 오랜 것부터"""
    en = lang == "en"
    rows = [{"rank": rank, "name": e if en else k, "short": se if en else sk, "b": b, "t": t, "color": color}
            for rank, k, e, sk, se, b, t, color in UNITS]
    rows.sort(key=lambda r: (RANKS.index(r["rank"]), -r["b"]))
    return rows
