param([string]$Python = "python", [switch]$InstallDependencies)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if ($InstallDependencies) {
    & $Python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}
& $Python -c "import tkinter; root=tkinter.Tk(); root.withdraw(); root.update(); root.destroy()"
if ($LASTEXITCODE -ne 0) { throw "Tcl/Tk is not functional. Repair the Python Tcl/Tk installation before packaging." }
& $Python -m unittest discover -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
& $Python -m PyInstaller --noconfirm packaging/Inspection.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
Copy-Item -LiteralPath "packaging\使用说明.txt" -Destination "dist\BubbleInspection\使用说明.txt"
Compress-Archive -Path "dist\BubbleInspection" -DestinationPath "dist\BubbleInspection-win64.zip" -Force
Write-Host "Created dist\BubbleInspection\BubbleInspection.exe and dist\BubbleInspection-win64.zip"
