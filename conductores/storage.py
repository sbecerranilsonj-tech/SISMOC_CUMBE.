from django.conf import settings
from django.core.files.storage import FileSystemStorage


def almacen_itinerarios():
    return FileSystemStorage(location=getattr(settings,'PRIVATE_CONDUCTORES_ROOT',settings.BASE_DIR / 'private_conductores'))
