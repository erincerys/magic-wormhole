from urllib.parse import urlsplit

from attr import attrib, attrs
from twisted.internet.endpoints import HostnameEndpoint
from zope.interface import implementer
import txtorcon

from ._interfaces import ISocksProxy
from .errors import UnsupportedProxyError


@implementer(ISocksProxy)
@attrs
class SocksProxy:
    """Connect streams through one explicitly configured SOCKS5 proxy."""

    host = attrib()
    port = attrib()
    reactor = attrib()

    def stream_via(self, host, port, tls=False):
        return txtorcon.socks.TorSocksEndpoint(
            HostnameEndpoint(self.reactor, self.host, self.port),
            host, port, tls=tls,
        )


def parse_proxy_url(url):
    """Return the host and port from an unauthenticated SOCKS5 URL."""
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127
           for character in url):
        raise UnsupportedProxyError(
            "Proxy URL must not contain whitespace or control characters.")
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise UnsupportedProxyError("Proxy URL has an invalid host.") from None

    if parsed.scheme not in ("socks5", "socks5h"):
        raise UnsupportedProxyError(
            f"Unsupported proxy scheme {parsed.scheme!r}; unset ALL_PROXY/all_proxy "
            "or use --socks-host/--socks-port instead.")
    if "@" in parsed.netloc:
        raise UnsupportedProxyError("Proxy credentials are not supported.")
    if not parsed.hostname:
        raise UnsupportedProxyError("Proxy URL is missing a host.")
    if parsed.netloc.startswith("["):
        suffix = parsed.netloc.split("]", 1)[1]
        if suffix and not suffix.startswith(":"):
            raise UnsupportedProxyError("Proxy URL has an invalid host.")
    if parsed.path not in ("", "/"):
        raise UnsupportedProxyError("Proxy URL must not contain a path other than '/'.")
    if "?" in url or "#" in url:
        raise UnsupportedProxyError("Proxy URL must not contain a query or fragment.")
    try:
        port = parsed.port
    except ValueError:
        raise UnsupportedProxyError(
            "Proxy port must be an integer from 1 to 65535.") from None
    if parsed.netloc.endswith(":") or port == 0:
        raise UnsupportedProxyError("Proxy port must be an integer from 1 to 65535.")
    return parsed.hostname, 1080 if port is None else port


def resolve_proxy(reactor, socks_host, socks_port, environ, stderr):
    """Select explicit SOCKS options or ALL_PROXY without a direct fallback."""
    if socks_port is not None and not socks_host:
        raise UnsupportedProxyError("--socks-port requires --socks-host.")
    if socks_host:
        proxy = SocksProxy(socks_host, 1080 if socks_port is None else socks_port, reactor)
    else:
        url = environ.get("ALL_PROXY") or environ.get("all_proxy")
        if not url:
            return None
        host, port = parse_proxy_url(url)
        proxy = SocksProxy(host, port, reactor)
    if environ.get("NO_PROXY") or environ.get("no_proxy"):
        stderr.write("Warning: NO_PROXY is ignored; every connection goes through the proxy.\n")
    return proxy
