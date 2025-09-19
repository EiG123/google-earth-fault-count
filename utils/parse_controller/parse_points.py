import os
import xml.etree.ElementTree as ET
import logging

ns = {'kml': 'http://www.opengis.net/kml/2.2'}

def parse_kml_points(filename):
    """อ่านจุดจาก KML → คืนค่า list ของ dict {'lat','lon','ticket','sign'}"""
    if not os.path.exists(filename):
        logging.warning("ไม่พบไฟล์ points: %s", filename)
        return []
    tree = ET.parse(filename)
    root = tree.getroot()
    points = []

    for placemark in root.findall('.//kml:Placemark', ns):
        ext_data = {}
        for sd in placemark.findall('.//kml:ExtendedData//kml:SimpleData', ns):
            name = sd.attrib.get('name')
            val = sd.text
            ext_data[name] = val

        coord_elem = placemark.find('.//kml:Point/kml:coordinates', ns)
        if coord_elem is not None and coord_elem.text:
            coords = coord_elem.text.strip()
            try:
                lon, lat, *_ = map(float, coords.split(','))
            except Exception:
                logging.warning("ไม่สามารถอ่านพิกัดจาก placemark ใน %s", filename)
                continue
            points.append({
                'lat': lat,
                'lon': lon,
                'ticket': ext_data.get('TICKET', None) or ext_data.get('Ticket', None) or 'N/A',
                'sign': ext_data.get('Sign', None) or 'N/A',
                'sla': ext_data.get('SLA', None) or 'N/A',
                'region': ext_data.get('Region', None) or 'N/A',
                'site': ext_data.get('Site', None) or 'N/A',
                'online/mobile': ext_data.get('Online___Mobile', None) or 'N/A',
            })
    return points