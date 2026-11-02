import io
import os
from unittest import mock

import pytest
import txtorcon
from twisted.internet.protocol import Protocol

from .._interfaces import ISocksProxy, ITorManager
from ..errors import UnsupportedProxyError, WormholeError
from ..socks_proxy import SocksProxy, parse_proxy_url, resolve_proxy


@pytest.mark.parametrize("url, expected", [
    ("socks5://proxy.example:9050", ("proxy.example", 9050)),
    ("socks5h://proxy.example:1081", ("proxy.example", 1081)),
    ("SOCKS5://proxy.example", ("proxy.example", 1080)),
    ("SoCkS5h://proxy.example/", ("proxy.example", 1080)),
    ("socks5://127.0.0.1:1080", ("127.0.0.1", 1080)),
    ("socks5h://[::1]:1081", ("::1", 1081)),
    ("socks5://[::1]", ("::1", 1080)),
    ("socks5://proxy.example:1", ("proxy.example", 1)),
    ("socks5://proxy.example:65535", ("proxy.example", 65535)),
])
def test_parse_proxy_url(url, expected):
    assert parse_proxy_url(url) == expected


@pytest.mark.parametrize("url, reason", [
    ("socks5://alice@proxy.example", "credentials"),
    ("socks5://alice:secret-password@proxy.example", "credentials"),
    ("socks5://@proxy.example", "credentials"),
    ("http://proxy.example", "http"),
    ("socks4://proxy.example", "socks4"),
    ("proxy.example:1080", "must start with socks5:// or socks5h://"),
    ("socks5://proxy.example/path", "path"),
    ("socks5://proxy.example?query=value", "query"),
    ("socks5://proxy.example#fragment", "fragment"),
    ("socks5://proxy.example?", "query"),
    ("socks5://proxy.example#", "fragment"),
    ("socks5://", "host"),
    ("socks5:///", "host"),
    ("socks5://:1080", "host"),
    ("socks5://proxy.example:invalid", "port"),
    ("socks5://proxy.example:0", "port"),
    ("socks5://proxy.example:65536", "port"),
    ("socks5://proxy.example:-1", "port"),
    ("socks5://proxy.example:", "port"),
    ("socks5://[::1", "host"),
    ("socks5://[::1]unexpected", "host"),
    ("socks5://::1", "host"),
    ("socks5://proxy.\nexample", "control"),
])
def test_parse_proxy_url_refuses_unsupported_configuration(url, reason):
    with pytest.raises(UnsupportedProxyError) as exc:
        parse_proxy_url(url)
    message = str(exc.value)
    assert reason in message
    assert len(message.splitlines()) == 1
    assert "alice" not in message
    assert "secret-password" not in message
    assert isinstance(exc.value, WormholeError)


def test_parse_proxy_url_without_scheme_never_echoes_credentials():
    with pytest.raises(UnsupportedProxyError) as exc:
        parse_proxy_url("alice:secret@host:1080")
    message = str(exc.value)
    assert message == "Proxy URL must start with socks5:// or socks5h://."
    assert "alice" not in message
    assert "secret" not in message


def test_parse_proxy_url_preserves_unsupported_scheme_message():
    with pytest.raises(UnsupportedProxyError) as exc:
        parse_proxy_url("http://proxy.example.com")
    assert str(exc.value) == (
        "Unsupported proxy scheme 'http'; unset ALL_PROXY/all_proxy "
        "or use --socks-host/--socks-port instead.")


@pytest.mark.parametrize("url", [
    "http://alice:secret-password@proxy.example",
    "socks5://alice:secret-password@[invalid]",
])
def test_parse_proxy_url_never_echoes_userinfo(url):
    with pytest.raises(UnsupportedProxyError) as exc:
        parse_proxy_url(url)
    assert "alice" not in str(exc.value)
    assert "secret-password" not in str(exc.value)


@pytest.mark.parametrize("scheme", ["http", "socks4"])
def test_unsupported_scheme_explains_how_to_disable_or_override(scheme):
    with pytest.raises(UnsupportedProxyError) as exc:
        parse_proxy_url(f"{scheme}://proxy.example")
    message = str(exc.value)
    for text in (scheme, "unset", "ALL_PROXY", "--socks-host", "--socks-port"):
        assert text in message


@pytest.mark.parametrize("host, port, environ, expected", [
    ("explicit.example", 9999,
     {"ALL_PROXY": "http://invalid", "all_proxy": "socks5://lower.example"},
     ("explicit.example", 9999)),
    ("explicit.example", None,
     {"ALL_PROXY": "socks5://upper.example:2222"},
     ("explicit.example", 1080)),
    (None, None,
     {"ALL_PROXY": "socks5://upper.example:2222", "all_proxy": "socks5://lower.example:3333"},
     ("upper.example", 2222)),
    (None, None, {"all_proxy": "socks5://lower.example:3333"},
     ("lower.example", 3333)),
    (None, None, {"ALL_PROXY": "", "all_proxy": "socks5h://lower.example"},
     ("lower.example", 1080)),
    (None, None, {"ALL_PROXY": "socks5://upper.example", "all_proxy": ""},
     ("upper.example", 1080)),
    (None, None, {}, None),
    (None, None, {"ALL_PROXY": "", "all_proxy": ""}, None),
])
def test_resolve_proxy_precedence(host, port, environ, expected):
    reactor = object()
    stderr = io.StringIO()
    proxy = resolve_proxy(reactor, host, port, environ, stderr)
    if expected is None:
        assert proxy is None
    else:
        assert proxy == SocksProxy(*expected, reactor)
        assert ISocksProxy.providedBy(proxy)
        assert not ITorManager.providedBy(proxy)
    assert stderr.getvalue() == ""


def test_resolve_proxy_port_requires_explicit_host():
    stderr = io.StringIO()
    with pytest.raises(UnsupportedProxyError, match="--socks-port requires --socks-host"):
        resolve_proxy(object(), None, 1081, {"ALL_PROXY": "socks5://proxy.example"}, stderr)
    assert stderr.getvalue() == ""


def test_resolve_proxy_errors_do_not_fall_back():
    stderr = io.StringIO()
    with pytest.raises(UnsupportedProxyError):
        resolve_proxy(object(), None, None, {
            "ALL_PROXY": "http://unsupported.example",
            "all_proxy": "socks5://valid.example",
        }, stderr)
    assert stderr.getvalue() == ""


def test_resolve_proxy_uses_only_passed_environment(monkeypatch):
    monkeypatch.setenv("ALL_PROXY", "socks5://ambient.example")
    monkeypatch.setenv("NO_PROXY", "*")
    stderr = io.StringIO()
    assert resolve_proxy(object(), None, None, {}, stderr) is None
    assert stderr.getvalue() == ""


def test_proxy_environment_is_cleared():
    for name in ("ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        assert name not in os.environ


@pytest.mark.parametrize("host, proxy_environment", [
    ("explicit.example", {}),
    (None, {"ALL_PROXY": "socks5://upper.example"}),
    (None, {"all_proxy": "socks5://lower.example"}),
])
@pytest.mark.parametrize("bypass_environment, warned", [
    ({"NO_PROXY": "example.com"}, True),
    ({"no_proxy": "example.com"}, True),
    ({"NO_PROXY": "example.com", "no_proxy": "*"}, True),
    ({"NO_PROXY": "", "no_proxy": ""}, False),
])
def test_no_proxy_warning(host, proxy_environment, bypass_environment, warned):
    stderr = io.StringIO()
    proxy = resolve_proxy(object(), host, None,
                          {**proxy_environment, **bypass_environment}, stderr)
    assert proxy is not None
    expected = "Warning: NO_PROXY is ignored; every connection goes through the proxy.\n"
    assert stderr.getvalue() == (expected if warned else "")


@pytest.mark.parametrize("environ", [
    {"NO_PROXY": "*"},
    {"no_proxy": "*"},
    {"NO_PROXY": "*", "no_proxy": "*", "ALL_PROXY": "", "all_proxy": ""},
])
def test_no_proxy_without_proxy_is_silent(environ):
    stderr = io.StringIO()
    assert resolve_proxy(object(), None, None, environ, stderr) is None
    assert stderr.getvalue() == ""


@pytest.mark.parametrize("kwargs", [{}, {"tls": False}, {"tls": True}])
def test_stream_via(kwargs):
    reactor = object()
    proxy = SocksProxy("proxy.example", 1081, reactor)
    proxy_endpoint = object()
    stream_endpoint = object()
    with mock.patch("wormhole.socks_proxy.HostnameEndpoint",
                    return_value=proxy_endpoint) as hostname_endpoint:
        with mock.patch("wormhole.socks_proxy.txtorcon.socks.TorSocksEndpoint",
                        return_value=stream_endpoint) as socks_endpoint:
            endpoint = proxy.stream_via("target.example", 443, **kwargs)
    assert endpoint is stream_endpoint
    assert hostname_endpoint.mock_calls == [mock.call(reactor, "proxy.example", 1081)]
    assert socks_endpoint.mock_calls == [
        mock.call(proxy_endpoint, "target.example", 443, tls=kwargs.get("tls", False)),
    ]


class FakeTransport:
    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data

    def getHost(self):
        return object()

    def take_data(self):
        data, self.data = self.data, b""
        return data


@pytest.mark.parametrize("host, expected_request", [
    ("2002:4493:5105::a299:9bff:fe0e:4471",
     b"\x05\x01\x00\x04"
     b"\x20\x02\x44\x93\x51\x05\x00\x00\xa2\x99\x9b\xff\xfe\x0e\x44\x71"
     b"\x04\xd2"),
    ("target.example", b"\x05\x01\x00\x03\x0e" + b"target.example" + b"\x04\xd2"),
], ids=["ipv6_full_16_byte_address", "hostname_sent_to_proxy"])
def test_socks_connect_bytes(host, expected_request):
    class SocksServer(Protocol):
        def __init__(self):
            self.requests = []

        def dataReceived(self, data):
            self.requests.append(data)
            if len(self.requests) == 1:
                assert data == b"\x05\x01\x00"
                self.transport.write(b"\x05\x00")

    factory = txtorcon.socks._TorSocksFactory(host, 1234, "CONNECT", mock.Mock())
    client = factory.buildProtocol("ignored")
    server = SocksServer()
    client_transport = FakeTransport()
    server_transport = FakeTransport()
    server.makeConnection(server_transport)
    client.makeConnection(client_transport)
    server.dataReceived(client_transport.take_data())
    client.dataReceived(server_transport.take_data())
    server.dataReceived(client_transport.take_data())

    assert server.requests == [b"\x05\x01\x00", expected_request]
    if host.startswith("2002:"):
        assert len(server.requests[1]) == 22
