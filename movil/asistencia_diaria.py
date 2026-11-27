from urllib.parse import urlencode
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.shortcuts import get_object_or_404,redirect
from django.core.exceptions import ValidationError
from django.utils import timezone
from asistencia.models import ResumenAsistenciaDiaria
from asistencia.services.revision import puede_gestionar,comprobar_abierto
from .models import Registro,Auditoria
from .views import exigir,instante,Problema,publicar_marca,PERU

@login_required
@require_POST
def revisar_marca_diaria(request,pk):
    from asistencia.views import queryset_visible
    from django.http import HttpResponseForbidden
    if not puede_gestionar(request.user):return HttpResponseForbidden('No puede revisar marcaciones.')
    resumen=get_object_or_404(queryset_visible(request.user),pk=pk)
    try:
        with transaction.atomic():
            ResumenAsistenciaDiaria.objects.select_for_update().get(pk=resumen.pk)
            comprobar_abierto(resumen.fecha)
            registro=Registro.objects.select_for_update(of=('self',)).select_related('perfil__trabajador','perfil__usuario').get(pk=request.POST['registro'],jornada=resumen.fecha)
            exigir(registro.perfil.trabajador_id==resumen.trabajador_id and resumen.trabajador_id,'Esta marca no pertenece al trabajador y día seleccionados.')
            exigir(registro.perfil.usuario_id!=request.user.pk,'No puede revisar su propia marcación.',403)
            exigir(registro.estado=='POR_REVISAR','Esta marca ya fue revisada.',409)
            motivo=request.POST.get('motivo','').strip()
            exigir(len(motivo)>=5,'Indique el motivo de la revisión.')
            if request.POST.get('decision')=='aceptar':
                confirmado=instante(request.POST['fecha_confirmada']+'-05:00')
                dia=confirmado.astimezone(PERU).date()
                exigir(resumen.fecha<=dia<=resumen.fecha+timedelta(days=1) and confirmado<=timezone.now()+timedelta(minutes=2),'La hora confirmada no corresponde a esta jornada.')
                publicar_marca(registro,confirmado);registro.estado='REGISTRADO'
            else:
                exigir(request.POST.get('decision')=='rechazar','Seleccione una decisión válida.')
                registro.estado='RECHAZADO'
            registro.motivo=motivo[:500];registro.save()
            Auditoria.objects.create(actor=request.user,accion='marca_en_asistencia_diaria',detalle={'registro':str(registro.pk),'resumen':resumen.pk,'estado':registro.estado})
            messages.success(request,'Marcación revisada. La aprobación de la jornada se realiza en este detalle diario.')
    except (Problema,ValidationError,ValueError,KeyError,Registro.DoesNotExist) as e:
        messages.error(request,getattr(e,'mensaje',str(e)))
    return redirect('/?'+urlencode({'vista':'asistencia','detalle':resumen.pk,'desde':resumen.fecha,'hasta':resumen.fecha,'persona_dni':resumen.persona.dni}))
