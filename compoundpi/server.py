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
import warnings

import daemon
import daemon.runner
import picamera
import RPi.GPIO as GPIO

from . import __version__
from .terminal import TerminalApplication
from .common import NetworkRepeater
from .exc import (
    CompoundPiInvalidClient,
    CompoundPiStaleSequence,
    CompoundPiStaleClientTime,
    )


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
        warnings.showwarning = self.showwarning
        warnings.filterwarnings('ignore', category=CompoundPiStaleSequence)
        warnings.filterwarnings('ignore', category=CompoundPiStaleClientTime)
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
        # Ensure the server's socket, any log file, and stderr are preserved
        # (if not forking)
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
            logging.info('Initializing camera')
            self.server.seqno = 0
            self.server.client_address = None
            self.server.client_timestamp = None
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

    def showwarning(self, message, category, filename, lineno, file=None,
            line=None):
        logging.warning(str(message))

    def terminate(self, signum, frame):
        logging.info('Recevied SIGTERM signal')
        self.server.shutdown()

    def interrupt(self, signum, frame):
        logging.info('Received SIGINT signal')
        self.server.shutdown()


class CameraRequestHandler(socketserver.DatagramRequestHandler):
    request_re = re.compile(
            r'(?P<seqno>\d+) '
            r'(?P<command>[A-Z]+)( (?P<params>.*))?')
    response_re = re.compile(
            r'(?P<seqno>\d+) '
            r'(?P<result>OK|ERROR)(\n(?P<data>.*))?')

    def handle(self):
        data = self.rfile.read().strip()
        logging.debug(
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
                    'ACK':          self.do_ack,
                    'AWB':          self.do_awb,
                    'BLINK':        self.do_blink,
                    'CAPTURE':      self.do_capture,
                    'CLEAR':        self.do_clear,
                    'EXPOSURE':     self.do_exposure,
                    'FLIP':         self.do_flip,
                    'FRAMERATE':    self.do_framerate,
                    'HELLO':        self.do_hello,
                    'ISO':          self.do_iso,
                    'LEVELS':       self.do_levels,
                    'LIST':         self.do_list,
                    'METERING':     self.do_metering,
                    'RESOLUTION':   self.do_resolution,
                    'SEND':         self.do_send,
                    'SHUTTERSPEED': self.do_shutter_speed,
                    'STATUS':       self.do_status,
                    }[command]
            except KeyError:
                raise ValueError('Unknown command %s' % command)
            if handler == self.do_ack:
                self.do_ack(seqno)
                return
            elif handler != self.do_hello:
                if self.client_address != self.server.client_address:
                    raise CompoundPiInvalidClient(self.client_address[0])
                elif seqno <= self.server.seqno:
                    raise CompoundPiStaleSequence(self.client_address[0], seqno)
            response = handler(*params)
            self.server.seqno = seqno
            if not response:
                response = ''
            self.send_response(seqno, '%d OK\n%s' % (seqno, response))
        except Warning as w:
            # Don't respond to raised warnings, just log them
            warnings.warn(w)
        except Exception as e:
            # Otherwise, send an ERROR response
            logging.error(str(e))
            self.send_response(seqno, '%d ERROR\n%s' % (seqno, e))

    def send_response(self, seqno, data):
        assert self.response_re.match(data)
        if isinstance(data, str):
            data = data.encode('utf-8')
        logging.debug(
                '%s:%d < %r',
                self.client_address[0], self.client_address[1], data)
        self.server.responders[(self.client_address, seqno)] = NetworkRepeater(
                self.socket, self.client_address, data)

    def do_ack(self, seqno):
        seqno = int(seqno)
        responder = self.server.responders.pop((self.client_address, seqno), None)
        if responder:
            responder.terminate = True
            responder.join()

    def do_hello(self, timestamp):
        timestamp = float(timestamp)
        if self.server.client_address == self.client_address:
            if timestamp <= self.server.client_timestamp:
                raise CompoundPiStaleClientTime(self.client_address, timestamp)
        self.server.client_address = self.client_address
        self.server.client_timestamp = timestamp
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
            'SHUTTERSPEED {shutter_speed}\n'
            'AWB {awb_mode}\n'
            'EXPOSURE {exposure_mode} {exposure_compensation}\n'
            'ISO {iso}\n'
            'METERING {meter_mode}\n'
            'LEVELS {brightness} {contrast} {saturation}\n'
            'FLIP {hflip} {vflip}\n'
            'TIMESTAMP {timestamp}\n'
            'IMAGES {images}\n'.format(
                width=self.server.camera.resolution[0],
                height=self.server.camera.resolution[1],
                framerate=self.server.camera.framerate,
                shutter_speed=self.server.camera.shutter_speed,
                awb_mode=self.server.camera.awb_mode,
                exposure_mode=self.server.camera.exposure_mode,
                exposure_compensation=self.server.camera.exposure_compensation,
                iso=self.server.camera.ISO,
                meter_mode=self.server.camera.meter_mode,
                brightness=self.server.camera.brightness,
                contrast=self.server.camera.contrast,
                saturation=self.server.camera.saturation,
                hflip=int(self.server.camera.hflip),
                vflip=int(self.server.camera.vflip),
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

    def do_shutter_speed(self, speed):
        speed = int(speed)
        logging.info('Changing camera shutter speed to %.4fms', speed / 1000)
        self.server.camera.shutter_speed = speed

    def do_awb(self, mode, red=0.0, blue=0.0):
        red = float(red)
        blue = float(blue)
        logging.info('Changing camera AWB mode to %s', mode)
        self.server.camera.awb_mode = mode
        if mode == 'off':
            logging.info('Changing camera AWB gains to %.2f, %.2f', red, blue)
            self.server.camera.awb_gains = (red, blue)

    def do_exposure(self, mode, compensation):
        compensation = int(compensation)
        logging.info('Changing camera exposure mode to %s', mode)
        self.server.camera.exposure_mode = mode
        logging.info('Changing camera exposure compensation to %d', compensation)
        self.server.camera.exposure_compensation = compensation

    def do_metering(self, mode):
        logging.info('Changing camera metering mode to %s', mode)
        self.server.camera.meter_mode = mode

    def do_iso(self, iso):
        iso = int(iso)
        logging.info('Changing camera ISO to %d', iso)
        self.server.camera.iso = iso

    def do_levels(self, brightness, contrast, saturation):
        brightness = int(brightness)
        contrast = int(contrast)
        saturation = int(saturation)
        logging.info('Changing camera brightness to %d', brightness)
        self.server.camera.brightness = brightness
        logging.info('Changing camera contrast to %d', contrast)
        self.server.camera.contrast = contrast
        logging.info('Changing camera saturation to %d', saturation)
        self.server.camera.saturation = saturation

    def do_contrast(self, value):
        value = int(value)
        logging.info('Changing camera contrast to %d', value)
        self.server.camera.contrast = value

    def do_saturation(self, value):
        value = int(value)
        logging.info('Changing camera saturation to %d', value)
        self.server.camera.saturation = value

    def do_flip(self, horizontal, vertical):
        horizontal = bool(int(horizontal))
        vertical = bool(int(vertical))
        logging.info('Changing camera horizontal flip to %s', horizontal)
        self.server.camera.hflip = horizontal
        logging.info('Changing camera vertical flip to %s', vertical)
        self.server.camera.vflip = vertical

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
