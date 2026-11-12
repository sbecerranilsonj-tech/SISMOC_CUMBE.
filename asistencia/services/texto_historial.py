"""Descripciones legibles sin modificar la evidencia original del historial."""
import ast
import re
from datetime import date

DIAS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')

def descripcion_historial(registro):
    texto = registro.detalle
    if registro.accion in {'Descanso programado', 'Días de trabajo programados'}:
        fechas = re.findall(r'datetime.date\((\d+), (\d+), (\d+)\)', texto)
        dias = re.search(r"'dias': \[([^]]*)\]", texto)
        if len(fechas) >= 2 and dias:
            desde, hasta = [date(*map(int, f)).strftime('%d/%m/%Y') for f in fechas[:2]]
            nombres = ', '.join(DIAS[int(d.strip())] for d in dias[1].split(',') if d.strip().isdigit() and 0 <= int(d.strip()) <= 6)
            if registro.accion == 'Días de trabajo programados':
                return f'Trabaja los {nombres}, del {desde} al {hasta}. Los demás días quedan sin trabajo programado.'
            return f'Descanso los {nombres}, del {desde} al {hasta}.' if nombres else f'Sin descanso semanal previsto del {desde} al {hasta}.'
    if registro.accion == 'Horario programado':
        coincidencia = re.search(r'fecha (\d{4}-\d{2}-\d{2}); anterior: (.*?); nuevo: (.*?);', texto)
        if coincidencia:
            fecha, antes, nuevo = coincidencia.groups()
            return f'El {date.fromisoformat(fecha):%d/%m/%Y} se asignó el horario {nuevo}. Horario anterior: {antes.lower() if antes == "Sin programación" else antes}.'
    if registro.accion == 'Configuración de extras':
        estados = re.search(r'25%=(True|False); 35%=(True|False)', texto)
        if estados:
            return f'Horas extras al 25 %: {"activadas" if estados[1] == "True" else "desactivadas"}. Horas extras al 35 %: {"activadas" if estados[2] == "True" else "desactivadas"}.'
    if registro.accion == 'Configuración de nocturnas':
        estado = re.search(r'→ (True|False)', texto)
        if estado:
            return 'Se activó el cálculo de horas nocturnas de 22:00 a 06:00.' if estado[1] == 'True' else 'Se desactivó el cálculo de horas nocturnas.'
    if registro.accion == 'Modalidad de horas trabajadas':
        return 'Se activó la modalidad de solo horas trabajadas.' if 'solo horas=True' in texto else 'Se desactivó la modalidad de solo horas trabajadas.'
    if registro.accion == 'Ficha de personal':
        cambio = re.search(r'antes=(.*); ahora=(.*)\.$', texto)
        if cambio:
            try:
                antes, despues = map(ast.literal_eval, cambio.groups())
                etiquetas = {'nombres': 'Nombres', 'apellido_paterno': 'Primer apellido', 'apellido_materno': 'Segundo apellido', 'dni': 'DNI', 'area': 'Área', 'sede': 'Sede'}
                cambios = [f'{etiquetas.get(k, k)}: {antes.get(k) or "sin registrar"} → {v or "sin registrar"}.' for k, v in despues.items() if antes.get(k) != v]
                return ' '.join(cambios) or 'Se guardaron los datos sin cambios.'
            except (ValueError, SyntaxError):
                pass
    texto = re.sub(r'^Trabajador #\d+[^:]*: *', '', texto)
    texto = re.sub(r'\b(\d{4})-(\d{2})-(\d{2})\b', r'\3/\2/\1', texto)
    texto = re.sub(r'periodo #\d+; *', '', texto)
    return texto
