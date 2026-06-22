"""Utilidades de red compartidas por el cliente y el servidor.

El protocolo utiliza TCP/IPv4 y mensajes JSON UTF-8 precedidos por una
cabecera de cuatro bytes que contiene el tamaño del cuerpo en orden de red.
"""

from __future__ import annotations

import json
import socket
import struct
import threading
from typing import Any


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5555
HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 1_048_576  # 1 MiB
_HEADER_FORMAT = "!I"


class NetworkError(Exception):
    """Error base de la capa de red."""


class NetworkConnectionError(NetworkError):
    """No se pudo establecer o mantener la conexión."""


class ConnectionClosedError(NetworkConnectionError):
    """El otro extremo cerró la conexión."""


class ProtocolError(NetworkError):
    """El mensaje no cumple el protocolo esperado."""


class MessageTooLargeError(ProtocolError):
    """El mensaje supera el límite permitido."""


def _receive_exact(connection: socket.socket, size: int) -> bytes:
    """Lee exactamente ``size`` bytes o informa una desconexión."""
    chunks: list[bytes] = []
    bytes_received = 0

    while bytes_received < size:
        try:
            chunk = connection.recv(size - bytes_received)
        except socket.timeout as exc:
            raise NetworkConnectionError(
                "Se agotó el tiempo de espera al recibir datos."
            ) from exc
        except OSError as exc:
            raise NetworkConnectionError(
                f"Error al recibir datos: {exc}"
            ) from exc

        if not chunk:
            raise ConnectionClosedError(
                "La conexión se cerró antes de recibir el mensaje completo."
            )

        chunks.append(chunk)
        bytes_received += len(chunk)

    return b"".join(chunks)


def _serialize_message(data: dict[str, Any]) -> bytes:
    if not isinstance(data, dict):
        raise ProtocolError("El mensaje debe ser un diccionario.")

    message_type = data.get("type")
    if message_type is not None and not isinstance(message_type, str):
        raise ProtocolError("El campo 'type' debe ser una cadena.")

    try:
        payload = json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ProtocolError(f"El mensaje no se puede serializar como JSON: {exc}") from exc

    if not payload:
        raise ProtocolError("El mensaje JSON no puede estar vacío.")
    if len(payload) > MAX_MESSAGE_SIZE:
        raise MessageTooLargeError(
            f"El mensaje ocupa {len(payload)} bytes; "
            f"el máximo es {MAX_MESSAGE_SIZE}."
        )

    return payload


def send_message(connection: socket.socket, data: dict[str, Any]) -> None:
    """Serializa y envía un mensaje completo por un socket conectado."""
    payload = _serialize_message(data)
    packet = struct.pack(_HEADER_FORMAT, len(payload)) + payload

    try:
        connection.sendall(packet)
    except socket.timeout as exc:
        raise NetworkConnectionError(
            "Se agotó el tiempo de espera al enviar datos."
        ) from exc
    except OSError as exc:
        raise NetworkConnectionError(f"Error al enviar datos: {exc}") from exc


def receive_message(connection: socket.socket) -> dict[str, Any]:
    """Recibe y deserializa un mensaje completo de un socket conectado."""
    header = _receive_exact(connection, HEADER_SIZE)
    (payload_size,) = struct.unpack(_HEADER_FORMAT, header)

    if payload_size == 0:
        raise ProtocolError("Se recibió un mensaje vacío.")
    if payload_size > MAX_MESSAGE_SIZE:
        raise MessageTooLargeError(
            f"El mensaje anuncia {payload_size} bytes; "
            f"el máximo es {MAX_MESSAGE_SIZE}."
        )

    payload = _receive_exact(connection, payload_size)
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"Se recibió JSON inválido: {exc}") from exc

    if not isinstance(data, dict):
        raise ProtocolError("La raíz del mensaje JSON debe ser un objeto.")

    message_type = data.get("type")
    if message_type is not None and not isinstance(message_type, str):
        raise ProtocolError("El campo 'type' debe ser una cadena.")

    return data


class Network:
    """Cliente TCP síncrono y seguro para mensajes enmarcados con JSON."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float | None = 5.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._io_lock = threading.RLock()

    @property
    def connected(self) -> bool:
        return self._socket is not None

    def connect(self) -> "Network":
        """Abre la conexión TCP/IPv4 y devuelve esta instancia."""
        with self._io_lock:
            if self.connected:
                return self

            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection.settimeout(self.timeout)

            try:
                connection.connect((self.host, self.port))
            except (socket.timeout, OSError) as exc:
                connection.close()
                raise NetworkConnectionError(
                    f"No fue posible conectar con {self.host}:{self.port}: {exc}"
                ) from exc

            self._socket = connection
            return self

    def _require_connection(self) -> socket.socket:
        if self._socket is None:
            raise NetworkConnectionError(
                "No hay una conexión activa. Llama a connect() primero."
            )
        return self._socket

    def send(self, data: dict[str, Any]) -> None:
        """Envía un diccionario JSON al servidor."""
        with self._io_lock:
            send_message(self._require_connection(), data)

    def receive(self) -> dict[str, Any]:
        """Espera y devuelve el siguiente diccionario JSON del servidor."""
        with self._io_lock:
            return receive_message(self._require_connection())

    def request(self, data: dict[str, Any]) -> dict[str, Any]:
        """Envía una solicitud y espera su respuesta sin intercalado de hilos."""
        with self._io_lock:
            connection = self._require_connection()
            send_message(connection, data)
            return receive_message(connection)

    def close(self) -> None:
        """Cierra la conexión de forma idempotente."""
        with self._io_lock:
            connection = self._socket
            self._socket = None
            if connection is None:
                return

            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            finally:
                connection.close()

    def __enter__(self) -> "Network":
        return self.connect()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

