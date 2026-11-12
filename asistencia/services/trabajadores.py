from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from asistencia.models import MarcacionBiometrica
from asistencia.services.revision import comprobar_abierto, registrar_historial


def vincular_ficha(identidad, trabajador, actor):
    """Llamar con la identidad bloqueada dentro de una transacción."""
    if identidad.trabajador_id and identidad.trabajador_id != trabajador.pk:
        raise ValidationError("Este código ya identifica a otro trabajador. No se reasigna para proteger el historial.")
    if identidad.usuario_id and identidad.usuario_id != trabajador.usuario_id:
        raise ValidationError("Este código tiene una asociación anterior con otra persona. Revise su historial.")
    marcas = MarcacionBiometrica.objects.filter(Q(identidad_biometrica=identidad) | Q(filas_origen__identidad=identidad)).distinct()
    for marca in marcas:
        comprobar_abierto(timezone.localtime(marca.fecha_hora).date())
        if marca.usuario_id and marca.usuario_id != trabajador.usuario_id:
            raise ValidationError("Hay marcaciones asociadas a otra persona. Revise la procedencia.")
    identidad.trabajador = trabajador
    identidad.nombre = trabajador.nombre_completo
    identidad.save(update_fields=["trabajador", "nombre"])
    registrar_historial(None, actor, "Ficha de trabajador vinculada", f"Identidad #{identidad.pk}: {identidad.sede} / {identidad.equipo} / {identidad.codigo}. Trabajador #{trabajador.pk}: {trabajador.nombre_completo}.")


def corregir_ficha_duplicada(origen, destino, actor):
    """Las fichas deben estar bloqueadas dentro de una transacción."""
    if origen.pk == destino.pk:
        return
    if origen.usuario_id:
        raise ValidationError("La ficha que desea corregir tiene una cuenta de acceso. No se pueden unir cuentas desde esta ventana.")
    if origen.jornadas.exists():
        raise ValidationError("La ficha ya tiene jornadas en Asistencia. Revise esas jornadas antes de unirla con otra ficha.")
    identidades = list(origen.identidades.select_for_update())
    ids = [i.pk for i in identidades]
    for identidad in identidades:
        if identidad.usuario_id and identidad.usuario_id != destino.usuario_id:
            raise ValidationError("Uno de los códigos está asociado a otra cuenta. Revise la procedencia antes de corregirlo.")
    marcas = MarcacionBiometrica.objects.filter(Q(identidad_biometrica_id__in=ids) | Q(filas_origen__identidad_id__in=ids)).distinct()
    for marca in marcas:
        comprobar_abierto(timezone.localtime(marca.fecha_hora).date())
        if marca.usuario_id and marca.usuario_id != destino.usuario_id:
            raise ValidationError("Hay marcaciones vinculadas a otra persona. No se realizó ningún cambio.")
    detalle = (f"Ficha duplicada #{origen.pk}: {origen.nombre_completo}, DNI {origen.dni}, área {origen.area}. "
               f"Ficha conservada #{destino.pk}: {destino.nombre_completo}, DNI {destino.dni}, área {destino.area}. "
               f"Códigos conservados: " + "; ".join(f"{i.sede}/{i.equipo}/{i.codigo}" for i in identidades))
    origen.identidades.update(trabajador=destino, nombre=destino.nombre_completo)
    registrar_historial(None, actor, "Ficha duplicada corregida", detalle)
    origen.delete()
