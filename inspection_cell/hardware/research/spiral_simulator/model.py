"""Geometría sintética de Machina. Biblioteca estándar; ninguna conexión a equipos.

Ejecutar: py -3.11 -X utf8 model.py --output scenarios.json
Las longitudes se integran por cuerdas. No se modelan óptica real ni elasticidad.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ARCS = [(13, 13, 0, 180, 360), (26, 0, 0, 0, 180),
        (39, 13, 0, 180, 360), (52, 0, 0, 0, 180),
        (65, 13, 0, 180, 270)]
NOMINAL = sum(r * math.radians(b-a) for r, _, _, a, b in ARCS)
SENSOR = (5472 * 0.0024, 3648 * 0.0024)
DEFAULT_STEP_MM = .01
DEFAULTS = dict(focal=35.0, camera_z=800.0, camera_x=0.0, camera_y=0.0,
                calibration_z=0.0, lift=0.0, shape="wave", span=1.0,
                waves=3, phase=0.0, deformation="inextensible", tilt=0.0,
                axis=90.0, anchor="start", diameter=4.0,
                scale_error_pct=0.0, distortion_pct=0.0)


def distort_local(x, y, corner_radius, percent):
    """Brown k1; porcentaje radial en esquina. Extensión monótona fuera de 2R."""
    if percent == 0:
        return [x, y]
    a, rho = percent/100, math.hypot(x, y)/corner_radius
    factor = 1+a*rho*rho if rho <= 2 else (2*(1+4*a)+(rho-2)*(1+12*a))/rho
    return [x*factor, y*factor]


def nominal_points(step=DEFAULT_STEP_MM):
    result = []
    s0 = 0.0
    for r, cx, cy, a, b in ARCS:
        arc = r * math.radians(b-a)
        n = math.ceil(arc / step)
        for j in range(n+1):
            if result and j == 0:
                continue
            theta = math.radians(a) + j / n * math.radians(b-a)
            result.append((cx+r*math.cos(theta), cy+r*math.sin(theta), s0+arc*j/n))
        s0 += arc
    return result


def path_length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def clip_segment(a, b, half_w, half_h):
    """Liang–Barsky: fracción visible de un segmento en el plano calibrado."""
    dx, dy = b[0]-a[0], b[1]-a[1]
    lo, hi = 0.0, 1.0
    for p, q in [(-dx, a[0]+half_w), (dx, half_w-a[0]),
                 (-dy, a[1]+half_h), (dy, half_h-a[1])]:
        if abs(p) < 1e-15:
            if q < 0:
                return 0.0
            continue
        t = q/p
        if p < 0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
        if lo > hi:
            return 0.0
    return max(0.0, hi-lo)


def simulate(parameters=None, step=DEFAULT_STEP_MM, include_points=False):
    p = DEFAULTS | (parameters or {})
    if p['shape'] not in ('flat', 'wave', 'bump', 'radial_drop'):
        raise ValueError('Forma no válida')
    if p['deformation'] not in ('inextensible', 'fixed_xy'):
        raise ValueError('Deformación no válida')
    if p['anchor'] not in ('start', 'middle', 'minimum'):
        raise ValueError('Referencia de alturas no válida')
    if not 0 < p['diameter'] <= 20:
        raise ValueError('Diámetro fuera de rango')
    if not -1 <= p['scale_error_pct'] <= 1 or not -5 <= p['distortion_pct'] <= 5:
        raise ValueError('Error simulado fuera de rango')
    if p['shape'] == 'radial_drop':
        p.update(deformation='fixed_xy', anchor='start')
    if not step > 0 or not 0 <= p['span'] <= 20 or not 1 <= p['waves'] <= 8:
        raise ValueError('Paso, desnivel o número de ondas fuera de rango')
    zc, zcam, f = p['calibration_z'], p['camera_z'], p['focal']
    distance = zcam-zc
    if f <= 0 or distance <= f:
        raise ValueError('La distancia al plano debe ser mayor que la focal')
    base = nominal_points(step)
    if p['shape'] == 'flat':
        heights = [0.0] * len(base)
    elif p['shape'] == 'radial_drop':
        radii = [math.hypot(x-base[0][0], y-base[0][1]) for x,y,s in base]
        max_radius = max(radii)
        heights = [-p['span']*r/max_radius for r in radii]
    else:
        if p['shape'] == 'wave':
            raw = [math.sin(2*math.pi*p['waves']*s/NOMINAL + math.radians(p['phase'])) for x,y,s in base]
        else:
            raw = [math.exp(-((s/NOMINAL-.5)/.12)**2) for x,y,s in base]
        low, high = min(raw), max(raw)
        heights = [p['span']*((z-low)/(high-low)-.5) for z in raw]

    if p['anchor'] == 'start':
        origin = heights[0]
        heights = [z-origin for z in heights]

    if p['deformation'] == 'inextensible' and p['shape'] != 'flat':
        # Cada segmento conserva exactamente su longitud, a la resolución elegida.
        # La dirección XY procede del nominal; su proyección se acorta al subir/bajar.
        xy = [[base[0][0], base[0][1]]]
        for i in range(1, len(base)):
            dx, dy = base[i][0]-base[i-1][0], base[i][1]-base[i-1][1]
            ds = math.hypot(dx, dy)
            dz = heights[i]-heights[i-1]
            if abs(dz) > ds + 1e-12:
                raise ValueError('Perfil imposible sin estirar: reducir altura u ondas')
            factor = math.sqrt(max(0.0, 1-(dz/ds)**2))
            xy.append([xy[-1][0]+factor*dx, xy[-1][1]+factor*dy])
        for axis in (() if p['anchor'] == 'start' else (0, 1)):
            shift = ((min(q[axis] for q in base)+max(q[axis] for q in base))
                     -(min(q[axis] for q in xy)+max(q[axis] for q in xy)))/2
            for q in xy:
                q[axis] += shift
    else:
        xy = [[x, y] for x,y,s in base]

    angle, azimuth = math.radians(p['tilt']), math.radians(p['axis'])
    ax, ay = math.cos(azimuth), math.sin(azimuth)
    co, si = math.cos(angle), math.sin(angle)
    pivot_x = xy[0][0] if p['anchor'] == 'start' else (min(q[0] for q in xy)+max(q[0] for q in xy))/2
    pivot_y = xy[0][1] if p['anchor'] == 'start' else (min(q[1] for q in xy)+max(q[1] for q in xy))/2
    points = []
    for (x, y), z in zip(xy, heights):
        x, y = x-pivot_x, y-pivot_y
        dot = ax*x+ay*y
        points.append([pivot_x+x*co+ay*z*si+ax*dot*(1-co),
                       pivot_y+y*co-ax*z*si+ay*dot*(1-co),
                       z*co+(ax*y-ay*x)*si])
    zmin, zmax = min(q[2] for q in points), max(q[2] for q in points)
    anchor = points[0][2] if p['anchor']=='start' else (zmin+zmax)/2 if p['anchor']=='middle' else zmin
    for q in points:
        q[2] += p['lift']-anchor
    zmin, zmax = min(q[2] for q in points), max(q[2] for q in points)
    if zmax >= zcam:
        raise ValueError('La pieza no puede alcanzar el centro óptico')

    # Lente delgada enfocada al plano calibrado; distorsión residual sintética opcional.
    image_distance = f*distance/(distance-f)
    fov = [s*distance/image_distance for s in SENSOR]
    mm_per_px = 0.0024*distance/image_distance
    ideal_projected = []
    radial = []
    for x,y,z in points:
        factor = distance/(zcam-z)
        radial.append(factor)
        ideal_projected.append([(x-p['camera_x'])*factor+p['camera_x'],
                          (y-p['camera_y'])*factor+p['camera_y']])
    scale, corner_radius = 1+p['scale_error_pct']/100, math.hypot(*fov)/2
    sensor_projected = []
    for x,y in ideal_projected:
        u,v = distort_local(x-p['camera_x'], y-p['camera_y'], corner_radius, p['distortion_pct'])
        sensor_projected.append([u+p['camera_x'], v+p['camera_y']])
    projected = [[p['camera_x']+(x-p['camera_x'])*scale, p['camera_y']+(y-p['camera_y'])*scale]
                 for x,y in sensor_projected]
    true_length = path_length(points)
    xy_length = path_length([q[:2] for q in points])
    apparent = path_length(projected)
    ideal_apparent, distorted_apparent = path_length(ideal_projected), path_length(sensor_projected)
    visible = 0.0
    for a,b in zip(sensor_projected,sensor_projected[1:]):
        local_a = [a[0]-p['camera_x'], a[1]-p['camera_y']]
        local_b = [b[0]-p['camera_x'], b[1]-p['camera_y']]
        visible += scale*math.dist(a,b)*clip_segment(local_a,local_b,fov[0]/2,fov[1]/2)
    fully_visible = all(abs(q[0]-p['camera_x']) <= fov[0]/2 and
                        abs(q[1]-p['camera_y']) <= fov[1]/2 for q in sensor_projected)
    weighted_z = sum(math.dist(a,b)*(a[2]+b[2])/2 for a,b in zip(points,points[1:]))/true_length
    nominal_polygon = path_length([q[:2] for q in base])
    # Proyectar los extremos de un segmento horizontal transversal local.
    # No se sustituye la distorsión espacial por un factor escalar uniforme.
    diameter_errors, diameter_visible = [], True
    for i,q in enumerate(points):
        a,b = points[max(0,i-1)], points[min(len(points)-1,i+1)]
        dx,dy = b[0]-a[0], b[1]-a[1]
        norm = math.hypot(dx,dy)
        nx,ny = (-dy/norm,dx/norm) if norm>1e-12 else (1.,0.)
        k = radial[i]
        x,y,h = (q[0]-p['camera_x'])*k, (q[1]-p['camera_y'])*k, p['diameter']*k/2
        lo = distort_local(x-h*nx,y-h*ny,corner_radius,p['distortion_pct'])
        hi = distort_local(x+h*nx,y+h*ny,corner_radius,p['distortion_pct'])
        diameter_visible = diameter_visible and all(abs(u)<=fov[0]/2 and abs(v)<=fov[1]/2 for u,v in (lo,hi))
        error = p['diameter']*(k*scale-1) if p['distortion_pct']==0 else math.dist(lo,hi)*scale-p['diameter']
        diameter_errors.append(error)
    diameter_min, diameter_max = min(diameter_errors), max(diameter_errors)
    diameter_worst = diameter_min if abs(diameter_min)>abs(diameter_max) else diameter_max
    result = dict(parameters=p, nominal_analytic_mm=NOMINAL,
                  nominal_polygon_mm=nominal_polygon,
                  spatial_mm=true_length, orthographic_mm=xy_length,
                  apparent_mm=apparent, visible_mm=visible, fully_visible=fully_visible,
                  ideal_apparent_mm=ideal_apparent, distorted_apparent_mm=distorted_apparent,
                  geometry_error_mm=ideal_apparent-true_length,
                  distortion_delta_mm=distorted_apparent-ideal_apparent,
                  scale_delta_mm=apparent-distorted_apparent,
                  error_mm=apparent-true_length, deformation_delta_mm=true_length-nominal_polygon,
                  numerical_nominal_error_mm=nominal_polygon-NOMINAL,
                  projection_loss_mm=xy_length-true_length,
                  perspective_delta_mm=ideal_apparent-xy_length,
                  z_min_mm=zmin, z_max_mm=zmax, z_mean_arclength_mm=weighted_z,
                  z_start_mm=points[0][2], diameter_model='horizontal_transverse_segment',
                  diameter_fully_visible=diameter_visible,
                  diameter_error_min_mm=diameter_min, diameter_error_max_mm=diameter_max,
                  diameter_error_worst_mm=diameter_worst, diameter_error_max_abs_mm=abs(diameter_worst),
                  radial_factor_min=min(radial), radial_factor_max=max(radial),
                  image_distance_mm=image_distance, fov_mm=fov, mm_per_px=mm_per_px,
                  applied_mm_per_px=mm_per_px*scale, distortion_model='synthetic_radial_k1_corner_percent',
                  points_count=len(points), step_mm=step)
    if include_points:
        result.update(points=points, projected=projected, ideal_projected=ideal_projected,
                      sensor_projected=sensor_projected, diameter_errors=diameter_errors)
    return result


def scenarios():
    # Conservar los casos históricos centrados para comparar con el estudio previo.
    flat = dict(shape='flat', span=0, tilt=0, lift=0, anchor='middle')
    tilt = math.degrees(math.asin(1/104))
    return {'plana_z0': flat, 'subida_uniforme_1mm': flat | dict(lift=1),
            'inclinada_centrada_1mm': flat | dict(tilt=tilt, axis=90),
            'inclinada_0_a_1mm': flat | dict(tilt=tilt, axis=90, anchor='minimum'),
            'onda_centrada_1mm_sin_estirar': dict(shape='wave', span=1, waves=3, anchor='middle'),
            'onda_0_a_1mm_sin_estirar': dict(shape='wave', span=1, waves=3, anchor='minimum'),
            'onda_centrada_1mm_xy_fijo': dict(shape='wave', span=1, waves=3, deformation='fixed_xy', anchor='middle'),
            'bulto_centro_fijo_10mm': dict(shape='bump', span=10),
            'onda_centro_fijo_fase_40': dict(shape='wave', span=5, phase=40),
            'caida_radial_1mm': dict(shape='radial_drop', span=1),
            'caida_radial_10mm': dict(shape='radial_drop', span=10),
            'caida_radial_inclinada_elevada': dict(shape='radial_drop', span=10, tilt=5, lift=2),
            'escala_positiva_002pct': flat | dict(scale_error_pct=.02),
            'distorsion_positiva_1pct': flat | dict(distortion_pct=1),
            'distorsion_negativa_1pct': flat | dict(distortion_pct=-1),
            'errores_combinados_onda': dict(shape='wave', span=10, phase=30, scale_error_pct=.1, distortion_pct=-2)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--step', type=float, default=.02)
    args = parser.parse_args()
    report = {'kind': 'synthetic_geometry_not_hardware_measurements',
              'scenarios': {name: simulate(p, args.step) for name,p in scenarios().items()}}
    encoded = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
    if args.output:
        args.output.write_text(encoded, encoding='utf-8')
    else:
        print(encoded)
