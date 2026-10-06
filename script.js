// Footer year
const yearEl = document.getElementById("year");
if (yearEl) yearEl.textContent = new Date().getFullYear();

// Image slots: until the real file is dropped into assets/, show a labeled placeholder
function toSlot(img) {
  const slot = document.createElement("div");
  slot.className = "slot";
  slot.textContent = img.dataset.slot;
  img.replaceWith(slot);
}
document.querySelectorAll("img[data-slot]").forEach((img) => {
  if (img.complete && img.naturalWidth === 0) toSlot(img);
  else img.addEventListener("error", () => toSlot(img));
});

// Theme toggle (remembered per browser)
const root = document.documentElement;
try {
  const saved = localStorage.getItem("theme");
  if (saved) root.dataset.theme = saved;
} catch {}
const themeBtn = document.querySelector(".theme-toggle");
if (themeBtn) {
  themeBtn.addEventListener("click", () => {
    const isDark = root.dataset.theme
      ? root.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = isDark ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch {}
  });
}

// Mobile menu
const toggle = document.querySelector(".nav-toggle");
const links = document.querySelector(".nav-links");
if (toggle && links) {
  toggle.addEventListener("click", () => {
    const open = links.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open);
  });
  links.querySelectorAll("a").forEach((a) =>
    a.addEventListener("click", () => links.classList.remove("open"))
  );
}

// Reveal sections on scroll
const io = new IntersectionObserver(
  (entries) => entries.forEach((e) => {
    if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
  }),
  { threshold: 0.08 }
);
document.querySelectorAll(".section, .card").forEach((el) => {
  el.classList.add("reveal");
  io.observe(el);
});

// Before/after comparison: markup ships all pairs; JS only switches which is shown.
document.querySelectorAll("[data-ba]").forEach((ba) => {
  const wrap = ba.querySelector(".ba-pairs");
  const pairs = [...ba.querySelectorAll("[data-ba-pair]")];
  const label = ba.querySelector("[data-ba-label]");
  const dots = ba.querySelector("[data-ba-dots]");
  if (!wrap || pairs.length === 0) return;

  let index = 0;
  const show = (next) => {
    index = (next + pairs.length) % pairs.length;
    pairs.forEach((p, i) => p.classList.toggle("active", i === index));
    if (label) label.textContent = pairs[index].dataset.label || "";
    if (dots) {
      [...dots.children].forEach((d, i) =>
        d.setAttribute("aria-current", String(i === index))
      );
    }
  };

  if (dots) {
    pairs.forEach((p, i) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = "ba-dot";
      dot.setAttribute("aria-label", `Show ${p.dataset.label || `location ${i + 1}`}`);
      dot.addEventListener("click", () => show(i));
      dots.append(dot);
    });
    dots.removeAttribute("aria-hidden");
  }

  const prev = ba.querySelector(".ba-prev");
  const next = ba.querySelector(".ba-next");
  if (prev) prev.addEventListener("click", () => show(index - 1));
  if (next) next.addEventListener("click", () => show(index + 1));
  ba.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") show(index - 1);
    if (e.key === "ArrowRight") show(index + 1);
  });

  wrap.dataset.baReady = "1";
  show(0);
});

// Featured event strip on the home page. Falls back to whatever markup is
// already in [data-featured] when no gallery data has been built yet.
(function () {
  const host = document.querySelector("[data-featured]");
  const data = window.GALLERY_DATA;
  if (!host || !data || !Array.isArray(data.events)) return;

  const featured = [];
  data.events.forEach((event) =>
    (event.photos || []).forEach((photo) => {
      if (photo.featured) featured.push({ event, photo });
    })
  );
  if (featured.length === 0) return;

  host.textContent = "";
  featured.slice(0, 8).forEach(({ event, photo }) => {
    const fig = document.createElement("figure");
    const img = document.createElement("img");
    img.src = photo.thumb || photo.src;
    // No width/height attributes: .photos img already fixes a 4:3 box via
    // aspect-ratio + object-fit, and setting mismatched width/height
    // attributes (most real photos aren't 4:3) overrides that aspect-ratio
    // with the photo's raw pixel height, breaking the grid into tall,
    // misaligned columns.
    img.alt = photo.caption || event.title;
    img.loading = "lazy";
    img.decoding = "async";
    const cap = document.createElement("figcaption");
    cap.textContent = photo.caption || event.title;
    fig.append(img, cap);
    host.append(fig);
  });
  host.classList.add("featured-grid");
})();
