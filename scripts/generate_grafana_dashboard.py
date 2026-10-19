"""Regenerate the metadata-aware Grafana dashboard from channel defaults.

Preserves the dashboard identity and Influx datasource, builds PostgreSQL
metadata selectors and bounded Influx waveform panels. Run from repo root:
    py -3.11 scripts/generate_grafana_dashboard.py --postgres-uid ACTUAL_UID
Then import iot/grafana_dashboard.json. This script never contacts the server.
Run setup preferences do not alter the hand-maintained channel defaults file.
"""
import json
import argparse
import sys
from pathlib import Path

# This script lives in scripts/ but imports the app's sensor_types (repo root)
# and reads/writes daq_config_defaults.json (config/) and grafana_dashboard.json
# (iot/). Anchor everything to the repo root so it runs from any directory.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sensor_types import sensor_category, sensor_label, sensor_unit
from dashboard_metadata import POSTGRES, variables, metadata_panel

CONFIG_FILE = ROOT / 'config' / 'daq_config_defaults.json'
DASHBOARD_FILE = ROOT / 'iot' / 'grafana_dashboard.json'

# Exact scoped predicates come from the PostgreSQL catalog, including nanosecond bounds.
WHERE = "(${cycle_predicate:raw})"


def find_influx_datasource(dash):
    """Pull the InfluxDB datasource ref out of the existing dashboard."""
    def walk(obj):
        if isinstance(obj, dict):
            ds = obj.get('datasource')
            if isinstance(ds, dict) and ds.get('type') == 'influxdb' and ds.get('uid'):
                return ds
            for value in obj.values():
                found = walk(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = walk(value)
                if found:
                    return found
        return None

    ds = walk(dash.get('panels', [])) or walk(dash.get('templating', {}))
    if not ds:
        sys.exit("No InfluxDB datasource found in the existing dashboard - "
                 "restore grafana_dashboard.json from git and retry.")
    return {'type': ds['type'], 'uid': ds['uid']}


def chart_panel(datasource, pid, ch, ch_type, x, y):
    """One 'cycles overlaid' xychart for a single channel."""
    field = f'CH{ch}_{ch_type}'
    label, unit = sensor_label(ch_type), sensor_unit(ch_type)
    axis = f'{label} [{unit}]' if unit else label
    return {
        'datasource': dict(datasource),
        'fieldConfig': {
            'defaults': {
                'color': {'mode': 'palette-classic'},
                'custom': {
                    'axisBorderShow': False,
                    'axisCenteredZero': False,
                    'axisColorMode': 'text',
                    'axisLabel': '',
                    'axisPlacement': 'auto',
                    'fillOpacity': 0,
                    'hideFrom': {'legend': False, 'tooltip': False, 'viz': False},
                    'lineWidth': 2,
                    'pointShape': 'circle',
                    'pointSize': {'fixed': 0},
                    'pointStrokeWidth': 1,
                    'scaleDistribution': {'type': 'linear'},
                    'show': 'lines'
                },
                'mappings': [],
                'thresholds': {
                    'mode': 'absolute',
                    'steps': [{'color': 'green'}, {'color': 'red', 'value': 80}]
                }
            },
            # Axis labels are attached per field (byRegexp so the cycle labels
            # added by the partition transform still match).
            'overrides': [
                {
                    'matcher': {'id': 'byRegexp', 'options': '/^t_ms.*/'},
                    'properties': [{'id': 'custom.axisLabel', 'value': 't [ms]'}]
                },
                {
                    'matcher': {'id': 'byRegexp', 'options': f'/^{field}.*/'},
                    'properties': [{'id': 'custom.axisLabel', 'value': axis}]
                }
            ]
        },
        'gridPos': {'h': 8, 'w': 12, 'x': x, 'y': y},
        'id': pid,
        'maxDataPoints': 50000,
        'options': {
            'legend': {'calcs': [], 'displayMode': 'list',
                       'placement': 'bottom', 'showLegend': True},
            'mapping': 'auto',
            'series': [
                {
                    'x': {'matcher': {'id': 'byName', 'options': 't_ms'}},
                    'y': [{'matcher': {'id': 'byName', 'options': field}}]
                }
            ],
            'seriesMapping': 'manual',
            'tooltip': {'hideZeros': False, 'mode': 'single', 'sort': 'none'}
        },
        'pluginVersion': '12.0.0',
        'targets': [
            {
                'datasource': dict(datasource),
                'policy': 'default',
                'query': (f'SELECT "{field}", "t_ms", "cycle_num", "machine_id", "session_id" FROM "autogen"."sensor_data" '
                          f'WHERE {WHERE}'),
                'rawQuery': True,
                'refId': 'A',
                'resultFormat': 'table'
            }
        ],
        'title': f'{label} (CH{ch})',
        'transformations': [
            {
                'id': 'partitionByValues',
                'options': {'fields': ['machine_id', 'session_id', 'cycle_num'], 'keepFields': False,
                            'naming': {'asLabels': True}}
            }
        ],
        'type': 'xychart'
    }


def export_row(datasource, row_id, y, fields_sql):
    """Collapsed row holding the raw-table panel used to export/inspect data."""
    return {
        'collapsed': True,
        'gridPos': {'h': 1, 'w': 24, 'x': 0, 'y': y},
        'id': row_id,
        'panels': [
            {
                'datasource': dict(datasource),
                'fieldConfig': {
                    'defaults': {
                        'color': {'mode': 'thresholds'},
                        'custom': {'align': 'auto', 'cellOptions': {'type': 'auto'},
                                   'filterable': True, 'inspect': False},
                        'mappings': [],
                        'thresholds': {'mode': 'absolute',
                                       'steps': [{'color': 'green'}]}
                    },
                    'overrides': []
                },
                'gridPos': {'h': 10, 'w': 24, 'x': 0, 'y': y + 1},
                'id': row_id + 1,
                'options': {
                    'cellHeight': 'sm',
                    'footer': {'countRows': False, 'fields': '',
                               'reducer': ['sum'], 'show': False},
                    'showHeader': True
                },
                'pluginVersion': '12.0.0',
                'targets': [
                    {
                        'datasource': dict(datasource),
                        'policy': 'default',
                        'query': (f'SELECT {fields_sql}, "cycle_num", "t_ms", "machine_id", "session_id" '
                                  f'FROM "autogen"."sensor_data" WHERE {WHERE}'),
                        'rawQuery': True,
                        'refId': 'A',
                        'resultFormat': 'table'
                    }
                ],
                'title': 'Export data (selected cycles, all channels)',
                'type': 'table'
            }
        ],
        'title': 'Export',
        'type': 'row'
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgres-uid', help='UID of the deployed PostgreSQL Grafana datasource')
    args = parser.parse_args()
    if not DASHBOARD_FILE.exists():
        sys.exit(f'{DASHBOARD_FILE.name} not found - restore it from git first '
                 '(it provides the dashboard uid, datasource and variables).')
    cfg = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    dash = json.loads(DASHBOARD_FILE.read_text(encoding='utf-8'))
    existing_pg = next((v.get('datasource', {}).get('uid') for v in dash.get('templating', {}).get('list', [])
                        if v.get('datasource', {}).get('type') == POSTGRES['type']), None)
    POSTGRES['uid'] = args.postgres_uid or existing_pg or 'cycle-metadata'
    datasource = find_influx_datasource(dash)

    channels = cfg['channels']
    types = cfg['channel_types']
    if len(channels) != len(types):
        print(f'WARNING: {len(channels)} channels but {len(types)} channel_types '
              '- extra entries are ignored.')
    type_by_ch = dict(zip(channels, types))
    plot_sel = set(cfg.get('plot_channels', channels))

    def is_signal(ch):
        return sensor_category(type_by_ch[ch]) not in (None, 'trigger')

    panel_chs = [ch for ch in type_by_ch if ch in plot_sel and is_signal(ch)]
    export_chs = [ch for ch in type_by_ch if is_signal(ch)]
    if not export_chs:
        sys.exit('No real-signal channels in the config - nothing to chart.')
    if not panel_chs:
        print('WARNING: no plot-selected signal channels; only the Export row '
              'will be generated.')

    panels = [chart_panel(datasource, i + 1, ch, type_by_ch[ch],
                          (i % 2) * 12, (i // 2) * 8)
              for i, ch in enumerate(panel_chs)]
    fields_sql = ', '.join(f'"CH{ch}_{type_by_ch[ch]}"' for ch in export_chs)
    panels.append(export_row(datasource, len(panel_chs) + 1,
                             ((len(panel_chs) + 1) // 2) * 8, fields_sql))
    panels.append(metadata_panel(len(panel_chs) + 3, ((len(panel_chs) + 1) // 2) * 8 + 2))
    dash['panels'] = panels

    machine_id = str(cfg.get('machine_id', '55t'))
    dash['templating'] = {'list': variables(machine_id)}
    dash['refresh'] = '5s'
    dash['timepicker'] = {'hidden': False}
    dash['description'] = ('Select cycles in PostgreSQL, then read their exact identity/time ranges from InfluxDB. '
                           'Time range applies to observed cycle start. Blank numeric filters include unknown values. '
                           'Refresh cycle variables after changing metadata; verify automatic refresh on the deployed Grafana version.')

    DASHBOARD_FILE.write_text(json.dumps(dash, indent=2, ensure_ascii=False) + '\n',
                              encoding='utf-8')

    print(f'{DASHBOARD_FILE.name} regenerated:')
    print('  panels : ' + ', '.join(
        f'{sensor_label(type_by_ch[ch])} (CH{ch})' for ch in panel_chs))
    print(f'  export : {len(export_chs)} channels')
    print(f'  machine: {machine_id}')
    print('Re-import the file in Grafana (Dashboards -> Import) to apply; the '
          'uid is unchanged so it updates the existing dashboard.')


if __name__ == '__main__':
    main()
