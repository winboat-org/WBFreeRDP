#!/usr/bin/env python3
"""Verify that the fault injector preserves bytes and only disrupts its own sockets."""
from pathlib import Path
import socket
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from rdp_test_proxy import RdpTestProxy

listener = socket.socket()
listener.bind(('127.0.0.1', 0))
listener.listen(4)
listener.settimeout(.2)
stopped = threading.Event()

def echo(connection):
    with connection:
        try:
            while data := connection.recv(65536):
                connection.sendall(data)
        except OSError:
            pass

def accept():
    while not stopped.is_set():
        try:
            peer, _ = listener.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        threading.Thread(target=echo, args=(peer,), daemon=True).start()

thread = threading.Thread(target=accept, daemon=True)
thread.start()
proxy = RdpTestProxy(listener.getsockname())

def read_exact(peer, size):
    data = b''
    while len(data) < size:
        part = peer.recv(size-len(data))
        assert part
        data += part
    return data

try:
    payload = bytes(range(256)) * 1024
    with socket.create_connection(('127.0.0.1', proxy.port), timeout=2) as peer:
        peer.sendall(payload)
        assert read_exact(peer, len(payload)) == payload
        proxy.pause()
        peer.sendall(b'held')
        peer.settimeout(.2)
        try:
            peer.recv(4)
            raise AssertionError('Paused proxy forwarded data')
        except socket.timeout:
            pass
        proxy.resume()
        peer.settimeout(2)
        assert read_exact(peer, 4) == b'held'
        proxy.cut()
        assert peer.recv(1) == b''
    with socket.create_connection(('127.0.0.1', proxy.port), timeout=2) as peer:
        peer.sendall(payload[::-1])
        assert read_exact(peer, len(payload)) == payload[::-1]
    assert len(proxy.snapshot()) == 2
    print('PASS: byte preservation, bounded pause/resume, deliberate cut, subsequent connection')
finally:
    proxy.close()
    stopped.set()
    listener.close()
    thread.join(timeout=2)
