SOCKS5 proxy support
====================

Magic-Wormhole can send all connections through a SOCKS5 proxy. Use this
with ``wormhole send``, ``wormhole receive``, ``wormhole ssh invite`` or
``wormhole ssh accept``. Only proxies that need no authentication are
supported.

Choose a proxy
--------------

Set ``ALL_PROXY`` to use a proxy for a command:

::

   ALL_PROXY=socks5h://127.0.0.1:1080 wormhole send myfile.jpg

   ALL_PROXY=socks5h://127.0.0.1:1080 wormhole receive

The value must be ``socks5://host[:port]`` or ``socks5h://host[:port]``.
The scheme is case-insensitive. Put IPv6 hosts in brackets, for example
``socks5h://[::1]:1080``. The default port is 1080.

Both forms resolve destination hostnames at the proxy. No DNS lookup
leaves your machine for the mailbox server, transit relays or peer names.
The proxy's own hostname is looked up locally, so give an IP address if
that lookup must not happen either.

The lowercase variable ``all_proxy`` is also read. ``ALL_PROXY`` wins when
both are set. An empty value counts as unset.

Alternatively, choose a proxy with command-line options:

::

   wormhole send --socks-host 127.0.0.1 --socks-port 1080 myfile.jpg

   wormhole ssh invite --socks-host proxy.example.com

   wormhole ssh accept --socks-host proxy.example.com CODE

``--socks-host`` takes a bare hostname or IP address. For IPv6, leave out
the brackets. ``--socks-port`` must be between 1 and 65535 and requires
``--socks-host``. If you omit ``--socks-port``, the port is 1080.

The command-line options override the environment variable. When no
option is given, the environment variable still applies.

One way to get a local SOCKS5 proxy is to open an SSH dynamic forward:

::

   ssh -D 1080 user@gateway

Leave that SSH connection running, then use ``127.0.0.1:1080`` as the
proxy in another terminal.

What goes through the proxy
---------------------------

While a proxy is set, every connection goes through it. This includes the
mailbox server, also called the rendezvous server, the transit relay,
and every address the peer offers, including private, loopback and IPv6
addresses. Nothing falls back to a direct connection.

Wormhole opens no listening port and never sends its own IP addresses to
the peer. It only advertises the transit relay. The proxy must be able to
reach the mailbox server, and a transfer can work when the proxy can
reach the relay or one of the peer's addresses. If it cannot, the command
fails; it never retries directly. When both sides use a proxy, neither
advertises its own addresses, so the transfer goes through the relay.

``NO_PROXY`` and ``no_proxy`` are ignored. If either is set while a proxy
is active, wormhole prints one line:

::

   Warning: NO_PROXY is ignored; every connection goes through the proxy.

Refused settings
----------------

For the settings below, wormhole prints ``ERROR:`` followed by the
message and exits with status 1 before making any connection.

An unsupported scheme, for example ``ALL_PROXY=http://proxy.example.com``,
produces this error. The quoted scheme varies with the value:

::

   ERROR: Unsupported proxy scheme 'http'; unset ALL_PROXY/all_proxy or use --socks-host/--socks-port instead.

If you export an HTTP proxy for curl, wormhole stops until you unset it
for wormhole or choose a SOCKS5 proxy with the command-line options.

Any user or password in ``ALL_PROXY`` is refused:

::

   ERROR: Proxy credentials are not supported.

Do not combine a proxy with any of ``--tor``, ``--launch-tor`` or
``--tor-control-port``. Wormhole refuses the combination:

::

   ERROR: Tor options cannot be combined with a SOCKS proxy (--socks-host or ALL_PROXY). Unset ALL_PROXY to use Tor.

Unset both ``ALL_PROXY`` and ``all_proxy`` if they are set before using
Tor, and omit the SOCKS options.

Invalid command-line proxy options produce these errors:

::

   ERROR: --socks-port requires --socks-host.
   ERROR: --socks-host must not be empty.
   ERROR: --socks-host takes a bare hostname or IP address, without credentials, a scheme, a path or brackets.

A ``--socks-port`` outside 1 to 65535 is rejected by the option parser
with a usage error and exit status 2.

Other malformed ``ALL_PROXY`` values, including a path other than ``/``, a query, fragment,
missing host, bad port or whitespace, are refused with a message starting
``Proxy URL`` or ``Proxy port``, after the ``ERROR:`` prefix.

Limitations and API use
-----------------------

The proxy must answer a connect request with an IP address. A proxy that
answers with a domain name gives no usable connection and may fail with
an error. Common servers such as Dante answer with an address.

For API users, ``wormhole.create()`` accepts ``proxy=`` and refuses it
together with ``tor=``. Dilation, the newer connection layer used by some
API users, does not support a proxy. Calling
``wormhole.create(..., proxy=...)`` with dilation enabled raises
``UnsupportedProxyError`` with the message
``Dilation does not support a SOCKS proxy.`` The CLI's send, receive and
SSH commands do not use dilation.
