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

  document.addEventListener("alpine:init", () => {
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
