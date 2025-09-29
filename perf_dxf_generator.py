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

# Inputs
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

step = spacing  # always center-to-center

# DXF
doc = ezdxf.new()
doc.header["$INSUNITS"] = 1
msp = doc.modelspace()

# Outer + inner (clipping/reference) shapes
if shape_choice == "rectangle":
    inner_length = outer_length - 2*offset
    inner_width  = outer_width  - 2*offset
    if inner_length <= 0 or inner_width <= 0:
        raise ValueError("Offset too large for given rectangle dimensions.")

    # draw outer
    outer_rect = Polygon([
        (-outer_length/2, -outer_width/2),
        ( outer_length/2, -outer_width/2),
        ( outer_length/2,  outer_width/2),
        (-outer_length/2,  outer_width/2),
    ])
    msp.add_lwpolyline(list(outer_rect.exterior.coords), close=True)

    # inner region for clipping/reference
    inner_rect = Polygon([
        (-inner_length/2, -inner_width/2),
        ( inner_length/2, -inner_width/2),
        ( inner_length/2,  inner_width/2),
        (-inner_length/2,  inner_width/2),
    ])

    grid_span_x = inner_length
    grid_span_y = inner_width
else:
    inner_radius = (outer_diameter/2) - offset
    if inner_radius <= 0:
        raise ValueError("Offset too large for given diameter.")
    msp.add_circle(center=(0,0), radius=outer_diameter/2)
    inner_disk = Point(0,0).buffer(inner_radius, resolution=180)
    grid_span_x = grid_span_y = inner_radius*2

# Square hole geometry (centered) for clipping; circles will not use Shapely
def square_geom_centered(s):
    h = s/2.0
    return Polygon([(-h,-h),(h,-h),(h,h),(-h,h)])

square_proto = square_geom_centered(hole_size) if hole_shape_choice=="square" else None

# Grid of centers
if pattern_choice == "straight":
    nx = math.ceil(grid_span_x/step) + 1
    ny = math.ceil(grid_span_y/step) + 1
    wX = (nx-1)*step
    wY = (ny-1)*step
    x0 = -wX/2.0
    y0 = -wY/2.0
    centers = [(x0 + i*step, y0 + j*step) for i in range(nx) for j in range(ny)]
else:
    row_step = step*math.sqrt(3)/2.0
    ny = math.ceil(grid_span_y/row_step) + 1
    nx = math.ceil(grid_span_x/step) + 2
    wX = (nx-1)*step
    wY = (ny-1)*row_step
    x0 = -wX/2.0
    y0 = -wY/2.0
    centers = []
    for j in range(ny):
        y = y0 + j*row_step
        xoff = step/2.0 if (j % 2 == 1) else 0.0
        for i in range(nx):
            centers.append((x0 + i*step + xoff, y))

# Draw holes
for (x, y) in centers:
    if hole_shape_choice == "circle":
        # Only add if the entire circle fits inside the inner boundary
        if shape_choice == "rectangle":
            if (abs(x) <= inner_length/2 - hole_radius) and (abs(y) <= inner_width/2 - hole_radius):
                msp.add_circle(center=(x, y), radius=hole_radius)
        else:
            if math.hypot(x, y) <= inner_radius - hole_radius:
                msp.add_circle(center=(x, y), radius=hole_radius)
    else:
        # Square: clip to inner boundary to allow edge trims (polylines)
        g = translate(square_proto, xoff=x, yoff=y)
        if shape_choice == "rectangle":
            clipped = g.intersection(inner_rect)
        else:
            clipped = g.intersection(inner_disk)
        if clipped.is_empty:
            continue
        if clipped.geom_type == "Polygon":
            msp.add_lwpolyline(list(clipped.exterior.coords), close=True)
        elif clipped.geom_type == "MultiPolygon":
            for geom in clipped.geoms:
                msp.add_lwpolyline(list(geom.exterior.coords), close=True)

suffix = "staggered" if pattern_choice == "staggered" else "straight"
outname = f"{shape_choice}_{suffix}_grid_trimmed_centered.dxf"
doc.saveas(outname)
print(f"Saved as {outname}")
input("Press Enter to exit...")

