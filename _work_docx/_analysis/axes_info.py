# -*- coding: utf-8 -*-
"""Extract exact tick/gridline/spine geometry from the SVG, and inspect the embedded PNG."""
import re, os
import numpy as np
from PIL import Image

SVG = r'D:\claude\华为杯\D题\_work_docx\media\image2.svg'
AN = r'D:\claude\华为杯\D题\_work_docx\_analysis'
s = open(SVG, encoding='utf-8').read()

def blk(gid):
    a = s.find('<g id="%s"' % gid)
    b = s.find('</g>', a)
    return s[a:b]

for gid in ['matplotlib.axis_1', 'matplotlib.axis_2']:
    a = s.find('<g id="%s"' % gid)
    b = s.find('<g id="', a + 10)
    print('#' * 20, gid)
    print(s[a:b][:2500])

print('#' * 20, 'gridline-ish line2d_17/18')
for gid in ['line2d_17', 'line2d_18', 'line2d_11', 'line2d_12', 'line2d_1']:
    print(gid, ':', blk(gid)[:400])
    print()

print('#' * 20, 'legend + patches + scatter')
for gid in ['legend_1', 'PathCollection_1', 'PathCollection_2', 'text_12', 'text_13', 'text_14', 'text_15', 'text_16']:
    print(gid, ':', blk(gid)[:600].replace('\n', ' '))
    print()

print('#' * 20, 'embed PNG stats')
im = Image.open(os.path.join(AN, 'embedded_0.png'))
a = np.asarray(im)
print('shape', a.shape, 'alpha uniq', np.unique(a[..., 3])[:10], np.unique(a[..., 3]).size)
rgb = a[..., :3].astype(int)
gray_like = (rgb[..., 0] == rgb[..., 1]) & (rgb[..., 1] == rgb[..., 2])
print('fraction R=G=B:', gray_like.mean())
print('corner colours TL,TR,BL,BR:', a[0, 0], a[0, -1], a[-1, 0], a[-1, -1])
print('mean rgb', rgb.reshape(-1, 3).mean(axis=0))
print('uniq colours (approx):', len(np.unique(rgb.reshape(-1, 3), axis=0)))
# alpha==255 everywhere?
print('alpha==255 fraction', (a[..., 3] == 255).mean())
# is there a visible border? check first/last rows/cols
print('row0 mean', rgb[0].mean(axis=0), 'row1 mean', rgb[1].mean(axis=0), 'row-1 mean', rgb[-1].mean(axis=0))
print('col0 mean', rgb[:, 0].mean(axis=0), 'col-1 mean', rgb[:, -1].mean(axis=0))
