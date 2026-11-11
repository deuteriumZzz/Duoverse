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

  document.addEventListener("alpine:init", () => {
    Alpine.data("datePicker", datePicker);
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
