import xml.etree.ElementTree as ET
from shapely.geometry import LineString, Point
from shapely.ops import transform
from pyproj import Transformer
from tqdm import tqdm
from collections import defaultdict
from pyproj import CRS
from visualize import visualize_kml_data_interactive
from shapely.ops import unary_union
import os

def make_project_fn(lon, lat):
    """สร้าง projection function สำหรับแปลง WGS84 -> UTM"""
    utm_crs = get_utm_crs(lon, lat)
    transformer = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    return lambda geom: transform(transformer.transform, geom)

def get_utm_crs(lon, lat):
    """คำนวณ UTM zone ที่เหมาะสมตามพิกัด"""
    zone = int((lon + 180) / 6) + 1
    is_northern = lat >= 0
    return CRS.from_epsg(32600 + zone if is_northern else 32700 + zone)

def parse_kml_points(filename):
    """อ่านจุด (points) จากไฟล์ KML"""
    tree = ET.parse(filename)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    points = []

    for placemark in root.findall('.//kml:Placemark', ns):
        ext_data = {}
        for sd in placemark.findall('.//kml:ExtendedData//kml:SimpleData', ns):
            name = sd.attrib.get('name')
            val = sd.text
            ext_data[name] = val

        coord_elem = placemark.find('.//kml:Point/kml:coordinates', ns)
        if coord_elem is not None:
            coords = coord_elem.text.strip()
            lon, lat, *_ = map(float, coords.split(','))
            point = {
                'lat': lat,
                'lon': lon,
                'ticket': ext_data.get('TICKET', 'N/A'),
                'sign': ext_data.get('Sign', 'N/A')
            }
            points.append(point)

    return points

def parse_kml_lines(filename):
    """อ่านเส้น (lines) จากไฟล์ KML"""
    tree = ET.parse(filename)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    lines = []

    for i, placemark in enumerate(root.findall('.//kml:Placemark', ns), start=1):
        coords_elem = placemark.find('.//kml:coordinates', ns)
        if coords_elem is not None:
            coord_text = coords_elem.text.strip()
            coord_pairs = [tuple(map(float, coord.split(',')[:2])) for coord in coord_text.strip().split()]
            if len(coord_pairs) >= 2:
                lines.append(LineString(coord_pairs))
            else:
                print(f"[WARN] Placemark #{i} มีพิกัดน้อยเกินไป ({len(coord_pairs)} จุด) ข้ามไป")

    return lines

def parse_combined_redlines(filenames):
    """รวมเส้นจากหลายไฟล์เป็น redlines"""
    combined_redlines = []

    for fname in filenames:
        if not os.path.exists(fname):
            print(f"[ERROR] ไม่พบไฟล์: {fname}")
            continue
            
        # ดึงเส้นทั้งหมดจากไฟล์
        lines = parse_kml_lines(fname)

        if not lines:
            print(f"ข้าม '{fname}' เพราะไม่มีเส้น")
            continue

        # รวมเส้นในไฟล์นี้เป็น redline เดียว
        combined = unary_union(lines)
        combined_redlines.append({
            "name": os.path.basename(fname),
            "geometry": combined
        })

        print(f"รวมเส้นจาก '{fname}' ได้ geometry: {type(combined)}")

    return combined_redlines

def count_faults_per_redline(points, redlines, redlines_files, threshold_m):
    """นับจำนวน point ที่อยู่ใกล้แต่ละเส้น redline"""
    redline_summary = defaultdict(list)
    
    # สร้าง mapping ระหว่าง redline กับไฟล์ต้นฉบับ
    lines_per_file = []
    for fname in redlines_files:
        if not os.path.exists(fname):
            print(f"[ERROR] ไม่พบไฟล์: {fname}")
            continue
            
        file_lines = parse_kml_lines(fname)
        lines_per_file.append({
            "name": os.path.basename(fname),
            "lines": file_lines
        })
    
    # วิเคราะห์แต่ละไฟล์
    for file_data in tqdm(lines_per_file, desc="ตรวจสอบแต่ละไฟล์"):
        file_name = file_data["name"]
        file_lines = file_data["lines"]
        
        if not file_lines:
            print(f"[WARN] ไม่พบเส้นในไฟล์ {file_name}")
            continue
            
        # รวมเส้นทั้งหมดในไฟล์เป็น geometry เดียว
        combined_geom = unary_union(file_lines) if len(file_lines) > 1 else file_lines[0]
        
        # หาจุดใดจุดหนึ่งเพื่อกำหนด UTM zone
        if hasattr(combined_geom, 'coords'):
            # Single LineString
            lon, lat = list(combined_geom.coords)[0]
        elif hasattr(combined_geom, 'geoms'):
            # MultiLineString
            lon, lat = list(combined_geom.geoms[0].coords)[0]
        else:
            print(f"[WARN] ไม่สามารถหา coordinate สำหรับ {file_name}")
            continue
            
        project_fn = make_project_fn(lon, lat)

        # แปลง redline ไป UTM และสร้าง buffer
        utm_redline = project_fn(combined_geom)
        buffer_zone = utm_redline.buffer(threshold_m)

        for point in points:
            wgs_point = Point(point['lon'], point['lat'])
            utm_point = project_fn(wgs_point)

            if buffer_zone.contains(utm_point):
                redline_summary[file_name].append(point)

    return redline_summary

def count_points_near_redlines(points, redlines, threshold_m):
    """นับจำนวน point ที่อยู่ใกล้ redlines รวมทั้งหมด"""
    count = 0
    
    for point in points:
        found_match = False
        wgs_point = Point(point['lon'], point['lat'])
        
        for redline_geom in redlines:
            # หา coordinate สำหรับ projection
            if hasattr(redline_geom, 'coords'):
                lon, lat = list(redline_geom.coords)[0]
            elif hasattr(redline_geom, 'geoms'):
                lon, lat = list(redline_geom.geoms[0].coords)[0]
            else:
                continue
                
            project_fn = make_project_fn(lon, lat)
            utm_point = project_fn(wgs_point)
            utm_redline = project_fn(redline_geom)
            buffer_zone = utm_redline.buffer(threshold_m)

            if buffer_zone.contains(utm_point):
                count += 1
                print(f"TICKET: {point.get('ticket', 'N/A')}, SIGN: {point.get('sign', 'N/A')} → ภายใน {threshold_m} เมตร")
                found_match = True
                break
                
        if not found_match:
            # ตรวจสอบระยะใกล้สุด (สำหรับ debug)
            min_dist = float('inf')
            for redline_geom in redlines:
                if hasattr(redline_geom, 'coords'):
                    lon, lat = list(redline_geom.coords)[0]
                elif hasattr(redline_geom, 'geoms'):
                    lon, lat = list(redline_geom.geoms[0].coords)[0]
                else:
                    continue
                    
                project_fn = make_project_fn(lon, lat)
                utm_point = project_fn(wgs_point)
                utm_redline = project_fn(redline_geom)
                dist = utm_redline.distance(utm_point)
                min_dist = min(min_dist, dist)
                
            if min_dist < threshold_m + 50:  # ใกล้เกินไปแต่ไม่เข้า?
                print(f"[WARN] ใกล้มาก (ระยะ {min_dist:.2f} m) แต่ไม่โดน buffer - ticket: {point['ticket']}")

    return count

if __name__ == "__main__":
    # กำหนดไฟล์
    points_file = "Test/M1/Confirm.kml"
    redlines_files = [
        "A/ยังไม่ได้แยก/U1/BJ 3007.kml",
        "A/ยังไม่ได้แยก/U1/CMI0072_DN-CMI1000_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000 to LPN3052 (New).kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN - LPN3052_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-CMI0078_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-CMI0078_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-CMI1641_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-CMI2009_DN ช่วงที่มีการคร่อมสาย.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-CMI2009_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-CMI2009-DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-CMI6837_DN-MHS1601_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-LPG1521_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-LPG1521_DN_3.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-LPG1521_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-LPN3052_DN (New).kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-LPN3052_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-LPN3052_DN_หนองหอย.kml",
        "A/ยังไม่ได้แยก/U1/CMI1000_DN-LPN3052_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1601_DN-CMI1000_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1682_DN-CMI1601_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI1682_DN-CMI2009_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI2009_DN-CMI3010_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI2009_DN-CRI3014_DN ช่วงที่มีการคร่อมสาย.kml",
        "A/ยังไม่ได้แยก/U1/CMI2009_DN-CRI3014_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI2116_DN-CMI2115_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/CMI2116_DN-CMI2115_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI2250_DN-CMI0078_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI2250_DN-CMI2115_DN คร่อมสาย.kml",
        "A/ยังไม่ได้แยก/U1/CMI3010_DN-LPG1604_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/CMI3010_DN-LPG1604_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI6738 to CMI0073.kml",
        "A/ยังไม่ได้แยก/U1/CMI6837_DN-LPN3052_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/CMI6837_DN-LPN3052_DN.kml",
        "A/ยังไม่ได้แยก/U1/CMI6837_DN-MHS6749_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI1601_DN-CRI2065_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI1720_DN-CRI2009_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI1903_PN-CRI1219_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI1903_PN-CRI1720_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI1903_PN-CRI2067_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/CRI1903_PN-CRI2067_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI1903_PN-CRI8651_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI1903_PN-PYO1712_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI2009_DN-CRI1601_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI2009_DN-CRI8625_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/CRI2009_DN-CRI8625_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI2065_DN-CRI1219_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI2067_DN-PYO3107_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI3014_DN-CRI8651_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI8625_DN-CMI2116_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/CRI8625_DN-CMI2116_DN.kml",
        "A/ยังไม่ได้แยก/U1/CRI8651_DN-CMI2115_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/CRI8651_DN-CMI2115_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPG1102_DN-LPN1138_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPG1102_DN-TAK2391_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPG1521_DN วัดป่าขาม - LPG3120_DN แยกวัดนาแก้ว.kml",
        "A/ยังไม่ได้แยก/U1/LPG3112_DN การประปาส่วนภูมิภาคเถิน - LPG3120_DN แยกวัดนาแก้ว.kml",
        "A/ยังไม่ได้แยก/U1/LPG6737_DN-LPG1521_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPG6737_DN-LPG1604_DN-CRI3014_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPG6737_DN-LPG1604_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPG6737_DN-PHE0569_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPN1138_DN-LPN3007_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPN3007_DN-LPG1102_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/LPN3007_DN-LPG1102_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPN3007_DN-LPN3051_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPN3007_DN-LPN3052_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/LPN3007_DN-LPN3052_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPN3052_DN-CMI0637_DN.kml",
        "A/ยังไม่ได้แยก/U1/LPN3052_DN-CMI6837_DN.kml",
        "A/ยังไม่ได้แยก/U1/MHS1601_DN-MHS6700_DN.kml",
        "A/ยังไม่ได้แยก/U1/MHS1602_DN-CMI0078_DN.kml",
        "A/ยังไม่ได้แยก/U1/MHS1606_DN-MHS6714_DN.kml",
        "A/ยังไม่ได้แยก/U1/MHS1606_DN-MHS6749_DN.kml",
        "A/ยังไม่ได้แยก/U1/MHS6700_DN-MHS1602_DN.kml",
        "A/ยังไม่ได้แยก/U1/MHS6714_DN-MHS1603_DN.kml",
        "A/ยังไม่ได้แยก/U1/MHS6749_DN-CMI6822_DN.kml",
        "A/ยังไม่ได้แยก/U1/NAN1288_DN-NAN1606_DN.kml",
        "A/ยังไม่ได้แยก/U1/NAN1288_DN-PHE6731_DN.kml",
        "A/ยังไม่ได้แยก/U1/NAN1288_DN-PYO6713_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/NAN1288_DN-PYO6713_DN.kml",
        "A/ยังไม่ได้แยก/U1/NAN8804_DN-NAN1606_DN.kml",
        "A/ยังไม่ได้แยก/U1/New OFC BJ(LPN3052)-CMI1000.kml",
        "A/ยังไม่ได้แยก/U1/New OFC.kml",
        "A/ยังไม่ได้แยก/U1/PHE0569_DN-PHE3103_DN.kml",
        "A/ยังไม่ได้แยก/U1/PHE0569_DN-PHE6731_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/PHE0569_DN-PHE6731_DN.kml",
        "A/ยังไม่ได้แยก/U1/PHE0569_DN-UTR1611_DN.kml",
        "A/ยังไม่ได้แยก/U1/PHE3103_DN-PHE6731_DN.kml",
        "A/ยังไม่ได้แยก/U1/PHE6719_DN บ้านแม่ลอง - LPG1521_DN วัดป่าขาม.kml",
        "A/ยังไม่ได้แยก/U1/PHE6719_DN บ้านแม่ลอง-LPG1521_DN วัดป่าขาม.kml",
        "A/ยังไม่ได้แยก/U1/PHE6719_DN-LPG1521_DN.kml",
        "A/ยังไม่ได้แยก/U1/PHE6719_DN-PHE0569_DN.kml",
        "A/ยังไม่ได้แยก/U1/PHE6731_DN-LPG6737_DN.kml",
        "A/ยังไม่ได้แยก/U1/PHE6746_DN-PHE6719_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/PHE6746_DN-PHE6719_DN.kml",
        "A/ยังไม่ได้แยก/U1/PYO1148_DN-PYO1712_DN.kml",
        "A/ยังไม่ได้แยก/U1/PYO1148_DN-PYO6713_DN OFC 60C Fig8.kml",
        "A/ยังไม่ได้แยก/U1/PYO1712_DN-CRI2067_DN-CRI1903_PN.kml",
        "A/ยังไม่ได้แยก/U1/PYO1712_DN-NAN8804_DN.kml",
        "A/ยังไม่ได้แยก/U1/PYO3107_DN-CRI2067_DN.kml",
        "A/ยังไม่ได้แยก/U1/PYO3107_DN-CRI3014_DN.kml",
        "A/ยังไม่ได้แยก/U1/PYO3107_DN-LPG6737_DN_2.kml",
        "A/ยังไม่ได้แยก/U1/PYO3107_DN-LPG6737_DN.kml",
        "A/ยังไม่ได้แยก/U1/PYO3107_DN-PYO1148_DN.kml",
        "A/ยังไม่ได้แยก/U1/SKT6708_DN-PHE6746_DN.kml",

        "A/ยังไม่ได้แยก/U2/EGAT MAE SOT-EGAT_TAK1.kml",
        "A/ยังไม่ได้แยก/U2/KPP1144_DN-KPP1606_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/KPP1144_DN-KPP1606_DN.kml",
        "A/ยังไม่ได้แยก/U2/KPP1144_DN-KPP2036_DN.kml",
        "A/ยังไม่ได้แยก/U2/KPP1144_DN-KPP3188_DN_48C.kml",
        "A/ยังไม่ได้แยก/U2/KPP1144_DN-KPP3188_DN.kml",
        "A/ยังไม่ได้แยก/U2/KPP1144_DN-TAK2391_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/KPP1144_DN-TAK2391_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/KPP1144_DN-TAK2391_DN_48C.kml",
        "A/ยังไม่ได้แยก/U2/KPP1144_DN-TAK2391_DN.kml",
        "A/ยังไม่ได้แยก/U2/KPP1606_DN-PCT1123_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/KPP1606_DN-PCT1123_DN.kml",
        "A/ยังไม่ได้แยก/U2/KPP2036_DN-KPP1144_DN.kml",
        "A/ยังไม่ได้แยก/U2/KPP2036_DN-KPP1606_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/KPP2036_DN-KPP1606_DN.kml",
        "A/ยังไม่ได้แยก/U2/KPP2036_DN-SKT8528_DN.kml",
        "A/ยังไม่ได้แยก/U2/KPP3188_DN-NKW1239_DN.kml",
        "A/ยังไม่ได้แยก/U2/KPP3188_DN-PCT6742_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/KPP3188_DN-PCT6742_DN.kml",
        "A/ยังไม่ได้แยก/U2/NKW0567_DN-PCB1159_DN.kml",
        "A/ยังไม่ได้แยก/U2/NKW0567_DN-PCT1125_DN.kml",
        "A/ยังไม่ได้แยก/U2/NKW1082_DN-PCT1122_DN.kml",
        "A/ยังไม่ได้แยก/U2/NKW1239_DN-KPP3188_DN.kml",
        "A/ยังไม่ได้แยก/U2/NKW1239_DN-NKW8557_DN.kml",
        "A/ยังไม่ได้แยก/U2/NKW1239_DN-PNP-I (PNP_ITL).kml",
        "A/ยังไม่ได้แยก/U2/NKW8557_DN-NKW1082_DN.kml",
        "A/ยังไม่ได้แยก/U2/NKW8557_DN-PCT6742_DN.kml",
        "A/ยังไม่ได้แยก/U2/NKW8557_DN-PNP-I.kml",
        "A/ยังไม่ได้แยก/U2/Node แม่ตื่น-TAK-I.kml",
        "A/ยังไม่ได้แยก/U2/Node แม่ตื่น-TAK1603_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCB2099_DN-PCB1159_DN_60C.kml",
        "A/ยังไม่ได้แยก/U2/PCB2099_DN-PCB1159_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCB2158_DN-PSN0545_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PCB2158_DN-PSN0545_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCB8030_PN-PCB2099_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PCB8030_PN-PCB2099_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCB8030_PN-PCB2158_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PCB8030_PN-PCB2158_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCB8030_PN-PCB8800_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PCB8030_PN-PCB8800_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCB8800_DN-PCT1125_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT-I-PLK_ITL.kml",
        "A/ยังไม่ได้แยก/U2/PCT1120_DN-PCT1122_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1120_DN-PCT1125_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1120_DN-PCT1291_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1120_DN-PCT6742_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1123_DN-KPP1606_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PCT1123_DN-KPP1606_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1123_DN-PCT6742_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PCT1123_DN-PCT6742_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/PCT1123_DN-PCT6742_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1124_DN-PCT1291_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1124_DN-PSN1160_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PCT1124_DN-PSN1160_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1125_DN-NKW0567_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1125_DN-PCT1124_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PCT1125_DN-PCT1124_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1291_DN-PCT-I.kml",
        "A/ยังไม่ได้แยก/U2/PCT1291_DN-PCT1123_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1291_DN-PCT1124_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT1291_DN-PSN2005_DN.kml",
        "A/ยังไม่ได้แยก/U2/PCT6742_DN-NKW1239_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PCT6742_DN-PCT1291_DN.kml",
        "A/ยังไม่ได้แยก/U2/PLK_ITL-PSN0013_DN (True 0013).kml",
        "A/ยังไม่ได้แยก/U2/PNP-I-PCT-I.kml",
        "A/ยังไม่ได้แยก/U2/PSN0012_DN-PCT1123_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PSN0012_DN-PCT1123_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/PSN0012_DN-PCT1123_DN_4.kml",
        "A/ยังไม่ได้แยก/U2/PSN0012_DN-PCT1123_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0013_DN-PSN0017_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PSN0013_DN-PSN0017_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0013_DN-PSN0543_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0013_DN-PSN1160_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PSN0013_DN-PSN1160_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/PSN0013_DN-PSN1160_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0013_DN-PSN2005_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0013_DN-PSN3121_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0013_DN-SKT8528_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PSN0013_DN-SKT8528_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0017_DN-PLK_ITL.kml",
        "A/ยังไม่ได้แยก/U2/PSN0017_DN-PSN0012_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PSN0017_DN-PSN0012_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/PSN0017_DN-PSN0012_DN_4.kml",
        "A/ยังไม่ได้แยก/U2/PSN0017_DN-PSN0012_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0017_DN-PSN0013_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0017_DN-SKT8528_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0545_DN-PCB2158_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN0545_DN-PSN1160_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN1160_DN-PCT1124_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/PSN1160_DN-PCT1124_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN1624_DN-PSN0543_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN2005_DN-PCT1291_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN2005_DN-PSN0013_DN.kml",
        "A/ยังไม่ได้แยก/U2/PSN3121_DN-PSN0013_DN.kml",
        "A/ยังไม่ได้แยก/U2/SKT2032_DN-SKT8528_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/SKT2032_DN-SKT8528_DN.kml",
        "A/ยังไม่ได้แยก/U2/SKT2591 DN-SKT8528_DN.kml",
        "A/ยังไม่ได้แยก/U2/SKT2591_DN-SKT8528_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/SKT2591_DN-SKT8528_DN.kml",
        "A/ยังไม่ได้แยก/U2/SKT3032_DN-SKT6708_DN.kml",
        "A/ยังไม่ได้แยก/U2/SKT6708_DN-SKT3032_DN.kml",
        "A/ยังไม่ได้แยก/U2/SKT6708_DN-UTR1611_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/SKT6708_DN-UTR1611_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/SKT6708_DN-UTR1611_DN_4.kml",
        "A/ยังไม่ได้แยก/U2/SKT6708_DN-UTR1611_DN.kml",
        "A/ยังไม่ได้แยก/U2/SKT8528_DN-KPP2036_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/SKT8528_DN-KPP2036_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/SKT8528_DN-KPP2036_DN.kml",
        "A/ยังไม่ได้แยก/U2/SKT8528_DN-PSN0017_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/SKT8528_DN-PSN0017_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/SKT8528_DN-PSN0017_DN.kml",
        "A/ยังไม่ได้แยก/U2/SKT8528_DN-SKT3032_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/SKT8528_DN-SKT3032_DN.kml",
        "A/ยังไม่ได้แยก/U2/TAK-I-TAK2391_DN.kml",
        "A/ยังไม่ได้แยก/U2/TAK1609_DN-EGAT MAE SOT.kml",
        "A/ยังไม่ได้แยก/U2/TAK1609_DN-TAK1603_DN.kml",
        "A/ยังไม่ได้แยก/U2/TAK2391_DN-KPP2036_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/TAK2391_DN-KPP2036_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/TAK2391_DN-KPP2036_DN_4.kml",
        "A/ยังไม่ได้แยก/U2/TAK2391_DN-KPP2036_DN.kml",
        "A/ยังไม่ได้แยก/U2/TAK2391_DN-SKT2591_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/TAK2391_DN-SKT2591_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/TAK2391_DN-SKT2591_DN.kml",
        "A/ยังไม่ได้แยก/U2/TAK2391_DN-SKT8528_DN.kml",
        "A/ยังไม่ได้แยก/U2/UTR1611_DN-PSN3121_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/UTR1611_DN-PSN3121_DN_3.kml",
        "A/ยังไม่ได้แยก/U2/UTR1611_DN-PSN3121_DN.kml",
        "A/ยังไม่ได้แยก/U2/UTR1611_DN-UTR2030_DN_2.kml",
        "A/ยังไม่ได้แยก/U2/UTR1611_DN-UTR2030_DN.kml",
        "A/ยังไม่ได้แยก/U2/UTR2030_DN-PSN1624_D_2.kml",
        "A/ยังไม่ได้แยก/U2/UTR2030_DN-PSN1624_DN.kml",
        "A/ยังไม่ได้แยก/U2/UTR6708_DN-UTR1611_DN_60c.kml",
    ]

    # ตรวจสอบไฟล์
    if not os.path.exists(points_file):
        print(f"[ERROR] ไม่พบไฟล์ points: {points_file}")
        exit(1)

    # อ่านข้อมูล
    print("🔄 อ่านข้อมูล points...")
    points = parse_kml_points(points_file)
    print(f"✅ อ่าน {len(points)} points แล้ว")

    print("🔄 อ่านข้อมูล redlines...")
    redlines = parse_combined_redlines(redlines_files)
    print(f"✅ อ่าน {len(redlines)} redlines แล้ว")

    if not points:
        print("[ERROR] ไม่มี points ให้วิเคราะห์")
        exit(1)
        
    if not redlines:
        print("[ERROR] ไม่มี redlines ให้วิเคราะห์")
        exit(1)

    # วิเคราะห์ข้อมูล
    threshold_m = 100  # ระยะห่างไม่เกิน 100 เมตร
    
    print(f"\n🔄 วิเคราะห์ fault points ในระยะ {threshold_m} เมตร...")
    
    # วิธีใหม่ - นับแยกตาม redline file
    result = count_faults_per_redline(points, redlines, redlines_files, threshold_m)
    
    # วิธีเก่า - นับรวม
    # total_count = count_points_near_redlines(points, redlines, threshold_m)

    # แสดงผลสรุป
    print("\n" + "="*50)
    print("📌 สรุปผลการวิเคราะห์:")
    print("="*50)
    
    total_unique = 0
    for redline_name, matched_points in result.items():
        print(f"🔴 {redline_name}: เจอ {len(matched_points)} จุด")
        
        # แสดงรายละเอียด points (จำกัดแค่ 5 รายการแรก)
        for i, point in enumerate(matched_points[:]):
            print(f"   └─ TICKET: {point.get('ticket', 'N/A')}, SIGN: {point.get('sign', 'N/A')}")
        
        # if len(matched_points) > 5:
        #     print(f"   └─ ... และอีก {len(matched_points) - 5} จุด")
            
        total_unique += len(matched_points)

    print(f"\n✅ รวมทั้งหมดเจอ {total_unique} fault points ภายใน {threshold_m} เมตร")
    # print(f"🔍 การนับแบบเก่า: {total_count} points")

    # สร้างภาพ (ถ้ามี visualize function)
    # try:
    #     print("\n🔄 สร้างภาพแสดงผล...")
    #     visualize_kml_data_interactive(points, redlines)
    #     print("✅ สร้างภาพสำเร็จ")
    # except Exception as e:
    #     print(f"[WARN] ไม่สามารถสร้างภาพได้: {e}")