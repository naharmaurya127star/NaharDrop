// Shared incremental list renderer. Re-rendering a polled/pushed list by
// blowing away innerHTML causes visible flicker, resets scroll position, and
// (worst of all) tears down and reloads any <video>/<img> elements inside
// it. This instead keeps existing DOM nodes for keys that still exist,
// updates them in place, only creates nodes for genuinely new keys, and only
// removes nodes for keys that disappeared - so untouched rows (including
// playing videos) are never touched.
window.NDListDiff = (function () {
  function renderDiffList(container, items, keyFn, createEl, updateEl, emptyHtml) {
    // Drop any non-keyed placeholder (e.g. an "nothing yet" <li>) before diffing.
    Array.from(container.children).forEach((el) => {
      if (!el.dataset || !el.dataset.key) el.remove();
    });

    if (items.length === 0) {
      if (container.children.length === 0) container.innerHTML = emptyHtml || "";
      return;
    }

    const existing = new Map();
    Array.from(container.children).forEach((el) => existing.set(el.dataset.key, el));

    let prevEl = null;
    const seen = new Set();
    items.forEach((item) => {
      const key = String(keyFn(item));
      seen.add(key);
      let el = existing.get(key);
      if (el) {
        updateEl(el, item);
      } else {
        el = createEl(item);
        el.dataset.key = key;
      }
      const expectedNext = prevEl ? prevEl.nextSibling : container.firstChild;
      if (expectedNext !== el) container.insertBefore(el, expectedNext);
      prevEl = el;
    });

    existing.forEach((el, key) => {
      if (!seen.has(key)) el.remove();
    });
  }

  return { renderDiffList };
})();
