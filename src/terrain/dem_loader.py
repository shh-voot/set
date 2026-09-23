#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEM数据加载模块
支持GeoTIFF和MAT格式的数字高程模型数据
"""

import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class DEMLoader:
    """DEM数据加载器"""

    def __init__(self, dem_file: str):
        """
        初始化DEM加载器

        Args:
            dem_file: DEM文件路径（支持.tif或.mat格式）
        """
        self.dem_file = Path(dem_file)
        self.dem_data = None
        self.dem_bounds = None
        self.resolution = None

    def load(self) -> Tuple[np.ndarray, Dict]:
        """
        加载DEM数据

        Returns:
            (dem_data, dem_bounds): 高程矩阵和边界信息
        """
        if not self.dem_file.exists():
            raise FileNotFoundError(f"DEM文件不存在: {self.dem_file}")

        print(f"正在加载DEM数据: {self.dem_file.name}")

        if self.dem_file.suffix.lower() == '.tif':
            return self._load_geotiff()
        elif self.dem_file.suffix.lower() == '.mat':
            return self._load_mat()
        else:
            raise ValueError(f"不支持的DEM格式: {self.dem_file.suffix}")

    def _load_geotiff(self) -> Tuple[np.ndarray, Dict]:
        """加载GeoTIFF格式的DEM"""
        try:
            import rasterio
        except ImportError:
            print("警告: rasterio未安装，尝试使用GDAL...")
            return self._load_geotiff_gdal()

        with rasterio.open(self.dem_file) as dataset:
            # 读取高程数据
            self.dem_data = dataset.read(1)

            # 获取地理变换参数
            transform = dataset.transform
            bounds = dataset.bounds

            self.dem_bounds = {
                'min_x': bounds.left,
                'max_x': bounds.right,
                'min_y': bounds.bottom,
                'max_y': bounds.top,
                'resolution': transform[0]  # 像元大小
            }

            self.resolution = transform[0]

            print(f"  DEM尺寸: {self.dem_data.shape}")
            print(f"  高程范围: {self.dem_data.min():.1f} - {self.dem_data.max():.1f} 米")
            print(f"  地理范围: ({bounds.left:.4f}, {bounds.bottom:.4f}) - "
                  f"({bounds.right:.4f}, {bounds.top:.4f})")
            print(f"  分辨率: {self.resolution:.1f} 米")

            return self.dem_data, self.dem_bounds

    def _load_geotiff_gdal(self) -> Tuple[np.ndarray, Dict]:
        """使用GDAL加载GeoTIFF"""
        try:
            from osgeo import gdal
        except ImportError:
            raise ImportError("需要安装rasterio或GDAL来读取GeoTIFF文件")

        dataset = gdal.Open(str(self.dem_file))
        if dataset is None:
            raise RuntimeError(f"无法打开DEM文件: {self.dem_file}")

        # 读取高程数据
        band = dataset.GetRasterBand(1)
        self.dem_data = band.ReadAsArray()

        # 获取地理变换参数
        geotransform = dataset.GetGeoTransform()
        x_min = geotransform[0]
        y_max = geotransform[3]
        pixel_width = geotransform[1]
        pixel_height = -geotransform[5]  # 通常是负值

        rows, cols = self.dem_data.shape
        x_max = x_min + cols * pixel_width
        y_min = y_max - rows * pixel_height

        self.dem_bounds = {
            'min_x': x_min,
            'max_x': x_max,
            'min_y': y_min,
            'max_y': y_max,
            'resolution': pixel_width
        }

        self.resolution = pixel_width

        print(f"  DEM尺寸: {self.dem_data.shape}")
        print(f"  高程范围: {self.dem_data.min():.1f} - {self.dem_data.max():.1f} 米")
        print(f"  分辨率: {self.resolution:.1f} 米")

        dataset = None  # 关闭文件

        return self.dem_data, self.dem_bounds

    def _load_mat(self) -> Tuple[np.ndarray, Dict]:
        """加载MATLAB .mat格式的DEM"""
        try:
            from scipy.io import loadmat
        except ImportError:
            raise ImportError("需要安装scipy来读取.mat文件")

        print("  加载MATLAB格式DEM...")
        mat_data = loadmat(self.dem_file)

        # 读取DEM数据
        self.dem_data = mat_data['dem']

        print(f"  DEM尺寸: {self.dem_data.shape}")
        print(f"  高程范围: {self.dem_data.min():.1f} - {self.dem_data.max():.1f} 米")

        # 读取经纬度范围
        longitude = mat_data['longitude'].flatten()
        latitude = mat_data['latitude'].flatten()

        # 从transform读取地理变换参数
        # transform = [pixel_width, 0, x_min, 0, -pixel_height, y_max]
        transform = mat_data['transform'].flatten()
        pixel_width = transform[0]
        x_min = transform[2]
        pixel_height = abs(transform[4])
        y_max = transform[5]

        rows, cols = self.dem_data.shape
        x_max = x_min + cols * pixel_width
        y_min = y_max - rows * pixel_height

        self.resolution = pixel_width
        self.dem_bounds = {
            'min_x': x_min,
            'max_x': x_max,
            'min_y': y_min,
            'max_y': y_max,
            'resolution': self.resolution
        }

        print(f"  地理范围: ({x_min:.4f}, {y_min:.4f}) - ({x_max:.4f}, {y_max:.4f})")
        print(f"  分辨率: {self.resolution:.6f} 度")

        return self.dem_data, self.dem_bounds

    def get_height(self, x: float, y: float) -> Optional[float]:
        """
        获取指定位置的高程（双线性插值）

        Args:
            x: 经度或X坐标
            y: 纬度或Y坐标

        Returns:
            高程值（米），超出范围返回None
        """
        if self.dem_data is None or self.dem_bounds is None:
            return None

        # 检查是否在范围内
        if (x < self.dem_bounds['min_x'] or x > self.dem_bounds['max_x'] or
            y < self.dem_bounds['min_y'] or y > self.dem_bounds['max_y']):
            return None

        # 计算矩阵索引
        resolution = self.dem_bounds['resolution']
        col = (x - self.dem_bounds['min_x']) / resolution
        row = (self.dem_bounds['max_y'] - y) / resolution

        # 边界检查
        if row < 0 or row >= self.dem_data.shape[0] - 1:
            return None
        if col < 0 or col >= self.dem_data.shape[1] - 1:
            return None

        # 双线性插值
        row_floor = int(np.floor(row))
        col_floor = int(np.floor(col))

        row_frac = row - row_floor
        col_frac = col - col_floor

        # 四个角点的高度
        h00 = self.dem_data[row_floor, col_floor]
        h01 = self.dem_data[row_floor, col_floor + 1]
        h10 = self.dem_data[row_floor + 1, col_floor]
        h11 = self.dem_data[row_floor + 1, col_floor + 1]

        # 插值
        h0 = h00 * (1 - col_frac) + h01 * col_frac
        h1 = h10 * (1 - col_frac) + h11 * col_frac
        height = h0 * (1 - row_frac) + h1 * row_frac

        return float(height)


def test_dem_loader():
    """测试DEM加载器"""
    print("="*80)
    print("测试DEM加载器")
    print("="*80)

    # 直接使用.mat文件（无需rasterio/GDAL）
    dem_file = "数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/数字高程模型数据（DEM）/镇龙乡及周边30米DEM.mat"

    if not Path(dem_file).exists():
        print(f"错误: 找不到DEM文件: {dem_file}")
        return

    loader = DEMLoader(dem_file)
    dem_data, dem_bounds = loader.load()

    print("\n测试高程查询:")
    # 测试几个点的高程
    test_points = [
        (109.230852, 23.008509),  # 调度中心附近
        (109.25, 23.02),
        (109.28, 23.04),
    ]

    for x, y in test_points:
        height = loader.get_height(x, y)
        if height is not None:
            print(f"  位置 ({x:.6f}, {y:.6f}): {height:.1f} 米")
        else:
            print(f"  位置 ({x:.6f}, {y:.6f}): 超出范围")

    print("\n" + "="*80)
    print("DEM加载器测试完成")
    print("="*80)


if __name__ == "__main__":
    test_dem_loader()
