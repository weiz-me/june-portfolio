// tools/tests/js/css-aspect-ratio.test.js
//
// Regression test for Task 15 round-1 finding 3: script.js and gallery.js
// both set explicit width/height attributes on generated <img> elements to
// reserve layout space before the image loads. That attribute acts as a
// presentation hint, so any CSS rule that also sets `aspect-ratio` on that
// same img needs an explicit `height: auto` too -- otherwise the attribute
// wins and the box renders at the photo's raw pixel height instead of the
// intended ratio (confirmed: without height: auto, a 1080x1920 test photo
// rendered as a 287x933 box, ratio 0.308, instead of 4:3).
//
// This scans every CSS rule in style.css and gallery.css whose selector
// targets `img` and whose declarations set `aspect-ratio`, and asserts the
// same rule also sets `height`. It would catch the bug being reintroduced
// in either file.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

function rulesWithImgAndAspectRatio(css) {
  // Strip comments first so a commented-out example doesn't count.
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const rules = [];
  // Matches only innermost {...} blocks (no nested braces in plain CSS),
  // so this finds individual rules whether they're top-level or nested
  // inside an @media block.
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m;
  while ((m = re.exec(stripped))) {
    const selector = m[1].trim();
    const body = m[2];
    const touchesImg = selector
      .split(",")
      .some((s) => /(^|[\s.#[])img(\b|$)/.test(s.trim()));
    if (touchesImg && /\baspect-ratio\s*:/.test(body)) {
      rules.push({ selector, body });
    }
  }
  return rules;
}

for (const file of ["style.css", "gallery.css"]) {
  test(`every img rule setting aspect-ratio also sets height (${file})`, () => {
    const css = readFileSync(file, "utf8");
    const rules = rulesWithImgAndAspectRatio(css);
    assert.ok(
      rules.length > 0,
      `expected to find at least one img + aspect-ratio rule in ${file}`
    );
    for (const { selector, body } of rules) {
      assert.match(
        body,
        /\bheight\s*:/,
        `${file}: "${selector}" sets aspect-ratio without height`
      );
    }
  });
}
