"""Synthetic geometry study, NOT inspection software or a camera calibration.

Run from any directory with Python, numpy, scipy, opencv and matplotlib.
Outputs are written beside this script. No camera or network access.
The distortion and tilt below are invented to isolate mathematical effects.
"""

from pathlib import Path
import json
import platform

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import RBFInterpolator
import scipy


OUT = Path(__file__).resolve().parent
LENGTH = 510.508806
WIDTH = 4.0
Z = 800.0
SCALE = 200.0 / 3648.0
K = np.array([[Z / SCALE, 0, 2735.5], [0, Z / SCALE, 1823.5], [0, 0, 1.0]])
D = np.array([0.04, 0, 0, 0, 0.0])  # invented, NOT Computar coefficients
RX = cv2.Rodrigues(np.array([np.deg2rad(1.5), 0.0, 0.0]))[0]
RY = cv2.Rodrigues(np.array([0.0, np.deg2rad(3.0), 0.0]))[0]
R = RY @ RX
RV = cv2.Rodrigues(R)[0]
T = np.array([0.0, 0.0, Z])


def grid(xs, ys):
    x, y = np.meshgrid(xs, ys)
    return np.column_stack([x.ravel(), y.ravel()])


def project(xy, z=0.0):
    obj = np.column_stack([xy, np.broadcast_to(z, len(xy))])
    return cv2.projectPoints(obj, RV, T, K, D)[0].reshape(-1, 2)


def apply_h(points, h):
    p = np.column_stack([points, np.ones(len(points))]) @ h.T
    return p[:, :2] / p[:, 2:]


def stats(values):
    return dict(rms_mm=float(np.sqrt(np.mean(values ** 2))),
                maximum_mm=float(np.max(np.abs(values))))


def main():
    # Training and validation positions are distinct; no detection noise here.
    train = grid(np.linspace(-140, 140, 15), np.linspace(-90, 90, 11))
    test = grid(np.linspace(-132.7, 132.7, 42), np.linspace(-82.3, 82.3, 30))
    p, q = project(train), project(test)
    assert len(set(map(tuple, train)) & set(map(tuple, test))) == 0
    assert np.all((q >= 0) & (q < np.array([5472, 3648])))

    # Fit similarity: X=a*u-b*v+tx; Y=b*u+a*v+ty.
    pc = p - K[:2, 2]
    A = np.zeros((2 * len(p), 4))
    A[0::2] = np.column_stack([pc[:, 0], -pc[:, 1], np.ones(len(p)), np.zeros(len(p))])
    A[1::2] = np.column_stack([pc[:, 1], pc[:, 0], np.zeros(len(p)), np.ones(len(p))])
    a, b, tx, ty = np.linalg.lstsq(A, train.ravel(), rcond=None)[0]
    qc = q - K[:2, 2]
    sim = qc @ np.array([[a, b], [-b, a]]) + [tx, ty]
    h_fit = cv2.findHomography(p, train, method=0)[0]
    hom = apply_h(q, h_fit)

    # An illustrative empirical map, not a recommended production interpolator.
    empirical = RBFInterpolator(pc / 3000.0, train, kernel="thin_plate_spline", degree=1)
    direct = empirical(qc / 3000.0)

    # Ideal benchmark using the true, known simulation parameters, NOT estimates.
    q_ideal = cv2.undistortPoints(q.reshape(-1, 1, 2), K, D, P=K).reshape(-1, 2)
    h_true = K @ np.column_stack([R[:, 0], R[:, 1], T])
    exact = apply_h(q_ideal, np.linalg.inv(h_true))
    assert np.max(np.abs(exact - test)) < 1e-6

    names = ["Escala global + giro", "Homografia", "Mapa 2D interpolado", "Modelo exacto conocido"]
    estimates = [sim, hom, direct, exact]
    errors = [np.linalg.norm(v - test, axis=1) for v in estimates]
    table = {name: stats(err) for name, err in zip(names, errors)}

    # Pure uniform scale ambiguity: rescaling target and translation leaves pixels unchanged.
    factor = 100.0 / 100.02
    obj = np.column_stack([train, np.zeros(len(train))])
    p_scaled = cv2.projectPoints(obj * factor, RV, T * factor, K, D)[0].reshape(-1, 2)
    ambiguity_px = float(np.max(np.linalg.norm(p_scaled - p, axis=1)))
    assert ambiguity_px < 1e-8

    heights = np.array([0.1, 1, 2, 10.0])
    hrows = [dict(height_mm=float(h), width_error_mm=float(WIDTH*h/(Z-h)),
                  length_error_mm=float(LENGTH*h/(Z-h))) for h in heights]
    lens_angles = {str(f): dict(horizontal_deg=float(np.rad2deg(2*np.arctan(13.1328/(2*f)))),
                                vertical_deg=float(np.rad2deg(2*np.arctan(8.7552/(2*f))))) for f in [35, 75]}
    result = dict(
        status="synthetic_only_no_hardware_validation",
        assumptions=dict(image_size_px=[5472,3648], nominal_field_mm=[300,200], z_mm=Z,
                         tilt_degrees=[1.5,3], distortion=D.tolist(), detection_noise_px=0,
                         training_points=len(train), independent_test_points=len(test),
                         warning="Invented distortion; exact model is an oracle, not a fitted result."),
        coordinate_errors=table,
        scale_ambiguity=dict(actual_reference_mm=100.02, assigned_reference_mm=100,
                             maximum_pixel_change=ambiguity_px,
                             resulting_length_error_mm=LENGTH*(factor-1),
                             resulting_width_error_mm=WIDTH*(factor-1)),
        uniform_height_examples=hrows,
        height_for_0_1mm_length_error_mm=0.1*Z/(LENGTH+0.1),
        lens_angular_estimates=lens_angles,
        versions=dict(python=platform.python_version(),numpy=np.__version__,opencv=cv2.__version__,scipy=scipy.__version__),
    )
    (OUT / "calibration_sensitivity.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")

    fig, axes = plt.subplots(2,2,figsize=(12,8),layout="constrained")
    vmax = max(float(np.max(e)) for e in errors[:2])
    for ax, title, err in zip(axes.flat[:2], names[:2], errors[:2]):
        sc=ax.scatter(test[:,0],test[:,1],c=err,s=10,vmin=0,vmax=vmax,cmap="viridis")
        ax.set(title=title+" | error de coordenada",xlabel="X real (mm)",ylabel="Y real (mm)")
        ax.set_aspect("equal");fig.colorbar(sc,ax=ax,label="Error (mm)",shrink=.8)
    ax=axes[1,0]
    vals=[table[n]["rms_mm"] for n in names[:3]]
    ax.bar(["Escala", "Homografia", "Mapa 2D"],vals,color=["#386cb0","#7fc97f","#fdc086"])
    ax.set(ylabel="RMS de coordenadas (mm)",title=f"{len(test)} puntos reservados; sin ruido")
    for i,v in enumerate(vals):ax.text(i,v,f"{v:.5f}",ha="center",va="bottom")
    ax.set_ylim(0,max(vals)*1.3)
    ax=axes[1,1];h=np.linspace(0,2,201)
    ax.plot(h,LENGTH*h/(Z-h),label="Recorrido 510,51 mm",color="#386cb0")
    ax.plot(h,WIDTH*h/(Z-h),label="Ancho 4 mm",color="#e6550d")
    ax.axhline(.1,color="black",ls="--",lw=.8,label="0,1 mm orientativos")
    ax.set(xlabel="Desplazamiento uniforme hacia camara (mm)",ylabel="Error (mm)",
           title="Altura no corregida; plano perpendicular a 800 mm")
    ax.legend(fontsize=8)
    fig.suptitle("Ejemplo sintetico: calibrar el plano no elimina el error de altura",fontsize=14)
    fig.savefig(OUT / "calibration_sensitivity.png",dpi=170)
    plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
