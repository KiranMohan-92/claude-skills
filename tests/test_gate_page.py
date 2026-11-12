"""gate_page.py must FAIL each logged page incident and PASS a page built the right way.

Every page here is one template with a single defect switched on, so a failure can only come from that defect.
Each gate run loads the page three times (normal, reduced motion, WebGL refused), so results are cached per page.
"""
import importlib.util
import re
import sys

import pytest

from conftest import SKILLS, run

GATE = SKILLS / "page-delivery-gates" / "scripts" / "gate_page.py"
pytestmark = pytest.mark.skipif(importlib.util.find_spec("playwright") is None or importlib.util.find_spec("PIL") is None,
                                reason="playwright and pillow not installed")

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>fixture</title>
<style>
  html, body { margin: 0; background: #101018; color: #eee; font: 16px/1.5 sans-serif; }
  canvas { position: fixed; inset: 0; width: 100%; height: 100%; }
  main { position: relative; }
  section { min-height: 100vh; padding: 24px; box-sizing: border-box; }
  .reveal { opacity: 0; transition: opacity .3s; }
  .reveal.on { opacity: 1; }
  .mover { width: 200px; height: 200px; background: #c33; animation: slide 1s linear infinite alternate; }
  @keyframes slide { to { transform: translateX(120px); } }
  .stamp { display: none; position: absolute; top: 150vh; left: 0; width: 430px; height: 40px; background: #3c3; }
  .stamp.on { display: block; }
  @media (prefers-reduced-motion: reduce) { %(reduced_css)s }
</style></head><body>
<canvas id="scene"></canvas>
<main>
  <section><h1>Fixture title</h1><p class="reveal">First block of copy.</p><div class="mover"></div></section>
  <section><h2>Second heading</h2><p class="reveal">Second block of copy, 42 items.</p></section>
  <section><h2>Third heading</h2><p class="reveal">Third block of copy.</p>
    <p><span class="boxless" style="display: contents">A note in a wrapper without a box.</span></p></section>
</main>
<div class="stamp"></div>
%(extra_html)s
<script>
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canvas = document.getElementById('scene');
  const gl = canvas.getContext('webgl');
  %(scene_js)s
  const show = new IntersectionObserver(es => es.forEach(e => e.isIntersecting && e.target.classList.add('on')));
  if (%(reveal_when)s) document.querySelectorAll('.reveal').forEach(el => show.observe(el));
  %(extra_js)s
</script></body></html>
"""

DRAW = """
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const pr = gl.createProgram();
    gl.attachShader(pr, sh(gl.VERTEX_SHADER, 'attribute vec2 p; varying vec2 v; void main(){ v = p; gl_Position = vec4(p, 0., 1.); }'));
    gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, 'precision mediump float; varying vec2 v; void main(){ gl_FragColor = vec4(v * .5 + .5, .6, 1.); }'));
    gl.linkProgram(pr); gl.useProgram(pr);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, 0, 1]), gl.STATIC_DRAW);
    const at = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(at); gl.vertexAttribPointer(at, 2, gl.FLOAT, false, 0, 0);
    const draw = () => { gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT); gl.drawArrays(gl.TRIANGLES, 0, 3);
                         if (!reduced) requestAnimationFrame(draw); };
    draw();
"""

GOOD = dict(
    reduced_css=".mover { animation: none; } .reveal { opacity: 1; transition: none; }",
    scene_js="if (!gl) canvas.style.display = 'none'; else {" + DRAW + "}",
    reveal_when="true", extra_html="", extra_js="")

DEFECTS = {
    "good": {},
    # 2026-10-27: stamps animating in on scroll made a phone-width page 394px wide; nothing overflowed at the top
    "overflow_on_scroll": dict(extra_js="addEventListener('scroll', () => { if (scrollY > 200) "
                                        "document.querySelector('.stamp').classList.add('on'); });"),
    # 2026-09-29 and 2026-10-16: a shader NaN left the scene black behind a working HUD
    "dead_canvas": dict(scene_js="if (!gl) canvas.style.display = 'none';"),
    # 2026-10-20: the scene kept moving with reduced motion on
    "ignores_reduced_motion": dict(reduced_css=".reveal { opacity: 1; transition: none; }"),
    # 2026-10-21: the reduced-motion view was handed over unrendered; here its copy never appears
    "reveal_needs_motion": dict(reduced_css=".mover { animation: none; }", reveal_when="!reduced"),
    # 2026-10-21: same for the no-WebGL view; an unguarded context kills the script before the copy is revealed
    "throws_without_webgl": dict(scene_js="gl.clearColor(0, 0, 0, 1); {" + DRAW + "}"),
    "console_error": dict(extra_js="console.error('scene failed to build');"),
    "missing_asset": dict(extra_html='<img src="poster-that-does-not-exist.png" alt="">'),
    # From the independent review of the first draft: four ways the gate passed a page it had not really checked.
    "grows_on_scroll": dict(extra_js="let grown = false; addEventListener('scroll', () => { "
                                     "if (grown || scrollY + innerHeight < document.documentElement.scrollHeight - 50) return; "
                                     "grown = true; const s = document.createElement('section'); "
                                     "s.innerHTML = '<h2>Loaded on arrival</h2>'; "
                                     "setTimeout(() => document.querySelector('main').append(s), 700); });"),
    "grows_too_late": dict(extra_js="let late = false; addEventListener('scroll', () => { "
                                    "if (late || scrollY + innerHeight < document.documentElement.scrollHeight - 50) return; "
                                    "late = true; const s = document.createElement('section'); "
                                    "s.innerHTML = '<h2>Loaded far too late</h2>'; "
                                    "setTimeout(() => document.querySelector('main').append(s), 2000); });"),
    # A marker that eases towards the scroll position, as a scroll-driven camera does: blue near the top of
    # the page, orange once its eased position has left it.
    "eased_scroll": dict(
        extra_html='<div id="lag" style="position: fixed; top: 20px; right: 20px; width: 100px; height: 100px; '
                   'z-index: 5; background: rgb(0, 90, 255)"></div>'
                   # a placeholder that is replaced 0.6 s after the bottom of the page is reached
                   '<div id="late" style="position: fixed; top: 20px; left: 20px; width: 100px; height: 100px; '
                   'z-index: 5; background: rgb(90, 90, 90)"></div>',
        extra_js="addEventListener('scroll', () => { if (scrollY + innerHeight >= document.documentElement.scrollHeight - 2) "
                 "setTimeout(() => { document.getElementById('late').style.background = 'rgb(0, 160, 60)'; }, 600); }); "
                 "let eased = 0; const lag = document.getElementById('lag'); (function ease() { "
                 "const target = scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight); "
                 "eased += (target - eased) * (reduced ? 1 : 0.03); "
                 "lag.style.background = eased < 0.1 ? 'rgb(0, 90, 255)' : 'rgb(255, 140, 0)'; requestAnimationFrame(ease); })();"),
    "fallback_clipped": dict(reduced_css=".mover { animation: none; } .boxless { visibility: hidden; } "
                                         ".reveal { opacity: 1; transition: none; max-height: 0; overflow: hidden; }"),
    "webgl_inside_a_worker": dict(
        extra_js="new Worker(URL.createObjectURL(new Blob([`const g = new OffscreenCanvas(64, 64).getContext('webgl'); "
                 "setInterval(() => { g.clearColor(Math.random(), .5, .5, 1); g.clear(g.COLOR_BUFFER_BIT); }, 100);`])));"),
    "dead_scene_beside_live_chart": dict(
        scene_js="if (!gl) canvas.style.display = 'none';",
        extra_html='<canvas id="chart" width="300" height="300" '
                   'style="position: relative; display: block; width: 300px; height: 300px"></canvas>',
        extra_js="const cx = document.getElementById('chart').getContext('2d'), fade = cx.createLinearGradient(0, 0, 300, 300); "
                 "fade.addColorStop(0, '#fff'); fade.addColorStop(1, '#036'); cx.fillStyle = fade; cx.fillRect(0, 0, 300, 300);"),
    "webgl_through_offscreen_canvas": dict(
        scene_js="document.createElement('canvas').transferControlToOffscreen(); "
                 "const off = new OffscreenCanvas(8, 8).getContext('webgl'); off.clearColor(0, 0, 0, 1); "
                 "if (!gl) canvas.style.display = 'none'; else {" + DRAW + "}"),
}
_results = {}


@pytest.fixture
def gate(tmp_path_factory):
    def run_gate(defect, *args):
        if (defect, args) not in _results:
            folder, html = tmp_path_factory.mktemp(defect), PAGE
            for key, value in {**GOOD, **DEFECTS[defect]}.items():  # not %-formatting: the CSS is full of "100%"
                html = html.replace(f"%({key})s", value)
            (folder / "index.html").write_text(html, encoding="utf-8")
            _results[defect, args] = run(sys.executable, GATE, folder / "index.html", "--out", folder / "sheets",
                                         "--settle-ms", "300", *(args or ("--viewport", "390x844")), timeout=300), folder
        return _results[defect, args]
    return run_gate


def fail_lines(result):
    return [line for line in result.stdout.splitlines() if line.startswith("FAIL: ")]


def test_good_page_passes_and_writes_a_sheet_per_run(gate):
    r, folder = gate("good")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.rstrip().endswith("PASS")
    # six blocks with boxes of their own, plus one whose parent is display: contents and has none
    assert r.stdout.count(": 7 text blocks") == 3, r.stdout
    assert sorted(p.name for p in (folder / "sheets").iterdir()) == [
        "sheet-390x844-no-webgl.png", "sheet-390x844-normal.png", "sheet-390x844-reduced-motion.png"]


def test_the_sheet_shows_the_page_without_capture_holes(gate):
    # With software compositing, a screenshot showed a page-coloured square punched through the canvas where the
    # red box animates above it (39,800 px at this size). The canvas covers the whole page here, so the page
    # colour must not appear in the normal sheet at all.
    from PIL import Image
    _, folder = gate("good")
    sheet = Image.open(folder / "sheets" / "sheet-390x844-normal.png").convert("RGB")
    assert sheet.width > 4 * 180, "four scroll stops side by side"
    assert sum(count for count, colour in sheet.getcolors(1 << 24) if colour == (16, 16, 24)) == 0


def test_a_drawn_webgl_canvas_is_not_read_as_black(gate):
    # 2026-08-07: a pixel probe that screenshotted the canvas element saw black in headless Chromium and failed a
    # good page. The composited page must show the triangle at every checked stop.
    r, _ = gate("good")
    assert re.search(r"390x844 normal: .*\n\s+note: canvas#scene shows a picture at (\d+) of \1 checked", r.stdout), r.stdout


def test_overflow_that_only_appears_after_scrolling_fails_at_phone_width_only(gate):
    r, _ = gate("overflow_on_scroll", "--viewport", "1440x900", "--viewport", "390x844")
    assert r.returncode == 1, r.stdout + r.stderr
    fails = fail_lines(r)
    assert any("390x844 normal: sideways overflow of 40px" in f and "div.stamp.on" in f for f in fails), fails
    assert not any("1440x900" in f for f in fails), fails


def test_canvas_that_never_draws_fails(gate):
    r, _ = gate("dead_canvas")
    assert r.returncode == 1, r.stdout + r.stderr
    assert any("390x844 normal: canvas#scene never shows a picture" in f for f in fail_lines(r)), r.stdout


def test_motion_that_ignores_reduced_motion_fails_only_in_that_run(gate):
    r, _ = gate("ignores_reduced_motion")
    fails = fail_lines(r)
    assert r.returncode == 1 and fails, r.stdout + r.stderr
    assert all("390x844 reduced-motion: still moving with reduced motion on" in f for f in fails), fails


def test_copy_hidden_with_reduced_motion_fails_and_names_the_text(gate):
    r, _ = gate("reveal_needs_motion")
    fails = fail_lines(r)
    assert r.returncode == 1 and len(fails) == 1, r.stdout + r.stderr
    assert "390x844 reduced-motion: 3 text block(s) shown in the normal run are not shown here" in fails[0]
    assert "'Second block of copy, # items.'" in fails[0]  # digits masked, so counters compare equal


def test_page_that_dies_without_webgl_fails_on_the_error_and_the_lost_copy(gate):
    r, _ = gate("throws_without_webgl")
    fails = fail_lines(r)
    assert r.returncode == 1, r.stdout + r.stderr
    assert all(f.startswith("FAIL: 390x844 no-webgl: ") for f in fails), fails
    assert any("uncaught error" in f for f in fails) and any("3 text block(s)" in f for f in fails), fails


def test_a_section_added_when_the_bottom_is_reached_is_scrolled_too(gate):
    # Scroll stops were worked out once from the page's first height, so anything lazy-loaded below it was never
    # on screen and the gate could pass it unseen. The section here arrives 0.7 s after the bottom is reached.
    r, _ = gate("grows_on_scroll")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.count(": 8 text blocks") == 3, r.stdout


def test_a_section_that_arrives_after_the_scroll_has_ended_fails_as_ungated(gate):
    # The gate waits about a second at the bottom for a load to land. One that lands later was never scrolled, so
    # the load must fail and say so; it must not pass with that section unseen. All three loads must notice,
    # the no-webgl one included: a section can be late only in the fallback.
    r, _ = gate("grows_too_late")
    fails = fail_lines(r)
    assert r.returncode == 1 and len(fails) == 3, r.stdout + r.stderr
    assert all("after it had been scrolled to the bottom" in f and "that part is ungated" in f for f in fails), fails


def test_the_sheet_shows_the_page_at_rest_at_the_top_and_settled_at_the_bottom(gate):
    # 0.11.0 took its stills after scrolling to the bottom and jumping back. A page whose scene eases towards the
    # scroll position was then caught flying back from the end, and the sheet's "0%" frame showed a view no
    # visitor sees on arrival. Here the marker is blue at rest at the top and orange while it is still on its way.
    from PIL import Image
    r, folder = gate("eased_scroll")
    assert r.returncode == 0, r.stdout + r.stderr
    sheet = Image.open(folder / "sheets" / "sheet-390x844-normal.png").convert("RGB")
    scale = 420 / 844                                    # shots are drawn 420px tall, after an 8px gap and a 22px head
    marker = sheet.getpixel((8 + round(320 * scale), 22 + round(70 * scale)))
    assert marker == (0, 90, 255), marker
    # The last frame is taken again after the wait at the bottom, so it shows what loaded there (green), not the
    # placeholder (grey) that was on screen when the bottom was first reached.
    last_shot_left = sheet.width - 8 - round(390 * scale)
    late = sheet.getpixel((last_shot_left + round(70 * scale), 22 + round(70 * scale)))
    assert late == (0, 160, 60), late


def test_copy_clipped_or_hidden_through_a_boxless_parent_counts_as_not_shown(gate):
    # A reveal wrapper left at max-height: 0 keeps its text laid out and "visible", but nobody can read it.
    # Nor can they read text whose display: contents parent is visibility: hidden. Three blocks plus one.
    r, _ = gate("fallback_clipped")
    fails = fail_lines(r)
    assert r.returncode == 1 and len(fails) == 1, r.stdout + r.stderr
    assert "390x844 reduced-motion: 4 text block(s) shown in the normal run are not shown here" in fails[0]


def test_webgl_drawn_inside_a_worker_makes_the_no_webgl_load_unverified(gate):
    # A worker can make its own OffscreenCanvas context, out of reach of the page script that refuses WebGL.
    r, _ = gate("webgl_inside_a_worker")
    fails = fail_lines(r)
    assert r.returncode == 1 and len(fails) == 1, r.stdout + r.stderr
    assert "390x844 no-webgl: a worker drew with WebGL during this load" in fails[0]


def test_a_live_chart_does_not_vouch_for_a_dead_scene(gate):
    # With one verdict for all canvases, a drawn 2D chart made the stop count as healthy and hid a blank scene.
    r, _ = gate("dead_scene_beside_live_chart")
    fails = fail_lines(r)
    assert r.returncode == 1, r.stdout + r.stderr
    assert any("390x844 normal: canvas#scene never shows a picture" in f for f in fails), fails
    assert not any("canvas#chart" in f for f in fails), fails
    assert "note: canvas#chart shows a picture" in r.stdout


def test_webgl_through_an_offscreen_canvas_is_refused_too_and_a_handed_off_canvas_is_unverified(gate):
    # The no-WebGL load only refused contexts on page canvases, so a scene drawing through OffscreenCanvas kept
    # its WebGL and the "fallback" that passed was never the fallback.
    r, _ = gate("webgl_through_offscreen_canvas")
    fails = fail_lines(r)
    assert r.returncode == 1, r.stdout + r.stderr
    assert all(f.startswith("FAIL: 390x844 no-webgl: ") for f in fails), fails
    assert any("uncaught error" in f for f in fails) and any("the no-WebGL view is unverified" in f for f in fails), fails


def test_ignore_accepts_text_that_is_meant_to_be_absent(gate):
    r, _ = gate("reveal_needs_motion", "--viewport", "390x844", "--ignore", "block of copy")
    assert r.returncode == 0, r.stdout + r.stderr


def test_console_error_and_missing_asset_fail(gate):
    r, _ = gate("console_error")
    assert r.returncode == 1 and any("console error: scene failed to build" in f for f in fail_lines(r)), r.stdout
    r, _ = gate("missing_asset")
    assert r.returncode == 1 and any("HTTP 404" in f and "poster-that-does-not-exist.png" in f for f in fail_lines(r)), r.stdout


def test_missing_page_is_a_usage_error(tmp_path):
    r = run(sys.executable, GATE, tmp_path / "nope.html")
    assert r.returncode == 2 and "no such page" in r.stderr


def test_missing_browser_is_exit_2_with_the_fix_named_not_a_failed_page(tmp_path):
    # Exit 1 means "the page failed". A gate that could not start must not look like that.
    (tmp_path / "index.html").write_text("<!doctype html><title>x</title><p>Some text.</p>", encoding="utf-8")
    r = run(sys.executable, GATE, tmp_path / "index.html", "--channel", "no-such-browser-channel")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "no browser to run the gate in" in r.stderr and "--channel chrome" in r.stderr
    assert "PASS" not in r.stdout and "FAIL" not in r.stdout


def test_a_fragment_is_served_as_a_utf8_document_and_a_full_page_untouched(tmp_path):
    # Review pages written for a host that adds the doctype and charset were served bare: the browser guessed
    # Windows-1252, so "18–20 Oct · retro" reached the sheet as mojibake, in quirks mode.
    import urllib.request
    sys.path.insert(0, str(GATE.parent))
    from gate_page import serve
    fragment = "<title>Retro</title><p>18–20 Oct · retro</p>"
    full = "<!DOCTYPE html><html><head><title>x</title></head><body><p>18–20 Oct</p></body></html>"
    (tmp_path / "fragment.html").write_text(fragment, encoding="utf-8")
    (tmp_path / "full.html").write_text(full, encoding="utf-8")
    url, server = serve(tmp_path / "fragment.html")
    try:
        with urllib.request.urlopen(url) as r:
            assert r.headers["Content-Type"] == "text/html; charset=utf-8"
            body = r.read().decode("utf-8")
        assert body.startswith("<!doctype html>") and '<meta charset="utf-8">' in body and fragment in body
        with urllib.request.urlopen(url.replace("fragment.html", "full.html")) as r:
            assert r.headers["Content-Type"] == "text/html; charset=utf-8"
            assert r.read().decode("utf-8") == full
    finally:
        server.shutdown()
    # a # in the file name must reach the server, not be read by the browser as a fragment
    (tmp_path / "landing#v2.html").write_text(full, encoding="utf-8")
    url, server = serve(tmp_path / "landing#v2.html")
    try:
        assert url.endswith("/landing%23v2.html")
        with urllib.request.urlopen(url) as r:
            assert r.read().decode("utf-8") == full
    finally:
        server.shutdown()


def test_scroll_stops_stay_less_than_a_screen_apart_and_follow_a_page_that_grows():
    # A 43,584px page (52 phone screens) was scrolled in 40 capped stops, 1.3 screens apart. Text between stops
    # was never on screen, and eight blocks were reported missing that were there in every load.
    sys.path.insert(0, str(GATE.parent))
    from gate_page import next_stop
    stops, y = [0], 0
    while (y := next_stop(y, 43584 - 844, 844)) is not None:
        stops.append(y)
    assert stops[-1] == 43584 - 844 and max(b - a for a, b in zip(stops, stops[1:])) < 844
    assert next_stop(0, 0, 844) is None                    # a page of one screen has one stop
    assert next_stop(1000, 1000, 844) is None              # at the bottom
    assert next_stop(1000, 1900, 844) == 1000 + 675        # the page grew while we stood at its old bottom


def test_unpinned_cdn_urls_are_found():
    sys.path.insert(0, str(GATE.parent))
    from gate_page import unpinned_cdn
    assert unpinned_cdn([
        "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",   # exact: fine
        "https://unpkg.com/three@0.170.0/examples/jsm/controls/OrbitControls.js",
        "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js",  # version is in every cdnjs path
        "https://fonts.googleapis.com/css2?family=Inter",                     # not an npm CDN
        "https://unpkg.com/three/build/three.module.js",                      # no version
        "https://cdn.jsdelivr.net/npm/three@latest/build/three.module.js",
        "https://esm.sh/three@0.170",                                         # a range, not a version
        "https://cdn.jsdelivr.net/npm/react@19.0.0-rc.1/index.js",            # a pre-release is still exact
        "https://cdn.jsdelivr.net/combine/npm/a@1.2.3/a.js,npm/b@2.0.0/b.js",  # every package pinned
        "https://cdn.jsdelivr.net/combine/npm/a@1.2.3/a.js,npm/b/b.js",        # one of two is not
        "https://cdn.jsdelivr.net/npm/react@18.2.0%20-%2019.0.0/index.js",     # a range that starts like a version
    ]) == ["https://cdn.jsdelivr.net/combine/npm/a@1.2.3/a.js,npm/b/b.js",
           "https://cdn.jsdelivr.net/npm/react@18.2.0%20-%2019.0.0/index.js",
           "https://cdn.jsdelivr.net/npm/three@latest/build/three.module.js", "https://esm.sh/three@0.170",
           "https://unpkg.com/three/build/three.module.js"]


def test_two_colours_of_equal_grey_are_a_picture_and_one_colour_is_not():
    from PIL import Image
    sys.path.insert(0, str(GATE.parent))
    from gate_page import FLAT_RANGE, colour_range
    split = Image.new("RGB", (40, 20), (97, 0, 0))
    split.paste((0, 0, 255), (20, 0, 40, 20))
    assert split.convert("L").getextrema() == (29, 29)  # the incident: flat in grey
    assert colour_range(split) >= FLAT_RANGE
    assert colour_range(Image.new("RGB", (40, 20), (0, 0, 0))) == 0
