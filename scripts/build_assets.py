#!/usr/bin/env python3
"""
Build the profile's SVG assets from one set of design tokens.

Display type is converted to vector paths so every asset renders identically
on GitHub (SVGs shown through GitHub's image proxy cannot load web fonts).

    pip install fonttools
    python scripts/build_assets.py

Fonts (SIL Open Font License) are downloaded from github.com/google/fonts
into scripts/.fonts/ on first run.
"""
import math
import os
import urllib.request

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
FONT_DIR = os.path.join(ROOT, "scripts", ".fonts")

# ── Design tokens ────────────────────────────────────────────────────────────
# Channel colours carry meaning and are never used decoratively:
#   signal       → hardware, RF, firmware, sensing
#   system       → software that moves and presents data
#   intelligence → models and agents that act on it
INK = "#060A13"        # panel background ("scope glass")
GRID = "#0F1930"       # graticule
LINE = "#1F2C4A"       # borders, idle edges
TEXT = "#E6EBF5"
MUTED = "#7D88A8"
SIGNAL = "#3DE7FF"
SYSTEM = "#8B6CFF"
INTEL = "#FF4FD8"

FONTS = {
    "display": "ofl/michroma/Michroma-Regular.ttf",
    "mono": "ofl/ibmplexmono/IBMPlexMono-Regular.ttf",
    "mono_md": "ofl/ibmplexmono/IBMPlexMono-Medium.ttf",
}


def n(v):
    """Compact number formatting for path data."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class Face:
    def __init__(self, rel):
        os.makedirs(FONT_DIR, exist_ok=True)
        path = os.path.join(FONT_DIR, os.path.basename(rel))
        if not os.path.exists(path):
            urllib.request.urlretrieve(
                "https://raw.githubusercontent.com/google/fonts/main/" + rel, path)
        self.font = TTFont(path)
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm
        self.hmtx = self.font["hmtx"]

    def _glyph(self, ch):
        g = self.cmap.get(ord(ch))
        if g is None:
            raise ValueError(f"glyph missing for {ch!r}")
        return g

    def width(self, text, size, tracking=0.0):
        s = size / self.upm
        return sum(self.hmtx[self._glyph(c)][0] * s + tracking for c in text) - tracking

    def path(self, text, size, x, y, tracking=0.0, anchor="start"):
        if anchor == "middle":
            x -= self.width(text, size, tracking) / 2
        elif anchor == "end":
            x -= self.width(text, size, tracking)
        s = size / self.upm
        pen = SVGPathPen(self.glyphs, ntos=n)
        for c in text:
            g = self._glyph(c)
            self.glyphs[g].draw(TransformPen(pen, (s, 0, 0, -s, x, y)))
            x += self.hmtx[g][0] * s + tracking
        return pen.getCommands()


D = Face(FONTS["display"])
M = Face(FONTS["mono"])
MM = Face(FONTS["mono_md"])


def text(face, s, size, x, y, fill, tracking=0.0, anchor="start", extra=""):
    return f'<path {extra} fill="{fill}" d="{face.path(s, size, x, y, tracking, anchor)}"/>'


def graticule(w, h, cols, rows, pad=0):
    """Oscilloscope graticule: major divisions plus minor ticks on the centre axes."""
    out = []
    for i in range(1, cols):
        x = pad + i * (w - 2 * pad) / cols
        out.append(f'<line x1="{n(x)}" y1="{pad}" x2="{n(x)}" y2="{h - pad}"/>')
    for j in range(1, rows):
        y = pad + j * (h - 2 * pad) / rows
        out.append(f'<line x1="{pad}" y1="{n(y)}" x2="{w - pad}" y2="{n(y)}"/>')
    cx, cy = w / 2, h / 2
    step = (w - 2 * pad) / cols / 5
    x = pad
    while x < w - pad:
        out.append(f'<line x1="{n(x)}" y1="{n(cy - 3)}" x2="{n(x)}" y2="{n(cy + 3)}"/>')
        x += step
    return f'<g stroke="{GRID}" stroke-width="1">{"".join(out)}</g>'


def write(name, svg):
    os.makedirs(ASSETS, exist_ok=True)
    with open(os.path.join(ASSETS, name), "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"  assets/{name:<24} {len(svg.encode()) / 1024:6.1f} KB")


REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"


# ── Hero ─────────────────────────────────────────────────────────────────────
def hero():
    W, H = 1200, 420
    base = 318
    amp = 30
    lam = 78.0

    def wave(x):
        return base - amp * math.sin(2 * math.pi * (x - 110) / lam)

    # Analog stage: continuous wave
    pts = [(x, wave(x)) for x in range(110, 501, 2)]
    sine = "M" + " L".join(f"{n(x)} {n(y)}" for x, y in pts)

    # Sampling stage: the same wave, sampled and quantised to 8 levels
    stems = []
    levels = 8
    for i, x in enumerate(range(584, 861, 13)):
        v = math.sin(2 * math.pi * (x - 110) / lam)
        q = round((v + 1) / 2 * (levels - 1)) / (levels - 1) * 2 - 1
        y = base - amp * q
        delay = 2.55 + i * 0.065
        stems.append(
            f'<g class="s" style="animation-delay:{delay:.2f}s">'
            f'<line x1="{x}" y1="{base}" x2="{x}" y2="{n(y)}"/>'
            f'<circle cx="{x}" cy="{n(y)}" r="2.8"/></g>')

    # Inference stage: a small fully-connected network
    layers = [(930, 4), (1005, 5), (1080, 3), (1148, 1)]
    nodes = []
    for lx, count in layers:
        ys = [base + (k - (count - 1) / 2) * 22 for k in range(count)]
        nodes.append([(lx, y) for y in ys])
    edges = []
    for a, b in zip(nodes, nodes[1:]):
        for (x1, y1) in a:
            for (x2, y2) in b:
                edges.append(f'<line x1="{x1}" y1="{n(y1)}" x2="{x2}" y2="{n(y2)}"/>')
    node_svg = []
    for li, layer in enumerate(nodes[:-1]):
        for (x, y) in layer:
            node_svg.append(
                f'<circle class="nd" style="animation-delay:{4.2 + li * 0.35:.2f}s" '
                f'cx="{x}" cy="{n(y)}" r="5"/>')
    ox, oy = nodes[-1][0]

    antenna_arcs = []
    for k, r in enumerate((11, 19, 27)):
        a0, a1 = math.radians(-50), math.radians(50)
        x0, y0 = 72 + r * math.cos(a0), 296 + r * math.sin(a0)
        x1, y1 = 72 + r * math.cos(a1), 296 + r * math.sin(a1)
        antenna_arcs.append(
            f'<path class="arc" style="animation-delay:{k * 0.18:.2f}s" '
            f'd="M{n(x0)} {n(y0)} A{r} {r} 0 0 1 {n(x1)} {n(y1)}"/>')

    channels = []
    cx = 48
    for label, name, col in (("CH1", "signal", SIGNAL), ("CH2", "system", SYSTEM),
                             ("CH3", "intelligence", INTEL)):
        channels.append(f'<circle cx="{cx + 4}" cy="37" r="4" fill="{col}"/>')
        channels.append(text(MM, label, 13, cx + 16, 42, col))
        w1 = MM.width(label, 13)
        channels.append(text(M, name, 13, cx + 16 + w1 + 8, 42, MUTED))
        cx += 16 + w1 + 8 + M.width(name, 13) + 34

    css = f"""
.sweep{{fill:none;stroke:{SIGNAL};stroke-width:3;stroke-linecap:round;
  stroke-dasharray:90 2000;stroke-dashoffset:90;filter:url(#glow);
  animation:sweep 8s linear infinite}}
@keyframes sweep{{0%{{stroke-dashoffset:90}}30%{{stroke-dashoffset:-1000}}100%{{stroke-dashoffset:-1000}}}}
.arc{{fill:none;stroke:{SIGNAL};stroke-width:2;stroke-linecap:round;opacity:.55;
  animation:rx 8s ease-out infinite}}
@keyframes rx{{0%{{opacity:.25}}3%{{opacity:1}}12%{{opacity:.55}}100%{{opacity:.55}}}}
.adc{{animation:adc 8s linear infinite;animation-delay:2.4s}}
@keyframes adc{{0%{{stroke-opacity:1;fill-opacity:.35}}6%{{stroke-opacity:.7;fill-opacity:0}}100%{{stroke-opacity:.7;fill-opacity:0}}}}
.s{{stroke:{SYSTEM};fill:{SYSTEM};stroke-width:1.8;opacity:.6;animation:lit 8s linear infinite}}
@keyframes lit{{0%{{opacity:.6}}2%{{opacity:1}}12%{{opacity:.6}}100%{{opacity:.6}}}}
.nd{{fill:{INK};stroke:{INTEL};stroke-width:1.6;animation:nd 8s ease-out infinite}}
@keyframes nd{{0%{{fill:{INK}}}3%{{fill:{INTEL}}}14%{{fill:{INK}}}100%{{fill:{INK}}}}}
.ping{{fill:none;stroke:{INTEL};stroke-width:1.5;opacity:0;transform-box:fill-box;
  transform-origin:center;animation:ping 8s ease-out infinite;animation-delay:5.3s}}
@keyframes ping{{0%{{opacity:.9;transform:scale(1)}}14%{{opacity:0;transform:scale(3.2)}}100%{{opacity:0;transform:scale(3.2)}}}}
{REDUCED}"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">Anto Roshan — from antenna to inference</title>
<desc id="d">Oscilloscope-style banner. A radio wave is received by an antenna, sampled and quantised by an ADC, and passed into a small neural network.</desc>
<defs>
<filter id="glow" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="panel"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16"/></clipPath>
</defs>
<style>{css}</style>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="{INK}" stroke="{LINE}"/>
<g clip-path="url(#panel)">{graticule(W, H, 10, 8)}</g>
{''.join(channels)}
{text(M, "github.com/AntoRoshanm", 13, W - 48, 42, MUTED, anchor="end")}
{text(D, "ANTO ROSHAN", 62, 46, 152, TEXT, tracking=5)}
{text(M, "from antenna to inference", 22, 48, 196, MUTED)}
<g>
  <line x1="72" y1="296" x2="72" y2="{base + 26}" stroke="{SIGNAL}" stroke-width="2"/>
  <path d="M62 {base + 26} H82" stroke="{SIGNAL}" stroke-width="2"/>
  {''.join(antenna_arcs)}
</g>
<path d="{sine}" fill="none" stroke="{SIGNAL}" stroke-width="1.8" opacity=".55"/>
<path class="sweep" pathLength="1000" d="{sine}"/>
<rect class="adc" x="514" y="{base - 16}" width="50" height="32" rx="4" fill="{SYSTEM}" fill-opacity="0" stroke="{SYSTEM}" stroke-opacity=".7"/>
{text(MM, "ADC", 12, 539, base + 4.5, SYSTEM, anchor="middle")}
<line x1="500" y1="{base}" x2="514" y2="{base}" stroke="{LINE}" stroke-width="1.5"/>
<line x1="564" y1="{base}" x2="578" y2="{base}" stroke="{LINE}" stroke-width="1.5"/>
<line x1="578" y1="{base}" x2="866" y2="{base}" stroke="{LINE}" stroke-width="1"/>
{''.join(stems)}
<line x1="872" y1="{base}" x2="918" y2="{base}" stroke="{LINE}" stroke-width="1.5" stroke-dasharray="3 4"/>
<g stroke="{LINE}" stroke-width="1" opacity=".9">{''.join(edges)}</g>
{''.join(node_svg)}
<circle class="ping" cx="{ox}" cy="{n(oy)}" r="7"/>
<circle cx="{ox}" cy="{n(oy)}" r="7" fill="{INTEL}"/>
{text(M, "sense", 13, 110, 392, MUTED)}
{text(M, "sample", 13, 584, 392, MUTED)}
{text(M, "infer", 13, 930, 392, MUTED)}
</svg>"""
    write("hero.svg", svg)


# ── Divider ──────────────────────────────────────────────────────────────────
def divider():
    W, H, c = 1200, 24, 12
    blip = []
    for x in range(570, 631):
        env = math.sin(math.pi * (x - 570) / 60)
        blip.append(f"{x} {n(c - 7 * env * math.sin(2 * math.pi * (x - 570) / 20))}")
    d = f"M0 {c} H570 L" + " L".join(blip) + f" H{W}"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="section divider">
<defs><linearGradient id="g" x1="0" x2="{W}" gradientUnits="userSpaceOnUse">
<stop offset="0" stop-color="{SIGNAL}" stop-opacity="0"/><stop offset=".3" stop-color="{SIGNAL}" stop-opacity=".6"/>
<stop offset=".5" stop-color="{SYSTEM}" stop-opacity=".9"/><stop offset=".7" stop-color="{INTEL}" stop-opacity=".6"/>
<stop offset="1" stop-color="{INTEL}" stop-opacity="0"/></linearGradient></defs>
<path d="{d}" fill="none" stroke="url(#g)" stroke-width="1.6" stroke-linejoin="round"/>
</svg>"""
    write("divider.svg", svg)


# ── Layer chips ──────────────────────────────────────────────────────────────
def chip(name, col):
    size, h = 13, 26
    w = int(M.width(name, size) + 38)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{name} layer">
<rect x=".75" y=".75" width="{w - 1.5}" height="{h - 1.5}" rx="{(h - 1.5) / 2}" fill="{INK}" stroke="{col}" stroke-opacity=".75" stroke-width="1.2"/>
<circle cx="14" cy="{h / 2}" r="3.5" fill="{col}"/>
{text(M, name, size, 25, 17.5, col)}
</svg>"""
    write(f"layer-{name}.svg", svg)


# ── Contact buttons ──────────────────────────────────────────────────────────
def button(slug, label, value, col):
    h = 40
    lw = M.width(label, 12)
    w = int(20 + 10 + lw + 12 + MM.width(value, 14) + 18)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{label}: {value}">
<rect x=".75" y=".75" width="{w - 1.5}" height="{h - 1.5}" rx="8" fill="{INK}" stroke="{LINE}" stroke-width="1.5"/>
<circle cx="18" cy="{h / 2}" r="3.5" fill="{col}"/>
{text(M, label, 12, 30, 24.5, MUTED)}
{text(MM, value, 14, 30 + lw + 12, 25, TEXT)}
</svg>"""
    write(f"link-{slug}.svg", svg)


# ── Sign-off ─────────────────────────────────────────────────────────────────
def signoff():
    W, H, c = 1200, 170, 86
    pts = []
    for x in range(48, 721, 2):
        if 150 <= x <= 470:
            t = (x - 150) / 320
            y = c - 34 * math.exp(-4.2 * t) * math.sin(2 * math.pi * t * 9)
        else:
            y = c
        pts.append(f"{x} {n(y)}")
    trace = "M" + " L".join(pts)
    css = f""".dot{{fill:{SIGNAL};animation:b 3.2s ease-in-out infinite}}
@keyframes b{{0%,100%{{opacity:.25}}50%{{opacity:1}}}}{REDUCED}"""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
<title id="t">End of transmission. 73 de AR.</title>
<defs><clipPath id="p"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16"/></clipPath>
<linearGradient id="g" x1="48" x2="720" gradientUnits="userSpaceOnUse">
<stop offset="0" stop-color="{SIGNAL}"/><stop offset=".6" stop-color="{SYSTEM}"/><stop offset="1" stop-color="{INTEL}" stop-opacity=".4"/></linearGradient></defs>
<style>{css}</style>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="{INK}" stroke="{LINE}"/>
<g clip-path="url(#p)">{graticule(W, H, 10, 4)}</g>
<path d="{trace}" fill="none" stroke="url(#g)" stroke-width="2" stroke-linejoin="round"/>
{text(MM, "end of transmission", 20, 790, 80, TEXT)}
<circle class="dot" cx="796" cy="106" r="4.5"/>
{text(M, "73 de AR", 15, 812, 111, SIGNAL)}
{text(M, "standing by", 15, 812 + M.width("73 de AR", 15) + 18, 111, MUTED)}
</svg>"""
    write("signoff.svg", svg)


if __name__ == "__main__":
    print("Building assets")
    hero()
    divider()
    chip("signal", SIGNAL)
    chip("system", SYSTEM)
    chip("intelligence", INTEL)
    button("email", "email", "anto2003roshan@gmail.com", SIGNAL)
    button("linkedin", "linkedin", "in/antoroshan2003", SYSTEM)
    button("github", "github", "AntoRoshanm", INTEL)
    signoff()
