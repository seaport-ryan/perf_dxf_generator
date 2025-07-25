import ezdxf
import math
from shapely.geometry import Polygon, Point
from shapely.affinity import translate

# --- Get User Input ---
def get_float(prompt, default=None):
    try:
        value = input(prompt)
        if not value.strip() and default is not None:
            return default
        return float(value)
    except ValueError:
        print("Invalid input. Please enter a number.")
        return get_float(prompt, default)

shape_choice = input(
    "Choose outer shape circle (c) or rectangle (r) [circle]: "
).strip().lower()
if not shape_choice:
    shape_choice = "circle"
if shape_choice in {"c", "circle"}:
    shape_choice = "circle"
elif shape_choice in {"r", "rectangle"}:
    shape_choice = "rectangle"
else:
    print("Invalid choice. Defaulting to circle.")
    shape_choice = "circle"

if shape_choice == "rectangle":
    outer_length = get_float("Enter outer length in inches (e.g. 24): ")
    outer_width = get_float("Enter outer width in inches (e.g. 18): ")
else:
    outer_diameter = get_float("Enter outer diameter in inches (e.g. 25.875): ")

offset = get_float("Enter offset from edge in inches (default 0.125): ", default=0.125)
square_size = get_float("Enter square size in inches (e.g. 1): ")
spacing = get_float("Enter spacing between squares in inches (e.g. 0.1875): ")

step = square_size + spacing

# --- DXF Setup ---
doc = ezdxf.new()
msp = doc.modelspace()

if shape_choice == "rectangle":
    inner_length = outer_length - 2 * offset
    inner_width = outer_width - 2 * offset
    if inner_length <= 0 or inner_width <= 0:
        raise ValueError("Offset too large for given rectangle dimensions.")

    outer_rect = Polygon([
        (-outer_length / 2, -outer_width / 2),
        (outer_length / 2, -outer_width / 2),
        (outer_length / 2, outer_width / 2),
        (-outer_length / 2, outer_width / 2),
    ])
    msp.add_lwpolyline(list(outer_rect.exterior.coords), close=True)

    clipping_shape = Polygon([
        (-inner_length / 2, -inner_width / 2),
        (inner_length / 2, -inner_width / 2),
        (inner_length / 2, inner_width / 2),
        (-inner_length / 2, inner_width / 2),
    ])

    grid_span_x = inner_length + square_size
    grid_span_y = inner_width + square_size
else:
    inner_radius = (outer_diameter / 2) - offset
    if inner_radius <= 0:
        raise ValueError("Offset too large for given diameter.")

    msp.add_circle(center=(0, 0), radius=outer_diameter / 2)

    clipping_shape = Point(0, 0).buffer(inner_radius, resolution=180)

    grid_span_x = inner_radius * 2 + square_size
    grid_span_y = grid_span_x

grid_steps_x = math.ceil(grid_span_x / step)
grid_steps_y = math.ceil(grid_span_y / step)

# Actual width and height of the grid of squares (without the extra spacing
# at the far edges) so that the pattern is centered around (0, 0).
grid_width_x = (grid_steps_x - 1) * step + square_size
grid_width_y = (grid_steps_y - 1) * step + square_size

# Starting offset so the pattern is centered around the origin
grid_offset_x = -grid_width_x / 2
grid_offset_y = -grid_width_y / 2

# Loop over grid positions
for i in range(grid_steps_x):
    x = grid_offset_x + i * step
    for j in range(grid_steps_y):
        y = grid_offset_y + j * step
        square = Polygon([
            (0, 0),
            (square_size, 0),
            (square_size, square_size),
            (0, square_size)
        ])
        square_moved = translate(square, xoff=x, yoff=y)
        clipped = square_moved.intersection(clipping_shape)

        if not clipped.is_empty:
            if clipped.geom_type == 'Polygon':
                msp.add_lwpolyline(list(clipped.exterior.coords), close=True)
            elif clipped.geom_type == 'MultiPolygon':
                for geom in clipped.geoms:
                    msp.add_lwpolyline(list(geom.exterior.coords), close=True)

# Save DXF
output_filename = f"{shape_choice}_grid_trimmed_centered.dxf"
doc.saveas(output_filename)
print(f"Saved as {output_filename}")

# Keep window open for user
input("Press Enter to exit...")

