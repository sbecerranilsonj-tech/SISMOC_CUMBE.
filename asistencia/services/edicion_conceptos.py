import re
from django.core.exceptions import ValidationError
from asistencia.services.revision import dejar_pendiente, registrar_historial

CONCEPTOS = ('jornada_base', 'horas_extras_25', 'horas_extras_35', 'horas_nocturnas')


def guardar_conceptos(resumen, datos, actor):
    if resumen.verificado_contabilidad:
        raise ValidationError('Reabra la jornada antes de editar sus tiempos.')
    nuevos = {k: v for k, v in resumen.conceptos_editados.items() if k not in CONCEPTOS}
    for concepto in CONCEPTOS:
        valor = datos.get(concepto, '08:00:00' if concepto == 'jornada_base' else '').strip().replace('−', '-')
        if concepto == 'horas_nocturnas' and not valor:
            from asistencia.services.reglas_jornada import es_area_vigilancia
            if es_area_vigilancia(resumen):
                continue
        patron = r'-?\d{1,2}:[0-5]\d:[0-5]\d' if concepto == 'horas_extras_25' else r'\d{1,2}:[0-5]\d:[0-5]\d'
        if not re.fullmatch(patron, valor):
            raise ValidationError('Ingrese los cuatro tiempos en formato HH:MM:SS.')
        h, m, s = map(int, valor.lstrip('-').split(':'))
        segundos = (h * 3600 + m * 60 + s) * (-1 if valor.startswith('-') else 1)
        if abs(segundos) > 86400:
            raise ValidationError('Cada tiempo debe estar entre 00:00:00 y 24:00:00.')
        nuevos[concepto] = segundos
    from asistencia.services.cuadro_excel import base_jornada_segundos
    if nuevos['jornada_base'] != base_jornada_segundos(resumen):
        from asistencia.services.revision import detalle_jornada
        from asistencia.services.reglas_jornada import trabajo_efectivo
        detalle = detalle_jornada(resumen, incluir_formulario=False)
        if detalle['completa']:
            extra = trabajo_efectivo(resumen, detalle['tramos']) - nuevos['jornada_base']
            for concepto, clave, calculado in [('horas_extras_25', 'he25', min(extra, 7200)), ('horas_extras_35', 'he35', max(0, extra - 7200))]:
                # Si solo se cambia la base, no convertir el resultado anterior en un ajuste manual.
                if datos.get(concepto, '').strip().replace('−', '-') == detalle['cuadro_excel']['totales'][clave].replace('−', '-'):
                    nuevos[concepto] = int(calculado)
    if nuevos == resumen.conceptos_editados:
        return
    registrar_historial(resumen, actor, 'Conceptos diarios editados', f'Antes: {resumen.conceptos_editados or "Cálculo original"}. Ahora (segundos): {nuevos}.')
    resumen.conceptos_editados = nuevos
    resumen.save(update_fields=['conceptos_editados'])
    dejar_pendiente(resumen, actor, 'Extras y nocturnas editadas; requiere aprobación de la jornada.')
