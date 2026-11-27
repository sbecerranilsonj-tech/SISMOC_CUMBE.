"""Regularización auditada de llegadas olvidadas, sin inventar horarios."""
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import Auditoria, EventoViaje, Operacion
from .views import PERU, Problema, asignado, exigir, aviso_operacion


def fecha_registro(valor):
    """Acepta ISO con zona, sin zona (hora local de Perú) o DD/MM/AAAA HH:mm."""
    texto = str(valor or '').strip().replace('Z', '+00:00')
    try:
        resultado = datetime.fromisoformat(texto)
    except ValueError:
        try:
            resultado = datetime.strptime(texto, '%d/%m/%Y %H:%M')
        except ValueError as exc:
            raise Problema('Revise la fecha y hora de llegada.', 422) from exc
    if not timezone.is_aware(resultado):
        resultado = resultado.replace(tzinfo=PERU)
    return resultado


@transaction.atomic
def regularizar_llegada(datos, perfil):
    op = Operacion.objects.select_for_update().select_related('salida').get(
        pk=datos.get('viaje'))
    exigir(asignado(op, perfil) or perfil.usuario.rol in {
        'CONTADORA', 'ADMINISTRADOR', 'GERENTE_GENERAL'},
        'No está autorizado a regularizar este viaje.', 403)
    exigir(op.estado == 'EN_CURSO' and op.salida_real and not op.llegada_real,
           'Este viaje no tiene una llegada pendiente.', 409)
    eid = uuid.UUID(datos.get('id', ''))
    exigir(not EventoViaje.objects.filter(pk=eid).exists(),
           'El registro ya fue enviado. Actualice el viaje.', 409)
    llegada = fecha_registro(datos.get('llegada', ''))
    ahora = timezone.now()
    exigir(op.salida_real <= llegada <= ahora + timedelta(minutes=5),
           'La llegada debe estar entre la salida registrada y la hora actual.', 422)
    exigir(llegada >= op.salida_real + timedelta(hours=7),
           'Revise la hora: el trayecto debe durar al menos 7 horas.', 422)
    motivo = str(datos.get('motivo', '')).strip()
    op.llegada_real = llegada
    op.estado = 'FINALIZADO'
    op.conduciendo = None
    op.relevo_pendiente = None
    op.llegadas_confirmadas.add(perfil)
    op.save()
    EventoViaje.objects.create(
        id=eid, operacion=op, perfil=perfil, tipo='LLEGADA_TARDIA',
        datos={'llegada': llegada.isoformat(), 'motivo': motivo,
               'registrada_el': ahora.isoformat()})
    Auditoria.objects.create(
        actor=perfil.usuario, accion='regularizar_llegada',
        detalle={'viaje': op.pk, 'salida': op.salida.pk,
                 'llegada': llegada.isoformat(), 'motivo': motivo})
    aviso_operacion(op, f'{op.salida.origen} → {op.salida.destino}: '
                         f'llegada registrada después del viaje con auditoría.')
    return {'mensaje': 'Llegada registrada con la hora indicada y su motivo. '
                       'El viaje quedó finalizado para revisión y descanso.'}
