"""Carga de una sola jornada, sin reconstruir el resto del periodo."""
from datetime import date, timedelta
from urllib.parse import urlencode
from django.shortcuts import get_object_or_404
from asistencia.models import PeriodoVacaciones, MarcacionBiometrica, IncidenciaAsistencia, AjusteAsistencia
from asistencia.services.revision import detalle_jornada, puede_gestionar, puede_aprobar
from asistencia.services.reglas_jornada import calendario_especial


def contexto_detalle_rapido(request):
    from asistencia.views import reporte_filtrado, queryset_visible
    from asistencia.services.revision_trabajador import filtrar_persona
    filtros, qs = reporte_filtrado(request)
    r=get_object_or_404(queryset_visible(request.user),pk=int(request.GET['detalle']))
    d=detalle_jornada(r)
    inicio,fin=date.fromisoformat(filtros['desde']),date.fromisoformat(filtros['hasta'])
    dias=list(filtrar_persona(queryset_visible(request.user),r.persona.dni).filter(fecha__range=(inicio,fin)).values('pk','fecha','verificado_contabilidad','estado','conceptos_editados'))
    por_fecha={s['fecha']:s for s in dias}
    vacaciones=list(PeriodoVacaciones.objects.filter(trabajador_id=r.trabajador_id,desde__lte=fin,hasta__gte=inicio)) if r.trabajador_id else []
    omitidas={s['fecha'] for s in dias if s['verificado_contabilidad'] and s['estado']=='VACACIONES' and any(v.aprobado_el and v.desde<=s['fecha']<=v.hasta for v in vacaciones)}
    omitidas.update(s['fecha'] for s in dias if s['verificado_contabilidad'] and s['estado']=='DIA_LIBRE' and s['conceptos_editados'].get('descanso_validado_programacion'))
    for direccion,paso in [('anterior',-1),('siguiente',1)]:
        fecha=r.fecha+timedelta(days=paso)
        while fecha in omitidas:fecha+=timedelta(days=paso)
        fecha=fecha if inicio<=fecha<=fin else None
        d[direccion+'_fecha']=fecha
        d[direccion+'_pk']=por_fecha.get(fecha,{}).get('pk')
    d['periodo_vacaciones']=next((v for v in vacaciones if v.desde<=r.fecha<=v.hasta),None)
    d['posicion_indice']=(r.fecha-inicio).days+1
    d['total_dias']=(fin-inicio).days+1
    especial=calendario_especial(r.fecha,r.fecha).get(r.fecha,'')
    semana=r.fecha.weekday()
    d['calendario_dia']={'dia':('Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo')[semana],'clase':'feriado' if especial else 'sabado' if semana==5 else 'domingo' if semana==6 else 'normal','feriado':especial}
    # Solo nombres e identificadores para las flechas entre trabajadores.
    personas={}
    for fila in qs.values('trabajador__dni','trabajador__nombre_completo','usuario__dni','usuario__first_name','usuario__last_name').distinct():
        dni=fila['trabajador__dni'] or fila['usuario__dni']
        nombre=fila['trabajador__nombre_completo'] or (str(fila['usuario__first_name'] or '')+' '+str(fila['usuario__last_name'] or '')).strip()
        personas[dni]=nombre
    orden=sorted(personas,key=lambda dni:personas[dni].casefold())
    rev={'dni':r.persona.dni,'persona':r.persona,'total_trabajadores':len(orden)}
    if r.persona.dni in orden:
        i=orden.index(r.persona.dni);rev['posicion_indice']=i+1
        for direccion,indice in [('anterior',i-1),('siguiente',i+1)]:
            if 0<=indice<len(orden):rev[direccion+'_dni']=orden[indice];rev[direccion+'_nombre']=personas[orden[indice]]
    query={k:v for k,v in filtros.items() if k!='error' and v};query['vista']='asistencia'
    return {'detalle_jornada':d,'revision_trabajador':rev,'filtros':filtros,'consulta_asistencia':urlencode(query),
            'puede_gestionar':puede_gestionar(request.user),'puede_aprobar':puede_aprobar(request.user),
            'tipos_evento':MarcacionBiometrica.TipoEvento.choices,'tipos_incidencia':IncidenciaAsistencia.TIPOS,'conceptos_ajuste':AjusteAsistencia.CONCEPTOS}
