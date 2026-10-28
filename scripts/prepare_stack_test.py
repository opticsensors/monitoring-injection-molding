"""Prepare ignored config for the isolated Docker integration test; stdlib only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / 'data' / 'validation' / 'stack'
    destination.mkdir(parents=True, exist_ok=True)
    flow = json.loads((ROOT / 'iot/nodered_flows.json').read_text(encoding='utf-8'))
    for node in flow:
        if node['type'] == 'postgreSQLConfig':
            node.update(userFieldType='env', userEnv='TEST_PG_USER',
                        passwordFieldType='env', passwordEnv='TEST_PG_PASSWORD')
        if node['type'] == 'mqtt-broker':
            node['clientid'] = 'isolated-metadata-validation'
    (destination / 'flows.json').write_text(json.dumps(flow, indent=2) + '\n', encoding='utf-8')
    dashboard = json.loads((ROOT / 'iot/grafana_dashboard.json').read_text(encoding='utf-8'))
    sources = {}
    for panel in [*dashboard['panels'], *dashboard.get('templating', {}).get('list', [])]:
        for item in [panel, *panel.get('targets', [])]:
            ds = item.get('datasource', {})
            if isinstance(ds, dict) and ds.get('uid'):
                sources[ds['type']] = ds['uid']
    # JSON is valid YAML and safely quotes UIDs; Grafana accepts this provisioning file.
    provision = {'apiVersion': 1, 'datasources': [
        dict(name='Validation Influx', type='influxdb', uid=sources['influxdb'],
             access='proxy', url='http://influxdb:8086', database='sensor_data',
             jsonData={'httpMode': 'GET', 'version': 'InfluxQL'}),
        dict(name='Cycle metadata', type='grafana-postgresql-datasource',
             uid=sources['grafana-postgresql-datasource'], access='proxy', url='postgres:5432',
             user='monitoring_reader', secureJsonData={'password': 'test-only-reader'},
             jsonData={'database': 'injection_monitoring', 'sslmode': 'disable', 'postgresVersion': 1700})]}
    (destination / 'datasources.yaml').write_text(json.dumps(provision, indent=2) + '\n', encoding='utf-8')
    # The installer uses umask 077. These deliberately public/test-only bind
    # mounts must still be readable by container UIDs 1000, 999 and 472.
    public_mounts = [destination / 'flows.json', destination / 'datasources.yaml',
        ROOT / 'iot/postgres/001_cycle_metadata.sql', ROOT / 'iot/postgres/002_ingestion_recovery.sql',
        ROOT / 'iot/postgres/003_history_reader.sql', ROOT / 'iot/postgres/004_cycle_review.sql',
        ROOT / 'iot/postgres/005_machine_correction.sql',
        ROOT / 'iot/nodered/history_api.cjs',
        ROOT / 'iot/nodered/capture_queue.cjs', ROOT / 'iot/grafana_dashboard.json',
        *(p for p in (ROOT / 'iot/validation').iterdir() if p.is_file())]
    for path in public_mounts:
        path.chmod(0o644)
    print(f'Prepared isolated stack config in {destination}')


if __name__ == '__main__':
    main()
