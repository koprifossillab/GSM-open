/* 대돌여지도 — 관리 화면 (wetherilli P08·118).
 *
 * 지금은 두 가지다. 기능이 늘면 탭을 더한다.
 *   - 개인 레이어 반입 — 양식(docs/개인레이어_양식.md)에 맞춘 JSON·CSV 를 읽어 보여 주고, 저장하면
 *     이 브라우저의 IndexedDB 에 둔다(`personal.js`). 서버로 보내지 않는다
 *   - 저장 자료 관리 — 개인 레이어와 이 브라우저의 설정(localStorage `gsm.*`)을 보고 지운다
 *
 * 지도(map.js)는 같은 저장소를 읽는다. 여기서 바꾸면 열린 지도 창이 따라온다(BroadcastChannel).
 */
(function () {
  "use strict";

  var P = window.GSMPersonal;
  var LANG = document.documentElement.lang === "en" ? "en" : "ko";
  var I18N = JSON.parse((document.getElementById("i18n-data") || {}).textContent || "{}");

  function T(text, vars) {
    var out = (LANG === "en" && I18N[text]) || text;
    if (vars) out = out.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; });
    return out;
  }
  P.setTranslator(T);
  P.configure({
    proxy: document.body.dataset.linkedProxy === "1" ? location.pathname.replace(/manage\/?$/, "") + "linked/fetch/" : "",
    csrf: function () { var i = document.querySelector("#csrf-form [name=csrfmiddlewaretoken]"); return i ? i.value : ""; },
  });

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function msg(id, text, kind) {
    var m = $(id);
    m.textContent = text || "";
    m.className = "msg" + (kind ? " " + kind : "");
  }
  function bytes(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / 1024 / 1024).toFixed(1) + " MB";
  }
  /** ISO 시각 -> 이 브라우저의 시각 "YYYY-MM-DD HH:MM". 저장은 UTC 로 한다. */
  function localTime(iso) {
    var d = new Date(iso || "");
    if (isNaN(d)) return "";
    function two(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + two(d.getMonth() + 1) + "-" + two(d.getDate()) + " " + two(d.getHours()) + ":" + two(d.getMinutes());
  }
  function kindText(kind) { return kind === "polygon" ? T("면") : kind === "line" ? T("선") : T("점"); }

  /** "점 46 · 선 6 · 면 27" — 섞인 것을 읽었을 때 */
  function kindsText(kinds) {
    return ["point", "line", "polygon"].filter(function (k) { return kinds[k]; })
      .map(function (k) { return kindText(k) + " " + kinds[k]; }).join(" · ");
  }

  function download(name, text, type) {
    var blob = new Blob([text], { type: type });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }
  function fileStem(name) {
    return String(name || "layer").replace(/[\\/:*?"<>|]+/g, "_").slice(0, 80);
  }

  // ── 모양 — 지도에서 고른 테마·글꼴을 따른다 ──────────────────────

  [["data-theme", "gsm.theme", "brown"], ["data-font", "gsm.font", "sans"], ["data-size", "gsm.size", "m"]]
    .forEach(function (spec) {
      var v = null;
      try { v = localStorage.getItem(spec[1]); } catch (e) { /* 사생활 모드 */ }
      document.documentElement.setAttribute(spec[0], v || spec[2]);
    });

  // ── 탭 ──────────────────────────────────────────────────────────

  var TAB_KEY = "gsm.manage.tab";
  function showTab(name) {
    document.querySelectorAll(".mg-tab").forEach(function (b) { b.classList.toggle("on", b.dataset.tab === name); });
    document.querySelectorAll(".mg-body").forEach(function (s) { s.classList.toggle("on", s.id === "tab-" + name); });
    try { localStorage.setItem(TAB_KEY, name); } catch (e) { /* 사생활 모드 */ }
    if (name === "stored") renderStored();
  }
  document.querySelectorAll(".mg-tab").forEach(function (b) {
    b.addEventListener("click", function () { showTab(b.dataset.tab); });
  });

  // ── 반입 ────────────────────────────────────────────────────────

  var pending = null;    // 읽었으나 아직 저장하지 않은 것 { parsed, file } 또는 { parsed, link, via, editId }

  function readFile(file) {
    msg("mg-read-msg", T("읽는 중…"));
    $("mg-preview").hidden = true;
    pending = null;
    file.arrayBuffer().then(function (buf) {
      var d = P.decode(buf);
      var parsed = P.parse(d.text, file.name);
      parsed.encoding = d.encoding;
      pending = { parsed: parsed, file: file };
      msg("mg-read-msg", "");
      preview();
    }).catch(function (e) {
      msg("mg-read-msg", T("읽지 못했다 — {why}", { why: e.message || e }), "bad");
    });
  }

  $("mg-file").addEventListener("change", function () {
    if (this.files[0]) readFile(this.files[0]);
    this.value = "";
  });
  var drop = $("mg-drop");
  ["dragenter", "dragover"].forEach(function (t) {
    drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add("over"); });
  });
  ["dragleave", "drop"].forEach(function (t) {
    drop.addEventListener(t, function () { drop.classList.remove("over"); });
  });
  drop.addEventListener("drop", function (e) {
    e.preventDefault();
    var f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) readFile(f);
  });

  function preview() {
    var p = pending.parsed, file = pending.file, link = pending.link;
    $("mg-preview").hidden = false;
    var source = file ? file.name + " · " + bytes(file.size) : hostOf(link.url) + " · " + viaText(pending.via);
    $("mg-file-name").textContent = source + " · " + p.format.toUpperCase() +
      (p.format === "csv" ? " · " + p.encoding.toUpperCase() : "");
    var keep = pending.keep || {};
    $("mg-name").value = keep.name || p.name || (file ? file.name.replace(/\.[^.]+$/, "") : hostOf(link.url));
    $("mg-color").value = keep.color || (/^#[0-9a-f]{6}$/i.test(p.meta.color || "") ? p.meta.color
      : P.PALETTE[Math.floor(Math.random() * (P.PALETTE.length - 1))]);

    var label = $("mg-label");
    label.innerHTML = "";
    label.appendChild(new Option(T("없음"), ""));
    p.columns.forEach(function (c) { label.appendChild(new Option(c.label === c.key ? c.key : c.label + " (" + c.key + ")", c.key)); });
    label.value = keep.label !== undefined ? keep.label : (p.meta.label || "");

    var stats = $("mg-stats");
    stats.innerHTML = "";
    var rows = [
      [T("종류"), p.kind === "mixed"
        ? T("{kinds} — 모양마다 레이어 {n}개로 나눈다", { kinds: kindsText(p.kinds), n: P.split(p).length })
        : T("{kind} 레이어", { kind: kindText(p.kind) })],
      [T("행"), String(p.count)],
      [T("지도에 뜨는 것"), String(p.drawn)],
      [T("좌표가 없는 것"), p.undrawn ? T("{n}행 — 속성은 남긴다", { n: p.undrawn }) : "0"],
    ];
    if (p.meta.source) rows.push([T("출처"), p.meta.source]);
    if (p.meta.license) rows.push([T("이용 조건"), p.meta.license]);
    if (p.meta.description) rows.push([T("설명"), p.meta.description]);
    rows.forEach(function (r) {
      stats.appendChild(el("dt", "", r[0]));
      stats.appendChild(el("dd", "", r[1]));
    });

    var notes = $("mg-notes");
    notes.innerHTML = "";
    if (p.warnings.length) notes.appendChild(noteList(T("경고"), p.warnings, "warn-list"));
    if (p.problems.length) notes.appendChild(noteList(T("읽지 못한 것 {n}건", { n: p.problems.length }), p.problems, "bad-list"));

    $("mg-col-count").textContent = p.columns.length;
    var ct = $("mg-columns");
    ct.innerHTML = "<thead><tr><th>key</th><th>" + esc(T("이름")) + "</th><th>" + esc(T("형식")) + "</th><th>" +
      esc(T("설명")) + "</th></tr></thead>";
    var body = el("tbody");
    p.columns.forEach(function (c) {
      var tr = el("tr");
      [c.key, c.label, c.type, c.note].forEach(function (v, i) { tr.appendChild(el("td", i === 0 || i === 2 ? "mono" : "", v || "")); });
      body.appendChild(tr);
    });
    ct.appendChild(body);

    var rt = $("mg-rows");
    var shown = p.columns.slice(0, 12);
    var head = "<thead><tr><th>" + esc(T("좌표")) + "</th>" + shown.map(function (c) { return "<th>" + esc(c.label) + "</th>"; }).join("") + "</tr></thead>";
    rt.innerHTML = head;
    var rb = el("tbody");
    p.features.slice(0, 8).forEach(function (f) {
      var tr = el("tr");
      tr.appendChild(el("td", "mono", geomText(f.geometry)));
      shown.forEach(function (c) { var v = f.properties[c.key]; tr.appendChild(el("td", "", v === null || v === undefined ? "" : String(v))); });
      rb.appendChild(tr);
    });
    rt.appendChild(rb);
    msg("mg-save-msg", "");
    checkSize();
  }

  /** 저장하기 전에 크기와 자리를 잰다 (wetherilli 131). 자리가 없으면 저장 단추를 막는다 */
  function checkSize() {
    var host = $("mg-size-check");
    host.innerHTML = "";
    $("mg-save").disabled = false;
    var recs = P.split(pending.parsed).map(function (part) {
      var r = P.record(part, pending.file);
      r.name = $("mg-name").value.trim() || r.name;
      if (pending.link) r.link = pending.link;
      return r;
    });
    P.checkBeforeSave(recs).then(function (c) {
      var line = el("div", "mg-size-line");
      line.appendChild(el("span", "", T("저장하면 {size}", { size: P.formatBytes(c.bytes) })));
      host.appendChild(line);
      c.warnings.forEach(function (w) { host.appendChild(el("div", "mg-cap-warn " + w.level, w.text)); });
      if (!c.room) $("mg-save").disabled = true;
    });
  }

  function geomText(g) {
    if (!g) return "—";
    if (g.type === "Point") return g.coordinates[1].toFixed(5) + ", " + g.coordinates[0].toFixed(5);
    return g.type;
  }

  function noteList(title, items, cls) {
    var box = el("div", "mg-note " + cls);
    box.appendChild(el("b", "", title));
    var ul = el("ul");
    items.slice(0, 30).forEach(function (t) { ul.appendChild(el("li", "", t)); });
    if (items.length > 30) ul.appendChild(el("li", "more", T("…외 {n}건", { n: items.length - 30 })));
    box.appendChild(ul);
    return box;
  }

  $("mg-save").addEventListener("click", function () {
    if (!pending) return;
    // 섞여 왔으면 모양마다 한 레이어 (wetherilli 126). 연결이면 같은 `linkGroup` 으로 묶어 한 번 받아 함께 덮는다
    var parts = P.split(pending.parsed);
    var base = $("mg-name").value.trim();
    var old = pending.editRecs || [];          // 고치는 연결의 옛 기록들
    var group = pending.link ? (old.length ? (old[0].linkGroup || old[0].id) : "lg-" + Date.now().toString(36)) : null;
    var recs = parts.map(function (part) {
      var rec = P.record(part, pending.file);
      var name = base || rec.name;
      rec.baseName = name;
      rec.name = parts.length > 1 ? T("{name} — {kind}", { name: name, kind: kindText(part.kind) }) : name;
      rec.color = $("mg-color").value;
      rec.label = $("mg-label").value;
      if (pending.link) {
        rec.link = pending.link;
        rec.linkGroup = group;
        rec.linkPart = part.kind;
        P.applyFetched(rec, { parsed: pending.parsed, via: pending.via });
        // 고친 연결 — 같은 모양의 옛 기록 자리를 잇는다(켜고 끈 것·반입한 날)
        var before = old.filter(function (r) { return (r.linkPart || r.kind) === part.kind; })[0];
        if (before) {
          rec.id = before.id;
          rec.visible = before.visible;
          rec.imported = before.imported || rec.imported;
        }
      }
      return rec;
    });
    var keep = recs.map(function (r) { return r.id; });
    var gone = old.filter(function (r) { return keep.indexOf(r.id) < 0; });
    $("mg-save").disabled = true;
    Promise.all(gone.map(function (r) { return P.remove(r.id); }))
      .then(function () { return Promise.all(recs.map(function (r) { return P.put(r); })); })
      .then(function () {
        linkEditing(null);
        $("mg-save").disabled = false;
        msg("mg-save-msg", recs.length > 1
          ? T("'{name}' 을 레이어 {n}개로 저장했다. 지도의 개인 레이어에 뜬다.", { name: base || recs[0].baseName, n: recs.length })
          : T("'{name}' 을 저장했다. 지도의 개인 레이어에 뜬다.", { name: recs[0].name }), "good");
        pending = null;
        requestPersist(false);
      }).catch(function (e) {
        $("mg-save").disabled = false;
        msg("mg-save-msg", T("저장하지 못했다 — {why}", { why: e && e.message ? e.message : e }), "bad");
      });
  });
  $("mg-discard").addEventListener("click", function () {
    pending = null;
    $("mg-preview").hidden = true;
  });

  // ── API 로 잇기 (wetherilli P09·122) ────────────────────────────

  function hostOf(url) { try { return new URL(url).host; } catch (e) { return String(url || ""); } }
  function viaText(via) { return via === "server" ? T("우리 서버를 거쳐 받았다") : T("곧장 받았다"); }

  var editing = null;      // 연결을 고치는 기록
  var editingRecs = [];    // 그 연결에서 나온 기록들(모양마다 하나)
  function linkEditing(rec) {
    editing = rec;
    if (!rec) editingRecs = [];
    $("mg-link-editing").textContent = rec ? T("'{name}' 의 연결을 고친다", { name: rec.name }) : "";
  }

  function syncMode() {
    var mode = $("mg-link-mode").value;
    $("mg-link-name-wrap").hidden = !(mode === "header" || mode === "query");
    $("mg-link-key-wrap").hidden = mode === "none";
  }
  $("mg-link-mode").addEventListener("change", syncMode);

  function readLinkForm() {
    return {
      url: $("mg-link-url").value.trim(),
      auth: { mode: $("mg-link-mode").value, name: $("mg-link-name").value.trim(), key: $("mg-link-key").value },
    };
  }

  $("mg-link-try").addEventListener("click", function () {
    var link;
    try { link = P.checkLink(readLinkForm()); } catch (e) { msg("mg-link-msg", e.message, "bad"); return; }
    $("mg-link-try").disabled = true;
    msg("mg-link-msg", T("받는 중…"));
    $("mg-preview").hidden = true;
    P.fetchLinked(link).then(function (got) {
      $("mg-link-try").disabled = false;
      if (got.url && got.url !== link.url) {
        // API 의 목차 주소를 넣었다 — 거기서 찾은 자료 주소로 잇는다 (wetherilli 129)
        link.url = got.url;
        $("mg-link-url").value = got.url;
        msg("mg-link-msg", T("API 의 목차라 자료 주소를 찾아 이었다 — {url}", { url: got.url }) + " · " + viaText(got.via), "good");
      } else {
        msg("mg-link-msg", viaText(got.via), "good");
      }
      pending = { parsed: got.parsed, link: link, via: got.via,
                  editRecs: editing ? editingRecs : [],
                  keep: editing ? { name: editing.baseName || editing.name, color: editing.color, label: editing.label,
                                    visible: editing.visible, imported: editing.imported } : {} };
      preview();
    }).catch(function (e) {
      $("mg-link-try").disabled = false;
      msg("mg-link-msg", T("받지 못했다 — {why}", { why: (e && e.message) || e }), "bad");
    });
  });

  /** 이 기록과 같은 연결에서 나온 기록들 */
  function groupOf(rec) {
    var key = rec.linkGroup || rec.id;
    return P.list().then(function (all) {
      return all.filter(function (r) { return r.link && (r.linkGroup || r.id) === key; });
    });
  }

  function editLink(rec) {
    showTab("import");
    $("mg-link-url").value = rec.link.url;
    $("mg-link-mode").value = rec.link.auth.mode;
    $("mg-link-name").value = rec.link.auth.name || "";
    $("mg-link-key").value = rec.link.auth.key || "";
    syncMode();
    groupOf(rec).then(function (recs) { editingRecs = recs; });
    linkEditing(rec);
    msg("mg-link-msg", "");
    $("mg-link-box").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ── 양식 예시 (wetherilli 130) ──────────────────────────────────
  //
  // 반입 탭에 펼쳐 보인다. 글은 **내려받기·반입과 같은 코드**(`P.toCSV`·`P.toGeoJSON`)로 만든다 — 손으로 적은 예시는
  // 읽개가 바뀌면 어긋난다. "이 예시로 읽어 본다" 는 그 글을 반입처럼 읽혀 미리 보기에 띄운다.

  var SAMPLE = {
    name: T("예시 — 내 시료 위치"),
    source: T("손으로 적은 예시"),
    columns: [
      { key: "name", label: T("시료 번호"), type: "string" },
      { key: "rock", label: T("암석"), type: "string" },
      { key: "age_ma", label: T("연대 (Ma)"), type: "number", note: T("U-Pb 저어콘") },
    ],
  };
  function sampleLayer(kind) {
    var feats = kind === "point" ? [
      { id: "S-01", geometry: { type: "Point", coordinates: [127.0276, 37.4979] }, properties: { name: "S-01", rock: T("화강암"), age_ma: 172.4 } },
      { id: "S-02", geometry: { type: "Point", coordinates: [128.5912, 35.8714] }, properties: { name: "S-02", rock: T("편마암"), age_ma: null } },
      { id: "S-03", geometry: null, properties: { name: "S-03", rock: T("사암"), age_ma: null } },
    ] : kind === "line" ? [
      { id: "T-1", geometry: { type: "LineString", coordinates: [[128.10, 36.65], [128.12, 36.66], [128.15, 36.66]] },
        properties: { name: T("노두 단면 1"), rock: T("석회암"), age_ma: 509 } },
    ] : [
      { id: "A", geometry: { type: "Polygon", coordinates: [[[126.9, 37.5], [127.1, 37.5], [127.1, 37.6], [126.9, 37.6], [126.9, 37.5]]] },
        properties: { name: "A", rock: T("화강암"), age_ma: 172.4 } },
    ];
    return {
      name: SAMPLE.name, kind: kind, color: P.DEFAULT_COLOR,
      meta: { name: SAMPLE.name, source: SAMPLE.source, label: "name", created: new Date().toISOString().slice(0, 10) },
      columns: SAMPLE.columns,
      features: feats.map(function (f) { return { type: "Feature", id: f.id, geometry: f.geometry, properties: f.properties }; }),
    };
  }

  /** JSON 을 사람이 읽기 좋게 — 머리는 펼치고, 열 설명·피처는 한 줄에 하나. */
  function prettyJSON(doc) {
    var head = doc.gsm, cols = head.columns;
    var h = {};
    Object.keys(head).forEach(function (k) { if (k !== "columns") h[k] = head[k]; });
    var lines = ['{', '  "type": "FeatureCollection",', '  "gsm": {'];
    Object.keys(h).forEach(function (k) { lines.push("    " + JSON.stringify(k) + ": " + JSON.stringify(h[k]) + ","); });
    lines.push('    "columns": [');
    cols.forEach(function (c, i) { lines.push("      " + JSON.stringify(c) + (i < cols.length - 1 ? "," : "")); });
    lines.push("    ]", "  },", '  "features": [');
    doc.features.forEach(function (f, i) { lines.push("    " + JSON.stringify(f) + (i < doc.features.length - 1 ? "," : "")); });
    lines.push("  ]", "}");
    return lines.join("\n") + "\n";
  }

  var exKind = "point", exFormat = "csv";
  /** 본문 — CSV 거나 JSON. API 탭도 본문은 JSON 이다 */
  function exampleBody() {
    var layer = sampleLayer(exKind);
    return exFormat === "csv" ? P.toCSV(layer).replace(/^\uFEFF/, "").replace(/\r\n/g, "\n") : prettyJSON(P.toGeoJSON(layer));
  }
  /** API 탭 — 상대 사이트가 받을 요청과 돌려줄 응답 한 쌍. 본문은 JSON 예시 그대로다 */
  function exampleApi() {
    return [
      "# " + T("요청 — 우리가 보낸다. 인증키는 연결할 때 고른 꼴 하나로 싣는다"),
      "GET /api/v1/samples/ HTTP/1.1",
      "Host: api.example.org",
      "Accept: application/geo+json, application/json, text/csv",
      "X-API-Key: <" + T("인증키") + ">        # " + T("머리 — 이름은 상대가 정한다"),
      "#   Authorization: Bearer <" + T("인증키") + ">   # Bearer",
      "#   GET /api/v1/samples/?apikey=<" + T("인증키") + ">   # " + T("주소 뒤"),
      "",
      "# " + T("응답 — 상대가 돌려준다. 본문은 양식 그대로(JSON 또는 CSV)"),
      "HTTP/1.1 200 OK",
      "Content-Type: application/geo+json",
      "Access-Control-Allow-Origin: *                # " + T("열어 주면 브라우저가 곧장 받는다(권함)"),
      "Access-Control-Allow-Headers: X-API-Key",
      "",
      "",
    ].join("\n") + exampleBody();
  }
  function exampleText() { return exFormat === "api" ? exampleApi() : exampleBody(); }

  var NOTES = {
    csv: [
      T("맨 위 <code>#열쇠: 값</code> 줄이 머리다 — <code>name</code>(레이어 이름)·<code>source</code>(출처)·<code>label</code>(이름표로 쓸 열)·<code>color</code> 따위. 없어도 읽는다"),
      T("<code>#column: 열 | 화면 이름 | 형식 | 설명</code> — 형식은 <code>string</code>·<code>integer</code>·<code>number</code>"),
      T("그다음 줄이 열 이름이다. 점은 <code>lon</code>·<code>lat</code>(WGS84 십진도), 선·면은 <code>geometry</code> 칸에 WKT"),
      T("빈 칸은 값이 없는 것이다. 좌표가 빈 행도 버리지 않는다 — 지도에만 안 뜬다"),
      T("UTF-8 로 저장한다. 한국어 엑셀의 EUC-KR 도 읽는다"),
    ],
    api: [
      T("<code>GET</code> 한 번에 이 양식의 JSON(또는 CSV)을 통째로 준다. 200 이 아니면 받지 못한 것으로 본다 — 401·403 이면 인증키를 보라고 알린다"),
      T("인증키는 넷 가운데 하나 — 없음, <code>Authorization: Bearer</code>, 머리(이름은 상대가 정한다), 주소 뒤 <code>?이름=키</code>"),
      T("CORS 를 열어 주면(<code>Access-Control-Allow-Origin</code>, 머리로 키를 받으면 <code>Access-Control-Allow-Headers</code> 에 그 이름) 보는 사람의 브라우저가 곧장 받는다. 열지 않으면 우리 서버가 대신 받는다"),
      T("IP 로 막는 API 는 우리 서버(극지연구소)의 IP 를 열어 준다 — 그때는 늘 우리 서버가 받는다"),
      T("20 MB · 20 초 안에 끝나야 한다. 넘겨주기는 세 번까지, 다른 호스트로 넘기면 키를 싣지 않는다"),
      T("목차(<code>endpoints</code> 의 <code>url</code>)를 주는 주소를 넣어도 같은 호스트의 자료 주소를 찾아간다. 피처 하나(<code>Feature</code>)도 받는다"),
    ],
    json: [
      T("GeoJSON <code>FeatureCollection</code> 에 <code>gsm</code> 머리를 더한 것이다. QGIS 따위는 <code>gsm</code> 을 모르고 넘긴다"),
      T("<code>gsm.columns</code> 는 열마다 <code>key</code>·<code>label</code>·<code>type</code>·<code>note</code>"),
      T("좌표는 <code>[경도, 위도]</code> 차례다. <code>geometry</code> 가 <code>null</code> 이면 좌표를 모르는 행이다"),
      T("<code>id</code> 는 원본의 번호다 — 있으면 내려받을 때 그대로 나간다"),
    ],
  };

  function renderExample() {
    document.querySelectorAll("#mg-ex-kind button").forEach(function (b) { b.classList.toggle("on", b.dataset.kind === exKind); });
    document.querySelectorAll("#mg-ex-format button").forEach(function (b) { b.classList.toggle("on", b.dataset.format === exFormat); });
    $("mg-ex-text").textContent = exampleText();
    $("mg-ex-notes").innerHTML = NOTES[exFormat].map(function (t) { return "<li>" + t + "</li>"; }).join("");
  }
  document.querySelectorAll("#mg-ex-kind button").forEach(function (b) {
    b.addEventListener("click", function () { exKind = b.dataset.kind; renderExample(); });
  });
  document.querySelectorAll("#mg-ex-format button").forEach(function (b) {
    b.addEventListener("click", function () { exFormat = b.dataset.format; renderExample(); });
  });
  $("mg-ex-copy").addEventListener("click", function () {
    var btn = this, text = exampleText();
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () {
      btn.textContent = T("복사했다");
      setTimeout(function () { btn.textContent = T("복사"); }, 900);
    }, function () {
      var range = document.createRange();
      range.selectNodeContents($("mg-ex-text"));
      var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
    });
  });
  $("mg-ex-download").addEventListener("click", function () {
    var layer = sampleLayer(exKind);
    if (exFormat === "csv") download("gsm-sample-" + exKind + ".csv", P.toCSV(layer), "text/csv;charset=utf-8");
    else download("gsm-sample-" + exKind + ".json", exampleBody(), "application/json");      // API 탭은 응답 본문
  });
  $("mg-ex-try").addEventListener("click", function () {
    var csv = exFormat === "csv";
    var name = "gsm-sample-" + exKind + "." + (csv ? "csv" : "json");
    readFile(new File([exampleBody()], name, { type: csv ? "text/csv" : "application/json" }));
    $("mg-preview").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  renderExample();
  $("mg-link-example").addEventListener("click", function () {
    exFormat = "api";
    renderExample();
    $("mg-example-box").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  // ── 저장 자료 관리 ──────────────────────────────────────────────

  function renderStored() {
    P.list().then(function (layers) {
      $("mg-count").textContent = layers.length;
      var table = $("mg-layers");
      table.innerHTML = "";
      if (!layers.length) {
        table.innerHTML = '<tbody><tr><td class="empty">' + esc(T("저장한 개인 레이어가 없다")) + "</td></tr></tbody>";
      } else {
        table.innerHTML = "<thead><tr><th></th><th>" + [T("이름"), T("종류"), T("행"), T("원본 파일"), T("반입한 날"), T("크기"), ""]
          .map(esc).join("</th><th>") + "</th></tr></thead>";
        var body = el("tbody");
        layers.forEach(function (rec) { body.appendChild(layerRow(rec)); });
        table.appendChild(body);
      }
      renderUsage(layers);
    }).catch(function (e) {
      msg("mg-stored-msg", (e && e.message) || String(e), "bad");
    });
    renderPrefs();
  }

  function layerRow(rec) {
    var tr = el("tr");

    var vis = el("input");
    vis.type = "checkbox";
    vis.checked = rec.visible !== false;
    vis.title = T("지도에 보인다");
    vis.addEventListener("change", function () { rec.visible = vis.checked; P.put(rec); });
    var c0 = el("td"); c0.appendChild(vis); tr.appendChild(c0);

    var nameCell = el("td", "mg-name-cell");
    var color = el("input");
    color.type = "color";
    color.value = rec.color || P.DEFAULT_COLOR;
    color.title = T("색");
    color.addEventListener("change", function () { rec.color = color.value; P.put(rec); });
    var name = el("input");
    name.type = "text";
    name.value = rec.name;
    name.title = T("이름을 고친다");
    name.addEventListener("change", function () {
      rec.name = name.value.trim() || rec.name;
      name.value = rec.name;
      P.put(rec);
    });
    nameCell.appendChild(color);
    nameCell.appendChild(name);
    tr.appendChild(nameCell);

    // 칸마다 머리줄의 이름을 단다 — 휴대폰은 머리줄을 숨기고 줄을 카드로 세워 이 이름을 칸 앞에 적는다(manage.css, wetherilli 369)
    var labelled = function (td, label) { td.dataset.label = label; return td; };
    tr.appendChild(labelled(el("td", "", kindText(rec.kind)), T("종류")));
    tr.appendChild(labelled(el("td", "mono", rec.drawn === rec.count ? String(rec.count) : T("{n} (좌표 {m})", { n: rec.count, m: rec.drawn })), T("행")));
    tr.appendChild(labelled(rec.link ? linkCell(rec) : el("td", "", rec.file ? rec.file.name : ""), T("원본 파일")));
    tr.appendChild(labelled(el("td", "mono", localTime(rec.imported)), T("반입한 날")));
    var size = P.sizeOf(rec);
    var sizeCell = el("td", "mono" + (size > P.LIMITS.layer ? " mg-big" : ""), bytes(size));
    if (size > P.LIMITS.layer) sizeCell.title = T("지도가 느려질 수 있다");
    tr.appendChild(labelled(sizeCell, T("크기")));

    var acts = el("td", "mg-row-acts");
    var json = el("button", "btn quiet", "JSON");
    json.type = "button";
    json.title = T("양식 그대로 내려받는다");
    json.addEventListener("click", function () {
      download(fileStem(rec.name) + ".json", JSON.stringify(P.toGeoJSON(rec), null, 1), "application/json");
    });
    var csv = el("button", "btn quiet", "CSV");
    csv.type = "button";
    csv.title = T("양식 그대로 내려받는다");
    csv.addEventListener("click", function () {
      download(fileStem(rec.name) + ".csv", P.toCSV(rec), "text/csv;charset=utf-8");
    });
    var del = el("button", "btn quiet danger", "×");
    del.type = "button";
    del.title = T("지운다");
    del.addEventListener("click", function () {
      if (!confirm(T("'{name}' 을 이 브라우저에서 지운다. 되살릴 수 없다.", { name: rec.name }))) return;
      P.remove(rec.id).then(renderStored);
    });
    if (rec.link) {
      var again = el("button", "btn quiet", "⟳");
      again.type = "button";
      again.title = T("지금 새로 받는다");
      again.addEventListener("click", function () {
        again.disabled = true;
        groupOf(rec).then(P.refresh).then(renderStored);
      });
      var edit = el("button", "btn quiet", T("연결"));
      edit.type = "button";
      edit.title = T("주소·인증키를 고친다");
      edit.addEventListener("click", function () { editLink(rec); });
      [again, edit].forEach(function (b) { acts.appendChild(b); });
    }
    [json, csv, del].forEach(function (b) { acts.appendChild(b); });
    tr.appendChild(acts);
    return tr;
  }

  /** 연결 레이어의 "원본" 칸 — 호스트와 마지막으로 받은 때·길, 못 받았으면 그 까닭. */
  function linkCell(rec) {
    var td = el("td", "mg-link-cell");
    td.appendChild(el("span", "mg-link-badge", T("연결")));
    td.appendChild(document.createTextNode(" " + hostOf(rec.link.url)));
    var st = rec.status || {};
    var line = st.ok
      ? T("{when} · {via}", { when: localTime(rec.fetched), via: viaText(st.via) })
      : T("받지 못했다 ({when}) — {why} · 마지막으로 받은 것을 보인다", { when: localTime(st.at), why: st.error || "" });
    var small = el("small", st.ok ? "" : "bad", line);
    td.appendChild(small);
    return td;
  }

  /** 용량 — 개인 레이어 합계, 이 사이트가 쓰는 저장소와 한도, 넘은 것의 경고 (wetherilli 131) */
  function renderUsage(layers) {
    P.measure(layers || []).then(function (m) {
      $("mg-usage").textContent = m.quota
        ? T("이 사이트가 쓰는 저장소 {used} / 한도 {quota}", { used: bytes(m.usage), quota: bytes(m.quota) }) : "";
      var host = $("mg-capacity");
      host.innerHTML = "";
      var head = el("div", "mg-cap-head");
      head.appendChild(el("b", "", T("용량")));
      head.appendChild(el("span", "", T("개인 레이어 {total} · 레이어 하나 {layer} 넘으면, 모두 {all} 넘으면 알린다",
        { total: P.formatBytes(m.total), layer: P.formatBytes(P.LIMITS.layer), all: P.formatBytes(P.LIMITS.total) })));
      host.appendChild(head);
      if (m.quota) {
        var ratio = Math.min(1, m.usage / m.quota);
        var bar = el("div", "mg-cap-bar");
        var fill = el("span", ratio >= P.LIMITS.quotaFull ? "bad" : ratio >= P.LIMITS.quotaWarn ? "warn" : "");
        fill.style.width = Math.max(0.5, ratio * 100) + "%";
        bar.appendChild(fill);
        bar.title = T("이 브라우저의 저장소를 {pct}% 썼다 ({used} / {quota})",
          { pct: Math.round(ratio * 100), used: P.formatBytes(m.usage), quota: P.formatBytes(m.quota) });
        host.appendChild(bar);
      }
      m.warnings.forEach(function (w) { host.appendChild(el("div", "mg-cap-warn " + w.level, w.text)); });
    });
    if (navigator.storage.persisted) {
      navigator.storage.persisted().then(function (yes) {
        $("mg-persist-state").textContent = yes ? T("지우지 않게 해 두었다") : T("공간이 모자라면 브라우저가 지울 수 있다");
        $("mg-persist").hidden = yes;
      });
    }
  }

  function requestPersist(loud) {
    if (!navigator.storage || !navigator.storage.persist) {
      if (loud) msg("mg-stored-msg", T("이 브라우저는 청할 수 없다"), "bad");
      return;
    }
    navigator.storage.persist().then(function (ok) {
      if (loud) msg("mg-stored-msg", ok ? T("지우지 않게 해 두었다") : T("브라우저가 받아 주지 않았다 — 즐겨찾기에 넣거나 자주 들어오면 받아 준다"), ok ? "good" : "bad");
      renderUsage();
    });
  }
  $("mg-persist").addEventListener("click", function () { requestPersist(true); });

  $("mg-clear").addEventListener("click", function () {
    if (!confirm(T("개인 레이어를 모두 이 브라우저에서 지운다. 되살릴 수 없다."))) return;
    P.clear().then(renderStored);
  });

  // ── 이 브라우저의 설정 (localStorage gsm.*) ─────────────────────

  var PREF_NAMES = [
    [/^gsm\.(theme|font|size|labs)$/, T("모양 고르기")],
    [/^gsm\.regions?$/, T("지역 탭")],
    [/^gsm\.layers/, T("켠 레이어")],
    [/^gsm\.view/, T("보던 자리")],
    [/^gsm\.basemap/, T("배경지도")],
    [/^gsm\.crs$/, T("좌표계")],
    [/^gsm\.pointsets\.off$/, T("끈 점묶음")],
    [/^gsm\.panelFolded$/, T("패널 접기")],
    [/^gsm\.attitudes$/, T("자세 기호")],
    [/^gsm\.manage\./, T("관리 화면")],
    [/^gsm\.3d\./, T("3D")],
    [/^gsm\.earth\./, T("온 지구")],
    [/^gsm\.moon\./, T("달")],
    [/^gsm\.mars\./, T("화성")],
  ];
  function prefName(key) {
    for (var i = 0; i < PREF_NAMES.length; i++) if (PREF_NAMES[i][0].test(key)) return PREF_NAMES[i][1];
    return "";
  }
  function prefKeys() {
    var keys = [];
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (/^gsm\./.test(k)) keys.push(k);
      }
    } catch (e) { /* 사생활 모드 */ }
    return keys.sort();
  }

  function renderPrefs() {
    var table = $("mg-prefs");
    var keys = prefKeys();
    table.innerHTML = "";
    if (!keys.length) {
      table.innerHTML = '<tbody><tr><td class="empty">' + esc(T("남긴 설정이 없다")) + "</td></tr></tbody>";
      return;
    }
    table.innerHTML = "<thead><tr><th>" + [T("무엇"), T("열쇠"), T("값"), ""].map(esc).join("</th><th>") + "</th></tr></thead>";
    var body = el("tbody");
    keys.forEach(function (k) {
      var v = "";
      try { v = localStorage.getItem(k) || ""; } catch (e) { /* 사생활 모드 */ }
      var tr = el("tr");
      tr.appendChild(el("td", "", prefName(k)));
      tr.appendChild(el("td", "mono", k));
      var val = el("td", "mono mg-val", v.length > 80 ? v.slice(0, 80) + "…" : v);
      val.title = v;
      tr.appendChild(val);
      var td = el("td", "mg-row-acts");
      var del = el("button", "btn quiet danger", "×");
      del.type = "button";
      del.title = T("지운다");
      del.addEventListener("click", function () {
        try { localStorage.removeItem(k); } catch (e) { /* 사생활 모드 */ }
        renderPrefs();
      });
      td.appendChild(del);
      tr.appendChild(td);
      body.appendChild(tr);
    });
    table.appendChild(body);
  }

  $("mg-prefs-clear").addEventListener("click", function () {
    if (!confirm(T("이 브라우저에 남긴 대돌여지도 설정을 모두 지운다. 지도는 처음 모습으로 뜬다."))) return;
    prefKeys().forEach(function (k) { try { localStorage.removeItem(k); } catch (e) { /* 사생활 모드 */ } });
    renderPrefs();
  });

  P.onChange(function () { if ($("tab-stored").classList.contains("on")) renderStored(); });

  // ── 데이터소스 (jikhanjung P02 3 단계) — 줄을 누르면 지난 차례가 펼쳐진다 ─────────────
  // 펼치는 것은 이름 칸의 단추다(키보드·낭독기) — 줄의 다른 곳을 눌러도 같은 일을 한다
  document.querySelectorAll("#mg-sources tr.mg-src").forEach(function (tr) {
    var button = tr.querySelector(".mg-src-toggle");
    function toggle() {
      var more = document.querySelector('#mg-sources tr.mg-src-more[data-for="' + tr.dataset.src + '"]');
      if (!more) return;
      more.hidden = !more.hidden;
      tr.classList.toggle("open", !more.hidden);
      if (button) button.setAttribute("aria-expanded", String(!more.hidden));
    }
    if (button) button.addEventListener("click", toggle);
    tr.addEventListener("click", function (e) {
      if (e.target.closest("a, button")) return;
      toggle();
    });
  });

  var first = "import";
  try { first = localStorage.getItem(TAB_KEY) || "import"; } catch (e) { /* 사생활 모드 */ }
  showTab(/^(import|stored)$/.test(first) ? first : "import");
})();
