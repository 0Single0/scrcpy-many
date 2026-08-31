[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $Plan,
    [string] $Python = "python",
    [string] $Runner = ""
)

$ErrorActionPreference = "Stop"

$planPath = (Resolve-Path -LiteralPath $Plan -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $planPath -PathType Leaf)) {
    throw "Plan must be a readable file: $planPath"
}

if ([string]::IsNullOrWhiteSpace($Runner)) {
    $Runner = Join-Path $PSScriptRoot "scrcpy_automation.py"
}
$runnerPath = (Resolve-Path -LiteralPath $Runner -ErrorAction Stop).Path

$pythonCommand = Get-Command $Python -ErrorAction Stop
$pythonPath = $pythonCommand.Source

& $pythonPath $runnerPath schedule $planPath --python $pythonPath --runner $runnerPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
