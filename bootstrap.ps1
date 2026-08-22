# fiducial bootstrap - wires this repo into the host project.
# Run once after cloning/submoduling:  ./fiducial/bootstrap.ps1
# Idempotent; remove with              ./fiducial/bootstrap.ps1 -Remove
param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$fiducialDir = $PSScriptRoot
$projectRoot = Split-Path -Parent $fiducialDir
$fiducialName = Split-Path -Leaf $fiducialDir
$agentsPath = Join-Path $projectRoot "AGENTS.md"
$importLine = "@$fiducialName/AGENTS.md"

function Test-Imported {
    return ((Test-Path -LiteralPath $agentsPath) -and
        ((Get-Content -LiteralPath $agentsPath -Raw) -match [regex]::Escape($importLine)))
}

if ($Remove) {
    if (-not (Test-Imported)) {
        Write-Host "Not installed (no '$importLine' in AGENTS.md). Nothing to do."
        exit 0
    }
    $lines = Get-Content -LiteralPath $agentsPath |
        Where-Object { $_ -notmatch [regex]::Escape($importLine) }
    Set-Content -LiteralPath $agentsPath -Value $lines -Encoding UTF8
    Write-Host "Removed fiducial import from $agentsPath"
    exit 0
}

# Create AGENTS.md if the project has none
if (-not (Test-Path -LiteralPath $agentsPath)) {
    New-Item -ItemType File -Path $agentsPath | Out-Null
    Write-Host "Created $agentsPath"
}

if (Test-Imported) {
    Write-Host "Already imported ($importLine). Nothing to do."
} else {
    Add-Content -LiteralPath $agentsPath -Value "`r`n$importLine" -Encoding UTF8
    Write-Host "Added '$importLine' to $agentsPath"
}

# Environment sanity check (non-fatal)
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    & python (Join-Path $fiducialDir "scripts\fiducial.py") doctor
} else {
    Write-Warning "python not found on PATH; fiducial.py tools need Python 3"
}
