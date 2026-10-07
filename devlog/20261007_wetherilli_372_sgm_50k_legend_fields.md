# 멕시코 1:5만 범례 — 상류가 바꾼 열 이름으로 묻는다

2026-10-07 · `fix/sgm-lithology-legend` · wetherilli

## 왜

v0.70.0 을 내고 `verify_layers --legends` 를 돌리니 97 개 가운데 `sgm:7`(암상 1:5만) 하나만 깨졌다. 상류가 범례 질의(통계)에 400 을 준다.
레이어 7 의 열이 지금 `CLAVE·DLO·EDAD_INI·EDAD_FIN·TIPOLITO·NOMBRE` 이고, 칠하기 규칙도 `CLAVE` 로 칠한다. 우리는 1:25만(8)의 열
(`CLAVE_SGM·LITOLOGIA·FORMACION·PERIODO`)로 묶어 물었다 — 없는 열로 묶으니 상류가 거절한 것이다. 타일·누른 자리는 열을 고르지 않아 멀쩡했다.

## 한 것

- `LEGENDS["sgm:7"]` 을 `CLAVE` 로 칠하고 `CLAVE·DLO·NOMBRE·EDAD_INI·EDAD_FIN` 으로 묶는다.
- 범례 줄은 암상을 `DLO` 에서, 시대를 시작·끝(`EDAD_INI`~`EDAD_FIN`)에서 짓는다. 값이 대문자 스페인어(`OLIGOCENO`·`TITHONIANO`)여도 `i18n.age_es` 가 옮긴다.

## 버린 것

- **열 이름을 상류의 `?f=json` 에서 그때그때 읽기** — 범례마다 한 번 더 묻게 된다. 열이 바뀌는 일은 드물고, 바뀌면 `verify_layers --legends` 가 잡는다.
