# SISMOC móvil

Cliente Flutter Android de la API `/movil/api/` del proyecto padre.

```powershell
./tool/preparar.ps1
flutter run
```

El script genera la plataforma Android con el SDK Flutter instalado y configura permisos de ubicación, acceso a red y HTTP de pruebas solo en debug. No sobrescribe `lib/`. Producción requiere HTTPS y firma propia.

Documentación y funciones pendientes: [APP_MOVIL.md](../docs/APP_MOVIL.md).
