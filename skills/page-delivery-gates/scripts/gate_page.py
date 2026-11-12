#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.49", "pillow>=10"]
# ///
"""Gate a web page before hand-off: load it the ways a viewer can and fail on what a viewer would hit.

usage: gate_page.py PAGE [--out DIR] [--viewport WxH ...] [--settle-ms N] [--ignore TEXT ...] [--channel NAME]

PAGE is a URL or a local .html file. A file is served over http from its own folder, because file:// blocks
module imports and fetch. Each viewport (default 1440x900 and 390x844) is loaded three times:
  normal          console and uncaught errors, failed requests, sideways overflow at every scroll stop,
                  and whether each large canvas ever shows a picture
  reduced-motion  the same, plus: every text block seen in the normal run is still shown, and the page
                  holds still when nobody is scrolling
  no-webgl        WebGL contexts are refused: no uncaught error, and every text block is still shown
It also fails on scripts loaded from an npm CDN without an exact version, and writes one contact sheet per
run (five scroll positions) to --out for the visual review.

Exit: 0 PASS, 1 FAIL (each failure printed), 2 usage, no browser, or the page could not be loaded or checked.
"""
import argparse
import functools
import http.server
import io
import math
import re
import sys
import tempfile
import threading
import urllib.parse
from pathlib import Path

NPM_CDN = ("cdn.jsdelivr.net", "unpkg.com", "esm.sh", "esm.run", "cdn.skypack.dev", "ga.jspm.io")
# A whole version selector: 1.2.3 or 1.2.3-beta.1, ending at a "/" or the end of the path. A range such as
# "1.2.3 - 2.0.0" starts the same way, so matching only a prefix would let it through.
EXACT_VERSION = re.compile(r"@v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?(?=/|$)")
FLAT_RANGE = 8        # of 255: a canvas where no colour channel varies by more than this shows nothing
MOVED_LEVEL = 24      # of 255: a pixel that changed by more than this between two stills counts as moved
MOVED_SHARE = 0.002   # share of the viewport allowed to move with reduced motion on (a caret, not a scene)
BIG_CANVAS = 0.15     # share of the viewport a canvas must cover to be judged as "the scene"
MAX_STOPS = 200       # about 160 screens; a page still going after that fails as ungated, it is never cut short
SHOT_AT = (0, 0.25, 0.5, 0.75, 1)

# Counts WebGL context requests and refuses them in the no-webgl run, for page canvases and for OffscreenCanvas
# on the main thread. A canvas handed to a worker draws where this script does not run, so that is counted.
INIT_JS = """(() => {
  window.__gate = {asked: 0, got: 0, handedOff: 0};
  for (const proto of [HTMLCanvasElement.prototype, window.OffscreenCanvas && OffscreenCanvas.prototype]) {
    if (!proto) continue;
    const real = proto.getContext;
    proto.getContext = function (type, ...rest) {
      const gl = /webgl/i.test(String(type));
      if (gl) window.__gate.asked++;
      if (gl && NO_WEBGL) return null;
      const ctx = real.call(this, type, ...rest);
      if (gl && ctx) window.__gate.got++;
      return ctx;
    };
  }
  const handOff = HTMLCanvasElement.prototype.transferControlToOffscreen;
  if (handOff) HTMLCanvasElement.prototype.transferControlToOffscreen = function (...args) {
    window.__gate.handedOff++;
    return handOff.apply(this, args);
  };
})()"""

# Text a viewer can read right now: in the viewport, not display:none, not hidden, not at opacity 0, and not
# cut away by an ancestor that clips its overflow (a reveal wrapper left at max-height: 0).
# Digits are masked so a counter caught mid-animation still matches its final value.
VISIBLE_TEXT_JS = """() => {
  const vw = document.documentElement.clientWidth, vh = innerHeight, out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), range = document.createRange();
  const afterClipping = (el, r) => {
    let left = r.left, top = r.top, right = r.right, bottom = r.bottom, escaping = false;
    for (let e = el; e && e !== document.body && e !== document.documentElement; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.display === 'contents') continue;
      // An absolutely positioned box is clipped by its containing block, not by static ancestors in between.
      if (!escaping || s.position !== 'static' || s.transform !== 'none') {
        escaping = false;
        const c = e.getBoundingClientRect();
        if (s.overflowX !== 'visible') { left = Math.max(left, c.left); right = Math.min(right, c.right); }
        if (s.overflowY !== 'visible') { top = Math.max(top, c.top); bottom = Math.min(bottom, c.bottom); }
      }
      if (s.position === 'fixed') break;
      if (s.position === 'absolute') escaping = true;
    }
    return {left, top, right, bottom};
  };
  for (let n; (n = walker.nextNode());) {
    const text = n.nodeValue.replace(/\\s+/g, ' ').trim(), el = n.parentElement;
    if (text.length < 2 || !el || el.closest('script,style,noscript,template')) continue;
    // A display: contents parent has no box of its own, so visibility is asked of the nearest ancestor that has.
    // Its own `visibility` still applies to the text, and is inherited, so that is read from the parent itself.
    if (getComputedStyle(el).visibility !== 'visible') continue;
    let box = el;
    while (box && getComputedStyle(box).display === 'contents') box = box.parentElement;
    if (!box || !box.checkVisibility({opacityProperty: true, visibilityProperty: true})) continue;
    range.selectNodeContents(n);
    const raw = range.getBoundingClientRect();
    if (raw.width < 1 || raw.height < 1 || raw.bottom <= 0 || raw.top >= vh || raw.right <= 0 || raw.left >= vw) continue;
    const r = afterClipping(el, raw);
    if (r.right - r.left < 1 || r.bottom - r.top < 1 || r.bottom <= 0 || r.top >= vh || r.right <= 0 || r.left >= vw) continue;
    out.push(text.replace(/\\d[\\d.,:%]*/g, '#'));
  }
  return out;
}"""

# Scrolls the element holding a text block into view. Returns false when the page has no such text at all.
FIND_TEXT_JS = """(want) => {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = walker.nextNode());) {
    const text = n.nodeValue.replace(/\\s+/g, ' ').trim().replace(/\\d[\\d.,:%]*/g, '#');
    if (text.includes(want) && n.parentElement && !n.parentElement.closest('script,style,noscript,template')) {
      n.parentElement.scrollIntoView({block: 'center', behavior: 'instant'});
      return true;
    }
  }
  return false;
}"""

# Run inside each worker of the no-webgl load. No script can be put into a worker before it starts, so a
# context made there cannot be refused. WebGL prototypes are shared with contexts that already exist, though,
# so a hook installed late still counts every draw call after it.
WORKER_DRAWS_JS = """() => {
  self.__gateDraws = self.__gateDraws || 0;
  for (const name of ['WebGLRenderingContext', 'WebGL2RenderingContext']) {
    const proto = self[name] && self[name].prototype;
    if (!proto || proto.__gateCounted) continue;
    proto.__gateCounted = true;
    for (const call of ['drawArrays', 'drawElements', 'clear']) {
      const real = proto[call];
      proto[call] = function (...args) { self.__gateDraws++; return real.apply(this, args); };
    }
  }
  return self.__gateDraws;
}"""

OVERFLOW_JS = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
SCROLLABLE_JS = "() => Math.max(0, document.scrollingElement.scrollHeight - innerHeight)"

# The deepest element sticking out past the right edge: where to start looking for the cause.
WIDEST_JS = """() => {
  const vw = document.documentElement.clientWidth;
  let worst = null, right = vw + 0.5;
  for (const el of document.body.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.right >= right) { worst = el; right = r.right; }
  }
  if (!worst) return '';
  const cls = typeof worst.className === 'string' && worst.className.trim() ? '.' + worst.className.trim().split(/\\s+/).join('.') : '';
  return worst.tagName.toLowerCase() + (worst.id ? '#' + worst.id : '') + cls + ' (right edge at ' + Math.round(right) + 'px)';
}"""

# Every visible canvas covering a large share of the view, tagged so each can be shown on its own.
BIG_CANVASES_JS = """(share) => [...document.querySelectorAll('canvas')].map((c, i) => {
  const r = c.getBoundingClientRect();
  const box = [Math.max(0, r.left), Math.max(0, r.top), Math.min(innerWidth, r.right), Math.min(innerHeight, r.bottom)];
  const big = box[2] > box[0] && box[3] > box[1] && (box[2] - box[0]) * (box[3] - box[1]) >= share * innerWidth * innerHeight;
  if (!big || !c.checkVisibility({opacityProperty: true, visibilityProperty: true})) return null;
  c.setAttribute('data-gate-canvas', i);
  return {i, label: c.id ? 'canvas#' + c.id : 'canvas ' + (i + 1), box};
}).filter(Boolean)"""

# A WebGL canvas read back in headless Chromium returns an empty buffer, so a canvas is judged from the
# composited page instead, with everything hidden except that one canvas (a second canvas drawn over it would
# otherwise vouch for it).
ONLY_CANVAS_CSS = ('*{visibility:hidden!important}canvas[data-gate-canvas="INDEX"]{visibility:visible!important}'
                   'html,body{background:#000!important}')


def unpinned_cdn(urls):
    """Script URLs on an npm CDN that don't name an exact x.y.z version (latest, a range, or none)."""
    bad = []
    for url in urls:
        m = re.match(r"https?://([^/]+)(/[^?#]*)", url)
        # A combined URL ("/combine/npm/a@1.2.3,npm/b") names several packages; each needs its own version.
        if m and m.group(1) in NPM_CDN and not all(EXACT_VERSION.search(part) for part in m.group(2).split(",")):
            bad.append(url)
    return sorted(set(bad))


def next_stop(y, scrollable, height):
    """The next scroll position, less than one screen further down, or None once y is the bottom.

    `scrollable` is asked of the page again before every step, because a page can grow as it is scrolled
    (lazy sections, late images). The number of stops is not tied to the page's first height, and a gap of a
    screen or more between stops would leave text that no load ever had on screen.
    """
    return None if y >= scrollable else min(y + math.floor(0.8 * height), scrollable)


FRAGMENT_HEAD = (b'<!doctype html><html><head><meta charset="utf-8">'
                 b'<meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0}</style></head><body>')


def is_fragment(html):
    """A page body with no document around it, as written for a host that adds the doctype and charset itself."""
    head = html[:2048].lower()
    return b"<!doctype" not in head and b"<html" not in head


class PageHandler(http.server.SimpleHTTPRequestHandler):
    # Windows can map .js to text/plain from the registry, and browsers then refuse module scripts.
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".mjs": "text/javascript", ".wasm": "application/wasm"}

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = Path(self.translate_path(self.path))
        if path.suffix.lower() not in (".html", ".htm") or not path.is_file():
            return super().do_GET()
        # Served bare, a fragment is guessed to be Windows-1252 (so a dash arrives as mojibake) and laid out in
        # quirks mode: a page no viewer gets. Its host wraps it in a document, so the gate does the same.
        body = path.read_bytes()
        if is_fragment(body):
            body = FRAGMENT_HEAD + body + b"</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(path):
    """Serve a local page's folder on a free port; returns (url, server)."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(PageHandler, directory=str(path.parent)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # Quoted, or a name like "landing#v2.html" loses everything after the # on its way to the server.
    return f"http://127.0.0.1:{server.server_address[1]}/{urllib.parse.quote(path.name)}", server


RENDERER_JS = """() => {
  const gl = document.createElement('canvas').getContext('webgl');
  const info = gl && gl.getExtension('WEBGL_debug_renderer_info');
  return gl ? (info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : 'WebGL') : '';
}"""


def launch(pw, channel):
    """Full Chromium (not the headless shell), on the hardware GPU when there is one. Returns (browser, renderer).

    With software compositing (the headless shell, or no GPU) a screenshot shows a page-coloured hole in the
    canvas wherever an element animates above it: a defect in the capture, not the page. Running SwiftShader as
    the GPU keeps GPU compositing and has no hole, but is slow, so it is used only when no hardware GPU answers.
    """
    flags = ["--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]
    browser = pw.chromium.launch(channel=channel or "chromium", args=flags)
    page = browser.new_page()
    renderer = page.evaluate(RENDERER_JS)
    page.close()
    if renderer and "SwiftShader" not in renderer:
        return browser, renderer
    browser.close()
    return pw.chromium.launch(channel=channel or "chromium", args=flags + ["--use-angle=swiftshader"]), "SwiftShader (no hardware GPU)"


def worker_draws(page):
    """Install the draw counter in every worker (once each) and return the draw calls counted so far."""
    from playwright.sync_api import Error
    total = 0
    for worker in page.workers:
        try:
            total += worker.evaluate(WORKER_DRAWS_JS)
        except Error:  # a worker that has already exited has nothing to draw with
            pass
    return total


def shot(page):
    from PIL import Image
    return Image.open(io.BytesIO(page.screenshot())).convert("RGB")


def colour_range(image):
    """The widest spread of any one colour channel. In grey, (97, 0, 0) and (0, 0, 255) are both 29."""
    return max(hi - lo for lo, hi in image.convert("RGB").getextrema())


def canvas_shows_picture(page, canvas):
    tag = page.add_style_tag(content=ONLY_CANVAS_CSS.replace("INDEX", str(canvas["i"])))
    img = shot(page)
    tag.evaluate("el => el.remove()")
    left, top, right, bottom = canvas["box"]
    return colour_range(img.crop((int(left), int(top), math.ceil(right), math.ceil(bottom)))) >= FLAT_RANGE


def moved_share(a, b):
    from PIL import ImageChops
    hist = ImageChops.difference(a, b).convert("L").histogram()
    return sum(hist[MOVED_LEVEL + 1:]) / (a.width * a.height)


def contact_sheet(shots, title, path):
    """Shots at 420px tall, wrapped into rows no wider than 2000px so a wide viewport stays readable."""
    from PIL import Image, ImageDraw
    height, gap, head, max_width = 420, 8, 22, 2000
    thumbs = [(pct, im.resize((max(1, round(im.width * height / im.height)), height))) for pct, im in shots]
    rows = [[]]
    for item in thumbs:
        if rows[-1] and sum(t.width + gap for _, t in rows[-1]) + item[1].width + gap > max_width:
            rows.append([])
        rows[-1].append(item)
    width = max(sum(t.width + gap for _, t in row) for row in rows) + gap
    sheet = Image.new("RGB", (width, head + len(rows) * (height + gap)), "#202020")
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 5), title, fill="#ffffff")
    for r, row in enumerate(rows):
        x, y = gap, head + r * (height + gap)
        for pct, thumb in row:
            sheet.paste(thumb, (x, y))
            draw.rectangle((x, y, x + 34, y + 14), fill="#202020")
            draw.text((x + 3, y + 1), f"{pct}%", fill="#ffffff")
            x += thumb.width + gap
    sheet.save(path)


def run_mode(browser, url, size, mode, args, baseline):
    """One load of the page. Returns (failures, notes, visible text, script urls)."""
    width, height = size
    fails, notes, errors, scripts = [], [], [], set()
    context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1,
                                  reduced_motion="reduce" if mode == "reduced-motion" else "no-preference")
    context.add_init_script(INIT_JS.replace("NO_WEBGL", "true" if mode == "no-webgl" else "false"))
    page = context.new_page()

    def on_console(msg):
        # Failed loads are reported once, with their URL, by on_response / on_failed.
        if msg.type == "error" and not msg.text.startswith("Failed to load resource"):
            errors.append(f"console error: {msg.text[:200]}")

    def on_response(resp):
        # Browsers ask for /favicon.ico unprompted; a page without one isn't broken.
        if resp.status >= 400 and not resp.url.endswith("/favicon.ico"):
            errors.append(f"HTTP {resp.status}: {resp.url}")

    def on_failed(req):
        # ERR_ABORTED is the browser cancelling its own request (a media range, a navigation), not a failure.
        if "ERR_ABORTED" not in (req.failure or ""):
            errors.append(f"request failed ({req.failure}): {req.url}")

    def on_request(req):
        if req.resource_type == "script":  # the version rule is about code; an image on the same CDN is not code
            scripts.add(req.url)

    uncaught = []
    page.on("pageerror", lambda exc: uncaught.append(f"uncaught error: {str(exc)[:200]}"))
    page.on("request", on_request)
    if mode != "no-webgl":  # a refused context makes libraries log errors; only an uncaught one counts there
        page.on("console", on_console)
        page.on("response", on_response)
        page.on("requestfailed", on_failed)

    page.goto(url, wait_until="load", timeout=60_000)
    try:
        page.wait_for_load_state("networkidle", timeout=5_000)
    except Exception:  # a page that polls or streams never goes idle; the settle wait below still applies
        pass
    page.evaluate("document.fonts.ready.then(() => true)")
    page.wait_for_timeout(args.settle_ms)
    if mode == "no-webgl":
        worker_draws(page)

    # First pass, every stop from top to bottom: sideways overflow, and the text on screen.
    seen, worst, y, count = [], (0, 0, ""), 0, 0
    while y is not None:
        page.evaluate("y => window.scrollTo({top: y, behavior: 'instant'})", y)
        for _ in range(3):  # an element can widen the page only while it animates in
            page.wait_for_timeout(120)
            over = page.evaluate(OVERFLOW_JS)
            if over > worst[0]:
                worst = (over, y, page.evaluate(WIDEST_JS))
        seen += page.evaluate(VISIBLE_TEXT_JS)
        count += 1
        scrollable = page.evaluate(SCROLLABLE_JS)
        following = next_stop(y, scrollable, height)
        if following is None:  # what looks like the bottom: a load started by arriving here gets time to land
            try:
                page.wait_for_load_state("networkidle", timeout=2_000)
            except Exception:
                pass
            page.wait_for_timeout(1000)
            scrollable = page.evaluate(SCROLLABLE_JS)
            following = next_stop(y, scrollable, height)
        y = following
        if y is not None and count >= MAX_STOPS:
            fails.append(f"the page was still going after {count} scroll stops ({scrollable + height}px so far): "
                         "everything below is ungated")
            break

    def percent(pos):
        return round(100 * pos / scrollable) if scrollable else 0

    # Second pass, five positions of the page at its final length: stills, stillness, and each large canvas.
    shots, canvases = [], {}
    for y in sorted({round(scrollable * f) for f in SHOT_AT}):
        page.evaluate("y => window.scrollTo({top: y, behavior: 'instant'})", y)
        page.wait_for_timeout(400)
        still = shot(page)
        if mode == "reduced-motion":
            page.wait_for_timeout(600)
            later = shot(page)
            share = moved_share(still, later)
            if share > MOVED_SHARE:  # a fade started by the scroll may still be finishing: look once more
                page.wait_for_timeout(1000)
                still = shot(page)
                page.wait_for_timeout(600)
                later = shot(page)
                share = moved_share(still, later)
            if share > MOVED_SHARE:
                fails.append(f"still moving with reduced motion on: {share:.1%} of the view changed in 0.6 s "
                             f"at {percent(y)}% scroll")
            still = later
        shots.append((percent(y), still))
        if mode != "no-webgl":
            for canvas in page.evaluate(BIG_CANVASES_JS, BIG_CANVAS):
                record = canvases.setdefault(canvas["label"], {"checked": 0, "pictured": 0, "flat": []})
                record["checked"] += 1
                if canvas_shows_picture(page, canvas):
                    record["pictured"] += 1
                else:
                    record["flat"].append(f"{percent(y)}%")

    grew = page.evaluate(SCROLLABLE_JS) - scrollable
    if grew > 50:  # px; smaller shifts are fonts and images settling
        fails.append(f"the page grew by {grew}px after it had been scrolled to the bottom (a slow lazy load?): "
                     "that part is ungated")
    gl = page.evaluate("() => window.__gate")
    if mode == "normal" and gl["asked"] and not gl["got"]:
        fails.append("the page asked for WebGL and this browser gave none, so the scene is unverified "
                     "(rerun with --channel chrome)")
    else:
        for label, record in canvases.items():
            if not record["pictured"]:
                fails.append(f"{label} never shows a picture (flat at every checked scroll stop: {', '.join(record['flat'])})")
                continue
            notes.append(f"{label} shows a picture at {record['pictured']} of {record['checked']} checked scroll stops")
            if record["flat"]:
                notes.append(f"{label} is flat at {', '.join(record['flat'])} scroll: look at the sheet")
    if mode == "no-webgl" and worker_draws(page):
        fails.append("a worker drew with WebGL during this load, where WebGL cannot be refused: "
                     "the no-WebGL view is unverified")
    if mode == "no-webgl" and gl["handedOff"]:
        fails.append("a canvas was handed to an OffscreenCanvas, which can draw in a worker where this run cannot "
                     "refuse WebGL: the no-WebGL view is unverified")
    if worst[0] > 0:
        fails.append(f"sideways overflow of {worst[0]}px at {percent(worst[1])}% scroll "
                     f"(page is {width + worst[0]}px wide in a {width}px view); widest: {worst[2] or 'unknown'}")
    fails += sorted(set(uncaught)) + sorted(set(errors))

    seen = list(dict.fromkeys(seen))
    if baseline is not None:
        joined = " ".join(seen)
        missing = [t for t in baseline if t not in joined and not any(skip in t for skip in args.ignore)]
        for text in missing[:40]:  # give a slow reveal a second, centred look before calling it missing
            if page.evaluate(FIND_TEXT_JS, text):
                for _ in range(3):
                    page.wait_for_timeout(350)
                    if text in " ".join(page.evaluate(VISIBLE_TEXT_JS)):
                        missing.remove(text)
                        break
        if missing:
            sample = "; ".join(repr(t[:60]) for t in missing[:5])
            fails.append(f"{len(missing)} text block(s) shown in the normal run are not shown here: {sample}")

    contact_sheet(shots, f"{width}x{height}  {mode}", args.out / f"sheet-{width}x{height}-{mode}.png")
    context.close()
    return fails, notes, seen, scripts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("page", help="URL or local .html file")
    ap.add_argument("--out", type=Path, help="folder for the contact sheets (default: a new temp folder)")
    ap.add_argument("--viewport", action="append", metavar="WxH", help="repeatable; default 1440x900 and 390x844")
    ap.add_argument("--settle-ms", type=int, default=2000, help="wait after load before checking (default 2000)")
    ap.add_argument("--ignore", action="append", default=[], metavar="TEXT",
                    help="text that may be absent with motion or WebGL off, e.g. a 'Scroll to begin' hint (repeatable)")
    ap.add_argument("--channel", help="use an installed browser (chrome, msedge) instead of Playwright's Chromium")
    args = ap.parse_args()

    sizes = []
    for spec in args.viewport or ["1440x900", "390x844"]:
        m = re.fullmatch(r"(\d+)x(\d+)", spec)
        if not m:
            ap.error(f"--viewport wants WxH, got {spec!r}")
        sizes.append((int(m.group(1)), int(m.group(2))))
    url, server = args.page, None
    if not re.match(r"https?://", url):
        path = Path(url).resolve()
        if not path.is_file():
            print(f"no such page: {path}", file=sys.stderr)
            return 2
        url, server = serve(path)
        if is_fragment(path.read_bytes()):
            print("note: this file is a fragment (no doctype); served inside a minimal UTF-8 document, as its host would")
    args.out = args.out or Path(tempfile.mkdtemp(prefix="page-gate-"))
    args.out.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import Error, sync_playwright
    failures = []
    print(f"page: {args.page}")
    with sync_playwright() as pw:
        try:
            browser, renderer = launch(pw, args.channel)
        except Error as exc:
            if server:
                server.shutdown()
            print(f"no browser to run the gate in: {str(exc).splitlines()[0]}\n"
                  "install one with `python -m playwright install chromium`, or pass --channel chrome", file=sys.stderr)
            return 2
        print(f"browser: {args.channel or 'chromium'} {browser.version}, WebGL on {renderer}", flush=True)
        try:
            for n, size in enumerate(sizes):
                baseline = None
                for mode in ("normal", "reduced-motion", "no-webgl"):
                    label = f"{size[0]}x{size[1]} {mode}"
                    fails, notes, seen, scripts = run_mode(browser, url, size, mode, args, baseline)
                    if mode == "normal":
                        baseline = seen
                        if n == 0:
                            fails += [f"script from a CDN without an exact version: {u}" for u in unpinned_cdn(scripts)]
                    print(f"{'FAIL' if fails else 'ok  '}  {label}: {len(seen)} text blocks" + "".join(f"\n      note: {x}" for x in notes),
                          flush=True)
                    failures += [f"{label}: {f}" for f in fails]
        except Error as exc:
            print(f"the page could not be loaded or checked: {str(exc).splitlines()[0]}", file=sys.stderr)
            return 2
        finally:
            browser.close()
            if server:
                server.shutdown()
    for f in failures:
        print(f"FAIL: {f}")
    print(f"sheets: {args.out}")
    print("FAIL" if failures else "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
