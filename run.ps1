param(
  [Parameter(Position = 0)]
  [ValidateSet("sample", "validate", "report", "daily", "api")]
  [string]$Command = "sample",

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

if ($Command -eq "sample") {
  & $Python -m news_ingestion.cli sample @Args
} elseif ($Command -eq "validate") {
  & $Python -m news_ingestion.cli validate @Args
} elseif ($Command -eq "report") {
  & $Python -m news_ingestion.cli report @Args
} elseif ($Command -eq "daily") {
  & $Python -m news_ingestion.cli daily @Args
} elseif ($Command -eq "api") {
  & $Python -m news_ingestion.api_server @Args
}
