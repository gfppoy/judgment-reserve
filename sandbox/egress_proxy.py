"""CONNECT-only provider allowlist. No case, answer, or credential files are mounted."""
from __future__ import annotations

import ipaddress
import os
import select
import socket
import socketserver

PROVIDERS = {
    "codex": {"api.openai.com", "auth.openai.com", "auth0.openai.com", "chatgpt.com"},
    "claude": {"api.anthropic.com", "claude.ai", "console.anthropic.com",
               "platform.claude.com", "accounts.anthropic.com", "auth.anthropic.com"},
}


def allowed(host: str, port: int, provider: str) -> bool:
    return port == 443 and host.lower() in PROVIDERS.get(provider, set())


def upstream(host, port):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    # Resolve once and connect to that exact public address; do not re-resolve later.
    addresses = [a for a in addresses if ipaddress.ip_address(a[4][0]).is_global]
    if not addresses:
        raise OSError("No public upstream address")
    last = None
    for family, socktype, proto, _, address in addresses:
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(15)
        try:
            sock.connect(address)
            return sock
        except OSError as error:
            last = error
            sock.close()
    raise last or OSError("Connection failed")


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        peer = self.request
        peer.settimeout(15)
        try:
            header = b""
            while b"\r\n\r\n" not in header and len(header) <= 8192:
                chunk = peer.recv(1)
                if not chunk:
                    return
                header += chunk
            if len(header) > 8192:
                return
            line = header.split(b"\r\n", 1)[0].decode("ascii")
            method, authority, version = line.split()
            host, port = authority.rsplit(":", 1)
            if method != "CONNECT" or version not in ("HTTP/1.0", "HTTP/1.1") or not allowed(
                    host, int(port), os.environ.get("RESERVE_PROVIDER", "")):
                peer.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
                return
            with upstream(host, int(port)) as remote:
                peer.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                peer.settimeout(60)
                remote.settimeout(60)
                while True:
                    ready, _, _ = select.select([peer, remote], [], [], 120)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        (remote if source is peer else peer).sendall(data)
        except (OSError, ValueError, UnicodeError):
            return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("0.0.0.0", 8080), Handler) as server:
        server.serve_forever()
