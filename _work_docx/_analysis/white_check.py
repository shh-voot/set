# -*- coding: utf-8 -*-
"""Does the embedded PNG itself contain a white polygon overlay? Find plot rect inside it."""
import os, re
import numpy as np
from PIL import Image

AN = r'D:\claude\华为杯\D题\_work_docx\_analysis'
im = Image.open(os.path.join(AN, 'embedded_0.png')).convert('RGB')
a = np.asarray(im).astype(np.int16)
Hp, Wp = a.shape[:2]
print('png', Wp, Hp)

# how white is the brightest pixel in each row/col? (the stroke is pure white)
mx = a.max(axis=2)
whiteish = (mx > 240)
print('pixels with max channel >240: %d (%.4f%%)' % (whiteish.sum(), 100*whiteish.mean()))
ys, xs = np.nonzero(whiteish)
if len(xs):
    print('their bbox: x %d..%d  y %d..%d' % (xs.min(), xs.max(), ys.min(), ys.max()))
    print('row histogram top:', np.bincount(ys, minlength=Hp).argsort()[-8:][::-1])
    print('col histogram top:', np.bincount(xs, minlength=Wp).argsort()[-8:][::-1])

# Look specifically for the pixel VALUES that were sampled as border 6/43 in the
# original hypothesis: show the unique colours near the frame of the actual image.
for edge, arr in (('row0', a[0]), ('row_last', a[-1]), ('col0', a[:, 0]), ('col_last', a[:, -1])):
    u, c = np.unique(arr.reshape(-1, 3), axis=0, return_counts=True)
    o = np.argsort(c)[::-1][:4]
    print(edge, [(tuple(u[i]), int(c[i])) for i in o])
