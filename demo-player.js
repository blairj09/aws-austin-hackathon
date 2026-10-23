// Immersive layer for positron-on-sagemaker-live.qmd:
//  - a slowly drifting hexagon field behind every slide
//  - a frame player for the captured demo footage (clips/manifest.js)
//  - a typewriter for the CLI line on the setup slide
(function () {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- Hexagon field ------------------------------------------------------
  function buildHexField() {
    const host = document.createElement("div");
    host.className = "hexfield";
    const R = 46, W = Math.sqrt(3) * R, H = 1.5 * R;
    const cols = 30, rows = 18;
    let cells = "";
    const pts = (cx, cy) =>
      [0, 1, 2, 3, 4, 5]
        .map((k) => {
          const a = (Math.PI / 180) * (60 * k - 30);
          return `${(cx + R * 0.92 * Math.cos(a)).toFixed(1)},${(cy + R * 0.92 * Math.sin(a)).toFixed(1)}`;
        })
        .join(" ");
    let seed = 7;
    const rand = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const cx = c * W + (r % 2 ? W / 2 : 0), cy = r * H;
        const roll = rand();
        const cls = roll > 0.93 ? "lit" : roll > 0.86 ? "lit dim" : "";
        const delay = (rand() * 9).toFixed(2);
        // distance from the slide-1 ripple origin (behind the headline), 0..1
        const dist = Math.hypot(cx / (cols * W) - 0.3, (cy / (rows * H) - 0.48) * 0.6).toFixed(3);
        const style = cls ? `animation-delay:-${delay}s` : `--d:${dist}`;
        cells += `<polygon class="${cls}" style="${style}" points="${pts(cx, cy)}"/>`;
      }
    }
    host.innerHTML = `<svg viewBox="0 0 ${cols * W} ${rows * H}" preserveAspectRatio="xMidYMid slice">${cells}</svg>`;
    document.querySelector(".reveal").prepend(host);
  }

  // ---- Demo frame player --------------------------------------------------
  class Player {
    constructor(el) {
      this.el = el;
      this.clip = window.DEMO_CLIPS[el.dataset.clip];
      this.img = el.querySelector("img.frame");
      this.stage = el.querySelector(".zoom");
      this.bar = el.querySelector(".progress i");
      this.steps = [...el.closest("section").querySelectorAll("[data-mark]")].map((m) => {
        const li = m.closest("li") || m;
        li.dataset.mark = m.dataset.mark;
        return li;
      });
      // data-zooms="mark:scale:x%:y%;..." — the camera eases to each framing at its mark
      this.zooms = (el.dataset.zooms || "").split(";").filter(Boolean).map((z) => {
        const [at, s, x, y] = z.split(":");
        return { at, s: +s, x: +x, y: +y };
      });
      this.times = this.clip.frames.map((f) => f[0]);
      this.cache = this.clip.frames.map((f) => {
        const i = new Image();
        i.src = f[1];
        return i;
      });
      this.raf = null;
      this.idx = -1;
      el.addEventListener("click", () => this.play());
      this.seek(this.clip.duration); // show the end state until the slide plays it
    }
    markTime(name) {
      return this.clip.marks[name] ?? 0;
    }
    seek(t) {
      let lo = 0, hi = this.times.length - 1;
      while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (this.times[mid] <= t) lo = mid; else hi = mid - 1;
      }
      if (lo !== this.idx) {
        this.idx = lo;
        this.img.src = this.clip.frames[lo][1];
      }
      this.bar.style.transform = `scaleX(${Math.min(1, t / this.clip.duration)})`;
      // steps light up at their marks
      let current = null;
      for (const s of this.steps) {
        const on = t >= this.markTime(s.dataset.mark);
        s.classList.toggle("done", on);
        if (on) current = s;
      }
      this.steps.forEach((s) => s.classList.toggle("active", s === current));
      this.el.classList.toggle("skipping", this.clip.marks.skip != null &&
        t >= this.clip.marks.skip - 0.1 && t < this.clip.marks.skip + 1.4);
      // camera
      let z = { s: 1, x: 50, y: 50 };
      for (const zz of this.zooms) if (t >= this.markTime(zz.at)) z = zz;
      if (!reduceMotion) {
        this.stage.style.transformOrigin = `${z.x}% ${z.y}%`;
        this.stage.style.transform = `scale(${z.s})`;
      }
    }
    play() {
      cancelAnimationFrame(this.raf);
      const t0 = performance.now();
      const tick = (now) => {
        const t = (now - t0) / 1000;
        this.seek(t);
        if (t < this.clip.duration) this.raf = requestAnimationFrame(tick);
        else this.el.classList.add("ended");
      };
      this.el.classList.remove("ended");
      this.raf = requestAnimationFrame(tick);
    }
    stop() {
      cancelAnimationFrame(this.raf);
    }
  }

  // ---- Video demo (recorded screen capture) ------------------------------
  // <div class="demo video" data-rate="1.5"><video> + steps with data-at="seconds"
  class VideoPlayer {
    constructor(el) {
      this.el = el;
      this.video = el.querySelector("video");
      this.bar = el.querySelector(".progress i");
      this.rate = +(el.dataset.rate || 1);
      this.steps = [...el.closest("section").querySelectorAll("[data-at]")].map((m) => {
        const li = m.closest("li") || m;
        li.dataset.at = m.dataset.at;
        return li;
      });
      this.video.muted = true;
      this.video.playsInline = true;
      this.video.addEventListener("timeupdate", () => this.sync());
      this.video.addEventListener("ended", () => {
        this.want = false;
        this.el.classList.add("ended");
      });
      // Browsers may refuse or pause muted playback (for example in a hidden
      // tab). Retry a few times, then ask for a click.
      this.video.addEventListener("pause", () => {
        if (!this.want || this.video.ended) return;
        if (this.tries++ < 3) setTimeout(() => this.want && this.video.play().catch(() => {}), 400);
        else this.el.classList.add("needs-click");
      });
      this.video.addEventListener("playing", () => this.el.classList.remove("needs-click"));
      el.addEventListener("click", () => this.play());
    }
    sync() {
      const t = this.video.currentTime, d = this.video.duration || 1;
      this.bar.style.transform = `scaleX(${Math.min(1, t / d)})`;
      let current = null;
      for (const s of this.steps) {
        const on = t >= +s.dataset.at;
        s.classList.toggle("done", on);
        if (on) current = s;
      }
      this.steps.forEach((s) => s.classList.toggle("active", s === current));
    }
    play() {
      this.want = true;
      this.tries = 0;
      this.el.classList.remove("ended", "needs-click");
      this.video.currentTime = 0;
      this.video.playbackRate = this.rate;
      this.video.play().catch(() => {});
    }
    stop() {
      this.want = false;
      this.video.pause();
    }
  }

  // ---- Typewriter ---------------------------------------------------------
  function typeOut(el) {
    const full = el.dataset.text;
    if (reduceMotion) { el.textContent = full; return; }
    clearInterval(el._t);
    el.textContent = "";
    let i = 0;
    el._t = setInterval(() => {
      el.textContent = full.slice(0, ++i);
      if (i >= full.length) clearInterval(el._t);
    }, 28);
  }

  // Reveal can report the same slide more than once (ready, hash, slidechanged);
  // only (re)start the demos when the slide actually changes, or on replay.
  let lastSlide = null, pending = [];
  function onSlide(slide, force = false) {
    if (slide === lastSlide && !force) return;
    lastSlide = slide;
    pending.forEach(clearTimeout);
    pending = [];
    players.forEach((p) => p.stop());
    slide.querySelectorAll(".demo").forEach((el) => {
      const p = players.find((pp) => pp.el === el);
      if (p) pending.push(setTimeout(() => p.play(), 700));
    });
    slide.querySelectorAll(".typed").forEach((el) => pending.push(setTimeout(() => typeOut(el), 900)));
  }

  let players = [];
  const start = () => {
    buildHexField();
    players = [...document.querySelectorAll(".demo")].map((el) =>
      el.querySelector("video") ? new VideoPlayer(el) : new Player(el));
    onSlide(Reveal.getCurrentSlide());
  };
  if (Reveal.isReady()) start();
  else Reveal.on("ready", start);
  Reveal.on("slidechanged", (e) => onSlide(e.currentSlide));
  // R replays the demo on the current slide
  Reveal.addKeyBinding({ keyCode: 82, key: "R", description: "Replay demo" }, () =>
    onSlide(Reveal.getCurrentSlide(), true));
})();
