(function initAurora() {
  const canvas = document.getElementById("aurora-canvas");
  if (!canvas) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const darkScheme = window.matchMedia("(prefers-color-scheme: dark)");
  const ctx = canvas.getContext("2d");

  let width = 0;
  let height = 0;
  let dpr = Math.min(window.devicePixelRatio || 1, 2);
  let animationId = null;
  let running = false;

  const PALETTES = {
    dark: [
      { r: 34, g: 211, b: 238 },
      { r: 139, g: 92, b: 246 },
      { r: 236, g: 72, b: 153 },
      { r: 45, g: 212, b: 191 },
    ],
    light: [
      { r: 96, g: 165, b: 250 },
      { r: 167, g: 139, b: 250 },
      { r: 244, g: 114, b: 182 },
      { r: 45, g: 212, b: 191 },
    ],
  };

  let blobs = [];

  function palette() {
    return darkScheme.matches ? PALETTES.dark : PALETTES.light;
  }

  function makeBlobs() {
    const colors = palette();
    blobs = colors.map((color, index) => ({
      color,
      x: Math.random(),
      y: Math.random(),
      radius: 0.35 + Math.random() * 0.25,
      angle: Math.random() * Math.PI * 2,
      speed: 0.00006 + Math.random() * 0.00009,
      orbit: 0.12 + (index % 2) * 0.06,
      cx: 0.2 + Math.random() * 0.6,
      cy: 0.2 + Math.random() * 0.6,
    }));
  }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function drawStatic() {
    const alpha = darkScheme.matches ? 0.42 : 0.3;
    ctx.clearRect(0, 0, width, height);
    for (const blob of blobs) {
      paintBlob(blob, alpha);
    }
  }

  function paintBlob(blob, alpha) {
    const px = blob.x * width;
    const py = blob.y * height;
    const r = blob.radius * Math.max(width, height);
    const { r: cr, g: cg, b: cb } = blob.color;

    const gradient = ctx.createRadialGradient(px, py, 0, px, py, r);
    gradient.addColorStop(0, `rgba(${cr}, ${cg}, ${cb}, ${alpha})`);
    gradient.addColorStop(1, `rgba(${cr}, ${cg}, ${cb}, 0)`);

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fill();
  }

  function frame() {
    const alpha = darkScheme.matches ? 0.4 : 0.28;
    ctx.clearRect(0, 0, width, height);
    ctx.globalCompositeOperation = "lighter";

    for (const blob of blobs) {
      blob.angle += blob.speed * 16;
      blob.x = blob.cx + Math.cos(blob.angle) * blob.orbit;
      blob.y = blob.cy + Math.sin(blob.angle * 0.9) * blob.orbit;
      paintBlob(blob, alpha);
    }

    ctx.globalCompositeOperation = "source-over";
    animationId = requestAnimationFrame(frame);
  }

  function start() {
    if (running) return;
    running = true;
    if (reducedMotion.matches) {
      drawStatic();
      return;
    }
    animationId = requestAnimationFrame(frame);
  }

  function stop() {
    running = false;
    if (animationId) cancelAnimationFrame(animationId);
    animationId = null;
  }

  function reset() {
    resize();
    makeBlobs();
    if (reducedMotion.matches) {
      drawStatic();
    }
  }

  reset();
  start();

  window.addEventListener("resize", reset);
  darkScheme.addEventListener("change", reset);
  reducedMotion.addEventListener("change", () => {
    stop();
    reset();
    start();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stop();
    } else {
      start();
    }
  });
})();
