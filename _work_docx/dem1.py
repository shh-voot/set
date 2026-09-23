import numpy as np, scipy.io as sio, os
p = r"D:\claude\华为杯\D题\数据\镇龙乡地理空间数据\镇龙乡及周边地理数据\数字高程模型数据（DEM）\镇龙乡及周边30米DEM.mat"
d = sio.loadmat(p)
keys = [k for k in d.keys() if not k.startswith("__")]
print("keys:", keys)
for k in keys:
    v = d[k]
    print(k, type(v), getattr(v, "shape", None), getattr(v, "dtype", None), "ndim", getattr(v,"ndim",None))
    if v.dtype.names:
        print("  fields:", v.dtype.names)
