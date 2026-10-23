"""혼자 굽는 쪽의 소스 둘 (wetherilli P16·407) — `via_gsm`(GSM 서버의 HTTP 길을 거친다, 키 없음)과 `direct`(쓰는 사람의 키로 상류를 곧장).

소스의 꼴은 `gsmpack.bake` 머리글. 둘 다 서버 캐시가 없으니 받은 것을 parts(`bake.Parts`)에 두고 `cached` 가 거기서 읽는다 —
멈췄다 다시 부르면 이어진다. `touched` 는 방금 `fetch` 가 상류를 탔는가 — 아니면(GSM 캐시에서 나왔다) 굽는 고리가 1 초를 쉬지 않는다.
"""
from .. import format, grid as grids


class PartsSource:
    """받은 것을 parts 에 두는 소스의 바탕."""
    touched = True
    grid = grids.MERCATOR                     # 칸을 세는 격자 — 남극 소스는 제 격자를 단다(wetherilli 410)

    def __init__(self, name, parts):
        self.name, self.parts = name, parts

    def tiles(self, bbox, z):
        return self.grid.tiles_for(bbox, z)

    def cached(self, z, x, y):
        return self.parts.get(format.tile_key(self.name, z, x, y))

    def keep(self, z, x, y, data):
        self.parts.put(format.tile_key(self.name, z, x, y), data)
        return data
