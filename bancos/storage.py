from django.conf import settings
from django.core.files.storage import FileSystemStorage


def almacen_privado():
    # Se entrega exclusivamente mediante la vista con permisos, nunca por MEDIA_URL.
    return FileSystemStorage(location=getattr(settings,'PRIVATE_BANCOS_ROOT',settings.BASE_DIR / 'private_bancos'))
