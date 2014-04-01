#!/usr/bin/env python

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
                'SHOOT-NOW':   self.do_shoot_now,
                'SHOOT-AT':    self.do_shoot_at,
                'SEND':        self.do_send,
                'LIST':        self.do_list,
                'CLEAR':       self.do_clear,
                'QUIT':        self.do_quit,
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

    def do_status(self):
        self.wfile.write('RESOLUTION %d %d\n' % (camera.resolution[0], camera.resolution[1]))
        self.wfile.write('FRAMERATE %.2f\n' % camera.framerate)
        self.wfile.write('TIMESTAMP %s\n' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))

    def do_resolution(self, width, height):
        camera.resolution = (int(width), int(height))
        self.wfile.write('OK\n')

    def do_framerate(self, rate):
        camera.framerate = float(rate)
        self.wfile.write('OK\n')

    def do_shoot_now(self):
        stream = io.BytesIO()
        camera.capture(stream)
        images.append(stream)
        self.wfile.write('OK\n')

    def do_shoot_at(self, timestamp):
        delay = datetime.datetime.strptime('%Y-%m-%d %H:%M:%S.%f') - datetime.datetime.now()
        time.sleep(delay.seconds)
        self.do_shoot_now()

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


if __name__ == '__main__':
    server = SocketServer.UDPServer(('0.0.0.0', 8000), CameraRequestHandler)
    server.serve_forever()

