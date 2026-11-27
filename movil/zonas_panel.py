"""Personas incluidas por el mismo alcance que valida las marcaciones GPS."""
from .models import Perfil, Zona


def agrupar_zonas():
    personas = list(Perfil.objects.filter(
        activo=True, trabajador__isnull=False, conductor__isnull=True,
        usuario__is_active=True, usuario__esta_activo=True,
    ).select_related('trabajador', 'usuario').order_by('trabajador__nombre_completo', 'pk'))
    zonas = list(Zona.objects.prefetch_related('perfiles__trabajador').order_by('sede', 'nombre', 'pk'))
    for zona in zonas:
        individuales = {p.pk for p in zona.perfiles.all()}
        zona.personas = [p for p in personas if (
            p.pk in individuales if individuales else (
                p.trabajador.sede.strip().lower() == zona.sede.lower()
                and (not zona.area or p.trabajador.area.strip().lower() == zona.area.lower())
            )
        )]
    return zonas
