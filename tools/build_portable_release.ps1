[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $BuildDir,
    [Parameter(Mandatory = $true)][string] $RuntimeDir,
    [Parameter(Mandatory = $true)][string] $OutputDir,
    [string] $AutomationExe = ''
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$automationOutput = if ($AutomationExe) { [System.IO.Path]::GetFullPath($AutomationExe) } else { Join-Path ([System.IO.Path]::GetTempPath()) ('scrcpy-automation-' + [guid]::NewGuid().ToString('N') + '.exe') }
try {
    if (-not $AutomationExe) { & (Join-Path $PSScriptRoot 'build_automation_center.ps1') -OutputExe $automationOutput -ProjectRoot $root }
    & (Join-Path $PSScriptRoot 'package_windows.ps1') -BuildDir $BuildDir -RuntimeDir $RuntimeDir -OutputDir $OutputDir -AutomationExe $automationOutput
} finally {
    if (-not $AutomationExe -and (Test-Path -LiteralPath $automationOutput)) { Remove-Item -LiteralPath $automationOutput -Force }
}
