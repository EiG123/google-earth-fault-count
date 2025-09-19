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

ns = {'kml': 'http://www.opengis.net/kml/2.2'}

def parse_kml_lines(filepath):
    """
    อ่าน KML แล้วดึงทุก LineString ออกมา
    return: MultiLineString (ถ้ามีหลายเส้น) หรือ LineString (ถ้ามีเส้นเดียว) หรือ None
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        # KML namespace
        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        lines = []
        for linestring in root.findall(".//kml:LineString", ns):
            coords = linestring.find("kml:coordinates", ns)
            if coords is None or not coords.text.strip():
                continue

            points = []
            for coord in coords.text.strip().split():
                parts = coord.split(",")
                if len(parts) < 2:
                    continue
                lon, lat = float(parts[0]), float(parts[1])
                points.append((lon, lat))

            if len(points) >= 2:
                lines.append(LineString(points))

        if not lines:
            return None
        elif len(lines) == 1:
            return lines[0]
        else:
            return MultiLineString(lines)

    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None