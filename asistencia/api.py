# ==============================================================================
# asistencia/api.py
# SISMOC-CUMBE | Endpoints de Asistencia Biometría ZKTeco y Tiempo Real
# ==============================================================================

from typing import List, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.db import transaction
from ninja import Router, File, UploadedFile
from ninja.errors import HttpError

from core.models import Usuario
from core.security import (
    auth_any,
    auth_admin_only,
    auth_contadora_or_admin,
)
from asistencia.models import (
    MarcacionBiometrica,
    ResumenAsistenciaDiaria,
    CargaArchivoAsistencia,
    TurnoHorario,
)
from asistencia.schemas import (
    MarcacionCreateSchema,
    MarcacionOutSchema,
    ResumenAsistenciaOutSchema,
    CargaExcelResponseSchema,
    SincronizacionHuelleroOutSchema,
    ReportePlanillaConsolidadoSchema,
)
from asistencia.services.zkteco_parser import ZKTecoExcelParser
from asistencia.services.zkteco_live import ZKTecoLiveClient

router = Router()


@router.post("/marcar", response=MarcacionOutSchema, auth=auth_any)
def registrar_marcacion(request, data: MarcacionCreateSchema):
    """
    Registra una marcación biométrica o móvil en tiempo real.
    Puede ser invocada desde:
    - App Móvil con Reconocimiento Facial + GPS en paraderos.
    - Kiosko de marcación por DNI en terminales.
    - Webhook / Servicio de sincronización del reloj ZKTeco.
    """
    dni = data.dni.strip()
    if not dni.isdigit() or len(dni) != 8:
        raise HttpError(400, "El DNI debe contener ocho dígitos.")
    from asistencia.services.revision import puede_gestionar
    if request.auth.dni != dni and not puede_gestionar(request.auth):
        raise HttpError(403, "Solo puede registrar su propia asistencia.")
    if data.tipo_evento not in MarcacionBiometrica.TipoEvento.values:
        raise HttpError(400, "Tipo de evento no válido.")
    if data.origen not in MarcacionBiometrica.OrigenMarcacion.values:
        raise HttpError(400, "Origen de marcación no válido.")
    if data.origen == "SISTEMA_MANUAL":
        raise HttpError(400, "Use Agregar marcación manual en el detalle de la jornada para registrar su responsable y justificación.")
    usuario = Usuario.objects.filter(dni=dni).first()

    ahora = timezone.localtime(timezone.now())

    nueva_marcacion = MarcacionBiometrica.objects.create(
        usuario=usuario,
        dni=dni,
        nombre_empleado=usuario.nombre_completo if usuario else f"Trabajador DNI {dni}",
        zkteco_user_id=usuario.zkteco_user_id if usuario else None,
        fecha_hora=ahora,
        tipo_evento=data.tipo_evento,
        origen=data.origen or MarcacionBiometrica.OrigenMarcacion.APP_MOVIL_GPS,
        latitud=data.latitud,
        longitud=data.longitud,
        dispositivo_ip=data.dispositivo_ip,
        es_valida=True,
    )

    # Si hay usuario registrado, actualizar o crear el resumen diario
    if usuario:
        from asistencia.services.horarios import turno_programado, actualizar_tardanza
        fecha_hoy = ahora.date()
        resumen_abierto = None
        if data.tipo_evento != "ENTRADA":
            resumen_abierto = ResumenAsistenciaDiaria.objects.filter(
                usuario=usuario, fecha__range=(fecha_hoy - timedelta(days=1), fecha_hoy),
                primera_entrada__isnull=False, ultima_salida__isnull=True,
            ).order_by("-fecha").first()
        resumen, _ = (resumen_abierto, False) if resumen_abierto else ResumenAsistenciaDiaria.objects.get_or_create(
            usuario=usuario,
            fecha=fecha_hoy,
            defaults={
                "primera_entrada": ahora.time() if data.tipo_evento == "ENTRADA" else None,
                "turno_aplicado": turno_programado(usuario, fecha_hoy),
                "estado": ResumenAsistenciaDiaria.EstadoAsistencia.POR_REVISAR,
            },
        )
        if data.tipo_evento == "ENTRADA" and not resumen.primera_entrada:
            resumen.primera_entrada = ahora.time()
        if data.tipo_evento == "SALIDA":
            resumen.ultima_salida = ahora.time()
        if resumen.marcaciones_publicadas is not None:
            resumen.marcaciones_publicadas = [*resumen.marcaciones_publicadas, nueva_marcacion.pk]
        resumen.save()
        actualizar_tardanza(resumen)

    return nueva_marcacion


@router.post("/subir-excel", response=CargaExcelResponseSchema, auth=auth_contadora_or_admin)
def subir_excel_zkteco(request, file: UploadedFile = File(...)):
    """
    Importa y procesa en segundos archivos Excel exportados del biométrico ZKTeco
    (como 'ASISTENCIA AGOSTO 2026.xlsx' con 50+ hojas o formato tabular).
    Aplica el algoritmo de Horas Extras (25%/35%), sobretasa nocturna y vueltas de choferes.
    """
    nombre = file.name
    if not (nombre.endswith(".xlsx") or nombre.endswith(".xls") or nombre.endswith(".csv")):
        raise HttpError(400, "El archivo debe ser un libro de Excel (.xlsx, .xls) o CSV de ZKTeco.")

    usuario = request.auth
    parser = ZKTecoExcelParser(
        archivo_path_o_bytes=file,
        nombre_archivo=nombre,
        subido_por=usuario,
    )

    try:
        with transaction.atomic():
            resultado = parser.procesar()
        return resultado
    except Exception as e:
        raise HttpError(500, f"Error al procesar el archivo Excel de ZKTeco: {str(e)}")


@router.post("/sincronizar-huellero", response=SincronizacionHuelleroOutSchema, auth=auth_contadora_or_admin)
def sincronizar_huellero_en_tiempo_real(request, ip: Optional[str] = None, puerto: Optional[int] = None):
    """
    Se conecta directamente por socket TCP/IP al reloj biométrico ZKTeco físico en la agencia.
    Descarga marcaciones en caliente y actualiza el estado de presencia de choferes y administrativos.
    """
    client = ZKTecoLiveClient(ip=ip, port=puerto)
    res = client.sincronizar_marcaciones_en_vivo()
    return res


@router.get("/tiempo-real", response=SincronizacionHuelleroOutSchema, auth=auth_contadora_or_admin)
def consultar_asistencia_tiempo_real(request):
    """
    Retorna la lista de trabajadores presentes hoy en tiempo real,
    su hora de ingreso, rol, agencia y estado de asistencia.
    """
    client = ZKTecoLiveClient()
    return client.sincronizar_marcaciones_en_vivo()


@router.get("/resumen", response=List[ResumenAsistenciaOutSchema], auth=auth_any)
def listar_resumenes_asistencia(
    request,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    dni: Optional[str] = None,
    rol: Optional[str] = None,
):
    """
    Consulta los resúmenes diarios de asistencia con desglose de horas trabajadas,
    horas extras al 25% y 35%, horas nocturnas, tardanzas y vueltas de conductores.
    """
    queryset = ResumenAsistenciaDiaria.objects.select_related("usuario").all()

    # Si es un empleado normal o conductor, solo puede ver su propia asistencia
    usuario_actual = request.auth
    from asistencia.services.revision import puede_gestionar
    if usuario_actual and not puede_gestionar(usuario_actual):
        queryset = queryset.filter(Q(usuario=usuario_actual) | Q(trabajador__usuario=usuario_actual))
    elif dni:
        queryset = queryset.filter(Q(usuario__dni=dni.strip()) | Q(trabajador__dni=dni.strip()))

    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)
    if rol:
        queryset = queryset.filter(usuario__rol=rol)

    return list(queryset[:200])


@router.get("/reporte-planilla", response=ReportePlanillaConsolidadoSchema, auth=auth_contadora_or_admin)
def reporte_planilla_consolidado(
    request,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    mes_periodo: Optional[str] = None,
):
    """
    Genera el reporte oficial de nómina/planilla para la Contadora General (CPC. Yaneli Terrones).
    Consolida:
    - Total de Horas Efectivas
    - Horas Extras al 25% (2 primeras horas)
    - Horas Extras al 35% (a partir de la 3ra hora)
    - Sobretasa nocturna (22:00 a 06:00)
    - Total de Vueltas de Choferes ('X' simples y 'XX' dobles)
    - Minutos acumulados de tardanza
    """
    ahora = timezone.localtime()
    if not fecha_inicio:
        fecha_inicio = ahora.date().replace(day=1)
    if not fecha_fin:
        fecha_fin = ahora.date()
    if fecha_fin < fecha_inicio:
        raise HttpError(400, "La fecha final no puede ser anterior a la inicial.")

    periodo_str = mes_periodo or fecha_inicio.strftime("%Y-%m")

    queryset = ResumenAsistenciaDiaria.objects.filter(
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin,
    ).select_related("usuario").prefetch_related("ajustes")

    totales = queryset.aggregate(
        sum_horas=Sum("horas_trabajadas"),
        sum_he_25=Sum("horas_extras_25"),
        sum_he_35=Sum("horas_extras_35"),
        sum_nocturnas=Sum("horas_nocturnas"),
        sum_tardanza=Sum("minutos_tardanza"),
        sum_vueltas=Sum("total_vueltas_num"),
    )

    from asistencia.views import consolidar
    grupos = consolidar(queryset)
    desglose = []
    ajustados = {"horas_trabajadas": Decimal(0), "horas_extras_25": Decimal(0), "horas_extras_35": Decimal(0), "horas_nocturnas": Decimal(0)}
    for fila in grupos:
        persona = fila["usuario"]
        desglose.append({
            "usuario_id": persona.usuario_id if hasattr(persona, "usuario_id") else persona.pk,
            "trabajador_id": persona.pk if hasattr(persona, "usuario_id") else None,
            "dni": persona.dni, "nombre_completo": persona.nombre_completo,
            "rol": persona.rol, "rol_display": persona.get_rol_display(),
            "dias_asistidos": fila["jornadas"], "total_horas": float(fila["horas_trabajadas"]),
            "horas_extras_25": float(fila["horas_extras_25"]), "horas_extras_35": float(fila["horas_extras_35"]),
            "horas_nocturnas": float(fila["horas_nocturnas"]), "minutos_tardanza": fila["tardanza"],
            "total_vueltas_chofer": sum(r.total_vueltas_num for r in queryset if r.persona.dni == persona.dni),
            "jornadas_aprobadas": fila["aprobadas"], "jornadas_pendientes": fila["pendientes"] + fila["observadas"],
        })
        for campo in ajustados:
            ajustados[campo] += fila[campo]

    return {
        "periodo": periodo_str,
        "total_colaboradores": len(desglose),
        "total_horas_efectivas": ajustados["horas_trabajadas"],
        "total_horas_extras_25": ajustados["horas_extras_25"],
        "total_horas_extras_35": ajustados["horas_extras_35"],
        "total_horas_nocturnas": ajustados["horas_nocturnas"],
        "total_minutos_tardanza": totales["sum_tardanza"] or 0,
        "total_vueltas_conductores": totales["sum_vueltas"] or 0,
        "desglose_por_empleado": desglose,
    }


@router.put("/verificar-resumen/{int:resumen_id}", auth=auth_contadora_or_admin)
def verificar_resumen_contabilidad(request, resumen_id: int):
    """Permite a la Contadora marcar como verificado y aprobado el registro de asistencia."""
    try:
        resumen = ResumenAsistenciaDiaria.objects.get(id=resumen_id)
    except ResumenAsistenciaDiaria.DoesNotExist:
        raise HttpError(404, "Resumen de asistencia no encontrado")

    from asistencia.services.revision import revisar
    from django.core.exceptions import ValidationError
    try:
        with transaction.atomic():
            resumen = ResumenAsistenciaDiaria.objects.select_for_update().get(pk=resumen_id)
            revisar(resumen, request.auth, "APROBADO")
    except ValidationError as exc:
        raise HttpError(400, " ".join(exc.messages))
    return {"mensaje": f"Resumen del {resumen.fecha} verificado con éxito.", "exito": True}
