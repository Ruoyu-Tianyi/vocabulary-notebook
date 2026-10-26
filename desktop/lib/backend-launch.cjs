'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { environmentValue } = require('./compat.cjs')

function backendLaunch({ packaged, resourcesPath, root, platform = process.platform, environment = process.env }) {
  if (packaged) return { command: path.join(resourcesPath, 'backend', platform === 'win32' ? 'vocove-backend.exe' : 'vocove-backend'), args: [] }
  const suffix = platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'
  const projectPython = path.join(root, '.venv', suffix)
  const command = environmentValue('VOCOVE_DESKTOP_PYTHON', environment) || (fs.existsSync(projectPython) ? projectPython : path.join(root, '.venv-desktop', suffix))
  return { command, args: ['-u', path.join(root, 'desktop_backend.py')] }
}

module.exports = { backendLaunch }
