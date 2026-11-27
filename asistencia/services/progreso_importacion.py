"""Transmitir el avance de una importación atómica sin guardar cargas parciales."""
import json
import logging
from io import BytesIO
from queue import Queue, Empty
from threading import Thread
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import close_old_connections, connections, transaction
from django.http import StreamingHttpResponse


def respuesta_importacion(archivo, actor_id):
    # La petición puede cerrarse al perder la conexión: el lector no debe depender
    # del archivo temporal administrado por esa petición.
    contenido, nombre = archivo.read(), archivo.name
    eventos = Queue()

    def importar():
        close_old_connections()
        try:
            from core.models import Usuario
            from asistencia.services.zkteco_parser import ZKTecoExcelParser
            with transaction.atomic():
                actor = Usuario.objects.get(pk=actor_id)
                from asistencia.services.revision import puede_gestionar
                if not puede_gestionar(actor):
                    raise ValidationError('Ya no tiene permiso para importar asistencia.')
                resultado = ZKTecoExcelParser(BytesIO(contenido), nombre, actor, progreso=eventos.put).procesar()
            # Emitir éxito solo después del commit de la transacción exterior.
            eventos.put({'tipo':'completado','porcentaje':100,'resultado':resultado})
        except ValidationError as exc:
            eventos.put({'tipo':'error','detail':' '.join(exc.messages)})
        except (ValueError, ImportError):
            eventos.put({'tipo':'error','detail':'No se pudo leer el Excel. Revise su formato y que no esté protegido por contraseña.'})
        except Exception:
            logging.getLogger(__name__).exception('Fallo en importación con progreso')
            eventos.put({'tipo':'error','detail':'La importación se canceló sin guardar cambios. Revise el archivo o consulte al administrador.'})
        finally:
            connections.close_all()

    def transmitir():
        Thread(target=importar, daemon=True, name='importacion-asistencia').start()
        while True:
            try:
                evento = eventos.get(timeout=10)
            except Empty:
                yield json.dumps({'tipo':'espera'}) + '\n'
                continue
            yield json.dumps(evento, cls=DjangoJSONEncoder) + '\n'
            if evento['tipo'] in {'completado','error'}:
                break

    respuesta = StreamingHttpResponse(transmitir(), content_type='application/x-ndjson; charset=utf-8')
    respuesta['Cache-Control'] = 'no-cache, no-store'
    respuesta['X-Accel-Buffering'] = 'no'
    return respuesta
