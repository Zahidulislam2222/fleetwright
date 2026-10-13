"""HTTP-only crawler egress: allowlisted origin, validated DNS and pinned socket/TLS SNI.

Redirects are rejected. Browser execution and ambient proxy settings are deliberately absent:
fetching a page never executes untrusted scripts or triggers uncontrolled subresource requests.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlsplit


class EgressDenied(ValueError):
    pass


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    content_type: str


def validate_url(url: str, origin: str) -> tuple[str, str, int, str]:
    target, allowed = urlsplit(url), urlsplit(origin)
    if target.scheme not in {"http", "https"} or not target.hostname or target.username or target.password:
        raise EgressDenied("unsupported or credential-bearing URL")
    if target.fragment or any(ord(c) <= 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise EgressDenied("ambiguous URL")
    # Scheme default ports are HTTP protocol constants.
    port = target.port or (443 if target.scheme == "https" else 80)
    allowed_port = allowed.port or (443 if allowed.scheme == "https" else 80)
    if (target.scheme, target.hostname, port) != (allowed.scheme, allowed.hostname, allowed_port):
        raise EgressDenied("origin not allowed")
    path = target.path or "/"
    if target.query:
        path += "?" + target.query
    return target.scheme, target.hostname, port, path


def addresses(host: str, port: int, allow_private: bool) -> list[str]:
    resolved = sorted({str(row[4][0]) for row in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    if not resolved:
        raise EgressDenied("no destination addresses")
    for value in resolved:
        address = ipaddress.ip_address(value)
        effective = getattr(address, "ipv4_mapped", None) or address
        # Metadata/link-local/multicast/unspecified destinations are forbidden even for owned origins.
        if effective.is_link_local or effective.is_multicast or effective.is_unspecified or effective.is_reserved:
            raise EgressDenied("forbidden destination address")
        if not allow_private and not effective.is_global:
            raise EgressDenied("non-public destination address")
    return resolved


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        self.tls_context = ssl.create_default_context()
        super().__init__(host, port, timeout=timeout, context=self.tls_context)
        self.address = address

    def connect(self) -> None:
        sock = socket.create_connection((self.address, self.port), self.timeout)
        self.sock = self.tls_context.wrap_socket(sock, server_hostname=self.host)


def fetch(url: str, origin: str, *, allow_private: bool, timeout: float, limit: int, user_agent: str) -> Response:
    scheme, host, port, path = validate_url(url, origin)
    resolved = addresses(host, port, allow_private)
    conn = (
        PinnedHTTPS(host, port, resolved[0], timeout)
        if scheme == "https"
        else http.client.HTTPConnection(resolved[0], port, timeout=timeout)
    )
    authority = urlsplit(origin).netloc
    try:
        conn.request("GET", path, headers={"Host": authority, "User-Agent": user_agent, "Accept-Encoding": "identity"})
        response = conn.getresponse()
        if 300 <= response.status < 400:
            raise EgressDenied("redirects are not allowed")
        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            raise EgressDenied("compressed responses are not accepted")
        expected = response.length
        if expected is not None and expected > limit:
            raise EgressDenied("response size limit exceeded")
        body = response.read(limit + 1)
        if len(body) > limit:
            raise EgressDenied("response size limit exceeded")
        # HTTPResponse.read(amt) can return early at EOF without IncompleteRead.
        # A syntactically valid JSON prefix must never make a truncated page successful.
        if expected is not None and len(body) != expected:
            raise http.client.IncompleteRead(body, expected - len(body))
        return Response(response.status, body, response.getheader("Content-Type", ""))
    finally:
        conn.close()
