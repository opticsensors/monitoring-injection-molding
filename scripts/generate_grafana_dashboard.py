"""Regenerate ``grafana_dashboard.json`` from ``daq_config_defaults.json``.

The cloud pipeline adapts to the channel configuration automatically at every
stage except the Grafana dashboard, which is a static JSON document:

  app (main.py)           publishes one ``CH<n>_<type>`` key per configured
                          channel, values already in physical units
  Node-RED (function)     discovers the channel fields dynamically - no edits
                          needed when the configuration changes
  grafana_dashboard.json  STATIC - regenerate it with this script

So whenever ``channels`` / ``channel_types`` / ``plot_channels`` (or
``machine_id``) change in ``daq_config_defaults.json``, run:

    py generate_grafana_dashboard.py

and re-import ``grafana_dashboard.json`` in Grafana (Dashboards -> Import).
The dashboard ``uid`` is preserved, so the import updates the existing
dashboard in place instead of creating a new one.

Note: the in-app config window does NOT write ``daq_config_defaults.json``;
that file is the hand-maintained source of truth for the machine's channel
layout, and it is what both the app (at startup) and this script read.

What is generated:
  * one xychart panel (cycles overlaid) per channel in ``plot_channels`` whose
    sensor type is a real signal (trigger/none types are skipped), titled
    ``<sensor label> (CH<n>)`` with y-axis ``label [unit]`` from
    sensor_types.py and x-axis ``t [ms]``
  * a collapsed Export row with a table of every configured real channel
  * the ``machine_id`` dashboard variable defaults to the config's machine
    (added to the variable's options if missing)

Dashboard identity (uid, datasource, variables, refresh, time range...) is
preserved from the existing ``grafana_dashboard.json``, so that file must
exist - restore it from git if it was lost.
"""
import json
import sys
from pathlib import Path

# This script lives in scripts/ but imports the app's sensor_types (repo root)
# and reads/writes daq_config_defaults.json (config/) and grafana_dashboard.json
# (iot/). Anchor everything to the repo root so it runs from any directory.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sensor_types import sensor_category, sensor_label, sensor_unit

CONFIG_FILE = ROOT / 'config' / 'daq_config_defaults.json'
DASHBOARD_FILE = ROOT / 'iot' / 'grafana_dashboard.json'

# InfluxQL filter shared by every panel: one machine, last N cycles.
WHERE = "\"machine_id\" = '$machine_id' AND \"cycle_num\" > $max_cycle_num - $n_cycles"


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
                'query': (f'SELECT "{field}", "t_ms" FROM "sensor_data" '
                          f'WHERE {WHERE} GROUP BY "cycle_id"'),
                'rawQuery': True,
                'refId': 'A',
                'resultFormat': 'table'
            }
        ],
        'title': f'{label} (CH{ch})',
        'transformations': [
            {
                'id': 'partitionByValues',
                'options': {'fields': ['cycle_id'], 'keepFields': False,
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
                        'query': (f'SELECT {fields_sql}, "cycle_num", "t_ms" '
                                  f'FROM "sensor_data" WHERE {WHERE}'),
                        'rawQuery': True,
                        'refId': 'A',
                        'resultFormat': 'table'
                    }
                ],
                'title': 'Export data (all channels, last N cycles)',
                'type': 'table'
            }
        ],
        'title': 'Export',
        'type': 'row'
    }


def main():
    if not DASHBOARD_FILE.exists():
        sys.exit(f'{DASHBOARD_FILE.name} not found - restore it from git first '
                 '(it provides the dashboard uid, datasource and variables).')
    cfg = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    dash = json.loads(DASHBOARD_FILE.read_text(encoding='utf-8'))
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
    dash['panels'] = panels

    # Default machine selection follows the config (option added if missing).
    machine_id = str(cfg.get('machine_id', '160t'))
    for var in dash.get('templating', {}).get('list', []):
        if var.get('name') != 'machine_id':
            continue
        values = [opt['value'] for opt in var.get('options', [])]
        if machine_id not in values:
            values.append(machine_id)
        var['options'] = [{'selected': v == machine_id, 'text': v, 'value': v}
                          for v in values]
        var['query'] = ', '.join(values)
        var['current'] = {'text': machine_id, 'value': machine_id}

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
