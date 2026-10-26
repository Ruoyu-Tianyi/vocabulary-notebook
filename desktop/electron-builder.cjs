const fs = require('node:fs');
const path = require('node:path');
const { NSIS_UPGRADE_GUID } = require('./lib/compat.cjs');

module.exports = {
  appId: 'net.ericzhou.vocove',
  productName: 'Vocove',
  electronDist: path.join(__dirname, 'node_modules/electron/dist'),
  directories: { output: 'release', buildResources: 'resources' },
  // 显式白名单：不把仓库、开发环境、词库或凭据装入应用。
  files: ['main.cjs', 'lib/**/*.cjs', 'package.json'],
  extraResources: [
    { from: 'build/backend/vocove-backend', to: 'backend', filter: ['**/*'] },
    { from: '../LICENSE', to: 'LICENSE.vocove.txt' },
    { from: 'resources', to: 'branding', filter: ['icon.png', 'icon.ico'] },
  ],
  asar: true,
  npmRebuild: false,
  publish: { provider: 'github', owner: 'Eric-Zhou-0302', repo: 'vocove', private: false },
  // GitHub 依照 Release 的预发布标记选版；未指定 channel 时生成 latest*.yml。
  generateUpdatesFilesForAllChannels: true,
  artifactName: '${productName}-${version}-${os}-${arch}.${ext}',
  mac: {
    icon: 'icon.icns',
    category: 'public.app-category.education',
    target: ['dmg', 'zip'],
    identity: '-',
    hardenedRuntime: false,
    notarize: false,
  },
  win: { icon: 'icon.ico', target: ['nsis'], requestedExecutionLevel: 'asInvoker' },
  dmg: {
    background: 'background.png',
    icon: 'icon.icns',
    iconSize: 80,
    iconTextSize: 12,
    contents: [
      { x: 150, y: 200 },
      { x: 390, y: 200, type: 'link', path: '/Applications' },
    ],
  },
  nsis: {
    // 沿用旧版安装的 UUID；产品名和 AppID 改名后仍识别为原安装的升级。
    guid: NSIS_UPGRADE_GUID,
    oneClick: false,
    perMachine: false,
    allowToChangeInstallationDirectory: true,
    deleteAppDataOnUninstall: false,
    createDesktopShortcut: true,
    installerIcon: 'icon.ico',
    uninstallerIcon: 'icon.ico',
    installerHeader: 'installerHeader.bmp',
    installerSidebar: 'installerSidebar.bmp',
    uninstallerSidebar: 'installerSidebar.bmp',
  },
  beforePack: async (context) => {
    const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, 'build/backend/target.json'), 'utf8'));
    const arch = { 1: 'x64', 3: 'arm64' }[context.arch];
    if (manifest.platform !== context.electronPlatformName || manifest.arch !== arch) {
      throw new Error('内置 Python 后端与 Electron 平台/架构不匹配；请在目标平台重新构建。');
    }
  },
};
