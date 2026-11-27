# Agente local del huellero (ZKTeco MB360)

## Por qué

La página está en la nube y el huellero tiene una IP privada (`192.168.10.202`, puerto `4370`).
Un navegador o el servidor en la nube **no pueden** abrir esa dirección. El agente corre en la PC
de la sede donde ya funciona el software ZKteco: lee el equipo por TCP/IP y envía las marcas a la
nube por HTTPS. La nube solo recibe datos.

## Datos del equipo instalado

| Dato | Valor |
|---|---|
| Modelo | ZKTeco MB360 |
| IP | `192.168.10.202` |
| Puerto | `4370` (TCP/IP) |
| Gateway | `192.168.10.1` |
| Número de equipo | `1` |
| Clave de comunicación | `0` |
| Serie | `AEWD195060148` |

## Instalación (en la PC de la sede)

1. Instalar Python 3.10 o superior.
2. En esta carpeta, ejecutar:

   ```bash
   pip install -r requirements.txt
   ```

3. Copiar `config.example.json` como `config.json`.
4. Solicitar a administración el valor configurado en `HUELLERO_AGENT_TOKEN` (no se muestra en la web).
5. Pegar ese token en `config.json` (`"token"`). Ajustar `api_url` a la URL del sistema (por ejemplo
   `http://192.168.18.75:8000` o la URL pública en la nube).
6. Asignar un `agente_id` único por sede (por ejemplo `CHICLAYO`, `JAEN`) y su `sede`. Ese ID debe
   coincidir con el configurado en el servidor (`HUELLERO_AGENTES`).
7. Ejecutar:

   ```bash
   python agente.py
   ```

Dejar la ventana abierta. Para que arranque con Windows, crear un acceso directo a `python agente.py`
en la carpeta `shell:startup` del usuario.

## Qué hace el agente

- Cada `intervalo` segundos (por defecto 60) consulta al servidor si hay una orden **Probar conexión**.
- Lee las marcaciones del MB360 y envía solo las nuevas (controla el último UID en `ultimo_envio.json`).
- Si detecta marcas duplicadas, el servidor las descarta por la huella `serie:UID`.
- Reporta estado, modelo, serie, sede y total de registros del equipo.
- Envía el **nombre** de cada usuario leyendo la lista de usuarios del MB360. La nube identifica a
  la persona por nombre (los IDs se repiten entre sedes). Si el nombre no coincide de forma única,
  la marca queda como «Por identificar» en vez de atribuirse a alguien equivocado.
- Cada agente atiende solo las pruebas dirigidas a su `agente_id`.
- Si la nube no responde, conserva el último UID y reintenta en el siguiente ciclo.

## En la web

El botón **Configurar conexión** muestra IP, puerto, número de equipo, clave y ventanas
de refrigerio. El token no se muestra: se entrega fuera de banda desde `HUELLERO_AGENT_TOKEN`. El botón **Probar conexión** envía la orden al agente y muestra la respuesta cuando
el agente la reporta.

Ventanas del aviso interno: **07:15–08:00** y **18:00–18:45**. Las marcas fuera de esas ventanas se
guardan con la observación «Fuera de ventana de refrigerio»; **no se descuentan automáticamente**.
El descuento lo decide Contabilidad al revisar la jornada.

## Solución de problemas

- **«Sin reporte del agente»**: el agente no está ejecutándose o no alcanza `api_url`.
- **Token rechazado (403)**: el servidor no tiene definido `HUELLERO_AGENT_TOKEN`, o el token copiado
  no coincide. Configurar la variable de entorno en el servidor y reiniciarlo.
- **«No se pudo conectar al equipo»**: revisar IP, puerto y que la PC esté en la red `192.168.10.x`.
- **Primer ciclo lento**: el equipo tiene más de 50 000 registros; la primera lectura puede tardar.
  Los ciclos siguientes soloenvían las marcas nuevas.

## Seguridad

El token es compartido y debe mantenerse privado. No pegarlo en tickets, capturas ni repositorios.
El agente solo hace conexiones salientes a la API; no abre puertos al público.
