"""Lectura del manifiesto Excel y sincronización sin perder embarques verificados."""
from io import BytesIO
from django.db import transaction
from conductores.parser import normalizar
from .models import Pasajero, Operacion, Auditoria
from .views import exigir, aviso_operacion

ALIAS={
 'referencia':('REFERENCIA','BOLETO','NUMERO BOLETO','NRO BOLETO','TICKET'),
 'nombre':('NOMBRE','PASAJERO','NOMBRE COMPLETO','APELLIDOS Y NOMBRES','NOMBRES Y APELLIDOS'),
 'documento':('DOCUMENTO','DNI','NUMERO DOCUMENTO','NRO DOCUMENTO'),
 'piso':('PISO','NIVEL'),'asiento':('ASIENTO','NUMERO ASIENTO','NRO ASIENTO'),
 'origen':('ORIGEN','CIUDAD ORIGEN'),'destino':('DESTINO','CIUDAD DESTINO'),
 'punto':('PUNTO','PUNTO EMBARQUE','PUNTO DE EMBARQUE','EMBARQUE','SUBE'),
 'punto_desembarque':('PUNTO DESEMBARQUE','PUNTO DE DESEMBARQUE','DESEMBARQUE','BAJA'),
}


def leer_pasajeros(archivo):
    exigir(archivo.size<=4_000_000,'El Excel debe pesar como máximo 4 MB.')
    nombre=archivo.name.lower()
    if nombre.endswith('.xlsx'):
        from openpyxl import load_workbook
        try:wb=load_workbook(BytesIO(archivo.read()),read_only=True,data_only=True)
        except Exception as e:raise ValueError('No se pudo leer el Excel. Verifique que sea un archivo .xlsx válido.') from e
        try:
            exigir(len(wb.sheetnames)==1,'El manifiesto debe tener una sola hoja para identificar el viaje sin ambigüedad.')
            filas=[]
            for row in wb.active.iter_rows(values_only=True):
                filas.append(list(row))
                exigir(len(filas)<=350,'El manifiesto supera el máximo de filas permitido.')
        finally:wb.close()
    elif nombre.endswith('.xls'):
        from conductores.parser import abrir_xls
        try:wb=abrir_xls(archivo.read())
        except Exception as e:raise ValueError('No se pudo leer el Excel. Verifique que sea un archivo .xls válido.') from e
        try:
            exigir(wb.nsheets==1,'El manifiesto debe tener una sola hoja.')
            sheet=wb.sheet_by_index(0);exigir(sheet.nrows<=350,'El manifiesto supera el máximo de filas permitido.')
            filas=[sheet.row_values(n) for n in range(sheet.nrows)]
        finally:wb.release_resources()
    else:raise ValueError('Seleccione un archivo .xlsx o .xls.')
    indices={};inicio=None
    for i,row in enumerate(filas[:20]):
        indices={campo:next((n for n,v in enumerate(row) if normalizar(v) in nombres),None) for campo,nombres in ALIAS.items()}
        if all(indices[k] is not None for k in ('nombre','documento','asiento')):inicio=i+1;break
    exigir(inicio is not None,'Faltan columnas: Pasajero, Documento y Asiento.')
    def texto(v):return str(int(v)) if isinstance(v,float) and v.is_integer() else str(v or '').strip()
    resultado=[]
    for i,row in enumerate(filas[inicio:],inicio+1):
        if not any(v is not None and str(v).strip() for v in row):continue
        f={k:texto(row[n]) if n is not None and n<len(row) else '' for k,n in indices.items()}
        exigir(f['nombre'] and f['documento'] and f['asiento'],f'Fila {i}: complete pasajero, documento y asiento.')
        f['asiento']=int(f['asiento']);f['piso']=int(f['piso']) if f['piso'] else None
        resultado.append(f)
    exigir(resultado and len(resultado)<=300,'El manifiesto debe contener entre 1 y 300 pasajeros.')
    return resultado


def asientos_distribucion(config):
    inferiores=int(config.get('piso1',0));superiores=int(config.get('piso2',0))
    return [(piso,n+(inferiores if piso==2 and config.get('numeracion')=='continua' else 0)) for piso,cantidad in ((1,inferiores),(2,superiores)) for n in range(1,cantidad+1)]


@transaction.atomic
def importar_pasajeros_excel(operacion_id,archivo,actor):
    filas=leer_pasajeros(archivo)
    op=Operacion.objects.select_for_update().select_related('salida').get(pk=operacion_id)
    exigir(op.estado=='PROGRAMADO' and not op.salida.anulado and op.salida.estado_operativo!='CANCELADO','Solo se carga el manifiesto antes de iniciar el viaje.')
    exigir(op.distribucion_asientos.get('confirmada'),'Confirme la distribución del bus antes de cargar pasajeros.')
    permitidos=asientos_distribucion(op.distribucion_asientos)
    refs=set();ocupados=set();nuevos=actualizados=0
    for f in filas:
        if f['piso'] is None:
            posibilidades=[p for p,n in permitidos if n==f['asiento']]
            exigir(len(posibilidades)==1,'El número de asiento existe en ambos pisos. Incluya la columna Piso.');f['piso']=posibilidades[0]
        plaza=(f['piso'],f['asiento']);exigir(plaza in permitidos and plaza not in ocupados,'Asiento repetido o fuera de la distribución confirmada.');ocupados.add(plaza)
        ref=f['referencia'] or f"DOC-{f['documento']}"
        exigir(ref not in refs and len(ref)<=100,'Hay boletos o documentos repetidos.');refs.add(ref)
        actual=op.pasajeros.filter(referencia=ref).first()
        datos={k:v for k,v in f.items() if k!='referencia'}
        datos['origen']=datos['origen'] or op.salida.origen;datos['destino']=datos['destino'] or op.salida.destino
        datos['punto']=datos['punto'] or datos['origen'];datos['punto_desembarque']=datos['punto_desembarque'] or datos['destino']
        exigir(not op.pasajeros.exclude(pk=actual.pk if actual else None).filter(piso=f['piso'],asiento=f['asiento']).exists(),'El asiento ya está asignado a otro pasajero. Se conservó la lista anterior.')
        if actual:
            cambios={k:v for k,v in datos.items() if getattr(actual,k)!=v}
            exigir(not cambios or actual.estado=='PENDIENTE','Hay un pasajero ya verificado con datos distintos. Se conserva su embarque.')
            for k,v in cambios.items():setattr(actual,k,v)
            if cambios:actual.full_clean();actual.save();actualizados+=1
        else:
            pasajero=Pasajero(operacion=op,referencia=ref,**datos);pasajero.full_clean();pasajero.save();nuevos+=1
    aviso_operacion(op,'Manifiesto de pasajeros actualizado. Revise embarques y desembarques.')
    Auditoria.objects.create(actor=actor,accion='excel_pasajeros',detalle={'viaje':op.pk,'archivo':archivo.name,'nuevos':nuevos,'actualizados':actualizados})
    return nuevos,actualizados
