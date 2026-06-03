$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root
powershell -ExecutionPolicy Bypass -File .\run.ps1 daily

