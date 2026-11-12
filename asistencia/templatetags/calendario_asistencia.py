from django import template
from asistencia.services.reglas_jornada import calendario_especial
register = template.Library()
@register.simple_tag
def indicador_calendario(fecha):
    nombre = calendario_especial(fecha, fecha).get(fecha, '')
    semana = fecha.weekday()
    return {'dia': ('Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo')[semana], 'clase': 'feriado' if nombre else 'sabado' if semana == 5 else 'domingo' if semana == 6 else 'normal', 'feriado': nombre}
