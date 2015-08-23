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
import time

from . import __version__
from .ipaddress import IPv4Address, IPv4Network
from .client import CompoundPiClient
from .terminal import TerminalApplication
from .cmdline import Cmd, CmdSyntaxError, CmdError, ENCODING
from .exc import CompoundPiClientError


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

def record_format(s):
    s = s.strip().lower()
    try:
        return {
            'h264':  'h264',
            'mjpeg': 'mjpeg',
            'mjpg':  'mjpeg',
            }[s]
    except KeyError:
        raise ValueError('%s is not a valid recording format')

def numeric_range(conversion, inclusive=True, min_value=None, max_value=None):
    def test(value):
        result = conversion(value)
        if inclusive:
            if min_value is not None and result < min_value:
                raise ValueError('Value must be %s or more' % min_value)
            if max_value is not None and result > max_value:
                raise ValueError('Value must be %s or less' % max_value)
        else:
            if min_value is not None and result <= min_value:
                raise ValueError('Value must be greater than %s' % min_value)
            if max_value is not None and result >= max_value:
                raise ValueError('Value must be less than %s' % max_value)
        return result
    return test

network_timeout = numeric_range(conversion=int, min_value=1)
capture_count = numeric_range(conversion=int, min_value=1)
capture_quality = numeric_range(conversion=int, min_value=1, max_value=100)
time_delay = numeric_range(conversion=float, min_value=0.0)
time_delta = numeric_range(conversion=float, inclusive=False, min_value=0.0)
record_quality = numeric_range(conversion=int, min_value=0, max_value=100)
record_bitrate = numeric_range(conversion=int, min_value=1, max_value=25000000)
record_intra_period = numeric_range(conversion=int, min_value=0)

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
            '-t', '--timeout', type=network_timeout,
            default='15', metavar='SECS',
            help='specifies the timeout (in seconds) for network '
            'transactions (default: %(default)s)')
        self.parser.add_argument(
            '--capture-delay', type=time_delay, default='0.0', metavar='SECS',
            help='specifies the delay (in seconds) used to synchronize '
            'captures. This must be less than the network delay '
            '(default: %(default)s)')
        self.parser.add_argument(
            '--capture-quality', type=capture_quality, default='85', metavar='NUM',
            help='specifies the quality that the codec should attempt to '
            'maintain in image captures (default: %(default)s)')
        self.parser.add_argument(
            '--capture-count', type=capture_count, default='1', metavar='NUM',
            help='specifies the number of consecutive pictures to capture '
            'when requested (default: %(default)s)')
        self.parser.add_argument(
            '--video-port', action='store_true', default=False,
            help="if specified, use the camera's video port for rapid capture")
        self.parser.add_argument(
            '--record-format', type=record_format, default='h264', metavar='FMT',
            help='specifies the codec to use for video recordings '
            '(default: %(default)s)')
        self.parser.add_argument(
            '--record-quality', type=record_quality, default='0', metavar='NUM',
            help='specifies the quality that the codec should attempt to '
            'maintain in video recordings (default: %(default)s)')
        self.parser.add_argument(
            '--record-bitrate', type=record_bitrate, default='17000000', metavar='NUM',
            help='specifies the bitrate cap applied to the video codec when '
            'recording (default: %(default)s)')
        self.parser.add_argument(
            '--record-motion', action='store_true', default=False,
            help='specifies whether motion vector estimation data should be '
            'recorded with video (only valid for h264 format, '
            'default: %(default)s)')
        self.parser.add_argument(
            '--record-delay', type=time_delay, default='0.0', metavar='SECS',
            help='specifies the delay (in seconds) used to synchronize '
            'recordings. This must be less than the network delay '
            '(default: %(default)s)')
        self.parser.add_argument(
            '--record-intra-period', type=record_intra_period, default='30', metavar='FRAMES',
            help='specifies the number of images in a GOP when recording in '
            'h264 format (default: %(default)s)')
        self.parser.add_argument(
            '--time-delta', type=time_delta, default='0.25', metavar='SECS',
            help='specifies the maximum delta between server timestamps that '
            'the client will tolerate (default: %(default)ss)')
        self.parser.set_defaults(log_level=logging.INFO)

    def main(self, args):
        proc = CompoundPiCmd()
        proc.client.servers.network = args.network
        proc.client.servers.port = args.port
        proc.client.servers.timeout = args.timeout
        proc.client.bind = args.bind
        proc.capture_delay = args.capture_delay
        proc.capture_quality = args.capture_quality
        proc.capture_count = args.capture_count
        proc.video_port = args.video_port
        proc.record_format = args.record_format
        proc.record_quality = args.record_quality
        proc.record_bitrate = args.record_bitrate
        proc.record_motion = args.record_motion
        proc.record_delay = args.record_delay
        proc.record_intra_period = args.record_intra_period
        proc.time_delta = args.time_delta
        proc.output = args.output
        proc.cmdloop()


class CompoundPiProgress(object):
    def __init__(self, stdout):
        self.stdout = stdout
        self.count = 0
        self.output = None

    def start(self, count):
        self.count = count
        self.output = ''
        self.update(0)

    def clear(self):
        l = len(self.output)
        self.stdout.write((b'\b' * l) + (b' ' * l) + (b'\b' * l))
        self.stdout.flush()

    def update(self, count):
        self.clear()
        percent_complete = (count * 100) // self.count
        self.output = '[%-25s] %d%%' % (
            '#' * (percent_complete // 4), percent_complete)
        self.stdout.write(self.output.encode(ENCODING))
        self.stdout.flush()

    def finish(self):
        self.clear()
        self.count = 0
        self.output = None


class CompoundPiCmd(Cmd):
    prompt = 'cpi> '

    def __init__(self):
        Cmd.__init__(self)
        self.pprint('CompoundPi Client version %s' % __version__)
        self.pprint(
            'Type "help" for more information, '
            'or "find" to locate Pi servers')
        self.client = CompoundPiClient(CompoundPiProgress(self.stdout))
        self.capture_delay = 0.0
        self.capture_count = 1
        self.capture_quality = 85
        self.video_port = False
        self.record_format = 'h264'
        self.record_quality = 20
        self.record_bitrate = 17000000
        self.record_motion = False
        self.record_delay = 0.0
        self.record_intra_period = 30
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
        self.client.close()

    def onecmd(self, line):
        # Don't crash'n'burn for standard client errors
        try:
            return Cmd.onecmd(self, line)
        except CompoundPiClientError as exc:
            self.pprint(str(exc) + '\n')

    def parse_address(self, s):
        try:
            a = IPv4Address(s.strip())
        except ValueError:
            raise CmdSyntaxError('Invalid address "%s"' % s)
        if not a in self.client.servers.network:
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

    def parse_addresses(self, arg=None):
        if arg:
            return self.parse_address_list(arg)
        elif not len(self.client.servers):
            raise CmdError(
                    "You must define servers first (see help for 'find' "
                    "and 'add')")

    def complete_server(self, text, line, start, finish):
        return [
            str(server)
            for server in self.client.servers
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
                ('Setting',             'Value'),
                ('network',             self.client.servers.network),
                ('port',                self.client.servers.port),
                ('timeout',             self.client.servers.timeout),
                ('bind',                '%s:%d' % self.client.bind),
                ('capture_delay',       self.capture_delay),
                ('capture_quality',     self.capture_quality),
                ('capture_count',       self.capture_count),
                ('video_port',          self.video_port),
                ('record_delay',        self.record_delay),
                ('record_format',       self.record_format),
                ('record_quality',      self.record_quality),
                ('record_bitrate',      self.record_bitrate),
                ('record_motion',       self.record_motion),
                ('record_intra_period', self.record_intra_period),
                ('time_delta',          self.time_delta),
                ('output',              self.output),
                ('warnings',            self.warnings),
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
                'network':             network,
                'port':                service,
                'bind':                address,
                'timeout':             network_timeout,
                'capture_delay':       time_delay,
                'capture_count':       capture_count,
                'capture_quality':     capture_quality,
                'record_delay':        time_delay,
                'record_format':       record_format,
                'record_quality':      record_quality,
                'record_bitrate':      record_bitrate,
                'record_motion':       boolean,
                'record_intra_period': record_intra_period,
                'video_port':          boolean,
                'time_delta':          time_delta,
                'output':              path,
                'warnings':            boolean,
                }[name](value)
        except KeyError:
            raise CmdSyntaxError('Invalid configuration variable: %s' % name)
        except ValueError as e:
            raise CmdSyntaxError(e)
        if name in ('network', 'port', 'timeout'):
            setattr(self.client.servers, name, value)
        elif name in ('bind',):
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
            elif (
                    name.startswith('video_port') or
                    name.startswith('warnings') or
                    name.startswith('record_motion')):
                values = ['on', 'off', 'true', 'false', 'yes', 'no', '0', '1']
                return [value for value in values if value.startswith(text)]
            elif name.startswith('record_format'):
                values = ['h264', 'mjpeg']
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
                'capture_quality',
                'capture_count',
                'video_port',
                'record_delay',
                'record_format',
                'record_quality',
                'record_bitrate',
                'record_motion',
                'record_intra_period',
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
        if not len(self.client.servers):
            self.pprint('No servers are defined')
        else:
            self.pprint_table(
                [('Address',)] +
                [(server,) for server in self.client.servers]
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
        self.client.servers.find(count)
        if not len(self.client.servers):
            raise CmdError('Failed to find any servers')
        logging.info('Found %d servers' % len(self.client.servers))

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
        for addr in self.parse_address_list(arg):
            self.client.servers.append(addr)

    def complete_add(self, text, line, start, finish):
        return [
            str(server)
            for server in self.client.servers.network
            if server not in self.client.servers
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
        for addr in self.parse_address_list(arg):
            try:
                self.client.servers.remove(addr)
            except ValueError:
                logging.warning('%s was not in the server list', addr)

    def complete_remove(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)

    def do_move(self, arg):
        """
        Move addresses within the list of servers.

        Syntax: move <address> (top|bottom|to <index>|(above|below) <address>)

        The 'move' command is used to move a server to another position within
        the server list. The first address specified is moved to the position
        described by the subsequent parameters. The 'top', 'bottom', and
        'to' arguments specify absolute positions. Alternatively, 'above'
        and 'below' can be used to specify a position relative to another
        address.
        """
        match = re.match(
                r' *(?P<addr>[^ ]+)'
                r' *(?P<pos>top|bottom|to|above|below)'
                r' *(?P<location>[^ ]+)?', arg.lower())
        if not match:
            raise CmdSyntaxError(
                    'You must specify an address and a new position')
        addr = self.parse_address(match.group('addr'))
        if not addr in self.client.servers:
            raise CmdSyntaxError('%s is not in the server list' % addr)
        pos = match.group('pos')
        location = match.group('location')
        if pos in ('top', 'bottom'):
            if location is not None:
                raise CmdSyntaxError(
                        'You cannot specify anything after top/bottom')
            location = 0 if pos == 'top' else len(self.client.servers)
        elif pos in ('above', 'below'):
            location = self.parse_address(location)
            if not location in self.client.servers:
                raise CmdSyntaxError('%s is not in the server list' % location)
            location = self.client.servers.index(location)
            if pos == 'after':
                location += 1
        elif pos == 'to':
            try:
                location = int(location)
            except ValueError:
                raise CmdSyntaxError(
                        'Invalid location for "to": "%s"' % location)
        else:
            raise CmdSyntaxError('Invalid location specification: "%s"' % pos)
        self.client.servers.move(location, addr)

    def complete_move(self, text, line, start, finish):
        cmd_re = re.compile(r'move(?P<addr> +[^ ]+(?P<pos> +[^ ]+(?P<location> +[^ ]+)?)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('location') < finish <= match.end('location'):
            pos = match.group('pos').strip()
            if pos.startswith('top') or pos.startswith('bottom'):
                return []
            elif pos.startswith('to'):
                names = [str(i) for i in range(len(self.client.servers))]
                return [name for name in names if name.startswith(text)]
            else:
                return self.complete_server(text, line, start, finish)
        elif match.start('pos') < finish <= match.end('pos'):
            names = [
                'top',
                'bottom',
                'above',
                'below',
                'to',
                ]
            return [name + ' ' for name in names if name.startswith(text)]
        elif match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)

    def do_sort(self, arg=''):
        """
        Sorts the list of servers numerically.

        Syntax: sort [reverse]

        The 'sort' command is used to sort the list of defined servers
        numerically forwards or, if "reverse" is specified, backwards.

        See also: add, remove, find.

        cpi> sort
        cpi> sort reverse
        """
        if arg == 'reverse':
            reverse = True
        elif arg:
            raise CmdSyntaxError('Unexpected argument "%s"' % arg)
        else:
            reverse = False
        self.client.servers.sort(reverse=reverse)

    def complete_sort(self, text, line, start, finish):
        cmd_re = re.compile(r'sort(?P<reverse> +[^ ]+)?')
        match = cmd_re.match(line)
        assert match
        if match.start('reverse') < finish <= match.end('reverse'):
            return ['reverse'] if 'reverse'.startswith(text) else []

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
        responses = self.client.status(self.parse_addresses(arg))
        min_time = min(status.timestamp for status in responses.values())
        self.pprint_table(
            [
                (
                    'Address',
                    'Mode',
                    'AGC',
                    'AWB',
                    'Exp',
                    'Meter',
                    'Flip',
                    'Clock',
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
                    '%s (%.1f,%.1f)' % (
                        status.agc_mode,
                        status.agc_analog,
                        status.agc_digital,
                        ),
                    '%s (%.1f,%.1f)' % (
                        status.awb_mode,
                        status.awb_red,
                        status.awb_blue,
                        ),
                    '%s (%.2fms)' % (
                        status.exposure_mode,
                        status.exposure_speed,
                        ),
                    status.metering_mode,
                    (
                        'both' if status.vflip and status.hflip else
                        'vert' if status.vflip else
                        'horz' if status.hflip else
                        'none'
                        ),
                    status.timestamp - min_time,
                    status.files,
                    )
                for address in self.client.servers
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
                status.agc_mode
                for status in responses.values()
                )) > 1:
            logging.warning('Warning: multiple gain-control modes configured')
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
            width, height, self.parse_addresses(arg[1] if len(arg) > 1 else None))

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
            rate, self.parse_addresses(arg[1] if len(arg) > 1 else None))

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

    def do_agc(self, arg):
        """
        Sets the auto-gain-control (AGC) mode on the defined servers.

        Syntax: agc <mode> [addresses]

        The 'agc' command is used to set the AGC mode of the camera on all or
        some of the defined servers. The mode can be one of the following:

        antishake, auto, backlight, beach, fireworks, fixedfps, night,
        nightpreview, off, snow, sports, spotlight, verylong

        If 'off' is specified, the current sensor gains of the camera will
        be fixed at their present values (unfortunately there is no way at
        the moment to manually specify the gain values).

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status, awb, exposure, metering.

        cpi> agc auto
        cpi> agc backlight 192.168.0.1
        cpi> agc antishake 192.168.0.1-192.168.0.10
        cpi> agc off
        cpi> agc off 192.168.0.1
        """
        if not arg:
            raise CmdSyntaxError('You must specify a mode')
        arg = arg.split(' ', 1)
        self.client.agc(
                arg[0].lower(),
                addresses=self.parse_addresses(arg[1] if len(arg) > 1 else None))

    def complete_agc(self, text, line, start, finish):
        cmd_re = re.compile(r'agc(?P<mode> +[^ ]+(?P<addr> +.*)?)?')
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
                'off',
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

    def do_awb(self, arg):
        """
        Sets the auto-white-balance (AWB) mode on the defined servers.

        Syntax: awb (<mode>|<red-gain>,<blue-gain>) [addresses]

        The 'awb' command is used to set the AWB mode of the camera on all or
        some of the defined servers. The mode can be one of the following:

        auto, cloudy, flash, fluorescent, horizon, incandescent, shade,
        sunlight, tungsten

        Alternatively you can specify two comma-separated floating-point
        numbers which specify the red and blue gains manually (between 0.0 and
        8.0).

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status, exposure, metering.

        cpi> awb auto
        cpi> awb fluorescent 192.168.0.1
        cpi> awb sunlight 192.168.0.1-192.168.0.10
        cpi> awb 1.8,1.5
        cpi> awb 1.0,1.0 192.168.0.1
        """
        if not arg:
            raise CmdSyntaxError('You must specify a mode')
        arg = arg.split(' ', 1)
        if re.match(r'[a-z]+', arg[0]):
            self.client.awb(
                arg[0].lower(),
                addresses=self.parse_addresses(arg[1] if len(arg) > 1 else None))
        else:
            try:
                red_gain, blue_gain = (float(f) for f in arg[0].split(',', 1))
            except ValueError:
                raise CmdSyntaxError('Invalid red/blue gains: %s' % arg[0])
            self.client.awb(
                'off', red_gain, blue_gain,
                addresses=self.parse_addresses(arg[1] if len(arg) > 1 else None))

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

        Syntax: exposure (auto|<speed>) [addresses]

        The 'exposure' command is used to set the exposure mode of the camera
        on all or some of the defined servers. The mode can be 'auto' or a
        speed measured in ms. Please note that exposure speed is limited by
        framerate.

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status, awb, metering.

        cpi> exposure auto
        cpi> exposure 30 192.168.0.1
        cpi> exposure auto 192.168.0.1-192.168.0.10
        """
        if not arg:
            raise CmdSyntaxError('You must specify a mode')
        arg = arg.split(' ', 1)
        if re.match(r'[a-z]+', arg[0]):
            self.client.exposure(
                arg[0].lower(),
                addresses=self.parse_addresses(arg[1] if len(arg) > 1 else None))
        else:
            try:
                speed = float(arg[0])
            except ValueError:
                raise CmdSyntaxError('Invalid exposure speed: %s' % arg[0])
            self.client.exposure(
                'off', speed,
                addresses=self.parse_addresses(arg[1] if len(arg) > 1 else None))

    def complete_exposure(self, text, line, start, finish):
        cmd_re = re.compile(r'exposure(?P<mode> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('mode') < finish <= match.end('mode'):
            modes = [
                'auto',
                ]
            speeds = [
                '16.666',
                '33.333',
                '100',
                '250',
                '500',
                '1000',
                ]
            return [
                s
                for s in modes + speeds
                if s.startswith(text)
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
            addresses=self.parse_addresses(arg[1] if len(arg) > 1 else None))

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
            value = 0
        else:
            try:
                value = int(arg[0])
            except ValueError:
                raise CmdSyntaxError('Invalid ISO value "%s"' % arg[0])
        self.client.iso(
            value, self.parse_addresses(arg[1] if len(arg) > 1 else None))

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

    def do_brightness(self, arg):
        """
        Sets the brightness on the defined servers.

        Syntax: brightness <value> [addresses]

        The 'brightness' command is used to adjust the brightness level on all
        or some of the defined servers. Brightness is specified as an integer
        number between 0 and 100 (default 50).

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: contrast, saturation, ev.

        cpi> brightness 50
        cpi> brightness 75 192.168.0.1
        """
        if not arg:
            raise CmdSyntaxError('You must specify an brightness value')
        arg = arg.split(' ', 1)
        try:
            value = int(arg[0])
            if not (0 <= value <= 100):
                raise ValueError('Out of range')
        except ValueError:
            raise CmdSyntaxError('Invalid brightness value "%s"' % arg[0])
        self.client.brightness(
            value, self.parse_addresses(arg[1] if len(arg) > 1 else None))

    def complete_brightness(self, text, line, start, finish):
        cmd_re = re.compile(r'brightness(?P<value> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('value') < finish <= match.end('value'):
            # No completions for value
            return []

    def do_contrast(self, arg):
        """
        Sets the contrast on the defined servers.

        Syntax: contrast <value> [addresses]

        The 'contrast' command is used to adjust the contrast level on all
        or some of the defined servers. Contrast is specified as an integer
        number between -100 and 100 (default 0).

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: brightness, saturation, ev.

        cpi> contrast 0
        cpi> contrast -50 192.168.0.1
        """
        if not arg:
            raise CmdSyntaxError('You must specify an contrast value')
        arg = arg.split(' ', 1)
        try:
            value = int(arg[0])
            if not (-100 <= value <= 100):
                raise ValueError('Out of range')
        except ValueError:
            raise CmdSyntaxError('Invalid contrast value "%s"' % arg[0])
        self.client.contrast(
            value, self.parse_addresses(arg[1] if len(arg) > 1 else None))

    def complete_contrast(self, text, line, start, finish):
        cmd_re = re.compile(r'contrast(?P<value> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('value') < finish <= match.end('value'):
            # No completions for value
            return []

    def do_saturation(self, arg):
        """
        Sets the saturation on the defined servers.

        Syntax: saturation <value> [addresses]

        The 'saturation' command is used to adjust the saturation level on all
        or some of the defined servers. Saturation is specified as an integer
        number between -100 and 100 (default 0).

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: brightness, contrast, ev.

        cpi> saturation 0
        cpi> saturation -50 192.168.0.1
        """
        if not arg:
            raise CmdSyntaxError('You must specify an saturation value')
        arg = arg.split(' ', 1)
        try:
            value = int(arg[0])
            if not (-100 <= value <= 100):
                raise ValueError('Out of range')
        except ValueError:
            raise CmdSyntaxError('Invalid saturation value "%s"' % arg[0])
        self.client.saturation(
            value, self.parse_addresses(arg[1] if len(arg) > 1 else None))

    def complete_saturation(self, text, line, start, finish):
        cmd_re = re.compile(r'saturation(?P<value> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('value') < finish <= match.end('value'):
            # No completions for value
            return []

    def do_ev(self, arg):
        """
        Sets the exposure compensation (EV) on the defined servers.

        Syntax: ev <value> [addresses]

        The 'ev' command is used to adjust the exposure compensation (EV) level
        on all or some of the defined servers. Exposure compensation is
        specified as an integer number between -24 and 24 where each increment
        represents 1/6th of a stop. Hence, 12 indicates that camera should
        overexpose by 2 stops. The default EV is 0.

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: brightness, contrast, saturation.

        cpi> ev 0
        cpi> ev 6 192.168.0.1
        """
        if not arg:
            raise CmdSyntaxError('You must specify an EV value')
        arg = arg.split(' ', 1)
        try:
            value = int(arg[0])
            if not (-24 <= value <= 24):
                raise ValueError('Out of range')
        except ValueError:
            raise CmdSyntaxError('Invalid EV value "%s"' % arg[0])
        self.client.ev(
            value, self.parse_addresses(arg[1] if len(arg) > 1 else None))

    def complete_ev(self, text, line, start, finish):
        cmd_re = re.compile(r'ev(?P<value> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('value') < finish <= match.end('value'):
            # No completions for value
            return []

    def do_denoise(self, arg):
        """
        Sets whether denoise will be applied to captures on the defined servers.

        Syntax: denoise <value> [addresses]

        The 'denoise' command is used to set whether the camera's software
        denoise algorithm is active when capturing. The follow values can be
        specified:

        on, off

        If no address is specified then all currently defined servers will be
        targetted. Multiple addresses can be specified with dash-separated
        ranges, comma-separated lists, or any combination of the two.

        See also: status.

        cpi> denoise off
        cpi> denoise on 192.168.0.3
        """
        if not arg:
            raise CmdSyntaxError('You must specify a denoise value')
        arg = arg.split(' ', 1)
        self.client.denoise(self.parse_bool(arg[0]),
            self.parse_addresses(arg[1] if len(arg) > 1 else None))

    def complete_denoise(self, text, line, start, finish):
        cmd_re = re.compile(r'denoise(?P<value> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('value') < finish <= match.end('value'):
            values = [
                'false',
                'true',
                'no',
                'yes',
                'off',
                'on',
                ]
            return [
                value
                for value in values
                if value.startswith(text)
                ]

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
            hflip, vflip, self.parse_addresses(arg[1] if len(arg) > 1 else None))

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

        See also: record, download, clear.

        cpi> capture
        cpi> capture 192.168.0.1
        cpi> capture 192.168.0.50-192.168.0.53
        """
        self.client.capture(
            self.capture_count, self.video_port, self.capture_quality,
            self.capture_delay, self.parse_addresses(arg))

    def complete_capture(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)

    def do_record(self, arg):
        """
        Record video from the defined servers.

        Syntax: record <length> [addresses]

        The 'record' command causes the servers to record video. Note that this
        does not cause the recorded video to be sent to the client. See the
        'download' command for more information. The length of time to record
        for is specified as a number of seconds.

        If no addresses are specified, a broadcast message to all defined
        servers will be used in which case the timestamp of the recorded video
        are likely to be extremely close together. If addresses are specified,
        unicast messages will be sent to each server in turn.  While this is
        still reasonably quick there will be a measurable difference between
        the timestamps of the last and first recordings.

        See also: capture, download, clear.

        cpi> record 5
        cpi> record 10 192.168.0.1
        cpi> record 2.5 192.168.0.50-192.168.0.53
        """
        if not arg:
            raise CmdSyntaxError('You must specify a recording length')
        arg = arg.split(' ', 1)
        try:
            length = float(arg[0])
            if length <= 0.0:
                raise ValueError('Out of range')
        except ValueError:
            raise CmdSyntaxError('Invalid recording length "%s"' % arg[0])
        self.client.record(
            length, self.record_format, self.record_quality,
            self.record_bitrate, self.record_intra_period, self.record_motion,
            self.record_delay,
            self.parse_addresses(arg[1] if len(arg) > 1 else None))

    def complete_record(self, text, line, start, finish):
        cmd_re = re.compile(r'record(?P<length> +[^ ]+(?P<addr> +.*)?)?')
        match = cmd_re.match(line)
        assert match
        if match.start('addr') < finish <= match.end('addr'):
            return self.complete_server(text, line, start, finish)
        elif match.start('length') < finish <= match.end('length'):
            # No completions for length
            return []

    def do_download(self, arg=''):
        """
        Downloads captured files from the defined servers.

        Syntax: download [addresses]

        The 'download' command causes each server to send its captured files to
        the client. Servers are contacted consecutively to avoid saturating the
        network bandwidth. Once all files are successfully downloaded from all
        servers, all servers are wiped clean.

        See also: capture, clear.

        cpi> download
        cpi> download 192.168.0.1
        """
        responses = self.client.list(self.parse_addresses(arg))
        for (address, files) in responses.items():
            for f in files:
                filename = '{ts:%Y%m%d-%H%M%S%f}-{addr}.{ext}'.format(
                        ts=f.timestamp, addr=address, ext={
                            'IMAGE': 'jpg',
                            'VIDEO': 'h264',
                            'MOTION': 'motion',
                            }[f.filetype])
                with io.open(os.path.join(self.output, filename), 'wb') as output:
                    self.client.download(address, f.index, output)
                    if output.tell() != f.size:
                        raise CmdError('Wrong size for file %s' % filename)
                logging.info('Downloaded %s' % filename)
        self.client.clear(self.parse_addresses(arg))

    def complete_download(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)

    def do_clear(self, arg):
        """
        Clear the file store on the specified servers.

        Syntax: clear [addresses]

        The 'clear' command can be used to clear the in-memory file store on
        the specified Pi servers (or all Pi servers if no address is given).
        The 'download' command automatically clears the file store after
        successful transfers so this command is only useful in the case that
        the operator wants to discard files without first downloading them.

        See also: download, capture.

        cpi> clear
        cpi> clear 192.168.0.1-192.168.0.10
        """
        self.client.clear(self.parse_addresses(arg))

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
        self.client.identify(self.parse_addresses(arg))

    def complete_identify(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)

    def do_reference(self, arg):
        """
        Copy the settings of a reference server to all others.

        Syntax: reference <address>

        The 'reference' command can be used to duplicate the settings of the
        specified Pi server to all other currently known servers. This is
        particularly useful when one is trying to produce shots that are as
        close as possible to the output of the selected reference server.

        A single address must be specified, from which settings will be
        obtained, after which broadcasts will be used to update the settings on
        all currently defined servers.

        See also: status, servers.

        cpi> reference 192.168.0.10
        """
        addr = self.parse_address(arg)
        status = self.client.status([addr])[addr]
        # Before we go setting resolution and framerate (which will reset the
        # cameras, ensure AGC gains are allowed to float)
        logging.info('Setting resolution and framerate')
        self.client.agc('auto')
        self.client.resolution(*status.resolution)
        self.client.framerate(status.framerate)
        logging.info('Setting white balance')
        if status.awb_mode == 'off':
            self.client.awb('off', status.awb_red, status.awb_blue)
        else:
            self.client.awb(status.awb_mode)
        logging.info('Setting gain algorithm')
        if status.agc_mode == 'off':
            logging.info('Pausing for camera gains to settle')
            # We've just reset the resolution and framerate which has reset all
            # the cameras. Given we can't directly set the gains we need to
            # wait a decent number of frames to let the gains settle before we
            # disable AGC. Here we wait long enough for 30 frames to have
            # been captured (1 second at "normal" framerates)
            time.sleep(30.0 / status.framerate)
            self.client.agc('off')
        else:
            self.client.agc(status.agc_mode)
        logging.info('Setting exposure speed')
        if status.exposure_mode == 'off':
            self.client.exposure('off', status.exposure_speed)
        else:
            self.client.exposure(status.exposure_mode)
        self.client.ev(status.ev)
        logging.info('Setting ISO and metering')
        self.client.iso(status.iso)
        self.client.metering(status.metering_mode)
        logging.info('Setting levels')
        self.client.brightness(status.brightness)
        self.client.contrast(status.contrast)
        self.client.saturation(status.saturation)
        logging.info('Setting denoise')
        self.client.denoise(status.denoise)
        logging.info('Setting orientation')
        self.client.flip(status.hflip, status.vflip)

    def complete_reference(self, text, line, start, finish):
        return self.complete_server(text, line, start, finish)


main = CompoundPiClientApplication()

