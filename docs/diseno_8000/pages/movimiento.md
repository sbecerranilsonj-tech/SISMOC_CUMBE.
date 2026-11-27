# Movimiento del escritorio

Referencia observada: video Glassy Dashboard V5, duracion 5.69 segundos. Se adapta el movimiento, sin copiar sus recursos o transformar la identidad visual.

- Entrada escalonada de paneles y tarjetas visibles: opacity, translateY(18px), blur(3px), 460ms; desfase 65ms, limite 325ms.
- Ventanas: translateY(14px), scale(.98), opacity; 320ms.
- Tarjetas: elevacion de 4px al hover, 260ms.
- Login: entrada suave 520ms.
- Mantener las cifras y filas de tabla estaticas, sin contadores artificiales.
- Animar al entrar en una vista; cancelar al salir y cuando el usuario activa movimiento reducido.
- No retrasar formularios ni botones para esperar una animacion. Sin animaciones infinitas ni paquetes externos.
- Implementacion: frontend/static/movimiento.js y frontend/assets/pro-max.css.
- Esta excepcion ajusta los tiempos generales de MASTER; colores y densidad se conservan.
