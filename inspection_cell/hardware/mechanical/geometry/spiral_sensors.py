"""Plot the spiral and sensor positions. All distances are in millimetres.

Install dependencies: python -m pip install numpy matplotlib
Run: python spiral_sensors.py

Sensor distances follow the spiral centerline from its inner endpoint.
Spiral width and sensor diameters are defined in data coordinates (mm).
"""

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Wedge

SPIRAL_WIDTH_MM = 3.0
TEMPERATURE_DIAMETER_MM = 4.0
PRESSURE_DIAMETER_MM = 2.5

# radius, center_x, center_y, start_angle_deg, end_angle_deg, color
# Each arc has a unique color. The final R65 arc is a quarter circle.
ARCS = [
    (13.0, 13.0, 0.0, 180.0, 360.0, "#8E44AD"),  # purple
    (26.0,  0.0, 0.0,   0.0, 180.0, "#00897B"),  # teal
    (39.0, 13.0, 0.0, 180.0, 360.0, "#D88A00"),  # orange
    (52.0,  0.0, 0.0,   0.0, 180.0, "#686868"),  # grey
    (65.0, 13.0, 0.0, 180.0, 270.0, "#8C564B"),  # brown
]

# Successive distances: start -> T1 -> P1 -> P2 -> T2.
SENSOR_STEPS = [
    ("T1", 31.35),
    ("P1", 23.08),
    ("P2", 97.14),
    ("T2", 30.29),
]

TEMPERATURE_COLOR = "#D62728"
PRESSURE_COLOR = "#0057D9"

# Annotation positions only: changing these does not move the sensor markers.
SENSOR_LABELS = {
    "T1": (35.0, -6.0),
    "P1": (11.0, 12.0),
    "P2": (-28.0, -33.0),
    "T2": (27.0, -49.0),
}

# Radius dimension: ray angle, ray extension length, label position.
DIMENSIONS = [
    (-90.0, 20.0, (13.0, -24.0)),  # R13
    ( 78.0, 37.0, (8.0,   39.5)),  # R26
    (-30.0, 55.0, (64.0, -30.5)),  # R39
    (140.0, 69.0, (-58.0, 49.5)),  # R52
    (-155.0, 81.0, (-64.0, -38.0)),  # R65
]


def arc_length(arc):
    """Length of one circular arc, in mm."""
    radius, _, _, start_deg, end_deg, _ = arc
    return radius * np.deg2rad(end_deg - start_deg)


def point_at_length(distance):
    """Return x, y, arc radius at an exact distance along the centerline."""
    total_length = sum(arc_length(arc) for arc in ARCS)
    if not 0.0 <= distance <= total_length:
        raise ValueError(f"Distance must be between 0 and {total_length:.3f} mm")

    travelled = 0.0
    for arc in ARCS:
        radius, cx, cy, start_deg, _, _ = arc
        length = arc_length(arc)
        if distance <= travelled + length + 1e-9:
            local_distance = np.clip(distance - travelled, 0.0, length)
            theta = np.deg2rad(start_deg) + local_distance / radius
            return (cx + radius * np.cos(theta),
                    cy + radius * np.sin(theta), radius)
        travelled += length
    raise RuntimeError("Could not locate point on spiral")


def draw_dimension(ax, arc, dimension):
    """Draw the radius line, arrow and label in the arc's own color."""
    radius, cx, cy, _, _, color = arc
    angle_deg, extension, label_position = dimension
    direction = np.array([np.cos(np.deg2rad(angle_deg)),
                          np.sin(np.deg2rad(angle_deg))])
    center = np.array([cx, cy])
    tip = center + radius * direction
    end = center + extension * direction

    ax.plot([cx, end[0]], [cy, end[1]], color=color, lw=0.9, zorder=1)
    arrow = ax.annotate("", xy=tip, xytext=tip + 6.0 * direction,
                        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.0,
                                        mutation_scale=12, shrinkA=0, shrinkB=0),
                        zorder=4)
    # Keep the same-color arrow visible where it reaches the band centerline.
    arrow.arrow_patch.set_path_effects([
        pe.Stroke(linewidth=2.5, foreground="white"), pe.Normal(),
    ])
    ax.text(*label_position, f"R{radius:g}", color=color,
            fontsize=13, ha="center", va="center", zorder=5,
            bbox=dict(facecolor="white", edgecolor="none", pad=2.0))


def draw_spiral_arc(ax, arc):
    """Draw a filled band of exactly SPIRAL_WIDTH_MM around its centerline."""
    radius, cx, cy, start_deg, end_deg, color = arc
    ax.add_patch(Wedge(
        center=(cx, cy),
        r=radius + SPIRAL_WIDTH_MM / 2.0,
        theta1=start_deg,
        theta2=end_deg,
        width=SPIRAL_WIDTH_MM,
        facecolor=color,
        edgecolor="none",
        linewidth=0,
        zorder=3,
    ))


def draw_end_caps(ax):
    """Round only the two open ends; adjacent arc bands already join tangentially."""
    for arc, angle_index in ((ARCS[0], 3), (ARCS[-1], 4)):
        radius, cx, cy, _, _, color = arc
        theta = np.deg2rad(arc[angle_index])
        center = (cx + radius * np.cos(theta), cy + radius * np.sin(theta))
        ax.add_patch(Circle(
            center, radius=SPIRAL_WIDTH_MM / 2.0,
            facecolor=color, edgecolor="none", linewidth=0, zorder=3,
        ))


def main():
    plt.rcParams["svg.fonttype"] = "none"  # Keep SVG text editable.
    fig, ax = plt.subplots(figsize=(10, 10))
    fig.subplots_adjust(left=0.03, right=0.97, bottom=0.09, top=0.88)
    ax.set_aspect("equal")
    ax.set_xlim(-78, 78)
    ax.set_ylim(-76, 64)
    ax.axis("off")

    fig.suptitle("Spiral with sensor positions", y=0.96, fontsize=19)
    fig.text(0.5, 0.921, "Centerline radii and cumulative distances in mm",
             ha="center", fontsize=11, color="#667580")

    ax.plot([-63, 64], [0, 0], color="#D4DADE", lw=0.8,
            linestyle="-.", zorder=0)

    for arc, dimension in zip(ARCS, DIMENSIONS):
        draw_spiral_arc(ax, arc)
        draw_dimension(ax, arc, dimension)
    draw_end_caps(ax)

    for cx in (0.0, 13.0):
        ax.plot([cx - 1.5, cx + 1.5], [0, 0], color="#9BA5AD", lw=0.7)
        ax.plot([cx, cx], [-1.5, 1.5], color="#9BA5AD", lw=0.7)

    print("Point   From previous   From start        x          y       Arc")
    distance = 0.0
    for name, increment in SENSOR_STEPS:
        distance += increment
        x, y, radius = point_at_length(distance)
        is_temperature = name.startswith("T")
        color = TEMPERATURE_COLOR if is_temperature else PRESSURE_COLOR
        diameter = (TEMPERATURE_DIAMETER_MM if is_temperature
                    else PRESSURE_DIAMETER_MM)

        marker = Circle((x, y), radius=diameter / 2.0,
                        facecolor=color, edgecolor="none", linewidth=0, zorder=7)
        ax.add_patch(marker)
        ax.annotate(f"{name}\n{distance:.2f} mm", xy=(x, y),
                    xytext=SENSOR_LABELS[name], textcoords="data",
                    fontsize=10, fontweight="bold", color=color,
                    ha="center", va="center", zorder=8,
                    bbox=dict(facecolor="white", edgecolor="none", pad=2.0),
                    arrowprops=dict(arrowstyle="-", color=color, lw=1.0,
                                    shrinkA=3, shrinkB=0, patchB=marker))
        print(f"{name:<5} {increment:12.2f} {distance:12.2f}"
              f" {x:10.4f} {y:10.4f}    R{radius:g}")

    # Legend symbols are illustrative; the plotted sensor circles use mm.
    handles = [Line2D([], [], linestyle="none", marker="o",
                      markersize=9 * diameter / TEMPERATURE_DIAMETER_MM,
                      markerfacecolor=color, markeredgewidth=0,
                      markeredgecolor="none", label=label)
               for color, diameter, label in [
                   (TEMPERATURE_COLOR, TEMPERATURE_DIAMETER_MM,
                    f"Temperature: T1, T2 (Ø{TEMPERATURE_DIAMETER_MM:g} mm)"),
                   (PRESSURE_COLOR, PRESSURE_DIAMETER_MM,
                    f"Pressure: P1, P2 (Ø{PRESSURE_DIAMETER_MM:g} mm)"),
               ]]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.035),
               ncol=2, frameon=False, fontsize=11)
    fig.text(0.5, 0.018,
             f"Spiral width: {SPIRAL_WIDTH_MM:g} mm. Distance starts at the inner endpoint.",
             ha="center", fontsize=9, color="#667580")

    for suffix in ("png", "svg"):
        output = Path.cwd() / f"spiral_sensors.{suffix}"
        fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
        print(f"Saved: {output}")

    print(f"Total spiral length: {sum(arc_length(arc) for arc in ARCS):.2f} mm")
    plt.show()


if __name__ == "__main__":
    main()
