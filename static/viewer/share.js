/* 공유 링크 (wetherilli 189) — 보던 자리·켠 레이어·배경을 주소의 해시(#)에 담는다. 지역 지도·온 지구·달·화성·수성이 함께 쓴다.
 *
 * 꼴은 `#c=경도,위도&z=줌&l=레이어*투명도,…&b=배경…` — 질의(?)가 아니라 해시에 둔다. 해시는 서버로 가지 않아 정적 판(GitHub Pages)에서도
 * 그대로 돌고, 서버·브라우저의 페이지 캐시를 가르지 않고, 원래 있던 질의(`?region=`·`?age=`)와 부딪히지 않는다.
 *
 * **링크로 연 화면은 그 사람의 기억(localStorage)을 덮지 않는다.** 들어올 때 해시를 읽어 지우고, 링크의 상태를 메모리 덧층에 깐다.
 * 화면은 늘 하던 대로 기억을 읽고 쓰되 덧층이 먼저 답하고, 쓰는 것도 덧층에만 남는다. 새로 고치면 그 사람의 화면으로 돌아간다.
 *
 *   GSMShare.read()                 → 해시의 값들(객체) 또는 null. 읽으면 주소에서 지운다 — 처음 한 번만 적용한다
 *   GSMShare.store(seed)            → {get(key), set(key, value), shared} — seed 가 있으면 덧층, 없으면 localStorage 그대로
 *   GSMShare.link(values)           → 지금 주소에 해시를 붙인 링크
 *   GSMShare.copy(text)             → Promise<bool> — 클립보드가 막힌 곳(https 가 아닌 사내 주소)에서는 옛 길로, 그것도 안 되면 false
 *   GSMShare.layers(text) / pack(list) — `이름*투명도(0–100),…` ↔ `[{name, opacity}]`
 *   GSMShare.notice(text, back)     → 링크로 연 화면이라는 띠. `back` 을 누르면 그 사람의 화면으로(새로 고침)
 *   GSMShare.wire(button, make, words) → "링크 복사" 단추. words = {done, ask} — 화면의 글은 부르는 쪽이 넘긴다(i18n 시험이 그 파일을 긁는다)
 */
(function () {
  "use strict";
  var KEYS = ["r", "c", "z", "p", "l", "b", "m", "h", "hd", "pt", "res", "a"];

  function read() {
    var raw = (location.hash || "").replace(/^#/, "");
    if (!raw) return null;
    var q = new URLSearchParams(raw), out = {}, any = false;
    KEYS.forEach(function (k) { if (q.has(k)) { out[k] = q.get(k); any = true; } });
    if (!any) return null;                       // 다른 쓰임의 해시 — 건드리지 않는다
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* file:// 따위 */ }
    return out;
  }

  function store(seed) {
    var layer = seed ? Object.assign({}, seed) : null;
    return {
      shared: !!layer,
      get: function (key) {
        if (layer && Object.prototype.hasOwnProperty.call(layer, key)) return layer[key];
        try { return localStorage.getItem(key); } catch (e) { return null; }
      },
      set: function (key, value) {
        if (layer) { layer[key] = String(value); return; }
        try { localStorage.setItem(key, String(value)); } catch (e) { /* 사생활 모드 */ }
      },
      remove: function (key) {
        if (layer) { layer[key] = null; return; }
        try { localStorage.removeItem(key); } catch (e) { /* 사생활 모드 */ }
      },
    };
  }

  function link(values) {
    var q = new URLSearchParams();
    Object.keys(values).forEach(function (k) {
      var v = values[k];
      if (v !== null && v !== undefined && v !== "") q.set(k, String(v));
    });
    // 쉼표·별표는 그대로 둔다 — 사람이 읽고 손으로 고칠 수 있게
    var hash = q.toString().replace(/%2C/gi, ",").replace(/%2A/gi, "*").replace(/%3A/gi, ":");
    return location.origin + location.pathname + location.search + "#" + hash;
  }

  function layers(text) {
    if (!text) return [];
    return text.split(",").filter(Boolean).map(function (part) {
      var at = part.lastIndexOf("*"), name = at > 0 ? part.slice(0, at) : part;
      var pct = at > 0 ? parseFloat(part.slice(at + 1)) : 100;
      return { name: name, opacity: isFinite(pct) ? Math.min(1, Math.max(0, pct / 100)) : 1 };
    });
  }

  function pack(list) {
    return list.map(function (e) { return e.name + "*" + Math.round((isFinite(e.opacity) ? e.opacity : 1) * 100); }).join(",");
  }

  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return fallback(text); });
    }
    return Promise.resolve(fallback(text));
  }

  function fallback(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "-1000px";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    area.remove();
    return ok;
  }

  function notice(text, back) {
    var bar = document.createElement("div");
    bar.className = "share-notice";
    bar.setAttribute("role", "status");
    var span = document.createElement("span");
    span.textContent = text;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = back;
    btn.addEventListener("click", function () { location.reload(); });
    var x = document.createElement("button");
    x.type = "button";
    x.className = "share-notice-x";
    x.textContent = "×";
    x.setAttribute("aria-label", "×");
    x.addEventListener("click", function () { bar.remove(); });
    bar.appendChild(span);
    bar.appendChild(btn);
    bar.appendChild(x);
    (document.getElementById("map-wrap") || document.body).appendChild(bar);
    return bar;
  }

  function toast(text) {
    var old = document.querySelector(".share-toast");
    if (old) old.remove();
    var bar = document.createElement("div");
    bar.className = "share-toast";
    bar.setAttribute("role", "status");
    bar.textContent = text;
    (document.getElementById("map-wrap") || document.body).appendChild(bar);
    setTimeout(function () { bar.remove(); }, 1600);
  }

  function wire(button, make, words) {
    if (!button) return;
    var label = button.querySelector("span"), was = label ? label.textContent : "";
    button.addEventListener("click", function () {
      var url = make();
      copy(url).then(function (ok) {
        if (!ok) { window.prompt(words.ask, url); return; }     // 복사가 막힌 곳 — 사람이 골라 복사한다
        // 이름표가 숨은 곳(휴대폰의 툴바)에서는 띠로 알린다 (wetherilli 342)
        if (!label || label.offsetParent === null) { toast(words.done); return; }
        label.textContent = words.done;
        button.classList.add("on");
        setTimeout(function () { label.textContent = was; button.classList.remove("on"); }, 1600);
      });
    });
  }

  window.GSMShare = { read: read, store: store, link: link, copy: copy, layers: layers, pack: pack, notice: notice, wire: wire };
})();
