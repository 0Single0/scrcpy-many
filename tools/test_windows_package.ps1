param(
    [Parameter(Mandatory = $true)]
    [string] $PackageRoot
)

$required = @(
    'scrcpy.exe',
    'bin\scrcpy-core.exe',
    'bin\scrcpy-server',
    'lib',
    'platform-tools\adb.exe'
)

foreach ($relativePath in $required) {
    $path = Join-Path $PackageRoot $relativePath
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing packaged path: $relativePath"
    }
}

$rootDlls = Get-ChildItem -LiteralPath $PackageRoot -Filter '*.dll' -File
if ($rootDlls.Count -ne 0) {
    throw "DLLs must be stored below lib\ ($($rootDlls.Name -join ', '))"
}

$libDlls = Get-ChildItem -LiteralPath (Join-Path $PackageRoot 'lib') -Filter '*.dll' -File
if ($libDlls.Count -eq 0) {
    throw 'No runtime DLLs found below lib\'
}

Write-Output "Windows package layout OK: $PackageRoot"
