from django.conf import settings


def solicitudes_notificacion(request):
    """Solicitudes pendientes para el timbre de la barra superior."""
    usuario = getattr(request, 'user', None)
    if not usuario or not usuario.is_authenticated:
        return {'solicitudes_notificacion': [], 'puede_ver_notificaciones': False}
    from asistencia.services.revision import puede_gestionar
    if not puede_gestionar(usuario):
        return {'solicitudes_notificacion': [], 'puede_ver_notificaciones': False}
    from movil.models import Solicitud
    pendientes = Solicitud.objects.filter(estado='PENDIENTE').select_related(
        'perfil__trabajador', 'perfil__usuario').order_by('-creado')[:20]
    return {'puede_ver_notificaciones': True, 'solicitudes_notificacion': [
        {'id': s.pk,
         'nombre': (s.perfil.trabajador.nombre_completo
                    if s.perfil.trabajador_id and s.perfil.trabajador
                    else s.perfil.usuario.get_full_name()),
         'tipo': s.tipo, 'desde': str(s.desde), 'hasta': str(s.hasta),
         'detalle': s.detalle}
        for s in pendientes
    ]}


def edicion(request):
    from asistencia.services.revision import puede_gestionar
    usuario = getattr(request, 'user', None)
    mostrar_personal = bool(usuario and usuario.is_authenticated and puede_gestionar(usuario))
    from core.permissions import solo_consulta
    escritorio=getattr(settings,'ESCRITORIO',False)
    return {'sismoc_escritorio':escritorio,
            'solo_consulta': solo_consulta(usuario),
            'puede_editar': mostrar_personal and not solo_consulta(usuario),
            'sismoc_mostrar_personal': mostrar_personal,
            'sismoc_movil_habilitado':getattr(settings,'MOVIL_HABILITADO',True),
            'sismoc_edicion':'Gestión de la empresa'}
