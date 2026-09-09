"""Process-local TCP test proxy with controlled cuts and per-connection stalls."""
import socket
import threading
import time


class RdpTestProxy:
    def __init__(self, destination=('127.0.0.1', 47273)):
        self.destination = destination
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(4)
        self.listener.settimeout(.2)
        self.port = self.listener.getsockname()[1]
        self.stopped = threading.Event()
        self.lock = threading.RLock()
        self.connections = []
        self.active = None
        self.thread = threading.Thread(target=self._accept, daemon=True)
        self.thread.start()

    def _accept(self):
        while not self.stopped.is_set():
            try:
                client, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                server = socket.create_connection(self.destination, timeout=5)
                server.settimeout(None)
            except OSError:
                client.close()
                continue
            with self.lock:
                if self.active:
                    self._close(self.active)
                flow = threading.Event()
                flow.set()
                connection = {'sockets': (client, server), 'flow': flow, 'closed': False,
                              'number': len(self.connections)+1, 'started': time.monotonic(),
                              'upBytes': 0, 'downBytes': 0, 'threads': []}
                self.connections.append(connection)
                self.active = connection
                for source, destination, key in [(client, server, 'upBytes'), (server, client, 'downBytes')]:
                    thread = threading.Thread(target=self._forward,
                        args=(connection, source, destination, key), daemon=True)
                    connection['threads'].append(thread)
                    thread.start()

    def _forward(self, connection, source, destination, key):
        try:
            while not connection['closed'] and not self.stopped.is_set():
                if not connection['flow'].wait(.2):
                    continue
                data = source.recv(65536)
                if not data:
                    break
                while not connection['closed'] and not connection['flow'].wait(.2):
                    pass
                if connection['closed']:
                    break
                destination.sendall(data)
                connection[key] += len(data)
        except OSError:
            pass
        finally:
            with self.lock:
                self._close(connection)

    def _close(self, connection):
        if connection['closed']:
            return
        connection['closed'] = True
        connection['finished'] = time.monotonic()
        connection['flow'].set()
        for peer in connection['sockets']:
            try:
                peer.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            peer.close()

    def cut(self):
        with self.lock:
            if self.active:
                self._close(self.active)

    def pause(self):
        with self.lock:
            assert self.active and not self.active['closed']
            self.active['flow'].clear()

    def resume(self):
        with self.lock:
            if self.active:
                self.active['flow'].set()

    def snapshot(self):
        with self.lock:
            return [{k: v for k, v in c.items() if k not in ('sockets', 'flow', 'threads')}
                    for c in self.connections]

    def close(self):
        self.stopped.set()
        self.listener.close()
        with self.lock:
            for connection in self.connections:
                self._close(connection)
        self.thread.join(timeout=2)
        for connection in self.connections:
            for thread in connection['threads']:
                thread.join(timeout=2)
