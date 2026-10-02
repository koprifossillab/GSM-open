/* 대돌여지도 소개 (wetherilli 113·115).
 *
 * 장면(`section.scene`)마다 무대가 화면에 붙어 있고, 스크롤이 장면 안의 진행 `--p`(0→1)와
 * 단계(`data-step`)를 민다. 단계가 바뀌면 그 단계의 글·그림에 `.on` 을 단다.
 * 지금 장면(또는 단계)이 적은 테마와 목적지를 바탕색과 "지도로 바로 가기" 에 옮긴다.
 *
 * 둥근 지구·달·화성(`canvas.globes`)은 WebGL 로 그린다 — 정거원통 그림 한 장을 구에 감고 빛을 비춘다.
 * 감는 그림은 `deploy/host/intro_globes.py` 가 굽는다. WebGL 이 없으면 그 그림을 동그랗게 오려 둔다.
 *
 * 글은 모두 템플릿이 적는다 — 여기에는 화면 문장이 없다.
 */
(function () {
  "use strict";

  var BASE = location.pathname.replace(/\/*$/, "/");
  var scenes = Array.prototype.slice.call(document.querySelectorAll(".scene, .doors-wrap"));
  var skip = document.getElementById("skip");
  var skipTo = document.getElementById("skip-to");
  var chapters = Array.prototype.slice.call(document.querySelectorAll("#chapters a"));
  var still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var DPR = Math.min(window.devicePixelRatio || 1, 1.5);

  scenes.forEach(function (s) {
    if (s.dataset.steps) s.style.setProperty("--steps", s.dataset.steps);
  });

  // ── 첫 장면의 수십 장 — 다섯 장 뒤에 쏟아진다 ─────────────────────
  //
  // 찍어 둔 화면의 작은 판을 다시 쓴다. 자리는 씨앗을 둔 난수라 열 때마다 같다. 진행 .21 에서 .6 사이에
  // 하나씩 뜨고(`--t`), 화면을 덮을 만큼 쌓인 뒤 다 같이 가운데로 빨려 든다(CSS 의 `--q`).
  // 뜨는 때는 i/N 의 거듭제곱(0.42)이다 — 처음 한두 장은 띄엄띄엄 떨어지고 뒤로 갈수록 훅훅 쏟아진다 (wetherilli 119)
  (function flood() {
    var host = document.querySelector(".papers[data-flood]");
    if (!host) return;
    var names = host.dataset.names.split(/\s+/).filter(Boolean);
    var seed = 7;
    function rnd() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
    var N = 42;
    for (var i = 0; i < N; i++) {
      var f = document.createElement("figure");
      f.className = "paper flood";
      var img = document.createElement("img");
      img.alt = "";
      img.loading = "lazy";
      img.src = host.dataset.flood + names[i % names.length] + ".webp";
      img.style.objectPosition = Math.round(30 + rnd() * 60) + "% " + Math.round(20 + rnd() * 60) + "%";
      f.appendChild(img);
      // 가장자리부터 안쪽까지 고루 — 물음과 마지막 화면이 설 가운데 띠도 결국 덮인다
      var ang = rnd() * Math.PI * 2, rad = .25 + rnd() * .75;
      f.style.cssText = "--x:" + (Math.cos(ang) * rad * 44).toFixed(1) + "vw;--y:" + (Math.sin(ang) * rad * 40).toFixed(1) +
        "vh;--r:" + ((rnd() - .5) * 34).toFixed(1) + "deg;--t:" + (.21 + Math.pow(i / N, .42) * .39).toFixed(3) + ";--z:" + (10 + i);
      host.appendChild(f);
    }
  })();

  /** `data-step="0 1"` 처럼 여러 단계에 걸친 것도 있다. */
  function inStep(el, step) {
    return (" " + el.dataset.step + " ").indexOf(" " + step + " ") >= 0;
  }

  /** 장면 안의 진행 0→1 — 무대가 화면에 붙어 있는 동안만 움직인다. */
  function progress(s) {
    var r = s.getBoundingClientRect();
    var run = r.height - innerHeight;
    if (run <= 0) return r.top < innerHeight / 2 ? 1 : 0;
    return Math.max(0, Math.min(1, -r.top / run));
  }

  var current = null, ticking = false;

  function update() {
    ticking = false;
    var mid = innerHeight / 2, active = scenes[0];
    scenes.forEach(function (s) {
      var r = s.getBoundingClientRect();
      if (r.top <= mid && r.bottom > mid) active = s;
      if (r.bottom < -innerHeight || r.top > innerHeight * 2) return;   // 먼 장면은 셈하지 않는다
      var p = progress(s);
      s._p = p;
      s.style.setProperty("--p", p.toFixed(4));
      var steps = +s.dataset.steps || 0;
      if (!steps) return;
      var step = Math.min(steps - 1, Math.floor(p * steps * 0.999));
      if (s.dataset.step === String(step)) return;
      s.dataset.step = step;
      s.querySelectorAll("[data-step]").forEach(function (el) {
        el.classList.toggle("on", inStep(el, step));
      });
    });
    // 테마·목적지 — 지금 단계의 것이 장면의 것을 이긴다
    var theme = active.dataset.theme, go = active.dataset.go, label = active.dataset.goLabel;
    active.querySelectorAll("[data-step].on").forEach(function (el) {
      if (el.dataset.theme) theme = el.dataset.theme;
      if (el.dataset.go) { go = el.dataset.go; label = el.dataset.goLabel; }
    });
    theme = theme || "korea";
    if (document.body.dataset.theme !== theme) document.body.dataset.theme = theme;
    var href = BASE + (go || "map/");
    if (skip.getAttribute("href") !== href) {
      skip.setAttribute("href", href);
      skipTo.textContent = label || "";
    }
    if (active !== current) {
      current = active;
      // 대기 화면 애니메이션은 들어올 때마다 처음부터 (극지 표지, wetherilli 123)
      active.querySelectorAll("img.replay").forEach(function (img) { var src = img.src; img.src = ""; img.src = src; });
      chapters.forEach(function (a) {
        a.classList.toggle("on", a.dataset.for.split(" ").indexOf(active.id) >= 0);
      });
    }
  }

  function wake() {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }
  addEventListener("scroll", wake, { passive: true });
  addEventListener("resize", wake);
  update();

  // ── 별 ────────────────────────────────────────────────────────────

  function drawStars(c) {
    var w = c.clientWidth, h = c.clientHeight;
    c.width = w * DPR; c.height = h * DPR;
    var g = c.getContext("2d");
    g.scale(DPR, DPR);
    var seed = 3;
    function rnd() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
    var n = Math.round(w * h / 2600);
    for (var i = 0; i < n; i++) {
      var r = rnd() < .92 ? .5 + rnd() * .7 : 1 + rnd() * .9;
      g.globalAlpha = .25 + rnd() * .65;
      g.fillStyle = rnd() < .12 ? "#ffe2b0" : rnd() < .2 ? "#bcd4ff" : "#ffffff";
      g.beginPath(); g.arc(rnd() * w, rnd() * h, r, 0, Math.PI * 2); g.fill();
    }
  }

  // ── 둥근 지구·달·화성 ─────────────────────────────────────────────
  //
  // 구마다 네모 하나를 그리고, 조각 셰이더가 그 안의 점을 구의 겉으로 되짚어 경위도를 셈해 그림을 읽는다.
  // 보이는 반구(z > 0)만 그리므로 경도가 끊기는 자리(뒤쪽)는 보이지 않는다. 돌리는 각은 REPEAT 감기에 맡긴다.

  var VS = "attribute vec2 a;uniform vec3 s;uniform vec2 v;varying vec2 q;" +
    "void main(){q=a;vec2 p=s.xy+a*s.z;gl_Position=vec4(p/v*2.0-1.0,0.0,1.0);gl_Position.y=-gl_Position.y;}";
  var FS = "precision highp float;varying vec2 q;uniform sampler2D t;uniform float spin,tilt,atm,px,dim;" +
    "void main(){float d=length(q);if(d>1.0)discard;" +
    "vec3 n=vec3(q.x,-q.y,sqrt(max(0.0,1.0-d*d)));" +
    "float c=cos(tilt),s=sin(tilt);vec3 m=vec3(n.x*c-n.y*s,n.x*s+n.y*c,n.z);" +
    "float lon=atan(m.x,m.z),lat=asin(clamp(m.y,-1.0,1.0));" +
    "vec3 col=texture2D(t,vec2(lon/6.2831853+0.5+spin,0.5-lat/3.1415927)).rgb;" +
    "vec3 L=normalize(vec3(-0.55,0.38,0.74));float df=max(dot(n,L),0.0);" +
    "col=col*(0.07+1.08*df);" +
    "float rim=pow(1.0-n.z,2.6);col+=atm*rim*vec3(0.35,0.62,1.0)*(0.25+df);" +
    "float a=smoothstep(1.0,1.0-2.0/px,d);gl_FragColor=vec4(col*a*dim,a);}";

  function Globes(canvas) {
    this.canvas = canvas;
    this.tex = {};
    this.ready = false;
    var gl = null;
    try { gl = canvas.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: true }); } catch (e) { /* 없음 */ }
    this.gl = gl;
    var self = this;
    var names = ["earth", "moon", "mars", "mercury"];
    var left = names.length;
    this.imgs = {};
    names.forEach(function (name) {
      var img = new Image();
      img.onload = function () {
        self.imgs[name] = img;
        if (gl) self.upload(name, img);
        if (--left === 0) { self.ready = true; wakeGlobes(); }
      };
      img.src = canvas.dataset[name];
    });
    if (!gl) return;
    function sh(type, src) {
      var o = gl.createShader(type); gl.shaderSource(o, src); gl.compileShader(o);
      if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o));
      return o;
    }
    try {
      var prog = gl.createProgram();
      gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(prog);
      gl.useProgram(prog);
      this.prog = prog;
      var buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
      var loc = gl.getAttribLocation(prog, "a");
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      this.u = {};
      ["s", "v", "t", "spin", "tilt", "atm", "px", "dim"].forEach(function (k) { self.u[k] = gl.getUniformLocation(prog, k); });
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    } catch (e) {
      this.gl = null;
    }
  }
  Globes.prototype.upload = function (name, img) {
    var gl = this.gl, t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.generateMipmap(gl.TEXTURE_2D);
    this.tex[name] = t;
  };
  Globes.prototype.resize = function () {
    var c = this.canvas, w = Math.round(c.clientWidth * DPR), h = Math.round(c.clientHeight * DPR);
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  };
  /** list: [{ body, x, y, r (CSS px), spin (0→1 한 바퀴), tilt (라디안), dim }] — 먼 것(작은 것)부터 그린다. */
  Globes.prototype.draw = function (list) {
    if (!this.ready) return;
    this.resize();
    var c = this.canvas, w = c.width, h = c.height;
    list = list.filter(function (g) { return g.r > 1 && g.dim > .01; }).sort(function (a, b) { return a.r - b.r; });
    var gl = this.gl;
    if (!gl) return this.drawFlat(list);
    gl.viewport(0, 0, w, h);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.uniform2f(this.u.v, w, h);
    for (var i = 0; i < list.length; i++) {
      var g = list[i];
      gl.bindTexture(gl.TEXTURE_2D, this.tex[g.body]);
      gl.uniform3f(this.u.s, g.x * DPR, g.y * DPR, g.r * DPR);
      gl.uniform1f(this.u.spin, g.spin % 1);
      gl.uniform1f(this.u.tilt, g.tilt || 0);
      gl.uniform1f(this.u.atm, g.body === "earth" ? 1.0 : g.body === "mars" ? 0.25 : 0.0);
      gl.uniform1f(this.u.px, g.r * DPR);
      gl.uniform1f(this.u.dim, g.dim);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
  };
  /** WebGL 이 없을 때 — 그림의 가운데를 동그랗게 오려 둔다. 돌지 않는다. */
  Globes.prototype.drawFlat = function (list) {
    var c = this.canvas, g2 = c.getContext("2d");
    g2.setTransform(1, 0, 0, 1, 0, 0);
    g2.clearRect(0, 0, c.width, c.height);
    g2.scale(DPR, DPR);
    var self = this;
    list.forEach(function (g) {
      var img = self.imgs[g.body];
      g2.save(); g2.globalAlpha = g.dim;
      g2.beginPath(); g2.arc(g.x, g.y, g.r, 0, Math.PI * 2); g2.clip();
      g2.drawImage(img, img.width * .25, 0, img.width * .5, img.height, g.x - g.r, g.y - g.r, g.r * 2, g.r * 2);
      g2.restore();
    });
  };

  function ease(t) { t = Math.max(0, Math.min(1, t)); return t * t * (3 - 2 * t); }
  function mix(a, b, t) { return a + (b - a) * t; }

  /** 장면마다 구가 서는 자리. w·h 는 무대의 크기, p 는 장면의 진행, now 는 초. */
  var CHOREO = {
    title: function (w, h, p, now) {
      var lift = p * h * .25;
      if (w < 900) {          // 좁은 화면 — 지구를 위에 크게, 글은 그 아래
        var r = w * .42;
        return [
          { body: "earth", x: w * .58, y: h * .26 - lift, r: r, spin: now / 90, tilt: .41, dim: 1 },
          { body: "moon", x: w * .14, y: h * .14 - lift * 1.4, r: r * .2, spin: now / 140, tilt: .1, dim: 1 },
          { body: "mars", x: w * .12, y: h * .42 - lift * .6, r: r * .12, spin: now / 70, tilt: .44, dim: .95 },
          { body: "mercury", x: w * .9, y: h * .07 - lift * 1.2, r: r * .07, spin: now / 160, tilt: 0, dim: .95 },
        ];
      }
      var R = Math.min(h * .41, w * .28);
      return [
        { body: "earth", x: w * .73, y: h * .54 - lift, r: R, spin: now / 90, tilt: .41, dim: 1 },
        { body: "moon", x: w * .9, y: h * .2 - lift * 1.4, r: R * .2, spin: now / 140, tilt: .1, dim: 1 },
        { body: "mars", x: w * .46, y: h * .86 - lift * .6, r: R * .13, spin: now / 70, tilt: .44, dim: .95 },
        { body: "mercury", x: w * .58, y: h * .12 - lift * 1.2, r: R * .08, spin: now / 160, tilt: 0, dim: .95 },
      ];
    },
    space: function (w, h, p, now) {
      // 지구가 물러남 · 달이 다가옴 · 화성이 다가옴 · 수성이 다가옴 — 멈출 자리(⅛·⅜·⅝·⅞)에 닿기 전에 끝나게
      // (wetherilli 146 — 수성이 넷째 단계로 들어왔다)
      var a = ease((p - .03) / .22), b = ease((p - .16) / .18), c = ease((p - .42) / .18), d = ease((p - .67) / .18);
      var R = Math.min(h * .4, w * .28);
      return [
        { body: "earth", x: mix(w * .7, w * .1, a), y: mix(h * .5, h * .86, a), r: mix(R, R * .14, a),
          spin: now / 90, tilt: .41, dim: mix(1, .85, a) },
        { body: "moon", x: mix(mix(w * .86, w * .68, b), w * .2, c), y: mix(mix(h * .22, h * .46, b), h * .18, c),
          r: mix(mix(R * .12, R * 1.05, b), R * .2, c), spin: now / 120, tilt: .1, dim: 1 },
        { body: "mars", x: mix(mix(mix(w * .93, w * .88, b), w * .68, c), w * .36, d),
          y: mix(mix(mix(h * .7, h * .78, b), h * .46, c), h * .14, d),
          r: mix(mix(mix(R * .07, R * .16, b), R * 1.05, c), R * .16, d), spin: now / 60, tilt: .44, dim: 1 },
        // 수성은 자전이 느리다(공전 두 번에 세 바퀴) — 천천히 돈다
        { body: "mercury", x: mix(mix(w * .97, w * .9, c), w * .68, d), y: mix(mix(h * .12, h * .2, c), h * .46, d),
          r: mix(mix(R * .04, R * .1, c), R * 1.05, d), spin: now / 160, tilt: 0, dim: 1 },
      ];
    },
  };

  var globeSets = Array.prototype.slice.call(document.querySelectorAll("canvas.globes")).map(function (c) {
    return { canvas: c, scene: c.closest(".scene"), g: new Globes(c), choreo: CHOREO[c.dataset.scene] };
  });
  var starCanvases = Array.prototype.slice.call(document.querySelectorAll("canvas.stars"));
  function paintStars() { starCanvases.forEach(drawStars); }
  paintStars();
  addEventListener("resize", paintStars);

  var globeRaf = 0, t0 = performance.now();
  function renderGlobes(now) {
    globeRaf = 0;
    var any = false;
    globeSets.forEach(function (set) {
      var r = set.scene.getBoundingClientRect();
      if (r.bottom < 0 || r.top > innerHeight) return;           // 보이지 않으면 그리지 않는다
      any = true;
      var w = set.canvas.clientWidth, h = set.canvas.clientHeight;
      var sec = still ? 0 : (now - t0) / 1000;
      set.g.draw(set.choreo(w, h, set.scene._p || 0, sec));
    });
    if (any && !still) globeRaf = requestAnimationFrame(renderGlobes);
  }
  function wakeGlobes() { if (!globeRaf) globeRaf = requestAnimationFrame(renderGlobes); }
  addEventListener("scroll", wakeGlobes, { passive: true });
  addEventListener("resize", wakeGlobes);
  wakeGlobes();

  // ── 자동 재생 ──────────────────────────────────────────────────
  //
  // 스크롤하지 않아도 넘어간다. 멈출 자리(stop)는 장면의 단계마다 하나 — 단계 k 의 가운데
  // `(k + .5) / 단계 수` 이고, 움직임이 스크롤에 걸린 장면은 `data-stops` 로 적는다. 그 자리로 가는 데
  // 걸릴 시간을 따로 주려면 `data-durs`(밀리초) — 첫 장면의 수십 장은 천천히 넘어가야 쏟아지는 것이 보인다.
  // 자리마다 **보이는 글의 길이만큼** 머문다(훑을 틈). 장면 첫 자리에 `data-dwell` 이 있으면 그만큼.
  // 사람이 휠·터치·키·스크롤 막대로 움직이면 멈춘다.

  var EN = document.documentElement.lang === "en";
  var play = document.getElementById("play");
  var stops = [];

  function measure() {
    stops = [];
    scenes.forEach(function (s) {
      var top = s.getBoundingClientRect().top + scrollY;
      var run = Math.max(0, s.offsetHeight - innerHeight);
      var steps = +s.dataset.steps || 0;
      var fs = s.dataset.stops ? s.dataset.stops.split(" ").map(Number)
             : steps ? Array.apply(null, Array(steps)).map(function (_, k) { return (k + .5) / steps; })
             : [0];
      var durs = s.dataset.durs ? s.dataset.durs.split(" ").map(Number) : [];
      // `data-holds` — 자리마다 머무는 시간을 박는다(밀리초, `-` 는 글 길이로). 쏟아짐이 끝난 자리는 0 — 바로 모인다
      var holds = s.dataset.holds ? s.dataset.holds.split(" ") : [];
      fs.forEach(function (f, k) {
        stops.push({ scene: s, y: Math.round(top + run * f), dur: durs[k] || 0, first: k === 0,
                     hold: holds[k] && holds[k] !== "-" ? +holds[k] : null });
      });
    });
  }

  /** 그 자리에서 읽을 글자 수로 머무는 시간을 정한다. 한국어는 한 글자가 영어보다 무겁다. */
  function dwell(stop) {
    var s = stop.scene, text = "";
    s.querySelectorAll("h1, h2, h3, p, li, figcaption").forEach(function (el) {
      if (el.closest(".src") || el.closest(".badge") || el.closest(".chips")) return;
      if (!el.offsetParent) return;
      // 단계에 걸린 글은 `.on` 으로 본다 — 막 뜨는 중이라 아직 흐릴 수 있다.
      // 스크롤에 걸린 것(첫 장면의 종이·물음)은 지금의 투명도로 본다
      var gated = el.closest("[data-step]");
      if (gated && gated !== s) { if (!gated.classList.contains("on")) return; }
      else if (+getComputedStyle(el.closest(".paper, .hook-text, .resolve, .title-text") || el).opacity < .5) return;
      text += el.textContent.replace(/\s+/g, " ");
    });
    if (stop.hold !== null) return stop.hold;
    if (s.dataset.dwell && stop.first) return +s.dataset.dwell;
    // 한 장 한 장 들여다보라는 것이 아니다 — 훑고 지나간다. 119 의 1.1~3 초가 조금 빨라 1.4~3.6 초로 (wetherilli 121)
    var ms = 700 + text.length * (EN ? 9 : 18);
    return Math.max(1400, Math.min(3600, ms));
  }

  var playing = false, idx = 0, raf = 0, expectY = null;

  function setPlaying(on) {
    playing = on;
    play.setAttribute("aria-pressed", on ? "true" : "false");
    play.querySelector(".play-label").textContent = on ? play.dataset.pause : play.dataset.play;
    play.style.setProperty("--t", 0);
    cancelAnimationFrame(raf);
    if (on) go(nextIndex());
  }

  /** 지금 자리에서 가장 가까운 앞쪽 멈출 자리. */
  function nextIndex() {
    for (var i = 0; i < stops.length; i++) if (stops[i].y >= scrollY - 4) return i;
    return stops.length - 1;
  }

  function scrollToY(y) {
    expectY = y;
    scrollTo({ top: y, behavior: "instant" });
  }

  /** i 번째 자리로 부드럽게 가서 머문 뒤 다음으로. */
  function go(i) {
    idx = i;
    var from = scrollY, to = stops[i].y, d = to - from;
    var dur = still || !d ? 0 : stops[i].dur || Math.max(480, Math.min(1000, Math.abs(d) / innerHeight * 340));
    var start = performance.now();
    function step(now) {
      var t = dur ? Math.min(1, (now - start) / dur) : 1;
      var e = t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      // 쏟아지는 구간처럼 오래 가는 것은 고르게 — 처음과 끝만 부드럽게
      if (stops[i].dur) e = t;
      scrollToY(Math.round(from + d * e));
      if (t < 1) raf = requestAnimationFrame(step);
      else { update(); stay(); }
    }
    raf = requestAnimationFrame(step);
  }

  function stay() {
    // 끝(갈래)에 닿으면 멈춘다. 머무는 시간이 0 인 자리는 곧장 다음으로
    if (idx >= stops.length - 1) { setPlaying(false); return; }
    var ms = dwell(stops[idx]);
    if (!ms) { go(idx + 1); return; }
    var spent = 0, prev = performance.now();
    function tick(now) {
      if (!document.hidden) spent += now - prev;       // 다른 탭에 있는 동안은 세지 않는다
      prev = now;
      play.style.setProperty("--t", Math.min(1, spent / ms).toFixed(3));
      if (spent >= ms) { play.style.setProperty("--t", 0); go(idx + 1); }
      else raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
  }

  function interrupt() { if (playing) setPlaying(false); }
  addEventListener("wheel", interrupt, { passive: true });
  addEventListener("touchstart", interrupt, { passive: true });
  addEventListener("keydown", function (e) {
    if (["ArrowDown", "ArrowUp", "PageDown", "PageUp", "Home", "End", " "].indexOf(e.key) >= 0) interrupt();
  });
  // 스크롤 막대를 끈 것 — 우리가 민 자리와 다르면 사람이 움직인 것이다
  addEventListener("scroll", function () {
    if (playing && expectY !== null && Math.abs(scrollY - expectY) > 3) interrupt();
  }, { passive: true });
  addEventListener("resize", function () {
    measure();
    if (playing) setPlaying(true);
  });

  play.addEventListener("click", function () {
    if (playing) { setPlaying(false); return; }
    // 끝에서 다시 누르면 처음부터
    if (nextIndex() >= stops.length - 1 && scrollY >= stops[stops.length - 1].y - 4) scrollToY(0);
    setPlaying(true);
  });

  /** 장면의 첫 자리로 간다. 재생 중이면 거기서 이어 간다. */
  function jump(target, e) {
    var i = stops.findIndex(function (st) { return st.scene === target; });
    if (i < 0) return;
    if (e) e.preventDefault();
    cancelAnimationFrame(raf);
    if (playing) { go(i); return; }
    scrollToY(stops[i].y);
  }
  chapters.forEach(function (a) {
    a.addEventListener("click", function (e) { jump(document.getElementById(a.getAttribute("href").slice(1)), e); });
  });
  var tour = document.getElementById("tour");
  if (tour) tour.addEventListener("click", function (e) {
    jump(document.getElementById("hook"), e);
    if (!playing) setPlaying(true);
  });

  // 언어 — 지도 화면과 같은 쿠키다(`gsm_lang`)
  document.querySelectorAll(".langs button").forEach(function (b) {
    b.addEventListener("click", function () {
      document.cookie = "gsm_lang=" + b.dataset.lang + "; path=/; max-age=31536000; SameSite=Lax";
      location.reload();
    });
  });

  measure();
  setPlaying(true);
})();
