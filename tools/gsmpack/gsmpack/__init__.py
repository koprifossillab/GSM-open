"""오프라인 묶음(`.gsmpack`)을 굽고 읽는 패키지 (wetherilli P16).

GSM 없이 혼자 돈다 — Django·`viewer` 를 import 하지 않는다. 타일을 어디서 받을지는 부르는 쪽이 소스로 넘긴다(`gsmpack.bake`).
GSM 은 제 문·캐시를 소스로 꽂아 쓴다(`manage.py build_offline_pack`).
"""
__version__ = "0.1.0"
