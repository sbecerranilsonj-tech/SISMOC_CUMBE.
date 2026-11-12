from django.conf import settings


def edicion(request):
    escritorio=getattr(settings,'ESCRITORIO',False)
    return {'sismoc_escritorio':escritorio,
            'sismoc_movil_habilitado':getattr(settings,'MOVIL_HABILITADO',True),
            'sismoc_edicion':'Gestión de la empresa' if escritorio else 'Demostración académica'}
