# -*- coding: utf-8 -*-
"""Draw the extracted polygon over the embedded hillshade to verify registration."""
import re, os
import numpy as np
from PIL import Image, ImageDraw

AN = r'D:\claude\华为杯\D题\_work_docx\_analysis'
d = open(os.path.join(AN, 'poly_white_d.txt')).read()
pts = [(float(x), float(y)) for x, y in re.findall(r'(-?\d*\.?\d+) (-?\d*\.?\d+)', d)]
print('vertices', len(pts))

# axes-rect -> embedded-png coordinates (both cover the same map extent, same aspect)
A_ax, C_ax, B_ax, D_ax = 124.669, 672.55, 797.219, 637.56
pim = Image.open(os.path.join(AN, 'embedded_0.png')).convert('RGB')
Wp, Hp = pim.size
sc = (Wp/B_ax, Hp/D_ax)
pp = [(A_ax + (x-A_ax)*sc[0], (y-71.28)*sc[1]+ (0)) for x, y in pts]
# top of axes (y=71.28) maps to png y=0
pp = [((x-A_ax)*sc[0], (y-71.28)*sc[1]) for x, y in pts]
print('png bbox of polygon: x %.1f..%.1f  y %.1f..%.1f  (png %dx%d)'
      % (min(p[0] for p in pp), max(p[0] for p in pp),
         min(p[1] for p in pp), max(p[1] for p in pp), Wp, Hp))

for name, col, wd in (('chk_magenta', (255, 0, 255), 2), ('chk_white', (255, 255, 255), 2)):
    im = pim.copy()
    ImageDraw.Draw(im).line(pp + [pp[0]], fill=col, width=wd, joint='curve')
    im.save(os.path.join(AN, name + '.png'))
print('wrote chk_magenta.png / chk_white.png')

# also dump a half-size version for quick viewing
Image.open(os.path.join(AN, 'chk_magenta.png')).resize((Wp//2, Hp//2)).save(os.path.join(AN, 'chk_magenta_half.png'))

# and a version where the polygon is FILLED translucent, to visualise coverage
im = pim.copy().convert('RGBA')
ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
ImageDraw.Draw(ov).polygon(pp, fill=(255, 0, 255, 90))
Image.alpha_composite(im, ov).convert('RGB').resize((Wp//2, Hp//2)).save(os.path.join(AN, 'chk_fill_half.png'))
print('wrote chk_fill_half.png')
