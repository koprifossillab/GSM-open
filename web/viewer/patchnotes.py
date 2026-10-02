"""`CHANGELOG.md` 를 화면이 쓸 꼴로 읽는다.

**마크다운 라이브러리를 들이지 않는다.** 읽을 것이 우리가 쓴 문서 하나뿐이고
꼴이 정해져 있어서, 스무 줄로 끝난다.

문서의 꼴:

    ## v0.1.0 — 2026-09-23 · 뼈대

    첫 판. 아직 인증키가 없어 …

    - 무엇을 했다 (001)
    - 무엇을 했다

돌려주는 것: `[{"version", "date", "title", "lead", "items": [...]}, …]`
"""
import re

#: 판 머리는 **판 번호만 보고 가른다.** 처음에는 날짜까지 한 정규식에 넣었는데,
#: 날짜를 빼먹거나 꼴을 달리 적은 판(`## v0.5.0 — 손질`)이 머리로 안 잡혀
#: **그 판이 통째로 사라졌다.** 머리를 놓치는 것보다 날짜를 못 읽는 편이 낫다.
HEAD = re.compile(r"^##\s+(?P<version>v[\d.]+)\s*(?P<rest>.*)$")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _split_rest(rest: str):
    """판 머리의 나머지를 날짜와 제목으로 가른다. 둘 다 없어도 된다."""
    rest = rest.strip().lstrip("—–-").strip()
    if not rest:
        return "", ""
    left, sep, title = rest.partition("·")
    left, title = left.strip(), title.strip()
    if DATE.fullmatch(left):
        return left, title
    # 날짜 자리에 날짜가 아닌 것이 있으면 그것도 제목이다.
    # 빈 자리에 구분자를 붙이지 않는다 — `## v0.5.0 · 손질` 이 `· 손질` 이 된다.
    return "", " · ".join(part for part in (left, title) if part)


def parse(text: str) -> list:
    notes, current = [], None
    for raw in text.splitlines():
        line = raw.rstrip()
        head = HEAD.match(line.strip())
        if head:
            date, title = _split_rest(head.group("rest"))
            current = {
                "version": head.group("version"),
                "date": date,
                "title": title,
                "lead": "",
                "items": [],
            }
            notes.append(current)
            continue
        if current is None:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            current["items"].append(stripped[2:].strip())
        elif current["items"]:
            # 목록 다음에 이어지는 줄은 앞 항목의 이어짐이다
            current["items"][-1] += " " + stripped
        else:
            current["lead"] = (current["lead"] + " " + stripped).strip()
    return notes
