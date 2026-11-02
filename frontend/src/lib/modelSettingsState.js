// 草稿中的供应商选择独立于后端当前生效配置，切换标签不丢失选择。
export function builtinProvider(settings) {
  const builtins = settings.catalog.filter(item => item.id !== 'custom').map(item => item.id)
  if (builtins.includes(settings.provider)) return settings.provider
  if (builtins.includes(settings.last_builtin_provider)) return settings.last_builtin_provider
  return builtins.find(id => settings.providers[id]?.model) || builtins[0]
}

export function selectProvider(settings, provider) {
  if (provider === settings.provider) return settings
  return {
    ...settings,
    provider,
    last_builtin_provider: provider === 'custom' ? builtinProvider(settings) : provider,
  }
}
