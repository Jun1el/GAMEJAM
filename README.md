# La vida da vueltas en Eduroam

Juego multijugador 2D para un máximo de cuatro personas, ambientado en la
Universidad Nacional de Ingeniería. Los jugadores recorren el campus para
reparar los routers Eduroam en el momento correcto, mientras el servidor
mantiene las posiciones, colisiones y reglas de la partida.

## Objetivo

Completa en equipo una campaña de cuatro misiones para estabilizar Eduroam en
todo el campus. Las reparaciones individuales muestran la contribución de cada
jugador, pero la victoria es compartida.

Los routers representan estos lugares:

- FIGMM, FIEE, Biblioteca, FIEECS, FIC, FIA y FIQT.
- CTIC, FIM, FIIS, FC, Estadio UNI y FAUA.
- FIP, Entrada y Salida.

El **Comedor** y el **Centro Médico** son instalaciones especiales: no cuentan
como routers, no aparecen en la Ruta Crítica y no afectan el límite de cinco
conexiones activas.

## Controles

| Acción | Tecla |
| --- | --- |
| Moverse | `WASD` o flechas |
| Reparar / recoger pollo | `E` |
| Comer pollo almacenado | `Q` |
| Salir | `Esc` o cerrar la ventana |

Al abrir el cliente aparece una pantalla de inicio. Escribe o modifica el
nombre del jugador y pulsa **Conectar a Eduroam** para entrar a la partida.

## Cómo reparar un router

1. Busca un router rojo y acércate hasta quedar junto a él.
2. Observa la línea que gira dentro del router.
3. Cuando el router se vuelva amarillo, pulsa `E`. La ventana amarilla dura
   aproximadamente un segundo.
4. Si pulsaste dentro del intervalo correcto, el router se volverá verde y
   sumarás una reparación.

### Colores

- Rojo: router averiado.
- Amarillo: ventana correcta para repararlo.
- Verde: router reparado.
- Azul, rosa, amarillo o morado: jugadores conectados.

## Reglas especiales

### Campaña cooperativa

1. **Diagnóstico del campus:** reparen tres routers diferentes.
2. **Ruta crítica:** el servidor elige cuatro routers diferentes al azar en
   cada campaña. Deben repararlos en el orden mostrado; el objetivo actual
   aparece rodeado por un halo amarillo.
3. **Cobertura UNI:** activen un router de la zona superior, uno de la central
   y uno de la inferior. Deben mantener esos tres routers verdes
   simultáneamente durante 15 segundos; no es necesario activar todos los
   routers del mapa.
4. **Apagón general:** activen cinco routers y manténganlos estables durante
   10 segundos.

Cada misión tiene un límite de tiempo. Completar las cuatro produce una
victoria compartida; si se agota un cronómetro, el equipo pierde. Después del
resultado se puede pulsar `R` o usar el botón de reinicio para comenzar otra
campaña.

### Ciclo del Lag

Solo puede haber cinco routers reparados al mismo tiempo. Cuando se repara un
nuevo router y ya se alcanzó ese límite, otro router activo se avería
aleatoriamente.

### Karma de Conexión

Cada 60 segundos, siempre que haya al menos dos jugadores:

- Quien tenga más reparaciones recibe **Ping 999ms** y se mueve al 25 % de su
  velocidad durante 10 segundos.
- Quien tenga menos reparaciones recibe **Fibra Óptica** y duplica su velocidad
  durante 10 segundos.

La tabla de clasificación muestra el orden de los jugadores, sus reparaciones
y los estados de Karma activos para identificar al líder y al último lugar.

### Pollo a la brasa y supervivencia

- Cada reparación aumenta el cansancio y reduce gradualmente la velocidad.
- En el **Comedor** puedes pulsar `E` para recoger una porción del stock
  compartido. Solo puedes llevar una y debes esperar 15 segundos antes de
  recoger otra; su icono es un pollo y no un router.
- Pulsa `Q` para recuperar vida, reducir cansancio y obtener velocidad temporal.
- El **Centro Médico**, marcado con una cruz, recupera vida poco a poco mientras
  permaneces cerca.
- Las bombas de lag aparecen en los pasillos, avisan durante tres segundos y
  causan daño al explotar.
- Fallar la sincronización de un router también causa daño.
- Si un jugador pierde toda la vida queda fuera de juego: no se mueve ni
  interactúa y solo observa, pero el resto del equipo sigue jugando. La campaña
  solo termina en derrota cuando todos los jugadores quedan eliminados.

El mapa ampliado utiliza una cámara que sigue al jugador. El minimapa y las
flechas indican el objetivo de misión, el Comedor y el Centro Médico.

### Eventos del Comedor

Cada 60–90 segundos puede activarse durante 20 segundos uno de estos eventos:

- **¡DOBLEEE!**: una recogida entrega dos porciones.
- **¡TRIPLEEE!**: el raro menú triple entrega tres porciones.
- **¡MENÚ CON MOSCA!**: la porción causa daño y cansancio al consumirla.

Los eventos aparecen como una alerta grande. El stock sigue siendo compartido
y cada jugador mantiene su recarga personal de 15 segundos.

### Power-ups del campus

Cada 22–38 segundos aparece (hasta dos a la vez) un power-up en los pasillos.
Se recogen automáticamente al pasar por encima y desaparecen si nadie los toma
en 25 segundos. El minimapa y una flecha **BONUS** ayudan a localizarlos.

- **Escudo Firewall** (azul, `E`): otorga invulnerabilidad temporal; ignora
  bombas y cortocircuitos durante unos segundos.
- **Parche Express** (verde, `P`): guarda una carga que repara automáticamente
  el próximo router aunque falles la sincronización. Solo se gasta cuando el
  ángulo es incorrecto.
- **Respaldo de Red** (celeste, `R`): congela el Ciclo del Lag para todo el
  equipo, así reparar de más no derriba otros routers durante su duración.

El Escudo y el Parche son individuales y se pierden al perder la conexión; el
Respaldo de Red beneficia a todo el equipo.

### Prof. Montalvo y logros secretos

El Prof. Montalvo espera cerca de CTIC. Acércate y pulsa `E` para aceptar una
misión secundaria individual, como reparar routers de emergencia o recorrer
lugares del campus antes de que cierre la práctica. Completarla reduce el
cansancio y desbloquea un logro.

Otros logros secretos se revelan al reparar por primera vez, recorrer varias
facultades, probar menús especiales o recuperarse en el Centro Médico. El HUD
muestra cuántos has descubierto, pero no revela los pendientes.

Los límites de las cuatro misiones principales se ampliaron para que una
campaña completa dure aproximadamente entre 8 y 12 minutos y permita explorar
estas actividades opcionales.

## Instalación

Requiere Python 3.10 o posterior.

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Ejecutar una partida local

Primero inicia el servidor:

```powershell
.\.venv\Scripts\python.exe server.py
```

Luego abre otra terminal por cada jugador:

```powershell
.\.venv\Scripts\python.exe client.py --name "Jugador 1"
```

Se pueden abrir hasta cuatro clientes en la misma computadora.

## Jugar en una red LAN

1. Inicia `server.py` en la computadora que actuará como servidor.
2. Averigua la dirección IPv4 local de esa computadora con `ipconfig`.
3. En cada computadora cliente ejecuta:

```powershell
.\.venv\Scripts\python.exe client.py --host IP_DEL_SERVIDOR --name "Jugador 2"
```

El servidor utiliza el puerto TCP `5555`. Si Windows muestra una alerta de
firewall, permite el acceso en redes privadas.

## Usar otro puerto o un túnel TCP

Servidor:

```powershell
.\.venv\Scripts\python.exe server.py --port 6000
```

Cliente:

```powershell
.\.venv\Scripts\python.exe client.py --host HOST --port PUERTO --name "Jugador"
```

Para jugar mediante un túnel, este debe reenviar tráfico **TCP** al puerto del
servidor. Usa el host y el puerto públicos entregados por el proveedor en los
argumentos del cliente.

## Apagar el servidor

En la terminal del servidor pulsa `Ctrl+C`. Si Windows no lo detiene, abre otra
terminal PowerShell y ejecuta:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*server.py*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

## Arquitectura

- `network.py`: protocolo TCP/IPv4 con mensajes JSON.
- `server.py`: estado autoritativo, colisiones, routers y Karma.
- `client.py`: interfaz, controles y renderizado con Pygame.
- `audio.py`: carga y reproduce los efectos de sonido de `assets/`.
- `sprites.py`: carga los iconos PNG de `assets/` (escalado y tintado) con
  respaldo al dibujo procedural cuando falta un archivo.
- `generate_sprites.py`: regenera los iconos PNG por código (`python
  generate_sprites.py`).
- `test_network.py` y `test_server.py`: pruebas automatizadas.
