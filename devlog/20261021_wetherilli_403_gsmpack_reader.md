# 오프라인 묶음 읽기를 패키지로 — `gsmpack-reader.js` 와 꼴의 명세 (P16 2 단계)

2026-10-21 · `feature/gsmpack-reader` (`feature/gsmpack-core` 위) · wetherilli

P16 의 2 단계다. `offline.js` 에서 **묶음 하나를 읽는 것** — 머리, 타일 Blob, 지층 면, 누른 자리 — 을 `tools/gsmpack/js/gsmpack-reader.js`
(`GSMPack`)로 뗐다. 꼴의 명세는 패키지의 README 로 옮겼다. 이것으로 다른 앱(Cropobite 따위)이 GSM 의 화면 없이 같은 묶음을 연다.

## 어디서 자르나

- **읽는 쪽은 묶음 하나만 안다** — `{blob, head, base}` 하나를 받아 답한다. 여러 묶음 가운데 새것이 이기는 차례, IndexedDB 저장,
  localStorage 의 덮는 레이어 이름, OpenLayers 소스 감싸기(`wrap`), 지층 면을 묶음마다 한 번만 읽어 두기는 `offline.js` 에 남았다.
  그것들은 GSM 화면의 사정이다 — 다른 앱은 저장을 다르게 하고 지도 라이브러리도 다를 수 있다
- **오류는 말이 아니라 `code` 로** — 읽는 쪽이 `T("…")` 를 부르면 GSM 의 번역을 알아야 한다. `not-pack`·`truncated`·`bad-header` 를
  붙여 던지고, `offline.js` 가 그것을 지금의 한국어 문장(`T`)으로 바꾼다. 화면의 말은 그대로이고 `test_i18n` 이 보던 자리도 그대로다
- 하나 달라진 것 — 머리 JSON 이 깨진 묶음은 전에는 `JSON.parse` 의 영어 오류가 그대로 떴다. 이제 "묶음의 머리를 읽지 못했다" 다
- **GSM 은 `STATICFILES_DIRS` 로 낸다**(`static/gsmpack/gsmpack-reader.js`) — 1 단계의 `sys.path` 와 같은 까닭으로 복사하지 않는다.
  `collectstatic` 이 모으므로 이미지와 정적 판(`static_site.py`)도 따로 손댈 것이 없다. `map.html` 이 `offline.js` 바로 앞에 싣는다
- **명세는 README 하나** — `format.py` 의 머리글과 P13 은 거기를 가리킨다. P13 은 그때의 판단이라 고치지 않고 가리키는 줄만 더했다.
  지금 꼴은 P13 에 `tile_size`·`units`·`gsm`·`title`(레이어)이 더해진 것이다 — 그것을 다 적었다. 꼴을 고치면 README·`format.py`·
  `gsmpack-reader.js` 셋을 같은 커밋에서 맞추고, 옛 묶음을 못 읽게 되면 `GSMPACK1` 을 올린다

## 확인한 것

- 패키지 시험에 **읽는 쪽 시험**(`test_reader_js.py`)을 더했다 — `format.write` 로 지은 묶음을 node 가 `gsmpack-reader.js` 로 읽어
  머리·타일·격자가 다르면 거절·지층 면 안팎·영어판·범위·꼴 오류의 `code` 를 본다. node 가 없으면 건너뛴다(CI 의 GitHub 러너에는 있다).
  브라우저 없이 돈다 — 읽는 쪽이 DOM 을 쓰지 않는다는 것도 이것이 지킨다
- 휴대폰 화면의 `OfflinePack`(묶음을 들이면 망 없이 그린다)·`test_i18n`·`test_offlinepack`·정적 판(`test_static_site`) 통과
- `manage.py test viewer --parallel 8` — 1 단계와 같이 `test_안내_타일에는_ETag_가_없다` 하나만 깨진다(이 트리의 환경 탓, wetherilli 402)

## 버린 것

- **읽는 쪽에 IndexedDB 저장까지 넣기** — 다른 앱이 쓰기 좋아 보이지만 저장 이름(`gsm-offline`)·한도·지우기가 화면마다 다르다.
  필요해지면 그때 따로 뗀다
- **ES 모듈로 쓰기** — 지금 화면은 모듈을 쓰지 않고 `<script>` 를 잇는다. 같은 꼴(`root.GSMPack`)로 두었다
