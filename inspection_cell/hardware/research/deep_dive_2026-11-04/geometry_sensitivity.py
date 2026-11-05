"""Modelos geométricos de investigación; no miden imágenes ni piezas reales.

Ejecutar desde cualquier directorio: py -3.11 -X utf8 geometry_sensitivity.py
Escribe resultados JSON y, si matplotlib está disponible, una figura PNG.
Geometría: arcos de hardware/mechanical/geometry/spiral_sensors.py.
Sin ajuste de propiedades físicas del polímero ni deformación mecánica simulada.
"""
from pathlib import Path
import json
import math

HERE = Path(__file__).resolve().parent
ARCS = [(13, 13, 0, 180, 360), (26, 0, 0, 0, 180),
        (39, 13, 0, 180, 360), (52, 0, 0, 0, 180),
        (65, 13, 0, 180, 270)]
L = sum(r * math.radians(b-a) for r, _, _, a, b in ARCS)


def sample(step):
    points = []
    cumulative = 0.0
    for r, cx, cy, a, b in ARCS:
        angle = math.radians(b-a)
        count = math.ceil(r*angle/step)
        for j in range(count+1):
            if points and j == 0:
                continue
            t = j/count
            theta = math.radians(a)+angle*t
            points.append((cx+r*math.cos(theta), cy+r*math.sin(theta),
                           cumulative+r*angle*t))
        cumulative += r*angle
    return points


def length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def cases(step):
    ref = sample(step)
    xmin = min(p[0] for p in ref)
    xmax = max(p[0] for p in ref)
    angle = math.asin(10/(xmax-xmin))
    return {
        'plana_z0': [(x, y, 0) for x, y, s in ref],
        'elevada_2mm': [(x, y, 2) for x, y, s in ref],
        'elevada_10mm': [(x, y, 10) for x, y, s in ref],
        'inclinada_rigida_10mm': [(x*math.cos(angle), y, (x-xmin)*math.sin(angle))
                                 for x, y, s in ref],
        'un_bulto_z10_xy_fijo': [(x, y, 10*math.sin(math.pi*s/L)**2)
                               for x, y, s in ref],
        'cinco_bultos_z10_xy_fijo': [(x, y, 10*math.sin(5*math.pi*s/L)**2)
                                   for x, y, s in ref],
    }


def measurements(step):
    result = {}
    for name, pts in cases(step).items():
        true = length(pts)
        ortho = length([(x, y) for x, y, z in pts])
        row = {'spatial_mm': true, 'orthographic_mm': ortho,
               'orthographic_minus_spatial_mm': ortho-true,
               'perspective': {}}
        for camera_z in [635, 800, 835, 1500]:
            projected = [(x*camera_z/(camera_z-z), y*camera_z/(camera_z-z))
                         for x, y, z in pts]
            apparent = length(projected)
            row['perspective'][str(camera_z)] = {
                'apparent_mm': apparent,
                'minus_spatial_mm': apparent-true,
                'minus_flat_nominal_mm': apparent-L,
            }
        result[name] = row
    return result


def digital_chain(pixel_mm):
    """8-neighbour chain of quantized curve; not skeletonization of an image.

    Dense rounding first visits orthogonal staircase intermediates. Shorten
    these locally whenever a direct 8-neighbour step reaches a later point.
    Otherwise the result tends towards a 4-neighbour/Manhattan estimator.
    """
    grid = []
    for x, y, s in sample(pixel_mm/20):
        point = (round(x/pixel_mm), round(y/pixel_mm))
        if not grid or point != grid[-1]:
            grid.append(point)
    chain = [grid[0]]
    index = 0
    while index < len(grid)-1:
        following = index+1
        while following+1 < len(grid) and max(
                abs(grid[following+1][axis]-grid[index][axis]) for axis in [0, 1]) <= 1:
            following += 1
        chain.append(grid[following])
        index = following
    return length(chain)*pixel_mm


def main():
    fine = measurements(0.005)
    coarse = measurements(0.01)
    max_change = max(abs(fine[k]['perspective'][z]['apparent_mm']
                         - coarse[k]['perspective'][z]['apparent_mm'])
                     for k in fine for z in fine[k]['perspective'])
    sensor_short = 3648*0.0024
    m = sensor_short/200
    apertures = []
    for n in [2.8, 4, 5.6, 8, 11, 16]:
        airy = 2.44*0.000520*n*(1+m)/m
        defocus = m*5/(n*(1+m))
        apertures.append({'f_number': n, 'airy_object_diameter_mm': airy,
                          'defocus_circle_object_mm_at_5mm': defocus})
    chain = [{'pixel_mm': p, 'chain_mm': digital_chain(p)}
             for p in [0.1, 200/3648, 150/3648, 0.02]]
    for row in chain:
        row['relative_bias_percent'] = 100*(row['chain_mm']/L-1)
    result = {
        'kind': 'synthetic_geometric_models_not_measurements',
        'nominal_centerline_mm': L,
        'coordinate_system': 'mm; optical axis x=y=0; calibration plane z=0; camera at z=Z',
        'assumptions': [
            'pinhole, no lens distortion, no occlusion, no pixel noise',
            'bump examples keep XY fixed and ADD spatial length; not inextensible bends',
            'rigid tilt preserves spatial length',
            'Airy and defocus are blur diameters, not uncertainty or dimensional error',
            'thin lens, pupil magnification one, 520nm, 200mm FOV short side',
            'grid chain is quantization of ideal centerline, not a validated image method',
        ],
        'convergence': {'steps_mm': [0.01, 0.005],
                        'max_perspective_length_change_mm': max_change,
                        'flat_arc_chord_error_mm': fine['plana_z0']['spatial_mm']-L,
                        'tilt_length_preservation_error_mm':
                            fine['inclinada_rigida_10mm']['spatial_mm']-fine['plana_z0']['spatial_mm']},
        'cases': fine,
        'aperture_models': apertures,
        'grid_chain': chain,
        'eight_neighbour_arc_asymptotic_ratio': 8*(math.sqrt(2)-1)/math.pi,
        'uniform_height_examples': [
            {'height_mm': h, 'length_bias_mm': L*h/(800-h), 'width4_bias_mm': 4*h/(800-h)}
            for h in [0.1, 1, 2, 5, 10]
        ],
        'sprue_tip_parallax_examples': [
            {'axis_offset_mm': r, 'sprue_height_mm': 100,
             'camera_distance_mm': 800, 'tip_shift_from_base_mm': r*100/(800-100)}
            for r in [0, 10, 30, 50]
        ],
        'plate_mass_g': {'borofloat_200x200x3': 20*20*0.3*2.23,
                         'pmma_200x200x5': 20*20*0.5*1.19,
                         'pmma_200x200x10': 20*20*1.0*1.19},
        'force_N_for_0_01g': 0.00001*9.80665,
    }
    (HERE/'geometry_sensitivity.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'nominal_mm': L, 'convergence': result['convergence'],
                      'apertures': apertures, 'grid_chain': chain,
                      'cases_Z800': {k: {'true_mm': v['spatial_mm'],
                                        'ortho_minus_true_mm': v['orthographic_minus_spatial_mm'],
                                        **v['perspective']['800']} for k, v in fine.items()}},
                     ensure_ascii=False, indent=2))
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('Figura omitida: matplotlib no disponible; JSON generado.')
        return
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
    height = [i/20 for i in range(201)]
    axes[0].plot(height, [L*h/(800-h) for h in height], label='Recorrido 510,51 mm')
    axes[0].plot(height, [4*h/(800-h) for h in height], label='Ancho 4 mm')
    axes[0].set(xlabel='Elevación uniforme respecto a calibración (mm)',
                ylabel='Sesgo de escala (mm)', title='Perspectiva ideal: cámara a 800 mm')
    axes[0].legend(); axes[0].grid(alpha=.25)
    axes[1].plot([r['f_number'] for r in apertures],
                 [r['airy_object_diameter_mm'] for r in apertures], 'o-', label='Diámetro de Airy ideal')
    axes[1].plot([r['f_number'] for r in apertures],
                 [r['defocus_circle_object_mm_at_5mm'] for r in apertures], 'o-', label='Desenfoque a ±5 mm')
    axes[1].set(xlabel='Número f nominal', ylabel='Diámetro equivalente en objeto (mm)',
                title='FOV 200 mm · 520 nm · modelos de desenfoque')
    axes[1].legend(); axes[1].grid(alpha=.25)
    fig.suptitle('Cálculos ilustrativos; NO son errores medidos ni prestaciones garantizadas', fontsize=12)
    fig.savefig(HERE/'geometry_sensitivity.png', dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main()
