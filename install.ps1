# local-ai-env one-line installer (Windows, PowerShell)
#   irm https://raw.githubusercontent.com/DevEpoch/lai/main/install.ps1 | iex
# Override the repo/destination:
#   $env:LAI_REPO = 'https://github.com/DevEpoch/lai'; $env:LAI_DIR = 'D:\ai'
$ErrorActionPreference = 'Continue'

$repo = if ($env:LAI_REPO) { $env:LAI_REPO } else { 'https://github.com/DevEpoch/lai' }
$dest = if ($env:LAI_DIR)  { $env:LAI_DIR }  else { Join-Path $env:LOCALAPPDATA 'lai' }

Write-Host "local-ai-env installer -> $dest" -ForegroundColor Cyan

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Ensure-Tool($cmd, $wingetId, $label) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { return $true }
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Host "$label is required but winget is unavailable - install it manually." -ForegroundColor Red
        return $false
    }
    Write-Host "$label is not installed. Installing it now with winget..." -ForegroundColor Yellow
    & winget install -e --id $wingetId --accept-source-agreements --accept-package-agreements
    Refresh-Path
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# -- prerequisites: install them instead of just warning ---------------------
if (-not (Ensure-Tool 'python' 'Python.Python.3.12' 'Python 3.12')) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        Write-Host 'Could not get Python installed - aborting.' -ForegroundColor Red
        exit 1
    }
}
$null = Ensure-Tool 'git' 'Git.Git' 'Git'   # used for installs and lai update

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }

# -- fetch / update the program ----------------------------------------------
if (Test-Path (Join-Path $dest 'lai.py')) {
    Write-Host 'Existing install found - updating (git pull).'
    if (Test-Path (Join-Path $dest '.git')) { git -C $dest pull --ff-only }
} elseif (Get-Command git -ErrorAction SilentlyContinue) {
    git clone --depth 1 $repo $dest
} else {
    Write-Host 'git not found - downloading zip instead.'
    $zip = Join-Path $env:TEMP 'local-ai-env.zip'
    [Net.ServicePointManager]::SecurityProtocol = 'Tls12'
    Invoke-WebRequest "$repo/archive/refs/heads/main.zip" -OutFile $zip -UseBasicParsing
    $tmp = Join-Path $env:TEMP 'local-ai-env-x'
    Expand-Archive $zip $tmp -Force
    $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
    Move-Item $inner.FullName $dest
    Remove-Item $zip; Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path (Join-Path $dest 'lai.py'))) {
    Write-Host 'Install failed - lai.py not found.' -ForegroundColor Red
    exit 1
}

Set-Location $dest
Write-Host "`nInstalled. Checking your hardware:`n" -ForegroundColor Green
& $py.Source (Join-Path $dest 'lai.py') check
& $py.Source (Join-Path $dest 'lai.py') path --yes       # `lai` works in any terminal
& $py.Source (Join-Path $dest 'lai.py') shortcut --yes   # Desktop + Start Menu launcher
Refresh-Path

Write-Host ''
Write-Host '================= lai is installed =================' -ForegroundColor Green
Write-Host '  1. Open a NEW terminal (PowerShell or cmd).'
Write-Host '  2. Type:   lai go        <- sets everything up, then opens the dashboard'
Write-Host ''
Write-Host '  The dashboard (UI) lives at:  http://localhost:8090'
Write-Host '  Open it anytime with:  lai ui   - or the "Local AI Env" Desktop shortcut.'
Write-Host '====================================================' -ForegroundColor Green
