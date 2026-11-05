"""Illustrative hardware calculations; no camera model or measured uncertainty.

Run with Python 3. Output is JSON; uses only the standard library.
Distances u are from a thin lens principal plane, NOT its front working distance.
Height examples assume uniform lift of a parallel object in a central projection.
"""

import json
import math


def estimates():
    sensor_h = 3648 * 0.0024
    length = math.pi * (13 + 26 + 39 + 52) + math.pi * 65 / 2
    fields = []
    for side in (150, 200):
        magnification = sensor_h / side
        fields.append({
            "square_field_mm": side,
            "full_field_mm": [1.5 * side, side],
            "mm_per_pixel": side / 3648,
            "pixels_per_0_1_mm": 0.1 * 3648 / side,
            "thin_lens_u_mm_by_focal_length": {
                str(f): f * (1 + 1 / magnification) for f in (25, 35, 50, 75)
            },
        })
    height_cases = []
    for height in (0.1, 1, 10):
        z = 800
        relative_error = height / (z - height)
        height_cases.append({
            "projection_distance_mm": z,
            "uniform_lift_mm": height,
            "relative_scale_error": relative_error,
            "diameter_4_mm_error_mm": 4 * relative_error,
            "length_error_mm": length * relative_error,
        })
    plates = []
    for width, height, thickness in ((200, 200, 5), (200, 200, 10), (300, 300, 10)):
        plates.append({
            "dimensions_mm": [width, height, thickness],
            "pmma_mass_g": width * height * thickness / 1000 * 1.19,
        })
    return {
        "date": "2026-11-04",
        "status": "Analytical estimates, not experimental results",
        "sensor_mm": [5472 * 0.0024, sensor_h],
        "nominal_centerline_length_mm": length,
        "fields": fields,
        "height_examples": height_cases,
        "pmma_plate_examples": plates,
        "difference_sd_for_independent_measurements": math.sqrt(2) * 0.05,
        "pce_1100_cost_estimate_eur_vat_included": round((151.90 + 32.90 + 8.00) * 1.21, 2),
        "pce_5100_cost_estimate_eur_vat_included": round((166.90 + 32.90 + 9.00) * 1.21, 2),
        "cost_note": "PCE shipping is inconsistent across listings; these are scenarios, not confirmed quotes. Serial cable compatibility/cost pending.",
    }


if __name__ == "__main__":
    print(json.dumps(estimates(), indent=2, ensure_ascii=False))
