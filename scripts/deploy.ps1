param(
    [string]$Server = '172.20.48.28',
    [string]$User = 'eduard.almar@local.eurecat.org',
    [switch]$Check,
    [switch]$UploadOnly,
    [switch]$PackageOnly
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$packageDir = Join-Path $repoRoot 'data/deployment'
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
$package = Join-Path $packageDir 'injection-monitoring.tar.gz'
$files = @(
    'iot', 'scripts/deploy_server.py', 'scripts/apply_server_migrations.sh',
    'scripts/backup_server_metadata.sh', 'scripts/check_server_ingestion.sh',
    'scripts/diagnose_influxdb.py', 'scripts/build_legacy_catalog.py',
    'scripts/prepare_stack_test.py', 'tests/check_stack.py', 'cycle_metadata.py'
)
# Explicit list: no .env, PC recordings, credentials, node_modules or Python caches.
# USTAR omits Windows file flags (SCHILY.fflags) that Linux tar cannot use.
& tar --format=ustar --exclude=__pycache__ --exclude=*.pyc -czf $package -C $repoRoot @files
if ($LASTEXITCODE -ne 0) { throw 'Could not build deployment archive.' }
if ($PackageOnly) { Write-Host "Prepared $package"; return }
& scp -o "User=$User" $package "${Server}:injection-monitoring.tar.gz"
if ($LASTEXITCODE -ne 0) { throw 'Upload failed; the installer did not run on this attempt. Earlier server changes remain in place.' }
# Never extract over a previous upload: it may contain read-only directories
# inherited from Windows/OneDrive. Delay restoring directory modes until every
# member is extracted, then grant the owner access only inside this fresh tree.
$remote = @'
set -eu
umask 077
mkdir -p "$HOME/injection-monitoring-releases"
deploy_stage=$(mktemp -d "$HOME/injection-monitoring-releases/release.XXXXXXXX")
tar --no-same-owner --no-same-permissions --delay-directory-restore -xzf "$HOME/injection-monitoring.tar.gz" -C "$deploy_stage"
chmod -R u+rwX "$deploy_stage"
printf 'Deployment files: %s\n' "$deploy_stage"
cd "$deploy_stage"
'@
if (-not $UploadOnly) {
    $remote += "`nexec bash iot/deploy.sh"
    if ($Check) { $remote += ' --check' }
    # The bootstrap travels over a pipe; restore the SSH terminal for prompts.
    $remote += ' < /dev/tty'
} else {
    $remote += @'

printf "In your server terminal run: cd '%s' && bash iot/deploy.sh\n" "$deploy_stage"
'@
}
# Transport literal shell code without Windows PowerShell/OpenSSH re-quoting it.
$bootstrap = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remote.Replace("`r", '')))
& ssh -t -l $User $Server "printf %s $bootstrap | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw 'Server step stopped. Read its message before rerunning.' }
