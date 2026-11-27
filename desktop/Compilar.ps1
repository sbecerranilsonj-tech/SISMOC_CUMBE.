$ErrorActionPreference = 'Stop'
$raizSismoc = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $raizSismoc
$pythonSismoc = Join-Path $raizSismoc '.venv-desktop\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonSismoc)) {
    & py -3.12 -m venv .venv-desktop
    if ($LASTEXITCODE -ne 0) { throw 'Instala Python 3.12 de 64 bits y vuelve a compilar.' }
}
& $pythonSismoc -m pip install -r desktop/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias del escritorio.' }
& $pythonSismoc -m PyInstaller desktop/Sismoc.spec --distpath desktop/dist --workpath desktop/build --noconfirm
if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar SISMOC.exe.' }
$compiladorSismoc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($compiladorSismoc) {
    & $compiladorSismoc.Source desktop/instalador.iss
    if ($LASTEXITCODE -ne 0) { throw 'Falló la creación del instalador de Windows.' }
} else {
    Write-Host 'Ejecutable generado en desktop/dist/SISMOC. Instala Inno Setup 6 y compila desktop/instalador.iss para obtener el instalador.'
}
