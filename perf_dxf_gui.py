# perf_dxf_gui.py
# GUI wrapper for Perf DXF Generator with increased row spacing and icon support.
# Dependencies: ezdxf, shapely  (pip install ezdxf shapely)

import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

import ezdxf
from shapely.geometry import Polygon, Point
from shapely.affinity import translate


# ---------------- Core generator (unchanged behavior) ----------------
def generate_dxf(params, save_path):
    shape_choice = params["shape_choice"]
    offset = float(params["offset"])
    hole_shape_choice = params["hole_shape_choice"]
    hole_size = float(params["hole_size"])
    spacing = float(params["spacing"])
    pattern_choice = params["pattern_choice"]
    keep_clipped = bool(params["keep_clipped"])

    hole_radius = hole_size / 2.0 if hole_shape_choice == "circle" else None
    step = spacing  # center-to-center

    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 1
    msp = doc.modelspace()

    for lname, color in [("OUTER", 7), ("HOLES", 3), ("HOLES-CLIPPED", 1)]:
        if lname not in doc.layers:
            doc.layers.add(name=lname, color=color)

    if shape_choice == "rectangle":
        outer_length = float(params["outer_length"])
        outer_width = float(params["outer_width"])
        inner_length = outer_length - 2 * offset
        inner_width = outer_width - 2 * offset
        if inner_length <= 0 or inner_width <= 0:
            raise ValueError("Offset too large for given rectangle dimensions.")

        outer_rect = Polygon([
            (-outer_length / 2, -outer_width / 2),
            ( outer_length / 2, -outer_width / 2),
            ( outer_length / 2,  outer_width / 2),
            (-outer_length / 2,  outer_width / 2),
        ])
        msp.add_lwpolyline(list(outer_rect.exterior.coords), close=True, dxfattribs={"layer": "OUTER"})

        inner_region = Polygon([
            (-inner_length / 2, -inner_width / 2),
            ( inner_length / 2, -inner_width / 2),
            ( inner_length / 2,  inner_width / 2),
            (-inner_length / 2,  inner_width / 2),
        ])
        grid_span_x = inner_length
        grid_span_y = inner_width
        half_x = inner_length / 2
        half_y = inner_width / 2
    else:
        outer_diameter = float(params["outer_diameter"])
        inner_radius = (outer_diameter / 2) - offset
        if inner_radius <= 0:
            raise ValueError("Offset too large for given diameter.")
        msp.add_circle(center=(0, 0), radius=outer_diameter / 2, dxfattribs={"layer": "OUTER"})
        inner_region = Point(0, 0).buffer(inner_radius, resolution=180)
        grid_span_x = grid_span_y = inner_radius * 2

    def square_geom_centered(s):
        h = s / 2.0
        return Polygon([(-h, -h), (h, -h), (h, h), (-h, h)])

    square_proto = square_geom_centered(hole_size) if hole_shape_choice == "square" else None

    if pattern_choice == "straight":
        nx = math.ceil(grid_span_x / step) + 1
        ny = math.ceil(grid_span_y / step) + 1
        wX = (nx - 1) * step
        wY = (ny - 1) * step
        x0 = -wX / 2
        y0 = -wY / 2
        centers = [(x0 + i * step, y0 + j * step) for i in range(nx) for j in range(ny)]
    else:
        row_step = step * math.sqrt(3) / 2.0
        ny = math.ceil(grid_span_y / row_step) + 1
        nx = math.ceil(grid_span_x / step) + 2
        wX = (nx - 1) * step
        wY = (ny - 1) * row_step
        x0 = -wX / 2
        y0 = -wY / 2
        centers = []
        for j in range(ny):
            y = y0 + j * row_step
            xoff = step / 2.0 if (j % 2 == 1) else 0.0
            for i in range(nx):
                centers.append((x0 + i * step + xoff, y))

    for (x, y) in centers:
        if hole_shape_choice == "circle":
            if shape_choice == "rectangle":
                full_inside = (abs(x) <= half_x - hole_radius) and (abs(y) <= half_y - hole_radius)
            else:
                full_inside = (math.hypot(x, y) <= inner_radius - hole_radius)
            if full_inside:
                msp.add_circle(center=(x, y), radius=hole_radius, dxfattribs={"layer": "HOLES"})
            else:
                if not keep_clipped:
                    continue
                circle_poly = Point(x, y).buffer(hole_radius, resolution=96)
                clipped = circle_poly.intersection(inner_region)
                if clipped.is_empty:
                    continue
                if clipped.geom_type == "Polygon":
                    msp.add_lwpolyline(list(clipped.exterior.coords), close=True,
                                       dxfattribs={"layer": "HOLES-CLIPPED"})
                elif clipped.geom_type == "MultiPolygon":
                    for geom in clipped.geoms:
                        msp.add_lwpolyline(list(geom.exterior.coords), close=True,
                                           dxfattribs={"layer": "HOLES-CLIPPED"})
        else:
            if shape_choice == "rectangle":
                s2 = hole_size / 2.0
                full_inside = (abs(x) <= half_x - s2) and (abs(y) <= half_y - s2)
            else:
                r_sq = (hole_size * math.sqrt(2)) / 2.0
                full_inside = (math.hypot(x, y) <= inner_radius - r_sq)
            if full_inside:
                sq = translate(square_proto, xoff=x, yoff=y)
                msp.add_lwpolyline(list(sq.exterior.coords), close=True, dxfattribs={"layer": "HOLES"})
            else:
                if not keep_clipped:
                    continue
                g = translate(square_proto, xoff=x, yoff=y)
                clipped = g.intersection(inner_region)
                if clipped.is_empty:
                    continue
                if clipped.geom_type == "Polygon":
                    msp.add_lwpolyline(list(clipped.exterior.coords), close=True,
                                       dxfattribs={"layer": "HOLES-CLIPPED"})
                elif clipped.geom_type == "MultiPolygon":
                    for geom in clipped.geoms:
                        msp.add_lwpolyline(list(geom.exterior.coords), close=True,
                                           dxfattribs={"layer": "HOLES-CLIPPED"})

    doc.saveas(save_path)


# ---------------- Tk GUI ----------------
class PerfDXFGUI(tk.Tk):
    def __init__(self, row_gap=8):
        super().__init__()
        self.title("Perf DXF Generator")
        self.resizable(False, False)

        # Set icon from perf.ico in same directory (if present)
        try:
            ico = Path(__file__).resolve().parent / "perf.ico"
            if ico.exists():
                self.iconbitmap(default=str(ico))
        except Exception:
            pass  # icon is optional

        # ===== Variables =====
        self.shape_choice = tk.StringVar(value="rectangle")
        self.outer_length = tk.StringVar(value="24")
        self.outer_width = tk.StringVar(value="18")
        self.outer_diameter = tk.StringVar(value="25.875")

        self.offset = tk.StringVar(value="0.125")

        self.hole_shape_choice = tk.StringVar(value="circle")
        self.hole_size = tk.StringVar(value="1.0")

        self.spacing = tk.StringVar(value="2.0")
        self.pattern_choice = tk.StringVar(value="straight")
        self.keep_clipped = tk.BooleanVar(value=True)

        # Common padding
        self.row_gap = row_gap
        padx = 12

        frm = ttk.Frame(self, padding=(padx, padx, padx, padx))
        frm.grid(row=0, column=0, sticky="nsew")

        r = 0  # row index helper

        # Outer shape
        ttk.Label(frm, text="Outer Shape").grid(row=r, column=0, sticky="w", pady=(0, self.row_gap))
        sh = ttk.Frame(frm)
        sh.grid(row=r, column=1, sticky="w", pady=(0, self.row_gap))
        ttk.Radiobutton(sh, text="Rectangle", variable=self.shape_choice, value="rectangle",
                        command=self._toggle_outer_fields).grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Radiobutton(sh, text="Circle", variable=self.shape_choice, value="circle",
                        command=self._toggle_outer_fields).grid(row=0, column=1, sticky="w")
        r += 1

        # Rectangle dims
        self.rect_frame = ttk.Frame(frm)
        self.rect_frame.grid(row=r, column=0, columnspan=2, sticky="w", pady=(0, self.row_gap))
        ttk.Label(self.rect_frame, text="Length (in)").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(self.rect_frame, textvariable=self.outer_length, width=10).grid(row=0, column=1, sticky="w", padx=(0, 20))
        ttk.Label(self.rect_frame, text="Width (in)").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Entry(self.rect_frame, textvariable=self.outer_width, width=10).grid(row=0, column=3, sticky="w")
        r += 1

        # Circle dim
        self.circ_frame = ttk.Frame(frm)
        self.circ_frame.grid(row=r, column=0, columnspan=2, sticky="w", pady=(0, self.row_gap))
        ttk.Label(self.circ_frame, text="Diameter (in)").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(self.circ_frame, textvariable=self.outer_diameter, width=10).grid(row=0, column=1, sticky="w")
        r += 1

        # Offset
        ttk.Label(frm, text="Offset from edge (in)").grid(row=r, column=0, sticky="w", pady=(0, self.row_gap))
        ttk.Entry(frm, textvariable=self.offset, width=10).grid(row=r, column=1, sticky="w", pady=(0, self.row_gap))
        r += 1

        # Hole shape
        ttk.Label(frm, text="Hole Shape").grid(row=r, column=0, sticky="w", pady=(0, self.row_gap))
        hs = ttk.Frame(frm)
        hs.grid(row=r, column=1, sticky="w", pady=(0, self.row_gap))
        ttk.Radiobutton(hs, text="Circle (Ø)", variable=self.hole_shape_choice, value="circle").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Radiobutton(hs, text="Square", variable=self.hole_shape_choice, value="square").grid(row=0, column=1, sticky="w")
        r += 1

        # Hole size
        ttk.Label(frm, text="Hole size (Ø or square) in").grid(row=r, column=0, sticky="w", pady=(0, self.row_gap))
        ttk.Entry(frm, textvariable=self.hole_size, width=10).grid(row=r, column=1, sticky="w", pady=(0, self.row_gap))
        r += 1

        # Spacing
        ttk.Label(frm, text="Spacing (center-to-center) in").grid(row=r, column=0, sticky="w", pady=(0, self.row_gap))
        ttk.Entry(frm, textvariable=self.spacing, width=10).grid(row=r, column=1, sticky="w", pady=(0, self.row_gap))
        r += 1

        # Pattern
        ttk.Label(frm, text="Pattern").grid(row=r, column=0, sticky="w", pady=(0, self.row_gap))
        pt = ttk.Frame(frm)
        pt.grid(row=r, column=1, sticky="w", pady=(0, self.row_gap))
        ttk.Radiobutton(pt, text="Straight", variable=self.pattern_choice, value="straight").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Radiobutton(pt, text="Staggered (60°)", variable=self.pattern_choice, value="staggered").grid(row=0, column=1, sticky="w")
        r += 1

        # Keep clipped
        ttk.Checkbutton(frm, text="Include clipped holes (on layer HOLES-CLIPPED)",
                        variable=self.keep_clipped).grid(row=r, column=0, columnspan=2, sticky="w", pady=(0, self.row_gap))
        r += 1

        # Buttons
        btns = ttk.Frame(frm)
        btns.grid(row=r, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Generate DXF…", command=self.on_generate).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(btns, text="Quit", command=self.destroy).grid(row=0, column=1)

        self._toggle_outer_fields()

    def _toggle_outer_fields(self):
        is_rect = self.shape_choice.get() == "rectangle"
        # Enable/disable frames
        state_rect = "normal" if is_rect else "disabled"
        state_circ = "disabled" if is_rect else "normal"
        for child in self.rect_frame.winfo_children():
            child.configure(state=state_rect)
        for child in self.circ_frame.winfo_children():
            child.configure(state=state_circ)

    def _float(self, s, name):
        try:
            return float(s)
        except Exception:
            raise ValueError(f"{name} must be a number.")

    def _validate(self):
        params = dict(
            shape_choice=self.shape_choice.get(),
            offset=self._float(self.offset.get(), "Offset"),
            hole_shape_choice=self.hole_shape_choice.get(),
            hole_size=self._float(self.hole_size.get(), "Hole size"),
            spacing=self._float(self.spacing.get(), "Spacing"),
            pattern_choice=self.pattern_choice.get(),
            keep_clipped=self.keep_clipped.get(),
        )
        if params["hole_size"] <= 0: raise ValueError("Hole size must be > 0.")
        if params["spacing"] <= 0: raise ValueError("Spacing (center-to-center) must be > 0.")
        if params["offset"] < 0: raise ValueError("Offset must be ≥ 0.")

        if params["shape_choice"] == "rectangle":
            params["outer_length"] = self._float(self.outer_length.get(), "Length")
            params["outer_width"]  = self._float(self.outer_width.get(), "Width")
            if params["outer_length"] <= 0 or params["outer_width"] <= 0:
                raise ValueError("Length and Width must be > 0.")
            if (params["outer_length"] - 2*params["offset"] <= 0) or (params["outer_width"] - 2*params["offset"] <= 0):
                raise ValueError("Offset too large for given rectangle dimensions.")
        else:
            params["outer_diameter"] = self._float(self.outer_diameter.get(), "Diameter")
            if params["outer_diameter"] <= 0:
                raise ValueError("Diameter must be > 0.")
            if (params["outer_diameter"]/2 - params["offset"] <= 0):
                raise ValueError("Offset too large for given diameter.")
        return params

    def on_generate(self):
        try:
            params = self._validate()
        except Exception as e:
            messagebox.showerror("Invalid input", str(e))
            return

        # Suggest filename
        suggested = f'{params["shape_choice"]}_{params["pattern_choice"]}_{params["hole_shape_choice"]}.dxf'
        path = filedialog.asksaveasfilename(
            title="Save DXF",
            defaultextension=".dxf",
            filetypes=[("DXF files", "*.dxf"), ("All files", "*.*")],
            initialfile=suggested,
        )
        if not path:
            return
        try:
            generate_dxf(params, path)
        except Exception as e:
            messagebox.showerror("Generation error", f"Failed to generate DXF:\n{e}")
            return
        messagebox.showinfo("Success", f"Saved: {path}")


if __name__ == "__main__":
    app = PerfDXFGUI(row_gap=8)  # adjust to taste (e.g., 10–12 for extra breathing room)
    app.mainloop()

