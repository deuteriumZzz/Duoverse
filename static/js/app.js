// Motion + small UI helpers. Everything degrades to static content without JS.
(() => {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = matchMedia("(hover: hover) and (pointer: fine)").matches;
  const PALETTE = ["#f2865c", "#5470ee", "#f4c84f", "#7fae8e", "#b9a7f2"];

  /* ── reveal on scroll ── */
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        e.target.classList.add("in");
        if (e.target.matches("[data-count]")) countUp(e.target);
        e.target.querySelectorAll("[data-count]").forEach(countUp);
        if (e.target.matches("[data-roll]")) roll(e.target);
        e.target.querySelectorAll("[data-roll]").forEach(roll);
        if (e.target.matches("[data-burst-in]")) setTimeout(() => burst(e.target, 22), +e.target.dataset.burstIn || 600);
        io.unobserve(e.target);
      }
    },
    { threshold: 0.15, rootMargin: "0px 0px -6% 0px" }
  );

  function countUp(el) {
    if (el.dataset.counted) return;
    el.dataset.counted = "1";
    const to = parseFloat(el.dataset.count);
    if (reduced || Number.isNaN(to)) return void (el.textContent = el.dataset.count);
    const dur = +(el.dataset.dur || 1400), start = performance.now() + +(el.dataset.delay || 0);
    const ease = (t) => 1 - Math.pow(1 - t, 4);
    const tick = (now) => {
      const t = Math.max(0, Math.min(1, (now - start) / dur));
      el.textContent = Math.round(to * ease(t));
      if (t < 1) requestAnimationFrame(tick);
    };
    el.textContent = "0";
    requestAnimationFrame(tick);
  }

  /* ── slot-machine roll for numbers ── */
  function roll(el) {
    if (el.dataset.rolled) return;
    el.dataset.rolled = "1";
    const final = el.dataset.roll, max = +(el.dataset.max || 9);
    if (reduced) return void (el.textContent = final);
    const until = performance.now() + 700 + +(el.dataset.i || 0) * 180;
    const spin = () => {
      if (performance.now() < until) {
        el.textContent = 1 + Math.floor(Math.random() * max);
        return void setTimeout(spin, 55);
      }
      el.textContent = final;
      el.animate([{ scale: 1.35 }, { scale: 1 }], { duration: 500, easing: "cubic-bezier(.34,1.56,.64,1)" });
    };
    spin();
  }

  /* ── split headings into masked words ── */
  function split(el) {
    if (el.dataset.splitDone) return;
    el.dataset.splitDone = "1";
    let i = 0;
    const wrap = (node) => {
      const w = document.createElement("span");
      w.className = "split-w";
      const inner = document.createElement("span");
      inner.style.setProperty("--i", i++);
      inner.append(node);
      w.append(inner);
      return w;
    };
    for (const node of [...el.childNodes]) {
      if (node.nodeType === Node.TEXT_NODE) {
        const frag = document.createDocumentFragment();
        node.textContent.split(/([ \t\n\r]+)/).forEach((part) => {
          if (!part) return;
          frag.append(/^[ \t\n\r]+$/.test(part) ? document.createTextNode(" ") : wrap(document.createTextNode(part)));
        });
        node.replaceWith(frag);
      } else if (node.nodeType === Node.ELEMENT_NODE && node.tagName !== "BR") {
        node.replaceWith(wrap(node.cloneNode(true)));
      }
    }
  }

  /* ── magnetic buttons ── */
  function magnetic(el) {
    if (!finePointer || reduced || el.dataset.magOn) return;
    el.dataset.magOn = "1";
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      el.classList.add("pulling");
      el.style.setProperty("--tx", `${(e.clientX - r.left - r.width / 2) * 0.22}px`);
      el.style.setProperty("--ty", `${(e.clientY - r.top - r.height / 2) * 0.32}px`);
    });
    el.addEventListener("pointerleave", () => {
      el.classList.remove("pulling");
      el.style.setProperty("--tx", "0px");
      el.style.setProperty("--ty", "0px");
    });
  }

  /* ── confetti-like burst from an element ── */
  function burst(el, n = 18) {
    if (reduced || !el) return;
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    for (let k = 0; k < n; k++) {
      const d = document.createElement("i");
      const a = (Math.PI * 2 * k) / n + Math.random() * 0.5;
      const dist = 70 + Math.random() * 110;
      d.className = "burst-dot";
      d.style.cssText = `left:${cx}px;top:${cy}px;--c:${PALETTE[k % PALETTE.length]};--dx:${Math.cos(a) * dist}px;--dy:${Math.sin(a) * dist - 30}px;` +
        `--rot:${Math.random() * 540 - 270}deg;--s:${6 + Math.random() * 7}px;--r:${k % 3 ? "999px" : "3px"};animation-delay:${Math.random() * 80}ms`;
      document.body.append(d);
      setTimeout(() => d.remove(), 1300);
    }
  }

  /* ── pointer-follow parallax (hero blobs, floating chips) ── */
  const followers = new Set();
  let tx = 0, ty = 0, cx = 0, cy = 0, raf = 0;
  function followLoop() {
    cx += (tx - cx) * 0.07;
    cy += (ty - cy) * 0.07;
    followers.forEach((el) => {
      const d = +(el.dataset.follow || 20);
      el.style.translate = `${cx * d}px ${cy * d}px`;
    });
    raf = Math.abs(tx - cx) + Math.abs(ty - cy) > 0.001 ? requestAnimationFrame(followLoop) : 0;
  }
  if (finePointer && !reduced) {
    addEventListener("pointermove", (e) => {
      tx = e.clientX / innerWidth - 0.5;
      ty = e.clientY / innerHeight - 0.5;
      if (!raf && followers.size) raf = requestAnimationFrame(followLoop);
    }, { passive: true });
  }

  /* ── sticky story: which step is centred ── */
  function story(root) {
    const steps = [...root.querySelectorAll("[data-step]")];
    const obs = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        root.dataset.active = e.target.dataset.step;
        steps.forEach((s) => s.classList.toggle("is-active", s === e.target));
      }
    }, { rootMargin: "-45% 0px -45% 0px" });
    steps.forEach((s) => obs.observe(s));
  }

  /* ── category card ↔ radar dot ── */
  function linkRadar(card) {
    const key = card.dataset.catCard;
    card.addEventListener("pointerenter", () => document.querySelectorAll(`[data-cat-dot="${key}"]`).forEach((d) => d.classList.add("hot")));
    card.addEventListener("pointerleave", () => document.querySelectorAll(`[data-cat-dot="${key}"]`).forEach((d) => d.classList.remove("hot")));
  }

  function init(root) {
    root.querySelectorAll("[data-split]").forEach(split);
    root.querySelectorAll("[data-reveal], [data-observe], [data-split], .gauge, .bar, .marker, [data-count], [data-burst-in], [data-roll]").forEach((el) => {
      if (!el.classList.contains("in")) io.observe(el);
    });
    root.querySelectorAll("[data-magnetic]").forEach(magnetic);
    root.querySelectorAll("[data-follow]").forEach((el) => followers.add(el));
    root.querySelectorAll("[data-story]").forEach(story);
    root.querySelectorAll("[data-cat-card]").forEach(linkRadar);
    root.querySelectorAll("[data-hover-link]").forEach((el) => {
      const sel = `[data-hover-target="${el.dataset.hoverLink}"]`;
      el.addEventListener("pointerenter", () => document.querySelectorAll(sel).forEach((t) => t.classList.add("hot")));
      el.addEventListener("pointerleave", () => document.querySelectorAll(sel).forEach((t) => t.classList.remove("hot")));
    });
  }

  /* themed loader: clone <template id="tpl-{name}"> into the hx-target while the request runs */
  document.addEventListener("htmx:beforeRequest", (e) => {
    const form = e.detail.elt.closest("[data-loader]");
    const tpl = form && document.getElementById(`tpl-${form.dataset.loader}`);
    const target = form && document.querySelector(form.getAttribute("hx-target"));
    if (!tpl || !target) return;
    const fmt = (v) => (v ? v.split("-").reverse().join(".") : "—");
    const data = new FormData(form);
    const html = tpl.innerHTML.replace("{a}", fmt(data.get("date_a"))).replace("{b}", fmt(data.get("date_b")));
    target.innerHTML = html;
    target.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
    window.dispatchEvent(new CustomEvent("aligning"));
  });

  /* mobile tab bar tucks away while reading down, returns on any upward scroll */
  let lastY = scrollY;
  addEventListener("scroll", () => {
    const bar = document.querySelector(".tabbar");
    if (!bar) return;
    const y = scrollY, down = y > lastY + 6, up = y < lastY - 6;
    if (down && y > 160) bar.classList.add("tucked");
    if (up || y < 80) bar.classList.remove("tucked");
    if (down || up) lastY = y;
  }, { passive: true });

  document.addEventListener("DOMContentLoaded", () => init(document));
  document.addEventListener("htmx:load", (e) => init(e.detail.elt));

  /* ── Birth-date picker (templates/components/date_field.html): typing ДД.ММ.ГГГГ or a calendar with
     day / month / year views; values are ISO strings, everything in UTC so time zones never shift a day. ── */
  const pad = (n) => String(n).padStart(2, "0");
  const isoOf = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;
  const localToday = () => { const t = new Date(); return isoOf(t.getFullYear(), t.getMonth(), t.getDate()); };
  const toText = (iso) => (iso ? iso.split("-").reverse().join(".") : "");
  const fromText = (t) => {
    const r = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(t);
    if (!r) return "";
    const [d, m, y] = [+r[1], +r[2] - 1, +r[3]];
    const dt = new Date(Date.UTC(y, m, d));
    return dt.getUTCMonth() === m && dt.getUTCDate() === d ? isoOf(y, m, d) : "";
  };
  const fmt = (o) => new Intl.DateTimeFormat(document.documentElement.lang || "ru", { ...o, timeZone: "UTC" });
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const MONTHS = [...Array(12)].map((_, i) => cap(fmt({ month: "long" }).format(Date.UTC(2000, i, 1))));
  const MONTHS_SHORT = [...Array(12)].map((_, i) => cap(fmt({ month: "short" }).format(Date.UTC(2000, i, 1)).replace(".", "")));
  const WEEK = [...Array(7)].map((_, i) => fmt({ weekday: "short" }).format(Date.UTC(2024, 0, 1 + i)));  // 2024-01-01 is a Monday
  const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  const datePicker = () => ({
    value: "", text: "", open: false, view: "days", y: 1995, m: 5, focused: "",
    min: "1900-01-01", max: localToday(), months: MONTHS, monthsShort: MONTHS_SHORT, week: WEEK,
    init() {
      this.value = this.value || this.$el.dataset.value || "";
      this.text = toText(this.value);
      this.$watch("value", (v) => { if (v !== fromText(this.text)) this.text = toText(v); this.check(); });
      this.$nextTick(() => this.check());
    },
    get hint() {
      return { days: "Можно ввести с клавиатуры: 14031996", months: "Выберите месяц", years: "Выберите год" }[this.view];
    },
    inRange(iso) { return iso >= this.min && iso <= this.max; },
    check() {
      const el = this.$refs.text;
      if (el) el.setCustomValidity(this.text && !this.value ? "Укажите дату между 1900 годом и сегодняшним днём" : "");
    },
    typed(e) {
      const digits = e.target.value.replace(/\D/g, "").slice(0, 8);
      this.text = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)].filter(Boolean).join(".");
      e.target.value = this.text;
      const iso = fromText(this.text);
      this.value = iso && this.inRange(iso) ? iso : "";
      if (this.value) { this.go(this.value); this.view = "days"; this.focused = this.value; }
      this.check();
    },
    go(iso) { this.y = +iso.slice(0, 4); this.m = +iso.slice(5, 7) - 1; },
    openPicker(focusGrid = false) {
      if (!this.open) {
        if (this.value) { this.go(this.value); this.view = "days"; this.focused = this.value; }
        else { this.y = 1995; this.view = "years"; this.focused = ""; }  // birth dates are decades back: start with years
      }
      this.open = true;
      this.$nextTick(() => {
        const pop = this.$refs.pop, box = this.$el.getBoundingClientRect();  // pop is mid-animation (scaled): use offset sizes
        const over = box.left + pop.offsetWidth - (innerWidth - 12);
        pop.style.left = over > 0 ? `${-over}px` : "0px";
        const h = pop.offsetHeight, bar = document.querySelector(".tabbar")?.offsetHeight || 0;
        const below = innerHeight - box.bottom - bar - 24, above = box.top - (document.querySelector("header")?.offsetHeight || 0) - 24;
        const up = below < h && above >= h;
        pop.classList.toggle("dp-up", up);
        if (!up && below < h) scrollBy({ top: h - below, behavior: calm() ? "auto" : "smooth" });
        if (focusGrid) (pop.querySelector('[tabindex="0"]') || pop.querySelector(".dp-cell:not(:disabled), .dp-day:not(:disabled)"))?.focus();
      });
    },
    close(refocus = false) { this.open = false; if (refocus) this.$refs.text.focus(); },
    get days() {
      const lead = (new Date(Date.UTC(this.y, this.m, 1)).getUTCDay() + 6) % 7;
      return [...Array(42)].map((_, i) => {
        const dt = new Date(Date.UTC(this.y, this.m, i - lead + 1));
        const iso = dt.toISOString().slice(0, 10);
        return { iso, d: dt.getUTCDate(), out: dt.getUTCMonth() !== this.m, off: !this.inRange(iso) };
      });
    },
    get years() { const start = 1900 + Math.floor((this.y - 1900) / 12) * 12; return [...Array(12)].map((_, i) => start + i); },
    monthOk(i) { return isoOf(this.y, i, 1) <= this.max && isoOf(this.y, i, 28) >= this.min; },
    canStep(dir) {
      const maxY = +this.max.slice(0, 4);
      if (this.view === "years") return dir < 0 ? this.years[0] > 1900 : this.years[11] < maxY;
      if (this.view === "months") return dir < 0 ? this.y > 1900 : this.y < maxY;
      const first = isoOf(this.y, this.m, 1);
      return dir < 0 ? first > this.min : isoOf(this.y, this.m + 1, 1) <= this.max;
    },
    step(dir) {
      if (!this.canStep(dir)) return;
      if (this.view === "years") this.y += 12 * dir;
      else if (this.view === "months") this.y += dir;
      else { const d = new Date(Date.UTC(this.y, this.m + dir, 1)); this.y = d.getUTCFullYear(); this.m = d.getUTCMonth(); }
      this.animate("slide", dir);
    },
    setView(v) { this.view = v; this.animate("zoom", v === "days" ? 1 : -1); },
    pickYear(yr) { this.y = yr; this.setView("months"); },
    pickMonth(i) { this.m = i; this.focused = this.value && this.value.slice(0, 7) === isoOf(this.y, i, 1).slice(0, 7) ? this.value : ""; this.setView("days"); },
    pick(iso) {
      this.value = iso;
      this.focused = iso;
      setTimeout(() => this.close(true), calm() ? 0 : 260);  // let the selection pop land first
    },
    label(iso) { return fmt({ day: "numeric", month: "long", year: "numeric" }).format(Date.parse(iso)); },
    key(e) {
      const moves = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
      if (!(e.key in moves)) return;
      e.preventDefault();
      const from = this.focused || isoOf(this.y, this.m, 1);
      const dt = new Date(Date.parse(from) + moves[e.key] * 864e5).toISOString().slice(0, 10);
      if (!this.inRange(dt)) return;
      const monthDir = Math.sign(dt.slice(0, 7).localeCompare(isoOf(this.y, this.m, 1).slice(0, 7)));
      this.focused = dt;
      if (monthDir) { this.go(dt); this.animate("slide", monthDir); }
      this.$nextTick(() => this.$refs.grid.querySelector(`[data-iso="${dt}"]`)?.focus());
    },
    animate(kind, dir) {
      if (calm()) return;
      this.$nextTick(() => {
        const from = kind === "slide" ? { opacity: 0, transform: `translateX(${dir * 22}px)` } : { opacity: 0, transform: `scale(${dir > 0 ? 1.06 : 0.94})` };
        this.$refs.grid.animate([from, { opacity: 1, transform: "none" }], { duration: 300, easing: "cubic-bezier(.2,.8,.2,1)" });
      });
    },
  });

  /* ── Birthplace: suggestions + our own world map (templates/components/place_field.html). Places come from
     /places/* on our server (GeoNames), outlines from Natural Earth; d3 is loaded only when the map opens. ── */
  const regionNames = (() => { try { return new Intl.DisplayNames([document.documentElement.lang || "ru"], { type: "region" }); } catch { return null; } })();
  const scripts = {};
  const loadScript = (src) => (scripts[src] ||= new Promise((ok, fail) => {
    const el = document.createElement("script");
    Object.assign(el, { src, onload: ok, onerror: fail });
    document.head.append(el);
  }));
  let worldData = null;
  const placesApi = async (path, params) => (await fetch(`/places/${path}/?${new URLSearchParams(params)}`)).json();

  let detailData = null, countryLabels = null;
  const DETAIL_K = 5;  // from this zoom the 1:10m coastlines, lakes and rivers take over

  function worldMap(svgEl, { onPick, onCity, detailUrl, labelsUrl }) {
    const W = svgEl.clientWidth || 800, H = svgEl.clientHeight || 500;
    const svg = d3.select(svgEl).attr("viewBox", [0, 0, W, H]);
    svg.selectAll("*").remove();
    const base = W / (2 * Math.PI);
    const proj = d3.geoMercator().scale(base).translate([W / 2, W / 2]);  // the whole Mercator square is W × W
    const path = d3.geoPath(proj);
    const land = topojson.feature(worldData, worldData.objects.countries);
    const borders = topojson.mesh(worldData, worldData.objects.countries, (a, b) => a !== b);

    // overview (1:50m): one group moved by the zoom transform; stays underneath as the fallback while panning
    const g = svg.append("g").attr("class", "geo-overview");
    g.append("path").datum(d3.geoGraticule().step([15, 15])()).attr("class", "geo-grid").attr("d", path);
    g.append("path").datum(land).attr("class", "geo-coast").attr("d", path);
    g.append("path").datum(land).attr("class", "geo-land").attr("d", path);
    g.append("path").datum(borders).attr("class", "geo-border").attr("d", path);
    // detail (1:10m): redrawn in screen space for the visible area once a gesture ends, stretched in between
    const detail = svg.append("g").attr("class", "geo-detail").style("display", "none");
    const dl = Object.fromEntries(["coast", "land", "lakes", "rivers", "border"].map((c) => [c, detail.append("path").attr("class", `geo-${c}`)]));
    const names = svg.append("g").attr("class", "geo-countries");
    const dots = svg.append("g").attr("class", "geo-cities");
    const pin = svg.append("g").attr("class", "geo-pin").style("display", "none");
    pin.append("ellipse").attr("class", "geo-pin-shadow").attr("rx", 7).attr("ry", 2.5);
    const drop = pin.append("g").attr("class", "geo-pin-body");
    drop.append("path").attr("d", "M0 0C-5-7-13-14-13-24a13 13 0 1 1 26 0C13-14 5-7 0 0Z");
    drop.append("circle").attr("cy", -24).attr("r", 4.6);

    const minK = Math.max(1, H / W);
    let t = d3.zoomIdentity, cities = [], pinAt = null, drawnAt = null;
    const screen = (lat, lon) => t.apply(proj([lon, lat]));
    const level = () => Math.log2((W * t.k) / 256);  // ≈ web-map zoom level, what Natural Earth's MIN_LABEL is in
    const overlaps = (a, list) => list.some((b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1]);
    const inView = (b) => b[2] > 0 && b[0] < W && b[3] > 0 && b[1] < H;

    const place = () => {
      const taken = [], z = level();
      names.selectAll("text").each(function (d) {  // country names first, while the view is wide
        const [x, y] = screen(d.lat, d.lon), w = d.name.length * 7.2 + 12;
        const box = [x - w / 2, y - 9, x + w / 2, y + 9];
        const show = d.min <= z + 0.6 && z < 7.5 && inView(box) && !overlaps(box, taken);
        this.setAttribute("x", x); this.setAttribute("y", y);
        this.style.opacity = show ? 1 : 0;
        if (show) taken.push(box);
      });
      dots.selectAll("g").attr("transform", (d) => `translate(${screen(d.lat, d.lon)})`).each(function (d) {
        const text = this.lastChild;
        if (!text.textContent) return;
        const [x, y] = screen(d.lat, d.lon), w = text.textContent.length * 6.6 + 10;
        const box = [x - 3, y - 8, x + w, y + 8];
        const free = inView(box) && !overlaps(box, taken);  // biggest towns first; a smaller one's label yields
        text.style.opacity = free ? 1 : 0;
        if (free) taken.push(box);
      });
      if (pinAt) pin.attr("transform", `translate(${screen(...pinAt)})`);
      if (drawnAt) {  // stretch the last detail drawing until it is redrawn
        const f = t.k / drawnAt.k;
        detail.attr("transform", `translate(${t.x - drawnAt.x * f},${t.y - drawnAt.y * f}) scale(${f})`);
      }
    };
    const drawDetail = () => {
      if (!detailData || t.k < DETAIL_K) { detail.style("display", "none"); g.classed("is-under", false); drawnAt = null; return; }
      const pad = Math.max(W, H) * 0.6;  // drawn wider than the view so a pan does not run off the edge before the redraw
      const p = d3.geoMercator().scale(base * t.k).translate([t.x + (t.k * W) / 2, t.y + (t.k * W) / 2]).clipExtent([[-pad, -pad], [W + pad, H + pad]]);
      const dp = d3.geoPath(p), landD = dp(detailData.land);
      dl.coast.attr("d", landD); dl.land.attr("d", landD);
      dl.lakes.attr("d", dp(detailData.lakes));
      dl.rivers.attr("d", dp(detailData.rivers));
      dl.border.attr("d", dp(detailData.borders));
      drawnAt = t;
      detail.attr("transform", null).style("display", null);
      g.classed("is-under", true);  // the coarse outline would stick out past the precise coast
    };
    const draw = () => {
      const labels = t.k < 3 ? 12 : t.k < 12 ? 28 : 48;
      const sel = dots.selectAll("g").data(cities, (d) => d.id);
      sel.exit().remove();
      const enter = sel.enter().append("g").on("click", (ev, d) => { ev.stopPropagation(); onCity(d); });
      enter.append("circle").attr("class", "geo-ring");
      enter.append("circle").attr("class", "geo-dot");
      enter.append("text").attr("dx", 7).attr("dy", 3.8);
      dots.selectAll("g").each(function (d, i) {
        const big = (d.pop || 0) >= 1e6, mid = (d.pop || 0) >= 1e5;
        const el = d3.select(this).attr("class", `geo-city ${big ? "is-big" : mid ? "is-mid" : ""}`);
        el.select(".geo-dot").attr("r", big ? 3.2 : mid ? 2.6 : 2);
        el.select(".geo-ring").attr("r", big ? 6.5 : 0);
        el.select("text").text(i < labels ? d.name : "");
      });
      place();
    };
    let timer = 0, seq = 0;
    const settle = () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const id = ++seq;
        if (t.k >= DETAIL_K && !detailData) {
          const d = await (await fetch(detailUrl)).json(), o = d.objects;
          const lakes = topojson.feature(d, o.lakes);
          lakes.features = lakes.features.filter((f) => d3.geoArea(f) < 2 * Math.PI);  // a reversed ring would flood the view
          detailData = { land: topojson.feature(d, o.land), lakes, rivers: topojson.feature(d, o.rivers), borders: topojson.mesh(d, o.borders) };
        }
        if (id !== seq) return;
        drawDetail();
        const [w, n] = proj.invert(t.invert([0, 0])), [e, s] = proj.invert(t.invert([W, H]));
        const data = await placesApi("box", { w: Math.max(w, -180), s: Math.max(s, -85), e: Math.min(e, 180), n: Math.min(n, 85), limit: t.k < 3 ? 30 : 160 });
        if (id !== seq) return;  // a slower answer for an older view
        cities = data.items;
        draw();
      }, 140);
    };
    const zoom = d3.zoom().scaleExtent([minK, 4000]).translateExtent([[0, 0], [W, W]]).clickDistance(5)
      .on("zoom", (ev) => { t = ev.transform; g.attr("transform", t); place(); })
      .on("end", settle);
    svg.call(zoom);
    svg.on("click", (ev) => {
      const [lon, lat] = proj.invert(t.invert(d3.pointer(ev)));
      if (Math.abs(lat) <= 85) onPick(+lat.toFixed(5), +lon.toFixed(5));
    });
    (async () => {  // country names: small, loaded once, placed with the cities
      countryLabels ||= (await (await fetch(labelsUrl)).json()).features
        .map((f) => ({ name: f.properties.name, min: f.properties.min, lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] }))
        .sort((a, b) => a.min - b.min);
      names.selectAll("text").data(countryLabels).join("text").attr("class", "geo-country").text((d) => d.name);
      place();
    })();
    const target = (lat, lon, k) => { const [x, y] = proj([lon, lat]); return d3.zoomIdentity.translate(W / 2, H / 2).scale(k).translate(-x, -y); };
    svg.call(zoom.transform, target(30, 40, minK * 1.15));
    return {
      flyTo(lat, lon, k = 48, ms = 1100) {  // k is for a desktop-wide map; a phone zooms in as far in kilometres
        const kk = Math.max(k * Math.max(1, 640 / W), minK);
        svg.transition().duration(calm() ? 0 : ms).ease(d3.easeCubicInOut).call(zoom.transform, target(lat, lon, kk));
      },
      zoomBy(f) { svg.transition().duration(calm() ? 0 : 350).call(zoom.scaleBy, f); },
      setPin(lat, lon) {
        pinAt = [lat, lon];
        pin.style("display", null).attr("transform", `translate(${screen(lat, lon)})`);
        drop.classed("drop", false); pin.node().getBBox(); drop.classed("drop", !calm());  // restart the drop animation
      },
    };
  }

  const placeField = (who) => {
    let m = null;  // the d3 map lives outside Alpine's reactivity
    return {
      q: "", geo: null, items: [], open: false, active: 0,
      map: false, mapQ: "", mapItems: [], mapActive: 0, mapSel: null, mapLoading: false,
      init() {
        const src = who && this.form ? this.form[who] : this.$el.dataset;
        this.q = src.place || "";
        if (src.tz) this.geo = { name: src.place, lat: +src.lat, lon: +src.lon, tz: src.tz, country: src.country || "" };
      },
      sync() {
        if (who && this.form) Object.assign(this.form[who], { place: this.q, lat: this.geo?.lat ?? "", lon: this.geo?.lon ?? "", tz: this.geo?.tz ?? "", country: this.geo?.country ?? "" });
      },
      country(code) { try { return code ? regionNames?.of(code) || code : ""; } catch { return code; } },
      offset(tz) {
        try {
          const part = new Intl.DateTimeFormat("ru", { timeZone: tz, timeZoneName: "shortOffset" }).formatToParts(new Date()).find((p) => p.type === "timeZoneName");
          return (part?.value || "").replace("GMT", "UTC").replace(/^UTC$/, "UTC+0");
        } catch { return ""; }
      },
      coordsText(p) {
        const f = (v, pos, neg) => `${Math.abs(v).toFixed(2).replace(".", ",")}° ${v >= 0 ? pos : neg}`;
        return p ? `${f(p.lat, "с. ш.", "ю. ш.")}, ${f(p.lon, "в. д.", "з. д.")}` : "";
      },
      async typed() {
        this.geo = null;
        this.sync();
        const q = this.q.trim();
        const items = q.length >= 2 ? (await placesApi("search", { q })).items : [];
        if (q !== this.q.trim()) return;  // a newer keystroke won
        this.items = items; this.active = 0; this.open = items.length > 0;
      },
      move(d) { if (this.items.length) { this.open = true; this.active = (this.active + d + this.items.length) % this.items.length; } },
      choose(p) { this.geo = { ...p }; this.q = p.name; this.open = false; this.sync(); },
      async openMap() {
        this.map = true; this.mapSel = this.geo ? { ...this.geo } : null; this.mapQ = ""; this.mapItems = [];
        this.mapLoading = !m;
        const box = this.$refs.svg.closest(".place-modal");
        if (!worldData) {
          await Promise.all([loadScript(box.dataset.d3), loadScript(box.dataset.topo)]);
          worldData = await (await fetch(box.dataset.world)).json();
        }
        await this.$nextTick();
        m ||= worldMap(this.$refs.svg, {
          onPick: (lat, lon) => this.pickPoint(lat, lon), onCity: (p) => this.mapChoose(p), detailUrl: box.dataset.detail, labelsUrl: box.dataset.labels,
        });
        this.mapLoading = false;
        if (this.mapSel) { m.flyTo(this.mapSel.lat, this.mapSel.lon, 60, 900); m.setPin(this.mapSel.lat, this.mapSel.lon); }
        this.$refs.mapSearch.focus();
      },
      closeMap() { this.map = false; },
      async mapTyped() {
        const q = this.mapQ.trim();
        const items = q.length >= 2 ? (await placesApi("search", { q })).items : [];
        if (q === this.mapQ.trim()) { this.mapItems = items; this.mapActive = 0; }
      },
      mapMove(d) { if (this.mapItems.length) this.mapActive = (this.mapActive + d + this.mapItems.length) % this.mapItems.length; },
      mapChoose(p) {
        this.mapSel = { ...p }; this.mapItems = []; this.mapQ = "";
        m?.flyTo(p.lat, p.lon, 60); m?.setPin(p.lat, p.lon);
      },
      async pickPoint(lat, lon) {
        m.setPin(lat, lon);
        const { place, km } = await placesApi("near", { lat, lon });
        if (!place) { this.mapSel = null; return; }
        const close = km < 3;
        this.mapSel = { ...place, lat, lon, name: close ? place.name : `${place.name} (≈${Math.round(km)} км)`, country: place.country };
      },
      zoomBy(f) { m?.zoomBy(f); },
      confirmMap() {
        if (!this.mapSel) return;
        this.geo = { ...this.mapSel };
        this.q = this.mapSel.name;
        this.items = []; this.open = false; this.map = false;
        this.sync();
      },
    };
  };

  document.addEventListener("alpine:init", () => {
    Alpine.data("datePicker", datePicker);
    Alpine.data("placeField", placeField);
    Alpine.store("toasts", {
      items: [],
      push(text, icon = "sparkles") {
        const id = Math.random();
        this.items.push({ id, text, icon });
        setTimeout(() => (this.items = this.items.filter((t) => t.id !== id)), 3200);
      },
    });
    Alpine.store("dev", document.body.dataset.dev === "1");
    Alpine.store("demo", { open: false, title: "", text: "", show(title, text) { Object.assign(this, { open: true, title, text }); } });
  });
  window.toast = (text, icon) => Alpine.store("toasts").push(text, icon);
  window.demo = (title, text) => Alpine.store("demo").show(title, text);
  window.burst = burst;
  if ("serviceWorker" in navigator) addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
  /* POST form fields (arrays become repeated keys) with the CSRF header from <body hx-headers>, get JSON back */
  window.postForm = async (url, fields) => {
    const body = new URLSearchParams();
    for (const [k, v] of Object.entries(fields)) [].concat(v).forEach((x) => body.append(k, x));
    const csrf = JSON.parse(document.body.getAttribute("hx-headers") || "{}")["X-CSRFToken"];
    const r = await fetch(url, { method: "POST", headers: { "X-CSRFToken": csrf }, body });
    if (!r.ok) throw new Error(r.status);
    return r.json();
  };
})();
