# -*- coding: utf-8 -*-
"""Geometry analysis of image2.svg.

Part A: embedded hillshade PNG -- identify plot-area rectangle within it by a grid search
        over offsets (M rounded to whole px, and edge channel colours).
Part B: white polygon (LineCollection_1) -- geodesic area, bbox, orientation, vertex reduction.
"""
import re, json, math, os
import numpy as np
from PIL import Image
from matplotlib.path import Path as MplPath

AN = r'D:\claude\华为杯\D题\_work_docx\_analysis'
SVG = r'D:\claude\华为杯\D题\_work_docx\media\image2.svg'
s = open(SVG, encoding='utf-8').read()

# ---- georeference -------------------------------------------------------------
X0, Y0 = 109.03277777777778, 23.224722222222223     # top-left (ModelPixelScale/Tiepoint)
DX = DY = 0.00027777777777778
W, H = 1486, 1309
R = 6371000.0
lat_c = 23.0 + 52.0/60      # 23.86667 not needed; use full-extent mean


def m_per_deg_lat(lat):
    p = math.radians(lat)
    return 111132.92 - 559.82*math.cos(2*p) + 1.175*math.cos(4*p) - 0.0023*math.cos(6*p)


def m_per_deg_lon(lat):
    p = math.radians(lat)
    return 111412.84*math.cos(p) - 93.5*math.cos(3*p) + 0.118*math.cos(5*p)


LAT_N, LAT_S = Y0, Y0 - H*DY
LON_W, LON_E = X0, X0 + W*DX
lat_mid = 0.5*(LAT_N + LAT_S)
mx = m_per_deg_lon(lat_mid)
my = m_per_deg_lat(lat_mid)
ext_w_km = (LON_E-LON_W)*mx/1000
ext_h_km = (LAT_N-LAT_S)*my/1000
print('geo extent  lat %.6f..%.6f  lon %.6f..%.6f' % (LAT_S, LAT_N, LON_W, LON_E))
print('m/deg lon %.3f  m/deg lat %.3f' % (mx, my))
print('extent %.4f km (E-W) x %.4f km (N-S) = %.2f km2' % (ext_w_km, ext_h_km, ext_w_km*ext_h_km))
print('native pixel size ~30 m x 30 m -> nominal area 3600 m2')

# ---- A: locate plot rectangle inside embedded PNG -----------------------------
im = Image.open(os.path.join(AN, 'embedded_0.png'))
a = np.asarray(im).astype(np.int16)
print('embedded PNG', im.size, im.mode)
Hp, Wp = a.shape[:2]
mx_ = 672.55/1486.0
my_ = 637.56/1309.0
print('expected scale: %.6f (x), %.6f (y)' % (mx_, my_))
ob = 124.669
if True:
    print('offset (x0,y0) if M=(0,0):', -ob/mx_, (-71.28)/my_)

def score(x0f, y0f):
    x0 = round(x0f); y0 = round(y0f)
    if x0 < 0 or y0 < 0 or x0+W > Wp or y0+H > Hp:
        return None
    sub = a[y0:y0+H, x0:x0+W]
    res = 0
    for ch, outer, inner in ((0, 6, 43), (1, 6, 43), (2, 4, 60)):
        c = sub[:, :, ch]
        res += int((c == outer).sum()) + int((c == inner).sum())
    return res

best = None
for x0f in np.arange(0, 25, 1.0):
    for y0f in np.arange(0, 25, 1.0):
        sc = score(x0f, y0f)
        if sc and (best is None or sc > best[0]):
            best = (sc, x0f, y0f)
print('coarse best (score, x0, y0):', best)

if best:
    sc, bx, by = best
    sub = a[round(by):round(by)+H, round(bx):round(bx)+W]
    print('plot-box sub-pixel grid origin: x0=%.3f, y0=%.3f' % (-ob/mx_, -71.28/my_))
    print(' -> scan row sums of exact colour 6/43 on y-borders')
    for ch in (0, 1, 2):
        for nm, val in (('outer', (6, 6, 4)[ch]), ('inner', (43, 43, 60)[ch])):
            cnt = (sub[:, :, ch] == val).sum(axis=1)
            k = np.argsort(cnt)[-3:]
            print('   ch%d %s val=%d  row hits %s' % (ch, nm, val, sorted(cnt[k])[::-1]))

# exact border colours: sample the first/last rows/cols of the found box
if best:
    _, bx, by = best
    bx, by = round(bx), round(by)
    sub = a[by:by+H, bx:bx+W]
    print('box top row unique (r,g,b) first 5:', [tuple(x) for x in sub[0, :5]])
    print('box left col unique first 5:', [tuple(x) for x in sub[:5, 0]])

# ---- B: polygon vertices -------------------------------------------------------
d = open(os.path.join(AN, 'poly_white_d.txt')).read()
toks = re.findall(r'[MLZmlz]|-?\d*\.?\d+', d)
pts, cur, cmd, i = [], [], None, 0
while i < len(toks):
    t = toks[i]
    if t in 'MLZmlz':
        cmd = t; i += 1
        if t == 'M':
            if cur: pts.append(cur)
            cur = []
        continue
    x, y = float(toks[i]), float(toks[i+1]); i += 2
    cur.append((x, y))
if cur: pts.append(cur)
P = np.array(pts[0], dtype=float)
P = P[:-1] if np.allclose(P[0], P[-1]) else P
print('\nraw polygon vertices:', len(P))
print('bbox px: x %.3f..%.3f  y %.3f..%.3f' % (P[:, 0].min(), P[:, 0].max(), P[:, 1].min(), P[:, 1].max()))

A_ax, B_ax, C_ax, D_ax = 124.669, 797.219, 708.84, 71.28
sx = W/(B_ax-A_ax)
sy = H/(C_ax-D_ax)
def px2geo(p):
    lon = LON_W + (p[:, 0]-A_ax)/ (B_ax-A_ax) * (LON_E-LON_W)
    lat = LAT_N - (p[:, 1]-D_ax)/ (C_ax-D_ax) * (LAT_N-LAT_S)
    return lon, lat

lon, lat = px2geo(P)
print('polygon lon %.6f..%.6f  lat %.6f..%.6f' % (lon.min(), lon.max(), lat.min(), lat.max()))

# geodesic area (Shoelace on local equal-area projected coords)
lat0 = lat.mean()
X = (lon - lon.mean())*m_per_deg_lon(lat0)
Y = (lat - lat.mean())*m_per_deg_lat(lat0)
area_m2 = 0.5*abs(np.dot(X, np.roll(Y, -1)) - np.dot(Y, np.roll(X, -1)))
print('polygon geodesic area = %.4f km2  (%.2f %% of %.2f km2 extent)'
      % (area_m2/1e6, 100*area_m2/1e6/(ext_w_km*ext_h_km), ext_w_km*ext_h_km))
print('bbox area = %.4f km2 (%.2f %%)'
      % (((lon.max()-lon.min())*m_per_deg_lon(lat0)/1e3)*((lat.max()-lat.min())*m_per_deg_lat(lat0)/1e3),
         100*(((lon.max()-lon.min())*m_per_deg_lon(lat0)/1e3)*((lat.max()-lat.min())*m_per_deg_lat(lat0)/1e3))/(ext_w_km*ext_h_km)))
print('fill ratio of polygon vs its bbox = %.3f' % (area_m2/1e6 / (((lon.max()-lon.min())*m_per_deg_lon(lat0)/1e3)*((lat.max()-lat.min())*m_per_deg_lat(lat0)/1e3))))

# pixel-space area (for cross-check of scale)
xs, ys = P[:, 0], -P[:, 1]
apx = 0.5*abs(np.dot(xs, np.roll(ys, -1)) - np.dot(ys, np.roll(xs, -1)))
print('polygon pixel area = %.1f px2 = %.2f %% of axes rect (672.55x637.56=%.0f px2)'
      % (apx, 100*apx/(672.55*637.56), 672.55*637.56))
print('implied px2->m2 factor %.3f (geo) vs %.3f (pixel)' % (area_m2/apx, (ext_w_km*1e3*ext_h_km*1e3)/(672.55*637.56)))

# ---- orientation / aspect ------------------------------------------------------
def pca_shape(pts_xy):
    c = pts_xy.mean(axis=0)
    q = pts_xy - c
    cov = q.T @ q / len(q)
    w, v = np.linalg.eigh(cov)
    order = np.argsort(w)[::-1]
    w, v = w[order], v[:, order]
    return c, np.sqrt(w), v

c, sd, v = pca_shape(np.column_stack([X, Y])/1000)
print('\nPCA st.dev (km): %.3f, %.3f  ratio %.2f' % (sd[0], sd[1], sd[0]/sd[1]))
ang = math.degrees(math.atan2(v[0, 0], v[1, 0]))
print('major axis bearing (deg from north, CW): %.1f' % ((90 - ang) % 180))
print('equivalent-circle diameter %.2f km' % (2*math.sqrt(area_m2/math.pi)/1000))

# oriented bbox (km) by rotating to principal axes
th = math.atan2(v[1, 0], v[0, 0])
Rot = np.array([[math.cos(-th), -math.sin(-th)], [math.sin(-th), math.cos(-th)]])
Q = (np.column_stack([X, Y])/1000) @ Rot.T
q0, q1 = float(np.ptp(Q[:, 0])), float(np.ptp(Q[:, 1]))
print('oriented bbox: %.2f km x %.2f km  (aspect %.2f:1), fill %.3f'
      % (q0, q1, q0/q1, area_m2/1e6/(q0*q1)))

# ---- straight-segment count (Douglas-Peucker) ----------------------------------
def rdp_idx(pts, eps):
    keep = np.zeros(len(pts), bool); keep[0] = keep[-1] = True
    stack = [(0, len(pts)-1)]
    while stack:
        i, j = stack.pop()
        if j <= i+1:
            continue
        p, q = pts[i], pts[j]
        seg = q - p
        L = np.hypot(*seg)
        if L == 0:
            d = np.hypot(*(pts[i+1:j]-p).T)
        else:
            cross = np.abs(seg[0]*(pts[i+1:j, 1]-p[1]) - seg[1]*(pts[i+1:j, 0]-p[0]))
            d = cross/L
        k = int(np.argmax(d))
        if d[k] > eps:
            m = i+1+k
            keep[m] = True
            stack.append((i, m)); stack.append((m, j))
    return keep

Pg = np.column_stack([X, Y])   # metres
for eps_m in (5, 10, 20, 30, 45, 60, 100, 150, 200, 300):
    keep = rdp_idx(Pg, eps_m)
    n = int(keep.sum())
    # count segments longer than 1 km in reduced ring
    kp = Pg[keep]
    seg = np.hypot(*(np.roll(kp, -1, axis=0) - kp).T)
    print('RDP eps=%4d m -> %3d vertices ; segments >%.0fm: %d ; median seg %.0f m ; max seg %.0f m'
          % (eps_m, n, max(300, eps_m), int((seg > max(300, eps_m)).sum()), np.median(seg), seg.max()))

# convex hull / hull ratio
from scipy.spatial import ConvexHull
ch = ConvexHull(Pg)
print('convex hull area %.2f km2 ; area/hull = %.3f' % (ch.volume/1e6, area_m2/1e6/(ch.volume/1e6)))
print('perimeter %.1f km ; compactness 4piA/P^2 = %.3f'
      % (np.hypot(*(np.roll(Pg, -1, axis=0)-Pg).T).sum()/1000,
         4*math.pi*area_m2/(np.hypot(*(np.roll(Pg, -1, axis=0)-Pg).T).sum()**2)))

json.dump({'lon': lon.tolist(), 'lat': lat.tolist()}, open(os.path.join(AN, 'poly_geo.json'), 'w'))
