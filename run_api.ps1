param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8080,
  [int]$RefreshIntervalMinutes = 10,
  [switch]$NoRefreshOnStart,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $Root "src"
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path -LiteralPath $BundledPython) {
  $Python = $BundledPython
} else {
  $Python = "python"
}

$cmdArgs = @(
  "-m", "news_ingestion.api_server",
  "--host", $HostName,
  "--port", "$Port",
  "--refresh-interval-minutes", "$RefreshIntervalMinutes"
)
if ($NoRefreshOnStart) {
  $cmdArgs += "--no-refresh-on-start"
}
$cmdArgs += $Args

& $Python @cmdArgs
