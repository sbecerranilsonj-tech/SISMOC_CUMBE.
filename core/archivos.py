"""Validación común de archivos subidos antes de pasarlos a un parser."""
from django.core.exceptions import ValidationError

TAMANO_MAXIMO = 10 * 1024 * 1024
TAMANO_MAXIMO_DOCUMENTOS = 20 * 1024 * 1024


def validar_archivo_subido(archivo, extensiones, tamano_maximo=TAMANO_MAXIMO,
                           verificar_zip=False):
    """Devuelve el archivo si nombre, tamaño y firma son aceptables."""
    nombre = str(getattr(archivo, 'name', '') or '').lower()
    if not nombre.endswith(tuple(extensiones)):
        raise ValidationError('Formato de archivo no permitido.')
    tamano = getattr(archivo, 'size', None)
    if tamano is not None and tamano > tamano_maximo:
        raise ValidationError('El archivo supera el tamaño máximo permitido de 10 MB.')
    if verificar_zip or nombre.endswith(('.xlsx', '.xls', '.xlsm')):
        archivo.seek(0)
        cabecera = archivo.read(4) or b''
        archivo.seek(0)
        if cabecera[:2] != b'PK':
            raise ValidationError('El archivo no es un libro Excel válido.')
    return archivo
