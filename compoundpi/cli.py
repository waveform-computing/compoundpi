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

"Implements the client terminal interface"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')
range = xrange
# Py3: correct super-class calls
# Py3: remove getattr, setattr methods

import sys
import io
import os
import re
import logging
import warnings
import datetime
import socket
import fractions
try:
    from ipaddress import IPv4Address, IPv4Network
except ImportError:
    from ipaddr import IPv4Address, IPv4Network

from . import __version__
from .client import CompoundPiClient
from .terminal import TerminalApplication
from .cmdline import Cmd, CmdSyntaxError, CmdError


def service(s):
    try:
        return int(s)
    except ValueError:
        return socket.getservbyname(s)

def address(s):
    host, port = s.rsplit(':', 1)
    return socket.getaddrinfo(host, service(port), 0, socket.SOCK_STREAM)[0][-1]

def network(s):
    return IPv4Network(s)

def zero_or_more(s):
    result = int(s)
    if result < 0:
        raise ValueError('Value must be 0 or more')
    return result

def one_or_more(s):
    result = int(s)
    if result < 1:
        raise ValueError('Value must be 1 or more')
    return result

def positive_float(s):
    result = float(s)
    if result > 0.0:
        return result
    raise ValueError('Value must be greater than 0')

def path(s):
    s = os.path.expanduser(s)
    if not os.path.exists(s):
        raise ValueError('%s does not exist' % s)
    if not os.path.isdir(s):
        raise ValueError('%s is not a directory' % s)
    return s

def boolean(s):
    s = s.strip().lower()
    if s in {'true', 't', 'yes', 'y', 'on', '1'}:
        return True
    elif s in {'false', 'f', 'no', 'n', 'off', '0'}:
        return False
    raise ValueError('%s is not a valid boolean' % s)


class CompoundPiClientApplication(TerminalApplication):
    """
    This is the CompoundPi client application which provides a command line
    interface through which you can query and interact with any Pi's running
    the CompoundPi server on your configured subnet. Use the "help" command
    within the application for information on the available commands. The
    application can be configured via command line switches, a configuration
    file (defaults to ~/.cpid.ini), or through the interactive command line
    itself.
    """

    def __init__(self):
        super(CompoundPiClientApplication, self).__init__(
            version=__version__,
            config_files=[
                '/etc/cpi.ini',
                '/usr/local/etc/cpi.ini',
                os.path.expanduser('~/.cpi.ini'),
                ],
            config_bools=[
                'video_port',
                ],
            )
        self.parser.add_argument(
            '-o', '--output', metavar='PATH', default='/tmp',
            help='specifies the directory that downloaded images will be '
            'written to (default: %(default)s)')
        self.parser.add_argument(
            '-n', '--network', type=network, default='192.168.0.0/16',
            help='specifies the network that the servers '
            'belong to (default: %(default)s)')
        self.parser.add_argument(
            '-p', '--port', type=service, default='5647', metavar='PORT',
            help='specifies the port that the servers are listening on '
            '(default: %(default)s)')
        self.parser.add_argument(
            '-b', '--bind', type=address, default='0.0.0.0:5647', metavar='ADDRESS:PORT',
            help='specifies the address and port that the client listens on '
            'for downloads (default: %(default)s)')
        self.parser.add_argument(
            '-t', '--timeout', type=int, default='5', metavar='SECS',
            help='specifies the timeout (in seconds) for network '
            'transactions (default: %(default)s)')
        self.parser.add_argument(
            '--capture-delay', type=int, default='0', metavar='SECS',
            help='specifies the delay (in seconds) used to synchronize '
            'captures. This must be less than the network delay '
            '(default: %(default)s)')
        self.parser.add_argument(
            '--capture-count', type=int, default='1', metavar='NUM',
            help='specifies the number of consecutive pictures to capture '
            'when requested (default: %(default)s)')
        self.parser.add_argument(
            '--video-port', action='store_true', default=False,
            help="if specified, use the camera's video port for rapid capture")
        self.parser.add_argument(
            '--time-delta', type=float, default='0.25', metavar='SECS',
            help='specifies the maximum delta between server timestamps that '
            'the client will tolerate (default: %(default)ss)')
        self.parser.set_defaults(log_level=logging.INFO)

    def main(self, args):
        proc = CompoundPiCmd()
        proc.client.network = args.network
        proc.client.port = args.port
        proc.client.bind = args.bind
        proc.client.timeout = args.timeout
        proc.capture_delay = args.capture_delay
        proc.capture_count = args.capture_count
        proc.video_port = args.video_port
        proc.time_delta = args.time_delta
        proc.output = args.output
        proc.cmdloop()


class CompoundPiCmd(Cmd):

    prompt = 'cpi> '
    request_re = re.compile(
            r'(?P<seqno>\d+) '
            r'(?P<command>[A-Z]+)( (?P<params>.*))?')
    response_re = re.compile(
            r'(?P<seqno>\d+) '
            r'(?P<result>OK|ERROR)(\n(?P<data>.*))?', flags=re.DOTALL)

    def __init__(self):
        Cmd.__init__(self)
        self.pprint('CompoundPi Client version %s' % __version__)
        self.pprint(
            'Type "help" for more information, '
            'or "find" to locate Pi servers')
        self.client = CompoundPiClient()
        self.capture_delay = 0
        self.capture_count = 1
        self.video_port = False
        self.time_delta = 0.25
        self.output = '/tmp'
        self.warnings = False
        warnings.simplefilter('always')

    def showwarning(self, message, category, filename, lineno, file=None,
            line=None):
        if self.warnings:
            logging.warning(str(message))

    def preloop(self):
        assert self.client.bind
        Cmd.preloop(self)

    def postloop(self):
        Cmd.postloop(self)
        self.client.bind = None

    def parse_address(self, s):
        try:
            a = IPv4Address(s.strip())
        except ValueError:
            raise CmdSyntaxError('Invalid address "%s"' % s)
        if not a in self.client.network:
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

    def parse_arg(self, arg=None):
        if arg:
            return self.parse_address_list(arg)
        elif not len(self.client):
            raise CmdError(
                    "You must define servers first (see help for 'find' "
                    "and 'add')")

    def complete_server(self, text, line, start, finish):
        return [
            str(server)
            for server in self.client
            if str(server).startswith(text)
            ]

    def do_config(self, arg=''):
        """
        Prints the client configuration.

        Syntax: config

        The config command is used to display the current client configuration.
        Use the related 'set' command to alter the configuration.

        See also: set.

        cpi> config
        """
        self.pprint_table(
            [
                ('Setting',       'Value'),
                ('network',       self.client.network),
                ('port',          self.client.port),
                ('bind',          '%s:%d' % self.client.bind),
                ('timeout',       self.client.timeout),
                ('capture_delay', self.capture_delay),
                ('capture_count', self.capture_count),
                ('video_port',    self.video_port),
                ('time_delta',    self.time_delta),
                ('output',        self.output),
                ('warnings',      self.warnings),
                ]
            )

    def do_set(self, arg):
        """
        Change a configuration variable.

        Syntax: set <name> <value>

        The 'set' command is used to alter the value of a client configuration
        variable. Use the related 'config' command to view the current
        configuration.

        See also: config.

        cpi> set timeout 10
        cpi> set output ~/Pictures/
        cpi> set capture_count 5
        """
        # XXX Correct this
        match = re.match(r' *(?P<name>[A-Za-z_]+) +(?P<value>.*)', arg)
        if not match:
            raise CmdSyntaxError('You must specify a variable name and value')
        name = match.group('name').lower()
        value = match.group('value').strip()
        try:
            value = {
                'network':       network,
                'port':          service,
                'bind':          address,
                'timeout':       one_or_more,
                'capture_delay': zero_or_more,
                'capture_count': one_or_more,
                'video_port':    boolean,
                'time_delta':    positive_float,
                'output':        path,
                'warnings':      boolean,
                }[name](value)
        except KeyError:
            raise CmdSyntaxError('Invalid configuration variable: %s' % name)
        except ValueError as e:
            raise CmdSyntaxError(e)
        if name in ('network', 'port', 'bind', 'timeout'):
            setattr(self.client, name, value)
        else:
            setattr(self, name, value)

    def complete_set(self, text, line, start, finish):
        cmd_re = re.compile(r'set(?P<name> +[^ ]+(?P<value> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('value') < finish <= match.end('value'):
            name = match.group('name').strip()
            value = match.group('value').strip()
            if name.startswith('output'):
                return self.complete_path(text, value, start, finish)
            elif name.startswith('video_port') or name.startswith('warnings'):
                values = ['on', 'off', 'true', 'false', 'yes', 'no', '0', '1']
                return [value for value in values if value.startswith(text)]
            else:
                return []
        elif match.start('name') < finish <= match.end('name'):
            names = [
                'network',
                'port',
                'bind',
                'timeout',
                'capture_delay',
                'capture_count',
                'video_port',
                'time_delta',
                'output',
                'warnings',
                ]
            return [name + ' ' for name in names if name.startswith(text)]

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
        if not len(self.client):
            self.pprint('No servers are defined')
        else:
            self.pprint_table(
                [('Address',)] +
                [(server,) for server in self.client]
                )

    def do_find(self, arg=''):
        """
        Find all servers on the current subnet.

        Syntax: find [count]

        The 'find' command is typically the first command used in a client
        session to locate all Pis on the configured subnet. If a count is
        specified, the command will display an error if the expected number of
        Pis is not located.

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
        self.client.find(count)
        if not len(self.client):
            raise CmdError('Failed to find any servers')
        logging.info('Found %d servers' % len(self.client))

    def do_add(self, arg):
        """
        Add addresses to the list of servers.

        Syntax: add <addresses>

        The 'add' command is used to manually define the set of Pi servers to
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
        self.client.add(self.parse_address_list(arg))

    def complete_add(self, text, line, start, finish):
        return [
            str(server)
            for server in self.client.network
            if server not in self.client
            and str(server).startswith(text)
            ]

    def do_remove(self, arg):
        """
        Remove addresses from the list of servers.

        Syntax: remove <addresses>

        The 'remove' command is used to remove addresses from the set of Pi
        servers to communicate with. Addresses can be specified individually,
        as a dash-separated range, or a comma-separated list of ranges and
        addresses.

        See also: add, find, servers.

        cpi> remove 192.168.0.1
        cpi> remove 192.168.0.1-192.168.0.10
        cpi> remove 192.168.0.1,192.168.0.5-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify address(es) to remove')
        self.client.remove(self.parse_address_list(arg))

    def complete_remove(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)

    status_re = re.compile(
            r'RESOLUTION (?P<width>\d+) (?P<height>\d+)\n'
            r'FRAMERATE (?P<rate>\d+(/\d+)?)\n'
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
        responses = self.client.status(self.parse_arg(arg))
        min_time = min(status.timestamp for status in responses.values())
        min_speed = min(status.shutter_speed for status in responses.values())
        self.pprint_table(
            [
                (
                    'Address',
                    'Mode',
                    'Shutter',
                    'AWB',
                    'Exp',
                    'Meter',
                    'Flip',
                    'Time Delta',
                    '#',
                    )
            ] + [
                (
                    address,
                    '%dx%d@%s' % (
                        status.resolution.width,
                        status.resolution.height,
                        status.framerate,
                        ),
                    (
                        'auto' if status.shutter_speed == 0 else
                        '%.3fms' % (status.shutter_speed / 1000)
                        ),
                    status.awb_mode,
                    status.exposure_mode,
                    status.metering_mode,
                    (
                        'both' if status.vflip and status.hflip else
                        'vert' if status.vflip else
                        'horz' if status.hflip else
                        'none'
                        ),
                    status.timestamp - min_time,
                    status.images,
                    )
                for address in sorted(self.client)
                if address in responses
                for status in (responses[address],)
                ])
        if len(set(
                status.resolution
                for status in responses.values()
                )) > 1:
            logging.warning('Warning: multiple resolutions configured')
        if len(set(
                status.framerate
                for status in responses.values()
                )) > 1:
            logging.warning('Warning: multiple framerates configured')
        if len(set(
                status.awb_mode
                for status in responses.values()
                )) > 1:
            logging.warning('Warning: multiple white-balance modes configured')
        if len(set(
                status.exposure_mode
                for status in responses.values()
                )) > 1:
            logging.warning('Warning: multiple exposure modes configured')
        if len(set(
                status.exposure_compensation
                for status in responses.values()
                )) > 1:
            logging.warning('Warning: multiple exposure compensations configured')
        if len(set(
                status.metering_mode
                for status in responses.values()
                )) > 1:
            logging.warning('Warning: multiple metering modes configured')
        if len(set(
                (status.hflip, status.vflip)
                for status in responses.values()
                )) > 1:
            logging.warning('Warning: multiple orientations configured')
        for address, status in responses.items():
            if (status.shutter_speed - min_speed) > 1000:
                logging.warning(
                    'Warning: shutter speed of %s deviates from min by >1ms',
                    address)
            if (status.timestamp - min_time).total_seconds() > self.time_delta:
                logging.warning(
                    'Warning: time delta of %s is >%.2fs',
                    address, self.time_delta)

    def complete_status(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)

    def do_resolution(self, arg):
        """
        Sets the resolution on the defined servers.

        Syntax: resolution <width>x<height> [addresses]

        The 'resolution' command is used to set the capture resolution of the
        camera on all or some of the defined servers. The resolution of the
        camera influences the capture mode that the camera uses. See the
        camera hardware[1] chapter of the picamera documentation for more
        information.

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        [1] http://picamera.readthedocs.org/en/latest/fov.html

        See also: status, framerate, shutter.

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
        self.client.resolution(
            width, height, self.parse_arg(arg[1] if len(arg) > 1 else None))

    def complete_resolution(self, text, line, start, finish):
        cmd_re = re.compile(r'resolution(?P<res> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('res') < finish <= match.end('res'):
            # Some common resolutions; this list isn't intended to be
            # exhaustive, just useful for completion
            resolutions = [
                '320x240',   # QVGA
                '640x480',   # VGA (NTSC)
                '768x576',   # PAL (4:3)
                '800x600',   # SVGA
                '1024x576',  # PAL (16:9)
                '1024x768',  # XGA
                '1280x720',  # HD 720
                '1680x1050', # WSXGA+
                '1920x1080', # HD 1080
                '2048x1536', # QXGA
                '2560x1440', # WQHD
                '2592x1944', # Full resolution
                ]
            return [
                resolution
                for resolution in resolutions
                if resolution.startswith(text)
                ]

    def do_framerate(self, arg):
        """
        Sets the framerate on the defined servers.

        Syntax: framerate <rate> [addresses]

        The 'framerate' command is used to set the capture framerate of the
        camera on all or some of the defined servers. The rate can be specified
        as an integer, a floating-point number, or as a fractional value. The
        framerate of the camera influences the capture mode that the camera
        uses. See the camera hardware[1] chapter of the picamera documentation
        for more information.

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        [1] http://picamera.readthedocs.org/en/latest/fov.html

        See also: status, resolution, shutter.

        cpi> framerate 30
        cpi> framerate 90 192.168.0.1
        cpi> framerate 15 192.168.0.1-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify a framerate')
        arg = arg.split(' ', 1)
        try:
            rate = fractions.Fraction(arg[0])
        except (TypeError, ValueError) as exc:
            raise CmdSyntaxError('Invalid framerate "%s"' % arg[0])
        self.client.framerate(
            rate, self.parse_arg(arg[1] if len(arg) > 1 else None))

    def complete_framerate(self, text, line, start, finish):
        cmd_re = re.compile(r'framerate(?P<rate> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('rate') < finish <= match.end('rate'):
            # Some common framerates; this list isn't intended to be
            # exhaustive, just useful for completion
            framerates = [
                '90',
                '60',
                '50',
                '48',
                '30',
                '25',
                '24',
                '23.976',
                '15',
                '1',
                ]
            return [
                framerate
                for framerate in framerates
                if framerate.startswith(text)
                ]

    def do_shutter(self, arg):
        """
        Sets the shutter speed on the defined servers.

        Syntax: shutter <speed> [addresses]

        The 'shutter' command is used to set the shutter speed of the camera on
        all or some of the defined servers. The speed can be specified as a
        floating-point number (in milli-seconds), or 'auto' which leaves the
        camera to determine the shutter speed. The framerate of the camera
        limits the shutter speed that can be set. For example, if framerate is
        30fps, then shutter speed cannot be slower than 33.333ms.

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status, resolution, framerate.

        cpi> shutter auto
        cpi> shutter 33.333 192.168.0.1
        cpi> shutter 100 192.168.0.1-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify a shutter speed')
        arg = arg.split(' ', 1)
        if arg[0].lower() == 'auto':
            speed = 0
        else:
            try:
                speed = int(float(arg[0]) * 1000)
            except ValueError:
                raise CmdSyntaxError('Invalid shutter speed "%s"' % arg[0])
        self.client.shutter_speed(
            speed, self.parse_arg(arg[1] if len(arg) > 1 else None))

    def complete_shutter(self, text, line, start, finish):
        cmd_re = re.compile(r'shutter(?P<speed> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('speed') < finish <= match.end('speed'):
            # Some common shutter speeds; this list isn't intended to be
            # exhaustive, just useful for completion
            speeds = [
                'auto',
                '16.666',
                '33.333',
                '100',
                '250',
                '500',
                '1000',
                ]
            return [
                speed
                for speed in speeds
                if speed.startswith(text)
                ]

    def do_awb(self, arg):
        """
        Sets the auto-white-balance (AWB) mode on the defined servers.

        Syntax: awb <mode> [addresses]

        The 'awb' command is used to set the AWB mode of the camera on all or
        some of the defined servers. The mode can be one of the following:

        auto, cloudy, flash, fluorescent, horizon, incandescent, shade,
        sunlight, tungsten

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status, exposure, metering.

        cpi> awb auto
        cpi> awb fluorescent 192.168.0.1
        cpi> awb sunlight 192.168.0.1-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify a mode')
        arg = arg.split(' ', 1)
        self.client.awb(
            arg[0].lower(),
            addresses=self.parse_arg(arg[1] if len(arg) > 1 else None))

    def complete_awb(self, text, line, start, finish):
        cmd_re = re.compile(r'awb(?P<mode> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('mode') < finish <= match.end('mode'):
            modes = [
                'auto',
                'cloudy',
                'flash',
                'fluorescent',
                'horizon',
                'incandescent',
                'shade',
                'sunlight',
                'tungsten',
                ]
            return [
                mode
                for mode in modes
                if mode.startswith(text)
                ]

    def do_exposure(self, arg):
        """
        Sets the exposure mode on the defined servers.

        Syntax: exposure <mode> [addresses]

        The 'exposure' command is used to set the exposure mode of the camera
        on all or some of the defined servers. The mode can be one of the
        following:

        antishake, auto, backlight, beach, fireworks, fixedfps, night,
        nightpreview, snow, sports, spotlight, verylong

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status, awb, metering.

        cpi> exposure auto
        cpi> exposure night 192.168.0.1
        cpi> exposure backlight 192.168.0.1-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify a mode')
        arg = arg.split(' ', 1)
        self.client.exposure(
            arg[0].lower(),
            addresses=self.parse_arg(arg[1] if len(arg) > 1 else None))

    def complete_exposure(self, text, line, start, finish):
        cmd_re = re.compile(r'exposure(?P<mode> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('mode') < finish <= match.end('mode'):
            modes = [
                'antishake',
                'auto',
                'backlight',
                'beach',
                'fireworks',
                'fixedfps',
                'night',
                'nightpreview',
                'snow',
                'sports',
                'spotlight',
                'verylong',
                ]
            return [
                mode
                for mode in modes
                if mode.startswith(text)
                ]

    def do_metering(self, arg):
        """
        Sets the metering mode on the defined servers.

        Syntax: metering <mode> [addresses]

        The 'metering' command is used to set the metering mode of the camera
        on all or some of the defined servers. The mode can be one of the
        following:

        average, backlit, matrix, spot

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status, awb, exposure.

        cpi> metering average
        cpi> metering spot 192.168.0.1
        cpi> metering backlit 192.168.0.1-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify a mode')
        arg = arg.split(' ', 1)
        self.client.metering(
            arg[0].lower(),
            addresses=self.parse_arg(arg[1] if len(arg) > 1 else None))

    def complete_metering(self, text, line, start, finish):
        cmd_re = re.compile(r'metering(?P<mode> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('mode') < finish <= match.end('mode'):
            modes = [
                'average',
                'backlit',
                'matrix',
                'spot',
                ]
            return [
                mode
                for mode in modes
                if mode.startswith(text)
                ]

    def do_iso(self, arg):
        """
        Sets the ISO value on the defined servers.

        Syntax: iso <value> [addresses]

        The 'iso' command is used to set the emulated ISO value of the camera
        on all or some of the defined servers. The value can be specified as an
        integer number between 0 and 1600, or 'auto' which leaves the camera to
        determine the optimal ISO value.

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status, exposure.

        cpi> iso auto
        cpi> iso 100 192.168.0.1
        cpi> iso 800 192.168.0.1-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify an ISO value')
        arg = arg.split(' ', 1)
        if arg[0].lower() == 'auto':
            iso = 0
        else:
            try:
                iso = int(arg[0])
            except ValueError:
                raise CmdSyntaxError('Invalid ISO value "%s"' % arg[0])
        self.client.iso(
            value, self.parse_arg(arg[1] if len(arg) > 1 else None))

    def complete_iso(self, text, line, start, finish):
        cmd_re = re.compile(r'iso(?P<value> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('value') < finish <= match.end('value'):
            # Some common ISO values; this list isn't intended to be
            # exhaustive, just useful for completion
            values = [
                'auto',
                '100',
                '200',
                '400',
                '800',
                '1600',
                ]
            return [
                value
                for value in values
                if value.startswith(text)
                ]

    def do_levels(self, arg):
        """
        Sets the brightness, contrast, and saturation on the defined servers.

        Syntax: levels <brightness> <contrast> <saturation> [addresses]

        The 'levels' command is used to simultaneously set the brightness,
        contrast, and saturation levels on all or some of the defined servers.
        Each level is specified as an integer number between 0 and 100. The
        default for each level is 50.

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status.

        cpi> levels 50 50 50
        cpi> levels 70 50 50 192.168.0.1
        cpi> levels 40 60 70 192.168.0.1-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify any levels')
        arg = arg.split(' ', 3)
        values = {}
        for index, name in enumerate(('brightness', 'contrast', 'saturation')):
            try:
                value = int(arg[index])
                if not (0 <= value <= 100):
                    raise ValueError('Out of range')
            except ValueError:
                raise CmdSyntaxError('Invalid %s "%s"' % (name, arg[index]))
            if index > 0:
                # Contrast and saturation are actually from -100..100, but
                # we're keeping the interface simple...
                values[name] = (value * 2) - 100
            else:
                values[name] = value
        self.client.flip(
            values['brightness'], values['contrast'], values['saturation'],
            self.parse_arg(arg[3] if len(arg) > 3 else None))

    def complete_levels(self, text, line, start, finish):
        cmd_re = re.compile(r'levels(?P<values>( +[^ ]+){,3}(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('values') < finish <= match.end('values'):
            # No completions for levels
            return []

    def do_flip(self, arg):
        """
        Sets the picture orientation on the defined servers.

        Syntax: flip <value> [addresses]

        The 'flip' command is used to set the picture orientation on all or
        some of the defined servers. The following values can be specified:

        none, horizontal, vertical, both

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status.

        cpi> flip none
        cpi> flip vertical 192.168.0.1
        cpi> flip both 192.168.0.1-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify an orientation')
        arg = arg.split(' ', 1)
        try:
            hflip, vflip = {
                'none':       (False, False),
                'horizontal': (True,  False),
                'horz':       (True,  False),
                'vertical':   (False, True),
                'vert':       (False, True),
                'both':       (True,  True),
                }[arg[0].lower()]
        except KeyError:
            raise CmdSyntaxError('Invalid orientation "%s"' % arg[0])
        self.client.flip(
            hflip, vflip, self.parse_arg(arg[1] if len(arg) > 1 else None))

    def complete_flip(self, text, line, start, finish):
        cmd_re = re.compile(r'flip(?P<value> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('value') < finish <= match.end('value'):
            values = [
                'none',
                'horizontal',
                'vertical',
                'both',
                ]
            return [
                value
                for value in values
                if value.startswith(text)
                ]

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

        See also: download, clear.

        cpi> capture
        cpi> capture 192.168.0.1
        cpi> capture 192.168.0.50-192.168.0.53
        """
        self.client.capture(
            self.capture_count, self.video_port, self.capture_delay,
            self.parse_arg(arg))

    def complete_capture(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)

    def do_download(self, arg=''):
        """
        Downloads captured images from the defined servers.

        Syntax: download [addresses]

        The 'download' command causes each server to send its captured images
        to the client. Servers are contacted consecutively to avoid saturating
        the network bandwidth. Once images are successfully downloaded from a
        server, they are wiped from the server.

        See also: capture, clear.

        cpi> download
        cpi> download 192.168.0.1
        """
        responses = self.client.list(self.parse_arg(arg))
        for (address, images) in responses.items():
            for image in images:
                filename = '{ts:%Y%m%d-%H%M%S%f}-{addr}.jpg'.format(
                        ts=image.timestamp, addr=address)
                with io.open(os.path.join(self.output, filename), 'wb') as output:
                    self.client.download(address, image.index, output)
                    if output.tell() != image.size:
                        raise CmdError('Wrong size for image %s' % filename)
                logging.info('Downloaded %s' % filename)
        self.client.clear(self.parse_arg(arg))

    def complete_download(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)

    def do_clear(self, arg):
        """
        Clear the image store on the specified servers.

        Syntax: clear [addresses]

        The 'clear' command can be used to clear the in-memory image store
        on the specified Pi servers (or all Pi servers if no address is
        given). The 'download' command automatically clears the image store
        after successful transfers so this command is only useful in the case
        that the operator wants to discard images without first downloading
        them.

        See also: download, capture.

        cpi> clear
        cpi> clear 192.168.0.1-192.168.0.10
        """
        self.client.clear(self.parse_arg(arg))

    def complete_clear(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)

    def do_identify(self, arg):
        """
        Blink the LED on the specified servers.

        Syntax: identify [addresses]

        The 'identify' command can be used to locate a specific Pi server (or
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
        self.client.identify(self.parse_arg(arg))

    def complete_identify(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)


main = CompoundPiClientApplication()

