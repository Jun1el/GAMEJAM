import json
import socket
import struct
import threading
import unittest

from network import (
    MAX_MESSAGE_SIZE,
    ConnectionClosedError,
    MessageTooLargeError,
    Network,
    NetworkConnectionError,
    ProtocolError,
    receive_message,
    send_message,
)


class NetworkProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.left, self.right = socket.socketpair()

    def tearDown(self) -> None:
        self.left.close()
        self.right.close()

    def test_round_trip_preserves_unicode_and_fields(self) -> None:
        expected = {
            "type": "join",
            "payload": {"name": "Jugador UNI", "zone": "BIBLIOTECA"},
            "request_id": "req-1",
        }

        send_message(self.left, expected)

        self.assertEqual(receive_message(self.right), expected)

    def test_receive_handles_fragmented_tcp_data(self) -> None:
        expected = {"type": "state", "payload": {"x": 32, "y": 64}}
        body = json.dumps(expected).encode("utf-8")
        packet = struct.pack("!I", len(body)) + body

        for byte in packet:
            self.left.sendall(bytes([byte]))

        self.assertEqual(receive_message(self.right), expected)

    def test_receive_handles_consecutive_messages(self) -> None:
        first = {"type": "input", "payload": {"up": True}}
        second = {"type": "interact", "payload": {"action": "repair"}}

        send_message(self.left, first)
        send_message(self.left, second)

        self.assertEqual(receive_message(self.right), first)
        self.assertEqual(receive_message(self.right), second)

    def test_rejects_non_dictionary_messages(self) -> None:
        with self.assertRaises(ProtocolError):
            send_message(self.left, ["not", "an", "object"])  # type: ignore[arg-type]

    def test_rejects_invalid_json(self) -> None:
        body = b"{invalid"
        self.left.sendall(struct.pack("!I", len(body)) + body)

        with self.assertRaises(ProtocolError):
            receive_message(self.right)

    def test_rejects_oversized_announced_payload(self) -> None:
        self.left.sendall(struct.pack("!I", MAX_MESSAGE_SIZE + 1))

        with self.assertRaises(MessageTooLargeError):
            receive_message(self.right)

    def test_detects_incomplete_message(self) -> None:
        self.left.sendall(struct.pack("!I", 10) + b"short")
        self.left.shutdown(socket.SHUT_WR)

        with self.assertRaises(ConnectionClosedError):
            receive_message(self.right)


class NetworkClientTests(unittest.TestCase):
    def test_request_and_context_manager(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        host, port = server.getsockname()

        def serve_once() -> None:
            connection, _ = server.accept()
            with connection:
                request = receive_message(connection)
                send_message(
                    connection,
                    {
                        "type": "ack",
                        "payload": request["payload"],
                        "request_id": request["request_id"],
                    },
                )
            server.close()

        thread = threading.Thread(target=serve_once)
        thread.start()

        with Network(host, port, timeout=2.0) as network:
            response = network.request(
                {
                    "type": "join",
                    "payload": {"name": "Ada"},
                    "request_id": "42",
                }
            )
            self.assertTrue(network.connected)

        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())
        self.assertFalse(network.connected)
        self.assertEqual(response["type"], "ack")
        self.assertEqual(response["request_id"], "42")

    def test_operations_require_connection(self) -> None:
        network = Network()

        with self.assertRaises(NetworkConnectionError):
            network.send({"type": "join", "payload": {}})


if __name__ == "__main__":
    unittest.main()
