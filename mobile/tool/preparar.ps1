param([string]$Flutter = 'flutter')
$ErrorActionPreference = 'Stop'
$appPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $appPath
try {
    if (-not (Test-Path 'android/gradlew.bat')) {
        & $Flutter create --platforms=android --project-name=sismoc_movil --org=pe.elcumbe.sismoc .
        if ($LASTEXITCODE -ne 0) { throw 'Flutter no pudo preparar Android.' }
    }
    $manifestPath = Join-Path $appPath 'android/app/src/main/AndroidManifest.xml'
    [xml]$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8
    $androidNs = 'http://schemas.android.com/apk/res/android'
    foreach ($permission in @('android.permission.INTERNET','android.permission.ACCESS_FINE_LOCATION','android.permission.ACCESS_COARSE_LOCATION')) {
        $exists = @($manifest.manifest.'uses-permission') | Where-Object { $null -ne $_ -and $_.GetAttribute('name',$androidNs) -eq $permission }
        if (-not $exists) {
            $node = $manifest.CreateElement('uses-permission')
            $node.SetAttribute('name',$androidNs,$permission) | Out-Null
            $manifest.manifest.AppendChild($node) | Out-Null
        }
    }
    $manifest.manifest.application.SetAttribute('label',$androidNs,'SISMOC - El Cumbe') | Out-Null
    $manifest.manifest.application.SetAttribute('allowBackup',$androidNs,'false') | Out-Null
    $manifest.Save($manifestPath)
    $debugPath = Join-Path $appPath 'android/app/src/debug/AndroidManifest.xml'
    $debugXml = '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><uses-permission android:name="android.permission.INTERNET"/><application android:usesCleartextTraffic="true" /></manifest>'
    Set-Content -LiteralPath $debugPath -Value $debugXml -Encoding utf8
    & $Flutter pub get
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron descargar dependencias.' }
    # Los avisos informativos siguen visibles. Los errores y warnings detienen la preparacion.
    & $Flutter analyze --no-fatal-infos
    if ($LASTEXITCODE -ne 0) { throw 'Hay errores o advertencias en el analisis de Flutter.' }
    & $Flutter test
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas de Flutter.' }
    Write-Host 'Listo. Ejecuta flutter devices y flutter run para abrir la app.'
} finally { Pop-Location }
