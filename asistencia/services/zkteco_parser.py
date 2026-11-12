"""Importación de eventos originales ZKTeco por sede y código de trabajador."""
from collections import Counter
from datetime import datetime, date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import re
import unicodedata

import pandas as pd
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import Usuario
from asistencia.models import (
    CargaArchivoAsistencia, IdentidadBiometrica, FilaImportacionBiometrica,
    MarcacionBiometrica, ResumenAsistenciaDiaria,
)


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "").strip())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in texto if not unicodedata.combining(c)).lower())


def texto(valor):
    if pd.isna(valor):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def asegurar_jornada(usuario, fecha):
    """Solo crea la jornada pendiente; no inventa eventos ni horas a partir de su orden."""
    from asistencia.services.horarios import turno_programado
    qs = MarcacionBiometrica.objects.filter(usuario=usuario, fecha_hora__date=fecha, es_valida=True).order_by("fecha_hora")
    primera, ultima = qs.first(), qs.last()
    if not primera:
        return None, False
    return ResumenAsistenciaDiaria.objects.get_or_create(
        usuario=usuario, fecha=fecha,
        defaults={
            "primera_entrada": timezone.localtime(primera.fecha_hora).time(),
            "ultima_salida": timezone.localtime(ultima.fecha_hora).time() if ultima.pk != primera.pk else None,
            "turno_aplicado": turno_programado(usuario, fecha),
            "observaciones": "Marcaciones importadas. Límites de consulta tomados de primera y última marca; entrada, salida y tiempos pendientes de revisión.",
        },
    )


class ZKTecoExcelParser:
    def __init__(self, archivo_path_o_bytes, nombre_archivo, subido_por=None, *, sede=None, progreso=None):
        self.archivo = archivo_path_o_bytes
        self.nombre_archivo = nombre_archivo
        self.subido_por = subido_por
        self.sede = (sede or '').strip().upper()
        self.progreso = progreso

    def notificar(self, etapa, porcentaje, actual=0, total=0):
        if self.progreso:
            self.progreso({'tipo':'progreso','etapa':etapa,'porcentaje':porcentaje,'actual':actual,'total':total})

    def sede_de_hoja(self, hoja):
        """Una hoja genérica no es una sede; conservar el nombre original como procedencia."""
        if not re.fullmatch(r'(sheet|hoja|feuille)\d*', normalizar(hoja)):
            return hoja.strip().upper()
        if self.sede:
            if len(self.sede) > 100:
                raise ValidationError('El nombre de la sede supera 100 caracteres.')
            return self.sede
        tokens = {normalizar(t) for t in re.findall(r'[^\W_]+', Path(self.nombre_archivo).stem)}
        sedes = set()
        if tokens & {'cix', 'chiclayo'}:
            sedes.add('CHICLAYO')
        if 'cajamarca' in tokens:
            sedes.add('CAJAMARCA')
        if 'jaen' in tokens:
            sedes.add('JAEN')
        if {'paul', 'harris'} <= tokens:
            sedes.add('PAUL HARRIS')
        if len(sedes) == 1:
            return sedes.pop()
        raise ValidationError(f'La hoja «{hoja}» no identifica una sede. Indique una sede única en el nombre del archivo (por ejemplo, asistencia octubre CIX.xls) o especifique la sede al importar.')

    def leer(self):
        """Validar todo el archivo antes de realizar escrituras."""
        registros, ignoradas, errores = [], [], []
        if hasattr(self.archivo, "seek"):
            self.archivo.seek(0)
        with pd.ExcelFile(self.archivo) as libro:
            hojas = list(libro.sheet_names)
            for hoja in hojas:
                df = pd.read_excel(libro, sheet_name=hoja, dtype=object)
                columnas = {normalizar(c): c for c in df.columns}
                def buscar(*alias):
                    return next((columnas[a] for a in alias if a in columnas), None)
                codigo = buscar("no", "dni", "acno", "userid", "id", "enrolno", "enrollno")
                fecha = buscar("fechahora", "datetime", "timestamp", "time", "fecha")
                nombre = buscar("nombre", "name", "empleado", "trabajador")
                equipo = buscar("idequipo", "equipo", "deviceid")
                estado = buscar("estado", "state", "tipo", "evento")
                verificacion = buscar("codverificacion", "verificacion", "verify")
                if codigo is None or fecha is None:
                    ignoradas.append(hoja.strip())
                    continue
                sede = self.sede_de_hoja(hoja)
                for posicion, (_, fila) in enumerate(df.iterrows(), 2):
                    code, valor_fecha = texto(fila[codigo]), fila[fecha]
                    if not code and pd.isna(valor_fecha):
                        continue
                    try:
                        if not code or len(code) > 60:
                            raise ValueError("Falta el código del trabajador o supera 60 caracteres")
                        if isinstance(valor_fecha, (int, float)) or pd.isna(valor_fecha):
                            raise ValueError("La fecha debe ser una fecha y hora, no un número o una celda vacía")
                        if isinstance(valor_fecha, datetime):
                            fh = valor_fecha
                        elif isinstance(valor_fecha, str) and re.search(r"\d{4}", valor_fecha):
                            fh = pd.to_datetime(valor_fecha, dayfirst=not bool(re.match(r"^\d{4}-", valor_fecha))).to_pydatetime()
                        else:
                            raise ValueError("La fecha no contiene un año y una hora válidos")
                        if not (2000 <= fh.year <= timezone.localdate().year + 1):
                            raise ValueError("El año de la marcación está fuera del intervalo admitido")
                        if timezone.is_naive(fh):
                            fh = timezone.make_aware(fh, timezone.get_default_timezone())
                        else:
                            fh = timezone.localtime(fh)
                        registros.append({
                            "hoja": hoja, "fila": posicion, "sede": sede,
                            "codigo": code, "fecha_hora": fh,
                            "nombre": texto(fila[nombre]) if nombre else "",
                            "equipo": texto(fila[equipo]) if equipo else "",
                            "estado": texto(fila[estado]) if estado else "",
                            "verificacion": texto(fila[verificacion]) if verificacion else "",
                            "original": {str(k): (v.isoformat() if isinstance(v, (datetime, date)) else texto(v)) for k, v in fila.items()},
                        })
                    except (ValueError, TypeError, OverflowError) as exc:
                        errores.append(f"{hoja.strip()}, fila {posicion}: {exc}.")
        if errores:
            raise ValidationError(errores[:15] + ([f"Hay {len(errores)} filas con errores. No se importó ninguna."] if len(errores) > 15 else []))
        if not registros:
            raise ValidationError("No hay hojas con columnas de código y Fecha/Hora. Seleccione la exportación original por sedes.")
        return registros, hojas, ignoradas

    @transaction.atomic
    def procesar(self):
        self.notificar('validando', 0)
        registros, hojas, ignoradas = self.leer()
        self.notificar('registrando', 5, total=len(registros))
        periodo = Counter(r["fecha_hora"].strftime("%Y-%m") for r in registros).most_common(1)[0][0]
        carga = CargaArchivoAsistencia.objects.create(
            nombre_archivo_original=self.nombre_archivo, subido_por=self.subido_por,
            mes_periodo=periodo, estado="PROCESANDO",
        )
        identidades, nuevas, repetidas, jornadas = {}, 0, 0, set()
        eventos = {
            "entrada": "ENTRADA", "checkin": "ENTRADA", "salida": "SALIDA", "checkout": "SALIDA",
            "salidarefrigerio": "SALIDA_REFRIGERIO", "retornorefrigerio": "RETORNO_REFRIGERIO",
        }
        salto = max(1, len(registros) // 100)
        for numero, r in enumerate(registros, 1):
            clave = (r["sede"], r["equipo"], r["codigo"])
            if clave not in identidades:
                usuario = None
                # El DNI solo se usa si coincide exactamente con un usuario ya registrado.
                if re.fullmatch(r"\d{8}", r["codigo"]):
                    usuario = Usuario.objects.filter(dni=r["codigo"]).first()
                identidad, _ = IdentidadBiometrica.objects.get_or_create(
                    sede=r["sede"], equipo=r["equipo"], codigo=r["codigo"],
                    defaults={"nombre": r["nombre"], "usuario": usuario},
                )
                if not identidad.usuario_id and usuario:
                    identidad.usuario = usuario
                    identidad.save(update_fields=["usuario"])
                identidades[clave] = identidad
            identidad = identidades[clave]
            # Los códigos locales cortos se delimitan por sede y equipo.
            # Para códigos de ocho dígitos, una misma lectura copiada en otra hoja
            # conserva un evento y todas las filas de procedencia.
            alcance = "GLOBAL8" if re.fullmatch(r"\d{8}", r["codigo"]) else r["sede"]
            huella = sha256("|".join([alcance, r["equipo"], r["codigo"], r["fecha_hora"].isoformat(), r["estado"], r["verificacion"]]).encode()).hexdigest()
            marca, creada = MarcacionBiometrica.objects.get_or_create(
                huella_importacion=huella,
                defaults={
                    "usuario": identidad.usuario, "identidad_biometrica": identidad,
                    "dni": identidad.usuario.dni if identidad.usuario_id else "",
                    "nombre_empleado": identidad.nombre or r["nombre"],
                    "zkteco_user_id": int(r["codigo"]) if r["codigo"].isdigit() and len(r["codigo"]) <= 9 else None,
                    "fecha_hora": r["fecha_hora"], "tipo_evento": eventos.get(normalizar(r["estado"]), "SIN_CLASIFICAR"),
                    "origen": "EXCEL_ZKTECO", "carga_origen": carga,
                    "estado_reportado": r["estado"][:60], "verificacion_reportada": r["verificacion"][:40],
                },
            )
            if not creada and marca.usuario_id and identidad.usuario_id and marca.usuario_id != identidad.usuario_id:
                raise ValidationError(f"El código {r['codigo']} tiene asociaciones contradictorias. Revise las identidades antes de importar.")
            FilaImportacionBiometrica.objects.create(
                carga=carga, marcacion=marca, identidad=identidad, hoja=r["hoja"], fila=r["fila"], repetida=not creada, datos_originales=r["original"],
            )
            nuevas += int(creada)
            repetidas += int(not creada)
            if creada and identidad.usuario_id:
                jornadas.add((identidad.usuario_id, timezone.localtime(r["fecha_hora"]).date()))
            if numero % salto == 0 or numero == len(registros):
                self.notificar('registrando', 5 + (90 * numero // len(registros)), numero, len(registros))
        self.notificar('guardando', 97, len(registros), len(registros))
        generadas = 0
        for uid, fecha in jornadas:
            _, creada = asegurar_jornada(Usuario.objects.get(pk=uid), fecha)
            generadas += int(creada)
        pendientes = sum(not i.trabajador_id for i in identidades.values())
        alertas = ["Las horas no se calculan durante la importación. Revise la clasificación de las marcaciones."]
        if pendientes:
            alertas.append(f"{pendientes} códigos biométricos guardados pendientes de vincular a una ficha de trabajador.")
        if ignoradas:
            alertas.append("Hojas sin formato de exportación omitidas: " + ", ".join(ignoradas))
        carga.total_filas_procesadas = len(registros)
        carga.total_empleados_identificados = len({i.usuario_id for i in identidades.values() if i.usuario_id})
        carga.estado = "COMPLETADO"
        carga.detalle_log = f"Nuevas: {nuevas}; repetidas: {repetidas}; códigos: {len(identidades)}.\n" + "\n".join(alertas)
        carga.save()
        self.notificar('guardando', 99, len(registros), len(registros))
        return {
            "archivo": self.nombre_archivo, "carga_id": carga.pk, "hojas_encontradas": len(hojas),
            "filas_procesadas": len(registros), "empleados_identificados": carga.total_empleados_identificados,
            "codigos_biometricos": len(identidades), "identidades_pendientes": pendientes,
            "marcaciones_nuevas": nuevas, "marcaciones_repetidas": repetidas,
            "total_he_25": Decimal(0), "total_he_35": Decimal(0), "total_vueltas_choferes": 0,
            "resumenes_generados": generadas, "alertas": alertas, "exito": True,
        }
