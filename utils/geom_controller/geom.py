import os
import logging
from collections import defaultdict
from tqdm import tqdm

import pandas as pd
import xml.etree.ElementTree as ET

from shapely.geometry import LineString, Point, MultiLineString, GeometryCollection
from shapely.ops import unary_union, transform

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from pyproj import CRS, Transformer
from datetime import datetime

_transformer_cache = {}

def utm_epsg_for_lon(lon, lat):
    """คืน EPSG code ของ UTM zone ตาม lon, lat (Thailand อยู่ซีกเหนือ => 326xx)"""
    zone = int((lon + 180) / 6) + 1
    # ถ้าจุดอยู่ใต้เส้นศูนย์สูตร ใช้ 327xx แต่สำหรับไทย lat>0 เสมอ
    return 32600 + zone if lat >= 0 else 32700 + zone

def get_transformer_to_utm(epsg):
    """Cache transformer จาก EPSG:4326 -> EPSG:xxxx"""
    key = int(epsg)
    if key not in _transformer_cache:
        _transformer_cache[key] = Transformer.from_crs("EPSG:4326", f"EPSG:{key}", always_xy=True)
    return _transformer_cache[key]

def project_geom_with_transformer(geom, transformer):
    """แปลง shapely geometry โดยใช้ pyproj transformer"""
    return transform(transformer.transform, geom)

# ---------- distance computation ----------
def point_to_geom_distance_m(point_lon, point_lat, geom, epsg_cache_for_geom):
    """
    คำนวณระยะ (เมตร) จากจุด (lon,lat) ไปยัง geom (shapely geometry ใน lon/lat)
    - ใช้ UTM zone ของ point เป็น EPSG
    - epsg_cache_for_geom: dict mapping epsg -> projected_geom (เพื่อ cache per redline)
    คืนค่า distance (float, meters) และ epsg ที่ใช้
    """
    epsg = utm_epsg_for_lon(point_lon, point_lat)
    if epsg not in epsg_cache_for_geom:
        transformer = get_transformer_to_utm(epsg)
        try:
            projected_geom = project_geom_with_transformer(geom, transformer)
        except Exception as e:
            logging.error("การแปลง geometry ไป EPSG:%d ผิดพลาด: %s", epsg, e)
            return float('inf'), epsg
        epsg_cache_for_geom[epsg] = projected_geom

    transformer = get_transformer_to_utm(epsg)
    utm_point = project_geom_with_transformer(Point(point_lon, point_lat), transformer)
    projected_geom = epsg_cache_for_geom[epsg]
    dist_m = projected_geom.distance(utm_point)
    return dist_m, epsg