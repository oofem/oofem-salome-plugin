<#
    OOFEM-Salome-Plugin Windows Installer
    -------------------------------------
    Usage:
        powershell -ExecutionPolicy Bypass -File install.ps1
#>

Write-Host ""
Write-Host "=== OOFEM-Salome-Plugin Installer (Windows) ==="
Write-Host ""

# ------------------------------------------------------------
# 1. Try auto-detecting Salome installation
# ------------------------------------------------------------

$PossiblePaths = @(
    "C:\SALOME-9.15.*",
    "C:\Program Files\SALOME-9.15.*",
    "C:\Program Files (x86)\SALOME-9.15.*"
)

$SalomeRoot = $null

foreach ($path in $PossiblePaths) {
    $resolvedPath = Get-Item -Path $path -ErrorAction SilentlyContinue
    if ($resolvedPath) {
        $SalomeRoot = $resolvedPath.FullName
        break
    }
}

if ($SalomeRoot) {
    Write-Host "✔ Auto-detected Salome installation at:"
    Write-Host "  $SalomeRoot"
} else {
    Write-Host "⚠ Could not auto-detect Salome installation."
    Write-Host "Please enter the Salome installation directory manually."
    $SalomeRoot = Read-Host "Example: C:\SALOME-9.15.0"

    if (-not (Test-Path $SalomeRoot)) {
        Write-Host "❌ The provided path does not exist. Aborting installation."
        exit 1
    }
}

# ------------------------------------------------------------
# 2. Define source and target directories
# ------------------------------------------------------------

$SourceDir = Join-Path $PSScriptRoot "src\OOFEMSalomePlugin"
$TargetDir = Join-Path $SalomeRoot "WORK\salome\modules\OOFEMSalomePlugin"

Write-Host ""
Write-Host "Source directory:"
Write-Host "  $SourceDir"
Write-Host "Target directory:"
Write-Host "  $TargetDir"
Write-Host ""

# ------------------------------------------------------------
# 3. Validate source directory
# ------------------------------------------------------------

if (-not (Test-Path $SourceDir)) {
    Write-Host "❌ ERROR: Source directory not found:"
    Write-Host "  $SourceDir"
    Write-Host "Make sure you are running this script from the plugin root directory."
    exit 1
}

# ------------------------------------------------------------
# 4. Create target directory
# ------------------------------------------------------------

if (Test-Path $TargetDir) {
    Write-Host "Removing old plugin directory..."
    Remove-Item -Recurse -Force $TargetDir
}

Write-Host "Creating plugin directory..."
New-Item -ItemType Directory -Path $TargetDir | Out-Null

# ------------------------------------------------------------
# 5. Copy plugin files
# ------------------------------------------------------------

Write-Host "Copying plugin files..."
Copy-Item -Path "$SourceDir\*" -Destination $TargetDir -Recurse -Force

# ------------------------------------------------------------
# 6. Finish
# ------------------------------------------------------------

Write-Host ""
Write-Host "✔ Installation complete!"
Write-Host "Restart Salome to load the OOFEM module."
Write-Host ""
Write-Host "If the module does not appear:"
Write-Host "  - Verify the plugin is in: $TargetDir"
Write-Host "  - Ensure you are using Salome 9.15"
Write-Host ""
