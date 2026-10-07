import os
import socket

import blue
import scheduler

import carbonapp

DEFAULT_PORT = int(os.environ.get("NET_PORT", "47400"))
MAX_PACKET = 16 << 20


class Peer:
    def __init__(self, sock, on_message, on_close=lambda peer: None):
        self.sock = sock
        self.alive = True
        self.bytes_sent = 0
        self.bytes_received = 0
        self._on_message = on_message
        self._on_close = on_close
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setmaxpacketsize(MAX_PACKET)
        carbonapp.spawn(self._read_loop)

    def send(self, message):
        if not self.alive:
            return
        data = blue.marshal.Save(message)
        self.bytes_sent += len(data) + 4
        try:
            self.sock.sendpacket(data)
        except OSError:
            self.close()

    def _read_loop(self):
        try:
            while self.alive:
                data, _oob, _seq = self.sock.recvpacketoob()
                if data is None:
                    break
                self.bytes_received += len(data) + 4
                self._on_message(self, blue.marshal.Load(data))
        except OSError:
            pass
        finally:
            self.close()

    def close(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.sock.close()
        except OSError:
            pass
        self._on_close(self)


def serve(port, on_connect):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("0.0.0.0", port))
    listener.listen(16)

    def accept_loop():
        while True:
            sock, address = listener.accept()
            on_connect(sock, address)

    carbonapp.spawn(accept_loop)
    return listener


def connect(host, port):
    if scheduler.getcurrent().is_main:
        raise RuntimeError("connect() must run in a tasklet")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
    except OSError:
        sock.close()
        raise
    return sock
