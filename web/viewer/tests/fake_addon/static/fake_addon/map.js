/* 가짜 덧붙이의 화면 파일 — `GSMScreen` 의 손을 한 번씩 부른다 (wetherilli 447). 계약 시험(`test_addons.py`)이 읽는다. */
(function () {
  "use strict";
  var S = window.GSMScreen;
  window.fakeAddon = { lines: [], clears: 0, clicks: [] };
  S.tool({ id: "fake", label: "가짜", title: "가짜 덧붙이의 단추", toggle: true,
           onClick: function (on) { window.fakeAddon.clicks.push(on); } });
  S.onLine(function (got) {
    window.fakeAddon.lines.push(got);
    S.mark(got.coords[0]);
    // 단추가 켜져 있을 때만 제가 그린다 — 꺼져 있으면 GSM 의 높이 그래프가 뜬다
    return document.getElementById("tool-x-fake").getAttribute("aria-pressed") === "true";
  });
  S.onLineClear(function () { window.fakeAddon.clears += 1; });
  window.fakeAddon.ready = { base: S.base, region: S.region(), length: S.asLength(1500), text: S.T("가짜 덧붙이의 문장") };
})();
