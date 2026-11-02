from twisted.internet import defer

from unittest import mock

import pytest
from pytest_twisted import ensureDeferred

from .. import xfer_util
from ..errors import UnsupportedProxyError


APPID = "appid"


@pytest.mark.parametrize("command", [xfer_util.send, xfer_util.receive])
@pytest.mark.parametrize("tor_options", [
    {"use_tor": True},
    {"launch_tor": True},
    {"tor_control_port": "tcp:localhost:9051"},
    {"tor_control_port": ""},
])
@ensureDeferred
async def test_proxy_tor_refused(command, tor_options):
    args = [None, APPID, "ws://localhost/v1"]
    if command is xfer_util.send:
        args.append("data")
    args.append("1-code")
    with (mock.patch.object(xfer_util.wormhole, "create") as create,
          mock.patch.object(xfer_util, "get_tor") as get_tor):
        with pytest.raises(UnsupportedProxyError) as exc:
            await command(*args, proxy=mock.sentinel.proxy, **tor_options)
        assert str(exc.value) == (
            "Tor options cannot be combined with a SOCKS proxy (--socks-host or ALL_PROXY). "
            "Unset ALL_PROXY to use Tor.")
        get_tor.assert_not_called()
        create.assert_not_called()


@pytest.mark.parametrize("command", [xfer_util.send, xfer_util.receive])
@ensureDeferred
async def test_proxy_forwarded(command):
    args = [None, APPID, "ws://localhost/v1"]
    if command is xfer_util.send:
        args.append("data")
        response = b'{"answer": {"message_ack": "ok"}}'
    else:
        response = b'{"offer": {"message": "data"}}'
    args.append("1-code")
    wh = mock.Mock()
    wh.get_message.return_value = defer.succeed(response)
    wh.close.return_value = defer.succeed(None)
    with (mock.patch.object(xfer_util.wormhole, "create", return_value=wh) as create,
          mock.patch.object(xfer_util, "get_tor") as get_tor):
        await command(*args, proxy=mock.sentinel.proxy)
        create.assert_called_once_with(
            APPID, "ws://localhost/v1", None, tor=None, proxy=mock.sentinel.proxy)
        get_tor.assert_not_called()


@ensureDeferred
async def test_xfer(reactor, mailbox):
    code = "1-code"
    data = "data"
    d1 = xfer_util.send(reactor, APPID, mailbox.url, data, code)
    d2 = xfer_util.receive(reactor, APPID, mailbox.url, code)
    send_result = await d1
    receive_result = await d2
    assert send_result is None
    assert receive_result == data


@ensureDeferred
async def test_on_code(reactor, mailbox):
    code = "1-code"
    data = "data"
    send_code = []
    receive_code = []
    d1 = xfer_util.send(
        reactor,
        APPID,
        mailbox.url,
        data,
        code,
        on_code=send_code.append)
    d2 = xfer_util.receive(
        reactor, APPID, mailbox.url, code, on_code=receive_code.append)
    send_result = await d1
    receive_result = await d2
    assert send_code == [code]
    assert receive_code == [code]
    assert send_result is None
    assert receive_result == data


@ensureDeferred
async def test_make_code(reactor, mailbox):
    data = "data"
    got_code = defer.Deferred()
    d1 = xfer_util.send(
        reactor,
        APPID,
        mailbox.url,
        data,
        code=None,
        on_code=got_code.callback)
    code = await got_code
    d2 = xfer_util.receive(reactor, APPID, mailbox.url, code)
    send_result = await d1
    receive_result = await d2
    assert send_result is None
    assert receive_result == data
