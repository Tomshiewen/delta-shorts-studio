# ASCII-only shim. Real logic lives in github-setup.py.
#
# Why: PowerShell 5.1 decodes UTF-8 .ps1 files WITHOUT a BOM as the system ANSI
# codepage (GBK on this machine), which truncates Chinese strings and breaks
# parsing. Python source is UTF-8 by default, so the logic lives there.
#
# Usage:
#   .\tools\github-setup.ps1 -Token ghp_xxx
#   .\tools\github-setup.ps1
param(
  [string]$Token,
  [string]$Repo,
  [switch]$Private,
  [switch]$NoPush
)

$py = Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

$target = Join-Path $PSScriptRoot 'github-setup.py'
$argv = @($target)
if ($Token)   { $argv += @('--token', $Token) }
if ($Repo)    { $argv += @('--repo', $Repo) }
if ($Private) { $argv += '--private' }
if ($NoPush)  { $argv += '--no-push' }

& $py @argv
exit $LASTEXITCODE
