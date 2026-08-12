param(
    [string]$Version = "0.2.0"
)

$ErrorActionPreference = "Stop"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$ExeBuildScript = Join-Path $PSScriptRoot "build_exe.ps1"
$InstallerScript = Join-Path $RepoRoot "installer\Harvis.iss"

& $ExeBuildScript

$Candidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$Compiler = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Compiler) {
    throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isdl.php and run this script again."
}

& $Compiler "/DAppVersion=$Version" $InstallerScript
Write-Host "Harvis installer created in: $RepoRoot\dist\installer"
