"""Recupera solo el flujo Workbook de un contenedor OLE; no interpreta celdas."""
import struct


def flujo_workbook(contenido):
    if len(contenido) < 512 or contenido[:8] != bytes.fromhex('D0CF11E0A1B11AE1'):
        raise ValueError('El archivo no tiene una cabecera XLS válida.')
    shift = struct.unpack_from('<H', contenido, 30)[0]
    if shift not in (9, 12):
        raise ValueError('El tamaño de sector XLS no es compatible.')
    sector_size = 1 << shift
    limite = len(contenido) // sector_size - 1

    def sector(numero):
        if not 0 <= numero < limite:
            raise ValueError('El XLS contiene un sector fuera del archivo.')
        return contenido[(numero+1)*sector_size:(numero+2)*sector_size]

    # Recuperación limitada a los archivos pequeños del reporte exportado.
    # Los contenedores con FAT extendida se dejan al lector principal.
    if struct.unpack_from('<I', contenido, 72)[0]:
        raise ValueError('El contenedor XLS requiere una recuperación no compatible.')
    fat = []
    cantidad_fat = struct.unpack_from('<I', contenido, 44)[0]
    sectores_fat = [n for n in struct.unpack_from('<109I', contenido, 76) if n < 0xfffffffa]
    if len(sectores_fat) < cantidad_fat:
        raise ValueError('La tabla de sectores XLS está incompleta.')
    for n in sectores_fat[:cantidad_fat]:
        fat.extend(struct.unpack('<'+'I'*(sector_size//4), sector(n)))

    def cadena(inicio):
        partes, visitados = [], set()
        while inicio < 0xfffffffa:
            if inicio in visitados or inicio >= len(fat):
                raise ValueError('El XLS contiene una cadena de sectores inválida.')
            visitados.add(inicio)
            partes.append(sector(inicio))
            inicio = fat[inicio]
        return b''.join(partes)

    directorio = cadena(struct.unpack_from('<I', contenido, 48)[0])
    for offset in range(0, len(directorio)-127, 128):
        entrada = directorio[offset:offset+128]
        longitud = struct.unpack_from('<H', entrada, 64)[0]
        if not 2 <= longitud <= 64:
            continue
        nombre = entrada[:longitud-2].decode('utf-16le', errors='replace')
        if nombre in ('Workbook', 'Book') and entrada[66] == 2:
            longitud_flujo = struct.unpack_from('<Q', entrada, 120)[0]
            if longitud_flujo < 4096:
                raise ValueError('El flujo XLS pequeño no admite esta recuperación.')
            flujo = cadena(struct.unpack_from('<I', entrada, 116)[0])
            if longitud_flujo > len(flujo):
                raise ValueError('El flujo del libro XLS está truncado.')
            return flujo[:longitud_flujo]
    raise ValueError('No se encontró el libro dentro del contenedor XLS.')
