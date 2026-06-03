param()

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Push-Location $Root.Path
try {
  $BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  if (Test-Path -LiteralPath $BundledPython) {
    $Python = $BundledPython
  } else {
    $Python = "python"
  }

  $versionOutput = & $Python --version 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "Python not found. Install Python 3.11+ and retry."
  }

  $env:PYTHONPATH = Join-Path $Root.Path "src"
  & $Python -m compileall src | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Python compile check failed."
  }

  $jsonFiles = @(
    "config\source_registry.v1.json",
    "config\quality_rules.v1.json",
    "schemas\article_record.schema.json"
  )
  foreach ($file in $jsonFiles) {
    Get-Content -LiteralPath (Join-Path $Root.Path $file) -Encoding UTF8 -Raw | ConvertFrom-Json | Out-Null
  }

  & $Python -m news_ingestion.cli sample --out-dir data\doctor_sample | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Sample command failed."
  }

  Write-Output "doctor_ok=True"
  Write-Output "python=$versionOutput"
  Write-Output "project_root=$($Root.Path)"
} finally {
  Pop-Location
}
