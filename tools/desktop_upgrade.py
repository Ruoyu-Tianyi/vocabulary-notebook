"""Local Windows developer upgrade; never restores or uploads personal data."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import maintenance  # noqa: E402


def run(args, **kwargs):
    command = args if isinstance(args, str) else [str(arg) for arg in args]
    return subprocess.run(command, check=kwargs.pop('check', True), **kwargs)


def checked_installer(installer):
    installer = Path(installer).absolute()
    sidecar = Path(str(installer) + '.sha256')
    if installer.is_symlink() or sidecar.is_symlink() or not installer.is_file():
        raise ValueError('安装包和校验文件必须是普通文件')
    match = re.fullmatch(r'([0-9a-fA-F]{64})  (.+)\n?', sidecar.read_text(encoding='utf-8'))
    if not match or match[2] != installer.name or maintenance.digest(installer) != match[1].lower():
        raise ValueError('安装包 SHA-256 校验失败，停止升级')
    return installer


def build(root):
    """Dependencies and artifacts stay inside the checkout; no global installations."""
    python = root / '.venv-desktop/Scripts/python.exe'
    if not python.exists():
        run([sys.executable, '-m', 'venv', python.parents[1]])
    run([python, '-m', 'pip', 'install', '-r', 'requirements-desktop.txt'], cwd=root)
    npm = shutil.which('npm.cmd')
    if not npm:
        raise RuntimeError('需要 Node.js 和 npm 才能构建桌面程序')
    run([npm, '--prefix', 'frontend', 'ci'], cwd=root)
    run([npm, '--prefix', 'desktop', 'ci'], cwd=root)
    run([npm, '--prefix', 'frontend', 'run', 'check'], cwd=root)
    run([npm, '--prefix', 'desktop', 'test'], cwd=root)
    run([sys.executable, '-m', 'ruff', 'check', '.'], cwd=root)
    with tempfile.TemporaryDirectory(prefix='vocove-build-tests-') as directory:
        run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--basetemp', directory], cwd=root)
    run([npm, '--prefix', 'desktop', 'run', 'dist'], cwd=root)
    version = json.loads((root / 'desktop/package.json').read_text(encoding='utf-8'))['version']
    return root / 'desktop/release' / f'Vocove-{version}-win-x64.exe'


def stop_application(executable):
    # Filter by full executable path; never kill by a process name or force termination.
    environment = {**os.environ, 'VOCOVE_UPGRADE_EXE': str(executable)}
    script = """
        $ErrorActionPreference='Stop'
        $target=$env:VOCOVE_UPGRADE_EXE
        $owned=@(Get-CimInstance Win32_Process -Filter "name='Vocove.exe'" |
            Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals($target,[StringComparison]::OrdinalIgnoreCase) })
        foreach($item in $owned) {
            $p=Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
            if($p -and $p.MainWindowHandle -ne 0) { [void]$p.CloseMainWindow() }
        }
        $deadline=(Get-Date).AddSeconds(45)
        do {
            $remaining=@(Get-CimInstance Win32_Process -Filter "name='Vocove.exe'" |
                Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals($target,[StringComparison]::OrdinalIgnoreCase) })
            if(!$remaining.Count) { exit 0 }
            Start-Sleep -Milliseconds 300
        } while((Get-Date) -lt $deadline)
        throw '应用尚未退出，请手动退出后重试；未强制结束进程。'
    """
    run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW)


def snapshot(profile, backup_root, revision):
    data = profile / 'data'
    if not (data / 'words.json').is_file() or not (data / 'config.json').is_file():
        raise ValueError('未找到已有桌面词库/配置，停止以免升级错误的资料目录')
    config_file = data / 'config.json'
    settings = json.loads(config_file.read_text(encoding='utf-8-sig'))
    credentials = Path(settings.get('sync', {}).get('credentials_dir', '.secrets'))
    if not credentials.is_absolute():
        credentials = data / credentials
    backup = maintenance.create_backup(data / 'words.json', config_file, credentials, backup_root, revision)
    # Include all desktop data, not only the files understood by this code version.
    shutil.copytree(data, backup / 'desktop-data', ignore=shutil.ignore_patterns('*.lock', '*.tmp'))
    manifest_path = backup / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for source in sorted((backup / 'desktop-data').rglob('*')):
        if not source.is_file():
            continue
        original = data / source.relative_to(backup / 'desktop-data')
        manifest['files'].append({'source': str(original), 'copy': str(source.relative_to(backup)),
                                  'sha256': maintenance.digest(source)})
    preference = profile / 'desktop-preferences.json'
    if preference.is_file():
        shutil.copy2(preference, backup / preference.name)
        manifest['files'].append({'source': str(preference), 'copy': preference.name,
                                  'sha256': maintenance.digest(preference)})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    maintenance.verify_backup(backup)
    return backup


def isolated_environment(profile):
    env = dict(os.environ)
    # These overrides apply only to installer/smoke children, never the user's environment.
    for key in ('VOCOVE_DESKTOP_USER_DATA_DIR', 'VOCAB_DESKTOP_USER_DATA_DIR',
                'VOCOVE_DATA_FILE', 'VOCAB_DATA_FILE', 'ELECTRON_RUN_AS_NODE'):
        env.pop(key, None)
    env['VOCOVE_DESKTOP_USER_DATA_DIR'] = str(profile)
    return env


def install_and_check(installer, executable, backup):
    with tempfile.TemporaryDirectory(prefix='vocove-upgrade-') as temporary:
        temporary = Path(temporary)
        # A silent installer that unexpectedly starts the app must not open real data.
        env = isolated_environment(temporary / 'installer-profile')
        # NSIS requires /D last and unquoted, including paths containing spaces.
        command = subprocess.list2cmdline([str(installer), '/S', '/currentuser']) + f' /D={executable.parent}'
        run(command, env=env, timeout=240,
            creationflags=subprocess.CREATE_NO_WINDOW)
        maintenance.verify_backup(backup)
        if not executable.is_file():
            raise RuntimeError('安装后的应用不存在，停止启动')
        env = isolated_environment(temporary / 'smoke-profile')
        result = run([executable, '--smoke-test'], env=env, timeout=120, capture_output=True, text=True, check=False,
                     encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
        (backup / 'smoke.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode or 'DESKTOP_SMOKE_OK' not in result.stdout:
            raise RuntimeError('独立资料冒烟检查失败，停止启动；见备份中的 smoke.log')
        maintenance.verify_backup(backup)


def upgrade(installer, executable, profile, backup_root, revision, restart=True):
    installer = checked_installer(installer)
    stop_application(executable)
    backup = snapshot(profile, backup_root, revision)
    print(f'本地备份（含密钥，请勿上传）：{backup}', flush=True)
    report = {'revision': revision, 'installer': str(installer),
              'installer_sha256': maintenance.digest(installer), 'status': 'backed-up'}
    report_path = backup / 'upgrade.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    try:
        install_and_check(installer, executable, backup)
        report['status'] = 'verified'
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        if restart:
            environment = dict(os.environ)
            environment.pop('ELECTRON_RUN_AS_NODE', None)
            environment['VOCOVE_DESKTOP_USER_DATA_DIR'] = str(profile)
            subprocess.Popen([str(executable)], env=environment, cwd=executable.parent,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        return backup
    except Exception as error:
        report['status'] = 'failed; keep files and logs; no data restored'
        report['error'] = f'{type(error).__name__}: {error}'
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        raise


def main():
    parser = argparse.ArgumentParser(description='本地构建、备份、验证并升级 Windows 桌面版；失败不恢复覆盖数据')
    parser.add_argument('--installer', type=Path, help='已有可信安装包（必须同时提供同名 .sha256），省略则本地构建')
    parser.add_argument('--profile', type=Path, default=Path(os.environ.get('APPDATA', '')) / 'Vocove')
    parser.add_argument('--install-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Vocove')
    parser.add_argument('--no-restart', action='store_true')
    parser.add_argument('--build-only', action='store_true', help='只构建并校验安装包，不停止/升级应用')
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('本地一键安装目前仅支持 Windows；macOS 请使用内置更新或 DMG')
    for directory in (args.profile, args.install_dir):
        if not directory.is_absolute():
            parser.error('资料和安装目录必须是绝对路径')
    executable = args.install_dir / 'Vocove.exe'
    if not executable.is_file():
        parser.error('未找到已有 Vocove.exe；此工具仅升级已有安装')
    revision = run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout
    # Serialize developers' double-clicks without force-stopping either upgrade.
    with maintenance.instance_lock.acquire(ROOT / '.backups/desktop-upgrade-session'):
        installer = checked_installer(args.installer or build(ROOT))
        if args.build_only:
            print(f'构建与安装包校验通过：{installer}')
            return
        upgrade(installer, executable, args.profile.resolve(), ROOT / '.backups/desktop-upgrades',
                revision + (' (working tree modified)' if dirty else ''), not args.no_restart)
    print('校验通过，升级完成。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(f'升级停止，保留现有数据与本地备份。{error}') from None
