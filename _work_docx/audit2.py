import numpy as np, scipy.io as sio, pandas as pd, math

root = r"D:\claude\华为杯\D题\数据"
base = root + r"\镇龙乡地理空间数据\镇龙乡及周边地理数据"
d = sio.loadmat(base + r"\数字高程模型数据（DEM）\镇龙乡及周边30米DEM.mat")
dem = d["dem"]; lat = d["latitude"].ravel(); lon = d["longitude"].ravel(); nod = float(d["nodata"][0, 0])
print("DEM lon %.6f..%.6f  lat %.6f..%.6f  shape %s" % (lon.min(), lon.max(), lat.min(), lat.max(), str(dem.shape)))
print("lat step %.8f  lon step %.8f  nodata %.0f  nodata cells %d" % (lat[1]-lat[0], lon[1]-lon[0], nod, int((dem == nod).sum())))

raw = pd.read_excel(root + r"\无人机应急物资运输基础数据\调度中心与服务区.xlsx", sheet_name="数据", header=None)
rows = []
for _, r in raw.iterrows():
    a = r[0]
    if isinstance(a, str) and (a == "O01" or (len(a) == 4 and a[0] == "S" and a[1:].isdigit())):
        rows.append((a, r[1], float(r[2]), float(r[3]), float(r[4]), r[5]))
df = pd.DataFrame(rows, columns=["id", "name", "lon", "lat", "elev", "pop"])
print("parsed nodes:", df.shape, list(df["id"]))
center = df.iloc[0]
serv = df.iloc[1:].reset_index(drop=True)

def sample(lo, la):
    la_idx = int(np.argmin(np.abs(lat - la))); lo_idx = int(np.argmin(np.abs(lon - lo)))
    return float(dem[la_idx, lo_idx]), la_idx, lo_idx, float(lat[la_idx]), float(lon[lo_idx])

print("\n--- 调度中心 + 服务区 DEM 高程比对 ---")
allnodes = pd.DataFrame([center] + [r for _, r in serv.iterrows()])
for _, r in allnodes.iterrows():
    lo, la = float(r["lon"]), float(r["lat"])
    dv, _, _, glat, glon = sample(lo, la)
    inside = (lat.min() <= la <= lat.max()) and (lon.min() <= lo <= lon.max())
    print("%-5s %-18s lon=%.6f lat=%.6f | xls=%7.1f dem=%7.1f diff=%+7.1f | pop=%s inside=%s%s" % (
        r["id"], str(r["name"])[:18], lo, la, float(r["elev"]), dv, dv - float(r["elev"]),
        str(r["pop"]), inside,
        "" if abs(dv - float(r["elev"])) <= 1.0 else "   <== 高程不一致"))

print("\n--- 服务区到 O01 水平距离 ---")
o = (float(center["lon"]), float(center["lat"]))
dists = []
for _, r in serv.iterrows():
    dlat = (float(r["lat"]) - o[1]) * 111.32
    dlon = (float(r["lon"]) - o[0]) * 111.32 * math.cos(math.radians(o[1]))
    km = math.hypot(dlat, dlon)
    dists.append((r["id"], str(r["name"]), float(r["elev"]), km, int(r["pop"])))
for t in sorted(dists, key=lambda x: x[3]):
    print("  %-5s %-18s elev=%7.1f  dist=%6.3f km  pop=%5d" % t)
print("  最远 %.3f km (%s)  最近 %.3f km (%s)" % (max(dists, key=lambda x: x[3])[3], max(dists, key=lambda x: x[3])[0],
                                              min(dists, key=lambda x: x[3])[3], min(dists, key=lambda x: x[3])[0]))
print("  人口合计 %d" % sum(t[4] for t in dists))

print("\n--- DEM 高程相对节点海拔的偏差直方图（所有 O01/Si 附近 3x3 像元）---")
for _, r in allnodes.iterrows():
    lo, la = float(r["lon"]), float(r["lat"])
    li = int(np.argmin(np.abs(lat - la))); lj = int(np.argmin(np.abs(lon - lo)))
    win = dem[max(0,li-1):li+2, max(0,lj-1):lj+2]
    print("%-5s xls=%7.1f  dem_center=%7.1f  dem_win=[%s]" % (r["id"], float(r["elev"]), float(dem[li,lj]), ", ".join("%.1f" % v for v in win.ravel())))

print("\n--- 服务区两两最近邻 ---")
pts = [(r["id"], float(r["lon"]), float(r["lat"])) for _, r in serv.iterrows()]
out = []
for i in range(len(pts)):
    best = None
    for j in range(len(pts)):
        if i == j: continue
        dlat = (pts[i][2] - pts[j][2]) * 111.32
        dlon = (pts[i][1] - pts[j][1]) * 111.32 * math.cos(math.radians(pts[i][2]))
        dd = math.hypot(dlat, dlon)
        if best is None or dd < best[1]: best = (pts[j][0], dd)
    out.append((pts[i][0], best[0], best[1]))
for t in sorted(out, key=lambda x: x[2])[:6]:
    print("  %s <-> %s : %.3f km" % t)

print("\n--- 同名服务区检查 ---")
print(serv.groupby("name")["id"].apply(list).to_string())
