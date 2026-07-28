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
  'trigger' -> digital input only; drives cycles + arrows on both tabs, and is
               never plotted, written to the CSV or published to the cloud
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
    'trigger':        {'label': 'trigger',            'category': 'trigger', 'unit': '',
                       'tooltip': 'Cycle trigger: the main relay contact, wired to this digital input.\n'
                                  'Every source (manual switch, inductive sensor, machine signal) is\n'
                                  'OR-ed onto that one relay, which also takes the Kistler amplifiers\n'
                                  'out of reset - so the cycle and the amp window can never drift apart.\n'
                                  'Dry contact to GND: relay released = 0, energised = 1.'},
}

# Order shown in the per-channel (analog) dropdown. 'trigger' is absent on
# purpose: it is a digital input only, never an analog channel.
SENSOR_TYPE_ORDER = ['none', 'T_futaba', 'P_kistler', 'P_machine', 'vel_screw', 'pos_screw']

# The one trigger type, and the sensor types older configs used for it.
TRIGGER_TYPE = 'trigger'
LEGACY_TRIGGER_TYPES = ('Inductive', 'Machine_signal', 'I')

# Trigger modes offered for cycle control. They are labels for what is driving
# the main relay - all of them are read from the same digital input, because all
# of them are wired onto the same relay coil.
TRIGGER_MODES = ['None', 'Inductive', 'Machine', 'Manual']

# Digital inputs. The DI-4108 reports them in the HIGH byte of the digital scan
# word, so Dn is bit 8+n (D4 = bit 12, confirmed on the bench 2026-07-08).
DIGITAL_INPUTS = [f'D{n}' for n in range(7)]       # D0..D6


def normalize_trigger_type(code):
    """Map any legacy trigger type onto the single 'trigger' type ('none' otherwise)."""
    if code == TRIGGER_TYPE or code in LEGACY_TRIGGER_TYPES:
        return TRIGGER_TYPE
    return 'none'


def digital_bit(name):
    """Bit position of digital input 'Dn' in the digital scan word, or None."""
    try:
        n = int(str(name)[1:])
    except (TypeError, ValueError):
        return None
    return 8 + n if 0 <= n <= 6 else None

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
