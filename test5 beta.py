#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

from utils.parse_controller.parse_points import parse_kml_points
from utils.parse_controller.parse_lines import parse_kml_lines
from utils.excel_controller.save_points_to_excel import save_points_to_excel
from utils.main_controller.main_analysis import analyze_points_vs_redlines  
from utils.excel_controller.write_results_to_excel import write_results_to_excel

# ---------- config ----------
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
ns = {'kml': 'http://www.opengis.net/kml/2.2'}
# ปรับ threshold ตามต้องการ (เมตร)
THRESHOLD_M = 100
# --------------------------------

# ---------- parsing functions ----------

# ---------- CRS / transformer helpers ----------

# ---------- main analysis ----------

# ---------- excel output ----------

# ---------- example usage ----------
if __name__ == "__main__":
    # กำหนดไฟล์ points ตามกลุ่ม (แก้ paths ตามจริง)
    from config import points_files

    # M1_Close_Action_file = "Test/M1/Close Action.kml"
    # excel_file = "ALL POINTS/points_output_M1_Close_Action.xlsx"
    # points_list = parse_kml_points(M1_Close_Action_file)
    # save_points_to_excel(points_list, excel_file)
    
    # M1_Confirm_file = "Test/M1/Confirm.kml"
    # excel_file = "ALL POINTS/points_output_M1_Confirm.xlsx"
    # points_list = parse_kml_points(M1_Confirm_file)
    # save_points_to_excel(points_list, excel_file)

    # M1_Revise_file = "Test/M1/Revise.kml"
    # excel_file = "ALL POINTS/points_output_M1_Revise.xlsx"
    # points_list = parse_kml_points(M1_Revise_file)
    # save_points_to_excel(points_list, excel_file)

    # M2_Close_Action_file = "Test/M2/Close Action.kml"
    # excel_file = "ALL POINTS/points_output_M2_Close_Action.xlsx"
    # points_list = parse_kml_points(M2_Close_Action_file)
    # save_points_to_excel(points_list, excel_file)
    
    # M2_Confirm_file = "Test/M2/Confirm.kml"
    # excel_file = "ALL POINTS/points_output_M2_Confirm.xlsx"
    # points_list = parse_kml_points(M2_Confirm_file)
    # save_points_to_excel(points_list, excel_file)

    # M2_Revise_file = "Test/M2/Revise.kml"
    # excel_file = "ALL POINTS/points_output_M2_Revise.xlsx"
    # points_list = parse_kml_points(M2_Revise_file)
    # save_points_to_excel(points_list, excel_file)

    # M3_Close_Action_file = "Test/M3/Close Action.kml"
    # excel_file = "ALL POINTS/points_output_M3_Close_Action.xlsx"
    # points_list = parse_kml_points(M3_Close_Action_file)
    # save_points_to_excel(points_list, excel_file)
    
    # M3_Confirm_file = "Test/M3/Confirm.kml"
    # excel_file = "ALL POINTS/points_output_M3_Confirm.xlsx"
    # points_list = parse_kml_points(M3_Confirm_file)
    # save_points_to_excel(points_list, excel_file)

    # M3_Revise_file = "Test/M3/Revise.kml"
    # excel_file = "ALL POINTS/points_output_M3_Revise.xlsx"
    # points_list = parse_kml_points(M3_Revise_file)
    # save_points_to_excel(points_list, excel_file)

    
    # redline files list
    
    from config import redlines_files

    points_files = {
        # "มกราคม": "มกรา.kml",
        # "กุมภาพันธ์": "กุมภา.kml",
        # "มีนาคม": "มีนา.kml",
        # "เมษายน": "เมษา.kml",
        # "พฤษภาคม": "พฤษภา.kml",
        # "มิถุนายน": "มิถุนา.kml",
        # "test1": "Test/fault_test001.kml",
        # "test2": "Test/fault_test002.kml",
        # "test3": "Test/fault_test003.kml",
        "test4": "Test/Test004.kml",
        "test5": "Test/test005.kml",
        "test6": "Test/test006.kml",
        "test7": "Test/test007.kml",
        "test8": "Test/test008.kml",
        "test010": "Test/test010.kml",
    }

    redlines_files = [
        # "Root/CMI0073-LPN3012.kml",
        # "Root/CMI0637-MHS6749.kml",
        # "Root/CMI1000-CMI0044.kml",
        # "Root/CMI1000-CMI0068.kml",
        # "Root/CMI1000-CMI0072.kml",
        # "Root/CMI1000-CMI0078.kml",
        # "Root/CMI1000-CMI1601.kml",
        # "Root/CMI1000-CMI1641.kml",
        # "Root/CMI1000-CMI1804.kml",
        # "Root/CMI1000-CMI2009.kml",
        # "Root/CMI1000-CMI2381.kml",
        # "Root/CMI1000-CMI3010.kml",
        # "Root/CMI1000-CMI3014.kml",
        # "Root/CMI1000-CMI6837.kml",
        # "Root/CMI1000-CMIA036.kml",
        # "Root/CMI1000-CRI3014.kml",
        # "Root/CMI1000-LPN3012.kml",
        # "Root/CMI1000-LPN3052 (New).kml",
        # "Root/CMI1000-LPN3052 (Old).kml",
        # "Root/CMI1000-LPN3052.kml",
        # "Root/CMI1610-CMI0637.kml",
        # "Root/CMI1641-CMI1953.kml",
        # "Root/CMI1682-CMI1601.kml",
        # "Root/CMI1804-LPN3012.kml",
        # "Root/CMI1942-CMI1507.kml",
        # "Root/CMI1953-CMI2009.kml",
        # "Root/CMI2115-CMI0078.kml",
        # "Root/CMI2115-CMI2250.kml",
        # "Root/CMI2116-CMI2115.kml",
        # "Root/CMI2118-CMI2250.kml",
        # "Root/CMI2250-CMI8875.kml",
        # "Root/CMI3010-LPG1604.kml",
        # "Root/CMI6822-CMI0637.kml",
        # "Root/CMI6822-CMI1000.kml",
        # "Root/CMI6822-MHS1603.kml",
        # "Root/CMI6837-CMI0637 ทางไปถนนใหญ่.kml",
        # "Root/CMI6837-CMI0637.kml",
        # "Root/CMI6837-CMI6822.kml",
        # "Root/CMI6837-LPN3052.kml",
        # "Root/CRI0064-CRI1903.kml",
        # "Root/CRI1219-CRI1903.kml",
        # "Root/CRI1219-CRI2065.kml",
        # "Root/CRI1601-CRI0064.kml",
        # "Root/CRI1601-CRI2009.kml",
        # "Root/CRI1601-CRI2065.kml",
        # "Root/CRI1903-CMI2115.kml",
        # "Root/CRI1903-CRI2009.kml",
        # "Root/CRI1903-CRI2067.kml",
        # "Root/CRI1903-CRI8651.kml",
        # "Root/CRI1903-PYO1712.kml",
        # "Root/CRI1903-PYO3107.kml",
        # "Root/CRI1991-CRI2065.kml",
        # "Root/CRI2009-CMI2115.kml",
        # "Root/CRI2009-CRI8625.kml",
        # "Root/CRI2065-CRI1903.kml",
        # "Root/CRI2067-PYO1712.kml",
        # "Root/CRI2067-PYO3107.kml",
        # "Root/CRI2367-CRI2067.kml",
        # "Root/CRI3014-CMI2118.kml",
        # "Root/CRI3014-PYO3107.kml",
        # "Root/CRI8625-CMI2116.kml",
        # "Root/CRI8651-CMI2115.kml",
        # "Root/CRI8651-CRI3014.kml",
        # "Root/LPG1102-LPG1521.kml", 
        # "Root/LPG1102-LPN3007.kml",
        # "Root/LPG1102-PHE6746.kml",
        # "Root/LPG1102-TAK2391.kml",
        # "Root/LPG1521-LPG3120.kml",
        # "Root/LPG1521-LPG6737.kml",
        # "Root/LPG1521-LPN3052.kml",
        # "Root/LPG1521-PHE0569.kml",
        # "Root/LPG1521-PHE1149.kml",
        # "Root/LPG1521-PHE6719.kml",
        # "Root/LPG1521-PHE6746.kml",
        # "Root/LPG1604-CMI3010.kml",
        # "Root/LPG1604-LPG6722.kml",
        # "Root/LPG1604-LPG6737.kml",
        # "Root/LPG3120-LPG1102.kml",
        # "Root/LPG6722-LPG1521.kml",
        # "Root/LPG6728-LPG1521.kml",
        # "Root/LPG6737-LPG1604.kml",
        # "Root/LPG6737-PHE0569.kml",
        # "Root/LPG6737-PYO3107.kml",
        # "Root/LPN1138-CMI1610.kml",
        # "Root/LPN1761-LPN1138.kml",
        # "Root/LPN3007-LPG1102.kml",
        # "Root/LPN3051-LPN3052.kml",
        # "Root/LPN3052-LPN1761.kml",
        # "Root/LPN3052-LPN3007.kml",
        # "Root/MHS1601-MHS6700.kml",
        # "Root/MHS1602-CMI0078.kml",
        # "Root/MHS1602-MHS6712.kml",
        # "Root/MHS1603-MHS1601.kml",
        # "Root/MHS1606-MHS6714.kml",
        # "Root/MHS6700-MHS1602.kml",
        # "Root/MHS6714-MHS1603.kml",
        # "Root/MHS6749-CMI1000.kml",
        # "Root/MHS6749-CMI1690.kml",
        # "Root/MHS6749-CMI6822.kml",
        # "Root/MHS6749-CMI6837.kml",
        # "Root/MHS6749-MHS1606.kml",
        # "Root/NAN1288-NAN2413.kml",
        # "Root/NAN1288-NAN6763.kml",
        # "Root/NAN1288-PHE6731.kml",
        # "Root/NAN1288-PYO6713.kml",
        # "Root/NAN1601-NAN8546.kml",
        # "Root/NAN1606-NAN1288.kml",
        # "Root/NAN6763-NAN6747.kml",
        # "Root/NAN8546-NAN8805.kml",
        # "Root/NAN8804-NAN1288.kml",
        # "Root/NAN8804-NAN1606.kml",
        # "Root/NAN8804-PYO1712.kml",
        # "Root/NAN8805-NAN1288.kml",
        # "Root/PHE0569-PHE1149.kml",
        # "Root/PHE0569-UTR1611.kml",
        # "Root/PHE1149-PHE6719.kml",
        # "Root/PHE1602-PHE0569.kml",
        # "Root/PHE6719-PHE0569.kml",
        # "Root/PHE6731-NAN1288.kml",
        # "Root/PHE6731-PHE0569.kml",
        # "Root/PHE6731-PHE1602.kml",
        # "Root/PHE6746-SKT6708.kml",
        # "Root/PYO1148-PYO1712.kml",
        # "Root/PYO1148-PYO6713.kml",
        # "Root/PYO1600-PYO1148.kml",
        # "Root/PYO1712-CRI1903.kml",
        # "Root/PYO1712-CRI2367.kml",
        # "Root/PYO3107-CRI1903.kml",
        # "Root/PYO3107-PYO1148.kml",
        # "Root/PYO3107-PYO6701.kml",
        # "Root/PYO6701-PYO6713.kml",
        # "Root/PYO6713-PYO1600.kml"


        ########
        "Root/SKT1338-SKT8528.kml",
    ]

    points_df, redline_summary = analyze_points_vs_redlines(points_files, redlines_files, threshold_m=THRESHOLD_M)

    if points_df is None:
        logging.error("ไม่มีผลลัพธ์จากการวิเคราะห์")
    else:
        # แสดง summary บางส่วน
        logging.info("รวมจุดทั้งหมด: %d", len(points_df))
        total_matched = sum(info['count'] for info in redline_summary.values())
        logging.info("รวม matched (unique) across redlines: %d", total_matched)

        # เขียน excel
        name = "test004_100m"
        write_results_to_excel(points_df, redline_summary,THRESHOLD_M, name +".xlsx", use_detail_count=True)

        # ถ้าต้องการดูสรุปใน console
        for rl_name, info in redline_summary.items():
            logging.info("Redline '%s' -> %d points", rl_name, info['count'])
