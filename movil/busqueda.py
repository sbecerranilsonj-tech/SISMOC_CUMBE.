from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from django.http import JsonResponse, HttpResponseForbidden
from asistencia.models import Trabajador
from conductores.models import Conductor
from conductores.parser import normalizar
from .models import Perfil
from .funciones import funcion_por_area
from .views import GESTION, VENTAS, nombre
from django.db.models import Q

@login_required
@require_GET
@never_cache
def sugerencias_personas(request):
    scope=request.GET.get('scope','personas')
    if request.user.rol not in (VENTAS if scope in ('embarcadores','conductores') else GESTION):
        return HttpResponseForbidden('No tiene permiso para buscar personas.')
    consulta=normalizar(request.GET.get('q','')[:100])
    if not consulta:
        return JsonResponse({'resultados':[]})
    tokens=consulta.split()
    if scope in ('perfiles','personal','embarcadores','conductores'):
        perfiles=Perfil.objects.filter(activo=True,usuario__is_active=True,usuario__esta_activo=True).select_related('usuario','trabajador','conductor')
        if scope in ('personal','perfiles'):
            perfiles=perfiles.exclude(Q(usuario__rol__in=GESTION)&(Q(trabajador__area='')|Q(trabajador__isnull=True)))
        if scope=='perfiles':perfiles=perfiles.filter(Q(trabajador__isnull=False)|Q(conductor__isnull=False))
        if scope=='personal':perfiles=perfiles.filter(trabajador__isnull=False,conductor__isnull=True)
        if scope=='embarcadores':perfiles=perfiles.filter(Q(usuario__rol='OPERADOR_EMBARQUE')|Q(conductor__isnull=False))
        if scope=='conductores':perfiles=perfiles.filter(conductor__isnull=False)
        encontrados=[]
        for p in perfiles:
            area='Conductores' if p.conductor_id else (p.trabajador.area if p.trabajador_id else '')
            texto=normalizar(' '.join([nombre(p),p.codigo,area]))
            if all(t in texto for t in tokens):
                encontrados.append({'id':str(p.pk),'nombre':nombre(p),'tipo':'Conductor' if p.conductor_id else 'Trabajador','area':area,'sede':p.trabajador.sede if p.trabajador_id and not p.conductor_id else ''})
        encontrados.sort(key=lambda x:normalizar(x['nombre']))
        return JsonResponse({'resultados':encontrados[:8]})
    conductores=list(Conductor.objects.select_related('trabajador'))
    vinculados={c.trabajador_id for c in conductores if c.trabajador_id}
    perfiles={p.conductor_id:p for p in Perfil.objects.filter(conductor__isnull=False).select_related('usuario')}
    resultados=[]
    def agregar(tipo,pk,nombre,area,sede='',dni='',requiere=False):
        texto=normalizar(' '.join([nombre,area,sede,dni]))
        if all(token in texto for token in tokens):
            resultados.append({'id':f'{tipo}:{pk}','nombre':nombre,'tipo':'Conductor' if tipo=='conductor' else 'Trabajador',
                'area':area,'sede':sede,'requiere_identidad':requiere,'funcion_app':funcion_por_area(area,tipo=='conductor')})
    for t in Trabajador.objects.exclude(pk__in=vinculados).exclude(usuario__rol__in=GESTION,area=''):
        agregar('trabajador',t.pk,t.nombre_completo,t.area,t.sede,t.dni)
    for c in conductores:
        t=c.trabajador
        perfil=perfiles.get(c.pk)
        agregar('conductor',c.pk,c.nombre_apellidos,'Conductores','',
            t.dni if t else (perfil.usuario.dni if perfil else ''),not t and not perfil)
    resultados.sort(key=lambda x:(not normalizar(x['nombre']).startswith(consulta),normalizar(x['nombre']),x['id']))
    return JsonResponse({'resultados':resultados[:8]})
