from datetime import timedelta
from django.core.exceptions import ValidationError
from asistencia.services.revision import puede_aprobar, revisar, registrar_historial
from asistencia.services.revision_trabajador import detalles_en_lote


def aprobar_jornadas_listas(jornadas, desde, hasta, actor):
    """El llamador mantiene una transacción y bloquea las jornadas del trabajador."""
    if not puede_aprobar(actor):
        raise ValidationError("Solo Contabilidad o Gerencia puede aprobar jornadas.")
    if not jornadas:
        raise ValidationError("No hay jornadas disponibles para aprobar.")
    resultado = {"aprobadas": 0, "ya_aprobadas": 0, "pendientes": []}
    for detalle in detalles_en_lote(jornadas):
        resumen = detalle["resumen"]
        if resumen.verificado_contabilidad:
            resultado["ya_aprobadas"] += 1
            continue
        motivos = list(detalle["bloqueos"])
        if detalle['solo_situacion']:
            motivos.insert(0, 'Seleccione la situación del día y apruébelo individualmente desde su fila.')
        if detalle["cerrada"]:
            motivos.insert(0, "El día pertenece a un periodo cerrado.")
        if resumen.estado_revision == "OBSERVADO":
            motivos.insert(0, "La jornada está observada y requiere revisión individual.")
        if not motivos:
            try:
                revisar(resumen, actor, "APROBADO", f"Aprobación conjunta del periodo {desde} al {hasta}.")
                resultado["aprobadas"] += 1
            except ValidationError as exc:
                motivos = exc.messages
        if motivos:
            resultado["pendientes"].append({"fecha": resumen.fecha.isoformat(), "motivos": motivos})
    registradas = {r.fecha for r in jornadas}
    fecha = desde
    while fecha <= hasta:
        if fecha not in registradas:
            resultado["pendientes"].append({"fecha": fecha.isoformat(), "motivos": ["Sin jornada registrada: indique la situación del día antes de aprobarlo."]})
        fecha += timedelta(days=1)
    resultado["pendientes"].sort(key=lambda fila: fila["fecha"])
    registrar_historial(None, actor, "Aprobación conjunta de jornadas", f"Trabajador DNI {jornadas[0].persona.dni}; {desde} al {hasta}. Nuevas aprobaciones: {resultado['aprobadas']}; ya aprobadas: {resultado['ya_aprobadas']}; fechas pendientes: {len(resultado['pendientes'])}.")
    return resultado
