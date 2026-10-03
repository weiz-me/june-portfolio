// Footer year
document.getElementById("year").textContent = new Date().getFullYear();

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
document.querySelector(".theme-toggle").addEventListener("click", () => {
  const isDark = root.dataset.theme
    ? root.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = isDark ? "light" : "dark";
  try { localStorage.setItem("theme", root.dataset.theme); } catch {}
});

// Mobile menu
const toggle = document.querySelector(".nav-toggle");
const links = document.querySelector(".nav-links");
toggle.addEventListener("click", () => {
  const open = links.classList.toggle("open");
  toggle.setAttribute("aria-expanded", open);
});
links.querySelectorAll("a").forEach((a) =>
  a.addEventListener("click", () => links.classList.remove("open"))
);

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
