#!/usr/bin/env python

import sys
import cmdline
import datetime
import time
import select
import socket
import SocketServer

class CompoundPiCmd(cmdline.Cmd):

    prompt = 'cpi> '

    def __init__(self):
        cmdline.Cmd.__init__(self)
        self.pprint('CompoundPi Client')
        self.pprint('Type "help" for more information')
        self.broadcast_address = '192.168.255.255'
        self.broadcast_port = 8000
        self.client_timeout = 10
        self.client_count = 1
        self.server_port = 8000
        # Set up a broadcast capable UDP socket
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def broadcast(self, data):
        self.broadcast_socket.sendto(
            data, (self.broadcast_address, self.broadcast_port))

    def responses(self):
        result = {}
        start = time.time()
        while time.time() - start < self.client_timeout:
            if select.select([self.broadcast_socket], [], [], 1)[0]:
                data, address = self.broadcast_socket.recvfrom(128)
                assert address not in result
                result[address] = data
                if len(result) == self.client_count:
                    break
        return result

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
            [(address, response.strip()) for (address, response) in responses.items()]
            )


if __name__ == '__main__':
    proc = CompoundPiCmd()
    proc.cmdloop()
