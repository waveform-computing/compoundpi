# vim: set et sw=4 sts=4 fileencoding=utf-8:

# Copyright 2014 Dave Hughes <dave@waveform.org.uk>.
#
# This file is part of compoundpi.
#
# compoundpi is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) any later
# version.
#
# compoundpi is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# compoundpi.  If not, see <http://www.gnu.org/licenses/>.

"Implements the client network interface"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
native_str = str
str = type('')
try:
    from itertools import izip as zip
except ImportError:
    pass

import sys
import re
import warnings
import datetime
import time
import random
import threading
import logging
import select
import struct
import socket
try:
    # Py2 compat
    import SocketServer as socketserver
except ImportError:
    import socketserver
import inspect
from functools import wraps, total_ordering
from fractions import Fraction
from collections import namedtuple
try:
    # Py2 compat
    from itertools import izip_longest as zip_longest
except ImportError:
    from itertools import zip_longest

from . import __version__
from .ipaddress import IPv4Address, IPv4Network
from .common import NetworkRepeater
from .protocol import CompoundPiProtocol
from .exc import (
    CompoundPiBadResponse,
    CompoundPiFutureResponse,
    CompoundPiHelloError,
    CompoundPiInvalidResponse,
    CompoundPiMissingResponse,
    CompoundPiMultiResponse,
    CompoundPiNoServers,
    CompoundPiRedefinedServer,
    CompoundPiSendTimeout,
    CompoundPiSendTruncated,
    CompoundPiServerError,
    CompoundPiStaleResponse,
    CompoundPiTransactionFailed,
    CompoundPiUndefinedServers,
    CompoundPiUnknownAddress,
    CompoundPiWrongPort,
    CompoundPiWrongVersion,
    )


class Resolution(namedtuple('Resolution', ('width', 'height'))):
    """
    Represents an image resolution.

    .. attribute:: width

        The width of the resolution as an integer value.

    .. attribute:: height

        The height of the resolution as an integer value.
    """
    __slots__ = ()

    def __str__(self):
        return '%dx%d' % (self.width, self.height)


class CompoundPiStatus(namedtuple('CompoundPiStatus', (
    'resolution',
    'framerate',
    'awb_mode',
    'awb_red',
    'awb_blue',
    'agc_mode',
    'agc_analog',
    'agc_digital',
    'exposure_mode',
    'exposure_speed',
    'iso',
    'metering_mode',
    'brightness',
    'contrast',
    'saturation',
    'ev',
    'hflip',
    'vflip',
    'denoise',
    'timestamp',
    'files',
    ))):
    """
    This class is a namedtuple derivative used to store the status of a
    Compound Pi server. It is recommended you access the information stored by
    this class by attribute name rather than position (for example:
    ``status.resolution`` rather than ``status[0]``).

    .. attribute:: resolution

        Returns the current resolution of the camera as a :class:`Resolution`
        tuple.

    .. attribute:: framerate

        Returns the current framerate of the camera as a
        :class:`~fractions.Fraction`.

    .. attribute:: awb_mode

        Returns the current white balance mode of the camera as a lower case
        string. See :meth:`CompoundPiClient.awb` for valid values.

    .. attribute:: awb_red

        Returns the current red gain of the camera's white balance as a
        floating point value. If :attr:`awb_mode` is ``'off'`` this is a fixed
        value. Otherwise, it is the current gain being used by the configured
        auto white balance mode.

    .. attribute:: awb_blue

        Returns the current blue gain of the camera's white balance as a
        floating point value. If :attr:`awb_mode` is ``'off'`` this is a fixed
        value. Otherwise, it is the current gain being used by the configured
        auto white balance mode.

    .. attribute:: agc_mode

        Returns the current auto-gain mode of the camera as a lower case
        string.  See :meth:`CompoundPiClient.agc` for valid values.

    .. attribute:: agc_analog

        Returns the current analog gain applied by the camera. If
        :attr:`agc_mode` is ``'off'`` this is a fixed (but uneditable) value.
        Otherwise, it is a value which varies according to the selected AGC
        algorithm.

    .. attribute:: agc_digital

        Returns the current digital gain used by the camera. If
        :attr:`agc_mode` is ``'off'`` this is a fixed (but uneditable) value.
        Otherwise, it is a value which varies according to the selected AGC
        algorithm.

    .. attribute:: exposure_mode

        Returns the current exposure mode of the camera as a lower case string.
        See :meth:`CompoundPiClient.exposure` for valid values.

    .. attribute:: exposure_speed

        Returns the current exposure speed of the camera as a floating point
        value measured in milliseconds.

    .. attribute:: iso

        Returns the camera's ISO setting as an integer value. This will be
        one of 0 (indicating automatic), 100, 200, 320, 400, 500, 640, or 800.

    .. attribute:: metering_mode

        Returns the camera's metering mode as a lower case string. See
        :meth:`CompoundPiClient.metering` for valid values.

    .. attribute:: brightness

        Returns the camera's brightness level as an integer value between 0
        and 100.

    .. attribute:: contrast

        Returns the camera's contrast level as an integer value between -100
        and 100.

    .. attribute:: saturation

        Returns the camera's saturation level as an integer value between -100
        and 100.

    .. attribute:: ev

        Returns the camera's exposure compensation value as an integer value
        measured in 1/6ths of a stop. Hence, 24 indicates the camera's
        compensation is +4 stops, while -12 indicates -2 stops.

    .. attribute:: hflip

        Returns a boolean value indicating whether the camera's orientation is
        horizontally flipped.

    .. attribute:: vflip

        Returns a boolean value indicating whether the camera's orientation is
        vertically flipped.

    .. attribute:: denoise

        Returns a boolean value indicating whether the camera's denoise
        algorithm is active when capturing.

    .. attribute:: timestamp

        Returns a :class:`~datetime.datetime` instance representing the time at
        which the server received the :ref:`protocol_status` message. Due to
        network latencies there is little point comparing this to the client's
        current timestamp. However, if the :ref:`protocol_status` message was
        broadcast to all servers, it can be useful to calculate the maximum
        difference in the server's timestamps to determine whether any servers
        have lost time sync.

    .. attribute:: files

        Returns an integer number indicating the number of files currently
        stored in the server's memory.
    """


class CompoundPiFile(namedtuple('CompoundPiFile', (
    'filetype',
    'index',
    'timestamp',
    'size',
    ))):
    """
    This class is a namedtuple derivative used to store information about an
    files stored in the memory of a Compound Pi server.  It is recommended you
    access the information stored by this class by attribute name rather than
    position (for example: ``f.size`` rather than ``f[3]``).

    .. attribute:: filetype

        Specifies what sort of file this is. Can be one of ``IMAGE``,
        ``VIDEO``, or ``MOTION``.

    .. attribute:: index

        Specifies the index of the file on the server. This is the index that
        should be passed to :meth:`CompoundPiClient.download` in order to
        retrieve this file.

    .. attribute:: timestamp

        Specifies the timestamp on the server at which the file was captured as
        a :class:`~datetime.datetime` instance.

    .. attribute:: size

        Specifies the size of the file as an integer number of bytes.
    """


def client(cls):
    """
    Decorator to convert CompoundPiProtocol into CompoundPiClientProtocol.

    The client decorator is relatively simple; for each declared handler method
    the body of the method is re-written to convert each argument according to
    its defined type, then format the resulting command and arguments into a
    command string which is returned.
    """
    def client_message(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            argspec = inspect.getargspec(fn)
            callargs = inspect.getcallargs(fn, *args, **kwargs)
            return '{command} {params}'.format(
                command=fn.command,
                params=','.join(
                    '' if value is None else str(value)
                    for arg, conv in zip(argspec.args[1:], fn.params)
                    for value in (None if callargs[arg] is None else conv(callargs[arg]),)
                    )
                ).rstrip()
        return wrapper

    for name, fn in cls.__mro__[1].__dict__.items():
        if hasattr(fn, 'command'):
            setattr(cls, name, client_message(fn))
    return cls


@client
class CompoundPiClientProtocol(CompoundPiProtocol):
    """
    Generator for Compound Pi protocol messages. This class is generated
    automatically from the description of the syntax in
    :mod:`compoundpi.protocol`. Methods are provided for each protocol message.
    When called with the appropriate arguments for the message (which are
    type-checked according to the protocol spec), each method will return the
    correctly formatted protocol message.
    """
    pass


@total_ordering
class CompoundPiServerList(object):
    """
    Manages the list of servers under the control of the client.

    The server list can be accessed via the :attr:`CompoundPiClient.servers`
    attribute. The list of defined servers can be manipulated with the familiar
    :meth:`append`, :meth:`remove`, and :meth:`extend` methods, and individual
    entries can be replaced by assigning to them or deleted with :keyword:`del`
    in the usual manner. The :meth:`find` method can be used to discover
    available servers on the subnet via broadcast.

    The list can be iterated over as usual, in reverse order with
    :func:`reversed`, and can be sorted with the :meth:`sort` method just like
    a normal list.

    Where the server list differs from a typical Python list is firstly that no
    duplicate addresses are permitted (in this manner, it is akin to a set).
    Secondly, while addresses can be added in string format, all addresses
    within the list will be converted to :class:`~ipaddress.IPv4Address`
    instances (which can be coerced back to strings for display purposes).

    Furthermore, a :meth:`move` method is provided to reposition existing
    addresses within the list. This is provided because adding new addresses to
    the list (via :meth:`append`, :meth:`extend`, or :meth:`find` implicitly
    causes a :ref:`protocol_hello` message to be transmitted to the new servers
    to ensure they are alive and understand the correct version of the network
    protocol), so removing then re-inserting existing entries to move them is
    inefficient, whilst re-inserting then removing isn't permitted due to the
    prevention of duplicates.

    You may also assign to the :attr:`CompoundPiClient.servers` attribute to
    re-order or completely redefine the list. Re-ordering in this case will be
    done efficiently.

    .. warning::

        Upon construction, the assumes the local network is 192.168.0.0/16.
        Because this class utilizes UDP broadcast packets, it is crucial that
        the network configuration (including the network mask) is set
        correctly. If the default network is wrong (which is most likely the
        case), you must correct it before issuing any commands. This can be
        done by setting the :attr:`network` attribute.

    The class assumes the servers are listening on UDP port 5647 by default.
    This can be altered via the :attr:`port` attribute.
    """
    def __init__(self, progress):
        self._protocol = CompoundPiClientProtocol()
        self._seqno = 0
        self._items = []
        self._senders = {}
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._progress = progress
        self.network = '192.168.0.0/16'
        self.port = 5647
        self.timeout = 15

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __reversed__(self):
        return reversed(self._items)

    def __contains__(self, address):
        try:
            self.index(address)
        except ValueError:
            return False
        else:
            return True

    def __getitem__(self, index):
        return self._items[index]

    def __setitem__(self, index, value):
        # XXX What about slice?
        if isinstance(index, slice):
            raise NotImplementedError
        self.remove(self._items[index])
        self.insert(index, value)

    def __delitem__(self, index):
        self.remove(self._items[index])

    def __le__(self, other):
        count = 0
        for count, (i, j) in enumerate(zip(self, other), start=1):
            if i < j:
                return True
            elif i > j:
                return False
        return count == len(self)

    def __eq__(self, other):
        for i, j in zip_longest(self, other):
            if i != j:
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def _get_port(self):
        return self._port
    def _set_port(self, value):
        self._port = int(value)
    port = property(_get_port, _set_port, doc="""
        Defines the server port that the client will broadcast to.

        This attribute defaults to 5647 meaning that the client will send
        broadcasts to Compound Pi servers which are assumed to be listening for
        messages on port 5647. If you have configured :ref:`cpid` differently,
        simply assign a different value to this attribute. For example::

            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.port = 8080

        .. note::

            The port of the client's bound socket (see
            :attr:`CompoundPiClient.bind` doesn't need to match the server's
            port. Both simply default to 5647 for the sake of simplicity.
        """)

    def _get_network(self):
        return self._network
    def _set_network(self, value):
        self._network = IPv4Network(value)
        self._items = []
    network = property(_get_network, _set_network, doc="""
        Defines the network that all servers belong to.

        This attribute defaults to ``192.168.0.0/16`` meaning that the client
        assumes all servers belong to the network beginning with ``192.168.``
        and accept broadcast packets with the address ``192.168.255.255``. If
        this is incorrect (which is likely the case), assign the correct
        network configuration as a string (in CIDR or network/mask notation) to
        this attribute. A common configuration is::

            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.0.0/24'

        Note that the network mask *must* be correct for broadcast packets to
        operate correctly. It is not enough for the network prefix alone to be
        correct.

        Querying this attribute will return a :class:`~ipaddress.IPv4Network`
        object which can be converted to a string, or enumerated to discover
        all potential addresses within the defined network.
        """)

    def _get_timeout(self):
        return self._timeout
    def _set_timeout(self, value):
        self._timeout = int(value)
    timeout = property(_get_timeout, _set_timeout, doc="""
        Defines the timeout for responses to commands.

        This attribute specifies the length of time that the client will wait
        for all servers to complete a command and return a response. If all
        servers have not replied within the specified number of seconds a
        :exc:`CompoundPiTransactionFailed` error will be raised.
        """)

    def index(self, address):
        if not isinstance(address, IPv4Address):
            address = IPv4Address(address)
        return self._items.index(address)

    def count(self, address):
        return int(address in self)

    def insert(self, index, address):
        """
        Called to explicitly add a server *address* to the client's list at the
        specified *index*.  Before the server is added, the client will send a
        :ref:`protocol_hello` to verify that the server is alive. You can query
        the servers in the client's list by treating the list as an iterable::

            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.0.0/24'
                client.servers.insert(0, '192.168.0.2')
                assert len(client.servers) == 1
                assert '192.168.0.2' in client.servers

        Attempting to add an address that is already present in the client's
        list will raise a :exc:`CompoundPiRedefinedServer` error.
        """
        if not isinstance(address, IPv4Address):
            address = IPv4Address(address)
        if address in self:
            raise CompoundPiRedefinedServer(address)
        self._seqno += 1
        data = '%d %s' % (self._seqno, self._protocol.do_hello(time.time()))
        self._send_command(
            (str(address), self.port), self._seqno, data)
        response = self._parse_ping(self._responses({address}))
        if not address in response:
            raise CompoundPiTransactionFailed([
                CompoundPiMissingResponse(address)
                ])
        self._items.insert(index, address)

    def append(self, address):
        """
        Called to explicitly add a server *address* to the client's list. This
        is equivalent to insertion at the end of the list::

            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.0.0/24'
                client.servers.append('192.168.0.2')
                assert len(client.servers) == 1
                assert '192.168.0.2' in client.servers

        Attempting to add an address that is already present in the client's
        list will raise a :exc:`CompoundPiRedefinedServer` error.
        """
        self.insert(len(self), address)

    def extend(self, addresses):
        """
        Called to add multiple servers to the client's list. The *addresses*
        parameter must be an iterable of addresses to add.
        """
        for address in addresses:
            self.append(address)

    def remove(self, address):
        """
        Called to explicitly remove a server *address* from the client's list.
        Nothing is sent to a server that is removed from the list. If the
        server is still active on the client's network after removal it will
        continue to receive broadcast packets but the client will ignore any
        responses from the server.

        .. warning::

            Please note that this may cause unexpected issues. For example,
            such a server (active but unknown to a client) may capture images
            in response to a broadcast :ref:`protocol_capture` message. For
            this reason it is recommended that you shut down any servers that
            you do not intend to communicate with. Future versions of the
            protocol may include explicit disconnection messages to mitigate
            this issue.

        Attempting to remove an address that is not present in the client's
        list will raise a :exc:`ValueError`.
        """
        if not isinstance(address, IPv4Address):
            address = IPv4Address(address)
        self._items.remove(address)

    def move(self, index, address):
        """
        Called to move *address* (which must already be present within the
        server list) to *index*. Positioning is as for :meth:`insert`; the
        specified *address* will be moved so that it occupies *index* and all
        later entries will be moved down.
        """
        self._items.insert(index, self._items.pop(self.index(address)))

    def reverse(self):
        """
        Reverses the order of the servers in the list.
        """
        self._items.reverse()

    def sort(self, key=None, reverse=False):
        """
        Sorts the servers in the list according to the specified *key*
        comparison function. If *reverse* is True, the order of the sort is
        reversed.
        """
        self._items.sort(key=key, reverse=reverse)

    def find(self, count=0):
        """
        Called to discover servers on the client's network. The :meth:`find`
        method broadcasts a :ref:`protocol_hello` message to the currently
        configured network. If called with no expected *count*, the method then
        waits for the network :attr:`timeout` (default 15 seconds) and adds all
        servers that replied to the broadcast to the client's list. If called
        with an expected *count* value, the method will terminate as soon as
        *count* servers have replied.

        .. note::

            If *count* servers don't reply, no exception will be raised.
            Therefore it is important to check the length of the list after
            calling :meth:`find`.

        For example::

            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.2.0/24'
                client.servers.find(10)
                assert len(client.servers) == 10
                print('Found 10 clients:')
                for addr in client.servers:
                    print(str(addr))

        This method or the :meth:`append` method are usually the first methods
        called after construction and configuration of the client instance.
        """
        self._items = []
        self._seqno += 1
        data = '%d %s' % (self._seqno, self._protocol.do_hello(time.time()))
        self._send_command(
            (str(self.network.broadcast_address), self.port), self._seqno, data)
        self._items = self._parse_ping(self._responses(count=count))

    def _parse_ping(self, responses):
        addresses = list(responses.keys())
        for address, (result, response) in responses.items():
            response = response.strip()
            if result == 'OK':
                if response != 'VERSION %s' % __version__:
                    warnings.warn(CompoundPiWrongVersion(address, response))
                    addresses.remove(address)
            else:
                warnings.warn(CompoundPiHelloError(address, response))
                addresses.remove(address)
        return addresses

    def _send_command(self, address, seqno, data):
        assert self._protocol.request_re.match(data)
        logging.debug('%s Tx %s', address, data)
        if isinstance(data, str):
            data = data.encode('utf-8')
        self._senders[(address, seqno)] = NetworkRepeater(
            self._socket, address, data)

    def _responses(self, servers=None, count=0):
        if servers is None:
            servers = self._items
        if not count:
            count = len(servers)
        if not servers:
            servers = self.network
            if not count:
                count = sum(1 for a in self.network)
        self._progress.start(count)
        result = {}
        start = time.time()
        try:
            while time.time() - start < self.timeout:
                self._progress.update(len(result))
                if select.select([self._socket], [], [], 1)[0]:
                    data, server_address = self._socket.recvfrom(512)
                    data = data.decode('utf-8')
                    logging.debug('%s Rx %s', server_address, data)
                    match = self._protocol.response_re.match(data)
                    address, port = server_address
                    address = IPv4Address(address)
                    if port != self.port:
                        warnings.warn(CompoundPiWrongPort(address, port))
                    elif address in result:
                        warnings.warn(CompoundPiMultiResponse(address))
                    elif address not in servers:
                        warnings.warn(CompoundPiUnknownAddress(address))
                    elif not match:
                        warnings.warn(CompoundPiBadResponse(address))
                    else:
                        seqno = int(match.group('seqno'))
                        # Unconditionally send an ACK to silence the responder
                        # of whatever server sent the message
                        ack_msg = ('%d ACK' % seqno).encode('utf-8')
                        self._socket.sendto(ack_msg, server_address)
                        # Silence the sender that the response corresponds
                        # to (if any)
                        sender = self._senders.get((server_address, seqno))
                        if sender:
                            sender.terminate = True
                            # We deliberately don't join() the sender here
                            # to ensure we don't delay receiving the next
                            # response
                        if seqno < self._seqno:
                            warnings.warn(CompoundPiStaleResponse(address))
                        elif seqno > self._seqno:
                            warnings.warn(CompoundPiFutureResponse(address))
                        else:
                            result[address] = (
                                    match.group('result'),
                                    match.group('data'),
                                    )
                            if len(result) == count:
                                break
            self._progress.update(len(result))
            return result
        finally:
            while self._senders:
                _, sender = self._senders.popitem()
                sender.terminate = True
                sender.join()
            self._progress.finish()

    def transact(self, data, addresses=None):
        if addresses is None:
            if not self._items:
                raise CompoundPiNoServers()
            addresses = set(self._items)
        else:
            addresses = set(
                addr if isinstance(addr, IPv4Address) else IPv4Address(addr)
                for addr in addresses
                )
            if addresses - set(self._items):
                raise CompoundPiUndefinedServers(addresses - set(self._items))
        errors = []
        self._seqno += 1
        data = '%d %s' % (self._seqno, data)
        if addresses == set(self._items):
            self._send_command(
                (str(self.network.broadcast_address), self.port), self._seqno, data)
        else:
            for address in addresses:
                self._send_command(
                    (str(address), self.port), self._seqno, data)
        responses = self._responses(addresses)
        for address in addresses:
            try:
                result, response = responses[address]
            except KeyError:
                errors.append(CompoundPiMissingResponse(address))
            else:
                responses[address] = response
                if result == 'ERROR':
                    errors.append(CompoundPiServerError(address, response))
                elif result != 'OK':
                    errors.append(CompoundPiInvalidResponse(address))
        if errors:
            raise CompoundPiTransactionFailed(errors)
        return responses


class CompoundPiProgressHandler(object):
    """
    Progress handler class for the Compound Pi client. This class is used by
    Compound Pi to "mock out" any progress handler methods missing from the
    user's specified progress handler object for the purpose of keeping the
    client code simple. There is generally no need for end users to utilise
    this class.
    """
    def __init__(self, handler=None):
        if handler is not None:
            if hasattr(handler, 'start'):
                self.start = handler.start
            if hasattr(handler, 'update'):
                self.update = handler.update
            if hasattr(handler, 'finish'):
                self.finish = handler.finish

    def start(self, count):
        logging.debug('progress.start fallback called')

    def update(self, count):
        logging.debug('progress.update fallback called')

    def finish(self):
        logging.debug('progress.finish fallback called')


class CompoundPiClient(object):
    """
    Implements a network client for Compound Pi servers.

    The optional *progress* parameter provides an object which will be notified
    of long client operations. When the client begins a long operation it will
    call the ``start`` method of the object with a single parameter indicating
    the number of expected operations to complete. As the operation progresses,
    the object's ``update`` method will be called with a parameter indicating
    the current operation (the ``update`` method may be called multiple times
    with the same number, but it will never decrease within the span of one
    operation, and it will never exceed the count passed to ``start``). To
    terminate a long operation prematurely, :keyword:`raise` an exception in
    the ``update`` method. Finally, the object's ``finish`` routine will be
    called with no parameters (if the ``start`` method is called, the
    ``finish`` method is guaranteed to be called).

    Before controlling any Compound Pi servers, the client must either be told
    the addresses of the servers, or discover them via broadcast. The
    :attr:`servers` attribute is the list of available servers. Servers can be
    defined manually, or discovered by broadcast. See the
    :class:`CompoundPiServerList` documentation for further information.

    Various methods are provided for configuring and controlling the cameras on
    the Compound Pi servers (:meth:`resolution`, :meth:`framerate`,
    :meth:`exposure`, :meth:`capture`, etc). Each method optionally accepts a
    set of addresses to operate on. If omitted, the command is applied to all
    servers that the client knows about (via a broadcast packet).

    The one exception to this is the :meth:`download` method for retrieving
    captured images. For the sake of efficiency this is expected to operate
    against one server at a time, so the *address* parameter is mandatory.  The
    class listens on port 5647 on all available interfaces for download
    transmissions. If this is incorrect (or if you wish to limit the interfaces
    that the client listens on), adjust the :attr:`bind` attribute.

    When you are finished with the client, you must call the :meth:`close`
    method which shuts down the listening socket and server thread. Failure
    to do so will likely cause your application or script to hang (the server
    thread is deliberately not marked as a daemon thread, so your script will
    not terminate while it is still active). For example::

        from compoundpi.client import CompoundPiClient

        client = CompoundPiClient()
        try:
            client.servers.find(10)
            client.capture()
        finally:
            client.close()

    The client class can be used as a context handler to ensure this happens
    implicitly::

        from compoundpi.client import CompoundPiClient

        with CompoundPiClient() as client:
            client.servers.find(10)
            client.capture()
    """

    def __init__(self, progress=None):
        self._protocol = CompoundPiClientProtocol()
        self._server = None
        self._server_thread = None
        self._servers = CompoundPiServerList(CompoundPiProgressHandler(progress))
        self.bind = ('0.0.0.0', 5647)

    def close(self):
        self.servers = []
        self.bind = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    def _get_servers(self):
        return self._servers
    def _set_servers(self, value):
        value = [
                a if isinstance(a, IPv4Address) else IPv4Address(a)
                for a in value
                ]
        added = set(value) - set(self._servers)
        for address in added:
            self._servers.append(address)
        removed = set(self._servers) - set(value)
        for address in removed:
            self._servers.remove(address)
        if len(value) != len(self._servers):
            raise ValueError('duplicate addresses in servers')
        for index, address in value:
            self._servers.move(index, address)
    servers = property(_get_servers, _set_servers)

    def _get_bind(self):
        if self._server:
            return self._server.socket.getsockname()
    def _set_bind(self, value):
        if self._server:
            self._server.shutdown()
            self._server.socket.close()
            self._server_thread = None
            self._server = None
        if value is not None:
            self._server = CompoundPiDownloadServer(value, CompoundPiDownloadHandler)
            self._server.event = threading.Event()
            self._server.source = None
            self._server.output = None
            self._server.exception = None
            self._server.progress = self._servers._progress
            self._server_thread = threading.Thread(target=self._server.serve_forever)
            self._server_thread.start()
    bind = property(_get_bind, _set_bind, doc="""
        Defines the port and interfaces the client will listen to for
        responses.

        This attribute defaults to ``('0.0.0.0', 5647)`` meaning that the
        client defaults to listening on port 5647 on all available network
        interfaces for responses from Compound Pi servers (the special address
        ``0.0.0.0`` means "all available interfaces"). If you wish to change
        the port, or limit the interfaces the client listens to, assign a tuple
        of ``(address, port)`` to this attribute. For example::

            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.bind = ('192.168.0.1', 8000)

        Querying this attribute will return a 2-tuple of the current address
        and port that the client is listening on.

        .. note::

            The port of the client's bound socket doesn't need to match the
            server's port. Both simply default to 5647 for the sake of
            simplicity.
        """)

    status_re = re.compile(
            r'RESOLUTION (?P<width>\d+),(?P<height>\d+)\n'
            r'FRAMERATE (?P<rate>\d+(/\d+)?)\n'
            r'AWB (?P<awb_mode>[a-z]+),(?P<awb_red>\d+(/\d+)?),(?P<awb_blue>\d+(/\d+)?)\n'
            r'AGC (?P<agc_mode>[a-z]+),(?P<agc_analog>\d+(/\d+)?),(?P<agc_digital>\d+(/\d+)?)\n'
            r'EXPOSURE (?P<exp_mode>[a-z]+),(?P<exp_speed>\d+(\.\d+)?)\n'
            r'ISO (?P<iso>\d+)\n'
            r'METERING (?P<metering_mode>[a-z]+)\n'
            r'BRIGHTNESS (?P<brightness>\d+)\n'
            r'CONTRAST (?P<contrast>-?\d+)\n'
            r'SATURATION (?P<saturation>-?\d+)\n'
            r'EV (?P<ev>-?\d+)\n'
            r'FLIP (?P<hflip>0|1),(?P<vflip>0|1)\n'
            r'DENOISE (?P<denoise>0|1)\n'
            r'TIMESTAMP (?P<time>\d+(\.\d+)?)\n'
            r'FILES (?P<files>\d{,3})\n')
    def status(self, addresses=None):
        """
        Called to determine the status of servers. The :meth:`status` method
        queries all servers at the specified *addresses* (or all defined
        servers if *addresses* is omitted) for their camera configurations. It
        returns a mapping of address to :class:`CompoundPiStatus` named tuples.
        For example::

            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.0.0/24'
                client.servers.find(10)
                print('Configured resolutions:')
                for address, status in client.status().items():
                    print('%s: %dx%d' % (
                        address,
                        status.resolution.width,
                        status.resolution.height,
                        ))
        """
        responses = [
            (address, self.status_re.match(data))
            for (address, data) in self.servers.transact(
                self._protocol.do_status(), addresses).items()
            ]
        errors = []
        result = {}
        for address, match in responses:
            if match is None:
                errors.append(CompoundPiInvalidResponse(address))
            else:
                result[address] = CompoundPiStatus(
                    resolution=Resolution(int(match.group('width')), int(match.group('height'))),
                    framerate=Fraction(match.group('rate')),
                    awb_mode=match.group('awb_mode'),
                    awb_red=Fraction(match.group('awb_red')),
                    awb_blue=Fraction(match.group('awb_blue')),
                    agc_mode=match.group('agc_mode'),
                    agc_analog=Fraction(match.group('agc_analog')),
                    agc_digital=Fraction(match.group('agc_digital')),
                    exposure_mode=match.group('exp_mode'),
                    exposure_speed=float(match.group('exp_speed')),
                    ev=int(match.group('ev')),
                    iso=int(match.group('iso')),
                    metering_mode=match.group('metering_mode'),
                    brightness=int(match.group('brightness')),
                    contrast=int(match.group('contrast')),
                    saturation=int(match.group('saturation')),
                    hflip=bool(int(match.group('hflip'))),
                    vflip=bool(int(match.group('vflip'))),
                    denoise=bool(int(match.group('denoise'))),
                    timestamp=datetime.datetime.fromtimestamp(float(match.group('time'))),
                    files=int(match.group('files')),
                    )
        if errors:
            raise CompoundPiTransactionFailed(
                errors, '%d invalid status responses' % len(errors))
        return result

    def resolution(self, width, height, addresses=None):
        """
        Called to change the camera resolution on the servers at the specified
        *addresses* (or all defined servers if *addresses* is omitted). The
        *width* and *height* parameters are integers defining the new
        resolution. For example::

            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.0.0/24'
                client.servers.find(10)
                client.resolution(1280, 720)
        """
        self.servers.transact(
                self._protocol.do_resolution(width, height), addresses)

    def framerate(self, rate, addresses=None):
        """
        Called to change the camera framerate on the servers at the specified
        *addresses* (or all defined servers if *addresses* is omitted). The
        *rate* parameter is the new framerate specified as a numeric value
        (e.g. :func:`int`, :func:`float` or :class:`~fractions.Fraction`).
        For example::

            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.0.0/24'
                client.servers.find(10)
                client.framerate(24)
        """
        self.servers.transact(self._protocol.do_framerate(rate), addresses)

    def awb(self, mode, red=0.0, blue=0.0, addresses=None):
        """
        Called to change the white balance on the servers at the specified
        *addresses* (or all defined servers if *addresses* is omitted). The
        *mode* parameter specifies the new white balance mode as a string.
        Valid values are:

        * ``'auto'``
        * ``'cloudy'``
        * ``'flash'``
        * ``'fluorescent'``
        * ``'horizon'``
        * ``'incandescent'``
        * ``'off'``
        * ``'shade'``
        * ``'sunlight'``
        * ``'tungsten'``

        If the special value ``'off'`` is given as the *mode*, the *red* and
        *blue* parameters specify the red and blue gains of the camera manually
        as floating point values between 0.0 and 8.0. Reasonable values for red
        and blue gains can be discovered easily by setting *mode* to
        ``'auto'``, waiting a while to let the camera settle, then querying the
        current gain by calling :meth:`status`.  For example::

            from time import sleep
            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.0.0/24'
                client.servers.find(10)
                # Pick an arbitrary camera to determine white balance gains and
                # set it auto white balance
                addr = client.servers[0]
                client.awb('auto', addresses=addr)
                # Wait a few seconds to let the camera measure the scene
                sleep(2)
                # Query the camera's gains and fix all cameras gains accordingly
                status = client.status(addresses=addr)[addr]
                client.awb('off', status.awb_red, status.awb_blue)
        """
        self.servers.transact(
            self._protocol.do_awb(mode, red, blue), addresses)

    def agc(self, mode, addresses=None):
        """
        Called to change the automatic gain control on the servers at the
        specified *addresses* (or all defined servers if *addresses* is
        omitted).  The *mode* parameter specifies the new exposure mode as a
        string. Valid values are:

        * ``'antishake'``
        * ``'auto'``
        * ``'backlight'``
        * ``'beach'``
        * ``'fireworks'``
        * ``'fixedfps'``
        * ``'night'``
        * ``'nightpreview'``
        * ``'off'``
        * ``'snow'``
        * ``'sports'``
        * ``'spotlight'``
        * ``'verylong'``

        .. note::

            When *mode* is set to ``'off'`` the analog and digital gains
            reported by :meth:`status` will become fixed. Any other mode causes
            them to vary according to the selected algorithm. Unfortunately, at
            present, the camera firmware provides no means for forcing the
            gains to a particular value (in contrast to AWB and exposure
            speed).
        """
        self.servers.transact(self._protocol.do_agc(mode), addresses)

    def exposure(self, mode, speed=0, addresses=None):
        """
        Called to change the exposure on the servers at the specified
        *addresses* (or all defined servers if *addresses* is omitted). The
        *mode* parameter specifies the new exposure mode as a string.  Valid
        values are:

        * ``'auto'``
        * ``'off'``

        The *speed* parameter specifies the exposure speed manually as a
        floating point value measured in milliseconds. Reasonable exposure
        speeds can be discovered easily by setting *mode* to ``'auto'``,
        waiting a while to let the camera settle, then querying the current
        speed by calling :meth:`status`.  For example::

            from time import sleep
            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.0.0/24'
                client.servers.find(10)
                # Pick an arbitrary camera to determine exposure speed and set it
                # to auto
                addr = client.servers[0]
                client.exposure('auto', addresses=addr)
                # Wait a few seconds to let the camera measure the scene
                sleep(2)
                # Query the camera's exposure speed and fix all cameras accordingly
                status = client.status(addresses=addr)[addr]
                client.exposure('off', speed=status.exposure_speed)
        """
        self.servers.transact(
            self._protocol.do_exposure(mode, speed), addresses)

    def metering(self, mode, addresses=None):
        """
        Called to change the metering algorithm on the servers at the specified
        *addresses* (or all defined servers if *addresses* is omitted). The
        *mode* parameter specifies the new metering mode as a string.  Valid
        values are:

        * ``'average'``
        * ``'backlit'``
        * ``'matrix'``
        * ``'spot'``
        """
        self.servers.transact(self._protocol.do_metering(mode), addresses)

    def iso(self, value, addresses=None):
        """
        Called to change the ISO setting on the servers at the specified
        *addresses* (or all defined servers if *addresses* is omitted). The
        *mode* parameter specifies the new ISO settings as an integer value.
        values are 0 (meaning auto), 100, 200, 320, 400, 500, 640, and 800.
        """
        self.servers.transact(self._protocol.do_iso(value), addresses)

    def brightness(self, value, addresses=None):
        """
        Called to change the brightness level on the servers at the specified
        *addresses* (or all defined servers if *addresses* is omitted). The
        new level is specified an integer between 0 and 100.
        """
        self.servers.transact(self._protocol.do_brightness(value), addresses)

    def contrast(self, value, addresses=None):
        """
        Called to change the contrast level on the servers at the specified
        *addresses* (or all defined servers if *addresses* is omitted). The
        new level is specified an integer between -100 and 100.
        """
        self.servers.transact(self._protocol.do_contrast(value), addresses)

    def saturation(self, value, addresses=None):
        """
        Called to change the saturation level on the servers at the specified
        *addresses* (or all defined servers if *addresses* is omitted). The
        new level is specified an integer between -100 and 100.
        """
        self.servers.transact(self._protocol.do_saturation(value), addresses)

    def ev(self, value, addresses=None):
        """
        Called to change the exposure compensation (EV) level on the servers at
        the specified *addresses* (or all defined servers if *addresses* is
        omitted). The new level is specified an integer between -24 and 24
        where each increment represents 1/6th of a stop.
        """
        self.servers.transact(self._protocol.do_ev(value), addresses)

    def flip(self, horizontal, vertical, addresses=None):
        """
        Called to change the orientation of the servers at the specified
        *addresses* (or all defined servers if *addresses* is omitted). The
        *horizontal* and *vertical* parameters are boolean values indicating
        whether to flip the camera's output along the corresponding axis. The
        default for both parameters is ``False``.
        """
        self.servers.transact(
            self._protocol.do_flip(horizontal, vertical), addresses)

    def denoise(self, value, addresses=None):
        """
        Called to change whether the firmware's denoise algorithm is active on
        the servers at the specified *addresses* (or all defined servers if
        *addresses* is omitted). The *value* is a simple boolean, which
        defaults to ``True``.
        """
        self.servers.transact(self._protocol.do_denoise(value), addresses)

    def capture(self, count=1, video_port=False, quality=None, delay=None,
            addresses=None):
        """
        Called to capture images on the servers at the specified *addresses*
        (or all defined servers if *addresses* is omitted). The optional
        *count* parameter is an integer value defining how many sequential
        images to capture, which defaults to 1. The optional *video_port*
        parameter defaults to ``False`` which indicates that the camera's slow,
        but high quality still port should be used for capture. If set to
        ``True``, the faster, lower quality video port will be used instead.
        This is particularly useful with *count* greater than 1 for capturing
        high motion scenes.

        The optional *delay* parameter defaults to ``None`` which indicates
        that all servers should capture images immediately upon receipt of the
        :ref:`protocol_capture` message. When using broadcast messages (when
        *addresses* is omitted) this typically results in near simultaneous
        captures, especially with fast, low latency networks like ethernet.

        If *delay* is set to a small floating point value measured in seconds,
        it indicates that the servers should synchronize their captures to a
        timestamp (the client calculates the timestamp as *now* + *delay*
        seconds). This functionality assumes that the servers all have accurate
        clocks which are reasonably in sync with the client's clock; a typical
        configuration is to run an NTP server on the client machine, and an NTP
        client on each of the Compound Pi servers.

        .. note::

            Note that this method merely causes the servers to capture images.
            The captured images are stored in RAM on the servers for later
            retrieval with the :meth:`download` method.
        """
        if delay:
            delay = time.time() + delay
        else:
            delay = None
        self.servers.transact(
            self._protocol.do_capture(count, video_port, quality, delay),
            addresses)

    def record(self, length, format='h264', quality=None, bitrate=None,
            intra_period=None, motion_output=False, delay=None,
            addresses=None):
        """
        Called to record video on the servers at the specified *addresses* (or
        all defined servers if *addresses* is omitted). The *length* parameter
        specifies the time (in seconds) to record for. This may be a decimal
        value. The optional *format* parameter specifies the video codec to
        use. This defaults to ``'h264'`` but may also be set to ``'mjpeg'``.

        The optional *quality* parameter specifies the quality that the codec
        will attempt to maintain. This is an integer value between 1 and 40 for
        ``h264`` (lower values are better), or an integer value between 1 and
        100 for ``mjpeg`` (higher values are better). The default provides
        "good" quality. The optional *bitrate* parameter specifies the limit
        of data that the codec is allowed to produce. The default is extremely
        high to ensure bitrate limiting never occurs by default.

        The optional *intra_period* parameter is only valid with the ``h264``
        format and specifies the number of frames in a GOP (group of pictures).
        As a GOP always starts with a keyframe (I-frame) this effectively
        dictates how regularly keyframes occurs in the output. The default is
        30 frames.

        The optional *motion_output* parameter is only valid with the ``h264``
        format and specifies that you wish to capture motion vector estimation
        data as well as video data. This will be stored in a separate file on
        the Compound Pi server.

        The optional *delay* parameter defaults to ``None`` which indicates
        that all servers should record video immediately upon receipt of the
        :ref:`protocol_capture` message. When using broadcast messages (when
        *addresses* is omitted) this typically results in near simultaneous
        recording, especially with fast, low latency networks like ethernet.

        .. note::

            Note that this method merely causes the servers to record video.
            The captured video is stored in RAM on the servers for later
            retrieval with the :meth:`download` method.
        """
        if delay:
            delay = time.time() + delay
        else:
            delay = None
        self.servers.transact(
            self._protocol.do_record(
                length, format, quality, bitrate, intra_period,
                motion_output, delay),
            addresses)

    list_line_re = re.compile(
            r'(?P<filetype>IMAGE|VIDEO|MOTION),'
            r'(?P<index>\d+),'
            r'(?P<time>\d+(\.\d+)?),'
            r'(?P<size>\d+)')
    def list(self, addresses=None):
        """
        Called to list files available for download from the servers at the
        specified *addresses* (or all defined servers if *addresses* is
        omitted). The method returns a mapping of address to sequences of
        :class:`CompoundPiFile` which provide the index, capture timestamp,
        and size of each image available on the server. For example, to
        enumerate the total size of all files stored on all servers::

            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.0.0/24'
                client.servers.find(10)
                client.capture()
                size = sum(
                    f.size
                    for addr, files in client.list().items()
                    for f in files
                    )
                print('%d bytes available for download' % size)
        """
        responses = {
            address: [
                self.list_line_re.match(line)
                for line in data.splitlines()
                ]
            for (address, data) in self.servers.transact(
                self._protocol.do_list(), addresses).items()
            }
        errors = []
        result = {}
        for address, matches in responses.items():
            result[address] = []
            for match in matches:
                if match is None:
                    errors.append(CompoundPiInvalidResponse(address))
                else:
                    result[address].append(CompoundPiFile(
                        match.group('filetype'),
                        int(match.group('index')),
                        datetime.datetime.fromtimestamp(float(match.group('time'))),
                        int(match.group('size')),
                        ))
        if errors:
            raise CompoundPiTransactionFailed(
                errors, '%d invalid lines in responses' % len(errors))
        return result

    def clear(self, addresses=None):
        """
        Called to clear captured files from the RAM of the servers at the
        specified *addresses* (or all defined servers if *addresses* is
        omitted). Currently the protocol for the :ref:`protocol_clear` message
        is fairly crude: it simply clears all captured files on the server;
        there is no method for specifying a subset of files to wipe.
        """
        self.servers.transact(self._protocol.do_clear(), addresses)

    def identify(self, addresses=None):
        """
        Called to cause the servers at the specified *addresses* to physically
        identify themselves (or all defined servers if *addresses* is omitted).
        Currently, the identification takes the form of the server blinking
        the camera's LED for 5 seconds.
        """
        self.servers.transact(self._protocol.do_blink(), addresses)

    def download(self, address, index, output):
        """
        Called to download the image with the specified *index* from the server
        at *address*, writing the content to the file-like object provided by
        the *output* parameter.

        The :meth:`download` method differs from all other client methods in
        that it targets a single server at a time (attempting to simultaneously
        download files from multiple servers would be extremely inefficient).
        The available image indices can be determined by calling the
        :meth:`list` method beforehand. Note that downloading files from
        servers does *not* wipe the file from the server's RAM. Once all files
        have been successfully retrieved, you should use the :meth:`clear`
        method to free up memory on the servers. For example::

            import io
            from compoundpi.client import CompoundPiClient

            with CompoundPiClient() as client:
                client.servers.network = '192.168.0.0/24'
                # Capture an image on all servers
                client.capture()
                # Download all available files from all servers
                for addr, files in client.list().items():
                    for f in files:
                        print('Downloading image %d from %s (%d bytes)' % (
                            f.index,
                            addr,
                            f.size,
                            ))
                        with io.open('%s-%d.jpg' % (addr, f.index)) as f:
                            client.download(addr, f.index, f)
                # Wipe all files on all servers
                client.clear()
        """
        self._server.source = address
        self._server.output = output
        self._server.event.clear()
        # As download is a long operation that always targets a single server,
        # we re-purpose progress notifications from counting server responses
        # to counting bytes received
        save_progress = self._servers._progress
        self._servers._progress = CompoundPiProgressHandler()
        try:
            self.servers.transact(
                self._protocol.do_send(index, self.bind[1]), [address])
            if not self._server.event.wait(self.servers.timeout):
                raise CompoundPiSendTimeout(address)
            elif self._server.exception:
                raise self._server.exception
        finally:
            self._server.source = None
            self._server.output = None
            self._server.exception = None
            self._servers._progress = save_progress


class CompoundPiDownloadHandler(socketserver.StreamRequestHandler):
    def handle(self):
        if self.client_address[0] != str(self.server.source):
            warnings.warn(CompoundPiUnknownAddress(self.client_address[0]))
        else:
            size, = struct.unpack(
                native_str('>L'),
                self.rfile.read(struct.calcsize(native_str('>L'))))
            self.server.output.truncate(size)
            self.server.output.seek(0)
            self.server.progress.start(size)
            try:
                while self.server.output.tell() < size:
                    data = self.rfile.read(16384)
                    if not data:
                        raise CompoundPiSendTruncated(self.server.source)
                    self.server.output.write(data)
                    self.server.progress.update(self.server.output.tell())
            except Exception as e:
                self.server.exception = e
            else:
                self.server.exception = None
            finally:
                self.server.progress.finish()
                self.server.event.set()


class CompoundPiDownloadServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

