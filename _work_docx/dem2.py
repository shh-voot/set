import numpy as np, scipy.io as sio
p = r"D:\claude\华为杯\D题\数据\镇龙乡地理空间数据\镇龙乡及周边地理数据\数字高程模型数据（DEM）\镇龙乡及周边30米DEM.mat"
d = sio.loadmat(p)
dem = d["dem"]; lat = d["latitude"].ravel(); lon = d["longitude"].ravel()
print("DEM shape", dem.shape, "dtype", dem.dtype)
print("lat: first", lat[0], "last", lat[-1], "n", len(lat), "step", lat[1]-lat[0])
print("lon: first", lon[0], "last", lon[-1], "n", len(lon), "step", lon[1]-lon[0])
print("nodata", float(d["nodata"][0,0]), "epsg", int(d["epsg_code"][0,0]))
print("transform", d["transform"].ravel())
valid = dem[dem != float(d["nodata"][0,0])]
print("valid cells", valid.size, "min", float(valid.min()), "max", float(valid.max()), "mean", float(valid.mean()))
# nan count
print("nan in dem:", int(np.isnan(dem).sum()))
# sample around O01
o = (109.2308517, 23.0085095)
ilat = int(np.argmin(np.abs(lat - o[1]))); ilon = int(np.argmin(np.abs(lon - o[0])))
print("O01 nearest idx", ilat, ilon, "elev", float(dem[ilat, ilon]), "lat", lat[ilat], "lon", lon[ilon])
# also check geotiff availability
try:
    from osgeo import gdal
    print("gdal ok")
except Exception as e:
    print("gdal no:", e)
