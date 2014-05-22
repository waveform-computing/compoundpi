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
import time
import random
import threading
import select
import struct
import socket
import SocketServer as socketserver
from fractions import Fraction
from collections import namedtuple
try:
    from ipaddress import IPv4Address, IPv4Network
except ImportError:
    from ipaddr import IPv4Address, IPv4Network

from . import __version__
from .common import NetworkRepeater
from .exc import (
    CompoundPiBadResponse,
    CompoundPiFutureResponse,
    CompoundPiHelloError,
    CompoundPiInvalidResponse,
    CompoundPiMissingResponse,
    CompoundPiMultiResponse,
    CompoundPiNoServers,
    CompoundPiRedefinedServers,
    CompoundPiSendTimeout,
    CompoundPiServerError,
    CompoundPiStaleResponse,
    CompoundPiTransactionFailed,
    CompoundPiUndefinedServers,
    CompoundPiUnknownAddress,
    CompoundPiWrongPort,
    CompoundPiWrongVersion,
    )


class Resolution(namedtuple('Resolution', ('width', 'height'))):
    __slots__ = ()

    def __str__(self):
        return '%dx%d' % (self.width, self.height)


CompoundPiStatus = namedtuple('CompoundPiStatus', (
    'resolution',
    'framerate',
    'shutter_speed',
    'awb_mode',
    'exposure_mode',
    'exposure_compensation',
    'iso',
    'metering_mode',
    'brightness',
    'contrast',
    'saturation',
    'hflip',
    'vflip',
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
        self._senders = {}
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

    def _send_command(self, address, seqno, data):
        assert self.request_re.match(data)
        if isinstance(data, str):
            data = data.encode('utf-8')
        self._senders[(address, seqno)] = NetworkRepeater(
            self._socket, address, data)

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
                    data, server_address = self._socket.recvfrom(512)
                    match = self.response_re.match(data.decode('utf-8'))
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
                        self._socket.sendto('%d ACK' % seqno, server_address)
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
            return result
        finally:
            while self._senders:
                _, sender = self._senders.popitem()
                sender.terminate = True
                sender.join()
            if self._progress_finish:
                self._progress_finish()

    def _transact(self, data, addresses=None):
        if addresses is None:
            if not self._servers:
                raise CompoundPiNoServers()
            addresses = self._servers
        elif set(addresses) - self._servers:
            raise CompoundPiUndefinedServers(set(addresses) - self._servers)
        errors = []
        self._seqno += 1
        data = '%d %s' % (self._seqno, data)
        if set(addresses) == self._servers:
            self._send_command(
                (str(self.network.broadcast), self.port), self._seqno, data)
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
                warnings.warn(CompoundPiHelloError(address, response))
                del responses[address]
        return set(responses.keys())

    def add(self, addresses):
        if set(addresses) & self._servers:
            raise CompoundPiRedefinedServers(set(addresses) & self._servers)
        self._seqno += 1
        data = '%d HELLO %f' % (self._seqno, time.time())
        for address in addresses:
            self._send_command(
                (str(address), self.port), self._seqno, data)
        # Abuse catch_warnings to mutate warnings in parse_ping into errors
        # associated with our transaction. We don't do this in find() as the
        # assumption is that a user explicitly calling add() expects the
        # addresses passed to work, whereas find() merely locates compatible
        # servers on the subnet
        to_add = self._parse_ping(self._responses(addresses))
        errors = []
        if set(addresses) - to_add:
            raise CompoundPiTransactionFailed([
                CompoundPiMissingResponse(address)
                for address in set(addresses) - to_add
                ])
        self._servers |= to_add

    def remove(self, addresses):
        self._servers -= set(addresses)

    def find(self, count=0):
        self._servers = set()
        self._seqno += 1
        data = '%d HELLO %f' % (self._seqno, time.time())
        self._send_command(
            (str(self.network.broadcast), self.port), self._seqno, data)
        self._servers = self._parse_ping(self._responses(count=count))

    status_re = re.compile(
            r'RESOLUTION (?P<width>\d+) (?P<height>\d+)\n'
            r'FRAMERATE (?P<rate>\d+(/\d+)?)\n'
            r'SHUTTERSPEED (?P<speed>\d+(\.\d+)?)\n'
            r'AWB (?P<awb_mode>[a-z]+)\n'
            r'EXPOSURE (?P<exposure_mode>[a-z]+) (?P<exposure_compensation>\d+)\n'
            r'ISO (?P<iso>\d+)\n'
            r'METERING (?P<metering_mode>[a-z]+)\n'
            r'LEVELS (?P<brightness>\d+) (?P<contrast>\d+) (?P<saturation>\d+)\n'
            r'FLIP (?P<hflip>0|1) (?P<vflip>0|1)\n'
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
                    resolution=Resolution(int(match.group('width')), int(match.group('height'))),
                    framerate=Fraction(match.group('rate')),
                    shutter_speed=float(match.group('speed')),
                    awb_mode=match.group('awb_mode'),
                    exposure_mode=match.group('exposure_mode'),
                    exposure_compensation=int(match.group('exposure_compensation')),
                    iso=int(match.group('iso')),
                    metering_mode=match.group('metering_mode'),
                    brightness=int(match.group('brightness')),
                    contrast=int(match.group('contrast')),
                    saturation=int(match.group('saturation')),
                    hflip=bool(int(match.group('hflip'))),
                    vflip=bool(int(match.group('vflip'))),
                    timestamp=datetime.datetime.fromtimestamp(float(match.group('time'))),
                    images=int(match.group('images')),
                    )
        if errors:
            raise CompoundPiTransactionFailed(
                errors, '%d invalid status responses' % len(errors))
        return result

    def resolution(self, width, height, addresses=None):
        self._transact('RESOLUTION %d %d' % (width, height), addresses)

    def framerate(self, rate, addresses=None):
        self._transact('FRAMERATE %s' % rate, addresses)

    def shutter_speed(self, speed, addresses=None):
        self._transact('SHUTTERSPEED %d' % speed, addresses)

    def awb(self, mode, red=0.0, blue=0.0, addresses=None):
        self._transact('AWB %s %f %f' % (mode, red, blue), addresses)

    def exposure(self, mode, compensation=0, addresses=None):
        self._transact('EXPOSURE %s %d' % (mode, compensation), addresses)

    def metering(self, mode, addresses=None):
        self._transact('METERING %s' % mode, addresses)

    def iso(self, value, addresses=None):
        self._transact('ISO %d' % value, addresses)

    def levels(self, brightness, contrast, saturation, addresses=None):
        self._transact('LEVELS %d %d %d' % (brightness, contrast, saturation), addresses)

    def flip(self, horizontal, vertical, addresses=None):
        self._transact('FLIP %d %d' % (horizontal, vertical), addresses)

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

