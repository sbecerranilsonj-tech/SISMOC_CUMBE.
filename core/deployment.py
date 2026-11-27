"""Comprobación de disponibilidad y entrega autenticada de archivos privados."""
from pathlib import Path
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, FileResponse, HttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache


@require_GET
def health(request):
    return HttpResponse('ok',content_type='text/plain')


@login_required
@never_cache
@require_GET
def archivo_media(request,path):
    user=request.user
    if not user.is_active or not user.esta_activo:
        raise Http404
    gestor=user.is_superuser or user.rol in {'ADMINISTRADOR','CONTADORA','GERENTE_GENERAL'}
    if not gestor and (not user.foto or user.foto.name != path):
        raise Http404
    base=Path(settings.MEDIA_ROOT).resolve()
    archivo=(base/path).resolve()
    if not archivo.is_relative_to(base) or not archivo.is_file():
        raise Http404
    inline=archivo.suffix.lower() in {'.jpg','.jpeg','.png','.webp','.gif'}
    response=FileResponse(archivo.open('rb'),as_attachment=not inline,filename=archivo.name)
    response['X-Content-Type-Options']='nosniff'
    return response
