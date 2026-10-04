/* 높이 그래프 밑의 지질 띠 (wetherilli 180). 지역 탭(map.js)·달·화성·수성 화면이 함께 쓴다.
 *
 * 서버(`profile/band/`, `profileband.py`)가 높이 그래프와 같은 점으로 선을 나눠 점마다 드는 지질 단위를 준다 —
 * `{"band": [단위 번호 또는 null…], "units": [{"label", "color"}…]}`. 우리 파일로 그리는 레이어만 받는다(상류에 점마다
 * 묻지 않는다). 여기서는 그 띠를 그래프 밑에 색 칸으로 잇는다. 화면의 글(T)은 부르는 쪽이 넘긴다 — i18n 시험이 그 파일을 긁는다.
 *
 *   GSMBand.load(base, layer, line, n)      → Promise<띠 또는 null> — 못 받으면 null(띠 없이 그래프만 남는다)
 *   GSMBand.draw(svg, P, X, d, band, label) → 그래프 밑에 띠를 덧그리고 판의 높이를 늘린다
 *   GSMBand.unitAt(band, i)                 → 점 i 의 단위 이름 또는 ""
 */
(function () {
  "use strict";
  var HEIGHT = 14, GAP = 6;

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }

  function load(base, layer, line, n) {
    return fetch(base + "profile/band/?layer=" + encodeURIComponent(layer) + "&line=" + encodeURIComponent(line) + "&n=" + n)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (b) { return b && b.band && b.band.some(function (k) { return k !== null; }) ? b : null; })
      .catch(function () { return null; });
  }

  // 같은 단위가 이어지는 점을 한 칸으로 — 칸의 끝은 이웃한 두 점의 가운데다
  function draw(svg, P, X, d, band, label) {
    var top = P.H + GAP / 2, out = "", i = 0, n = band.band.length;
    function edge(k) { return k <= 0 ? X(d.dist[0]) : k >= n ? X(d.dist[n - 1]) : (X(d.dist[k - 1]) + X(d.dist[k])) / 2; }
    while (i < n) {
      var j = i;
      while (j + 1 < n && band.band[j + 1] === band.band[i]) j++;
      var unit = band.band[i] === null ? null : band.units[band.band[i]];
      if (unit) {
        var x0 = edge(i), x1 = edge(j + 1);
        out += '<rect class="band" x="' + x0.toFixed(1) + '" y="' + top + '" width="' + Math.max(0.6, x1 - x0).toFixed(1) +
               '" height="' + HEIGHT + '" fill="' + esc(unit.color) + '"><title>' + esc(unit.label) + "</title></rect>";
      }
      i = j + 1;
    }
    out += '<rect class="band-frame" x="' + P.L + '" y="' + top + '" width="' + (P.W - P.L - P.R) + '" height="' + HEIGHT + '"/>' +
           '<text class="tick" x="' + (P.L - 5) + '" y="' + (top + HEIGHT - 3) + '" text-anchor="end">' + esc(label) + "</text>";
    var g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "band-row");
    g.innerHTML = out;
    var old = svg.querySelector(".band-row");
    if (old) old.remove();
    svg.insertBefore(g, svg.firstChild);
    var h = P.H + GAP + HEIGHT;
    svg.setAttribute("viewBox", "0 0 " + P.W + " " + h);
    svg.style.height = h + "px";
  }

  // 띠 없이 다시 그릴 때 판을 처음 높이로
  function reset(svg, P) {
    svg.setAttribute("viewBox", "0 0 " + P.W + " " + P.H);
    svg.style.height = "";
  }

  function unitAt(band, i) {
    if (!band || band.band[i] === null || band.band[i] === undefined) return "";
    return band.units[band.band[i]].label;
  }

  window.GSMBand = { load: load, draw: draw, reset: reset, unitAt: unitAt };
})();
