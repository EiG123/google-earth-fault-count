import matplotlib.pyplot as plt
from shapely.geometry import Point
from shapely.ops import transform
from pyproj import Transformer

# -------------------- เตรียม Projections --------------------
utm_project = Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True).transform
utm_project_inv = Transformer.from_crs("EPSG:32647", "EPSG:4326", always_xy=True).transform

# -------------------- ข้อมูลตัวอย่าง (แทนที่ด้วยของคุณ) --------------------
# redlines = [LineString([...]), ...]
# points = [{'lat': ..., 'lon': ...}, ...]
# sites = [{'lat': ..., 'lon': ...}, ...]

# -------------------- เริ่มต้น --------------------
class RedlineVisualizer:
    def __init__(self, redlines, points, sites, threshold_m=100):
        self.redlines = [transform(utm_project, rl) for rl in redlines]
        self.points_geom = [transform(utm_project, Point(p['lon'], p['lat'])) for p in points]
        self.points_raw = points
        self.sites = sites
        self.threshold_m = threshold_m
        self.current_index = 0

        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        self._init_plot()

        self.cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)
        plt.show()

    def _init_plot(self):
        self.ax.clear()
        self.ax.set_title("Click to step through redlines")
        self.ax.set_xlabel("Longitude")
        self.ax.set_ylabel("Latitude")
        self.ax.grid(True)

        # วาด Sites
        site_lons = [s['lon'] for s in self.sites]
        site_lats = [s['lat'] for s in self.sites]
        self.ax.scatter(site_lons, site_lats, c='red', s=80, label='Sites', zorder=5)

        self.ax.legend()

    def onclick(self, event):
        if self.current_index >= len(self.redlines):
            self.ax.set_title("Redlines exhausted.")
            self.fig.canvas.draw()
            return

        redline_utm = self.redlines[self.current_index]
        redline_ll = transform(utm_project_inv, redline_utm)
        x, y = redline_ll.xy
        self.ax.plot(x, y, color='gray', linestyle='--', linewidth=2)

        buffer = redline_utm.buffer(self.threshold_m)
        count = 0

        # วาด fault ที่อยู่ใน buffer
        for pt_utm, pt_raw in zip(self.points_geom, self.points_raw):
            if buffer.contains(pt_utm):
                self.ax.scatter(pt_raw['lon'], pt_raw['lat'], c='blue', s=40, marker='x', zorder=4)
                count += 1

        self.ax.set_title(f"Step {self.current_index+1}/{len(self.redlines)} - Found {count} faults")
        self.current_index += 1
        self.fig.canvas.draw()

