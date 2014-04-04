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
import io
import fractions
import time
import datetime
import socket
import struct
import SocketServer

import picamera


camera = picamera.PiCamera()
images = []

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
                'SHOOT':       self.do_shoot,
                'SHOOTAT':     self.do_shoot_at,
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

    def do_blink(self):
        self.wfile.write('OK\n')
        for i in range(5):
            camera.led = False
            time.sleep(1)
            camera.led = True

    def do_status(self):
        self.wfile.write('RESOLUTION %d %d\n' % (camera.resolution[0], camera.resolution[1]))
        self.wfile.write('FRAMERATE %.2f\n' % camera.framerate)
        self.wfile.write('TIMESTAMP %s\n' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))

    def do_resolution(self, width, height):
        camera.resolution = (int(width), int(height))
        self.wfile.write('OK\n')

    def do_framerate(self, rate):
        camera.framerate = fractions.Fraction(rate)
        self.wfile.write('OK\n')

    def do_shoot(self):
        stream = io.BytesIO()
        camera.capture(stream, format='jpeg')
        images.append(stream)
        self.wfile.write('OK\n')

    def do_shoot_at(self, timestamp):
        delay = datetime.datetime.strptime('%Y-%m-%d %H:%M:%S.%f') - datetime.datetime.now()
        time.sleep(delay.seconds)
        self.do_shoot()

    def do_send(self, image):
        stream = images[int(image)]
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.connect((self.client_address[0], 8000))
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
        del images[:]
        self.wfile.write('OK\n')

    def do_quit(self):
        sys.exit(0)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    server = SocketServer.UDPServer(('0.0.0.0', 8000), CameraRequestHandler)
    server.serve_forever()


if __name__ == '__main__':
    main()
