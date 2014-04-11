#!/usr/bin/env python3

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

import io
import sys
import re
import datetime
import fractions
import time
import threading
import select
import struct
import socket
import socketserver

from compoundpi import __version__
from compoundpi.ipaddr import IPv4Address, IPv4Network
from compoundpi.terminal import TerminalApplication
from compoundpi.cmdline import Cmd, CmdSyntaxError, CmdError


class CompoundPiClient(TerminalApplication):
    """
    %prog [options]

    This is the CompoundPi client application which provides a command line
    interface through which you can query and interact with any Pi's running
    the CompoundPi server on your configured subnet. Use the "help" command
    within the application for information on the available commands. The
    application can be configured via command line switches, a configuration
    file (defaults to ~/.cpid.conf), or through the interactive command line
    itself.
    """

    def __init__(self):
        super(CompoundPiClient, self).__init__(__version__)

    def main(self, args):
        proc = CompoundPiCmd()
        proc.cmdloop()


class CompoundPiCmd(Cmd):

    prompt = 'cpi> '

    def __init__(self):
        Cmd.__init__(self)
        self.pprint('CompoundPi Client')
        self.pprint(
            'Type "help" for more information, '
            'or "find" to locate Pi servers')
        self.servers = set()
        self.network = IPv4Network('192.168.0.0/16')
        self.client_port = 8000
        self.server_port = 8000
        self.timeout = 5
        self.path = '/tmp'
        # Set up a broadcast capable UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Set up a threading download server
        self.server = CompoundPiDownloadServer(
            ('0.0.0.0', self.client_port), CompoundPiDownloadHandler)
        self.server.cmd = self
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.server_event = threading.Event()

    def postloop(self):
        Cmd.postloop(self)
        self.server.shutdown()

    def parse_address(self, s):
        try:
            a = IPv4Address(s.strip())
        except ValueError:
            raise CmdSyntaxError('Invalid address "%s"' % s)
        if not a in self.network:
            raise CmdSyntaxError(
                'Address "%s" does not belong to the configured network '
                '"%s"' % (a, self.network))
        return a

    def parse_address_range(self, s):
        if not '-' in s:
            raise CmdSyntaxError('Expected two dash-separated addresses')
        start, finish = (
            self.parse_address(i)
            for i in s.split('-', 1)
            )
        return start, finish

    def parse_address_list(self, s):
        result = set()
        for i in s.split(','):
            if '-' in i:
                start, finish = self.parse_address_range(i)
                result |= {IPv4Address(a) for a in range(start, finish + 1)}
            else:
                result.add(self.parse_address(i))
        return result

    def no_servers(self):
        raise CmdError(
                "You must define servers first (see help for 'find' and 'add')")

    def unicast(self, data, address):
        self.socket.sendto(data, (str(address), self.server_port))

    def broadcast(self, data):
        self.socket.sendto(data, (str(self.network.broadcast), self.server_port))

    def responses(self, servers=None, count=0):
        if servers is None:
            servers = self.servers
        if not count:
            count = len(servers)
        if not servers:
            servers = self.network
        result = {}
        start = time.time()
        while time.time() - start < self.timeout:
            if select.select([self.socket], [], [], 1)[0]:
                data, address = self.socket.recvfrom(512)
                address, port = address
                address = IPv4Address(address)
                if port != self.server_port:
                    self.pprint('Ignoring response from wrong port %s:%d' % (address, port))
                elif address in result:
                    self.pprint('Ignoring double response from %s' % address)
                elif address not in servers:
                    self.pprint('Ignoring response from %s' % address)
                else:
                    result[address] = data
                    if len(result) == count:
                        break
        if len(result) < count:
            self.pprint('Missing response from %d servers' % (count - len(result)))
        return result

    def transact(self, data, addresses):
        if addresses:
            addresses = self.parse_address_list(addresses)
            for address in addresses:
                self.unicast(data, address)
        else:
            addresses = self.servers
            if not addresses:
                self.no_servers()
            self.broadcast(data)
        return self.responses(addresses)

    def do_config(self, arg=''):
        """
        Prints the client configuration.

        Syntax: config

        The config command is used to display the current client configuration.
        Use the related "set" command to alter the configuration.

        cpi> config
        """
        self.pprint_table(
            [('Setting', 'Value')] +
            [(name, getattr(self, name)) for name in (
                'network',
                'timeout',
                'client_port',
                'server_port',
                'path',
                )]
            )

    def do_servers(self, arg=''):
        """
        Display the list of servers.

        Syntax: servers

        The 'servers' command is used to list the set of servers that the
        client expects to communicate with. The content of the list can be
        manipulated with the 'find', 'add', and 'remove' commands.

        See also: find, add, remove.

        cpi> servers
        """
        if arg:
            raise CmdSyntaxError('Unexpected argument "%s"' % arg)
        if not self.servers:
            self.pprint('No servers are defined')
        else:
            self.pprint_table(
                [('Address',)] +
                [(key,) for key in self.servers]
                )

    def do_find(self, arg=''):
        """
        Find all servers on the current subnet.

        Syntax: find [count]

        The 'find' command is typically the first command used in a client
        session to locate all Pi's on the current subnet. If a count is
        specified, the command will display an error if the expected number of
        Pi's is not located.

        See also: add, remove, servers, identify.

        cpi> find
        cpi> find 20
        """
        if arg:
            try:
                count = int(arg)
            except ValueError:
                raise CmdSyntaxError('Invalid find count "%s"' % arg)
            if count < 1:
                raise CmdSyntaxError('Invalid find count "%d"' % arg)
        else:
            count = 0
        self.broadcast('PING\n')
        responses = self.responses(count=count)
        for address, response in responses.items():
            if response.strip() != 'PONG':
                self.pprint('Ignoring bogus response from %s' % address)
                del responses[address]
        if responses:
            self.servers = set(responses.keys())
            self.pprint('Found %d servers' % len(self.servers))
        else:
            raise CmdError('Failed to find any servers')

    def do_add(self, arg):
        """
        Add addresses to the list of servers.

        Syntax: add addresses

        The 'add' command is used to manually define the set of Pi's to
        communicate with. Addresses can be specified individually, as a
        dash-separated range, or a comma-separated list of ranges and
        addresses.

        See also: find, remove, servers.

        cpi> add 192.168.0.1
        cpi> add 192.168.0.1-192.168.0.10
        cpi> add 192.168.0.1,192.168.0.5-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify address(es) to add')
        self.servers |= self.parse_address_list(arg)

    def do_remove(self, arg):
        """
        Remove addresses from the list of servers.

        Syntax: remove addresses

        The 'remove' command is used to remove addresses from the set of Pi's
        to communicate with. Addresses can be specified individually, as a
        dash-separated range, or a comma-separated list of ranges and
        addresses.

        See also: add, find, servers.

        cpi> remove 192.168.0.1
        cpi> remove 192.168.0.1-192.168.0.10
        cpi> remove 192.168.0.1,192.168.0.5-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify address(es) to remove')
        self.servers -= self.parse_address_list(arg)

    status_re = re.compile(
            r'RESOLUTION (?P<width>\d+) (?P<height>\d+)\n'
            r'FRAMERATE (?P<rate>\d+(\.\d+)?)\n'
            r'TIMESTAMP (?P<time>\d+(\.\d+)?)\n'
            r'IMAGES (?P<images>\d{,3})\n')
    def do_status(self, arg=''):
        """
        Retrieves status from the defined servers.

        Syntax: status [addresses]

        The 'status' command is used to retrieve configuration information from
        servers. If no addresses are specified, then all defined servers will
        be queried.

        See also: resolution, framerate.

        cpi> status
        """
        responses = [
            (address, self.status_re.match(data))
            for (address, data) in self.transact('STATUS\n', arg).items()
            ]
        self.pprint_table(
            [('Address', 'Resolution', 'Framerate', 'Timestamp', 'Images')] +
            [
                (
                    address,
                    '%sx%s' % (match.group('width'), match.group('height')),
                    '%sfps' % match.group('rate'),
                    datetime.fromtimestamp(float(match.group('time'))),
                    int(match.group('images')),
                    )
                for (address, match) in responses
                ])

    def do_resolution(self, arg):
        """
        Sets the resolution on the defined servers.

        Syntax: resolution res [addresses]

        The 'resolution' command is used to set the capture resolution of the
        camera on all or some of the defined servers.

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status, framerate.

        cpi> resolution 640x480
        cpi> resolution 1280x720 192.168.0.54
        cpi> resolution 1280x720 192.168.0.1,192.168.0.3
        """
        if not arg:
            raise CmdSyntaxError('You must specify a resolution')
        arg = arg.split(' ', 1)
        try:
            width, height = arg[0].lower().split('x')
            width, height = int(width), int(height)
        except (TypeError, ValueError) as exc:
            raise CmdSyntaxError('Invalid resolution "%s"' % arg[0])
        responses = self.transact(
                'RESOLUTION %d %d\n' % (width, height),
                arg[1] if len(arg) > 1 else '')
        for address, response in responses.items():
            if response.strip() == 'OK':
                self.pprint('Changed resolution to %dx%d on %s' % (
                    width, height, address))
            else:
                self.pprint('Failed to change resolution on %s:' % address)
                self.pprint(response.strip())

    def do_framerate(self, arg):
        """
        Sets the framerate on the defined servers.

        Syntax: framerate rate [addresses]

        The 'framerate' command is used to set the capture framerate of the
        camera on all or some of the defined servers. The rate can be specified
        as an integer or floating-point number, or as a fractional value.

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status, resolution.

        cpi> framerate 30
        cpi> framerate 90 192.168.0.1
        cpi> framerate 15 192.168.0.1-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify a framerate')
        arg = arg.split(' ', 1)
        try:
            rate = fractions.Fraction(rate)
        except (TypeError, ValueError) as exc:
            raise CmdSyntaxError('Invalid framerate "%s"' % arg[0])
        responses = self.transact(
                'FRAMERATE %s\n' % rate,
                arg[1] if len(arg) > 1 else '')
        for address, response in responses.items():
            if response.strip() == 'OK':
                self.pprint('Changed framerate to %s on %s' % (rate, address))
            else:
                self.pprint('Failed to change framerate on %s:' % address)
                self.pprint(response.strip())

    def do_capture(self, arg=''):
        """
        Captures images from the defined servers.

        Syntax: capture [addresses]

        The 'capture' command causes the servers to capture an image. Note
        that this does not cause the captured images to be sent to the client.
        See the 'download' command for more information.

        If no addresses are specified, a broadcast message to all defined
        servers will be used in which case the timestamp of the captured images
        are likely to be extremely close together. If addresses are specified,
        unicast messages will be sent to each server in turn.  While this is
        still reasonably quick there will be a measurable difference between
        the timestamps of the last and first captures.

        See also: download, list, clear.

        cpi> capture
        cpi> capture 192.168.0.1
        cpi> capture 192.168.0.50-192.168.0.53
        """
        responses = self.transact('CAPTURE 0 1 0\n', arg)
        for address, response in responses.items():
            if response.strip() == 'OK':
                self.pprint('Captured image on %s' % address)
            else:
                self.pprint('Failed to capture image on %s:' % address)
                self.pprint(response.strip())

    def do_download(self, arg=''):
        """
        Downloads captured images from the defined servers.

        Syntax: download [addresses]

        The 'download' command causes each server to send its captured images
        to the client. Servers are contacted consecutively to avoid saturating
        the network bandwidth. Once images are successfully downloaded from a
        server, they are wiped from the server.
        """
        if arg:
            addresses = self.parse_address_list(arg)
        else:
            addresses = self.servers
            if not addresses:
                self.no_servers()
        for address in addresses:
            self.server_event.clear()
            self.unicast('SEND 0 %d\n' % self.client_port, address)
            if not self.server_event.wait(30):
                raise CmdError(
                    'Timed out waiting for image transfer from %s' % address)
            self.pprint('Downloaded image from %s' % address)
            self.unicast('CLEAR\n', address)

    def do_identify(self, arg):
        """
        Blink the LED on the specified servers.

        Syntax: identify [addresses]

        The 'identify' command can be used to locatea specific Pi server (or
        servers) by their address. It sends a command causing the camera's LED
        to blink on and off for 5 seconds. If no addresses are specified, the
        command will be sent to all defined servers (this can be useful after
        the 'find' command to determine whether any Pi's failed to respond due
        to network issues).

        See also: find.

        cpi> identify
        cpi> identify 192.168.0.1
        cpi> identify 192.168.0.3-192.168.0.5
        """
        responses = self.transact('BLINK\n', arg)
        for address, response in responses.items():
            if response.strip() == 'OK':
                self.pprint('Identified %s' % address)
            else:
                self.pprint('Failed identify %s:' % address)
                self.pprint(response.strip())


class CompoundPiDownloadHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            # XXX Check for unreasonable size (>10Mb)
            # XXX Add timestamp to protocol
            size = struct.unpack('<L', self.request.recv(4))[0]
            filename = '%s-%s.jpg' % (
                    self.client_address[0],
                    datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S'))
            # XXX Check for silly filename
            with io.open(filename, 'wb') as output:
                while size > 0:
                    data = self.request.recv(1024)
                    output.write(data)
                    size -= len(data)
        finally:
            self.server.cmd.server_event.set()


class CompoundPiDownloadServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


main = CompoundPiClient()
