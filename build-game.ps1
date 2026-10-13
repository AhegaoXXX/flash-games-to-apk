param(
    [Parameter(Mandatory = $true)][string]$Game,
    [string]$Sdk = $env:ANDROID_HOME
)
$ErrorActionPreference = 'Stop'
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python 3.12+ is required. Install it and add python to PATH.'
}
$arguments = @((Join-Path $PSScriptRoot 'builder/build_game.py'), '--game', $Game)
if ($Sdk) { $arguments += @('--sdk', $Sdk) }
& python @arguments
if ($LASTEXITCODE -ne 0) { throw "APK build failed (exit $LASTEXITCODE). See the error above." }
