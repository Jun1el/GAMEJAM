# La vida da vueltas en Eduroam

Juego multijugador 2D para un máximo de cuatro personas, ambientado en la
Universidad Nacional de Ingeniería. Los jugadores recorren el campus para
reparar los routers Eduroam en el momento correcto, mientras el servidor
mantiene las posiciones, colisiones y reglas de la partida.

## Objetivo

Consigue la mayor cantidad de reparaciones. Acércate a un router averiado y
pulsa `E` cuando su indicador esté dentro de la zona de sincronización.

Los routers representan estos lugares:

- FIGMM, FIEE, Biblioteca, Comedor, FIEECS, FIC, FIA y FIQT.
- CTIC, FIM, FIIS, FC, Estadio UNI, Centro Médico y FAUA.
- FIP, Entrada y Salida.

## Controles

| Acción | Tecla |
| --- | --- |
| Moverse | `WASD` o flechas |
| Intentar reparar | `E` |
| Salir | `Esc` o cerrar la ventana |

Al abrir el cliente aparece una pantalla de inicio. Escribe o modifica el
nombre del jugador y pulsa **Conectar a Eduroam** para entrar a la partida.

## Cómo reparar un router

1. Busca un router rojo y acércate hasta quedar junto a él.
2. Observa la línea que gira dentro del router.
3. Cuando el router se vuelva amarillo, pulsa `E`. La ventana amarilla dura
   aproximadamente un tercio de segundo.
4. Si pulsaste dentro del intervalo correcto, el router se volverá verde y
   sumarás una reparación.

### Colores

- Rojo: router averiado.
- Amarillo: ventana correcta para repararlo.
- Verde: router reparado.
- Azul, rosa, amarillo o morado: jugadores conectados.

## Reglas especiales

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
- `test_network.py` y `test_server.py`: pruebas automatizadas.
