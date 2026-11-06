"""Auditoría independiente: OpenCV (píxeles/homografía) y cuadratura continua.

Ejecutar con Python 3.11, numpy, scipy y opencv-python. No adquiere imágenes.
Las dependencias de auditoría no son necesarias para abrir el visor.
"""
import json
import math
from pathlib import Path

import cv2
import numpy as np
import scipy
from scipy.integrate import quad
from scipy.spatial.transform import Rotation

from model import ARCS, DEFAULTS, DEFAULT_STEP_MM, NOMINAL, SENSOR, simulate, scenarios

PIXELS = np.array([5472, 3648])
PITCH = .0024


def optics(parameters):
    """Intrínsecos ideales y pose cenital según la convención de OpenCV."""
    p = DEFAULTS | parameters
    d = p['camera_z'] - p['calibration_z']
    image_distance = 1 / (1/p['focal'] - 1/d)
    fp = image_distance / PITCH
    center = (PIXELS-1)/2
    k = np.array([[fp, 0, center[0]], [0, fp, center[1]], [0, 0, 1.]])
    rvec = np.array([math.pi, 0., 0.])
    rot = cv2.Rodrigues(rvec)[0]
    trans = -rot @ np.array([p['camera_x'], p['camera_y'], p['camera_z']])
    h = k @ np.column_stack((rot[:, 0], rot[:, 1], rot[:, 2]*p['calibration_z']+trans))
    return k, rvec, trans, np.linalg.inv(h)


def project(points, camera, distortion_pct=0):
    k, rvec, trans, _ = camera
    normalized_corner_squared = float(np.sum((PIXELS/2/k[0,0])**2))
    coeffs = np.array([distortion_pct/100/normalized_corner_squared, 0., 0., 0., 0.])
    return cv2.projectPoints(np.asarray(points, dtype=float), rvec, trans, k, coeffs)[0].reshape(-1, 2)


def unproject(uv, camera):
    rays = np.column_stack((uv, np.ones(len(uv)))) @ camera[3].T
    return rays[:, :2] / rays[:, 2, None]


def matrix_check(parameters):
    r = simulate(parameters, include_points=True)
    p, pts = r['parameters'], np.array(r['points'])
    camera = optics(p)
    uv = project(pts, camera, p['distortion_pct'])
    center = np.array([p['camera_x'],p['camera_y']])
    scale = 1+p['scale_error_pct']/100
    reconstructed = center+(unproject(uv, camera)-center)*scale
    position_residual = float(np.abs(reconstructed-np.array(r['projected'])).max())
    length = np.linalg.norm(np.diff(reconstructed, axis=0), axis=1).sum()
    length_residual = float(abs(length-r['apparent_mm']))
    assert position_residual < 1e-9 and length_residual < 1e-8
    assert bool(np.all((uv >= -.5) & (uv <= PIXELS-.5))) == r['fully_visible']
    # Bordes exteriores de los píxeles, no distancia entre centros extremos.
    frame = unproject(np.array([[-.5, -.5], [5471.5, 3647.5]]), camera)
    np.testing.assert_allclose(np.abs(frame[1]-frame[0]), r['fov_mm'], atol=1e-10, rtol=0)
    np.testing.assert_allclose(np.array(r['fov_mm']) / PIXELS, r['mm_per_px'], atol=1e-12)
    # Anchos transversales: extremos proyectados por OpenCV, no factor escalar.
    diameter_residual = 0.
    for i in np.unique(np.r_[np.linspace(0,len(pts)-1,25,dtype=int),pts[:,2].argmin(),pts[:,2].argmax()]):
        tangent = pts[min(len(pts)-1,i+1)]-pts[max(0,i-1)]
        normal = np.cross([0,0,1],tangent)
        normal = normal/np.linalg.norm(normal) if np.linalg.norm(normal)>1e-12 else np.array([1.,0,0])
        ends = np.array([pts[i]-p['diameter']/2*normal, pts[i]+p['diameter']/2*normal])
        measured = np.linalg.norm(np.diff(unproject(project(ends, camera, p['distortion_pct']), camera), axis=0))*scale
        expected = p['diameter']+r['diameter_errors'][i]
        diameter_residual = max(diameter_residual, float(abs(measured-expected)))
    assert diameter_residual < 1e-10
    return dict(coordinate_residual_mm=position_residual, length_residual_mm=length_residual,
                horizontal_width_residual_mm=diameter_residual, fully_visible=r['fully_visible'])


def continuous_lengths(parameters):
    """Curva analítica XY nominal; integración de la derivada proyectada.

    Independiente del mallado y la suma de cuerdas del simulador.
    Para curvas inextensibles se usa por separado el estudio de convergencia.
    """
    p = DEFAULTS | parameters
    assert p['anchor'] == 'start'
    assert p['shape'] == 'flat' or p['deformation'] == 'fixed_xy' or p['shape'] == 'radial_drop'
    axis = np.array([math.cos(math.radians(p['axis'])), math.sin(math.radians(p['axis'])), 0.])
    rotation = Rotation.from_rotvec(axis*math.radians(p['tilt'])).as_matrix()
    phase, omega = math.radians(p['phase']), 2*math.pi*p['waves']/NOMINAL
    bump0 = math.exp(-(.5/.12)**2)
    rmax = math.hypot(13, 65)
    d = p['camera_z'] - p['calibration_z']
    total_real = total_apparent = quad_error = 0.
    travelled = 0.
    for radius, cx, cy, a, b in ARCS:
        arc_length = radius*math.radians(b-a)

        def integrand(local_s, projected):
            s, t = travelled+local_s, math.radians(a)+local_s/radius
            x, y = cx+radius*math.cos(t), cy+radius*math.sin(t)
            dx, dy = -math.sin(t), math.cos(t)
            z = dz = 0.
            if p['shape'] == 'wave':
                z = p['span']/2*(math.sin(omega*s+phase)-math.sin(phase))
                dz = p['span']/2*omega*math.cos(omega*s+phase)
            elif p['shape'] == 'bump':
                g = math.exp(-((s/NOMINAL-.5)/.12)**2)
                z = p['span']*(g-bump0)/(1-bump0)
                dz = -p['span']*g*2*(s/NOMINAL-.5)/(.12**2*NOMINAL)/(1-bump0)
            elif p['shape'] == 'radial_drop':
                r = math.hypot(x, y)
                z = -p['span']*r/rmax
                dz = -p['span']/rmax*((x*dx+y*dy)/r if r>1e-10 else 1.)
            point = rotation @ np.array([x, y, z]) + np.array([0, 0, p['lift']])
            tangent = rotation @ np.array([dx, dy, dz])
            if not projected:
                return float(np.linalg.norm(tangent))
            delta = point[:2]-np.array([p['camera_x'], p['camera_y']])
            depth = p['camera_z']-point[2]
            derivative = d*(tangent[:2]/depth+delta*tangent[2]/depth**2)
            return float(np.linalg.norm(derivative))

        real, er = quad(lambda s: integrand(s, False), 0, arc_length, epsabs=1e-9, epsrel=1e-11, limit=300)
        apparent, ea = quad(lambda s: integrand(s, True), 0, arc_length, epsabs=1e-9, epsrel=1e-11, limit=300)
        total_real += real
        total_apparent += apparent
        quad_error += er+ea
        travelled += arc_length
    return dict(spatial_mm=total_real, apparent_mm=total_apparent,
                error_mm=total_apparent-total_real, quadrature_error_estimate_mm=quad_error)


def run():
    np.testing.assert_allclose(SENSOR, PIXELS*PITCH, rtol=0, atol=1e-12)
    cases = scenarios()
    rng = np.random.default_rng(20261105)
    for i in range(24):
        cases[f'variado_{i:02}'] = dict(shape=('flat','wave','bump','radial_drop')[i%4],
            focal=float(rng.choice([12,35,75,100])), camera_z=float(rng.uniform(250,2500)),
            camera_x=float(rng.uniform(-150,150)), camera_y=float(rng.uniform(-150,150)),
            calibration_z=float(rng.uniform(-20,20)), lift=float(rng.uniform(-20,20)),
            span=float(rng.uniform(0,20)), waves=int(rng.integers(1,9)), phase=float(rng.uniform(0,360)),
            tilt=float(rng.uniform(-12,12)), axis=float(rng.uniform(0,180)), diameter=float(rng.uniform(1,6)),
            deformation=('fixed_xy','inextensible')[i%2])
    for distortion in (-5,-1,1,5):
        for scale in (-.2,0,.2):
            cases[f'radial_{distortion}_escala_{scale}'] = dict(shape='wave',span=10,
                camera_x=30,camera_y=15,distortion_pct=distortion,scale_error_pct=scale)
    matrix = {name:matrix_check(p) for name,p in cases.items()}
    continuous_cases = {
        'plana_elevada_1mm': dict(shape='flat', lift=1),
        'inclinada_12_grados': dict(shape='flat', tilt=12, axis=37, camera_z=250, camera_x=30, calibration_z=10),
        'ondas_1mm_xy_fijo': dict(shape='wave', span=1, deformation='fixed_xy'),
        'ondas_20mm_8_ciclos_xy_fijo': dict(shape='wave', span=20, waves=8, phase=67, deformation='fixed_xy'),
        'bulto_20mm_xy_fijo': dict(shape='bump', span=20, deformation='fixed_xy'),
        'caida_20mm': dict(shape='radial_drop', span=20),
        'caida_inclinada': dict(shape='radial_drop', span=20, tilt=12, axis=45, camera_z=250),
    }
    continuous = {}
    for name,p in continuous_cases.items():
        exact = continuous_lengths(p)
        coarse, fine = simulate(p), simulate(p, .005)
        residual = abs(coarse['error_mm']-exact['error_mm'])
        fine_residual = abs(fine['error_mm']-exact['error_mm'])
        assert residual < .00003 and fine_residual < .00002, (name, residual, fine_residual)
        continuous[name] = dict(reference=exact, ui_error_mm=coarse['error_mm'],
                                ui_residual_mm=residual, fine_residual_mm=fine_residual)
    convergence = {}
    for shape in ('wave','bump'):
        p = dict(shape=shape, span=20, waves=8, phase=67, tilt=12, axis=33, camera_z=250)
        coarse, fine, previous = simulate(p), simulate(p, .005), simulate(p, .05)
        delta = abs(coarse['error_mm']-fine['error_mm'])
        assert delta < .00003, (shape, delta)
        convergence[shape] = dict(step_mm=[DEFAULT_STEP_MM,.005], difference_error_mm=delta,
            previous_step_mm=.05, previous_difference_error_mm=abs(previous['error_mm']-fine['error_mm']))
    # Contraejemplo: una dimensión inclinada no es un ancho horizontal.
    direction = np.array([math.cos(math.radians(12)), 0, math.sin(math.radians(12))])
    camera = optics(dict(shape='flat'))
    ends = np.array([-2*direction, 2*direction])
    measured = float(np.linalg.norm(np.diff(unproject(project(ends, camera), camera), axis=0)))
    width_limit = dict(dimension_mm=4, tilt_degrees=12, center_z_mm=0,
        horizontal_scale_error_mm=0, inclined_segment_error_mm=measured-4,
        meaning='scale_only_is_not_a_bound_on_cross_section_measurement_error')
    assert abs(measured-4)>.08
    examples = {name:{k:v for k,v in simulate(p, .005).items() if k in
        ('spatial_mm','apparent_mm','error_mm','diameter_error_worst_mm','fov_mm','mm_per_px','fully_visible')}
        for name,p in {'plana_z0':dict(shape='flat'), 'elevada_1mm':dict(shape='flat',lift=1),
        'ondas_iniciales':{}, 'caida_10mm':dict(shape='radial_drop',span=10),
        'lente_75mm_z800':dict(shape='flat',focal=75)}.items()}
    return dict(status='PASS', date='2026-11-05', camera_model='BFS-U3-200S6M-C',
        sensor_pixels=PIXELS.tolist(), pixel_pitch_mm=PITCH, sensor_mm=list(SENSOR),
        dependencies=dict(opencv=cv2.__version__, numpy=np.__version__, scipy=scipy.__version__),
        ui_step_mm=DEFAULT_STEP_MM, matrix_checks=matrix, continuous_checks=continuous,
        inextensible_convergence=convergence, diameter_scope_counterexample=width_limit,
        examples=examples, scope='synthetic_model_only_not_hardware_validation')


if __name__ == '__main__':
    report = run()
    Path(__file__).with_name('audit_results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=report['status'], matrix_cases=len(report['matrix_checks']),
        continuous_cases=len(report['continuous_checks']),
        maximum_matrix_coordinate_residual_mm=max(x['coordinate_residual_mm'] for x in report['matrix_checks'].values()),
        maximum_continuous_error_residual_mm=max(x['ui_residual_mm'] for x in report['continuous_checks'].values()),
        convergence=report['inextensible_convergence'], examples=report['examples']), indent=2))
