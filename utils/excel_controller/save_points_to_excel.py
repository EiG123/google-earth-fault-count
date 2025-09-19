import pandas as pd

def save_points_to_excel(points, output_filename):
    """บันทึก list ของ dict เป็นไฟล์ Excel"""
    df = pd.DataFrame(points)
    df.to_excel(output_filename, index=False, engine='openpyxl')
    print(f"✅ บันทึกข้อมูลลง Excel แล้ว: {output_filename}")