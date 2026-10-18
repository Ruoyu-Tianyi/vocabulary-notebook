$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Windows .NET Framework compiler is unavailable.' }
$runtime = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$iconBuilder = Join-Path $runtime 'BuildIcon.exe'
& $compiler /nologo /codepage:65001 /target:exe /r:System.Drawing.dll "/out:$iconBuilder" (Join-Path $PSScriptRoot 'BuildIcon.cs')
if ($LASTEXITCODE -ne 0) { throw 'Icon build failed.' }
& $iconBuilder (Join-Path $projectRoot 'assets')
if ($LASTEXITCODE -ne 0) { throw 'Icon rendering failed.' }
$output = Join-Path $projectRoot 'VocabularyBook.exe'
& $compiler /nologo /codepage:65001 /target:winexe /optimize+ /r:System.Drawing.dll /r:System.Windows.Forms.dll /r:System.Web.Extensions.dll "/win32icon:$(Join-Path $projectRoot 'assets\app-icon.ico')" "/out:$output" (Join-Path $PSScriptRoot 'Launcher.cs')
if ($LASTEXITCODE -ne 0) { throw 'Launcher build failed.' }
Write-Output "Built $output"
