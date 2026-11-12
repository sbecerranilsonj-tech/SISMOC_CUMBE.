# ==============================================================================
# asistencia/schemas.py
# SISMOC-CUMBE | Esquemas Pydantic / Ninja para Asistencia y Biometría
# ==============================================================================

from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional, List
from ninja import Schema
from pydantic import Field


class MarcacionCreateSchema(Schema):
    """Esquema para registrar una marcación manual o desde App Móvil / Facial."""
    dni: str = Field(..., min_length=8, max_length=8, description="DNI del trabajador")
    tipo_evento: str = Field(
        "ENTRADA",
        description="ENTRADA, SALIDA, SALIDA_REFRIGERIO, RETORNO_REFRIGERIO",
    )
    origen: Optional[str] = "APP_MOVIL_GPS"
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    dispositivo_ip: Optional[str] = None


class MarcacionOutSchema(Schema):
    """Detalle de una marcación biométrica registrada."""
    id: int
    dni: str
    nombre_empleado: str
    fecha_hora: datetime
    tipo_evento: str
    tipo_evento_display: str
    origen: str
    origen_display: str
    es_valida: bool

    @staticmethod
    def resolve_tipo_evento_display(obj):
        return obj.get_tipo_evento_display()

    @staticmethod
    def resolve_origen_display(obj):
        return obj.get_origen_display()


class ResumenAsistenciaOutSchema(Schema):
    """Resumen diario de asistencia para cálculo de planillas."""
    id: int
    dni: str
    nombre_completo: str
    rol: str
    agencia_sede: str
    fecha: date
    primera_entrada: Optional[time] = None
    ultima_salida: Optional[time] = None
    minutos_tardanza: int
    horas_trabajadas: Decimal
    horas_extras_25: Decimal
    horas_extras_35: Decimal
    horas_nocturnas: Decimal
    vueltas_codigo: str
    total_vueltas_num: int
    estado: str
    estado_display: str
    observaciones: str
    verificado_contabilidad: bool
    estado_revision: str
    fecha_revision: Optional[datetime] = None

    @staticmethod
    def resolve_dni(obj):
        return obj.persona.dni if obj.persona else ""

    @staticmethod
    def resolve_nombre_completo(obj):
        return obj.persona.nombre_completo if obj.persona else ""

    @staticmethod
    def resolve_rol(obj):
        return obj.persona.rol if obj.persona else ""

    @staticmethod
    def resolve_agencia_sede(obj):
        return obj.persona.agencia_sede if obj.persona else ""

    @staticmethod
    def resolve_estado_display(obj):
        return obj.get_estado_display()

    @staticmethod
    def resolve_estado_revision(obj):
        from asistencia.services.revision import estado_revision
        return estado_revision(obj)


class CargaExcelResponseSchema(Schema):
    """Resultado del procesamiento de un archivo Excel de ZKTeco con Pandas."""
    archivo: str
    carga_id: int
    hojas_encontradas: int
    filas_procesadas: int
    empleados_identificados: int
    total_he_25: Decimal
    total_he_35: Decimal
    total_vueltas_choferes: int
    resumenes_generados: int
    alertas: List[str]
    exito: bool
    codigos_biometricos: int = 0
    identidades_pendientes: int = 0
    marcaciones_nuevas: int = 0
    marcaciones_repetidas: int = 0


class ColaboradorPresenteSchema(Schema):
    """Personal presente en tiempo real hoy."""
    dni: str
    nombre: str
    rol: str
    rol_display: str
    agencia_sede: str
    primera_marcacion: str
    tipo_evento: str
    origen: str
    estado_asistencia: str


class SincronizacionHuelleroOutSchema(Schema):
    """Respuesta de la sincronización en vivo con el biométrico ZKTeco."""
    dispositivo_ip: str
    dispositivo_puerto: int
    estado_dispositivo: str
    fecha_consulta: str
    total_presentes_hoy: int
    nuevas_marcaciones_sincronizadas: int
    colaboradores_presentes: List[ColaboradorPresenteSchema]


class ReportePlanillaConsolidadoSchema(Schema):
    """Totales de nómina calculados para la Contadora (CPC. Yaneli Terrones)."""
    periodo: str
    total_colaboradores: int
    total_horas_efectivas: Decimal
    total_horas_extras_25: Decimal
    total_horas_extras_35: Decimal
    total_horas_nocturnas: Decimal
    total_minutos_tardanza: int
    total_vueltas_conductores: int
    desglose_por_empleado: List[dict]
