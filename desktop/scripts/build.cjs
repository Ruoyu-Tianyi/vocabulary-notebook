const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { environmentValue } = require('../lib/compat.cjs');

const root = path.resolve(__dirname, '../..');
const desktop = path.join(root, 'desktop');
const configuredPython = environmentValue('VOCOVE_DESKTOP_PYTHON');
const python = configuredPython
  ? path.resolve(root, configuredPython)
  : path.join(root, '.venv-desktop', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const args = new Set(process.argv.slice(2));
if ([...args].some((arg) => !['--backend-only', '--dir'].includes(arg))) {
  throw new Error('支持的参数为 --backend-only 或 --dir；只构建当前平台与架构。');
}
if (!['darwin', 'win32'].includes(process.platform) || !['arm64', 'x64'].includes(process.arch)) {
  throw new Error('桌面构建需要 macOS 或 Windows 的 arm64/x64 原生环境。');
}
if (!fs.existsSync(python)) throw new Error('请创建 .venv-desktop 并安装 requirements-desktop.txt，或设置 VOCOVE_DESKTOP_PYTHON。');

function run(command, commandArgs, cwd = root) {
  const result = spawnSync(command, commandArgs, { cwd, stdio: 'inherit', env: process.env });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}

// 通过 npm CLI 的 JS 入口运行，避免 Windows 的 .cmd / shell 路径转义问题。
const npmCli = process.env.npm_execpath;
if (!npmCli) throw new Error('请通过 npm --prefix desktop run pack / dist 调用。');
run(process.execPath, [npmCli, '--prefix', 'frontend', 'run', 'build']);
run(python, [path.join(desktop, 'scripts/build_backend.py'), '--arch', process.arch]);
if (!args.has('--backend-only')) {
  // 新版 Electron 按需下载运行时；复用当前平台已验证的本地二进制。
  require('electron');
  run(process.execPath, [require.resolve('electron-builder/cli.js'),
    '--config', 'electron-builder.cjs', '--publish', 'never',
    process.platform === 'darwin' ? '--mac' : '--win', `--${process.arch}`,
    ...(args.has('--dir') ? ['--dir'] : []),
  ], desktop);
  if (!args.has('--dir')) {
    run(process.execPath, [path.join(desktop, 'scripts/update-checksums.cjs'),
      process.platform, process.arch, require('../package.json').version, path.join(desktop, 'release'),
    ], desktop);
  }
}
