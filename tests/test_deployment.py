"""Deployment safety checks; no Docker/server access and no application imports."""
from copy import deepcopy
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from scripts import deploy_server as deploy
from scripts.diagnose_influxdb import response_rows
import check_stack


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.args = SimpleNamespace(check=False, state_dir=self.directory.name,
            nodered_url='http://127.0.0.1:1880', grafana_url='http://127.0.0.1:3000')
        self.installer = deploy.Installer(self.args)
        self.template = self.installer.template
        self.current = deepcopy(self.template)

    def test_flow_update_preserves_other_tabs_broker_identity_and_auth(self):
        broker = next(n for n in self.current if n['type'] == 'mqtt-broker')
        broker.update(id='actual-broker', broker='real-broker', clientid='stable-existing-id', usetls=True, tls='tls-config')
        next(n for n in self.current if n['type'] == 'mqtt in')['broker'] = 'actual-broker'
        http = next(n for n in self.current if n['id'] == 'cycle-http')
        http['authType'] = 'basic'
        other = [{'id': 'another-tab', 'type': 'tab'},
                 {'id': 'another-node', 'type': 'function', 'z': 'another-tab', 'func': 'return msg;'},
                 {'id': 'tls-config', 'type': 'tls-config', 'verifyservercert': True}]
        self.current += other
        before = deepcopy(self.current)
        merged = deploy.merge_flows(self.current, self.template)
        self.assertEqual(self.current, before)
        for node in other:
            self.assertIn(node, merged)
        self.assertEqual(next(n for n in merged if n['type'] == 'mqtt-broker'), broker)
        self.assertEqual(next(n for n in merged if n['type'] == 'mqtt in')['broker'], 'actual-broker')
        self.assertEqual(next(n for n in merged if n['id'] == 'cycle-http')['authType'], 'basic')
        self.assertEqual(deploy.merge_flows(merged, self.template), merged)

    def test_duplicate_subscriber_and_id_collision_are_rejected(self):
        duplicate = self.current + [{'id': 'duplicate', 'type': 'mqtt in', 'z': 'other', 'topic': '+/sensors'}]
        with self.assertRaisesRegex(deploy.DeployError, 'Another tab'):
            deploy.merge_flows(duplicate, self.template)
        colliding = [n for n in self.current if n['id'] != 'cycle-enqueue']
        colliding.append({'id': 'cycle-enqueue', 'type': 'function', 'z': 'other'})
        with self.assertRaisesRegex(deploy.DeployError, 'collision'):
            deploy.merge_flows(colliding, self.template)

    def test_shared_broker_cannot_be_changed_to_persistent_implicitly(self):
        broker = next(n for n in self.current if n['type'] == 'mqtt-broker')
        broker['cleansession'] = True
        self.current.append({'id': 'other', 'type': 'mqtt out', 'broker': broker['id'], 'z': 'unrelated'})
        with self.assertRaisesRegex(deploy.DeployError, 'shared'):
            deploy.merge_flows(self.current, self.template)

    def test_dashboard_mapping_includes_nested_export_and_preserves_version(self):
        before = deepcopy(self.installer.dashboard)
        mapped = deploy.mapped_dashboard(before, 'actual-influx', {'id': 7, 'version': 4, 'time': {'from': 'now-2d', 'to': 'now'}})
        def visit(value):
            if isinstance(value, dict):
                ds = value.get('datasource')
                if isinstance(ds, dict) and ds.get('type') == 'influxdb':
                    self.assertEqual(ds['uid'], 'actual-influx')
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(mapped)
        self.assertEqual(mapped['id'], 7)
        self.assertEqual(mapped['version'], 4)
        self.assertEqual(mapped['time'], before['time'])
        self.assertEqual(self.installer.dashboard, before)

    def test_check_mode_does_not_create_state_or_run_mutations(self):
        self.installer.args.check = True
        self.installer.state = Path(self.directory.name) / 'not-created'
        with patch.object(self.installer, 'preflight') as check, \
             patch.object(self.installer, 'backups') as backup:
            self.installer.execute()
        check.assert_called_once()
        backup.assert_not_called()
        self.assertFalse(self.installer.state.exists())

    def test_influx_cli_envelope_is_read_by_installer_and_stack_check(self):
        document = {'results': [{'statement_id': 0, 'series': [{
            'name': 'sensor_data', 'columns': ['time', 'count'],
            'values': [['1970-01-01T00:00:00Z', 1602]]}]}]}
        expected = [{'time': '1970-01-01T00:00:00Z', 'count': 1602}]
        with patch('scripts.deploy_server.run', return_value=json.dumps(document)):
            self.assertEqual(self.installer.influx_count(), expected)
        with patch.object(check_stack, 'command', return_value=json.dumps(document)):
            self.assertEqual(check_stack.influx('SELECT count("t_ms") FROM sensor_data'), expected)

    def test_empty_influx_measurement_is_valid_and_count_changes_remain_visible(self):
        with patch('scripts.deploy_server.run', return_value='{"results":[{"statement_id":0}]}'):
            self.assertEqual(self.installer.influx_count(), [])
        responses = [json.dumps({'results': [{'series': [{'columns': ['time', 'count'],
                      'values': [[0, count]]}]}]}) for count in (1602, 1603)]
        with patch('scripts.deploy_server.run', side_effect=responses):
            self.assertNotEqual(self.installer.influx_count(), self.installer.influx_count())

    def test_influx_errors_and_malformed_output_stop_both_consumers(self):
        documents = [{'error': 'authorization failed'},
                     {'results': [{'error': 'database not found'}]},
                     {'results': [{}, {'error': 'later statement failed'}]},
                     [], None, {}, {'results': 'not an array'},
                     {'results': ['not an object']},
                     {'results': [{'series': 'not an array'}]},
                     {'results': [{'series': ['not an object']}]},
                     {'results': [{'series': [{'columns': 'count', 'values': [[1]]}]}]},
                     {'results': [{'series': [{'columns': ['count'], 'values': [[1, 2]]}]}]}]
        for document in documents:
            with self.subTest(document=document):
                with patch('scripts.deploy_server.run', return_value=json.dumps(document)):
                    with self.assertRaisesRegex(deploy.DeployError, 'Influx read check failed'):
                        self.installer.influx_count()
                with patch.object(check_stack, 'command', return_value=json.dumps(document)):
                    with self.assertRaises(RuntimeError):
                        check_stack.influx('SELECT count("t_ms") FROM sensor_data')
        with patch('scripts.deploy_server.run', return_value='not JSON'):
            with self.assertRaisesRegex(deploy.DeployError, 'Influx read check failed'):
                self.installer.influx_count()

    def test_influx_diagnostic_retains_tags_and_chunk_rows(self):
        document = {'results': [{'statement_id': 0, 'partial': True, 'series': [{
            'tags': {'machine_id': '160t'}, 'columns': ['time', 't_ms'],
            'values': [[1785838969691369500, 0], [1785838969701369500, 10]]}]}]}
        self.assertEqual(list(response_rows(document)), [
            {'machine_id': '160t', 'time': 1785838969691369500, 't_ms': 0},
            {'machine_id': '160t', 'time': 1785838969701369500, 't_ms': 10}])

    def test_influx_preflight_error_prevents_container_test_and_backups(self):
        with patch.object(self.installer, 'preflight', side_effect=self.installer.influx_count), \
             patch('scripts.deploy_server.run', return_value='{"error":"authorization failed"}'), \
             patch.object(self.installer, 'validate_stack') as validate, \
             patch.object(self.installer, 'backups') as backup:
            with self.assertRaisesRegex(deploy.DeployError, 'authorization failed'):
                self.installer.execute()
        validate.assert_not_called()
        backup.assert_not_called()

    def test_backup_failure_prevents_schema_and_app_changes(self):
        with patch.object(self.installer, 'preflight'), \
             patch.object(self.installer, 'validate_stack'), \
             patch.object(self.installer, 'influx_count', return_value=[]), \
             patch.object(self.installer, 'backups', side_effect=deploy.DeployError('disk full')), \
             patch.object(self.installer, 'migrate') as migrate, \
             patch.object(self.installer, 'node_red') as node_red:
            with self.assertRaisesRegex(deploy.DeployError, 'disk full'):
                self.installer.execute()
        migrate.assert_not_called()
        node_red.assert_not_called()

    def test_password_creation_survives_interruption_without_rotating_existing_roles(self):
        self.installer.roles = set()
        self.installer.credentials()
        original = deepcopy(self.installer.creds)
        self.assertEqual(len(original), 2)
        # Simulate SQL schema creation succeeding but setting passwords failing.
        retry = deploy.Installer(self.args)
        retry.roles = {'monitoring_ingest', 'monitoring_reader'}
        with patch('scripts.deploy_server.getpass.getpass', side_effect=AssertionError('Must reuse saved passwords')), \
             patch('scripts.deploy_server.run'), patch('scripts.deploy_server.sql') as sql:
            retry.migrate()
        self.assertEqual(retry.creds, original)
        self.assertEqual(sql.call_count, 2)
        with patch('scripts.deploy_server.run'), patch('scripts.deploy_server.sql') as sql:
            retry.migrate()
        sql.assert_not_called()
        self.assertEqual(retry.creds, original)

    def test_existing_role_passwords_are_never_reset(self):
        self.installer.roles = {'monitoring_ingest', 'monitoring_reader'}
        with patch('scripts.deploy_server.getpass.getpass', side_effect=['existing-one', 'existing-two']), \
             patch('scripts.deploy_server.run'), patch('scripts.deploy_server.sql') as sql:
            self.installer.migrate()
        sql.assert_not_called()
        self.assertEqual(self.installer.creds['monitoring_ingest'], 'existing-one')

    def test_settings_extension_preserves_original_settings(self):
        source = "module.exports={credentialSecret:'keep-me',adminAuth:{type:'credentials'},functionGlobalContext:{other:42}};"
        # Execute actual JavaScript using a harmless stub for the queue module.
        addon = deploy.SETTINGS_ADDON.replace("require('/data/lib/capture_queue.cjs')", '({queue: true})')
        result = subprocess.run(['node', '-e', source + addon + ';console.log(JSON.stringify(module.exports));'],
            capture_output=True, text=True, check=True)
        settings = json.loads(result.stdout)
        self.assertEqual(settings['credentialSecret'], 'keep-me')
        self.assertEqual(settings['adminAuth']['type'], 'credentials')
        self.assertEqual(settings['functionGlobalContext']['other'], 42)

    def test_admin_api_refuses_remote_plaintext_and_cross_host_redirects(self):
        with self.assertRaisesRegex(deploy.DeployError, 'HTTPS'):
            deploy.API('http://untrusted.example:1880')
        with self.assertRaisesRegex(deploy.DeployError, 'not forwarded'):
            deploy.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.example')

    def test_api_posts_node_red_revision_and_credentials_as_json(self):
        api = deploy.API('http://localhost:1880')
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"rev":"new"}'
        api.opener = Mock()
        api.opener.open.return_value = response
        body = {'rev': 'old', 'flows': [], 'credentials': {'pg': {'password': 'secret'}}}
        self.assertEqual(api.request('POST', '/flows', body,
            headers={'Node-RED-API-Version': 'v2'}), {'rev': 'new'})
        request = api.opener.open.call_args.args[0]
        self.assertEqual(json.loads(request.data), body)
        self.assertNotIn('secret', request.full_url)

    def test_api_read_recovers_from_reset_disconnect_and_truncated_response(self):
        failures = [ConnectionResetError(104, 'Connection reset by peer'),
                    http.client.RemoteDisconnected('closed during startup'),
                    http.client.IncompleteRead(b'{', 100)]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                api = deploy.API('http://localhost:1880')
                response = Mock()
                response.__enter__ = Mock(return_value=response)
                response.__exit__ = Mock(return_value=False)
                response.read.side_effect = [failure, b'{"ready":true}']
                api.opener.open = Mock(return_value=response)
                with patch('scripts.deploy_server.time.sleep'):
                    self.assertEqual(api.read('/settings'), {'ready': True})
                self.assertEqual(api.opener.open.call_count, 2)

    def test_api_read_retries_startup_http_errors_but_not_access_errors(self):
        api = deploy.API('http://localhost:1880')
        with patch.object(api, 'request', side_effect=[deploy.APIError(503, '/settings'), {}]) as request, \
             patch('scripts.deploy_server.time.sleep'):
            self.assertEqual(api.read('/settings'), {})
        self.assertEqual(request.call_count, 2)
        for status in (401, 403, 404, 409):
            with self.subTest(status=status), \
                 patch.object(api, 'request', side_effect=deploy.APIError(status, '/settings')) as request, \
                 patch('scripts.deploy_server.time.sleep') as sleep:
                with self.assertRaises(deploy.APIError):
                    api.read('/settings')
                request.assert_called_once()
                sleep.assert_not_called()

    def test_api_read_stops_at_deadline_with_endpoint_in_error(self):
        api = deploy.API('http://localhost:1880')
        with patch.object(api, 'request', side_effect=deploy.APIConnectionError('connection reset')) as request, \
             patch('scripts.deploy_server.time.monotonic', side_effect=[0, 0, 30]), \
             patch('scripts.deploy_server.time.sleep') as sleep:
            with self.assertRaisesRegex(deploy.DeployError, 'Timed out after 30s.*localhost:1880/settings'):
                api.read('/settings')
        request.assert_called_once()
        sleep.assert_not_called()

    def test_api_write_is_not_repeated_when_response_is_lost(self):
        api = deploy.API('http://localhost:1880')
        api.opener.open = Mock(side_effect=ConnectionResetError(104, 'Connection reset by peer'))
        with self.assertRaisesRegex(deploy.APIConnectionError, 'POST.*localhost:1880/flows'):
            api.request('POST', '/flows', {'credentials': {'password': 'not-for-logs'}})
        api.opener.open.assert_called_once()

    def test_resume_after_restart_survives_real_http_disconnects(self):
        """Actual localhost HTTP with closed connections; no Docker/server access."""
        state = {'flows': deepcopy(self.current), 'counts': {}, 'posts': []}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                count = state['counts'][self.path] = state['counts'].get(self.path, 0) + 1
                # Each endpoint disconnects once, including the read after POST.
                if count == 1 or (self.path == '/flows' and count == 3):
                    self.close_connection = True
                    return
                if self.path == '/settings':
                    value = {'version': '4.0.9'}
                elif self.path == '/nodes':
                    value = [{'module': deploy.CONNECTOR, 'version': '0.16.2', 'enabled': True}]
                elif self.path == '/flows':
                    value = {'rev': 'after' if state['posts'] else 'before', 'flows': state['flows']}
                else:
                    raise AssertionError(self.path)
                self.respond(value)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                state['posts'].append(body)
                state['flows'] = body['flows']
                self.respond({'rev': 'after'})

            def respond(self, value):
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.installer.nr = deploy.API(f'http://127.0.0.1:{server.server_port}')
            self.installer.settings = 'module.exports={};' + deploy.SETTINGS_ADDON
            self.installer.install_connector = False
            self.installer.flows = {'rev': 'before', 'flows': self.current}
            self.installer.creds = {'monitoring_ingest': 'saved-password'}
            pending = self.installer.state / 'runtime-update-pending.json'
            deploy.save_private(pending, {'restart_required': True})
            queue = (deploy.ROOT / 'iot/nodered/capture_queue.cjs').read_text(encoding='utf-8').strip()
            with patch('scripts.deploy_server.run', return_value=queue) as run, \
                 patch('scripts.deploy_server.time.sleep'):
                self.installer.node_red()
            self.assertFalse(pending.exists())
            self.assertEqual(len(state['posts']), 1)
            self.assertEqual(state['posts'][0]['rev'], 'before')
            self.assertEqual(state['posts'][0]['credentials']['cycle-postgres-config']['password'], 'saved-password')
            self.assertEqual(state['counts'], {'/settings': 2, '/flows': 4, '/nodes': 2})
            self.assertEqual(sum(c.args[0] == ['docker', 'restart', 'nodered'] for c in run.call_args_list), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_failed_restart_retains_recovery_marker_and_does_not_deploy_flow(self):
        self.installer.settings = 'module.exports={};' + deploy.SETTINGS_ADDON
        self.installer.install_connector = False
        pending = self.installer.state / 'runtime-update-pending.json'
        deploy.save_private(pending, {'restart_required': True})
        queue = (deploy.ROOT / 'iot/nodered/capture_queue.cjs').read_text(encoding='utf-8').strip()
        with patch('scripts.deploy_server.run', return_value=queue), \
             patch.object(self.installer.nr, 'read', side_effect=deploy.DeployError('Timed out')) as read, \
             patch.object(self.installer.nr, 'request') as request:
            with self.assertRaisesRegex(deploy.DeployError, 'Timed out'):
                self.installer.node_red()
        self.assertTrue(pending.exists())
        read.assert_called_once_with('/settings', timeout=90)
        request.assert_not_called()

    def test_health_failure_prevents_success_marker(self):
        for method in ('preflight', 'validate_stack', 'backups', 'migrate', 'history', 'node_red', 'grafana'):
            p = patch.object(self.installer, method)
            p.start()
            self.addCleanup(p.stop)
        with patch.object(self.installer, 'influx_count', return_value=[]), \
             patch.object(self.installer, 'verify', side_effect=deploy.DeployError('failed health')):
            with self.assertRaisesRegex(deploy.DeployError, 'failed health'):
                self.installer.execute()
        self.assertFalse((self.installer.state / 'last-success.json').exists())

    def test_verification_runs_connection_probe_with_secret_on_stdin(self):
        self.installer.influx_source = {'uid': 'existing-influx'}
        self.installer.gf.request = Mock(return_value={'status': 'OK'})
        self.installer.creds = {'monitoring_ingest': 'private-test-password'}
        self.installer.before_count = [{'count': 45447}]
        with patch('scripts.deploy_server.run', return_value='OK') as run, \
             patch.object(self.installer, 'influx_count', return_value=self.installer.before_count):
            self.installer.verify()
        probe, health = run.call_args_list
        self.assertEqual(probe.args[0][:6], ['docker', 'exec', '-i', 'nodered', 'node', '-e'])
        self.assertEqual(probe.args[0][6], deploy.POSTGRES_CONNECTION_CHECK)
        self.assertEqual(probe.args[0][-2:], ['/data', '/usr/src/node-red'])
        self.assertNotIn('private-test-password', ' '.join(probe.args[0]))
        self.assertEqual(json.loads(probe.args[1]), 'private-test-password')
        self.assertFalse(probe.kwargs.get('sensitive', False))  # Only sanitized probe errors are printed.
        self.assertEqual(health.args[0][0], 'bash')

    def test_postgres_probe_failure_stops_verification_with_useful_code(self):
        self.installer.influx_source = {'uid': 'existing-influx'}
        self.installer.gf.request = Mock(return_value={'status': 'OK'})
        self.installer.creds = {'monitoring_ingest': 'private-test-password'}
        with patch('scripts.deploy_server.run', side_effect=deploy.DeployError(
                'Node-RED PostgreSQL check failed while connecting to postgres as monitoring_ingest [28P01].')) as run, \
             patch.object(self.installer, 'influx_count') as count:
            with self.assertRaisesRegex(deploy.DeployError, 'connecting.*28P01'):
                self.installer.verify()
        run.assert_called_once()
        count.assert_not_called()

    def test_rerun_reuses_runtime_but_posts_revision_and_only_app_credentials(self):
        self.installer.settings = 'module.exports = {};\n' + deploy.SETTINGS_ADDON
        self.installer.install_connector = False
        self.installer.creds = {'monitoring_ingest': 'generated-password'}
        self.installer.flows = {'rev': 'before', 'flows': self.current}
        requests = []
        def api(method, path, data=None, **kwargs):
            requests.append((method, path, data, kwargs))
            if path == '/nodes':
                return [{'module': deploy.CONNECTOR, 'enabled': True, 'version': '0.16.2'}]
            if method == 'GET' and path == '/flows':
                return {'rev': 'current', 'flows': self.current}
            if method == 'POST' and path == '/flows':
                return {'rev': 'after'}
            raise AssertionError((method, path))
        self.installer.nr.request = api
        queue = (deploy.ROOT / 'iot/nodered/capture_queue.cjs').read_text(encoding='utf-8').strip()
        with patch('scripts.deploy_server.run', side_effect=lambda args, **kwargs: queue if '-e' in args else '') as run, \
             patch.object(self.installer, 'write_container') as write:
            self.installer.node_red()
        self.assertFalse(any('restart' in call.args[0] or 'npm' in call.args[0] for call in run.call_args_list))
        write.assert_not_called()
        posts = [r for r in requests if r[0] == 'POST']
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][2]['rev'], 'current')
        self.assertEqual(posts[0][2]['credentials'], {'cycle-postgres-config':
            {'user': 'monitoring_ingest', 'password': 'generated-password'}})
        self.assertEqual(posts[0][3]['headers']['Node-RED-Deployment-Type'], 'flows')

    def test_concurrent_flow_edit_stops_before_post(self):
        self.installer.settings = 'module.exports={};' + deploy.SETTINGS_ADDON
        self.installer.install_connector = False
        self.installer.flows = {'rev': 'before', 'flows': self.current}
        changed = self.current + [{'id': 'new-other-tab', 'type': 'tab'}]
        self.installer.nr.request = Mock(side_effect=[{'rev': 'new', 'flows': changed},
            [{'module': deploy.CONNECTOR, 'enabled': True, 'version': '0.16.2'}]])
        queue = (deploy.ROOT / 'iot/nodered/capture_queue.cjs').read_text(encoding='utf-8').strip()
        with patch('scripts.deploy_server.run', return_value=queue):
            with self.assertRaisesRegex(deploy.DeployError, 'flows changed'):
                self.installer.node_red()
        self.assertFalse(any(c.args[0] == 'POST' for c in self.installer.nr.request.call_args_list))

    def test_grafana_posts_credentials_securely_and_preserves_folder_revision(self):
        self.installer.sources = []
        self.installer.creds = {'monitoring_reader': 'reader-secret'}
        self.installer.influx_source = {'uid': 'existing-influx'}
        self.installer.previous_dashboard = {'dashboard': {'id': 3, 'version': 9}, 'meta': {'folderUid': 'lab-folder'}}
        self.installer.gf.request = Mock(side_effect=[deploy.APIError(404, '/api/datasources/uid/' + deploy.PG_UID), {}, {}, {}])
        self.installer.grafana()
        calls = self.installer.gf.request.call_args_list
        self.assertEqual(calls[0].args[:2], ('GET', '/api/datasources/uid/' + deploy.PG_UID))
        self.assertEqual(calls[1].args[:2], ('POST', '/api/datasources'))
        source = calls[1].args[2]
        self.assertEqual(source['secureJsonData']['password'], 'reader-secret')
        self.assertNotIn('password', source)
        body = calls[2].args[2]
        self.assertFalse(body['overwrite'])
        self.assertEqual(body['folderUid'], 'lab-folder')
        self.assertEqual(body['dashboard']['version'], 9)

    def test_grafana_repeated_updates_use_latest_detail_version_not_list_summary(self):
        self.installer.sources = [{'uid': deploy.PG_UID, 'type': 'grafana-postgresql-datasource',
                                   'user': 'monitoring_reader'}]  # Grafana 12 list has no version.
        self.installer.creds = {'monitoring_reader': 'reader-secret'}
        self.installer.influx_source = {'uid': 'existing-influx'}
        self.installer.previous_dashboard = None
        state = {'version': 7, 'updates': []}
        def request(method, path, data=None, **kwargs):
            if path == '/api/datasources/uid/' + deploy.PG_UID:
                if method == 'GET':
                    return dict(self.installer.sources[0], version=state['version'], readOnly=False)
                self.assertEqual(method, 'PUT')
                if data.get('version') != state['version']:
                    raise deploy.APIError(409, path)
                state['updates'].append(deepcopy(data))
                state['version'] += 1
            elif path.startswith('/api/dashboards'):
                return {}
            else:
                raise AssertionError((method, path))
            return {}
        self.installer.gf.request = request
        for _ in range(3):
            self.installer.grafana()
        self.assertEqual([d['version'] for d in state['updates']], [7, 8, 9])
        self.assertTrue(all(d['secureJsonData'] == {'password': 'reader-secret'} for d in state['updates']))
        self.assertNotIn('version', self.installer.sources[0])

    def test_grafana_update_refuses_missing_version_or_foreign_datasource(self):
        valid = {'uid': deploy.PG_UID, 'type': 'grafana-postgresql-datasource',
                 'user': 'monitoring_reader', 'version': 3, 'readOnly': False}
        for changes in ({'version': None}, {'version': 0}, {'version': '3'}, {'version': True},
                        {'readOnly': True}, {'type': 'influxdb'}, {'user': 'other-user'}):
            with self.subTest(changes=changes):
                api = deploy.API('http://127.0.0.1:3000')
                api.request = Mock(return_value=dict(valid, **changes))
                with self.assertRaises(deploy.DeployError):
                    deploy.configure_postgres_datasource(api, 'reader-secret')
                api.request.assert_called_once()

    def test_grafana_concurrent_update_stops_without_forced_retry_or_dashboard_write(self):
        self.installer.creds = {'monitoring_reader': 'reader-secret'}
        self.installer.gf.request = Mock(side_effect=[{
            'uid': deploy.PG_UID, 'type': 'grafana-postgresql-datasource',
            'user': 'monitoring_reader', 'version': 4},
            deploy.APIError(409, '/api/datasources/uid/' + deploy.PG_UID)])
        with self.assertRaisesRegex(deploy.APIError, 'Update conflict') as caught:
            self.installer.grafana()
        self.assertNotIn('credentials', str(caught.exception))
        self.assertEqual(self.installer.gf.request.call_count, 2)
        self.assertEqual(self.installer.gf.request.call_args.args[2]['version'], 4)

    def test_cron_reruns_preserve_other_jobs_and_replace_only_managed_block(self):
        self.installer.backup = Path(self.directory.name) / 'backup'
        self.installer.backup.mkdir()
        unrelated = '15 * * * * /home/lab/unrelated-backup\n'
        existing = unrelated + '# BEGIN injection-monitoring\nold job\n# END injection-monitoring\n'
        with patch('scripts.deploy_server.shutil.which', return_value='/usr/bin/crontab'), \
             patch('scripts.deploy_server.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=existing, stderr='')), \
             patch('scripts.deploy_server.run') as run:
            self.installer.maintenance()
        generated = run.call_args.args[1].decode()
        self.assertIn(unrelated, generated)
        self.assertNotIn('old job', generated)
        self.assertEqual(generated.count('# BEGIN injection-monitoring'), 1)
        self.assertIn('0 2 * * *', generated)

    def test_interrupted_runtime_update_forces_restart_even_when_files_match(self):
        self.installer.settings = 'module.exports={};' + deploy.SETTINGS_ADDON
        self.installer.install_connector = False
        self.installer.flows = {'rev': 'before', 'flows': self.current}
        self.installer.creds = {'monitoring_ingest': 'saved-password'}
        pending = self.installer.state / 'runtime-update-pending.json'
        deploy.save_private(pending, {'restart_required': True})
        self.installer.nr.request = Mock(side_effect=[{'rev': 'before', 'flows': self.current},
            [{'module': deploy.CONNECTOR, 'enabled': True, 'version': '0.16.2'}],
            {'rev': 'after'}, {'rev': 'after', 'flows': self.current}])
        queue = (deploy.ROOT / 'iot/nodered/capture_queue.cjs').read_text(encoding='utf-8').strip()
        with patch('scripts.deploy_server.run', return_value=queue) as run, \
             patch.object(self.installer, 'wait_node_red'):
            self.installer.node_red()
        self.assertTrue(any(c.args[0] == ['docker', 'restart', 'nodered'] for c in run.call_args_list))
        self.assertFalse(pending.exists())

    def test_container_test_receipt_skips_only_the_same_release(self):
        with patch('scripts.deploy_server.run', return_value='') as run:
            self.installer.validate_stack()
        self.assertTrue(any('up' in c.args[0] for c in run.call_args_list))
        self.assertTrue(any('down' in c.args[0] for c in run.call_args_list))
        self.assertTrue((self.installer.state / 'validated-release.json').exists())
        with patch('scripts.deploy_server.run') as run:
            self.installer.validate_stack()
        run.assert_not_called()
        with patch('scripts.deploy_server.POSTGRES_CONNECTION_CHECK', 'changed probe'), \
             patch('scripts.deploy_server.run', return_value='') as run:
            self.installer.validate_stack()
        self.assertTrue(any('up' in c.args[0] for c in run.call_args_list))

    def test_failed_container_validation_tears_down_only_test_project_and_blocks_deploy(self):
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            if any(str(a).endswith('check_stack.py') for a in args):
                raise deploy.DeployError('test failed')
            if 'ps' in args:
                return 'test-grafana exited (1)'
            if 'logs' in args:
                return 'test-grafana: startup failure details'
            return ''
        with patch('scripts.deploy_server.run', side_effect=runner):
            with self.assertRaisesRegex(deploy.DeployError, 'Production was not changed') as failure:
                self.installer.validate_stack()
        self.assertIn('test failed', str(failure.exception))
        self.assertIn('Full test log', str(failure.exception))
        log = (self.installer.state / 'validation.log').read_text()
        self.assertIn('test failed', log)
        self.assertIn('test-grafana exited (1)', log)
        self.assertIn('test-grafana: startup failure details', log)
        downs = [c for c in calls if 'down' in c]
        self.assertEqual(len(downs), 1)
        self.assertIn('monitoring-metadata-test', downs[0])
        self.assertNotIn('--volumes', downs[0])
        for command in ('ps', 'logs'):
            diagnostic = next(c for c in calls if command in c)
            self.assertIn('monitoring-metadata-test', diagnostic)
            self.assertLess(calls.index(diagnostic), calls.index(downs[0]))
        self.assertFalse((self.installer.state / 'validated-release.json').exists())

    def test_diagnostic_and_cleanup_failures_preserve_original_test_error(self):
        def runner(args, **kwargs):
            if any(str(a).endswith('check_stack.py') for a in args):
                raise deploy.DeployError('original Grafana readiness failure')
            if any(a in args for a in ('ps', 'logs', 'down')):
                raise deploy.DeployError('Docker unavailable during diagnostics/cleanup')
            return ''
        with patch('scripts.deploy_server.run', side_effect=runner):
            with self.assertRaisesRegex(deploy.DeployError, 'original Grafana readiness failure') as failure:
                self.installer.validate_stack()
        self.assertIn('Test cleanup failed', str(failure.exception))
        self.assertIn('Docker unavailable', (self.installer.state / 'validation.log').read_text())
        self.assertFalse((self.installer.state / 'validated-release.json').exists())


class PostgresProbeTests(unittest.TestCase):
    """Run the actual Node program against packages with Node-RED's layout.

    Module resolution is real; the pg client is a stub so no network is used.
    """
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.package = self.root / 'node_modules/node-red-contrib-postgresql'
        self.package.mkdir(parents=True)
        # Like connector 0.16.2: only node-red.nodes, no main or index.js.
        (self.package / 'package.json').write_text(json.dumps({
            'name': 'node-red-contrib-postgresql', 'version': '0.16.2',
            'node-red': {'nodes': {'postgresql': 'postgresql.js'}}}), encoding='utf-8')
        (self.package / 'postgresql.js').write_text("throw Error('Must not load the Node-RED node itself');", encoding='utf-8')

    def run_probe(self, body, nested=False):
        pg = (self.package if nested else self.root) / 'node_modules/pg'
        pg.mkdir(parents=True, exist_ok=True)
        (pg / 'index.js').write_text(body, encoding='utf-8')
        return subprocess.run(['node', '-e', deploy.POSTGRES_CONNECTION_CHECK, str(self.root)],
            input=json.dumps('synthetic-secret'), capture_output=True, text=True, timeout=15)

    def test_manifest_lookup_supports_connector_without_main_and_hoisted_driver(self):
        old = subprocess.run(['node', '-e', "require.resolve('node-red-contrib-postgresql',{paths:[process.argv[1]]})",
                              str(self.root)], capture_output=True, text=True)
        self.assertNotEqual(old.returncode, 0)
        self.assertIn('MODULE_NOT_FOUND', old.stderr)
        result = self.run_probe("""exports.Client=class {
constructor(c) { if(c.host!=='postgres'||c.database!=='injection_monitoring'||
c.user!=='monitoring_ingest'||c.password!=='synthetic-secret') throw Error('bad options'); }
async connect() {} async query(q) { if(q!=='SELECT 1') throw Error('not a read check'); }
async end() {}
};""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('connection passed', result.stdout)

    def test_manifest_lookup_supports_nested_driver(self):
        result = self.run_probe('exports.Client=class {async connect(){} async query(){} async end(){}};', nested=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_database_failures_report_phase_and_code_without_secret(self):
        for method, code, phase in [('connect', '28P01', 'connecting'),
                                    ('connect', 'ECONNREFUSED', 'connecting'),
                                    ('connect', 'ENOTFOUND', 'connecting'),
                                    ('query', '42501', 'running SELECT 1')]:
            with self.subTest(code=code):
                result = self.run_probe('exports.Client=class { constructor(c){this.secret=c.password;} '
                    'async connect(){} async query(){} async end(){} async ' + method +
                    '(){throw Object.assign(new Error(this.secret),{code:' + json.dumps(code) + '});}};')
                self.assertEqual(result.returncode, 1)
                self.assertIn(phase, result.stderr)
                self.assertIn('[' + code + ']', result.stderr)
                self.assertNotIn('synthetic-secret', result.stderr + result.stdout)

    def test_missing_driver_reports_module_error_without_stack(self):
        result = subprocess.run(['node', '-e', deploy.POSTGRES_CONNECTION_CHECK, str(self.root)],
            input=json.dumps('synthetic-secret'), capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn('loading the connector PostgreSQL driver [MODULE_NOT_FOUND]', result.stderr)
        self.assertNotIn('Require stack', result.stderr)
        self.assertNotIn('synthetic-secret', result.stderr + result.stdout)


if __name__ == '__main__':
    unittest.main()
