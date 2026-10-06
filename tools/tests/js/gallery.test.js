// tools/tests/js/gallery.test.js
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

// gallery.js is a classic script so it works on file://. Load it into a
// sandbox with a stub DOM and pull the pure functions off window.Gallery.
function load() {
  const sandbox = {
    window: {},
    document: {
      addEventListener() {},
      querySelector: () => null,
      querySelectorAll: () => [],
      createElement: () => ({ style: {}, classList: { add() {}, toggle() {} },
                              setAttribute() {}, append() {}, addEventListener() {} }),
    },
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(readFileSync("gallery.js", "utf8"), sandbox);
  return sandbox.window.Gallery;
}

const EVENTS = [
  { id: "a", date: "2026-06-09", year: "2026", title: "Diabetes", category: "seminar",
    photos: [{ src: "1.jpg", featured: true }, { src: "2.jpg", featured: false }] },
  { id: "b", date: "2025-05-08", year: "2025", title: "Opening", category: "opening",
    photos: [{ src: "3.jpg", featured: true }] },
  { id: "c", date: "2026-03-01", year: "2026", title: "Parade", category: "cultural",
    photos: [{ src: "4.jpg", featured: false }] },
];

test("filterEvents returns everything for the all/all case", () => {
  const G = load();
  assert.equal(G.filterEvents(EVENTS, { year: "all", category: "all" }).length, 3);
});

test("filterEvents narrows by year", () => {
  const G = load();
  const got = G.filterEvents(EVENTS, { year: "2026", category: "all" });
  assert.deepEqual(got.map((e) => e.id), ["a", "c"]);
});

test("filterEvents narrows by category", () => {
  const G = load();
  const got = G.filterEvents(EVENTS, { year: "all", category: "opening" });
  assert.deepEqual(got.map((e) => e.id), ["b"]);
});

test("filterEvents combines both filters", () => {
  const G = load();
  assert.equal(G.filterEvents(EVENTS, { year: "2025", category: "cultural" }).length, 0);
});

test("filterEvents tolerates missing options", () => {
  const G = load();
  assert.equal(G.filterEvents(EVENTS, {}).length, 3);
});

test("yearsOf returns newest first without duplicates", () => {
  const G = load();
  // Array.from re-materializes the array in this realm: gallery.js runs in a
  // vm sandbox, so the array it returns carries that sandbox's Array
  // prototype, and node:assert/strict's deepEqual treats same-content arrays
  // from two different realms as "not reference-equal" and fails otherwise.
  assert.deepEqual(Array.from(G.yearsOf(EVENTS)), ["2026", "2025"]);
});

test("categoriesOf returns the categories present, sorted", () => {
  const G = load();
  assert.deepEqual(Array.from(G.categoriesOf(EVENTS)), ["cultural", "opening", "seminar"]);
});

test("flattenPhotos pairs each photo with its event", () => {
  const G = load();
  const flat = G.flattenPhotos(EVENTS);
  assert.equal(flat.length, 4);
  assert.equal(flat[0].event.id, "a");
  assert.equal(flat[0].photo.src, "1.jpg");
});

test("flattenPhotos can return only featured photos", () => {
  const G = load();
  assert.equal(G.flattenPhotos(EVENTS, { featuredOnly: true }).length, 2);
});

test("loading gallery.js without a gallery container does not throw", () => {
  assert.doesNotThrow(() => load());
});
