#!/usr/bin/env python

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

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

import sys
import re
import cmdline
import datetime
import time
import select
import socket
import SocketServer

from cmdline import COLOR_RED, COLOR_BOLD, COLOR_RESET

class CompoundPiCmd(cmdline.Cmd):

    prompt = 'cpi> '

    def __init__(self):
        cmdline.Cmd.__init__(self)
        self.pprint('CompoundPi Client')
        self.pprint('Type "help" for more information')
        self.broadcast_address = '192.168.255.255'
        self.broadcast_port = 8000
        self.client_timeout = 5
        self.client_count = 2
        self.server_port = 8000
        # Set up a broadcast capable UDP socket
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def broadcast(self, data, addresses=None):
        if isinstance(addresses, str):
            addresses = [address]
        elif not addresses:
            addresses = [self.broadcast_address]
        for address in addresses:
            self.broadcast_socket.sendto(data, (address, self.broadcast_port))

    def responses(self, count=None):
        if not count:
            count = self.client_count
        result = {}
        start = time.time()
        while time.time() - start < self.client_timeout:
            if select.select([self.broadcast_socket], [], [], 1)[0]:
                data, address = self.broadcast_socket.recvfrom(512)
                assert address not in result
                result[address] = data
                if len(result) == count:
                    break
        if len(result) < count:
            sys.stdout.write(COLOR_RED + COLOR_BOLD)
            self.pprint(
                'Missing response from %d clients' % (
                    count - len(result)))
            sys.stdout.write(COLOR_RESET)
        return result

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
                'broadcast_address',
                'broadcast_port',
                'client_count',
                'client_timeout',
                )]
            )

    def do_ping(self, arg=''):
        """
        Pings all Pi's on the current subnet.

        Syntax: ping

        The ping command is used to quickly test that all clients are alive
        and responding. It broadcasts the 'PING' message to all listening
        clients on the current subnet and waits for a 'PONG' response,
        printing the address of all responding clients.

        cpi> ping
        """
        self.broadcast('PING\n')
        responses = self.responses()
        self.pprint_table(
            [('Address', 'Response')] +
            [('%s' % address[0], response.strip())
                for (address, response) in responses.items()]
            )

    def do_resolution(self, arg=''):
        arg = arg.split()
        width, height, addresses = arg[0], arg[1], arg[2:]
        width, height = int(width), int(height)
        self.broadcast('RESOLUTION %s %s\n', addresses)
        responses = self.responses(len(addresses))

    status_re = re.compile(
            r'RESOLUTION (?P<width>\d+) (?P<height>\d+)\n'
            r'FRAMERATE (?P<rate>\d+(.\d+)?)\n'
            r'TIMESTAMP (?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d{6})\n')
    def do_status(self, arg=''):
        """
        Retrieves status from selected Pi's on the current subnet.

        Syntax: status [address]...

        The status command is used to retrieve configuration information from
        clients. It sends the 'STATUS' message to the specified addresses or
        all addresses on the current subnet if no addresses are specified.

        cpi> status
        """
        addresses = arg.split()
        self.broadcast('STATUS\n', addresses)
        responses = [
            (address, self.status_re.match(data))
            for (address, data) in self.responses(len(addresses)).items()
            ]
        self.pprint_table(
            [('Address', 'Resolution', 'Framerate', 'Timestamp')] +
            [(
                address[0],
                '%sx%s' % (match.group('width'), match.group('height')),
                '%sfps' % match.group('rate'),
                match.group('time')
                )
                for (address, match) in responses
                ])


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    proc = CompoundPiCmd()
    proc.cmdloop()


if __name__ == '__main__':
    main()
