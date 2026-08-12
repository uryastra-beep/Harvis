$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$BuildPath = Join-Path $RepoRoot "build\pyinstaller"
$DistPath = Join-Path $RepoRoot "dist"
$SpecPath = Join-Path $RepoRoot "harvis.spec"
$PackagedAppPath = [System.IO.Path]::GetFullPath((Join-Path $DistPath "Harvis"))
$PackagedAppPrefix = $PackagedAppPath + [System.IO.Path]::DirectorySeparatorChar

function Remove-BuildDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    for ($Attempt = 1; $Attempt -le 5; $Attempt++) {
        try {
            Remove-Item -Recurse -Force $Path -ErrorAction Stop
            return
        }
        catch {
            if ($Attempt -eq 5) {
                throw
            }
            Write-Host "Waiting for Windows to release $Path ($Attempt/5)..."
            Start-Sleep -Seconds 1
        }
    }
}

Set-Location $RepoRoot

if (-not (Test-Path $VenvPython)) {
    python -m venv .venv
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt
& $VenvPython -m pip install "pyinstaller>=6.11,<7"
& $VenvPython -m pytest -q

Get-CimInstance Win32_Process |
    Where-Object {
        $_.ExecutablePath -and
        $_.ExecutablePath.StartsWith(
            $PackagedAppPrefix,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Remove-BuildDirectory -Path $BuildPath
Remove-BuildDirectory -Path $PackagedAppPath

& $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --workpath $BuildPath `
    --distpath $DistPath `
    $SpecPath

Write-Host "Harvis executable created at: $DistPath\Harvis\Harvis.exe"
