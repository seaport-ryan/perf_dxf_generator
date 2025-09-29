import ezdxf
import math
from shapely.geometry import Polygon, Point
from shapely.affinity import translate

def get_float(prompt, default=None):
    try:
        v = input(prompt)
        if not v.strip() and default is not None:
            return default
        return float(v)
    except ValueError:
        print("Invalid input. Please enter a number.")
        return get_float(prompt, default)

# ---------------- Inputs ----------------
shape_choice = (input("Choose outer shape circle (c) or rectangle (r) [circle]: ").strip().lower() or "circle")
shape_choice = "circle" if shape_choice in {"c","circle"} else "rectangle"

if shape_choice == "rectangle":
    outer_length = get_float("Enter outer length in inches (e.g. 24): ")
    outer_width  = get_float("Enter outer width in inches (e.g. 18): ")
else:
    outer_diameter = get_float("Enter outer diameter in inches (e.g. 25.875): ")

offset = get_float("Enter offset from edge in inches (default 0.125): ", 0.125)

hole_shape_choice = (input("Choose hole shape square (s) or circle (c) [square]: ").strip().lower() or "square")
hole_shape_choice = "square" if hole_shape_choice in {"s","square"} else "circle"

if hole_shape_choice == "square":
    hole_size   = get_float("Enter square size in inches (e.g. 1): ")
    hole_radius = None
else:
    hole_size   = get_float("Enter circle diameter in inches (e.g. 1): ")
    hole_radius = hole_size / 2.0

spacing = get_float("Enter center-to-center spacing between holes in inches (e.g. 2): ")

pattern_choice = (input("Choose pattern straight or staggered [straight]: ").strip().lower() or "straight")
pattern_choice = pattern_choice if pattern_choice in {"straight","staggered"} else "straight"

keep_clipped = (input("Include clipped holes? [y/N]: ").strip().lower() == "y")

step = spacing  # always center-to-center

# ---------------- DXF doc & layers ----------------
doc = ezdxf.new()
doc.header["$INSUNITS"] = 1  # inches
msp = doc.modelspace()

# Ensure layers exist
for lname, color in [("OUTER", 7), ("HOLES", 3), ("HOLES-CLIPPED", 1)]:
    if lname not in doc.layers:
        doc.layers.add(name=lname, color=color)

# ---------------- Outer & inner regions ----------------
if shape_choice == "rectangle":
    inner_length = outer_length - 2*offset
    inner_width  = outer_width  - 2*offset
    if inner_length <= 0 or inner_width <= 0:
        raise ValueError("Offset too large for given rectangle dimensions.")

    # Draw outer perimeter
    outer_rect = Polygon([
        (-outer_length/2, -outer_width/2),
        ( outer_length/2, -outer_width/2),
        ( outer_length/2,  outer_width/2),
        (-outer_length/2,  outer_width/2),
    ])
    msp.add_lwpolyline(list(outer_rect.exterior.coords), close=True, dxfattribs={"layer":"OUTER"})

    # Inner usable region
    inner_region = Polygon([
        (-inner_length/2, -inner_width/2),
        ( inner_length/2, -inner_width/2),
        ( inner_length/2,  inner_width/2),
        (-inner_length/2,  inner_width/2),
    ])

    grid_span_x = inner_length
    grid_span_y = inner_width

    # Quick containment checks for full CIRCLE/SQUARE
    half_x = inner_length/2
    half_y = inner_width/2
else:
    inner_radius = (outer_diameter/2) - offset
    if inner_radius <= 0:
        raise ValueError("Offset too large for given diameter.")
    msp.add_circle(center=(0,0), radius=outer_diameter/2, dxfattribs={"layer":"OUTER"})
    inner_region = Point(0,0).buffer(inner_radius, resolution=180)
    grid_span_x = grid_span_y = inner_radius*2

# ---------------- Hole prototypes (centered at origin) ----------------
def square_geom_centered(s):
    h = s/2.0
    return Polygon([(-h,-h),(h,-h),(h,h),(-h,h)])

square_proto = square_geom_centered(hole_size) if hole_shape_choice=="square" else None

# ---------------- Build center grid ----------------
if pattern_choice == "straight":
    nx = math.ceil(grid_span_x/step) + 1
    ny = math.ceil(grid_span_y/step) + 1
    wX = (nx-1)*step; wY = (ny-1)*step
    x0 = -wX/2; y0 = -wY/2
    centers = [(x0 + i*step, y0 + j*step) for i in range(nx) for j in range(ny)]
else:
    row_step = step*math.sqrt(3)/2.0
    ny = math.ceil(grid_span_y/row_step) + 1
    nx = math.ceil(grid_span_x/step) + 2
    wX = (nx-1)*step; wY = (ny-1)*row_step
    x0 = -wX/2; y0 = -wY/2
    centers = []
    for j in range(ny):
        y = y0 + j*row_step
        xoff = step/2.0 if (j % 2 == 1) else 0.0
        for i in range(nx):
            centers.append((x0 + i*step + xoff, y))

# ---------------- Draw holes ----------------
for (x, y) in centers:
    if hole_shape_choice == "circle":
        # Full-circle containment test
        if shape_choice == "rectangle":
            full_inside = (abs(x) <= half_x - hole_radius) and (abs(y) <= half_y - hole_radius)
        else:
            full_inside = (math.hypot(x, y) <= inner_radius - hole_radius)

        if full_inside:
            msp.add_circle(center=(x, y), radius=hole_radius, dxfattribs={"layer":"HOLES"})
        else:
            if not keep_clipped:
                continue
            # Clip and draw as polyline(s)
            circle_poly = Point(x, y).buffer(hole_radius, resolution=96)
            clipped = circle_poly.intersection(inner_region)
            if clipped.is_empty:
                continue
            if clipped.geom_type == "Polygon":
                msp.add_lwpolyline(list(clipped.exterior.coords), close=True,
                                   dxfattribs={"layer":"HOLES-CLIPPED"})
            elif clipped.geom_type == "MultiPolygon":
                for geom in clipped.geoms:
                    msp.add_lwpolyline(list(geom.exterior.coords), close=True,
                                       dxfattribs={"layer":"HOLES-CLIPPED"})
    else:
        # Squares: check full containment (axis-aligned makes this easy)
        if shape_choice == "rectangle":
            s2 = hole_size/2.0
            full_inside = (abs(x) <= half_x - s2) and (abs(y) <= half_y - s2)
        else:
            # If the square's circumradius is inside the circle it's fully inside
            # circumradius of square = (s*sqrt(2))/2
            r_sq = (hole_size*math.sqrt(2))/2.0
            full_inside = (math.hypot(x, y) <= inner_radius - r_sq)

        if full_inside:
            # draw as a closed LWPolyline on HOLES layer
            sq = translate(square_proto, xoff=x, yoff=y)
            msp.add_lwpolyline(list(sq.exterior.coords), close=True, dxfattribs={"layer":"HOLES"})
        else:
            if not keep_clipped:
                continue
            g = translate(square_proto, xoff=x, yoff=y)
            clipped = g.intersection(inner_region)
            if clipped.is_empty:
                continue
            if clipped.geom_type == "Polygon":
                msp.add_lwpolyline(list(clipped.exterior.coords), close=True,
                                   dxfattribs={"layer":"HOLES-CLIPPED"})
            elif clipped.geom_type == "MultiPolygon":
                for geom in clipped.geoms:
                    msp.add_lwpolyline(list(geom.exterior.coords), close=True,
                                       dxfattribs={"layer":"HOLES-CLIPPED"})

# ---------------- Save ----------------
suffix = "staggered" if pattern_choice == "staggered" else "straight"
outname = f"{shape_choice}_{suffix}_grid_trimmed_centered.dxf"
doc.saveas(outname)
print(f"Saved as {outname}")
input("Press Enter to exit...")

