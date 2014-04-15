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

"Implements the camera daemon"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
_str = str
str = type('')
range = xrange

import sys
import os
import io
import fractions
import struct
import time
import logging
import threading
import socket
import SocketServer as socketserver
import shutil

import picamera
import daemon

from . import __version__
from .terminal import TerminalApplication


class CompoundPiServer(TerminalApplication):
    """
    This is the server daemon for the CompoundPi application. Starting the
    application with no arguments starts the server in the foreground. The
    server can be configured through command line arguments or a configuration
    file (which defaults to /etc/cpid.ini).
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
            port=5647,
            daemon=False,
            )
        self.parser.add_argument(
            '-b', '--bind', dest='bind', action='store', metavar='ADDRESS',
            help='specifies the address to listen on for packets '
            '(default: %(default)s)')
        self.parser.add_argument(
            '-p', '--port', dest='port', action='store',
            help='specifies the UDP port for the server to listen on '
            '(default: %(default)d)')
        self.parser.add_argument(
            '-d', '--daemon', dest='daemon', action='store_true',
            help='if specified, start as a background daemon')

    def main(self, args):
        address = socket.getaddrinfo(
            args.bind, args.port, 0, socket.SOCK_DGRAM)[0][-1]
        self.server = socketserver.UDPServer(address, CameraRequestHandler)
        self.server.images = []
        self.server.camera = picamera.PiCamera()
        try:
            self.server.serve_forever()
        finally:
            self.server.camera.close()


class CameraRequestHandler(socketserver.DatagramRequestHandler):
    def handle(self):
        data = self.request[0].strip()
        logging.debug(
            '<< %s:%d %s',
            self.client_address[0], self.client_address[1], data)
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
            logging.error(
                'Unknown command "%s" from %s',
                data, self.client_address[0])
            self.wfile.write('ERROR Unknown command "%s"' % command[0])
        else:
            try:
                handler(*command[1:])
                self.wfile.write('OK')
            except Exception as exc:
                logging.error(
                    'While executing "%s" from %s: %s',
                    data, self.client_address[0], str(exc))
                self.wfile.write('ERROR %s' % str(exc))
        logging.debug(
            '>> %s:%d %s',
            self.client_address[0], self.client_address[1],
            self.wfile.getvalue().strip())

    def do_ping(self):
        pass

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

    def do_framerate(self, rate):
        self.server.camera.framerate = fractions.Fraction(rate)

    def stream_generator(self, count):
        for i in range(count):
            stream = io.BytesIO()
            self.server.images.append((time.time(), stream))
            yield stream

    def do_capture(self, count=1, use_video_port=False, sync=None):
        self.server.camera.led = False
        if sync is not None:
            delay = float(sync) - time.time()
            if delay <= 0.0:
                raise ValueError('Sync time in past')
            time.sleep(delay)
        self.server.camera.capture_sequence(
            self.stream_generator(int(count)), format='jpeg',
            use_video_port=bool(use_video_port))
        self.server.camera.led = True

    def do_send(self, image, port):
        timestamp, stream = self.server.images[int(image)]
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.connect((self.client_address[0], int(port)))
        client_file = client_sock.makefile('wb')
        try:
            stream.seek(0, io.SEEK_END)
            client_file.write(struct.pack(_str('<dL'), timestamp, stream.tell()))
            client_file.flush()
            stream.seek(0)
            shutil.copyfileobj(stream, client_file)
        finally:
            client_file.close()
            client_sock.close()

    def do_list(self):
        for timestamp, stream in self.server.images:
            stream.seek(0, io.SEEK_END)
            self.wfile.write('%f %d\n' % (timestamp, stream.tell()))

    def do_clear(self):
        del self.server.images[:]

    def do_quit(self):
        sys.exit(0)


main = CompoundPiServer()
