"""중국 지질도 1:400만 스캔에서 중국 땅만 남기는 마스크를 굽는다 (wetherilli 386).

    manage.py build_china4m_mask                    <GSM_CHINA4M_DIR>/GeoChina400*.jpg → GeoChina400_mask.png
    manage.py build_china4m_mask --preview p.png    눈으로 볼 축소판도

원도는 중국 밖을 외국 땅 회색(214,230,230)·바다 하늘색 단계·흰 여백으로 칠하고, 국경을 분홍 띠로 두른다.
**색만으로는 가르지 못한다** — 쥐라계 청록(J₃ 의 176,255,255 따위)이 바다 수심 단계와 같은 색이다. 그래서

1. 1/4 로 줄여 바탕색(회색·바다·흰색·바다 위 청록 글자·강)을 고르고, **도곽 가장자리에 닿은 덩어리만** 바탕으로 본다.
   분홍 띠는 벽이다 — 국경 안쪽의 하늘색 지층은 바깥 바다와 이어지지 않아 땅으로 남는다
2. 범례·삽입도·연대표·제목(`china4m.NOT_MAP`)을 빼고, 닫고 열어 선·글자를 메운다
3. 큰 땅(본토·대만·하이난) 셋과, 거기서 50 km 안에 있고 꽉 찬 작은 덩어리(섬)만 남긴다. 바다·외국 땅 위의 글자·강
   조각을 버리려는 것이다
4. 경계 띠(1/4 에서 ±2 화소) 안에서만 원본 해상도의 색으로 다시 다듬는다 — 1/4 의 계단을 없앤다

**numpy·scipy 가 있는 파이썬으로만 돈다.** 제품은 numpy 를 쓰지 않는다 — 구운 마스크(1 비트 PNG)를 원본 옆에 두고
`build_china4m` 이 Pillow 로 읽는다. 다시 부를 일은 스캔이 바뀔 때뿐이다. 메모리를 1.5 GB 남짓 쓴다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import china4m

#: 줄여서 가르는 배율
SCALE = 4
#: 큰 땅으로 칠 크기(줄인 화소) — 하이난(약 2 만)보다 작고 바다 글자보다 훨씬 크다
BIG = 3000
#: 작은 섬을 남기는 거리(줄인 화소, 한 화소 1.7 km)
NEAR = 30


def background(rgb):
    """(회색, 바다, 흰색, 분홍, 청록 글자, 강) 마스크 — rgb 는 int 배열."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    grey = (abs(r - 214) <= 10) & (abs(g - 230) <= 8) & (abs(b - 229) <= 9)
    sea = (g >= 236) & (b >= 236) & (r <= 238) & (abs(g - b) <= 14) & (g - r >= 12)
    white = (r >= 245) & (g >= 245) & (b >= 245)
    pink = (r >= 235) & (b >= 235) & (g <= 232) & (r - g >= 20)
    teal = (r <= 70) & (g >= 90) & (g <= 175) & (abs(g - b) <= 22)
    river = (r <= 170) & (g >= 215) & (abs(g - b) <= 10)
    return grey, sea, white, pink, teal, river


def build_mask(image):
    """원본(PIL RGB) → 땅 마스크(bool 배열, 원본 크기)."""
    import numpy as np
    from scipy import ndimage as nd

    s = SCALE
    full = np.asarray(image)
    small = full[::s, ::s].astype(int)
    grey, sea, white, pink, teal, river = background(small)
    candidate = grey | sea | white | teal | river
    # 1. 도곽 가장자리에 닿은 바탕색 덩어리 (분홍 띠는 바탕색이 아니라서 벽이 된다)
    x0, y0, x1, y1 = china4m.NEATLINE
    frame = np.zeros_like(candidate)
    frame[y0 // s + 2, :] = frame[y1 // s - 2, :] = True
    frame[:, x0 // s + 2] = frame[:, x1 // s - 2] = True
    labels, count = nd.label(candidate)
    index = np.arange(1, count + 1)
    is_bg = np.zeros(count + 1, bool)
    touch = np.unique(labels[frame & candidate])
    is_bg[touch[touch > 0]] = True
    # 도곽에 닿지 않아도 거의 다 외국 땅 회색인 덩어리 (국경 띠 너머의 고립된 외국 땅)
    grey_share = nd.sum(grey, labels, index) / np.maximum(nd.sum(candidate, labels, index), 1)
    is_bg[1:] |= grey_share > 0.6
    land = ~(is_bg[labels] | pink | white)
    # 2. 도곽 밖·지도가 아닌 칸
    land[: y0 // s + 1, :] = land[y1 // s:, :] = False
    land[:, : x0 // s + 1] = land[:, x1 // s:] = False
    for bx0, by0, bx1, by1 in china4m.NOT_MAP:
        land[by0 // s: by1 // s, bx0 // s: bx1 // s] = False
    land = nd.binary_opening(nd.binary_closing(land, iterations=3), iterations=1)
    # 3. 큰 땅과 그 곁의 섬
    labels, count = nd.label(land)
    index = np.arange(1, count + 1)
    sizes = nd.sum(land, labels, index)
    big = np.zeros(count + 1, bool)
    big[1:] = sizes >= BIG
    near = nd.minimum(nd.distance_transform_edt(~big[labels]), labels, index)
    boxes = nd.find_objects(labels)
    fill = np.array([sizes[i] / max(1, (o[0].stop - o[0].start) * (o[1].stop - o[1].start))
                     for i, o in enumerate(boxes)])
    keep = np.zeros(count + 1, bool)
    keep[1:] = big[1:] | ((sizes >= 12) & (near <= NEAR) & (fill >= 0.25))
    land = nd.binary_fill_holes(keep[labels])
    # 4. 경계 띠만 원본 해상도로
    inner = nd.binary_erosion(land, iterations=2)
    outer = nd.binary_dilation(land, iterations=2)
    h, w = full.shape[:2]

    def up(mask):
        return np.repeat(np.repeat(mask, s, axis=0), s, axis=1)[:h, :w]

    result = up(inner)
    band = up(outer & ~inner)
    ys, xs = np.nonzero(band)
    grey, sea, white, pink, teal, river = background(full[ys, xs].astype(int))
    result[ys, xs] = ~(grey | sea | white | pink)
    return result


class Command(BaseCommand):
    help = "중국 지질도 1:400만 스캔에서 중국 땅 마스크를 굽는다 (numpy·scipy 필요)"

    def add_arguments(self, parser):
        parser.add_argument("--source", help="원본 스캔 (기본: GSM_CHINA4M_DIR 의 GeoChina400*.jpg)")
        parser.add_argument("--preview", help="땅 밖을 어둡게 한 축소판을 여기에 쓴다")

    def handle(self, *args, **options):
        try:
            import numpy as np
            from scipy import ndimage  # noqa: F401
        except ImportError:
            raise CommandError("numpy·scipy 가 있는 파이썬으로 부른다 — 제품 이미지에는 없다") from None
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None           # 1 억 5 천만 화소 — 폭탄이 아니라 지도다

        path = options["source"] or china4m.source_file()
        if not path:
            raise CommandError(f"원본이 없다 — {china4m.root()}/{china4m.SOURCE} (원본은 NAS N:\\GSM\\sources\\china4m\\)")
        image = Image.open(path).convert("RGB")
        if image.size != china4m.SIZE:
            raise CommandError(f"그림이 {image.size} 다 — {china4m.SIZE} 를 기다렸다")
        land = build_mask(image)
        out = china4m.mask_file()
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(land).convert("1").save(out, optimize=True)
        share = land.mean() * 100
        self.stdout.write(self.style.SUCCESS(f"{out} — 땅 {share:.1f} %, {out.stat().st_size / 1024:.0f} KB"))
        if options["preview"]:
            small = image.reduce(8)
            dark = np.asarray(small).copy()
            keep = np.asarray(Image.fromarray(land).resize(small.size))
            dark[~keep] = (dark[~keep] * 0.3).astype(np.uint8)
            Image.fromarray(dark).save(options["preview"])
