"""Exercise the real Windows packager; SSH/SCP are replaced before it runs.

The extraction check uses local WSL Ubuntu as an ordinary Linux user. It never
connects to the server, runs Docker, or invokes the production installer.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt' and shutil.which('powershell'), 'Windows PowerShell required')
class UploadTests(unittest.TestCase):
    def bootstrap(self, destination, *flags):
        command_file = destination / 'ssh-command.txt'
        env = dict(os.environ, DEPLOY_TEST_COMMAND=str(command_file),
                   DEPLOY_TEST_SCRIPT=str(ROOT / 'scripts/deploy.ps1'))
        # Function names take precedence over external programs in PowerShell.
        harness = '''
function scp { $global:LASTEXITCODE = 0 }
function ssh {
    [IO.File]::WriteAllText($env:DEPLOY_TEST_COMMAND, $args[-1])
    $global:LASTEXITCODE = 0
}
& $env:DEPLOY_TEST_SCRIPT ''' + ' '.join(flags)
        subprocess.run(['powershell', '-NoProfile', '-NonInteractive',
                        '-ExecutionPolicy', 'Bypass', '-Command', harness],
                       env=env, capture_output=True, text=True, check=True)
        return command_file.read_text(encoding='utf-8-sig')

    def test_archive_omits_windows_flags_caches_and_local_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            command = self.bootstrap(Path(temporary), '-UploadOnly')
        self.assertIn('| base64 -d | bash', command)
        with tarfile.open(ROOT / 'data/deployment/injection-monitoring.tar.gz') as archive:
            members = archive.getmembers()
            self.assertIn('iot/deploy.sh', [m.name for m in members])
            for member in members:
                self.assertFalse(member.pax_headers, member.name)
                self.assertTrue(member.isdir() or member.isfile(), member.name)
                self.assertFalse({'data', '__pycache__', '.env'} & set(Path(member.name).parts))
                self.assertFalse(member.name.endswith('.pyc'))

    @unittest.skipUnless(shutil.which('wsl'), 'Local WSL Ubuntu required')
    def test_linux_extraction_retry_failure_and_interactive_prompt(self):
        probe = subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'true'], capture_output=True)
        if probe.returncode:
            self.skipTest('Local WSL Ubuntu is unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            upload = self.bootstrap(destination, '-UploadOnly')
            check = self.bootstrap(destination, '-Check')
            archive = ROOT / 'data/deployment/injection-monitoring.tar.gz'
            linux_archive = subprocess.check_output(
                ['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-u', str(archive)], text=True).strip()
            # Real GNU tar, permissions, shell quoting and terminal input. The
            # second archive has a harmless stub where the installer would be.
            source = r'''
import io, os, pathlib, shutil, subprocess, sys, tarfile, tempfile
archive, upload, check = sys.argv[1:]
with tempfile.TemporaryDirectory(prefix='monitoring-upload-') as temporary:
    home = pathlib.Path(temporary) / 'home with spaces'
    home.mkdir()
    env = dict(os.environ, HOME=str(home))
    target = home / 'injection-monitoring.tar.gz'
    shutil.copyfile(archive, target)
    old = home / 'injection-monitoring-deploy'
    old.mkdir()
    (old / 'unchanged').write_text('old upload')
    old.chmod(0o500)
    try:
        paths = []
        for _ in range(2):
            result = subprocess.run(['bash', '-c', upload], env=env, capture_output=True, text=True, check=True)
            assert not result.stderr, result.stderr
            stage = pathlib.Path(result.stdout.splitlines()[0].removeprefix('Deployment files: '))
            paths.append(stage)
            assert stage.is_relative_to(home / 'injection-monitoring-releases')
            with tarfile.open(archive) as packed:
                for member in packed:
                    path = stage / member.name
                    assert path.stat().st_mode & 0o200, path
                    if member.isfile():
                        assert path.read_bytes() == packed.extractfile(member).read(), path
            assert (old / 'unchanged').read_text() == 'old upload'
            assert old.stat().st_mode & 0o777 == 0o500
        assert paths[0] != paths[1]
        with tarfile.open(target, 'w:gz', format=tarfile.USTAR_FORMAT) as packed:
            directory = tarfile.TarInfo('iot')
            directory.type, directory.mode = tarfile.DIRTYPE, 0o555
            packed.addfile(directory)
            content = b'printf "Mode: %s\n" "$1"; read -r reply; printf "Reply: %s\n" "$reply"\n'
            member = tarfile.TarInfo('iot/deploy.sh')
            member.mode, member.size = 0o444, len(content)
            packed.addfile(member, io.BytesIO(content))
        result = subprocess.run(['script', '-q', '-e', '-c', check, '/dev/null'],
            env=env, input='test-answer\n', capture_output=True, text=True, timeout=20, check=True)
        assert 'Mode: --check' in result.stdout, result.stdout
        assert 'Reply: test-answer' in result.stdout, result.stdout
        target.write_bytes(b'broken archive')
        result = subprocess.run(['bash', '-c', check], env=env, capture_output=True, text=True)
        assert result.returncode != 0
        assert 'Deployment files:' not in result.stdout
        assert 'Mode:' not in result.stdout
    finally:
        old.chmod(0o700)
print('Linux extraction, repeat upload, failure gating and terminal prompts passed')
'''
            result = subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', '-c',
                                     source, linux_archive, upload, check],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
