param(
    [Parameter(Mandatory = $true)]
    [string] $BuildDir,

    [Parameter(Mandatory = $true)]
    [string] $RuntimeDir,

    [Parameter(Mandatory = $true)]
    [string] $OutputDir
)

$buildRoot = (Resolve-Path -LiteralPath $BuildDir).Path
$runtimeRoot = (Resolve-Path -LiteralPath $RuntimeDir).Path
$outputParent = Split-Path -Parent $OutputDir
$outputName = Split-Path -Leaf $OutputDir
$stageDir = Join-Path $outputParent ($outputName + '.stage')

if (Test-Path -LiteralPath $stageDir) {
    Remove-Item -LiteralPath $stageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $stageDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stageDir 'bin') | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stageDir 'lib') | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stageDir 'platform-tools') | Out-Null

Copy-Item -LiteralPath (Join-Path $buildRoot 'app\scrcpy.exe') `
    -Destination (Join-Path $stageDir 'scrcpy.exe')
Copy-Item -LiteralPath (Join-Path $buildRoot 'app\scrcpy-core.exe') `
    -Destination (Join-Path $stageDir 'bin\scrcpy-core.exe')
Copy-Item -LiteralPath (Join-Path $buildRoot 'server\scrcpy-server') `
    -Destination (Join-Path $stageDir 'bin\scrcpy-server')

Get-ChildItem -LiteralPath $runtimeRoot -Filter '*.dll' -File |
    Copy-Item -Destination (Join-Path $stageDir 'lib')

foreach ($fileName in @('adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll')) {
    Copy-Item -LiteralPath (Join-Path $runtimeRoot $fileName) `
        -Destination (Join-Path (Join-Path $stageDir 'platform-tools') $fileName)
}

& (Join-Path $PSScriptRoot 'test_windows_package.ps1') -PackageRoot $stageDir

if (Test-Path -LiteralPath $OutputDir) {
    throw "Output directory already exists: $OutputDir"
}
Move-Item -LiteralPath $stageDir -Destination $OutputDir
Write-Output "Packaged Windows build: $OutputDir"
