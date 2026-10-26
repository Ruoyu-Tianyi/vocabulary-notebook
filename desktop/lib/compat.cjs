'use strict'

// 旧安装的外部标识集中保留于此；新数据与界面只使用 Vocove 名称。
const LEGACY_PRODUCT_NAME = 'Vocabulary Notebook'
const SESSION_PARTITION = 'persist:vocabulary-notebook'
const LEGACY_SORT_KEY = 'vocabulary-word-sort'
const NSIS_UPGRADE_GUID = 'f70998c7-a603-5b48-be52-0cea4bb24a82'
const ENV_ALIASES = Object.freeze({
  VOCOVE_DESKTOP_PYTHON: 'VOCAB_DESKTOP_PYTHON',
  VOCOVE_DESKTOP_USER_DATA_DIR: 'VOCAB_DESKTOP_USER_DATA_DIR',
  VOCOVE_DESKTOP_SMOKE_SCREENSHOT: 'VOCAB_DESKTOP_SMOKE_SCREENSHOT',
  VOCOVE_DESKTOP_ORIGIN: 'VOCAB_DESKTOP_ORIGIN',
  VOCOVE_DATA_FILE: 'VOCAB_DATA_FILE',
})

function environmentValue(name, environment = process.env) {
  return Object.hasOwn(environment, name) ? environment[name] : environment[ENV_ALIASES[name]]
}

function clearEnvironmentValue(environment, name) {
  delete environment[name]
  if (ENV_ALIASES[name]) delete environment[ENV_ALIASES[name]]
}

function legacyProfileName(packaged) {
  return packaged ? LEGACY_PRODUCT_NAME : `${LEGACY_PRODUCT_NAME} Dev`
}

function compatibleSortPreference(value) {
  return Object.hasOwn(value, 'vocove-word-sort') ? value['vocove-word-sort'] : value[LEGACY_SORT_KEY]
}

module.exports = { SESSION_PARTITION, LEGACY_SORT_KEY, NSIS_UPGRADE_GUID, environmentValue, clearEnvironmentValue, legacyProfileName, compatibleSortPreference }
