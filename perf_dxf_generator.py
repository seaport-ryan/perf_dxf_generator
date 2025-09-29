import ezdxf
import math
from shapely.geometry import Polygon, Point
from shapely.affinity import translate

# --- Helpers ---
def get_float(prompt, default=None):
    try:
        value = input(prompt)
        if not value.strip() and default is not None:
            return default
        return float(value)
    except ValueError:
        print("Invalid input. Please enter a number.")
        return get_float(prompt, default)

# --- Inputs ---
shape_choice = input("Choose outer shape circle (c) or rectangle (r) [circle]: ").strip().lower() or "circle"
shape_choice = "circle" if shape_choice in {"c", "circle"} else "rectangle"

if shape_choice == "rectangle":
    outer_length = get_float("Enter outer length in inches (e.g. 24): ")
    outer_width = get_float("Enter outer width in inches (e.g. 18): ")
else:
    outer_diameter = get_float("Enter outer diameter in inches (e.g. 25.875): ")

offset = get_float("Enter offset from edge in inches (default 0.125): ", default=0.125)

hole_shape_choice = input("Choose hole shape square (s) or circle (c) [square]: ").strip().lower() or "square"
hole_shape_choice = "square" if hole_shape_choice in {"s", "square"} else "circle"

if hole_shape_choice == "square":
    hole_size = get_float("Enter square size in inches (e.g. 1): ")
    hole_radius = None
else:
    hole_size = get_float("Enter circle diameter in inches (e.g. 1): ")
    hole_radius = hole_size / 2.0

# IMPORTANT: spacing is CENTER-TO-CENTER now
spacing = get_float("Enter center-to-center spacing between holes in inches (e.g. 2): ")

pattern_choice = input("Choose pattern straight or staggered [straight]: ").strip().lower() or "straight"
pattern_choice = pattern_choice if pattern_choice in {"straight", "staggered"} else "straight"

# Center-to-center step
step = spacing

# --- DXF setup ---
doc = ezdxf.new()
doc.header["$INSUNITS"] = 1  # inches
msp = doc.modelspace()

# Draw outer and define inner clipping shape
if shape_choice == "rectangle":
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
    msp.add_lwpolyline(list(outer_rect.exterior.coords), close=True)

    clipping_shape = Polygon([
        (-inner_length / 2, -inner_width / 2),
        ( inner_length / 2, -inner_width / 2),
        ( inner_length / 2,  inner_width / 2),
        (-inner_length / 2,  inner_width / 2),
    ])

    # For center grid coverage
    grid_span_x = inner_length
    grid_span_y = inner_width

else:
    inner_radius = (outer_diameter / 2) - offset
    if inner_radius <= 0:
        raise ValueError("Offset too large for given diameter.")

    msp.add_circle(center=(0, 0), radius=outer_diameter / 2)
    clipping_shape = Point(0, 0).buffer(inner_radius, resolution=180)

    # For center grid coverage (diameter of usable area)
    grid_span_x = inner_radius * 2
    grid_span_y = grid_span_x

# Hole geometry centered at (0,0)
def hole_geom_centered():
    if hole_shape_choice == "square":
        s = hole_size / 2.0
        return Polygon([(-s, -s), ( s, -s), ( s,  s), (-s,  s)])
    else:
        return Point(0.0, 0.0).buffer(hole_radius, resolution=180)

hole_proto = hole_geom_centered()

# --- Grid calculations (based on HOLE CENTERS) ---
if pattern_choice == "straight":
    # number of steps to cover span; +1 to ensure edges are filled
    nx = math.ceil(grid_span_x / step) + 1
    ny = math.ceil(grid_span_y / step) + 1

    width_x = (nx - 1) * step
    width_y = (ny - 1) * step
    x0 = -width_x / 2.0
    y0 = -width_y / 2.0

    positions = [(x0 + i * step, y0 + j * step) for i in range(nx) for j in range(ny)]

else:  # staggered (hex/triangular lattice)
    row_step = step * math.sqrt(3) / 2.0  # vertical distance between rows
    ny = math.ceil(grid_span_y / row_step) + 1
    nx = math.ceil(grid_span_x / step) + 2  # +2 to cover half-step on odd rows

    width_x = (nx - 1) * step
    width_y = (ny - 1) * row_step
    x_base = -width_x / 2.0
    y_base = -width_y / 2.0

    positions = []
    for j in range(ny):
        y = y_base + j * row_step
        x_offset = (step / 2.0) if (j % 2 == 1) else 0.0
        for i in range(nx):
            x = x_base + i * step + x_offset
            positions.append((x, y))

# --- Place holes, clip to inner boundary, and draw ---
for (x, y) in positions:
    g = translate(hole_proto, xoff=x, yoff=y)
    clipped = g.intersection(clipping_shape)
    if clipped.is_empty:
        continue
    if clipped.geom_type == "Polygon":
        msp.add_lwpolyline(list(clipped.exterior.coords), close=True)
    elif clipped.geom_type == "MultiPolygon":
        for geom in clipped.geoms:
            msp.add_lwpolyline(list(geom.exterior.coords), close=True)

# --- Save ---
suffix = "staggered" if pattern_choice == "staggered" else "straight"
outname = f"{shape_choice}_{suffix}_grid_trimmed_centered.dxf"
doc.saveas(outname)
print(f"Saved as {outname}")

input("Press Enter to exit...")

