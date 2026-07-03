(function initMatrixRain() {
  const canvas = document.getElementById("matrix-rain");
  if (!canvas) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const colorScheme = window.matchMedia("(prefers-color-scheme: dark)");

  if (reducedMotion.matches) return;

  const ctx = canvas.getContext("2d");
  const chars = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン";
  const fontSize = 16;
  let columns = 0;
  let drops = [];

  function getThemeColors() {
    if (colorScheme.matches) {
      return {
        trail: "rgba(2, 4, 2, 0.08)",
        char: "#00ff41",
      };
    }

    return {
      trail: "rgba(238, 248, 241, 0.45)",
      char: "#00a832",
    };
  }

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    columns = Math.floor(canvas.width / fontSize);
    drops = Array.from({ length: columns }, () => Math.random() * -100);
  }

  function draw() {
    const colors = getThemeColors();

    ctx.fillStyle = colors.trail;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = colors.char;
    ctx.font = `${fontSize}px "Courier New", Courier, monospace`;

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
  colorScheme.addEventListener("change", resize);
  setInterval(draw, 50);
})();
