"""Compara reportes con las salidas compartidas por contabilidad y boletería."""
from conductores.models import Salida
from conductores.parser import normalizar


def comparar_filas(filas):
    existentes = list(Salida.objects.filter(fecha__range=(min(f['fecha'] for f in filas), max(f['fecha'] for f in filas))).select_related('importacion')) if filas else []
    resultado = []
    vistas = set()
    for f in filas:
        candidatos = [s for s in existentes if s.clave == f['clave']]
        if not candidatos:
            candidatos = [s for s in existentes if s.fecha == f['fecha'] and normalizar(s.origen) == normalizar(f['origen']) and normalizar(s.destino) == normalizar(f['destino']) and (
                (f.get('correlativo') and s.correlativo == f['correlativo']) or
                (normalizar(s.nombre_uno) == normalizar(f['nombre_uno']) and normalizar(s.nombre_dos) == normalizar(f['nombre_dos'])) or
                s.hora == f['hora']
            )]
        diferencias = []
        previa = candidatos[0] if len(candidatos) == 1 else None
        if f['clave'] in vistas:
            estado = 'CONFLICTO';diferencias.append({'campo':'Archivo','antes':'','despues':'Salida repetida dentro del Excel'})
        elif len(candidatos) > 1:
            estado = 'CONFLICTO';diferencias.append({'campo':'Coincidencias','antes':str(len(candidatos)),'despues':'Revisar registros existentes'})
        elif previa:
            for campo, etiqueta in [('fecha','Fecha'),('hora','Hora'),('bus','Bus'),('origen','Origen'),('destino','Destino'),('nombre_uno','Conductor 1'),('nombre_dos','Conductor 2'),('anulado','Anulación')]:
                antes, despues = getattr(previa,campo), f[campo]
                iguales = normalizar(antes) == normalizar(despues) if isinstance(antes,str) else antes == despues
                if not iguales:diferencias.append({'campo':etiqueta,'antes':str(antes),'despues':str(despues)})
            comercial = f.get('original',{}).get('comercial',{})
            for campo, etiqueta in [('capacidad','Capacidad'),('vendidos_primer_piso','Ventas piso 1'),('vendidos_segundo_piso','Ventas piso 2')]:
                antes, despues = previa.comercial.get(campo), comercial.get(campo)
                if antes != despues:diferencias.append({'campo':etiqueta,'antes':str(antes),'despues':str(despues)})
            estado = 'CAMBIO' if diferencias else 'EXISTENTE' if previa.importacion.estado == 'VALIDADO' else 'PENDIENTE'
        else:estado = 'NUEVO'
        vistas.add(f['clave'])
        resultado.append({'fila':f['fila'],'fecha':str(f['fecha']),'hora':str(f['hora']),'recorrido':f"{f['origen']} → {f['destino']}",'estado':estado,'salida_id':previa.pk if previa else None,'diferencias':diferencias})
    return resultado
