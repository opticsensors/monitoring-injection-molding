"""Deploy this application's server integration on the existing IOTstack host.

Stdlib only. Default: inspect, back up, apply, verify. --check never deploys.
Run with acquisition stopped and old desktop uploads drained. Never runs a
whole-stack pull, replaces databases, resets admin passwords or edits other tabs.
"""
import argparse
import base64
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import getpass
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_legacy_catalog import read_cycles, build_sql
from scripts.diagnose_influxdb import response_rows

TAB = '9a5797004b410dd8'
PG_UID = 'cycle-metadata'
CONNECTOR = 'node-red-contrib-postgresql'
POSTGRES_CONNECTION_CHECK = r"""const fs=require('fs'),{createRequire}=require('module');
let client,phase='locating the installed PostgreSQL connector';
function report(error) {
    // Log only our phase and a code, never exception messages, stacks or input.
    const raw=error.code||error.name||'UNKNOWN';
    const code=/^[A-Za-z0-9_]{1,64}$/.test(raw)?raw:'UNKNOWN';
    console.error('Node-RED PostgreSQL check failed while '+phase+' ['+code+'].');
    process.exitCode=1;
}
(async()=>{
    try {
        // Node-RED packages need not provide a main/index.js entry point.
        const manifest=require.resolve('node-red-contrib-postgresql/package.json',
            {paths:process.argv.slice(1)});
        phase='loading the connector PostgreSQL driver';
        const {Client}=createRequire(manifest)('pg');
        phase='reading the saved database password';
        const secret=JSON.parse(fs.readFileSync(0,'utf8'));
        if(typeof secret!=='string'||!secret) throw new TypeError();
        client=new Client({host:'postgres',database:'injection_monitoring',
            user:'monitoring_ingest',password:secret,connectionTimeoutMillis:10000});
        phase='connecting to postgres as monitoring_ingest';
        await client.connect();
        phase='running SELECT 1 in injection_monitoring';
        await client.query('SELECT 1');
        console.log('Node-RED to PostgreSQL connection passed.');
    } catch(error) {
        report(error);
    } finally {
        if(client) {
            phase='closing the PostgreSQL test connection';
            try { await client.end(); } catch(error) { report(error); }
        }
    }
})();"""
SETTINGS_MARKER = '// injection-monitoring managed integration v1'
SETTINGS_ADDON = '''
// injection-monitoring managed integration v1
module.exports.functionGlobalContext = Object.assign({}, module.exports.functionGlobalContext, {
    captureQueue: require('/data/lib/capture_queue.cjs')
});
'''
HISTORY_MARKER = '// injection-monitoring managed history v1'
HISTORY_ADDON = '''
// injection-monitoring managed history v1
module.exports.functionGlobalContext = Object.assign({}, module.exports.functionGlobalContext, {
    historyApi: require('/data/lib/history_api.cjs')
});
'''


class DeployError(RuntimeError):
    pass


class APIError(DeployError):
    def __init__(self, status, path):
        self.status = status
        if status in (401, 403):
            detail = 'Check access/credentials; no passwords were reset.'
        elif status in (409, 412):
            detail = 'Update conflict. Check the current object version, name and concurrent edits.'
        else:
            detail = 'Check the service response and logs.'
        super().__init__(f'HTTP {status} at {path}. {detail}')


class APIConnectionError(DeployError):
    """The HTTP exchange failed; a write may already have reached the service."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise DeployError('Admin API redirected the request. Use its direct URL; credentials were not forwarded.')


class API:
    def __init__(self, url):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
            raise DeployError('Use an HTTP(S) URL without embedded credentials.')
        if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise DeployError('Use localhost or HTTPS for authenticated admin requests.')
        self.url = url.rstrip('/')
        self.headers = {'Accept': 'application/json'}
        # Local admin traffic must not go through a machine-wide HTTP proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, path, data=None, headers=None, form=False, timeout=60):
        body = None
        merged = dict(self.headers, **(headers or {}))
        if data is not None:
            body = (urllib.parse.urlencode(data) if form else json.dumps(data)).encode('utf-8')
            merged['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        request = urllib.request.Request(self.url + path, data=body, headers=merged, method=method)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raise APIError(exc.code, path) from None
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise APIConnectionError(f'{method} {self.url}{path}: connection failed '
                                     f'({type(exc).__name__}).') from None
        except ValueError:
            raise DeployError(f'{method} {self.url}{path}: invalid JSON response; check the service logs.') from None

    def read(self, path, headers=None, timeout=30):
        """Retry read-only requests while a restarting service becomes available.

        Writes use request() once: losing their response cannot establish whether
        the server applied them. Authentication/configuration errors fail at once.
        """
        deadline = time.monotonic() + timeout
        while True:
            try:
                return self.request('GET', path, headers=headers,
                                    timeout=min(5, max(0.1, deadline - time.monotonic())))
            except APIConnectionError as exc:
                last_error = str(exc)
            except APIError as exc:
                if exc.status not in (502, 503, 504):
                    raise
                last_error = str(exc)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DeployError(f'Timed out after {timeout}s waiting for {self.url}{path}. '
                                  f'Last response: {last_error} Check the service logs.') from None
            time.sleep(min(2, remaining))


def run(args, data=None, output=None, timeout=300, sensitive=False):
    """Secrets travel through stdin, never shell commands or exception messages."""
    try:
        result = subprocess.run([str(a) for a in args], input=data,
            stdout=output if output is not None else subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise DeployError(f'{args[0]} timed out; inspect its service logs before rerunning.') from None
    if result.returncode:
        detail = '' if sensitive else result.stderr.decode('utf-8', errors='replace').strip()[-1500:]
        raise DeployError(f'{args[0]} command failed (exit {result.returncode}). ' +
                          (detail or 'Inspect the service logs.'))
    return (result.stdout or b'').decode('utf-8').strip()


def sql(query, database='injection_monitoring'):
    return run(['docker', 'exec', '-i', 'postgres', 'psql', '-X', '-A', '-t',
                '-v', 'ON_ERROR_STOP=1', '-U', 'postuser', '-d', database], query.encode('utf-8'), sensitive=True)


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_private(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(path.suffix + '.tmp')
    with open(temp, 'w', encoding='utf-8') as stream:
        os.chmod(temp, 0o600)
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)
    if os.name == 'posix':
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def merge_flows(current, template):
    """Replace only the known application tab; retain shared config and credentials."""
    existing = {n['id']: n for n in current}
    target = {n['id']: deepcopy(n) for n in template}
    if TAB not in existing or existing[TAB]['type'] != 'tab':
        raise DeployError('Cannot identify the existing injection-monitoring tab by ID. No flow was changed.')
    # Unexpected duplicate subscribers could overwrite waveforms outside this flow.
    for node in current:
        if node.get('type') == 'mqtt in' and node.get('z') != TAB and node.get('topic') in ('+/sensors', '#', '+/#'):
            raise DeployError('Another tab subscribes to the sensor stream. Resolve that duplicate before deploying.')
    original_inputs = [n for n in current if n.get('z') == TAB and n['type'] == 'mqtt in']
    if len(original_inputs) != 1 or original_inputs[0].get('topic') != '+/sensors':
        raise DeployError('The existing MQTT input differs from the expected single +/sensors input.')
    old_broker_id = original_inputs[0]['broker']
    old_broker = existing.get(old_broker_id)
    if not old_broker or old_broker.get('type') != 'mqtt-broker':
        raise DeployError('Existing MQTT broker configuration is missing.')
    new_input = next(n for n in target.values() if n['type'] == 'mqtt in')
    new_broker_id = new_input['broker']
    del target[new_broker_id]
    new_input['broker'] = old_broker_id
    broker = deepcopy(old_broker)
    # Retain endpoint/TLS and credential ID. A shared broker must already have
    # durable settings, otherwise changing it would affect another application.
    shared = any(n.get('broker') == old_broker_id and n.get('z') != TAB for n in current)
    if shared and (not broker.get('clientid') or broker.get('cleansession', True)):
        raise DeployError('The MQTT broker config is shared and lacks a persistent session; review it first.')
    if not shared:
        broker.update(clientid=broker.get('clientid') or 'nodered-daq-ingest',
                      cleansession=False, autoUnsubscribe=False)
    target[old_broker_id] = broker
    for key, node in target.items():
        previous = existing.get(key)
        if previous and previous.get('z') != TAB and previous['type'] != 'tab':
            if key not in (old_broker_id, 'cycle-postgres-config'):
                raise DeployError(f'Node ID collision outside the application tab: {key}')
            if key == 'cycle-postgres-config' and any(
                    n.get('postgreSQLConfig') == key and n.get('z') != TAB for n in current):
                raise DeployError('Application PostgreSQL configuration is shared with another tab.')
        # Existing HTTP credentials are kept by Node-RED when omitted in POST.
        if key == 'cycle-http' and previous:
            for field in ('authType', 'url', 'tls', 'persist', 'proxy'):
                if field in previous:
                    node[field] = previous[field]
    survivors = [deepcopy(n) for n in current
                 if n.get('z') != TAB and n['id'] != TAB and n['id'] not in target]
    return survivors + list(target.values())


def mapped_dashboard(template, influx_uid, previous=None):
    dashboard = deepcopy(template)
    def visit(value):
        if isinstance(value, dict):
            ds = value.get('datasource')
            if isinstance(ds, dict) and ds.get('type') == 'influxdb':
                ds['uid'] = influx_uid
            elif isinstance(ds, dict) and ds.get('type') == 'grafana-postgresql-datasource':
                ds['uid'] = PG_UID
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(dashboard)
    dashboard['id'] = previous.get('id') if previous else None
    dashboard['version'] = previous.get('version', 0) if previous else 0
    # Hidden time controls mean the dashboard owns its live clock. Do not keep
    # an old absolute window that could stop latest-cycle variable refresh.
    if previous and 'time' in previous and not dashboard.get('timepicker', {}).get('hidden'):
        dashboard['time'] = previous['time']
    return dashboard


def configure_postgres_datasource(api, password, uid=PG_UID, name='Cycle metadata'):
    """Fetch the single-resource revision immediately before updating Grafana.

    GET /api/datasources returns list summaries without a version in Grafana 12.
    Never guess that version or disable its optimistic concurrency check.
    """
    path = '/api/datasources/uid/' + urllib.parse.quote(uid, safe='')
    try:
        existing = api.read(path)
    except APIError as exc:
        if exc.status != 404:
            raise
        existing = None
    source = dict(name=name, uid=uid, type='grafana-postgresql-datasource',
        access='proxy', url='postgres:5432', user='monitoring_reader',
        jsonData={'database': 'injection_monitoring', 'sslmode': 'disable', 'postgresVersion': 1700},
        secureJsonData={'password': password})
    if existing is not None:
        if (existing.get('uid') != uid or existing.get('readOnly')
                or existing.get('type') != source['type'] or existing.get('user') != source['user']):
            raise DeployError('The PostgreSQL datasource is provisioned or belongs to another configuration.')
        version = existing.get('version')
        if type(version) is not int or version < 1:
            raise DeployError('Grafana did not return a valid datasource version; no update was attempted.')
        source['version'] = version
        return api.request('PUT', path, source)
    return api.request('POST', '/api/datasources', source)


class Installer:
    def __init__(self, args):
        self.args = args
        self.state = Path(args.state_dir).expanduser().resolve()
        self.nr = API(args.nodered_url)
        self.gf = API(args.grafana_url)
        self.backup = None
        self.stage = 'preflight'
        self.template = load_json(ROOT / 'iot/nodered_flows.json')
        self.dashboard = load_json(ROOT / 'iot/grafana_dashboard.json')

    def step(self, message):
        self.stage = message
        print('\n' + message, flush=True)

    def preflight(self):
        self.step('1. Checking the existing server and application')
        if sys.platform != 'linux' or not shutil.which('docker'):
            raise DeployError('Run on the Linux Docker host, or use scripts/deploy.ps1 on Windows.')
        self.containers = {}
        for name in ('postgres', 'influxdb', 'nodered', 'grafana', 'mosquitto'):
            info = json.loads(run(['docker', 'inspect', name]))[0]
            if not info['State']['Running']:
                raise DeployError(f'{name} is not running. Start the existing service first.')
            self.containers[name] = info
        self.mount('nodered', '/data')
        self.mount('postgres', '/var/lib/postgresql/data')
        self.mount('influxdb', '/var/lib/influxdb')
        self.mount('influxdb', '/var/lib/influxdb/backup')
        self.mount('grafana', '/var/lib/grafana')
        run(['docker', 'exec', 'grafana', 'test', '-f', '/var/lib/grafana/grafana.db'])
        version = sql('SHOW server_version_num', 'postgres')
        if not 170000 <= int(version) < 180000:
            raise DeployError('This installer is validated for PostgreSQL 17; no image upgrade was attempted.')
        node = run(['docker', 'exec', 'nodered', 'node', '--version'])
        if int(node.lstrip('v').split('.')[0]) < 20:
            raise DeployError('Node-RED needs Node 20 or later.')
        for peer in ('postgres', 'influxdb', 'mosquitto'):
            if not (set(self.containers['nodered']['NetworkSettings']['Networks']) &
                    set(self.containers[peer]['NetworkSettings']['Networks'])):
                raise DeployError(f'Node-RED and {peer} do not share a Docker network.')
        for peer in ('postgres', 'influxdb'):
            if not (set(self.containers['grafana']['NetworkSettings']['Networks']) &
                    set(self.containers[peer]['NetworkSettings']['Networks'])):
                raise DeployError(f'Grafana and {peer} do not share a Docker network.')
        self.settings = run(['docker', 'exec', 'nodered', 'cat', '/data/settings.js'])
        runtime = run(['docker', 'exec', 'nodered', 'node', '-e',
            "const s=require('/data/settings.js');console.log(JSON.stringify({projects:s.editorTheme?.projects?.enabled,userDir:s.userDir}));"])
        runtime = json.loads(runtime)
        if runtime.get('projects'):
            raise DeployError('Node-RED Projects is enabled; use the project deployment workflow instead.')
        if runtime.get('userDir') not in (None, '/data'):
            raise DeployError('Node-RED uses a custom user directory; review the deployment paths first.')
        scheme = self.nr.request('GET', '/auth/login')
        token = os.environ.get('NODERED_TOKEN')
        if token:
            self.nr.headers['Authorization'] = 'Bearer ' + token
        elif scheme:
            if scheme.get('type') != 'credentials':
                raise DeployError('Set NODERED_TOKEN for this Node-RED authentication provider.')
            username = input('Node-RED username: ').strip()
            response = self.nr.request('POST', '/auth/token', dict(client_id='node-red-admin',
                grant_type='password', scope='*', username=username,
                password=getpass.getpass('Node-RED password: ')), form=True)
            self.nr.headers['Authorization'] = 'Bearer ' + response['access_token']
        self.flows = self.nr.request('GET', '/flows', headers={'Node-RED-API-Version': 'v2'})
        self.planned = merge_flows(self.flows['flows'], self.template)
        modules = self.nr.request('GET', '/nodes')
        installed = [n for n in modules if n.get('module') == CONNECTOR]
        self.install_connector = not installed
        if installed and any(n.get('version') != '0.16.2' or n.get('enabled') is False or n.get('err') for n in installed):
            raise DeployError('The installed PostgreSQL connector differs from enabled 0.16.2; review its other users first.')
        self.gf.request('GET', '/api/health')
        token = os.environ.get('GRAFANA_TOKEN')
        if token:
            self.gf.headers['Authorization'] = 'Bearer ' + token
        else:
            username = input('Grafana username [admin]: ').strip() or 'admin'
            password = getpass.getpass('Grafana password: ')
            self.gf.headers['Authorization'] = 'Basic ' + base64.b64encode(f'{username}:{password}'.encode()).decode()
        self.sources = self.gf.request('GET', '/api/datasources')
        candidates = [s for s in self.sources if s['type'] == 'influxdb'
                      and (s.get('database') or s.get('jsonData', {}).get('dbName')) == 'sensor_data'
                      and s.get('jsonData', {}).get('version', 'InfluxQL') == 'InfluxQL']
        if len(candidates) != 1:
            raise DeployError('Expected one Grafana InfluxQL datasource for sensor_data; resolve missing/ambiguous sources first.')
        self.influx_source = candidates[0]
        existing_pg = next((s for s in self.sources if s['uid'] == PG_UID), None)
        if existing_pg and (existing_pg.get('readOnly') or existing_pg['type'] != 'grafana-postgresql-datasource'
                            or existing_pg.get('user') != 'monitoring_reader'):
            raise DeployError('The cycle-metadata datasource UID is provisioned or belongs to another configuration.')
        self.previous_dashboard = None
        try:
            self.previous_dashboard = self.gf.request('GET', '/api/dashboards/uid/' + self.dashboard['uid'])
            if self.previous_dashboard['meta'].get('provisioned'):
                raise DeployError('The existing dashboard is provisioned; update its provisioning source instead.')
        except APIError as exc:
            if exc.status != 404:
                raise
        # This known deployment uses the local unauthenticated Influx CLI. Stop
        # early if that changed, rather than silently skipping history checks.
        self.influx_count()
        self.db_exists = sql("SELECT count(*) FROM pg_database WHERE datname='injection_monitoring'", 'postgres') == '1'
        if self.db_exists and sql("SELECT to_regclass('monitoring.cycles') IS NOT NULL") != 't':
            if sql("SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')") != '0':
                raise DeployError('injection_monitoring contains another schema; no migration was attempted.')
        self.roles = set(sql("SELECT rolname FROM pg_roles WHERE rolname IN ('monitoring_ingest','monitoring_reader')", 'postgres').splitlines())
        print(f'OK: PostgreSQL 17, Node {node}, persistent storage, admin APIs and existing MQTT flow.')
        print('PostgreSQL connector: ' + ('will install 0.16.2' if self.install_connector else 'already installed'))
        print('Grafana datasource and dashboard will be configured automatically.')

    def mount(self, name, destination):
        item = next((m for m in self.containers[name]['Mounts'] if m['Destination'] == destination
                     and m.get('RW') and m.get('Type') in ('bind', 'volume')), None)
        if not item:
            raise DeployError(f'Missing writable persistent mount: {name}:{destination}')
        return item

    def validate_stack(self):
        self.step('Testing this release with isolated containers before production changes')
        paths = [ROOT / 'iot/nodered_flows.json', ROOT / 'iot/grafana_dashboard.json',
                 ROOT / 'scripts/prepare_stack_test.py', ROOT / 'scripts/diagnose_influxdb.py',
                 ROOT / 'scripts/deploy_server.py', ROOT / 'scripts/apply_server_migrations.sh', ROOT / 'tests/check_stack.py']
        for folder in ('iot/nodered', 'iot/postgres', 'iot/validation'):
            paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file())
        digest = hashlib.sha256()
        # check_stack runs this exact connection probe in the isolated Node-RED.
        digest.update(POSTGRES_CONNECTION_CHECK.encode('utf-8'))
        for path in sorted(paths):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(b'\0' + path.read_bytes().replace(b'\r\n', b'\n') + b'\0')
        fingerprint = digest.hexdigest()
        receipt = self.state / 'validated-release.json'
        if receipt.exists() and load_json(receipt).get('sha256') == fingerprint:
            print('This release already passed on this server; skipping repeat container tests.')
            return
        run(['docker', 'compose', 'version'])
        compose = ['docker', 'compose', '-p', 'monitoring-metadata-test', '-f',
                   str(ROOT / 'iot/validation/compose.yaml')]
        run([sys.executable, '-B', ROOT / 'scripts/prepare_stack_test.py'])
        run([*compose, 'config', '--quiet'])
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        log_path = self.state / 'validation.log'
        print('First run can take several minutes to build test images. Log:', log_path, flush=True)
        failure = None
        try:
            with log_path.open('wb') as stream:
                run([*compose, 'up', '-d', '--build'], output=stream, timeout=1800)
                run([sys.executable, '-B', ROOT / 'tests/check_stack.py'], output=stream, timeout=900)
        except DeployError as exc:
            failure = str(exc)
            # Collect evidence while containers still exist. Never inspect the
            # production project, and never let diagnostics hide the test error.
            with log_path.open('ab') as stream:
                stream.write(('\n' + failure + '\n').encode('utf-8'))
                for args in (['ps', '--all'], ['logs', '--no-color', '--tail', '80']):
                    try:
                        diagnostic = run([*compose, *args], timeout=30)
                    except DeployError as diagnostic_error:
                        diagnostic = str(diagnostic_error)
                    stream.write(('\nTest containers: ' + ' '.join(args) + '\n' +
                                  diagnostic + '\n').encode('utf-8'))
                    if args[0] == 'ps':
                        print(diagnostic, flush=True)
        finally:
            # Fixed test project, isolated mounts/network; retain its test volumes.
            try:
                run([*compose, 'down'], timeout=120)
            except DeployError as cleanup_error:
                failure = ((failure + '\n') if failure else '') + 'Test cleanup failed: ' + str(cleanup_error)
                with log_path.open('a', encoding='utf-8') as stream:
                    stream.write('\n' + str(cleanup_error) + '\n')
        if failure:
            raise DeployError('Isolated integration test failed. Production was not changed by this attempt.\n'
                              f'{failure}\nFull test log (including container logs): {log_path}')
        save_private(receipt, {'sha256': fingerprint, 'at': datetime.now(timezone.utc).isoformat()})
        print('Isolated database outage/replay and multi-cycle tests passed.')

    def influx_count(self):
        value = run(['docker', 'exec', 'influxdb', 'influx', '-database', 'sensor_data',
                     '-format', 'json', '-execute', 'SELECT count("t_ms") FROM "autogen"."sensor_data"'])
        try:
            # Influx 1.8 returns {"results": [...]}, not a bare list. Consume
            # every statement so an error cannot be mistaken for empty data.
            return list(response_rows(json.loads(value)))
        except (ValueError, RuntimeError) as exc:
            raise DeployError(f'Influx read check failed: {exc} '
                              'Check local CLI authentication/database access.') from None

    def backups(self):
        self.step('2. Backing up databases, Node-RED and the Grafana configuration')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
        self.backup = self.state / 'backups' / stamp
        self.backup.mkdir(parents=True, mode=0o700)
        save_private(self.backup / 'containers-before.json', self.containers)
        save_private(self.backup / 'flows-before.json', self.flows)
        save_private(self.backup / 'grafana-datasources-before.json', self.sources)
        save_private(self.backup / 'grafana-dashboard-before.json', self.previous_dashboard)
        for name in ('docker-compose.yml', 'compose.yaml', 'docker-compose.override.yml', '.env'):
            source = Path.home() / 'IOTstack' / name
            if source.is_file():
                shutil.copyfile(source, self.backup / ('iotstack-' + name.lstrip('.')))
        with (self.backup / 'postgres-before.sql').open('wb') as stream:
            run(['docker', 'exec', 'postgres', 'pg_dumpall', '-U', 'postuser'], output=stream, timeout=1800)
        run(['docker', 'exec', 'influxdb', 'influxd', 'backup', '-portable', '-database',
             'sensor_data', '/var/lib/influxdb/backup/metadata_' + stamp], timeout=1800)
        with (self.backup / 'nodered-data.tgz').open('wb') as stream:
            run(['docker', 'exec', '-u', '0', 'nodered', 'tar', '-czf', '-', '-C', '/data', '.'],
                output=stream, timeout=1800)
        # Grafana API exports mask secrets. Briefly stop Grafana for a consistent
        # SQLite backup, including WAL/SHM and its other persistent configuration.
        try:
            run(['docker', 'stop', 'grafana'])
            run(['docker', 'cp', 'grafana:/var/lib/grafana', str(self.backup / 'grafana-data')], timeout=1800)
        finally:
            run(['docker', 'start', 'grafana'])
        save_private(self.backup / 'backup-info.json', {'influx_container_path':
            '/var/lib/influxdb/backup/metadata_' + stamp, 'completed_at': datetime.now(timezone.utc).isoformat()})
        print('Backups:', self.backup)

    def credentials(self):
        filename = self.state / 'database-credentials.json'
        state = load_json(filename) if filename.exists() else {'passwords': {}, 'pending_password_roles': []}
        creds = state['passwords']
        for role in ('monitoring_ingest', 'monitoring_reader'):
            if role not in creds:
                creds[role] = (getpass.getpass(f'Existing password for {role}: ') if role in self.roles
                               else secrets.token_urlsafe(36))
                if role not in self.roles:
                    state['pending_password_roles'].append(role)
            if not creds[role]:
                raise DeployError(f'Empty password for {role}.')
            if any(c in creds[role] for c in ('\n', '\r', '\0')):
                raise DeployError(f'Unsupported control character in {role} password.')
            if role in self.roles and role not in state['pending_password_roles']:
                # Authenticate before changing either app. Stock PostgreSQL Docker
                # uses host authentication for this TCP connection, not local peer.
                for attempt in range(3):
                    try:
                        run(['docker', 'exec', '-i', 'postgres', 'sh', '-c',
                            'IFS= read -r PGPASSWORD; export PGPASSWORD; exec psql -h 127.0.0.1 -U "$1" -d postgres -X -A -t -v ON_ERROR_STOP=1 -c "SELECT 1"',
                            'check-role', role], (creds[role] + '\n').encode('utf-8'), sensitive=True)
                        break
                    except DeployError:
                        if attempt == 2:
                            raise DeployError(f'Could not authenticate {role}; its password was not reset.') from None
                        creds[role] = getpass.getpass(f'Login failed. Enter the current password for {role}: ')
                        if not creds[role] or any(c in creds[role] for c in ('\n', '\r', '\0')):
                            raise DeployError(f'Invalid password input for {role}.')
        # Save BEFORE creating roles so an interrupted first run keeps its passwords.
        save_private(filename, state)
        self.creds = creds
        self.credential_state = state

    def migrate(self):
        self.step('3. Applying missing PostgreSQL setup')
        self.credentials()
        run(['bash', str(ROOT / 'scripts/apply_server_migrations.sh')])
        for role in ('monitoring_ingest', 'monitoring_reader'):
            password = self.creds[role]
            if role in self.credential_state['pending_password_roles']:
                sql("SET standard_conforming_strings=on; ALTER ROLE " + role + " PASSWORD '" +
                    password.replace("'", "''") + "';")
                self.credential_state['pending_password_roles'].remove(role)
                save_private(self.state / 'database-credentials.json', self.credential_state)
        print('Schema ready; existing role passwords retained.')

    def history(self):
        self.step('4. Reconciling historical cycles automatically')
        export = self.backup / 'server.metadata.json'
        export.write_text(sql((ROOT / 'iot/postgres/export_metadata.sql').read_text(encoding='utf-8')), encoding='utf-8')
        diagnostic = self.backup / 'diagnostic'
        with (self.backup / 'diagnostic.log').open('wb') as stream:
            run([sys.executable, '-B', ROOT / 'scripts/diagnose_influxdb.py', '--output', diagnostic],
                output=stream, timeout=1800)
        import csv
        with (diagnostic / 'cycles.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            print('No historical cycles; nothing to backfill.')
            return
        report = []
        entries = read_cycles(diagnostic / 'cycles.csv', export, report)
        generated = build_sql(entries)
        (self.backup / 'legacy_catalog.sql').write_text(generated, encoding='utf-8')
        sql(generated)
        print(f'Cataloged {len(entries)} historical cycles; {len(report)} already matched.')

    def write_container(self, path, content, private=False):
        # Preserve original owner/mode; new library files use settings.js ownership.
        program = """const fs=require('fs'),p=require('path'),file=process.argv[1];
const stat=fs.statSync(fs.existsSync(file)?file:'/data/settings.js');
fs.mkdirSync(p.dirname(file),{recursive:true});
const mode=process.argv[2]==='private'?0o600:stat.mode&0o777;
const tmp=file+'.monitoring-tmp';fs.writeFileSync(tmp,fs.readFileSync(0),{mode});
fs.chmodSync(tmp,mode);
fs.chownSync(tmp,stat.uid,stat.gid);fs.renameSync(tmp,file);"""
        run(['docker', 'exec', '-i', '-u', '0', 'nodered', 'node', '-e', program, path,
             'private' if private else 'normal'], content.encode('utf-8'))

    def history_runtime_plan(self, settings):
        if HISTORY_MARKER in settings and HISTORY_ADDON.strip() not in settings:
            raise DeployError('The managed history settings block was modified; review it before replacing it.')
        access_file = self.state / 'history-api-access.json'
        if not access_file.exists():
            save_private(access_file, {'token': secrets.token_urlsafe(32)})
        access = load_json(access_file)
        if not isinstance(access.get('token'), str) or len(access['token']) < 32:
            raise DeployError('Invalid saved history access key; inspect history-api-access.json.')
        config = {'token': access['token'], 'database': {'host': 'postgres',
            'database': 'injection_monitoring', 'user': 'monitoring_reader',
            'password': self.creds['monitoring_reader']}}
        planned = {
            '/data/lib/history_api.cjs': (ROOT / 'iot/nodered/history_api.cjs').read_text(encoding='utf-8'),
            '/data/history-access.json': json.dumps(config, sort_keys=True) + '\n'}
        # Compare digests, never print or pass the reader password as an argument.
        probe = """const fs=require('fs'),crypto=require('crypto');
const result={};for(const p of process.argv.slice(1)) result[p]=fs.existsSync(p)?
crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'):null;
process.stdout.write(JSON.stringify(result));"""
        existing = json.loads(run(['docker', 'exec', 'nodered', 'node', '-e', probe, *planned]))
        changed = {path: content for path, content in planned.items()
                   if existing.get(path) != hashlib.sha256(content.encode('utf-8')).hexdigest()}
        if HISTORY_MARKER not in settings:
            settings += '\n' + HISTORY_ADDON
        return settings, changed

    def wait_node_red(self):
        self.nr.read('/settings', timeout=90)

    def node_red(self):
        self.step('5. Installing the queue and deploying the Node-RED flow')
        queue = (ROOT / 'iot/nodered/capture_queue.cjs').read_text(encoding='utf-8')
        # An append-only extension preserves credentialSecret/authentication and
        # arbitrary JavaScript settings. No regex rewrite of the settings object.
        if SETTINGS_MARKER in self.settings and SETTINGS_ADDON.strip() not in self.settings:
            raise DeployError('The managed settings block was modified; review it before replacing it.')
        old_queue = run(['docker', 'exec', 'nodered', 'node', '-e',
            "const fs=require('fs'),p='/data/lib/capture_queue.cjs';process.stdout.write(fs.existsSync(p)?fs.readFileSync(p):'');"])
        queue_changed = old_queue != queue.strip()
        new_settings = self.settings if SETTINGS_MARKER in self.settings else self.settings + '\n' + SETTINGS_ADDON
        new_settings, history_files = self.history_runtime_plan(new_settings)
        pending_restart = self.state / 'runtime-update-pending.json'
        runtime_changed = queue_changed or bool(history_files) or new_settings != self.settings or self.install_connector
        if runtime_changed:
            # A crash after replacing files but before restart must not make a
            # subsequent run mistake on-disk equality for a running new module.
            save_private(pending_restart, {'restart_required': True})
        if queue_changed:
            self.write_container('/data/lib/capture_queue.cjs', queue)
        for path, content in history_files.items():
            self.write_container(path, content, private=path.endswith('history-access.json'))
        if new_settings != self.settings:
            self.write_container('/data/settings.js', new_settings)
        run(['docker', 'exec', 'nodered', 'node', '--check', '/data/settings.js'])
        if self.install_connector:
            print('Installing the PostgreSQL connector...', flush=True)
            run(['docker', 'exec', '-w', '/data', 'nodered', 'npm', 'install', '--save-exact',
                 '--no-audit', '--no-fund', CONNECTOR + '@0.16.2'], timeout=600)
        if runtime_changed or pending_restart.exists():
            print('Restarting Node-RED; waiting up to 90 seconds for its admin API...', flush=True)
            run(['docker', 'restart', 'nodered'], timeout=120)
            self.wait_node_red()
            print('Node-RED admin API is ready.', flush=True)
            pending_restart.unlink(missing_ok=True)
        current = self.nr.read('/flows', headers={'Node-RED-API-Version': 'v2'})
        modules = self.nr.read('/nodes')
        if not any(n.get('module') == CONNECTOR and n.get('enabled') is not False and not n.get('err')
                   and n.get('version') == '0.16.2' for n in modules):
            raise DeployError('Node-RED did not load the PostgreSQL connector; existing flows were not replaced.')
        if current['flows'] != self.flows['flows']:
            raise DeployError('Node-RED flows changed during deployment. Rerun after the editor is idle.')
        planned = merge_flows(current['flows'], self.template)
        credentials = {'cycle-postgres-config': {'user': 'monitoring_ingest', 'password': self.creds['monitoring_ingest']}}
        # GET /flows masks credentials, so reapply the app's DB credentials even
        # on a repeat deployment; no other node credentials are supplied/changed.
        print('Applying and verifying the Node-RED flow...', flush=True)
        self.nr.request('POST', '/flows', {'rev': current['rev'], 'flows': planned, 'credentials': credentials},
            headers={'Node-RED-API-Version': 'v2', 'Node-RED-Deployment-Type': 'flows'})
        deployed = self.nr.read('/flows', headers={'Node-RED-API-Version': 'v2'})
        if not any(n['id'] == 'cycle-enqueue' for n in deployed['flows']):
            raise DeployError('The Node-RED deployment could not be verified.')
        print('Node-RED flow deployed; existing MQTT credentials and other tabs retained.')

    def grafana(self):
        self.step('6. Configuring Grafana and updating its dashboard')
        configure_postgres_datasource(self.gf, self.creds['monitoring_reader'])
        previous = self.previous_dashboard['dashboard'] if self.previous_dashboard else None
        dashboard = mapped_dashboard(self.dashboard, self.influx_source['uid'], previous)
        body = {'dashboard': dashboard, 'overwrite': False, 'message': 'Injection monitoring deployment'}
        if self.previous_dashboard:
            body['folderUid'] = self.previous_dashboard['meta'].get('folderUid', '')
        self.gf.request('POST', '/api/dashboards/db', body)
        self.gf.request('GET', '/api/dashboards/uid/' + dashboard['uid'])
        print('Grafana datasource and dashboard applied; no GUI import needed.')

    def verify_history(self):
        token = load_json(self.state / 'history-api-access.json')['token']
        page = self.nr.read('/monitoring/history', headers={'Authorization': 'Bearer ' + token}, timeout=60)
        if not isinstance(page, dict) or not isinstance(page.get('cycles'), list):
            raise DeployError('Desktop history endpoint returned an invalid response.')
        if any(not isinstance(row.get('review'), dict) or 'effective_settings' not in row for row in page['cycles']):
            raise DeployError('Desktop history endpoint is missing the cycle correction update.')

    def verify(self):
        self.step('7. Verifying database access and deployed configuration')
        print('Checking Grafana database connections...', flush=True)
        for uid in (PG_UID, self.influx_source['uid']):
            health = self.gf.request('GET', '/api/datasources/uid/' + urllib.parse.quote(uid, safe='') + '/health')
            if health.get('status') != 'OK':
                raise DeployError(f'Grafana datasource {uid} did not pass its health check.')
        print('Checking Node-RED -> PostgreSQL using the saved ingestion password...', flush=True)
        # The probe emits only fixed labels/error codes, so failure details can
        # be shown safely. The password still travels only through stdin.
        run(['docker', 'exec', '-i', 'nodered', 'node', '-e', POSTGRES_CONNECTION_CHECK,
             '/data', '/usr/src/node-red'], json.dumps(self.creds['monitoring_ingest']).encode(), timeout=30)
        print('Checking the read-only desktop history endpoint...', flush=True)
        if sql('SELECT max(version) FROM monitoring.schema_migrations').strip() != '5':
            raise DeployError('Expected database migration 005 (editable machine setting).')
        sql('SELECT melt_temperature_c,excluded,review_revision,effective_machine_id FROM monitoring.cycle_catalog LIMIT 0')
        self.verify_history()
        print('Checking the ingestion queue and metadata status...', flush=True)
        run(['bash', ROOT / 'scripts/check_server_ingestion.sh'])
        print('Checking that waveform counts are unchanged...', flush=True)
        if self.influx_count() != self.before_count:
            raise DeployError('Influx counts changed during deployment. Keep recording paused and reconcile new uploads.')
        print('OK: database connections, queue health, catalog migration and unchanged waveform counts.')

    def maintenance(self):
        self.step('8. Installing scheduled backups and health checks')
        if not shutil.which('crontab'):
            print('crontab is unavailable: backup/health helpers remain available in scripts/. No schedule installed.')
            return
        bin_dir = self.state / 'bin'
        bin_dir.mkdir(exist_ok=True, mode=0o700)
        for name in ('backup_server_metadata.sh', 'check_server_ingestion.sh'):
            shutil.copyfile(ROOT / 'scripts' / name, bin_dir / name)
        current = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        if current.returncode not in (0, 1) or (current.returncode == 1 and 'no crontab' not in current.stderr.lower()):
            raise DeployError('Cannot inspect the user crontab; existing jobs were not changed.')
        before, after = '# BEGIN injection-monitoring', '# END injection-monitoring'
        existing = current.stdout
        if existing.count(before) != existing.count(after) or existing.count(before) > 1:
            raise DeployError('The existing managed cron block is malformed; no cron jobs were changed.')
        if before in existing:
            start, end = existing.index(before), existing.index(after) + len(after)
            if existing.index(after) < start:
                raise DeployError('The managed cron markers are reversed; no cron jobs were changed.')
            existing = existing[:start] + existing[end:]
        quote = lambda value: shlex.quote(value).replace('%', '\\%')
        jobs = ('\n' + before + '\n'
            '0 2 * * * /bin/bash ' + quote(str(bin_dir / 'backup_server_metadata.sh')) + ' ' +
            quote(str(self.state / 'backups/scheduled')) + ' >> ' + quote(str(self.state / 'backup.log')) + ' 2>&1\n'
            '*/5 * * * * /bin/bash ' + quote(str(bin_dir / 'check_server_ingestion.sh')) + ' > ' +
            quote(str(self.state / 'health.log')) + ' 2>&1\n' + after + '\n')
        save_private(self.backup / 'crontab-before.json', current.stdout)
        run(['crontab', '-'], (existing.rstrip() + jobs).encode('utf-8'))
        print('Daily backups at 02:00 server time; health.log updated every 5 minutes.')
        print('Logs are local; this does not configure email or external alerts.')

    def execute(self):
        self.preflight()
        if self.args.check:
            print('\nChecks complete. No deployment or backup performed. Run without --check to apply.')
            return
        self.validate_stack()
        self.before_count = self.influx_count()
        self.backups()
        self.migrate()
        self.history()
        self.node_red()
        self.grafana()
        self.verify()
        self.maintenance()
        save_private(self.state / 'last-success.json', {'at': datetime.now(timezone.utc).isoformat(),
            'backup': str(self.backup), 'dashboard_uid': self.dashboard['uid']})
        print('\nDeployment complete. Open your Grafana dashboard and set Latest cycles (max 100).')
        print('Then record one real cycle and verify it appears. Hardware and browser appearance need this check.')
        print('Backups:', self.backup)
        print('Desktop: set HISTORY_URL and HISTORY_TOKEN in the same local .env as MQTT.')
        print('History access key is in', self.state / 'history-api-access.json')
        print('OneDrive checkouts use %LOCALAPPDATA%\\InjectionMonitoring\\.env (or MONITORING_ENV_FILE).')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Inspect only; do not deploy')
    parser.add_argument('--nodered-url', default='http://127.0.0.1:1880')
    parser.add_argument('--grafana-url', default='http://127.0.0.1:3000')
    parser.add_argument('--state-dir', default='~/.local/state/injection-monitoring')
    args = parser.parse_args()
    os.umask(0o077)
    installer = Installer(args)
    print('Injection monitoring installer. Checks and backups run before production changes.')
    try:
        with ExitStack() as stack:
            if not args.check:
                if sys.platform != 'linux':
                    raise DeployError('Use scripts/deploy.ps1 on Windows, or run iot/deploy.sh on the Linux server.')
                import fcntl
                installer.state.mkdir(parents=True, exist_ok=True, mode=0o700)
                lock = stack.enter_context((installer.state / 'deployment.lock').open('a'))
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise DeployError('Another installer is already running for this server account.') from None
            installer.execute()
    except (DeployError, OSError, ValueError, KeyError, EOFError, KeyboardInterrupt) as exc:
        print(f'\nSTOPPED during: {installer.stage}', file=sys.stderr)
        print(str(exc) if not isinstance(exc, KeyboardInterrupt) else 'Interrupted.', file=sys.stderr)
        if installer.backup:
            print(f'Existing data was not deleted. Backup: {installer.backup}', file=sys.stderr)
        print('Read the failure details above before trying again.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
