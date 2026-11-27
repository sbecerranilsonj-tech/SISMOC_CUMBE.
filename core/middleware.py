from django.http import JsonResponse
from django.urls import resolve, Resolver404

from .permissions import solo_consulta, MENSAJE_SOLO_CONSULTA


class GerenteSoloConsultaMiddleware:
    """Denegar escrituras web antes de ejecutar cualquier vista del sistema."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if solo_consulta(getattr(request, 'user', None)) and request.method not in {
            'GET', 'HEAD', 'OPTIONS',
        }:
            try:
                ruta = resolve(request.path_info)
            except Resolver404:
                ruta = None
            # Autenticación y cierre de sesión no modifican datos operativos.
            if not ruta or ruta.url_name not in {'login', 'logout'}:
                return JsonResponse(
                    {'ok': False, 'error': MENSAJE_SOLO_CONSULTA}, status=403)
        return self.get_response(request)
