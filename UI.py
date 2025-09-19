import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from test3 import analyze_kml_files
# from visualize import visualize_kml_data

# == ใส่ฟังก์ชันวิเคราะห์จากโค้ดของคุณที่นี่ ==
# นำเข้า analyze_kml_files จากโค้ดที่คุณเขียนไว้ก่อนหน้านี้

# == ฟังก์ชัน UI ==
class KMLAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KML Analyzer UI")

        self.sites_file = tk.StringVar()
        self.points_file = tk.StringVar()
        self.redlines_file = tk.StringVar()
        self.threshold = tk.DoubleVar(value=5.0)

        self.create_widgets()

    def create_widgets(self):
        # เลือกไฟล์ Site
        self._file_input("Sites KML:", self.sites_file, 0)

        # เลือกไฟล์ Point
        self._file_input("Points KML:", self.points_file, 1)

        # เลือกไฟล์ Redline
        self._file_input("Redlines KML:", self.redlines_file, 2)

        # ค่า Threshold
        tk.Label(self.root, text="Threshold (m):").grid(row=3, column=0, sticky="e")
        tk.Entry(self.root, textvariable=self.threshold, width=10).grid(row=3, column=1, sticky="w")

        # ปุ่ม Run
        run_btn = tk.Button(self.root, text="Analyze", command=self.run_analysis)
        run_btn.grid(row=4, column=0, columnspan=2, pady=10)

        # พื้นที่แสดงผล
        self.output = tk.Text(self.root, height=20, width=70)
        self.output.grid(row=5, column=0, columnspan=3, padx=10, pady=10)

    def _file_input(self, label, variable, row):
        tk.Label(self.root, text=label).grid(row=row, column=0, sticky="e")
        tk.Entry(self.root, textvariable=variable, width=50).grid(row=row, column=1)
        tk.Button(self.root, text="Browse", command=lambda: self.browse_file(variable)).grid(row=row, column=2)

    def browse_file(self, var):
        filename = filedialog.askopenfilename(filetypes=[("KML files", "*.kml")])
        if filename:
            var.set(filename)

    def run_analysis(self):
        self.output.delete(1.0, tk.END)
        t = threading.Thread(target=self._analyze_and_display)
        t.start()

    def _analyze_and_display(self):
        try:
            results = analyze_kml_files(
                self.sites_file.get(),
                self.points_file.get(),
                self.redlines_file.get(),
                self.threshold.get()
            )
            total = 0
            output_lines = []
            output_lines.append(f"=== Analysis Results (Threshold: {self.threshold.get()}m) ===\n")
            for r in results:
                output_lines.append(f"\n{r['from']} → {r['to']}")
                output_lines.append(f"  Segment distance: {r['segment_distance']}m")
                output_lines.append(f"  Points found: {r['count']}")
                total += r['count']
                for point in r['points']:
                    output_lines.append(f"    • {point['name']}: {point['segment_distance']}m from segment, {point['redline_distance']}m from redline")

            output_lines.append(f"\nTotal points found: {total}")
            self.output.insert(tk.END, "\n".join(output_lines))
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")


# เริ่มโปรแกรม
if __name__ == "__main__":
    root = tk.Tk()
    app = KMLAnalyzerApp(root)
    root.mainloop()
