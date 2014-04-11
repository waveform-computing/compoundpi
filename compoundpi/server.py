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

import sys
import os
import io
import fractions
import struct
import time
import threading
import socket
import socketserver

import picamera
import daemon

from compoundpi import __version__
from compoundpi.terminal import TerminalApplication


class CompoundPiServer(TerminalApplication):
    """
    This is the server daemon for the CompoundPi application. Starting the
    application with no arguments starts the server in the foreground. The
    server can be configured through command line arguments or a configuration
    file (which defaults to /etc/cpid.conf).
    """

    def __init__(self):
        super(CompoundPiServer, self).__init__(
            version=__version__,
            config_files=[
                '/etc/cpid.ini',
                '/usr/local/etc/cpid.ini',
                os.path.expanduser('~/.cpid.ini'),
                ],
            config_bools=[
                'daemon'
                ],
            )
        self.parser.set_defaults(
            bind='0.0.0.0',
            port=8000,
            daemon=False,
            )
        self.parser.add_option(
            '-b', '--bind', dest='bind', action='store',
            help='specifies the address to listen on for packets '
            '(default: %default)')
        self.parser.add_option(
            '-p', '--port', dest='port', action='store',
            help='specifies the UDP port for the server to listen on '
            '(default: %default)')
        self.parser.add_option(
            '-d', '--daemon', dest='daemon', action='store_true',
            help='if specified, start as a background daemon')

    def main(self, options, args):
        address = socket.getaddrinfo(
            options.bind, options.port, type=socket.SOCK_DGRAM)[0][-1]
        self.server = socketserver.UDPServer(address, CameraRequestHandler)
        self.server.images = []
        self.server.camera = picamera.PiCamera()
        try:
            self.server.serve_forever()
        finally:
            self.server.camera.close()


class CameraRequestHandler(SocketServer.DatagramRequestHandler):
    def handle(self):
        data = self.request[0].strip()
        command = data.split(' ')
        try:
            handler = {
                'PING':        self.do_ping,
                'STATUS':      self.do_status,
                'RESOLUTION':  self.do_resolution,
                'FRAMERATE':   self.do_framerate,
                'CAPTURE':     self.do_capture,
                'SEND':        self.do_send,
                'LIST':        self.do_list,
                'CLEAR':       self.do_clear,
                'QUIT':        self.do_quit,
                'BLINK':       self.do_blink,
                }[command[0]]
        except KeyError:
            self.wfile.write('UNKNOWN COMMAND\n')
        else:
            try:
                handler(*command[1:])
            except Exception as exc:
                print('%s:%d > %s' % (
                    self.client_address[0], self.client_address[1], data))
                print(str(exc))
                self.wfile.write('ERROR %s\n' % str(exc))

    def do_ping(self):
        self.wfile.write('PONG\n')

    def blink_led(self, timeout):
        try:
            timeout = time.time() + timeout
            while time.time() < timeout:
                time.sleep(0.1)
                self.server.camera.led = True
                time.sleep(0.1)
                self.server.camera.led = False
        finally:
            self.server.camera.led = True

    def do_blink(self):
        # Test we can control the LED (root required) before sending "OK".  If
        # we can, then send OK and return to ensure the client doesn't timeout
        # waiting for our response. The actual flashing is taken care of in
        # a background thread
        self.server.camera.led = False
        self.wfile.write('OK\n')
        thread = threading.Thread(target=self.blink_led, args=(5,))
        thread.daemon = True
        thread.start()

    def do_status(self):
        self.wfile.write('RESOLUTION %d %d\n' % (
            self.server.camera.resolution[0],
            self.server.camera.resolution[1]))
        self.wfile.write('FRAMERATE %.2f\n' % self.server.camera.framerate)
        self.wfile.write('TIMESTAMP %f\n' % time.time())
        self.wfile.write('IMAGES %d\n' % len(self.server.images))

    def do_resolution(self, width, height):
        self.server.camera.resolution = (int(width), int(height))
        self.wfile.write('OK\n')

    def do_framerate(self, rate):
        self.server.camera.framerate = fractions.Fraction(rate)
        self.wfile.write('OK\n')

    def stream_generator(self, count):
        for i in range(count):
            stream = io.BytesIO()
            self.server.images.append((time.time(), stream))
            yield stream

    def do_capture(self, sync=0, count=1, use_video_port=False):
        self.server.camera.led = False
        delay = time.time() - float(sync)
        if delay > 0:
            time.sleep(delay)
int(port)self.server.camera.capture_sequence(
            self.stream_generator(int(count)), format='jpeg',
            use_video_port=bool(use_video_port))
        self.server.camera.led = True
        self.wfile.write('OK\n')

    def do_send(self, image, port):
        timestamp, stream = self.server.images[int(image)]
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.connect((self.client_address[0], int(port)))
        client_file = client_sock.makefile('wb')
        try:
            stream.seek(0, io.SEEK_END)
            client_file.write(struct.pack('<L', stream.tell()))
            stream.seek(0)
            client_file.write(stream.read())
        finally:
            client_file.close()
            client_sock.close()

    def do_list(self):
        self.wfile.write('%d\n' % len(images))

    def do_clear(self):
        del self.server.images[:]
        self.wfile.write('OK\n')

    def do_quit(self):
        sys.exit(0)


main = CompoundPiServer()
