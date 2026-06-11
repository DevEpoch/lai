# local-ai-env one-line installer (Windows)
#   irm https://raw.githubusercontent.com/DevEpoch/lai/main/install.ps1 | iex
# Override the repo/destination:
#   $env:LAI_REPO = 'https://github.com/DevEpoch/lai'; $env:LAI_DIR = 'D:\ai'
$ErrorActionPreference = 'Continue'

$repo = if ($env:LAI_REPO) { $env:LAI_REPO } else { 'https://github.com/DevEpoch/lai' }
$dest = if ($env:LAI_DIR)  { $env:LAI_DIR }  else { Join-Path $env:USERPROFILE 'lai' }

Write-Host "local-ai-env installer -> $dest" -ForegroundColor Cyan

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host 'Python 3.9+ is required. Install it first:' -ForegroundColor Red
    Write-Host '    winget install Python.Python.3.12'
    exit 1
}

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
& $py.Source (Join-Path $dest 'lai.py') shortcut --yes   # Desktop + Start Menu launcher
Write-Host "`nNext:  cd $dest ; .\lai.ps1 setup    (or double-click 'Local AI Env')" -ForegroundColor Cyan
