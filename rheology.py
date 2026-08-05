"""
Capillary rheology: apparent viscosity of the melt from one cursor measurement.

Pure data + pure functions: no Qt, no DAQ, no config loading. `MainWindow`
calls `apparent_viscosity()` from `_update_cursor_readout()`, so the numbers are
recomputed every time Δt or ΔP changes (a cursor placed, dragged or cleared),
with the geometry constants read from `viscosity` in
`config/daq_config_defaults.json`.

The measurement is the capillary-rheometer one: the melt front travels the
distance Δx between the two cavity-pressure sensors in Δt seconds through a
runner of radius Rc, and ΔP is the pressure difference between those sensors.
Δx and the shear-stress length L are the same span - the sensor separation - so
one constant serves both.

    A   = π Rc²              cross-section        [mm²]  (derived, not stored)
    Q   = A Δx / Δt          volumetric flow rate [mm³/s]
    τ   = ΔP Rc / (2 L)      wall shear stress    [Pa]
    γ̇a  = 4 Q / (π Rc³)      apparent shear rate  [1/s]
    η   = τ / γ̇a             apparent viscosity   [Pa·s]

τ and γ̇a are the standard Hagen-Poiseuille expressions. η is *apparent*: γ̇a is
the Newtonian wall shear rate, with no Rabinowitsch correction applied.

Units are mixed on purpose, to keep the returned numbers in the magnitudes the
operator reads off the plot: Q in mm³/s and Rc in mm (the mm³ cancels in γ̇a),
while τ is SI - ΔP is converted bar → Pa, and the mm → m factors of Rc and L
cancel in the ratio Rc/2L.
"""
import math
from collections import namedtuple

BAR_TO_PA = 1e5

#: Q [mm³/s], tau [Pa], gamma_dot [1/s], eta [Pa·s]
Rheology = namedtuple('Rheology', 'Q tau gamma_dot eta')


def cross_section_mm2(Rc_mm):
    """Runner cross-section A = π Rc² [mm²].

    Derived from Rc rather than stored alongside it, so the two can never
    disagree when the radius is edited in the config.
    """
    return math.pi * float(Rc_mm) ** 2


def apparent_viscosity(dt_s, dp_bar, L_mm, Rc_mm):
    """Q, τ, γ̇a and η from the cursor Δt (s) and ΔP (bar).

    Returns a `Rheology` namedtuple, or None when the inputs cannot produce a
    number: a missing or non-positive Δt (no flow rate), a missing ΔP, or a
    non-positive geometry constant.
    """
    if dt_s is None or dp_bar is None:
        return None
    try:
        dt_s = float(dt_s)
        dp_bar = float(dp_bar)
        L_mm = float(L_mm)
        Rc_mm = float(Rc_mm)
    except (TypeError, ValueError):
        return None
    if dt_s <= 0 or L_mm <= 0 or Rc_mm <= 0:
        return None

    Q = cross_section_mm2(Rc_mm) * (L_mm / dt_s)          # mm³/s
    tau = dp_bar * BAR_TO_PA * Rc_mm / (2.0 * L_mm)       # Pa (mm/mm cancels)
    gamma_dot = 4.0 * Q / (math.pi * Rc_mm ** 3)          # 1/s
    if gamma_dot <= 0:
        return None
    return Rheology(Q, tau, gamma_dot, tau / gamma_dot)
