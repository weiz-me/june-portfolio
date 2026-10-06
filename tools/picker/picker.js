// Local picker. Selections live in localStorage so picking can span sittings.
const KEY = "june-picker-v1";
const state = load();

function load() {
  try { return JSON.parse(localStorage.getItem(KEY)) || { picks: {}, caps: {} }; }
  catch (e) { return { picks: {}, caps: {} }; }
}
function save() {
  try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
}
function count() {
  return Object.values(state.picks).filter(Boolean).length;
}
function paintCount() {
  document.querySelector("[data-count]").textContent = String(count());
}

// Restore previous session
document.querySelectorAll("[data-pick]").forEach((box) => {
  box.checked = Boolean(state.picks[box.dataset.pick]);
  box.addEventListener("change", () => {
    state.picks[box.dataset.pick] = box.checked;
    save();
    paintCount();
  });
});
document.querySelectorAll("[data-cap]").forEach((input) => {
  if (state.caps[input.dataset.cap]) input.value = state.caps[input.dataset.cap];
  input.addEventListener("input", () => {
    state.caps[input.dataset.cap] = input.value;
    save();
  });
});

// Click the image (not the checkbox) to open the full-size original
document.querySelectorAll(".tile img").forEach((img) => {
  img.addEventListener("click", (e) => {
    e.preventDefault();
    window.open("file://" + encodeURI(img.dataset.full), "_blank");
  });
});

// Category filters
const groups = [...document.querySelectorAll(".event")];
document.querySelectorAll(".filter").forEach((btn) => {
  btn.addEventListener("click", () => {
    const want = btn.dataset.filter;
    document.querySelectorAll(".filter").forEach((b) =>
      b.setAttribute("aria-pressed", String(b === btn))
    );
    groups.forEach((g) => {
      g.hidden = want !== "all" && g.dataset.category !== want;
    });
  });
});

// Export
document.querySelector("[data-export]").addEventListener("click", () => {
  const payload = { photos: [] };
  for (const [key, on] of Object.entries(state.picks)) {
    if (!on) continue;
    const [eventId, rel] = key.split("|");
    payload.photos.push({
      event_id: eventId,
      rel,
      caption: state.caps[key] || "",
    });
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "selection.json";
  a.click();
  URL.revokeObjectURL(a.href);
});

paintCount();
