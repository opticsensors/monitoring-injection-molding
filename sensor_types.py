"""
Sensor-type registry - the single source of truth for how each channel is
labelled, converted, coloured and where it is plotted.

Pure data + pure helper functions: no Qt, no DAQ, no side effects. Imported by
main.py (MainWindow, GraphThread) and config_window.py (DaqConfigWindow).

Every channel is assigned one sensor type. The registry below drives: the
dropdown label, the tooltip, the physical unit and the "category" that decides
conversion, colouring and which plot/axis the signal lands on.

category:
  'temp'    -> Mold tab, LEFT axis   (Temperature)
  'moldP'   -> Mold tab, RIGHT axis  (mould cavity Pressure)
  'machine' -> Machine tab           (P_machine / vel_screw / pos_screw)
  'trigger' -> not plotted as a line; drives cycles + arrows on both tabs
  None      -> channel unused
"""

SENSOR_TYPES = {
    'none':           {'label': 'none',              'category': None,      'unit': '',
                       'tooltip': 'Channel not used.'},
    'T_futaba':       {'label': 'T_futaba',          'category': 'temp',    'unit': '°C',
                       'tooltip': 'Temperature sensor (Futaba). Raw 0-10 V mapped to °C.'},
    'P_kistler':      {'label': 'P_kistler',         'category': 'moldP',   'unit': 'bar',
                       'tooltip': 'Cavity pressure sensor (Kistler). Raw 0-10 V mapped to bar.'},
    'P_machine':      {'label': 'P_machine',         'category': 'machine', 'unit': 'bar',
                       'tooltip': 'Machine signal - Presión específica inyección (specific injection pressure) → bar.'},
    'vel_screw':      {'label': 'vel_screw',         'category': 'machine', 'unit': 'mm/s',
                       'tooltip': 'Machine signal - Veloc. inyección (injection speed) → mm/s.'},
    'pos_screw':      {'label': 'pos_screw',         'category': 'machine', 'unit': 'mm',
                       'tooltip': 'Machine signal - Posición husillo (screw position) → mm.'},
    'Inductive':      {'label': 'Inductive',          'category': 'trigger', 'unit': '',
                       'tooltip': 'Inductive trigger. Analog 0/10 V read as a digital LOW/HIGH cycle trigger.'},
    'Machine_signal': {'label': 'Machine_signal',     'category': 'trigger', 'unit': '',
                       'tooltip': 'Machine cycle trigger. Analog 0/10 V read as a digital LOW/HIGH cycle trigger.'},
}

# Order shown in the per-channel dropdown.
SENSOR_TYPE_ORDER = ['none', 'T_futaba', 'P_kistler', 'P_machine', 'vel_screw', 'pos_screw',
                     'Inductive', 'Machine_signal']

# The trigger types (analog wiring) and the two trigger "modes" they back.
TRIGGER_TYPES = ('Inductive', 'Machine_signal')
# Map: Display-tab trigger mode -> the sensor type that provides it.
TRIGGER_MODE_TO_TYPE = {'Inductive': 'Inductive', 'Machine': 'Machine_signal'}

# Machine tab: fixed display order + axis assignment for the "shared" (3-axis) layout.
MACHINE_TYPES_ORDER = ['pos_screw', 'vel_screw', 'P_machine']
MACHINE_LEFT_TYPES = ['pos_screw', 'vel_screw']   # two left axes
MACHINE_RIGHT_TYPES = ['P_machine']              # one right axis


def sensor_category(type_str):
    return SENSOR_TYPES.get(type_str, {}).get('category')


def sensor_label(type_str):
    return SENSOR_TYPES.get(type_str, {}).get('label', type_str)


def sensor_unit(type_str):
    return SENSOR_TYPES.get(type_str, {}).get('unit', '')


def sensor_tooltip(type_str):
    return SENSOR_TYPES.get(type_str, {}).get('tooltip', '')
