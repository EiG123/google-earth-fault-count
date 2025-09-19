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

from ..parse_controller.parse_points import parse_kml_points
from ..parse_controller.parse_lines import parse_kml_lines
from ..geom_controller.geom import point_to_geom_distance_m

def analyze_points_vs_redlines(points_grouped, redlines_files, threshold_m=100):
    """
    points_grouped: dict mapping group_name -> filepath (kml)
    redlines_files: list of redline kml file paths
    Returns:
      - points_df: pandas.DataFrame with nearest redline and distance
      - redline_summary: dict mapping redline_name -> list of matched point dicts
    """
    # 1) Load points (with group label)
    all_points = []
    logging.info("เริ่มอ่านไฟล์ points...")
    for group_name, filepath in points_grouped.items():
        pts = parse_kml_points(filepath)
        if not pts:
            logging.info("ไฟล์ %s - ไม่มีจุดหรือไม่พบ", filepath)
            continue
        for p in pts:
            p['group'] = group_name
            p['key'] = group_name
            all_points.append(p)
        logging.info("อ่าน %s -> %d จุด", group_name, len(pts))

    if not all_points:
        logging.error("ไม่พบ points ใด ๆ")
        return None, None

    # ตรวจสอบและแจ้งเตือนจุดที่ซ้ำกัน (same lat/lon but different details)
    coord_groups = defaultdict(list)
    for p in all_points:
        coord_key = (round(float(p['lat']), 6), round(float(p['lon']), 6))  # ปัดเศษเพื่อจัดการ floating point precision
        coord_groups[coord_key].append(p)
    
    # รายงานจุดที่มี coordinate เหมือนกันแต่รายละเอียดต่าง
    duplicate_coords = 0
    for coord, points in coord_groups.items():
        if len(points) > 1:
            # ตรวจสอบว่ามีรายละเอียดที่แตกต่างกันหรือไม่
            unique_details = set()
            for p in points:
                detail_key = (
                    p.get('ticket'), 
                    p.get('sign'), 
                    p.get('site'), 
                    p.get('group')
                )
                unique_details.add(detail_key)
            
            if len(unique_details) > 1:
                duplicate_coords += 1
                logging.warning(
                    "พบจุดที่มี coordinate เหมือนกัน (%s) แต่รายละเอียดต่าง: %d จุด",
                    coord, len(points)
                )
                for i, p in enumerate(points):
                    logging.warning(
                        "  - จุดที่ %d: ticket=%s, sign=%s, site=%s, group=%s",
                        i+1, p.get('ticket'), p.get('sign'), p.get('site'), p.get('group')
                    )
    
    if duplicate_coords > 0:
        logging.warning("พบ coordinate ที่ซ้ำกันทั้งหมด %d ตำแหน่ง", duplicate_coords)

    # 2) Load redlines
    redline_geoms = []
    for fname in redlines_files:
        geom = parse_kml_lines(fname)
        if geom is None:
            logging.warning("redline %s ไม่มี geometry - ข้าม", fname)
            continue
        redline_geoms.append({
            'name': os.path.basename(fname),
            'geom': geom,
            'epsg_cache': {}  # จะเก็บ projected geometry per EPSG (per-zone caching)
        })
        logging.info("โหลด redline: %s", fname)

    if not redline_geoms:
        logging.error("ไม่พบ redlines ที่ใช้งานได้")
        return None, None

    # 3) สำหรับแต่ละ point หา nearest distance กับแต่ละ redline (ใช้ cache per redline per EPSG)
    points_results = []
    redline_matches = defaultdict(list)  # redline_name -> list of point dicts (matched within threshold)
    logging.info("เริ่มคำนวณระยะ (threshold %d m)...", threshold_m)

    for p in tqdm(all_points, desc="processing points"):
        lon = float(p['lon'])
        lat = float(p['lat'])
        best_dist = float('inf')
        best_redline = None
        matched_any = False

        for rl in redline_geoms:
            dist, epsg_used = point_to_geom_distance_m(lon, lat, rl['geom'], rl['epsg_cache'])
            # เก็บ nearest
            if dist < best_dist:
                best_dist = dist
                best_redline = rl['name']

            if dist <= threshold_m:
                # matched within threshold -> เก็บลง summary
                matched_any = True
                # store a shallow copy with distance + group
                rec = {
                    'group': p.get('group'),
                    'lat': lat,
                    'lon': lon,
                    'ticket': p.get('ticket'),
                    'sign': p.get('sign'),
                    'sla': p.get('sla'),
                    'region': p.get('region'),
                    'site': p.get('site'),
                    'online/mobile': p.get('online/mobile'),
                    'distance_m': dist
                }
                redline_matches[rl['name']].append(rec)

        # append overall point result
        points_results.append({
            'group': p.get('group'),
            'lat': lat,
            'lon': lon,
            'ticket': p.get('ticket'),
            'sign': p.get('sign'),
            'sla': p.get('sla'),
            'region': p.get('region'),
            'site': p.get('site'),
            'online/mobile': p.get('online/mobile'),
            'nearest_redline': best_redline,
            'distance_m': best_dist,
            'matched': matched_any,
            'key': p.get('key')
        })

    # 4) ทำ DataFrame และ summary
    points_df = pd.DataFrame(points_results)

    # Enhanced summary per redline with better deduplication
    redline_summary_counts = {}

    for rl in redline_geoms:   # ✅ วนทุก redline ที่โหลด ไม่ใช่แค่ redline_matches
        name = rl['name']
        matches = redline_matches.get(name, [])  # ถ้าไม่มี match → [] ว่าง
        
        # Option 1: Dedupe by lat/lon only
        seen_coords = set()
        unique_by_coords = []
        for r in matches:
            coord_key = (round(r.get('lat', 0), 6), round(r.get('lon', 0), 6))
            if coord_key not in seen_coords:
                seen_coords.add(coord_key)
                unique_by_coords.append(r)

        # Option 2: Dedupe by full details
        seen_full = set()
        unique_by_full = []
        for r in matches:
            full_key = (
                r.get('ticket'), 
                round(r.get('lat', 0), 6), 
                round(r.get('lon', 0), 6),
                r.get('site'),
                r.get('sign')
            )
            if full_key not in seen_full:
                seen_full.add(full_key)
                unique_by_full.append(r)

        redline_summary_counts[name] = {
            'count': len(unique_by_full),
            'count_by_coords': len(unique_by_coords),
            'count_by_details': len(unique_by_full),
            'total_matches': len(matches),
            'points': unique_by_coords,
            'points_by_coords': unique_by_coords,
            'points_by_details': unique_by_full,
            'raw_matches': matches
        }

        # แจ้งเตือนความต่างระหว่าง dedupe (ถ้ามี)
        if len(unique_by_coords) != len(unique_by_full):
            logging.info(
                "Redline %s: coordinate-based count (%d) != detail-based count (%d)",
                name, len(unique_by_coords), len(unique_by_full)
            )


    return points_df, redline_summary_counts