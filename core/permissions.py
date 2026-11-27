"""Políticas comunes de lectura y escritura por rol."""


def solo_consulta(usuario):
    # El rol prevalece incluso si la cuenta tiene is_staff/is_superuser.
    return bool(usuario and getattr(usuario, 'is_authenticated', False)
                and getattr(usuario, 'rol', '') == 'GERENTE_GENERAL')


MENSAJE_SOLO_CONSULTA = (
    'Gerente General tiene acceso de solo consulta. No puede modificar registros.'
)
