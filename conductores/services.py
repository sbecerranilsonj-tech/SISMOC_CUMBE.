from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import Auditoria, Conductor, IdentidadConductor, Importacion, Salida, SituacionConductor
from .parser import identidad, normalizar


@transaction.atomic
def guardar_ficha(form, usuario):
    nuevo = form.save(commit=False)
    nombre_completo = ' '.join(filter(None, (nuevo.nombres, nuevo.apellido_paterno, nuevo.apellido_materno)))
    for nombre in (nuevo.nombre, nombre_completo):
        if nombre:
            existente = buscar_conductor(nombre)
            if existente and existente.pk != nuevo.pk:
                raise ValueError('Este nombre corresponde a otro conductor registrado. Revise la ficha existente.')
    if not nuevo.nombre:
        nuevo.nombre = nombre_completo
    nuevo.save()
    for nombre in (nuevo.nombre, nombre_completo):
        alias, _ = IdentidadConductor.objects.get_or_create(nombre_origen=identidad(nombre), defaults={'conductor': nuevo})
        if alias.conductor_id != nuevo.pk:
            raise ValueError('El nombre ya está asociado a otro conductor.')
    Auditoria.objects.create(responsable=usuario, mensaje=f'Se guardó la configuración del conductor {nuevo.pk}: {nuevo.nombre_apellidos}.')
    return nuevo


def buscar_conductor(nombre):
    if not nombre:
        return None
    alias = IdentidadConductor.objects.filter(nombre_origen=identidad(nombre)).first()
    if alias:
        return alias.conductor
    candidatos = [c for c in Conductor.objects.all() if identidad(c.nombre) == identidad(nombre)]
    return candidatos[0] if len(candidatos) == 1 else None


def problemas(lote, incluir_identidades=True):
    errores = list(lote.incidencias)
    claves = Counter()
    pendientes = set()
    incorporadas = set(Salida.objects.filter(clave_confirmada__isnull=False).exclude(importacion=lote).values_list('clave_confirmada', flat=True))
    for salida in lote.salidas.filter(anulado=False):
        claves[salida.clave] += 1
        if not salida.nombre_uno or not salida.nombre_dos:
            errores.append(f'Fila {salida.fila}: faltan nombres; complete el reporte original y vuelva a importarlo.')
        elif not salida.conductor_uno_id or not salida.conductor_dos_id:
            if not salida.conductor_uno_id:
                pendientes.add(identidad(salida.nombre_uno))
            if not salida.conductor_dos_id:
                pendientes.add(identidad(salida.nombre_dos))
        elif salida.conductor_uno_id == salida.conductor_dos_id:
            errores.append(f'Fila {salida.fila}: ambos puestos corresponden al mismo conductor.')
        if salida.clave in incorporadas:
            errores.append(f'Fila {salida.fila}: la salida ya está incorporada en otro reporte.')
    if any(n > 1 for n in claves.values()):
        errores.append('Hay salidas repetidas dentro del reporte. Corrija el archivo de origen y vuelva a importarlo.')
    if not claves:
        errores.append('El reporte no tiene salidas activas para incorporar.')
    if incluir_identidades and pendientes:
        errores.append(f'Falta registrar {len(pendientes)} conductores del reporte. Use «Registrar conductores del reporte».')
    return errores


@transaction.atomic
def registrar_conductores_reporte(pk, usuario):
    lote = Importacion.objects.select_for_update().get(pk=pk)
    if lote.estado != 'PENDIENTE':
        raise ValueError('Este reporte ya está validado; sus conductores no se pueden modificar.')
    salidas = list(lote.salidas.filter(anulado=False))
    grupos = defaultdict(set)
    asignados = defaultdict(set)
    for salida in salidas:
        for nombre, cid in ((salida.nombre_uno, salida.conductor_uno_id), (salida.nombre_dos, salida.conductor_dos_id)):
            if nombre:
                key = identidad(nombre)
                grupos[key].add(nombre)
                if cid:
                    asignados[key].add(cid)
    creados = reutilizados = 0
    for key, nombres in grupos.items():
        candidatos = {c.pk for c in Conductor.objects.all() if identidad(c.nombre) == key} | asignados[key]
        alias = IdentidadConductor.objects.filter(nombre_origen=key).first()
        if alias:
            candidatos.add(alias.conductor_id)
        if len(candidatos) > 1:
            raise ValueError(f'El nombre «{sorted(nombres)[0]}» coincide con varias fichas. Revise ese nombre individualmente antes de registrar el grupo.')
        if candidatos:
            conductor = Conductor.objects.get(pk=next(iter(candidatos)))
            reutilizados += 1
        else:
            conductor = Conductor.objects.create(nombre=sorted(nombres)[0])
            creados += 1
        alias, _ = IdentidadConductor.objects.get_or_create(nombre_origen=key, defaults={'conductor': conductor})
        if alias.conductor_id != conductor.pk:
            raise ValueError('Se encontró una identidad modificada durante el registro. Actualice la página.')
        for nombre in nombres:
            lote.salidas.filter(nombre_uno=nombre, conductor_uno__isnull=True).update(conductor_uno=conductor)
            lote.salidas.filter(nombre_dos=nombre, conductor_dos__isnull=True).update(conductor_dos=conductor)
    if creados or reutilizados:
        Auditoria.objects.create(responsable=usuario, importacion=lote,
            mensaje=f'Se registraron los conductores del reporte: {creados} fichas nuevas y {reutilizados} reconocidas. Las salidas permanecen pendientes de validación.')
    return creados, reutilizados


@transaction.atomic
def reconocer_registrados(pk, usuario):
    lote = Importacion.objects.select_for_update().get(pk=pk)
    if lote.estado != 'PENDIENTE':
        return 0
    cantidad = 0
    for salida in lote.salidas.filter(anulado=False):
        for campo, origen in [('conductor_uno', 'nombre_uno'), ('conductor_dos', 'nombre_dos')]:
            if getattr(salida, campo+'_id') is None:
                conductor = buscar_conductor(getattr(salida, origen))
                if conductor:
                    setattr(salida, campo, conductor)
                    salida.save(update_fields=[campo])
                    cantidad += 1
    if cantidad:
        Auditoria.objects.create(responsable=usuario, importacion=lote, mensaje=f'Se reconocieron {cantidad} asignaciones de conductores ya registrados.')
    return cantidad


@transaction.atomic
def confirmar(pk, usuario):
    lote = Importacion.objects.select_for_update().get(pk=pk)
    if lote.estado == 'VALIDADO':
        return lote
    errores = problemas(lote)
    if errores:
        raise ValueError('No se puede confirmar: ' + errores[0])
    for salida in lote.salidas.filter(anulado=False):
        salida.clave_confirmada = salida.clave
        salida.save(update_fields=['clave_confirmada'])
    lote.estado = 'VALIDADO'
    lote.validado_por = usuario
    lote.validado = timezone.now()
    lote.save(update_fields=['estado', 'validado_por', 'validado'])
    Auditoria.objects.create(responsable=usuario, importacion=lote, mensaje='Se validó el reporte y se incorporaron sus salidas al control de conductores.')
    return lote


@transaction.atomic
def registrar_situacion(conductor, inicio, fin, tipo, motivo, usuario):
    # Serializa altas del mismo conductor para evitar períodos superpuestos.
    Conductor.objects.select_for_update().get(pk=conductor.pk)
    if inicio > fin:
        raise ValueError('La fecha final debe ser igual o posterior a la inicial.')
    if SituacionConductor.objects.filter(conductor=conductor, activa=True, inicio__lte=fin, fin__gte=inicio).exists():
        raise ValueError('El conductor ya tiene una situación registrada en ese período.')
    situacion = SituacionConductor.objects.create(conductor=conductor, inicio=inicio, fin=fin, tipo=tipo, motivo=motivo, creado_por=usuario)
    Auditoria.objects.create(responsable=usuario, situacion=situacion, mensaje=f'Se registró {situacion.get_tipo_display().lower()} de {conductor.nombre}: {inicio} a {fin}. Motivo: {motivo}')
    return situacion


@transaction.atomic
def editar_situacion_dia(pk, conductor, fecha, tipo, usuario, fin=None):
    fin = fin or fecha
    Conductor.objects.select_for_update().get(pk=conductor.pk)
    original = SituacionConductor.objects.select_for_update().filter(pk=pk, conductor=conductor, activa=True, inicio__lte=fin, fin__gte=fecha).first()
    if original is None:
        raise ValueError('La situación cambió. Actualice el calendario antes de editar.')
    if original.tipo == tipo and original.inicio <= fecha <= fin <= original.fin:
        return original
    original.activa = False
    original.save(update_fields=['activa'])
    # Conserva las fechas del registro original que quedan fuera del rango editado.
    for inicio_copia, fin_copia in ((original.inicio, fecha-timedelta(days=1)), (fin+timedelta(days=1), original.fin)):
        if inicio_copia <= fin_copia:
            copia = SituacionConductor.objects.create(conductor=conductor, inicio=inicio_copia, fin=fin_copia, tipo=original.tipo, motivo=original.motivo, creado_por=usuario)
            Auditoria.objects.create(responsable=usuario, situacion=copia, mensaje=f'Se conservó el período {inicio_copia} a {fin_copia} al editar el registro {original.pk}.')
    nueva = registrar_situacion(conductor, fecha, fin, tipo, '', usuario)
    Auditoria.objects.create(responsable=usuario, situacion=original, mensaje=f'Se cambió el período {fecha} a {fin} de {original.get_tipo_display()} a {nueva.get_tipo_display()}. El resto del período se conservó.')
    return nueva


def calendario(inicio, fin, busqueda=''):
    dias = [inicio + timedelta(days=i) for i in range((fin-inicio).days+1)]
    conductores = list(Conductor.objects.select_related('trabajador'))
    if busqueda:
        tokens = normalizar(busqueda).split()
        conductores = [c for c in conductores if all(t in normalizar(c.nombre_apellidos) for t in tokens)]
    import unicodedata
    def orden(c):
        nombre = c.nombre_apellidos.replace('Ñ', 'N~')
        return (''.join(t for t in unicodedata.normalize('NFD', nombre) if not unicodedata.combining(t)), c.pk)
    conductores.sort(key=orden)
    salidas = Salida.objects.filter(importacion__estado='VALIDADO', fecha__range=(inicio, fin)).select_related('conductor_uno', 'conductor_dos')
    indice = defaultdict(list)
    for s in salidas:
        for cid in {s.conductor_uno_id, s.conductor_dos_id} - {None}:
            indice[(cid, s.fecha)].append(s)
    situaciones = defaultdict(dict)
    for s in SituacionConductor.objects.filter(activa=True, inicio__lte=fin, fin__gte=inicio):
        for d in dias:
            if s.inicio <= d <= s.fin:
                situaciones[s.conductor_id][d] = s
    filas = []
    asignados = {cid for cid, fecha in indice}
    for c in conductores:
        if c.pk not in asignados and not situaciones.get(c.pk):
            continue
        celdas, total, trabajados, pendientes, conflictos = [], 0, 0, 0, 0
        conteo = Counter()
        marcas = Counter()
        for d in dias:
            asignaciones = indice[(c.pk, d)]
            viajes = [s for s in asignaciones if s.cuenta_para_control]
            excluidas = [s for s in asignaciones if not s.cuenta_para_control]
            situacion = situaciones[c.pk].get(d)
            n = len(viajes)
            if n:
                marcas[n] += 1
            conflicto = bool(n and situacion)
            total += n
            trabajados += bool(n)
            conflictos += conflicto
            if situacion:
                conteo[situacion.tipo] += 1
            if n == 1:
                etiqueta, clase = viajes[0].hora.strftime('%H:%M'), 'servicio'
            elif n:
                etiqueta, clase = {2: 'X', 3: 'XX'}.get(n, str(n)), 'servicio'
            elif situacion:
                etiqueta, clase = {'DESCANSO': 'D', 'VACACIONES': 'V', 'PERMISO': 'P', 'LICENCIA': 'L', 'LICENCIA_CG': 'LC', 'LICENCIA_SG': 'LS', 'DESCUENTO': 'DS'}[situacion.tipo], ('licencia' if situacion.tipo.startswith('LICENCIA') else situacion.tipo.lower())
            elif excluidas:
                por_confirmar = any(s.pendiente_salida for s in excluidas)
                programadas = any(s.estado_operativo == 'PROGRAMADO' and not s.anulado for s in excluidas)
                etiqueta, clase = ('PR', 'pendiente') if programadas else (('SV', 'sin-ventas') if por_confirmar else ('C', 'cancelado'))
                pendientes += bool(por_confirmar)
            else:
                etiqueta, clase = '—', 'pendiente'
                pendientes += 1
            celdas.append(dict(fecha=d, viajes=viajes, excluidas=excluidas, sin_ventas=sum(s.pendiente_salida for s in excluidas), situacion=situacion, cantidad=n, etiqueta=etiqueta, clase='conflicto' if conflicto else clase, conflicto=conflicto))
        filas.append(dict(conductor=c, celdas=celdas, trayectos=total, vueltas=Decimal(total)/2, trabajados=trabajados,
            pago_vueltas=(Decimal(total)/2*Decimal('20.00')).quantize(Decimal('0.01')),
            horas=marcas[1], una_x=marcas[2], dos_x=marcas[3],
            descansos=conteo['DESCANSO'], vacaciones=conteo['VACACIONES'], permisos=sum(conteo[t] for t in ('PERMISO','LICENCIA','LICENCIA_CG','LICENCIA_SG')), pendientes=pendientes, conflictos=conflictos))
    return dias, filas


def resumen_periodo(filas, busqueda=''):
    """Incluye el catálogo completo, con ceros para quien no tiene actividad."""
    existentes = {f['conductor'].pk: f for f in filas}
    tokens = normalizar(busqueda).split()
    resultado = []
    campos = ('trayectos', 'trabajados', 'descansos', 'horas', 'una_x', 'dos_x', 'pendientes', 'conflictos', 'vacaciones', 'permisos')
    for conductor in Conductor.objects.select_related('trabajador'):
        if tokens and not all(t in normalizar(conductor.nombre_apellidos) for t in tokens):
            continue
        fila = existentes.get(conductor.pk)
        if fila is None:
            fila = dict(conductor=conductor, celdas=[], vueltas=Decimal('0'), pago_vueltas=Decimal('0.00'), **{campo: 0 for campo in campos})
        resultado.append(fila)
    import unicodedata
    def orden(f):
        nombre = f['conductor'].nombre_apellidos.replace('Ñ', 'N~')
        return (''.join(t for t in unicodedata.normalize('NFD', nombre) if not unicodedata.combining(t)), f['conductor'].pk)
    return sorted(resultado, key=orden)
