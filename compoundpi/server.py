# vim: set et sw=4 sts=4 fileencoding=utf-8:

# Copyright 2014 Dave Hughes <dave@waveform.org.uk>.
#
# This file is part of compoundpi.
#
# compoundpi is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) any later
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
native_str = str
str = type('')
try:
    range = xrange
    from itertools import izip as zip
except NameError:
    pass
except ImportError:
    pass

import sys
import os
import io
import re
import pwd
import grp
import time
import random
import logging
import threading
import struct
import socket
try:
    # Py2 compat
    import SocketServer as socketserver
except ImportError:
    import socketserver
import shutil
import signal
import warnings
import inspect
from functools import wraps

import daemon
import daemon.runner
import picamera
import RPi.GPIO as GPIO

from . import __version__
from .terminal import TerminalApplication
from .common import NetworkRepeater
from .protocol import CompoundPiProtocol
from .exc import (
    CompoundPiInvalidClient,
    CompoundPiStaleSequence,
    CompoundPiStaleClientTime,
    )


def service(s):
    try:
        return int(s)
    except ValueError:
        return socket.getservbyname(s)

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


class CompoundPiFile(object):
    """
    Represents a file stored in memory on the Compound Pi Server. The
    *filetype* attribute is ``IMAGE``, ``VIDEO``, or ``MOTION`` depending on
    the content of the stream. The *timestamp* attribute is the UNIX epoch
    timestamp immediately prior to capture/record start. The *stream* attribute
    contains the file data, and the *size* attribute returns the size of the
    stream (note: this seeks to the end of the stream).
    """
    def __init__(self, filetype, timestamp=None):
        self._filetype = filetype
        if timestamp is None:
            self._timestamp = time.time()
        else:
            self._timestamp = timestamp
        self._stream = io.BytesIO()

    @property
    def filetype(self):
        return self._filetype

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def stream(self):
        return self._stream

    @property
    def size(self):
        return self._stream.seek(0, io.SEEK_END)


class CompoundPiUDPServer(socketserver.UDPServer):
    allow_reuse_address = True


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
        if args.debug:
            # Don't bother with daemon context in debug mode; we generally
            # want to debug protocol stuff anyway...
            signal.signal(signal.SIGINT, self.interrupt)
            signal.signal(signal.SIGTERM, self.terminate)
            self.privileged_setup(args)
            self.serve_forever()
        else:
            pidfile = daemon.runner.make_pidlockfile(args.pidfile, 5)
            if daemon.runner.is_pidfile_stale(pidfile):
                pidfile.break_lock()
            self.privileged_setup(args)
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
                self.serve_forever()
            logging.info('Exiting daemon context')

    def privileged_setup(self, args):
        # Bind to the socket before entering daemon context in case the port
        # requested is privileged
        address = socket.getaddrinfo(
            args.bind, args.port, 0, socket.SOCK_DGRAM)[0][-1]
        logging.info('Listening on %s:%d', address[0], address[1])
        self.server = CompoundPiUDPServer(address, CompoundPiServerProtocol)
        # Test GPIO before entering the daemon context (GPIO access usually
        # requires root privileges for access to /dev/mem - better to bomb out
        # earlier than later)
        GPIO.setmode(GPIO.BCM)
        GPIO.gpio_function(5)

    def serve_forever(self):
        # seed the random number generator from the system clock
        random.seed()
        logging.info('Initializing camera')
        self.server.seqno = 0
        self.server.client_address = None
        self.server.client_timestamp = None
        self.server.responders = {}
        self.server.files = []
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

    def showwarning(self, message, category, filename, lineno, file=None,
            line=None):
        logging.warning(str(message))

    def terminate(self, signum, frame):
        logging.info('Recevied SIGTERM signal')
        self.server.shutdown()

    def interrupt(self, signum, frame):
        logging.info('Received SIGINT signal')
        self.server.shutdown()


def server(protocol):
    """
    Decorator to convert handler arguments in CompoundPiServerProtocol.

    This is necessarily rather complicated compared to the client equivalent;
    in Python 2.x socket server request handlers are based on old-style classes
    which means we can't simply convert CompoundPiProtocol into a mixin class
    and use multiple inheritance. So instead we use the *protocol* as a
    template, looking up similarly named methods in *cls* and decorating them
    before adding a handler map to *cls*.
    """
    def method_decorator(fn, arg_names, arg_types):
        @wraps(fn)
        def wrapper(self, *args):
            typed_args = [
                    arg_type(value) if value else None
                    for arg_type, value in zip(arg_types, args)
                    ]
            return fn(self, **{
                arg_name: value
                for arg_name, value in zip(arg_names, typed_args)
                if value is not None
                })
        return wrapper

    def class_decorator(cls):
        handlers = {}
        for name, handler in cls.__dict__.items():
            if name in protocol.__dict__:
                template = protocol.__dict__[name]
                if inspect.isfunction(template) and hasattr(template, 'command'):
                    arg_names = inspect.getargspec(template).args[1:]
                    arg_types = template.params
                    wrapped_handler = method_decorator(handler, arg_names, arg_types)
                    handlers[template.command] = wrapped_handler
                    setattr(cls, name, wrapped_handler)
        cls.handlers = handlers
        cls.request_re = protocol.request_re
        cls.response_re = protocol.response_re
        return cls

    return class_decorator


@server(CompoundPiProtocol)
class CompoundPiServerProtocol(socketserver.DatagramRequestHandler):
    def handle(self):
        data = self.rfile.read().decode('utf-8').strip()
        logging.debug(
                '%s:%d Rx %r',
                self.client_address[0], self.client_address[1], data)
        seqno = 0
        try:
            match = self.request_re.match(data)
            if not match:
                raise ValueError('Unable to parse request')
            seqno = int(match.group('seqno'))
            command = match.group('command')
            # Implement special handling for ACK and HELLO. ACK sends no
            # response and has no handler. HELLO doesn't check the sequence
            # number and can come from a new client
            if command == 'ACK':
                self.ack_response(seqno)
                return
            if command != 'HELLO':
                if self.client_address != self.server.client_address:
                    raise CompoundPiInvalidClient(self.client_address[0])
                elif seqno <= self.server.seqno:
                    raise CompoundPiStaleSequence(self.client_address[0], seqno)
            if match.group('params'):
                params = (p.strip() for p in match.group('params').split(','))
            else:
                params = ()
            response = self.dispatch(command, *params)
            self.server.seqno = seqno
            if not response:
                response = ''
            self.send_response(seqno, 'OK\n%s' % response)
        except Exception as e:
            # Otherwise, send an ERROR response. Note: we use the client's
            # sequence number here in case it's stale (otherwise the client
            # will ignore the response or associate it with the wrong call)
            logging.error(str(e))
            self.send_response(seqno, 'ERROR\n%s' % e)

    def send_response(self, seqno, data):
        data = '%d %s' % (seqno, data)
        assert self.response_re.match(data)
        logging.debug(
                '%s:%d Tx %r',
                self.client_address[0], self.client_address[1], data)
        data = data.encode('utf-8')
        self.server.responders[(self.client_address, seqno)] = NetworkRepeater(
                self.socket, self.client_address, data)

    def ack_response(self, seqno):
        responder = self.server.responders.pop((self.client_address, seqno), None)
        if responder:
            responder.terminate = True
            responder.join()

    def dispatch(self, command, *params):
        # Look up the handler in self.handlers (this dict is defined by the
        # register_handlers decorator on the class)
        try:
            handler = self.handlers[command]
        except KeyError:
            raise ValueError('Unknown command %s' % command)
        # The handler we get back is an unbound method; bind it to this
        # instance
        handler = handler.__get__(self, CompoundPiServerProtocol)
        # Some magic happens here because the handler we're calling is actually
        # a wrapper created by @server. Basically parameters are magically
        # converted from strings to something more useful and defaults are
        # filled in as necessary
        return handler(*params)

    def do_hello(self, timestamp):
        if self.server.client_address == self.client_address:
            if timestamp <= self.server.client_timestamp:
                raise CompoundPiStaleClientTime(self.client_address[0], timestamp)
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
            'RESOLUTION {width},{height}\n'
            'FRAMERATE {framerate}\n'
            'AWB {awb_mode},{awb_red},{awb_blue}\n'
            'AGC {agc_mode},{agc_analog},{agc_digital}\n'
            'EXPOSURE {exp_mode},{exp_speed}\n'
            'ISO {iso}\n'
            'METERING {meter_mode}\n'
            'BRIGHTNESS {brightness}\n'
            'CONTRAST {contrast}\n'
            'SATURATION {saturation}\n'
            'EV {ev}\n'
            'FLIP {hflip},{vflip}\n'
            'DENOISE {denoise}\n'
            'TIMESTAMP {timestamp}\n'
            'FILES {files}\n'.format(
                width=self.server.camera.resolution[0],
                height=self.server.camera.resolution[1],
                framerate=self.server.camera.framerate,
                awb_mode=self.server.camera.awb_mode,
                awb_red=self.server.camera.awb_gains[0],
                awb_blue=self.server.camera.awb_gains[1],
                agc_mode=self.server.camera.exposure_mode,
                agc_analog=self.server.camera.analog_gain,
                agc_digital=self.server.camera.digital_gain,
                exp_mode='auto' if not self.server.camera.shutter_speed else 'off',
                exp_speed=self.server.camera.exposure_speed / 1000.0,
                ev=self.server.camera.exposure_compensation,
                iso=self.server.camera.iso,
                meter_mode=self.server.camera.meter_mode,
                brightness=self.server.camera.brightness,
                contrast=self.server.camera.contrast,
                saturation=self.server.camera.saturation,
                hflip=int(self.server.camera.hflip),
                vflip=int(self.server.camera.vflip),
                denoise=int(self.server.camera.image_denoise),
                timestamp=time.time(),
                files=len(self.server.files),
                ))

    def do_resolution(self, width, height):
        logging.info('Changing camera resolution to %dx%d', width, height)
        self.server.camera.resolution = (width, height)

    def do_framerate(self, rate):
        logging.info('Changing camera framerate to %.2ffps', rate)
        self.server.camera.framerate = rate

    def do_awb(self, mode, red=0.0, blue=0.0):
        logging.info('Changing camera AWB mode to %s', mode)
        self.server.camera.awb_mode = mode
        if mode == 'off':
            logging.info('Changing camera AWB gains to %.2f, %.2f', red, blue)
            self.server.camera.awb_gains = (red, blue)

    def do_agc(self, mode):
        logging.info('Changing camera AGC mode to %s', mode)
        self.server.camera.exposure_mode = mode

    def do_exposure(self, mode, speed):
        speed = int(speed * 1000)
        logging.info('Changing camera exposure speed mode to %s', mode)
        if mode == 'auto':
            self.server.camera.shutter_speed = 0
        else:
            logging.info('Changing camera exposure speed to %.4fms', speed / 1000.0)
            self.server.camera.shutter_speed = speed

    def do_metering(self, mode):
        logging.info('Changing camera metering mode to %s', mode)
        self.server.camera.meter_mode = mode

    def do_iso(self, iso):
        logging.info('Changing camera ISO to %d', iso)
        self.server.camera.iso = iso

    def do_brightness(self, brightness):
        logging.info('Changing camera brightness to %d', brightness)
        self.server.camera.brightness = brightness

    def do_contrast(self, contrast):
        logging.info('Changing camera contrast to %d', contrast)
        self.server.camera.contrast = contrast

    def do_saturation(self, saturation):
        logging.info('Changing camera saturation to %d', saturation)
        self.server.camera.saturation = saturation

    def do_ev(self, ev):
        logging.info('Changing camera EV to %d', ev)
        self.server.camera.exposure_compensation = ev

    def do_denoise(self, denoise):
        logging.info('Changing camera denoise to %s', denoise)
        self.server.camera.image_denoise = denoise
        self.server.camera.video_denoise = denoise

    def do_flip(self, horizontal, vertical):
        logging.info('Changing camera horizontal flip to %s', horizontal)
        self.server.camera.hflip = horizontal
        logging.info('Changing camera vertical flip to %s', vertical)
        self.server.camera.vflip = vertical

    def image_stream_generator(self, count):
        for i in range(count):
            f = CompoundPiFile('IMAGE')
            yield f.stream
            self.server.files.append(f)

    def wait_until(self, sync):
        if sync is not None:
            delay = sync - time.time()
            if delay <= 0.0:
                raise ValueError('Sync time in past')
            time.sleep(delay)

    def do_capture(self, count=1, use_video_port=False, quality=85, sync=None):
        self.server.camera.led = False
        try:
            self.wait_until(sync)
            self.server.camera.capture_sequence(
                self.image_stream_generator(count), format='jpeg',
                quality=quality, use_video_port=use_video_port,
                burst=not use_video_port)
            logging.info(
                    'Captured %d images from %s port',
                    count, 'video' if use_video_port else 'still')
        finally:
            self.server.camera.led = True

    def do_record(self, length, format='h264', quality=0, bitrate=17000000,
            intra_period=None, motion_output=False, sync=None):
        self.server.camera.led = False
        try:
            # Ensure video and motion streams have equivalent timestamps
            video_file = CompoundPiFile('VIDEO')
            if motion_output:
                if format != 'h264':
                    raise ValueError('Format must be h264 for motion output')
                motion_file = CompoundPiFile('MOTION', video_file.timestamp)
            else:
                motion_file = None
            self.wait_until(sync)
            self.server.camera.start_recording(
                    video_file.stream, format=format, quality=quality,
                    bitrate=bitrate, intra_period=intra_period,
                    motion_output=motion_file.stream if motion_file else None)
            self.server.camera.wait_recording(length)
            self.server.camera.stop_recording()
            self.server.files.append(video_file)
            if motion_file:
                self.server.files.append(motion_file)
            logging.info(
                'Recorded %.1f seconds of %s video%s', length, format,
                ' with motion' if motion_output else '')
        finally:
            self.server.camera.led = True

    def do_send(self, file_num, port):
        f = self.server.files[file_num]
        logging.info('Sending file %d', file_num)
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.connect((self.client_address[0], port))
        client_file = client_sock.makefile('wb')
        try:
            client_file.write(struct.pack(native_str('>L'), f.size))
            client_file.flush()
            f.stream.seek(0)
            shutil.copyfileobj(f.stream, client_file)
        finally:
            client_file.close()
            client_sock.close()

    def do_list(self):
        return '\n'.join(
            '%s,%d,%f,%d' % (f.filetype, index, f.timestamp, f.size)
            for index, f in enumerate(self.server.files)
            )

    def do_clear(self):
        logging.info('Clearing files')
        del self.server.files[:]


main = CompoundPiServer()
