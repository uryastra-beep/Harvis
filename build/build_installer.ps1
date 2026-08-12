param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$ExeBuildScript = Join-Path $PSScriptRoot "build_exe.ps1"
$InstallerScript = Join-Path $RepoRoot "installer\Harvis.iss"
$PortableSource = Join-Path $RepoRoot "dist\Harvis"
$PortableZip = Join-Path $RepoRoot "dist\Harvis-$Version-Windows-x64-portable.zip"

& $ExeBuildScript

if (-not (Test-Path $PortableSource)) {
    throw "Portable Harvis build was not created at $PortableSource."
}

if (Test-Path $PortableZip) {
    Remove-Item -Force $PortableZip
}
Compress-Archive -Path (Join-Path $PortableSource "*") -DestinationPath $PortableZip -CompressionLevel Optimal
Write-Host "Harvis portable archive created at: $PortableZip"

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
