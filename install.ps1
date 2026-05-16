param(
    [switch]$Uninstall,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$Repo = "https://github.com/0xH4KU/bilimanga-downloader.git"
$InstallDir = if ($env:BILIMANGA_INSTALL_DIR) { $env:BILIMANGA_INSTALL_DIR } else { "$env:LOCALAPPDATA\bilimanga-dl" }
$BinDir = if ($env:BILIMANGA_BIN_DIR) { $env:BILIMANGA_BIN_DIR } else { "$env:LOCALAPPDATA\bilimanga-dl\bin" }
$VenvDir = "$InstallDir\.venv"

if ($Help) {
    Write-Host "Usage: install.ps1 [-Uninstall] [-Help]"
    exit 0
}

if ($Uninstall) {
    if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
    if (Test-Path "$BinDir\bilimanga-dl.cmd") { Remove-Item -Force "$BinDir\bilimanga-dl.cmd" }
    if (Test-Path "$BinDir\bilimanga-dl-uninstall.cmd") { Remove-Item -Force "$BinDir\bilimanga-dl-uninstall.cmd" }
    Write-Host "Uninstalled bilimanga-dl. Config was preserved."
    exit 0
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required."
}

$PythonCmd = $null
foreach ($Command in @("python3", "python", "py")) {
    try {
        $Ok = & $Command -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        $PythonCmd = $Command
        break
    } catch {
        continue
    }
}
if (-not $PythonCmd) {
    throw "Python >= 3.11 is required."
}

if (Test-Path "$InstallDir\.git") {
    git -C $InstallDir pull --ff-only
} else {
    if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
    git clone --depth 1 $Repo $InstallDir
}

& $PythonCmd -m venv $VenvDir --clear
& "$VenvDir\Scripts\pip.exe" install --upgrade pip setuptools wheel
& "$VenvDir\Scripts\pip.exe" install -e $InstallDir
& "$VenvDir\Scripts\python.exe" -m playwright install chromium

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

@"
@echo off
"$VenvDir\Scripts\python.exe" -m bilimanga_dl %*
"@ | Set-Content "$BinDir\bilimanga-dl.cmd" -Encoding ASCII

@"
@echo off
rmdir /s /q "$InstallDir"
del "$BinDir\bilimanga-dl.cmd"
del "$BinDir\bilimanga-dl-uninstall.cmd"
echo Uninstalled bilimanga-dl. Config was preserved.
"@ | Set-Content "$BinDir\bilimanga-dl-uninstall.cmd" -Encoding ASCII

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    $env:Path = "$env:Path;$BinDir"
}

Write-Host "Installed bilimanga-dl to $InstallDir"
Write-Host "Command: $BinDir\bilimanga-dl.cmd"
Write-Host "Run: bilimanga-dl doctor"
