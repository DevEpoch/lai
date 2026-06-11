#Requires -Version 5.1
# Windows wrapper for lai.py - usage: .\lai.ps1 <command>
# 'Continue' on purpose: with 'Stop', PowerShell 5.1 turns harmless child
# stderr lines (e.g. git warnings) into fatal errors when output is redirected.
$ErrorActionPreference = 'Continue'

$py = Get-Command python -ErrorAction SilentlyContinue
$pyArgs = @()
if (-not $py) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { $pyArgs = @('-3') }
}
if (-not $py) {
    Write-Host 'Python 3.9+ not found. Install it with: winget install Python.Python.3.12' -ForegroundColor Red
    exit 1
}

& $py.Source @pyArgs (Join-Path $PSScriptRoot 'lai.py') @args
exit $LASTEXITCODE
