param([switch]$PrepareFolders)
$ErrorActionPreference = 'Stop'
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
Push-Location -LiteralPath $PSScriptRoot
try {
    $pythonCommand = $null
    $pythonArguments = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.14 -c "import struct,sys; assert sys.version_info[:2] == (3,14) and struct.calcsize('P') == 8" 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonCommand = (Get-Command py).Source; $pythonArguments = @('-3.14') }
    }
    if (-not $pythonCommand -and (Get-Command python -ErrorAction SilentlyContinue)) {
        & python -c "import struct,sys; assert sys.version_info[:2] == (3,14) and struct.calcsize('P') == 8" 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonCommand = (Get-Command python).Source }
    }
    if (-not $pythonCommand) { throw 'Install Python 3.14 (64-bit), then reopen this window. See Required Software.txt.' }
    if ($PrepareFolders) {
        & $pythonCommand @pythonArguments builder/inputs.py --prepare
        exit $LASTEXITCODE
    }
    # Missing inputs are reported before any dependency installation.
    & $pythonCommand @pythonArguments builder/inputs.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    New-Item -ItemType Directory -Path '.build/setup-temp' -Force | Out-Null
    $env:TEMP = (Resolve-Path -LiteralPath '.build/setup-temp').Path
    $env:TMP = $env:TEMP
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        Write-Host 'Setting up the local Python environment...'
        & $pythonCommand @pythonArguments -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv. See README.md troubleshooting.' }
    }
    $venvPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    $requirementsHash = (& $venvPython -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('builder/requirements.txt').read_bytes()).hexdigest())").Trim()
    if ($LASTEXITCODE -ne 0) { throw 'The local Python environment is damaged. Remove .venv and run the builder again.' }
    $stamp = '.venv/luminescent-requirements.txt'
    $installPackages = -not (Test-Path -LiteralPath $stamp)
    if (-not $installPackages) { $installPackages = (Get-Content -LiteralPath $stamp -Raw).Trim() -ne $requirementsHash }
    if (-not $installPackages) {
        & $venvPython -c "import lz4.block,PIL; from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes" 2>$null
        $installPackages = $LASTEXITCODE -ne 0
    }
    if ($installPackages) {
        Write-Host 'Installing the Python packages used by the builder...'
        & $venvPython -m pip install --disable-pip-version-check --only-binary=:all: -r builder/requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Package installation failed. Check your internet connection and see Required Software.txt.' }
        Set-Content -LiteralPath $stamp -Value $requirementsHash
    }
    & $venvPython builder/build.py
    exit $LASTEXITCODE
} catch {
    Write-Host "`nBUILD FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
    Pop-Location
}
