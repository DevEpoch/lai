# Publish/update the lai extension on the VS Code Marketplace.
#   .\publish.ps1                # package only (.vsix)
#   .\publish.ps1 -Bump patch    # bump version, package, and publish
# Requirements (one-time):
#   1. Create a publisher at https://marketplace.visualstudio.com/manage
#      (id must match "publisher" in package.json).
#   2. Create an Azure DevOps PAT with the "Marketplace > Manage" scope.
#   3. $env:VSCE_PAT = "<your pat>"   (or pass -Pat)
param(
    [ValidateSet("none", "patch", "minor", "major")] [string]$Bump = "none",
    [string]$Pat = $env:VSCE_PAT
)
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

if ($Bump -ne "none") { npm version $Bump --no-git-tag-version }
npm install --no-audit --no-fund
npx tsc -p .
npx vitest run
if ($LASTEXITCODE -ne 0) { Write-Host "tests failed - aborting" -ForegroundColor Red; exit 1 }
npx vsce package --allow-missing-repository
if (-not $Pat) {
    Write-Host "packaged only (no VSCE_PAT) - install locally with:" -ForegroundColor Yellow
    Write-Host "  code --install-extension (Get-ChildItem *.vsix | Select-Object -Last 1).Name"
    exit 0
}
npx vsce publish -p $Pat
Write-Host "published. Also consider Open VSX: npx ovsx publish -p `$env:OVSX_PAT" -ForegroundColor Green
