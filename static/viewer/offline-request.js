/* 오프라인 묶음 굽기 요청 화면 (wetherilli P16·408) — 고른 것을 모아 어림(`estimate/`)을 보이고 요청한다(POST 한 줄).
 * 굽는 것은 staff 가 승인한 뒤 서버의 일꾼이다. 검사는 서버(`offlinereq.clean`)가 한다 — 여기는 모으고 보이기만 한다. */
(function () {
  "use strict";

  var LANG = document.documentElement.lang === "en" ? "en" : "ko";
  var I18N = JSON.parse((document.getElementById("i18n-data") || {}).textContent || "{}");

  function T(text, vars) {
    var out = (LANG === "en" && I18N[text]) || text;
    if (vars) out = out.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; });
    return out;
  }
  function $(id) { return document.getElementById(id); }
  function csrf() { var i = document.querySelector("#csrf-form [name=csrfmiddlewaretoken]"); return i ? i.value : ""; }

  function gather() {
    var layers = {};
    document.querySelectorAll("#layers tr").forEach(function (tr) {
      if (!tr.querySelector("input[type=checkbox]").checked) return;
      layers[tr.dataset.name] = [Number(tr.querySelector(".z0").value), Number(tr.querySelector(".z1").value)];
    });
    return {
      title: $("r-title").value, requester: $("r-who").value, note: $("r-note").value, layers: layers,
      bbox: Array.prototype.map.call(document.querySelectorAll(".bb"), function (i) { return Number(i.value); }),
    };
  }

  function say(text, bad) {
    $("said").textContent = text;
    $("said").classList.toggle("bad", !!bad);
  }

  function post(url, body) {
    return fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
                        body: JSON.stringify(body), credentials: "same-origin" })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || r.status); return j; }); });
  }

  $("b-estimate").addEventListener("click", function () {
    say(T("어림하는 중…"));
    post("estimate/", gather()).then(function (got) {
      $("estimate").hidden = false;
      $("estimate").textContent = got.lines.join("\n");
      var dropped = Object.keys(got.dropped || {});
      say(dropped.length ? T("예산 {mb} MB 를 넘어 덜어 낼 것이 있다: {names}", { mb: got.budget, names: dropped.join(", ") })
                         : T("어림 {n} MB · 굽기 {m} 분 남짓", { n: got.mb, m: got.minutes }));
    }).catch(function (e) { say(e.message, true); });
  });

  $("b-send").addEventListener("click", function () {
    var button = $("b-send");
    button.disabled = true;
    say(T("요청하는 중…"));
    post("", gather()).then(function (got) {
      location.replace("?sent=" + encodeURIComponent(got.name));
    }).catch(function (e) { button.disabled = false; say(e.message, true); });
  });
})();
