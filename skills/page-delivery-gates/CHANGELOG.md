# Changelog: page-delivery-gates

## 0.11.0 (2026-11-12)
- First release. Built from four months of page work across several projects, where the same hand-off checks were written by hand in session after session (a sideways-overflow probe 144 times in 14 sessions, a reduced-motion check 81 times in 16, a no-WebGL check 56 times in 8) and both missed defects and invented them.
- `gate_page.py` loads a page at desktop and phone width three ways (normal, reduced motion, WebGL refused) and fails on errors, failed requests, sideways overflow at any scroll stop, a canvas that never shows a picture, motion with reduced motion on, text that is visible in the normal load and not in the others, and npm-CDN scripts without an exact version. It writes one contact sheet per load for the visual review.
- Three faults in the first draft were found by running it on real pages before release, and each now has a test:
  - **Holes in the screenshots.** With software compositing (Playwright's headless shell, or a machine without a GPU) a sheet showed a page-coloured square punched through the canvas under an animated element. The gate now launches full Chromium, and runs the software renderer as the GPU when there is no hardware one.
  - **Mojibake and quirks mode.** Pages written as fragments for a host that adds the doctype and charset were served bare. The gate now serves a fragment inside a minimal UTF-8 document and says so.
  - **Text reported missing that was never looked at.** Scroll stops were capped at 40, so on a page 52 screens tall they were 1.3 screens apart. The cap is gone.
- Two independent Codex review rounds of that draft found twelve more gaps, most of them ways to pass a page the gate had not really checked. All are fixed:
  - the page's height was read once, so sections that load on arrival were never scrolled (now read at every step);
  - text clipped away by a wrapper at `max-height: 0` counted as visible;
  - one drawn canvas vouched for every other canvas at the same position (each is now judged alone);
  - WebGL through `OffscreenCanvas` was not refused in the no-WebGL load, and a canvas handed to a worker now fails that load as unverified;
  - text under a `display: contents` parent was left out;
  - images and stylesheets on an npm CDN were held to the script version rule;
  - a `#` or `?` in a local file name broke the URL;
  - a load started by reaching the bottom, but slower than the sampling window, was missed (the gate now waits there, and fails a page that grows afterwards as ungated);
  - WebGL created inside a worker could not be refused (a worker caught drawing now fails the no-WebGL load as unverified);
  - one exact version passed a whole combined CDN URL, and a range beginning like a version passed too;
  - text under a `display: contents; visibility: hidden` parent counted as visible;
  - canvas flatness was judged in grey, where two different colours can be equal.
- Covered by `tests/test_gate_page.py` (22 tests): one fixture page per incident in a real headless browser, plus unit tests for the CDN, fragment, file-name, colour and scroll-stop rules and for a missing browser (exit 2, never a failed page). Twenty mutations of the script were each caught by a test, each one undoing a single rule: overflow measured only at the top, flat-canvas threshold removed, stillness limit removed, text comparison removed, uncaught errors dropped, headless shell with no fallback, digits left unmasked, page height read once, ancestor clipping ignored, canvases judged together, OffscreenCanvas not refused, `display: contents` parents skipped, file name unquoted, no wait at the bottom, late growth unreported, worker draws unreported, one version accepted for a combined URL, version matched by prefix, boxless parent's visibility unread, flatness in grey. The first thirteen were run before the second review's fixes; the tests they prove still pass.
- Not yet covered: the script-only filter of the CDN rule has no test (it would need the network); a worker that draws a single WebGL frame before the draw counter is installed; a `canvas` inside a cross-origin iframe; pages that scroll inside an element instead of the window; Firefox and WebKit.
