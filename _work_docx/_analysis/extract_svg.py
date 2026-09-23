# -*- coding: utf-8 -*-
"""Extract vector geometry (polygon outline, embedded raster, labels) from image2.svg."""
import re, json, base64, os

SVG = r'D:\claude\华为杯\D题\_work_docx\media\image2.svg'
OUT = r'D:\claude\华为杯\D题\_work_docx\_analysis'
os.makedirs(OUT, exist_ok=True)

s = open(SVG, encoding='utf-8').read()
print('svg chars', len(s))

def group_block(gid):
    a = s.find('<g id="%s"' % gid)
    if a < 0:
        return None
    b = s.find('</g>', a)
    return s[a:b]

# ---- vector paths of interest -------------------------------------------------
lc1 = group_block('LineCollection_1')
m = re.search(r'\sd="([^"]+)"', lc1)
d1 = m.group(1)
lc2 = group_block('LineCollection_2')
d2 = re.search(r'\sd="([^"]+)"', lc2).group(1)
open(os.path.join(OUT, 'poly_white_d.txt'), 'w').write(d1)
open(os.path.join(OUT, 'poly_dark_d.txt'), 'w').write(d2)
print('LC1 d len', len(d1), 'LC2 d len', len(d2), 'identical:', d1 == d2)
print('LC1 attrs:', re.findall(r'(stroke|stroke-width|fill)="[^"]*"', lc1))
print('LC2 attrs:', re.findall(r'(stroke|stroke-width|fill)="[^"]*"', lc2))

def parse_path(d):
    """Return list of subpaths, each a list of (x,y) with command letters."""
    toks = re.findall(r'[MLZmlz]|-?\d*\.?\d+(?:e-?\d+)?', d)
    subs, cur, cmd = [], [], None
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in 'MLZmlz':
            cmd = t
            i += 1
            if cmd in 'Zz':
                if cur:
                    subs.append(cur)
                cur = []
            continue
        x = float(toks[i]); y = float(toks[i + 1]); i += 2
        if cmd in 'ml':
            if cur:
                subs.append(cur)
            cur = [(x, y)]
        else:
            cur.append((x, y))
    if cur:
        subs.append(cur)
    return subs

subs1 = parse_path(d1)
subs2 = parse_path(d2)
print('LC1 subpaths:', [(len(sp), sp[0], sp[-1]) for sp in subs1])
print('LC2 subpaths:', [(len(sp), sp[0], sp[-1]) for sp in subs2])
json.dump({'subs_white': subs1, 'subs_dark': subs2}, open(os.path.join(OUT, 'polys.json'), 'w'))

# ---- embedded raster(s) -------------------------------------------------------
imgs = re.findall(r'<image[^>]*>', s)
print('num <image> elements:', len(imgs))
for k, tag in enumerate(imgs):
    attrs = dict(re.findall(r'(\w[\w:-]*)="([^"]*)"', tag))
    href = attrs.get('xlink:href', '')
    head = href[:30]
    print(k, 'x=', attrs.get('x'), 'y=', attrs.get('y'), 'w=', attrs.get('width'),
          'h=', attrs.get('height'), 'transform=', attrs.get('transform'), 'id=', attrs.get('id'))
    if href.startswith('data:image/png;base64,'):
        raw = base64.b64decode(href[len('data:image/png;base64,'):])
        fn = os.path.join(OUT, 'embedded_%d.png' % k)
        open(fn, 'wb').write(raw)
        print('   decoded', len(raw), 'bytes ->', fn)
        # PNG header
        import struct
        w, h = struct.unpack('>II', raw[16:24])
        bitd, ct = raw[24], raw[25]
        print('   PNG', w, 'x', h, 'bitdepth', bitd, 'colortype', ct)

# ---- text labels --------------------------------------------------------------
uses = re.findall(r'<use[^>]*xlink:href="#([^"]+)"[^>]*>', s)
print('num <use> glyphs:', len(uses))
texts = re.findall(r'<g id="text_\d+"[^>]*>(.*?)</g>', s, re.S)
print('num text groups:', len(texts))
def glyph_names(t):
    return re.findall(r'xlink:href="#([^"]+)"', t)
for k, t in enumerate(texts):
    g = glyph_names(t)
    tr = re.findall(r'transform="matrix\(([^)]*)\)"', t)
    print('text_%d:' % (k + 1), len(g), g[:12], 'transforms', tr[:4])
