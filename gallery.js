// Gallery: pure data helpers plus a DOM renderer.
// Classic script (not a module) so it works from file:// as well as HTTP.
(function () {
  const Gallery = {};

  Gallery.filterEvents = function (events, opts) {
    const o = opts || {};
    const year = o.year || "all";
    const category = o.category || "all";
    return events.filter(
      (e) =>
        (year === "all" || e.year === year) &&
        (category === "all" || e.category === category)
    );
  };

  Gallery.yearsOf = function (events) {
    return [...new Set(events.map((e) => e.year).filter(Boolean))].sort().reverse();
  };

  Gallery.categoriesOf = function (events) {
    return [...new Set(events.map((e) => e.category).filter(Boolean))].sort();
  };

  Gallery.flattenPhotos = function (events, opts) {
    const featuredOnly = Boolean(opts && opts.featuredOnly);
    const out = [];
    events.forEach((event) =>
      (event.photos || []).forEach((photo) => {
        if (featuredOnly && !photo.featured) return;
        out.push({ event, photo });
      })
    );
    return out;
  };

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderGrid(host, events, lightbox) {
    host.textContent = "";
    const flat = Gallery.flattenPhotos(events);
    if (flat.length === 0) {
      host.append(el("p", "gal-empty", "No events match these filters."));
      return;
    }
    flat.forEach(({ event, photo }, i) => {
      const fig = el("figure", "gal-item");
      const img = document.createElement("img");
      img.src = photo.thumb || photo.src;
      img.width = photo.w || 0;
      img.height = photo.h || 0;
      img.loading = "lazy";
      img.decoding = "async";
      img.alt = photo.caption || event.title;
      img.addEventListener("click", () => lightbox.open(flat, i));
      const cap = el("figcaption");
      cap.append(el("span", "gal-title", event.title));
      cap.append(el("span", "gal-meta",
        [event.date, event.category_label].filter(Boolean).join(" · ")));
      fig.append(img, cap);
      host.append(fig);
    });
  }

  function makeLightbox() {
    const box = el("div", "gal-lightbox");
    box.hidden = true;
    const img = document.createElement("img");
    const cap = el("p", "gal-lightbox-cap");
    const close = el("button", "gal-close", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Close");
    const prev = el("button", "gal-arrow gal-arrow-prev", "◀");
    const next = el("button", "gal-arrow gal-arrow-next", "▶");
    prev.type = next.type = "button";
    prev.setAttribute("aria-label", "Previous photo");
    next.setAttribute("aria-label", "Next photo");
    box.append(close, prev, img, next, cap);
    document.body.append(box);

    let items = [];
    let at = 0;
    const show = (i) => {
      at = (i + items.length) % items.length;
      const { event, photo } = items[at];
      img.src = photo.src;
      img.alt = photo.caption || event.title;
      cap.textContent = [event.title, event.date, photo.caption]
        .filter(Boolean).join(" · ");
    };
    const hide = () => { box.hidden = true; document.body.style.overflow = ""; };

    close.addEventListener("click", hide);
    prev.addEventListener("click", () => show(at - 1));
    next.addEventListener("click", () => show(at + 1));
    box.addEventListener("click", (e) => { if (e.target === box) hide(); });
    document.addEventListener("keydown", (e) => {
      if (box.hidden) return;
      if (e.key === "Escape") hide();
      if (e.key === "ArrowLeft") show(at - 1);
      if (e.key === "ArrowRight") show(at + 1);
    });

    return {
      open(list, i) {
        items = list;
        box.hidden = false;
        document.body.style.overflow = "hidden";
        show(i);
      },
    };
  }

  function chip(label, value, group, onPick) {
    const btn = el("button", "gal-chip", label);
    btn.type = "button";
    btn.dataset.value = value;
    btn.dataset.group = group;
    btn.addEventListener("click", () => onPick(group, value, btn));
    return btn;
  }

  Gallery.init = function () {
    const host = document.querySelector("[data-gallery]");
    if (!host) return;
    const data = window.GALLERY_DATA;
    const events = (data && data.events) || [];
    const grid = host.querySelector("[data-gallery-grid]");
    const yearBar = host.querySelector("[data-gallery-years]");
    const catBar = host.querySelector("[data-gallery-categories]");
    const countEl = host.querySelector("[data-gallery-count]");
    if (!grid) return;

    if (events.length === 0) {
      grid.append(el("p", "gal-empty",
        "Gallery data has not been built yet. Run tools/build_assets.py."));
      return;
    }

    const lightbox = makeLightbox();
    const picked = { year: "all", category: "all" };

    const paint = () => {
      const shown = Gallery.filterEvents(events, picked);
      renderGrid(grid, shown, lightbox);
      if (countEl) {
        const photos = Gallery.flattenPhotos(shown).length;
        countEl.textContent = `${shown.length} events · ${photos} photos`;
      }
    };

    const onPick = (group, value, btn) => {
      picked[group] = value;
      const bar = group === "year" ? yearBar : catBar;
      if (bar) {
        [...bar.children].forEach((b) =>
          b.setAttribute("aria-pressed", String(b === btn))
        );
      }
      paint();
    };

    if (yearBar) {
      const all = chip("All years", "all", "year", onPick);
      all.setAttribute("aria-pressed", "true");
      yearBar.append(all);
      Gallery.yearsOf(events).forEach((y) =>
        yearBar.append(chip(y, y, "year", onPick))
      );
    }
    if (catBar) {
      const all = chip("All types", "all", "category", onPick);
      all.setAttribute("aria-pressed", "true");
      catBar.append(all);
      Gallery.categoriesOf(events).forEach((c) => {
        const label = (events.find((e) => e.category === c) || {}).category_label || c;
        catBar.append(chip(label, c, "category", onPick));
      });
    }
    paint();
  };

  window.Gallery = Gallery;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", Gallery.init);
  } else {
    Gallery.init();
  }
})();
