[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $OutputExe,
    [string] $ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$uiRoot = Join-Path $root 'automation-ui'
$requirements = Join-Path $root 'tools\automation_center\requirements.txt'
$venv = Join-Path ([System.IO.Path]::GetTempPath()) ('scrcpy-many-python-' + [guid]::NewGuid().ToString('N'))
$output = [System.IO.Path]::GetFullPath($OutputExe)

try {
    npm --prefix $uiRoot ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    npm --prefix $uiRoot run build
    if ($LASTEXITCODE -ne 0) { throw 'UI build failed' }
    python -m venv $venv
    & (Join-Path $venv 'Scripts\python.exe') -m pip install --disable-pip-version-check -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency install failed' }
    $entrypoint = Join-Path $root 'tools\automation_center\app.py'
    $uiDist = Join-Path $uiRoot 'dist'
    $distDir = Join-Path $venv 'dist'
    # Keep PyInstaller's generated spec/build files inside the disposable venv.
    & (Join-Path $venv 'Scripts\pyinstaller.exe') --noconfirm --clean --onefile --windowed --name scrcpy-automation --specpath $venv --distpath $distDir --workpath (Join-Path $venv 'build') --add-data "$uiDist;ui" --paths $root $entrypoint
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
    Copy-Item -LiteralPath (Join-Path $distDir 'scrcpy-automation.exe') -Destination $output
    if (-not (Test-Path -LiteralPath $output)) { throw "Missing output executable: $output" }
} finally {
    if (Test-Path -LiteralPath $venv) { Remove-Item -LiteralPath $venv -Recurse -Force }
}
Write-Output "Built automation center: $output"
