param(
  [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
if (-not $OutputPath) {
  $Dist = Join-Path $Root.Path "dist"
  New-Item -ItemType Directory -Force -Path $Dist | Out-Null
  $OutputPath = Join-Path $Dist "news-ingestion-v1-source.zip"
}

$OutputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
$RootFullPath = $Root.Path
if (-not $OutputFullPath.StartsWith($RootFullPath)) {
  throw "OutputPath must stay inside project root: $RootFullPath"
}
if (Test-Path -LiteralPath $OutputFullPath) {
  Remove-Item -LiteralPath $OutputFullPath -Force
}

$excludeDirs = @(
  "\data\daily\",
  "\data\doctor_sample\",
  "\data\empty_inbox\",
  "\data\multisource_test\",
  "\data\realtest\",
  "\data\samples\",
  "\data\validated\",
  "\dist\",
  "\__pycache__\",
  "\.pytest_cache\",
  "\.git\",
  "\.vscode\",
  "\.idea\"
)

$excludeFiles = @(
  ".env",
  ".DS_Store",
  "Thumbs.db"
)

$files = Get-ChildItem -LiteralPath $RootFullPath -Recurse -File | Where-Object {
  $relative = $_.FullName.Substring($RootFullPath.Length)
  foreach ($dir in $excludeDirs) {
    if ($relative.Contains($dir)) { return $false }
  }
  if ($excludeFiles -contains $_.Name) { return $false }
  if ($_.Name.EndsWith(".pyc")) { return $false }
  if ($relative -like "\data\inbox\*" -and $_.Name -ne ".gitkeep") { return $false }
  return $true
}

if (-not $files) {
  throw "No files found for source package."
}

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("news-ingestion-v1-source-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
try {
  foreach ($file in $files) {
    $relative = $file.FullName.Substring($RootFullPath.Length).TrimStart("\")
    $target = Join-Path $tempDir $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $target
  }
  Compress-Archive -Path (Join-Path $tempDir "*") -DestinationPath $OutputFullPath -Force
  Write-Output "source_package=$OutputFullPath"
  Write-Output "file_count=$($files.Count)"
} finally {
  if (Test-Path -LiteralPath $tempDir) {
    Remove-Item -LiteralPath $tempDir -Recurse -Force
  }
}
