(function initMatrixRain() {
  const canvas = document.getElementById("matrix-rain");
  if (!canvas) return;

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReducedMotion) return;

  const ctx = canvas.getContext("2d");
  const chars = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン";
  const fontSize = 16;
  let columns = 0;
  let drops = [];

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    columns = Math.floor(canvas.width / fontSize);
    drops = Array.from({ length: columns }, () => Math.random() * -100);
  }

  function draw() {
    ctx.fillStyle = "rgba(2, 4, 2, 0.08)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = "#00ff41";
    ctx.font = `${fontSize}px Share Tech Mono, monospace`;

    for (let i = 0; i < drops.length; i += 1) {
      const char = chars[Math.floor(Math.random() * chars.length)];
      const x = i * fontSize;
      const y = drops[i] * fontSize;

      ctx.fillText(char, x, y);

      if (y > canvas.height && Math.random() > 0.975) {
        drops[i] = 0;
      }

      drops[i] += 1;
    }
  }

  resize();
  window.addEventListener("resize", resize);
  setInterval(draw, 50);
})();
