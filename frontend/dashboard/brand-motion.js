(function () {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canvas = document.querySelector("#global-particles");
  const intro = document.querySelector("#intro-overlay");
  const navbar = document.querySelector(".brand-header");
  const telemetry = document.querySelector("[data-trust-telemetry]");
  const body = document.body;

  let width = window.innerWidth;
  let height = window.innerHeight;
  let dpr = Math.min(window.devicePixelRatio || 1, 2);
  let frame = 0;
  let paused = false;
  let lastScrollY = window.scrollY;
  let scrollDirection = "down";
  let activeShape = "natural";
  let sectionShape = "natural";
  let lastTelemetryReplay = 0;

  const pointer = { x: width / 2, y: height / 2, active: false };
  const palette = [
    { r: 11, g: 31, b: 51, a: 0.22 },
    { r: 16, g: 42, b: 67, a: 0.18 },
    { r: 93, g: 107, b: 122, a: 0.18 },
    { r: 203, g: 211, b: 220, a: 0.28 },
    { r: 216, g: 162, b: 74, a: 0.3 },
  ];

  let context = null;
  let particles = [];
  let shapeCache = new Map();

  function rgba(color, alphaScale = 1) {
    return `rgba(${color.r}, ${color.g}, ${color.b}, ${Math.max(0.02, color.a * alphaScale)})`;
  }

  function countParticles() {
    if (reducedMotion) return width < 700 ? 56 : 96;
    if (width < 700) return 82;
    if (width < 1180) return 210;
    return 300;
  }

  function lerp(start, end, amount) {
    return start + (end - start) * amount;
  }

  function sampleLine(points, steps) {
    const output = [];
    for (let i = 0; i < points.length - 1; i += 1) {
      const start = points[i];
      const end = points[i + 1];
      for (let step = 0; step < steps; step += 1) {
        const t = step / steps;
        output.push({
          x: lerp(start.x, end.x, t),
          y: lerp(start.y, end.y, t),
        });
      }
    }
    return output;
  }

  function generateMinervaMarkTargets() {
    const cx = width * 0.5;
    const cy = height * 0.42;
    const scale = Math.min(width, height) * (width < 700 ? 0.35 : 0.48);
    const leftWing = sampleLine(
      [
        { x: cx - scale * 0.72, y: cy + scale * 0.2 },
        { x: cx - scale * 0.38, y: cy - scale * 0.2 },
        { x: cx - scale * 0.08, y: cy + scale * 0.06 },
      ],
      20,
    );
    const rightWing = sampleLine(
      [
        { x: cx + scale * 0.08, y: cy + scale * 0.06 },
        { x: cx + scale * 0.38, y: cy - scale * 0.2 },
        { x: cx + scale * 0.72, y: cy + scale * 0.2 },
      ],
      20,
    );
    const anchor = sampleLine(
      [
        { x: cx - scale * 0.18, y: cy + scale * 0.17 },
        { x: cx, y: cy + scale * 0.38 },
        { x: cx + scale * 0.18, y: cy + scale * 0.17 },
        { x: cx - scale * 0.18, y: cy + scale * 0.17 },
      ],
      12,
    );
    const sun = Array.from({ length: 36 }, (_, index) => {
      const angle = (Math.PI * 2 * index) / 24;
      const radius = scale * (0.045 + (index % 3) * 0.012);
      return { x: cx + Math.cos(angle) * radius, y: cy - scale * 0.27 + Math.sin(angle) * radius };
    });
    const rays = [-0.9, -0.55, -0.25, 0, 0.25, 0.55, 0.9].flatMap((angle) =>
      sampleLine(
        [
          { x: cx, y: cy - scale * 0.25 },
          { x: cx + Math.sin(angle) * scale * 0.28, y: cy - scale * (0.33 + Math.cos(angle) * 0.12) },
        ],
        5,
      ),
    );
    const lowerFold = sampleLine(
      [
        { x: cx - scale * 0.55, y: cy - scale * 0.04 },
        { x: cx - scale * 0.1, y: cy + scale * 0.2 },
        { x: cx + scale * 0.1, y: cy + scale * 0.2 },
        { x: cx + scale * 0.55, y: cy - scale * 0.04 },
      ],
      14,
    );
    const wingEdges = sampleLine(
      [
        { x: cx - scale * 0.82, y: cy + scale * 0.16 },
        { x: cx - scale * 0.56, y: cy + scale * 0.34 },
        { x: cx - scale * 0.42, y: cy - scale * 0.18 },
        { x: cx + scale * 0.42, y: cy - scale * 0.18 },
        { x: cx + scale * 0.56, y: cy + scale * 0.34 },
        { x: cx + scale * 0.82, y: cy + scale * 0.16 },
      ],
      10,
    );
    return [...leftWing, ...rightWing, ...lowerFold, ...wingEdges, ...anchor, ...sun, ...rays];
  }

  function generateScannerTargets() {
    const rect = document.querySelector(".demo-stage")?.getBoundingClientRect();
    const left = rect ? rect.left + 24 : width * 0.23;
    const top = rect ? rect.top + 90 : height * 0.23;
    const w = rect ? Math.max(260, rect.width - 48) : width * 0.42;
    const h = rect ? Math.max(230, rect.height - 140) : height * 0.42;
    const points = sampleLine(
      [
        { x: left, y: top },
        { x: left + w, y: top },
        { x: left + w, y: top + h },
        { x: left, y: top + h },
        { x: left, y: top },
      ],
      14,
    );
    const scan = sampleLine(
      [
        { x: left + w * 0.14, y: top + h * 0.48 },
        { x: left + w * 0.86, y: top + h * 0.48 },
      ],
      18,
    );
    const corners = [
      [left, top],
      [left + w, top],
      [left + w, top + h],
      [left, top + h],
    ].flatMap(([x, y]) =>
      Array.from({ length: 12 }, (_, index) => {
        const angle = (Math.PI * 2 * index) / 12;
        return { x: x + Math.cos(angle) * 13, y: y + Math.sin(angle) * 13 };
      }),
    );
    const guideLines = [0.28, 0.68].flatMap((ratio) =>
      sampleLine(
        [
          { x: left + w * 0.18, y: top + h * ratio },
          { x: left + w * 0.82, y: top + h * ratio },
        ],
        12,
      ),
    );
    return [...points, ...scan, ...corners, ...guideLines];
  }

  function generateChainTargets() {
    const rect = document.querySelector("#architecture")?.getBoundingClientRect();
    const left = rect ? rect.left + width * 0.04 : width * 0.16;
    const y = rect ? Math.min(height * 0.72, rect.top + rect.height * 0.48) : height * 0.58;
    const span = rect ? rect.width * 0.78 : width * 0.68;
    const nodes = [0, 1, 2, 3, 4].map((index) => ({
      x: left + (span * index) / 4,
      y: y + Math.sin(index * 0.9) * 26,
    }));
    const lines = sampleLine(nodes, 18);
    const rings = nodes.flatMap((node) =>
      Array.from({ length: 13 }, (_, index) => {
        const angle = (Math.PI * 2 * index) / 13;
        return { x: node.x + Math.cos(angle) * 20, y: node.y + Math.sin(angle) * 20 };
      }),
    );
    return [...lines, ...rings];
  }

  function generateTimelineTargets() {
    const rect = document.querySelector("#roadmap")?.getBoundingClientRect();
    const left = rect ? rect.left + rect.width * 0.08 : width * 0.12;
    const y = rect ? Math.min(height * 0.72, rect.top + rect.height * 0.5) : height * 0.6;
    const span = rect ? rect.width * 0.82 : width * 0.76;
    const nodes = [0, 1, 2, 3, 4].map((index) => ({
      x: left + (span * index) / 4,
      y,
    }));
    const lines = sampleLine(nodes, 18);
    const rings = nodes.flatMap((node) =>
      Array.from({ length: 12 }, (_, index) => {
        const angle = (Math.PI * 2 * index) / 12;
        return { x: node.x + Math.cos(angle) * 17, y: node.y + Math.sin(angle) * 17 };
      }),
    );
    return [...lines, ...rings];
  }

  function shapePoints(name) {
    if (name === "natural") return [];
    const cacheKey = `${name}:${Math.round(width)}:${Math.round(height)}:${Math.round(window.scrollY / 80)}`;
    if (shapeCache.has(cacheKey)) return shapeCache.get(cacheKey);
    const points =
      name === "scanner"
        ? generateScannerTargets()
        : name === "chain"
          ? generateChainTargets()
          : name === "timeline"
            ? generateTimelineTargets()
            : generateMinervaMarkTargets();
    shapeCache.set(cacheKey, points);
    return points;
  }

  function resizeCanvas() {
    if (!canvas || !context) return;
    width = window.innerWidth;
    height = window.innerHeight;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    shapeCache = new Map();
    particles = Array.from({ length: countParticles() }, (_, index) => ({
      x: Math.random() * width,
      y: Math.random() * height,
      homeX: Math.random() * width,
      homeY: Math.random() * height,
      size: 0.45 + Math.random() * 1.05,
      phase: Math.random() * Math.PI * 2,
      driftX: (Math.random() - 0.5) * 0.18,
      driftY: (Math.random() - 0.5) * 0.14,
      color: palette[index % palette.length],
    }));
  }

  function drawConnections(points) {
    if (!context || !points.length) return;
    context.save();
    context.strokeStyle = "rgba(216, 162, 74, 0.115)";
    context.lineWidth = 1;
    for (let i = 0; i < points.length - 1; i += 9) {
      context.beginPath();
      context.moveTo(points[i].x, points[i].y);
      context.lineTo(points[i + 1].x, points[i + 1].y);
      context.stroke();
    }
    context.restore();
  }

  function render(time) {
    if (!context) return;
    if (paused) {
      frame = window.requestAnimationFrame(render);
      return;
    }
    context.clearRect(0, 0, width, height);
    const shape = activeShape !== "natural" ? activeShape : sectionShape;
    const targets = shapePoints(shape);
    const scrollParallax = window.scrollY * 0.018;
    const pointerX = pointer.active ? (pointer.x / Math.max(width, 1) - 0.5) * 18 : 0;
    const pointerY = pointer.active ? (pointer.y / Math.max(height, 1) - 0.5) * 12 : 0;

    particles.forEach((particle, index) => {
      let targetX = particle.homeX + pointerX;
      let targetY = particle.homeY + pointerY + scrollParallax;
      if (targets.length) {
        const target = targets[index % targets.length];
        targetX = target.x + pointerX * 0.45;
        targetY = target.y + pointerY * 0.45;
      } else {
        particle.homeX += particle.driftX;
        particle.homeY += particle.driftY;
        if (particle.homeX < -16) particle.homeX = width + 16;
        if (particle.homeX > width + 16) particle.homeX = -16;
        if (particle.homeY < -16) particle.homeY = height + 16;
        if (particle.homeY > height + 16) particle.homeY = -16;
      }

      particle.x = lerp(particle.x, targetX, targets.length ? 0.048 : 0.01);
      particle.y = lerp(particle.y, targetY, targets.length ? 0.048 : 0.01);

      const pulse = reducedMotion ? 0.72 : 0.55 + Math.sin(time * 0.0012 + particle.phase) * 0.24;
      context.beginPath();
      context.fillStyle = rgba(particle.color, targets.length ? pulse * 1.55 : pulse * 0.72);
      context.arc(particle.x, particle.y, particle.size * (targets.length ? 1.42 : 0.82), 0, Math.PI * 2);
      context.fill();
    });

    drawConnections(targets);
    if (!reducedMotion) {
      frame = window.requestAnimationFrame(render);
    }
  }

  function detectPointerShape(target) {
    const element = target instanceof Element ? target : null;
    if (!element) return "natural";
    if (element.closest(".hero-section, .website-hero")) return "mark";
    if (element.closest(".demo-section, .scan-workflow-section")) return "scanner";
    if (element.closest(".evidence-section, #architecture")) return "chain";
    if (element.closest(".roadmap-section")) return "timeline";
    return "natural";
  }

  function hideIntro() {
    if (!intro) return;
    window.setTimeout(() => {
      intro.classList.add("intro-done");
      window.setTimeout(() => {
        intro.setAttribute("aria-hidden", "true");
        intro.style.display = "none";
      }, 420);
    }, reducedMotion ? 260 : 1680);
  }

  function animateTrustLine(panel, force = false) {
    if (!panel) return;
    const now = performance.now();
    if (!force && now - lastTelemetryReplay < 1000) return;
    lastTelemetryReplay = now;
    const number = panel.querySelector("[data-trust-number]");
    const line = panel.querySelector("[data-trust-line]");
    const target = Number(number?.dataset.target || 86);
    if (!number || !line || reducedMotion) {
      if (number) number.textContent = `${target}%`;
      if (line) line.style.width = `${target}%`;
      return;
    }
    number.textContent = "0%";
    line.style.width = "0%";
    const start = performance.now();
    const duration = 1150;
    function step(time) {
      const progress = Math.min(1, (time - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = Math.round(target * eased);
      number.textContent = `${value}%`;
      line.style.width = `${target * eased}%`;
      if (progress < 1) window.requestAnimationFrame(step);
    }
    window.requestAnimationFrame(step);
  }

  function replaySectionMotion(section) {
    if (!section || reducedMotion) return;
    section.classList.remove("motion-replay");
    void section.offsetWidth;
    section.classList.add("motion-replay");
    if (section.matches(".website-hero") || section.querySelector("[data-trust-telemetry]")) {
      animateTrustLine(telemetry);
    }
    window.setTimeout(() => section.classList.remove("motion-replay"), 1000);
  }

  function updateNavState() {
    const current = window.scrollY;
    scrollDirection = current >= lastScrollY ? "down" : "up";
    lastScrollY = current;
    navbar?.classList.toggle("is-scrolled", current > 18);
    body.dataset.scrollDirection = scrollDirection;
    const watermark = document.querySelector(".hero-m-watermark");
    if (watermark && !reducedMotion) {
      const x = pointer.active ? (pointer.x / Math.max(width, 1) - 0.5) * 16 : 0;
      const y = pointer.active ? (pointer.y / Math.max(height, 1) - 0.5) * 10 : 0;
      const scroll = Math.min(current * -0.075, 0);
      watermark.style.transform = `translate(calc(-50% + ${x}px), calc(-50% + ${y + scroll}px))`;
    }
  }

  function initScrollMotion() {
    const revealItems = document.querySelectorAll(
      ".website-hero, .motion-reveal, .reveal-section, .reveal-left, .reveal-right, .workflow-steps li, .architecture-flow article, .operations-section article, .roadmap-line li",
    );

    if (reducedMotion || !("IntersectionObserver" in window)) {
      revealItems.forEach((item) => item.classList.add("is-revealed"));
      animateTrustLine(telemetry, true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const section = entry.target;
          if (entry.isIntersecting) {
            section.classList.add("is-revealed", "is-motion-active");
            replaySectionMotion(section);
            const motion = section.dataset.motion;
            if (motion === "hero") sectionShape = "mark";
            if (motion === "scanner") sectionShape = "scanner";
            if (motion === "chain") sectionShape = "chain";
            if (motion === "roadmap") sectionShape = "timeline";
          } else {
            section.classList.remove("is-motion-active");
          }
        });
      },
      { threshold: 0.14, rootMargin: "0px 0px -10% 0px" },
    );

    revealItems.forEach((item, index) => {
      item.style.setProperty("--reveal-delay", `${Math.min(index % 6, 5) * 62}ms`);
      observer.observe(item);
    });
  }

  function initMotionField() {
    if (!canvas) return;
    context = canvas.getContext("2d");
    if (!context) return;
    resizeCanvas();
    if (reducedMotion) {
      render(0);
      return;
    }
    frame = window.requestAnimationFrame(render);
  }

  function init() {
    body.classList.add("js-ready");
    initMotionField();
    hideIntro();
    initScrollMotion();
    updateNavState();
    animateTrustLine(telemetry, true);

    window.addEventListener("resize", () => {
      window.cancelAnimationFrame(frame);
      resizeCanvas();
      if (!reducedMotion) frame = window.requestAnimationFrame(render);
    });

    window.addEventListener("pointermove", (event) => {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.active = true;
      activeShape = detectPointerShape(event.target);
      updateNavState();
    });

    window.addEventListener("pointerleave", () => {
      pointer.active = false;
      activeShape = "natural";
    });

    window.addEventListener("scroll", updateNavState, { passive: true });

    document.addEventListener("visibilitychange", () => {
      paused = document.hidden;
    });
  }

  try {
    init();
  } catch (error) {
    body.classList.remove("js-ready");
    document.querySelectorAll(".reveal-section, .reveal-left, .reveal-right").forEach((item) => {
      item.classList.add("is-revealed");
    });
    window.console?.error?.("Minerva motion field failed", error);
  }
})();
