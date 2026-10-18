param([string]$DesktopPath = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'VocabularyBook.exe'
if (-not (Test-Path -LiteralPath $launcher)) { throw 'VocabularyBook.exe is missing. Please update the installation first.' }
if (-not (Test-Path -LiteralPath $DesktopPath -PathType Container)) { throw 'Desktop directory is unavailable.' }
$shell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path $DesktopPath '云端词汇本.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    $previous = $shell.CreateShortcut($shortcutPath)
    if ($previous.TargetPath -ne $launcher) { throw 'A different shortcut already uses this name; it was preserved.' }
}
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.IconLocation = "$launcher,0"
$shortcut.Description = '打开云端词汇本，自动启动本机服务'
$shortcut.Save()
Write-Output $shortcutPath
