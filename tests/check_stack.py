"""Exercise ONLY the isolated Compose project, never the production containers.

Requires a running iot/validation/compose.yaml stack, stdlib only. Creates test
captures and stops/restarts that project's PostgreSQL, InfluxDB and Node-RED.
Keeps test data for inspection. Grafana browser checks remain in SERVER_SETUP.md.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.diagnose_influxdb import response_rows
from scripts.deploy_server import API, POSTGRES_CONNECTION_CHECK, configure_postgres_datasource

COMPOSE = ['docker', 'compose', '-p', 'monitoring-metadata-test', '-f',
           str(ROOT / 'iot/validation/compose.yaml')]


def command(*args, data=None):
    return subprocess.run([*COMPOSE, *args], input=data, text=True,
                          capture_output=True, check=True).stdout.strip()


def sql(query):
    return command('exec', '-T', 'postgres', 'psql', '-X', '-A', '-t', '-v',
                   'ON_ERROR_STOP=1', '-U', 'postuser', '-d', 'injection_monitoring', '-c', query)


def influx(query):
    document = json.loads(command('exec', '-T', 'influxdb', 'influx', '-database',
                                  'sensor_data', '-format', 'json', '-execute', query))
    return list(response_rows(document))


def wait_for(check, label, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                print('PASS:', label, flush=True)
                return
        except (subprocess.CalledProcessError, ValueError, KeyError):
            pass
        time.sleep(2)
    raise AssertionError('Timed out: ' + label)


def publish(message):
    command('exec', '-T', 'mosquitto', 'mosquitto_pub', '-h', 'localhost', '-q', '1',
            '-t', 'validation/sensors', '-s', data=json.dumps(message))


def queue_empty():
    return command('exec', '-T', 'nodered', 'node', '/opt/capture_queue.cjs', 'status') == '[]'


def capture(session, cycle, base, count, machine='55t'):
    samples = [dict(timestamp_ns=str(base+i*1000000), time_s=i/1000,
                    sample_index=i, CH0_T_futaba=35+i/7) for i in range(count)]
    return dict(schema_version=1, kind='capture',
        capture=dict(machine_id=machine, session_id=session, cycle_id=cycle, session_cycle=cycle,
            mode='cycle', status='complete', reason='test', sample_count=count,
            base_time_ns=str(base), first_time_ns=samples[0]['timestamp_ns'],
            last_time_ns=samples[-1]['timestamp_ns'], trigger_start_ns=str(base),
            trigger_end_ns=str(base+count*1000000), material='test', mold_temperature_c=None,
            pressure_settings_bar={'limit': None}, config_snapshot={'field_names': ['CH0_T_futaba']}),
        measurements=dict(revision=0, update_id=uuid4().hex, weight_g=None, length_mm=None), samples=samples)


def check_grafana_updates():
    # The Compose project exposes only its test Grafana on this loopback port.
    # Use a separate, unprovisioned datasource so the real update API is tested.
    api = API('http://127.0.0.1:13000')
    api.headers['Authorization'] = 'Basic ' + base64.b64encode(b'validation:test-only-grafana').decode()
    api.read('/api/health', timeout=90)
    uid = 'validation-installer-postgres'
    path = '/api/datasources/uid/' + uid
    versions = []
    for _ in range(3):
        configure_postgres_datasource(api, 'test-only-reader', uid, 'Validation installer PostgreSQL')
        versions.append(api.read(path)['version'])
    assert versions[1:] == [versions[0] + 1, versions[0] + 2], versions
    assert api.read(path + '/health')['status'] == 'OK'
    print('PASS: repeated installer datasource updates use real Grafana versions', flush=True)

def check_history_api(messages):
    # Requests stay inside the isolated Node-RED container/network.
    probe = r"""
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
(async()=>{
const root='http://127.0.0.1:1880',headers={Authorization:'Bearer test-only-history'};
const denied=await fetch(root+'/monitoring/history');
if(denied.status!==401)throw Error('History must require its access key');
let cursor='',found=[];
do {
 const r=await fetch(root+'/monitoring/history?cursor='+encodeURIComponent(cursor),{headers});
 if(!r.ok)throw Error('History HTTP '+r.status);
 const page=await r.json(); found.push(...page.cycles); cursor=page.next_cursor;
} while(cursor);
for(const capture of input) {
 const entry=found.find(e=>e.capture.machine_id===capture.machine_id&&e.capture.session_id===capture.session_id&&e.capture.cycle_id===capture.cycle_id);
 if(!entry||entry.capture.sample_count!==capture.sample_count)throw Error('History missing capture');
 const query=new URLSearchParams({machine_id:capture.machine_id,session_id:capture.session_id,cycle_id:capture.cycle_id});
 const r=await fetch(root+'/monitoring/waveform?'+query,{headers});
 if(!r.ok)throw Error('Waveform HTTP '+r.status);
 const wave=await r.json();
 if(wave.time_s.length!==capture.sample_count||wave.values.CH0_T_futaba.length!==capture.sample_count)throw Error('Waveform length mismatch');
 if(Math.abs(wave.values.CH0_T_futaba[1]-(35+1/7))>1e-8)throw Error('Waveform values changed');
}
console.log('PASS: authenticated desktop history and original waveforms for both machines');
})().catch(e=>{console.error(e.message);process.exitCode=1});
"""
    print(command('exec', '-T', 'nodered', 'node', '-e', probe,
                  data=json.dumps([m['capture'] for m in messages])), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=12001)
    args = parser.parse_args()
    if not 10001 <= args.samples <= 200000:
        parser.error('--samples must be 10001..200000 to exercise chunking')
    session = 'validation_' + uuid4().hex
    base = time.time_ns() - 600_000_000_000
    # Both machine IDs, ONLY inside the isolated Compose project.
    messages = [capture(session, n, base+(n-1)*250_000_000_000, args.samples, machine)
                for n, machine in enumerate(('55t', '160t'), 1)]
    where = f"machine_id IN ('55t', '160t') AND session_id='{session}'"
    stored = lambda n: sql(f"SELECT count(*) FROM monitoring.cycles WHERE {where} AND waveform_status='stored'") == str(n)
    wait_for(lambda: int(sql('SELECT max(version) FROM monitoring.schema_migrations')) >= 2, 'schema ready')
    # Exercise the actual migration runner and a rerun on this project's container.
    # Resolve the container from Compose; never fall back to production's name.
    container = command('ps', '-q', 'postgres')
    assert container and '\n' not in container, 'Expected one isolated PostgreSQL container'
    migration_env = {**os.environ, 'MONITORING_POSTGRES_CONTAINER': container}
    for _ in range(2):
        subprocess.run(['bash', str(ROOT / 'scripts/apply_server_migrations.sh')], env=migration_env, check=True)
    assert sql('SELECT max(version) FROM monitoring.schema_migrations') == '5'
    # MQTT subscription must exist before the first test publication.
    wait_for(lambda: 'Connected to broker' in command('logs', '--tail', '200', 'nodered'), 'MQTT subscriber connected')
    command('exec', '-T', 'nodered', 'node', '-e', POSTGRES_CONNECTION_CHECK,
            '/data', '/usr/src/node-red', data=json.dumps('test-only-ingest'))
    print('PASS: installer PostgreSQL probe using the real Node-RED connector', flush=True)
    check_grafana_updates()
    for message in messages:
        publish(message)
    wait_for(lambda: stored(2), 'two multi-chunk captures stored')
    wait_for(queue_empty, 'initial captures drained')
    check_history_api(messages)
    review = dict(schema_version=1, kind='review', machine_id='55t', session_id=session, cycle_id=1,
        review=dict(revision=1, update_id='isolated-review', updated_at_ns=str(time.time_ns()),
                    excluded=True, settings=dict(mold_temperature_c=80, melt_temperature_c=220)))
    publish(review)
    wait_for(lambda: sql(f"SELECT excluded FROM monitoring.cycle_catalog WHERE {where} AND cycle_id=1") == 't',
             'cycle exclusion stored')
    assert sql(f"SELECT mold_temperature_c FROM monitoring.cycle_catalog WHERE {where} AND cycle_id=1") == '80'
    assert sql(f"SELECT melt_temperature_c FROM monitoring.cycle_catalog WHERE {where} AND cycle_id=1") == '220'
    review['review'].update(revision=2, update_id='isolated-restore', excluded=False)
    publish(review)
    wait_for(lambda: sql(f"SELECT excluded FROM monitoring.cycle_catalog WHERE {where} AND cycle_id=1") == 'f',
             'cycle exclusion undone')
    wait_for(queue_empty, 'corrections drained')
    print('PASS: corrections, melt setpoint and reversible exclusion through the real MQTT flow', flush=True)
    predicate = sql("SELECT '(time >= '||min(first_time_ns)::text||' AND time <= '||max(last_time_ns)::text||"
        "' AND ('||string_agg(influx_predicate,' OR ')||'))' FROM monitoring.cycle_catalog WHERE " + where)
    result = influx('SELECT count("t_ms") FROM "autogen"."sensor_data" WHERE ' + predicate)
    assert len(result) == 1 and result[0]['count'] == args.samples*2, result
    print('PASS: real Influx multi-cycle query returns every sample from both machines', flush=True)
    receipt = sql(f"SELECT waveform_stored_at::text FROM monitoring.cycles WHERE {where} AND cycle_id=1")
    publish(messages[0])
    wait_for(lambda: sql(f"SELECT waveform_stored_at::text FROM monitoring.cycles WHERE {where} AND cycle_id=1") != receipt,
             'duplicate replay acknowledged by database')
    wait_for(queue_empty, 'duplicate replay drained')
    assert influx('SELECT count("t_ms") FROM "autogen"."sensor_data" WHERE ' + predicate)[0]['count'] == args.samples*2
    for service in ('postgres', 'influxdb'):
        print('Testing isolated outage:', service, flush=True)
        message = capture(session+'_'+service, 1, base, 10001)
        command('stop', service)
        try:
            publish(message)
            wait_for(lambda: any(s.get('lastError') for s in json.loads(command('exec','-T','nodered','node',
                     '/opt/capture_queue.cjs','status'))), 'failed work remains on disk')
            command('restart', 'nodered')
        finally:
            command('start', service)
        wait_for(lambda: sql("SELECT waveform_status FROM monitoring.cycles WHERE session_id='"+
                 message['capture']['session_id']+"'") == 'stored', service+' outage and Node-RED restart recovered')
        wait_for(queue_empty, service+' recovery drained')
    print('PASS: isolated real Node-RED/PostgreSQL/Influx/MQTT integration. Test session:',session)
    print('Now check Grafana at localhost:13000: latest cycle count, numeric legends and automatic refresh.')


if __name__ == '__main__':
    main()
