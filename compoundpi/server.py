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
import re
import pwd
import grp
import fractions
import struct
import time
import random
import logging
import threading
import socket
import SocketServer as socketserver
import shutil
import signal

import daemon
import daemon.runner
import RPi.GPIO as GPIO

from . import __version__
from .terminal import TerminalApplication


def service(s):
    try:
        return int(s)
    except ValueError:
        return socket.servbyname(s)

def address(s):
    return socket.getaddrinfo(s, 0, 0, socket.SOCK_DGRAM)[0][-1][0]

def user(s):
    try:
        return int(s)
    except ValueError:
        return pwd.getpwnam(s).pw_uid

def group(s):
    try:
        return int(s)
    except ValueError:
        return grp.getgrnam(s).gr_gid


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
        self.parser.add_argument(
            '-b', '--bind', type=address, default='0.0.0.0', metavar='ADDRESS',
            help='specifies the address to listen on for packets '
            '(default: %(default)s)')
        self.parser.add_argument(
            '-p', '--port', type=service, default='5647',
            help='specifies the UDP port for the server to listen on '
            '(default: %(default)s)')
        self.parser.add_argument(
            '-d', '--daemon', action='store_true', default=False,
            help='if specified, start as a background daemon')
        self.parser.add_argument(
            '-u', '--user', type=user, default=os.getuid(), metavar='UID',
            help='specifies the user that the daemon should run as. Defaults '
            'to the effective user (%(default)s)')
        self.parser.add_argument(
            '-g', '--group', type=group, default=os.getgid(), metavar='GID',
            help='specifies the group that the daemon should run as. Defaults '
            'to the effective group (%(default)s)')
        self.parser.add_argument(
            '--pidfile', metavar='FILE', default='/var/run/cpid.pid',
            help='specifies the location of the pid lock file '
            '(default: %(default)s)')

    def main(self, args):
        pidfile = daemon.runner.make_pidlockfile(args.pidfile, 5)
        if daemon.runner.is_pidfile_stale(pidfile):
            pidfile.break_lock()
        address = socket.getaddrinfo(
            args.bind, args.port, 0, socket.SOCK_DGRAM)[0][-1]
        logging.info('Listening on %s:%d', address[0], address[1])
        self.server = socketserver.UDPServer(address, CameraRequestHandler)
        # Test GPIO before entering the daemon context (GPIO access usually
        # requires root privileges for access to /dev/mem - better to bomb out
        # earlier than later)
        GPIO.setmode(GPIO.BCM)
        GPIO.gpio_function(5)
        # Ensure the server's socket, any log file, and stderr (if not forking)
        files_preserve = [self.server.socket]
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.FileHandler):
                files_preserve.append(handler.stream)
        logging.info('Entering daemon context')
        with daemon.DaemonContext(
                # The following odd construct is to ensure detachment only
                # where sensible (see default setting of detach_process)
                detach_process=None if args.daemon else False,
                stderr=None if args.daemon else sys.stderr,
                uid=args.user, gid=args.group,
                files_preserve=files_preserve,
                pidfile=pidfile,
                signal_map={
                    signal.SIGTERM: self.terminate,
                    signal.SIGINT:  self.interrupt,
                    }
                ):
            # seed the random number generator from the system clock
            random.seed()
            # picamera has to be imported here (currently) partly because the
            # camera doesn't like forks after initialization, and partly
            # because the author stupidly runs bcm_host_init on module import
            import picamera
            logging.info('Initializing camera')
            self.server.seqno = 0
            self.server.responders = {}
            self.server.images = []
            self.server.camera = picamera.PiCamera()
            try:
                logging.info('Starting server thread')
                thread = threading.Thread(target=self.server.serve_forever)
                thread.start()
                while thread.is_alive():
                    thread.join(1)
                logging.info('Server thread ended')
            finally:
                logging.info('Closing camera')
                self.server.camera.close()
        logging.info('Exiting daemon context')

    def terminate(self, signum, frame):
        logging.info('Recevied SIGTERM signal')
        self.server.shutdown()

    def interrupt(self, signum, frame):
        logging.info('Received SIGINT signal')
        self.server.shutdown()


class ResponderThread(threading.Thread):
    def __init__(self, socket, client_address, data):
        super(ResponderThread, self).__init__()
        self.socket = socket
        self.client_address = client_address
        self.data = data
        self.terminate = False
        self.daemon = True
        self.start()

    def run(self):
        start = time.time()
        while not self.terminate and time.time() < start + 5:
            self.socket.sendto(self.data, self.client_address)
            time.sleep(random.uniform(0.0, 0.2))


class CameraRequestHandler(socketserver.DatagramRequestHandler):
    request_re = re.compile(
            r'(?P<seqno>\d+) '
            r'(?P<command>[A-Z]+)( (?P<params>.*))?')
    response_re = re.compile(
            r'(?P<seqno>\d+) '
            r'(?P<result>OK|ERROR)(\n(?P<data>.*))?')

    def handle(self):
        data = self.rfile.read().strip()
        logging.info(
                '%s:%d > %r',
                self.client_address[0], self.client_address[1], data)
        seqno = 0
        try:
            match = self.request_re.match(data)
            if not match:
                raise ValueError('Unable to parse request')
            seqno = int(match.group('seqno'))
            command = match.group('command')
            if match.group('params'):
                params = match.group('params').split()
            else:
                params = ()
            try:
                handler = {
                    'ACK':         self.do_ack,
                    'PING':        self.do_ping,
                    'STATUS':      self.do_status,
                    'RESOLUTION':  self.do_resolution,
                    'FRAMERATE':   self.do_framerate,
                    'CAPTURE':     self.do_capture,
                    'SEND':        self.do_send,
                    'LIST':        self.do_list,
                    'CLEAR':       self.do_clear,
                    'BLINK':       self.do_blink,
                    }[command]
            except KeyError:
                raise ValueError('Unknown command %s' % command)
            if handler == self.do_ack:
                self.do_ack(seqno)
                return
            elif handler == self.do_ping:
                self.server.seqno = seqno
            elif seqno <= self.server.seqno:
                raise ValueError('Invalid sequence number')
            response = handler(*params)
            if not response:
                response = ''
            self.send_response(seqno, '%d OK\n%s' % (seqno, response))
        except Exception as exc:
            logging.error(str(exc))
            self.send_response(seqno, '%d ERROR\n%s' % (seqno, exc))

    def send_response(self, seqno, data):
        assert self.response_re.match(data)
        if isinstance(data, str):
            data = data.encode('utf-8')
        logging.info(
                '%s:%d < %r',
                self.client_address[0], self.client_address[1], data)
        self.server.responders[seqno] = ResponderThread(
                self.socket, self.client_address, data)

    def do_ack(self, seqno):
        seqno = int(seqno)
        responder = self.server.responders.pop(seqno, None)
        if responder:
            responder.terminate = True
            responder.join()

    def do_ping(self):
        return 'VERSION %s' % __version__

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
        logging.info('Starting blink thread')
        thread = threading.Thread(target=self.blink_led, args=(5,))
        thread.daemon = True
        thread.start()

    def do_status(self):
        return (
            'RESOLUTION {width} {height}\n'
            'FRAMERATE {framerate}\n'
            'TIMESTAMP {timestamp}\n'
            'IMAGES {images}\n'.format(
                width=self.server.camera.resolution[0],
                height=self.server.camera.resolution[1],
                framerate=self.server.camera.framerate,
                timestamp=time.time(),
                images=len(self.server.images),
                ))

    def do_resolution(self, width, height):
        width, height = int(width), int(height)
        logging.info('Changing camera resolution to %dx%d', width, height)
        self.server.camera.resolution = (width, height)

    def do_framerate(self, rate):
        rate = fractions.Fraction(rate)
        logging.info('Changing camera framerate to %.2ffps', rate)
        self.server.camera.framerate = rate

    def stream_generator(self, count):
        for i in range(count):
            stream = io.BytesIO()
            self.server.images.append((time.time(), stream))
            yield stream

    def do_capture(self, count=1, use_video_port=False, sync=None):
        count = int(count)
        use_video_port = bool(int(use_video_port))
        sync = float(sync) if sync else None
        self.server.camera.led = False
        try:
            if sync is not None:
                delay = sync - time.time()
                if delay <= 0.0:
                    raise ValueError('Sync time in past')
                time.sleep(delay)
            self.server.camera.capture_sequence(
                self.stream_generator(count), format='jpeg',
                use_video_port=use_video_port)
            logging.info(
                    'Captured %d images from %s port',
                    count, 'video' if use_video_port else 'still')
        finally:
            self.server.camera.led = True

    def do_send(self, image, port):
        image = int(image)
        port = int(port)
        timestamp, stream = self.server.images[image]
        logging.info('Sending image %d', image)
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.connect((self.client_address[0], port))
        client_file = client_sock.makefile('wb')
        try:
            stream.seek(0)
            shutil.copyfileobj(stream, client_file)
        finally:
            client_file.close()
            client_sock.close()

    def do_list(self):
        for timestamp, stream in self.server.images:
            stream.seek(0, io.SEEK_END)
        return '\n'.join(
            'IMAGE %d %f %d' % (index, timestamp, stream.tell())
            for (index, (timestamp, stream)) in enumerate(self.server.images)
            )

    def do_clear(self):
        logging.info('Clearing images')
        del self.server.images[:]


main = CompoundPiServer()
