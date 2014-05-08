# vim: set et sw=4 sts=4 fileencoding=utf-8:

# Copyright 2014 Dave Hughes <dave@waveform.org.uk>.
#
# This file is part of compoundpi.
#
# compoundpi is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# compoundpi is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# compoundpi.  If not, see <http://www.gnu.org/licenses/>.

"Implements the client terminal interface"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')
range = xrange

import sys
import re
import warnings
import datetime
import fractions
import time
import threading
import select
import struct
import socket
import SocketServer as socketserver
from collections import namedtuple
try:
    from ipaddress import IPv4Address, IPv4Network
except ImportError:
    from ipaddr import IPv4Address, IPv4Network

from . import __version__


class CompoundPiWarning(Warning):
    "Base class for warnings raised by the Compound Pi client"


class CompoundPiServerWarning(CompoundPiWarning):
    "Warning raised when a Compound Pi server does something unexpected"

    def __init__(self, address, msg):
        super(CompoundPiServerWarning, self).__init__(
            '%s: %s' % (address, msg))
        self.address = address


class CompoundPiWrongPort(CompoundPiServerWarning):
    "Warning raised when packets are received from the wrong port"

    def __init__(self, address, port):
        super(CompoundPiWrongPort, self).__init__(
                address, 'response from wrong port %d' % port)


class CompoundPiUnknownAddress(CompoundPiServerWarning):
    "Warning raised when a packet is received from an unexpected address"

    def __init__(self, address):
        super(CompoundPiUnknownAddress, self).__init__(
            address, 'unknown server')


class CompoundPiMultiResponse(CompoundPiServerWarning):
    "Warning raised when multiple responses are received"

    def __init__(self, address):
        super(CompoundPiMultiResponse, self).__init__(
            address, 'multiple responses received')


class CompoundPiBadResponse(CompoundPiServerWarning):
    "Warning raised when a response is badly formed"

    def __init__(self, address):
        super(CompoundPiBadResponse, self).__init__(
            address, 'badly formed response')


class CompoundPiStaleResponse(CompoundPiServerWarning):
    "Warning raised when a stale response (old sequence number) is received"

    def __init__(self, address):
        super(CompoundPiStaleResponse, self).__init__(
            address, 'stale response')


class CompoundPiFutureResponse(CompoundPiServerWarning):
    "Warning raised when a response with a future sequence number is received"

    def __init__(self, address):
        super(CompoundPiFutureResponse, self).__init__(
            address, 'future response')


class CompoundPiWrongVersion(CompoundPiServerWarning):
    "Warning raised when a server reports an incompatible version"

    def __init__(self, address, version):
        super(CompoundPiWrongVersion, self).__init__(
            address, 'wrong version "%s"' % version)
        self.version = version


class CompoundPiPingError(CompoundPiServerWarning):
    "Warning raised when a server reports an error in response to PING"

    def __init__(self, address, error):
        super(CompoundPiPingError, self).__init__(address, error)
        self.error = error


class CompoundPiError(Exception):
    "Base class for errors raised by the Compound Pi client"


class CompoundPiNoServers(CompoundPiError):
    "Exception raised when a command is execute with no servers defined"

    def __init__(self):
        super(CompoundPiNoServers, self).__init__('no servers defined')


class CompoundPiUndefinedServers(CompoundPiError):
    "Exception raised when a transaction is attempted with undefined servers"

    def __init__(self, addresses):
        super(CompoundPiUndefinedServers, self).__init__(
                'transaction with undefined servers: %s' %
                ','.join(str(addr) for addr in addresses))


class CompoundPiServerError(CompoundPiError):
    "Exception raised when a Compound Pi server reports an error"

    def __init__(self, address, msg):
        super(CompoundPiServerError, self).__init__('%s: %s' % (address, msg))
        self.address = address


class CompoundPiInvalidResponse(CompoundPiServerError):
    "Exception raised when a server returns an unexpected response"

    def __init__(self, address):
        super(CompoundPiInvalidResponse, self).__init__(
                address, 'invalid response')


class CompoundPiMissingResponse(CompoundPiServerError):
    "Exception raised when a server fails to return a response"

    def __init__(self, address):
        super(CompoundPiMissingResponse, self).__init__(
                address, 'no response')


class CompoundPiSendTimeout(CompoundPiServerError):
    "Exception raised when a server fails to open a connection for SEND"

    def __init__(self, address):
        super(CompoundPiSendTimeout, self).__init__(
                address, 'timed out waiting for SEND connection')


class CompoundPiTransactionFailed(CompoundPiError):
    "Compound exception which represents all errors encountered in a transaction"

    def __init__(self, errors, msg=None):
        if msg is None:
            msg = '%d errors encountered while executing' % len(errors)
        msg = '\n'.join([msg] + [str(e) for e in errors])
        super(CompoundPiTransactionFailed, self).__init__(msg)
        self.errors = errors


CompoundPiStatus = namedtuple('CompoundPiStatus', (
    'resolution',
    'framerate',
    'timestamp',
    'images',
    ))


CompoundPiListItem = namedtuple('CompoundPiListItem', (
    'index',
    'timestamp',
    'size',
    ))


class CompoundPiClient(object):

    request_re = re.compile(
            r'(?P<seqno>\d+) '
            r'(?P<command>[A-Z]+)( (?P<params>.*))?')
    response_re = re.compile(
            r'(?P<seqno>\d+) '
            r'(?P<result>OK|ERROR)(\n(?P<data>.*))?', flags=re.DOTALL)

    def __init__(self, progress=None):
        self._seqno = 0
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._server = None
        self._server_thread = None
        self._servers = set()
        self._progress_start = self._progress_update = self._progress_finish = None
        if progress is not None:
            (
                self._progress_start,
                self._progress_update,
                self._progress_finish,
                ) = progress
        self.network = '192.168.0.0/16'
        self.port = 5647
        self.bind = ('0.0.0.0', 5647)
        self.timeout = 5

    def _get_bind(self):
        if self._server:
            return self._server.socket.getsockname()
    def _set_bind(self, value):
        if self._server:
            self._server.shutdown()
            self._server.socket.close()
            self._server_thread = None
        if value is not None:
            self._server = CompoundPiDownloadServer(value, CompoundPiDownloadHandler)
            self._server.cmd = self
            self._server.event = threading.Event()
            self._server.source = None
            self._server.output = None
            self._server.exception = None
            self._server_thread = threading.Thread(target=self._server.serve_forever)
            self._server_thread.daemon = True
            self._server_thread.start()
    bind = property(_get_bind, _set_bind)

    def _get_network(self):
        return self._network
    def _set_network(self, value):
        self._network = IPv4Network(value)
        self._servers = set()
    network = property(_get_network, _set_network)

    def _unicast(self, data, address):
        assert self.request_re.match(data)
        self._socket.sendto(data, (str(address), self.port))

    def _broadcast(self, data):
        assert self.request_re.match(data)
        self._socket.sendto(data, (str(self.network.broadcast), self.port))

    def _responses(self, servers=None, count=0):
        if self._progress_start:
            self._progress_start()
        try:
            if servers is None:
                servers = self._servers
            if not count:
                count = len(servers)
            if not servers:
                servers = self.network
            result = dict()
            start = time.time()
            while time.time() - start < self.timeout:
                if self._progress_update:
                    self._progress_update()
                if select.select([self._socket], [], [], 1)[0]:
                    data, address = self._socket.recvfrom(512)
                    match = self.response_re.match(data.decode('utf-8'))
                    address, port = address
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
                        self._unicast('%d ACK' % seqno, address)
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
            return result
        finally:
            if self._progress_finish:
                self._progress_finish()

    def _transact(self, data, addresses=None):
        if addresses:
            addresses = set(addresses)
        errors = []
        self._seqno += 1
        data = '%d %s' % (self._seqno, data)
        if addresses is None:
            addresses = self._servers
            if not addresses:
                raise CompoundPiNoServers()
            self._broadcast(data)
        elif addresses == self._servers:
            self._broadcast(data)
        elif addresses - self._servers:
            raise CompoundPiUndefinedServers(addresses - self._servers)
        else:
            for address in addresses:
                self._unicast(data, address)
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

    def __len__(self):
        return len(self._servers)

    def __iter__(self):
        return iter(self._servers)

    def __contains__(self, value):
        return value in self._servers

    def _parse_ping(self, responses):
        for address, (result, response) in responses.items():
            response = response.strip()
            if result == 'OK':
                if response != 'VERSION %s' % __version__:
                    warnings.warn(CompoundPiWrongVersion(address, response))
                    del responses[address]
            else:
                warnings.warn(CompoundPiPingError(address, response))
                del responses[address]
        return set(responses.keys())

    def add(self, addresses):
        self._seqno += 1
        for address in addresses:
            self._unicast('%d PING' % self._seqno, address)
        self._servers |= self._parse_ping(self._responses(addresses))

    def remove(self, addresses):
        self._servers -= addresses

    def find(self, count=0):
        self._servers = set()
        self._seqno += 1
        self._broadcast('%d PING' % self._seqno)
        self._servers = self._parse_ping(self._responses(count=count))

    status_re = re.compile(
            r'RESOLUTION (?P<width>\d+) (?P<height>\d+)\n'
            r'FRAMERATE (?P<rate>\d+(/\d+)?)\n'
            r'TIMESTAMP (?P<time>\d+(\.\d+)?)\n'
            r'IMAGES (?P<images>\d{,3})\n')
    def status(self, addresses=None):
        responses = [
            (address, self.status_re.match(data))
            for (address, data) in self._transact('STATUS', addresses).items()
            ]
        errors = []
        result = {}
        for address, match in responses:
            if match is None:
                errors.append(CompoundPiInvalidResponse(address))
            else:
                result[address] = CompoundPiStatus(
                    (int(match.group('width')), int(match.group('height'))),
                    fractions.Fraction(match.group('rate')),
                    datetime.datetime.fromtimestamp(float(match.group('time'))),
                    int(match.group('images')),
                    )
        if errors:
            raise CompoundPiTransactionFailed(
                errors, '%d invalid status responses' % len(errors))
        return result

    def resolution(self, width, height, addresses=None):
        self._transact('RESOLUTION %d %d' % (width, height), addresses)

    def framerate(self, rate, addresses=None):
        self._transact('FRAMERATE %s' % rate, addresses)

    def capture(self, count=1, video_port=False, delay=None, addresses=None):
        cmd = 'CAPTURE %d %d'
        params = [count, video_port]
        if delay:
            cmd += ' %f'
            params.append(time.time() + delay)
        self._transact(cmd % tuple(params), addresses)

    list_line_re = re.compile(
            r'IMAGE (?P<index>\d+) (?P<time>\d+(\.\d+)?) (?P<size>\d+)')
    def list(self, addresses=None):
        responses = {
            address: [
                self.list_line_re.match(line)
                for line in data.splitlines()
                ]
            for (address, data) in self._transact('LIST', addresses).items()
            }
        errors = []
        result = {}
        for address, matches in responses.items():
            result[address] = []
            for match in matches:
                if match is None:
                    errors.append(CompoundPiInvalidResponse(address))
                else:
                    result[address].append(CompoundPiListItem(
                        int(match.group('index')),
                        datetime.datetime.fromtimestamp(float(match.group('time'))),
                        int(match.group('size')),
                        ))
        if errors:
            raise CompoundPiTransactionFailed(
                errors, '%d invalid lines in responses' % len(errors))
        return result

    def clear(self, addresses=None):
        self._transact('CLEAR', addresses)

    def identify(self, addresses=None):
        self._transact('BLINK', addresses)

    def download(self, address, index, output):
        self._server.source = address
        self._server.output = output
        self._server.event.clear()
        try:
            self._transact('SEND %d %d' % (index, self.port), [address])
            if self._server.event.wait(self.timeout):
                if self._server.exception:
                    print('Exception in download thread: %s' % self._server.exception)
                    raise self._server.exception
            else:
                raise CompoundPiSendTimeout(address)
        finally:
            self._server.source = None
            self._server.output = None


class CompoundPiDownloadHandler(socketserver.BaseRequestHandler):
    def handle(self):
        if self.client_address[0] != str(self.server.source):
            warnings.warn(CompoundPiUnknownAddress(self.client_address[0]))
        else:
            try:
                while True:
                    data = self.request.recv(1024)
                    if not data:
                        break
                    self.server.output.write(data)
            except Exception as e:
                self.server.exception = e
            else:
                self.server.exception = None
            finally:
                self.server.event.set()


class CompoundPiDownloadServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

