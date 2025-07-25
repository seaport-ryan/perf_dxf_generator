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

outer_diameter = get_float("Enter outer diameter in inches (e.g. 25.875): ")
offset = get_float("Enter offset from edge in inches (default 0.125): ", default=0.125)
square_size = get_float("Enter square size in inches (e.g. 1): ")
spacing = get_float("Enter spacing between squares in inches (e.g. 0.1875): ")

# --- Derived Parameters ---
inner_radius = (outer_diameter / 2) - offset
step = square_size + spacing

# --- DXF Setup ---
doc = ezdxf.new()
msp = doc.modelspace()

# Draw outer circle
msp.add_circle(center=(0, 0), radius=outer_diameter / 2)

# Create inner clipping circle using shapely
circle = Point(0, 0).buffer(inner_radius, resolution=180)

# Calculate grid extents
grid_span = inner_radius * 2 + square_size
grid_steps = math.ceil(grid_span / step)
grid_width = grid_steps * step
grid_offset = -grid_width / 2  # Center at (0, 0)

# Loop over grid positions
x = grid_offset
while x < -grid_offset + grid_width:
    y = grid_offset
    while y < -grid_offset + grid_width:
        square = Polygon([
            (0, 0),
            (square_size, 0),
            (square_size, square_size),
            (0, square_size)
        ])
        square_moved = translate(square, xoff=x, yoff=y)
        clipped = square_moved.intersection(circle)

        if not clipped.is_empty:
            if clipped.geom_type == 'Polygon':
                msp.add_lwpolyline(list(clipped.exterior.coords), close=True)
            elif clipped.geom_type == 'MultiPolygon':
                for geom in clipped.geoms:
                    msp.add_lwpolyline(list(geom.exterior.coords), close=True)
        y += step
    x += step

# Save DXF
output_filename = "circle_grid_trimmed_centered.dxf"
doc.saveas(output_filename)
print(f"Saved as {output_filename}")

# Keep window open for user
input("Press Enter to exit...")

