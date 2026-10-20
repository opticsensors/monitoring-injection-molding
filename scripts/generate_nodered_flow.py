"""Synchronize function bodies and wire the metadata ingestion path; offline only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'iot' / 'nodered_flows.json'
TAB = '9a5797004b410dd8'
PG = 'cycle-postgres-config'


def function(identifier, name, filename, wires, x, y):
    return dict(id=identifier, type='function', z=TAB, name=name,
                func=(ROOT / 'iot' / 'nodered' / filename).read_text(encoding='utf-8'),
                outputs=len(wires), timeout=0, noerr=0, initialize='', finalize='',
                libs=[], x=x, y=y, wires=wires)


def postgres(identifier, name, wires, x, y):
    return dict(id=identifier, type='postgresql', z=TAB, name=name,
                query='', postgreSQLConfig=PG, split=False, rowsPerMsg=1,
                outputs=1, x=x, y=y, wires=wires)


def main():
    nodes = json.loads(PATH.read_text(encoding='utf-8'))
    nodes = [n for n in nodes if not n['id'].startswith('cycle-') and n['id'] not in
             ('3c42711ed5d08dad', '2303a0420a27e0fd', '3be90c134058818c')]
    for node in nodes:
        if node['id'] == TAB:
            node.update(label='Injection monitoring: waveforms + cycle metadata',
                        info='See iot/SERVER_SETUP.md. Deploy server changes before the new desktop app.')
        if node['type'] == 'mqtt in':
            node.update(datatype='utf8', wires=[['cycle-enqueue']])
    nodes += [
        function('cycle-enqueue', 'Persist original message', 'nodered_enqueue.js',
                 [['cycle-claim']], 300, 140),
        dict(id='cycle-tick', type='inject', z=TAB, name='Recover pending work',
             props=[], repeat='5', crontab='', once=True, onceDelay=1,
             x=300, y=320, wires=[['cycle-claim']]),
        function('cycle-claim', 'Claim one durable job', 'nodered_claim.js',
                 [['3c42711ed5d08dad']], 520, 320),
        function('3c42711ed5d08dad', 'Validate and route capture', 'nodered_function.js',
                 [['cycle-register'], ['cycle-measurements']], 520, 140),
        postgres('cycle-register', 'Register capture', [['cycle-prepare']], 800, 60),
        postgres('cycle-measurements', 'Update measurements', [['cycle-ack']], 800, 240),
        function('cycle-prepare', 'Prepare exact-ns write', 'nodered_prepare_write.js',
                 [['cycle-http']], 1030, 60),
        dict(id='cycle-http', type='http request', z=TAB, name='Write Influx 1.8', method='POST',
             ret='txt', paytoqs='ignore', url='http://influxdb:8086/write?db=sensor_data&rp=autogen&precision=ns',
             tls='', persist=False, proxy='', insecureHTTPParser=False, authType='', senderr=False,
             headers=[], x=1250, y=60, wires=[['cycle-complete']]),
        function('cycle-complete', 'Check Influx response', 'nodered_store_complete.js',
                 [['cycle-http'], ['cycle-stored']], 1480, 60),
        postgres('cycle-stored', 'Mark waveform stored', [['cycle-ack']], 1720, 60),
        function('cycle-ack', 'Finish durable job', 'nodered_queue_complete.js',
                 [['cycle-claim']], 1720, 240),
        dict(id=PG, type='postgreSQLConfig', name='Cycle metadata', host='postgres', hostFieldType='str',
             port='5432', portFieldType='num', database='injection_monitoring', databaseFieldType='str',
             ssl='false', sslFieldType='bool', applicationName='injection-monitoring',
             applicationNameType='str', max='5', maxFieldType='num', idle='1000', idleFieldType='num',
             connectionTimeout='10000', connectionTimeoutFieldType='num',
             userFieldType='cred', passwordFieldType='cred'),
        dict(id='cycle-errors', type='catch', z=TAB, name='Ingestion errors',
             scope=['cycle-enqueue','cycle-claim','3c42711ed5d08dad','cycle-register',
                    'cycle-measurements','cycle-prepare','cycle-http','cycle-complete','cycle-stored','cycle-ack'],
             uncaught=False, x=500, y=440, wires=[['cycle-retain']]),
        function('cycle-retain', 'Retain failure for retry/review', 'nodered_queue_error.js',
                 [['cycle-error-log']], 800, 440),
        dict(id='cycle-error-log', type='debug', z=TAB, name='Ingestion error; inspect durable queue',
             active=True, tosidebar=True, console=True, tostatus=False, complete='error', targetType='msg',
             x=830, y=440, wires=[])
    ]
    PATH.write_text(json.dumps(nodes, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
