# vim: set et sw=4 sts=4 fileencoding=utf-8:
#
# Copyright 2014 Dave Hughes <dave@waveform.org.uk>.
#
# This file is part of compoundpi.
#
# compoundpi is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) any later
# version.
#
# compoundpi is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# compoundpi.  If not, see <http://www.gnu.org/licenses/>.

"Tests for the server component of Compound Pi"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')


import sys
import os
import io
import time
import signal
from fractions import Fraction

import pytest
from mock import Mock, MagicMock, patch, sentinel, call

# Several of the modules that CompoundPiServer relies upon are Raspberry Pi
# specific (can't be installed on other platforms) so we need to mock them
# out before performing attempting to import compoundpi.server
daemon_mock = Mock()
runner_mock = Mock()
picamera_mock = Mock()
rpi_mock = Mock()
gpio_mock = Mock()
with patch.dict('sys.modules', {
        'daemon':        daemon_mock,
        'daemon.runner': runner_mock,
        'picamera':      picamera_mock,
        'RPi':           rpi_mock,
        'RPi.GPIO':      gpio_mock,
    }):
    import compoundpi
    import compoundpi.common
    import compoundpi.server
    import compoundpi.exc

    def test_service():
        assert compoundpi.server.service('5000') == 5000
        with patch('socket.getservbyname') as m:
            m.return_value = 22
            assert compoundpi.server.service('ssh') == 22

    def test_address():
        with patch('socket.getaddrinfo') as m:
            m.return_value = [(2, 2, 17, '', ('127.0.0.1', 0))]
            assert compoundpi.server.address('localhost') == '127.0.0.1'

    def test_user():
        assert compoundpi.server.user('1000') == 1000
        with patch('pwd.getpwnam') as m:
            m.return_value = Mock()
            m.return_value.pw_uid = 0
            assert compoundpi.server.user('root') == 0

    def test_group():
        assert compoundpi.server.group('1000') == 1000
        with patch('grp.getgrnam') as m:
            m.return_value = Mock()
            m.return_value.gr_gid = 0
            assert compoundpi.server.group('wheel') == 0

    def test_server_showwarning():
        with patch('compoundpi.server.logging.warning') as m:
            app = compoundpi.server.CompoundPiServer()
            app.showwarning('foo', Warning, 'foo.py', 1)
            m.assert_called_once_with('foo')

    def test_server_init():
        daemon_mock.runner.make_pidlockfile.return_value = sentinel.pidfile
        daemon_mock.runner.is_pidfile_stale.return_value = False
        with patch.object(daemon_mock, 'DaemonContext') as ctx:
            ctx.__enter__ = Mock()
            ctx.__exit__ = Mock()
            with patch('compoundpi.server.CompoundPiUDPServer') as srv:
                app = compoundpi.server.CompoundPiServer()
                app([])
                ctx.assert_called_once_with(
                    detach_process=False,
                    stderr=sys.stderr,
                    uid=os.getuid(),
                    gid=os.getgid(),
                    files_preserve=[app.server.socket],
                    pidfile=sentinel.pidfile,
                    signal_map={
                        signal.SIGTERM: app.terminate,
                        signal.SIGINT:  app.interrupt,
                        })
                app.server.serve_forever.assert_called_once_with()

    def test_server_log_files_preserved(tmpdir):
        with patch.object(daemon_mock, 'DaemonContext') as ctx:
            ctx.__enter__ = Mock()
            ctx.__exit__ = Mock()
            with patch('compoundpi.server.CompoundPiUDPServer') as srv:
                app = compoundpi.server.CompoundPiServer()
                log_filename = os.path.join(str(tmpdir), 'log.txt')
                app(['--log-file', log_filename])
                assert len([
                    fd for fd in ctx.call_args[1]['files_preserve']
                    if hasattr(fd, 'name') and fd.name == log_filename
                    ]) == 1

    def test_server_pidfile_locked():
        pidfile = Mock()
        daemon_mock.runner.make_pidlockfile.return_value = pidfile
        daemon_mock.runner.is_pidfile_stale.return_value = True
        with patch.object(daemon_mock, 'DaemonContext') as ctx:
            ctx.__enter__ = Mock()
            ctx.__exit__ = Mock()
            with patch.object(compoundpi.server, 'CompoundPiUDPServer') as srv:
                app = compoundpi.server.CompoundPiServer()
                app([])
                assert pidfile.break_lock.called_once_with()

    def test_server_thread_join():
        daemon_mock.runner.is_pidfile_stale.return_value = False
        with patch.object(daemon_mock, 'DaemonContext') as ctx:
            ctx.__enter__ = Mock()
            ctx.__exit__ = Mock()
            with patch.object(compoundpi.server, 'CompoundPiUDPServer') as srv:
                with patch('threading.Thread') as thread:
                    thread.return_value = Mock()
                    thread.return_value.is_alive.return_value = True
                    thread.return_value.join.side_effect = RuntimeError('foo')
                    with pytest.raises(RuntimeError):
                        app = compoundpi.server.CompoundPiServer()
                        app([])
                    thread.return_value.start.assert_called_once_with()
                    thread.return_value.is_alive.assert_called_once_with()
                    thread.return_value.join.assert_called_once_with(1)

    def test_server_terminate():
        app = compoundpi.server.CompoundPiServer()
        app.server = Mock()
        app.terminate(signal.SIGTERM, None)
        app.server.shutdown.assert_called_once_with()

    def test_server_interrupt():
        app = compoundpi.server.CompoundPiServer()
        app.server = Mock()
        app.interrupt(signal.SIGINT, None)
        app.server.shutdown.assert_called_once_with()

    def test_handler_bad_request():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'FOO', socket), ('localhost', 1), MagicMock(seqno=2))
            m.assert_called_once_with(
                socket, ('localhost', 1), '0 ERROR\nUnable to parse request')

    def test_handler_unknown_command():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'3 FOO', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=2))
            m.assert_called_once_with(
                socket, ('localhost', 1), '3 ERROR\nUnknown command FOO')

    def test_handler_unknown_command_with_params():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'3 FOO 1 2 3', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=2))
            m.assert_called_once_with(
                socket, ('localhost', 1), '3 ERROR\nUnknown command FOO')

    def test_handler_invalid_client():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            server = MagicMock()
            server.client_address = ('foo', 1)
            compoundpi.server.CompoundPiServerProtocol(
                    (b'0 LIST', socket), ('localhost', 1), server)
            m.assert_called_once_with(
                socket, ('localhost', 1),
                '0 ERROR\nlocalhost: Invalid client or protocol error')

    def test_handler_stale_seqno():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            compoundpi.server.CompoundPiServerProtocol(
                    (b'0 LIST', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=10))
            m.assert_called_once_with(
                socket, ('localhost', 1),
                '0 ERROR\nlocalhost: Stale sequence number 0')

    def test_ack_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            responder = Mock()
            server = MagicMock()
            server.responders = {(('localhost', 1), 0): responder}
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'0 ACK', socket), ('localhost', 1), server)
            assert responder.terminate == True
            assert responder.join.called_once_with()

    def test_hello_handler_stale_time():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'0 HELLO 1000.0', socket), ('localhost', 1),
                    MagicMock(
                        client_address=('localhost', 1),
                        client_timestamp=2000.0))
            m.assert_called_once_with(
                socket, ('localhost', 1),
                '0 ERROR\nlocalhost: Stale client time 1000.000000')

    def test_hello_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            server = MagicMock()
            server.client_address = None
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'0 HELLO 1000.0', socket), ('localhost', 1), server)
            m.assert_called_once_with(
                    socket, ('localhost', 1),
                    '0 OK\nVERSION %s' % compoundpi.__version__)
            assert server.client_address == ('localhost', 1)
            assert server.client_timestamp == 1000.0
            assert server.seqno == 0

    def test_blink_thread():
        with patch('compoundpi.server.NetworkRepeater') as m, \
                patch('compoundpi.server.time.sleep') as sleep:
            server = MagicMock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'1 BLINK', Mock()), ('localhost', 1), server)
            start = time.time()
            handler.blink_led(0.1)
            assert time.time() - start >= 0.1
            assert sleep.call_count >= 2
            assert server.camera.led == True

    def test_blink_handler():
        with patch('compoundpi.server.NetworkRepeater') as m, \
                patch('threading.Thread') as thread:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'1 BLINK', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=0))
            m.assert_called_once_with(socket, ('localhost', 1), '1 OK\n')
            thread.assert_called_once_with(target=handler.blink_led, args=(5,))
            assert handler.server.seqno == 1

    def test_status_handler():
        with patch('compoundpi.server.NetworkRepeater') as m, \
                patch.object(compoundpi.server.time, 'time') as now:
            socket = Mock()
            camera = Mock(
                resolution=(1280, 720), framerate=30,
                awb_mode='auto', awb_gains=(1.5, 1.3),
                exposure_mode='off', analog_gain=8.0, digital_gain=2.0,
                exposure_speed=100000, exposure_compensation=0,
                iso=100, meter_mode='spot',
                brightness=50, contrast=25, saturation=15,
                hflip=True, vflip=False,
                image_denoise=False, video_denoise=False,
                )
            now.return_value = 2000.0
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 STATUS', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1,
                        files=[], camera=camera))
            m.assert_called_once_with(
                    socket, ('localhost', 1),
                    '2 OK\n'
                    'RESOLUTION 1280,720\n'
                    'FRAMERATE 30\n'
                    'AWB auto,1.5,1.3\n'
                    'AGC off,8.0,2.0\n'
                    'EXPOSURE off,100.0\n'
                    'ISO 100\n'
                    'METERING spot\n'
                    'BRIGHTNESS 50\n'
                    'CONTRAST 25\n'
                    'SATURATION 15\n'
                    'EV 0\n'
                    'FLIP 1,0\n'
                    'DENOISE 0\n'
                    'TIMESTAMP 2000.0\n'
                    'FILES 0\n')
            assert handler.server.seqno == 2

    def test_resolution_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 RESOLUTION 1920,1080', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.resolution == (1920, 1080)

    def test_framerate_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 FRAMERATE 30/2', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.framerate == 15

    def test_awb_handler_auto():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 AWB auto,1.0,1.0', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.awb_mode == 'auto'

    def test_awb_handler_manual():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 AWB off,1.5,1.3', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.awb_mode == 'off'
            assert handler.server.camera.awb_gains == (Fraction(3, 2), Fraction(13, 10))

    def test_agc_handler_auto():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 AGC auto', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.exposure_mode == 'auto'

    def test_agc_handler_manual():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 AGC off', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.exposure_mode == 'off'

    def test_exposure_handler_auto():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 EXPOSURE auto,1000.0', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.shutter_speed == 0

    def test_exposure_handler_manual():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 EXPOSURE off,1000.0', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.shutter_speed == 1000000

    def test_metering_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 METERING spot', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.meter_mode == 'spot'

    def test_iso_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 ISO 400', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.iso == 400

    def test_brightness_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 BRIGHTNESS 50', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.brightness == 50

    def test_contrast_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 CONTRAST 25', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.contrast == 25

    def test_saturation_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 SATURATION 15', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.saturation == 15

    def test_ev_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 EV -6', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.exposure_compensation == -6

    def test_denoise_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 DENOISE 0', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert not handler.server.camera.image_denoise
            assert not handler.server.camera.video_denoise

    def test_flip_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 FLIP 1,0', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.hflip == True
            assert handler.server.camera.vflip == False

    def test_image_stream_generator():
        with patch('compoundpi.server.NetworkRepeater') as m, \
                patch('compoundpi.server.time.time', return_value=100.0), \
                patch('compoundpi.server.io.BytesIO', return_value=sentinel.stream):
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 ACK', Mock()), ('localhost', 1),
                    MagicMock(
                        client_address=('localhost', 1), seqno=1,
                        files=[]))
            for s in handler.image_stream_generator(2):
                assert s is sentinel.stream
            assert len(handler.server.files) == 2
            assert handler.server.files[0].filetype == 'IMAGE'
            assert handler.server.files[0].timestamp == 100.0
            assert handler.server.files[0].stream == sentinel.stream
            assert handler.server.files[1].filetype == 'IMAGE'
            assert handler.server.files[1].timestamp == 100.0
            assert handler.server.files[1].stream == sentinel.stream

    def test_capture_handler():
        with patch('compoundpi.server.NetworkRepeater') as m, \
                patch('compoundpi.server.CompoundPiServerProtocol.image_stream_generator',
                        return_value=sentinel.iterator):
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 CAPTURE 1,1', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            handler.server.camera.capture_sequence.assert_called_once_with(
                    sentinel.iterator, format='jpeg', use_video_port=True,
                    burst=False, quality=85)
            assert handler.server.seqno == 2
            assert handler.server.camera.led == True

    def test_capture_handler_with_sync():
        with patch('compoundpi.server.NetworkRepeater') as m, \
                patch('compoundpi.server.time.time', return_value=1000.0), \
                patch('compoundpi.server.time.sleep') as sleep, \
                patch('compoundpi.server.CompoundPiServerProtocol.image_stream_generator',
                        return_value=sentinel.iterator):
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 CAPTURE 1,0,95,1050.0', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            sleep.assert_called_once_with(50.0)
            handler.server.camera.capture_sequence.assert_called_once_with(
                    sentinel.iterator, format='jpeg',
                    use_video_port=False, burst=True, quality=95)
            assert handler.server.seqno == 2
            assert handler.server.camera.led == True

    def test_capture_handler_past_sync():
        with patch('compoundpi.server.NetworkRepeater') as m, \
                patch('compoundpi.server.time.time', return_value=1000.0):
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 CAPTURE 1,0,,900.0', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(
                socket, ('localhost', 1), '2 ERROR\nSync time in past')

    def test_record_handler():
        with patch('compoundpi.server.NetworkRepeater') as m, \
                patch('compoundpi.server.io.BytesIO', return_value=sentinel.stream):
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 RECORD 5,mjpeg', socket), ('localhost', 1),
                    MagicMock(
                        client_address=('localhost', 1), seqno=1, files=[]))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.led == True
            handler.server.camera.start_recording.assert_called_once_with(
                    sentinel.stream, format='mjpeg', quality=0,
                    bitrate=17000000, intra_period=None,
                    motion_output=None)
            handler.server.camera.wait_recording.assert_called_once_with(5)
            handler.server.camera.stop_recording.assert_called_once_with()
            assert len(handler.server.files) == 1
            assert handler.server.files[0].filetype == 'VIDEO'
            assert handler.server.files[0].stream == sentinel.stream

    def test_record_handler_with_motion():
        with patch('compoundpi.server.NetworkRepeater') as m, \
                patch('compoundpi.server.io.BytesIO', return_value=sentinel.stream):
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 RECORD 5,h264,,,,1', socket), ('localhost', 1),
                    MagicMock(
                        client_address=('localhost', 1), seqno=1, files=[]))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.camera.led == True
            handler.server.camera.start_recording.assert_called_once_with(
                    sentinel.stream, format='h264', quality=0,
                    bitrate=17000000, intra_period=None,
                    motion_output=sentinel.stream)
            handler.server.camera.wait_recording.assert_called_once_with(5)
            handler.server.camera.stop_recording.assert_called_once_with()
            assert len(handler.server.files) == 2
            assert handler.server.files[0].filetype == 'VIDEO'
            assert handler.server.files[0].stream == sentinel.stream
            assert handler.server.files[1].filetype == 'MOTION'
            assert handler.server.files[1].stream == sentinel.stream

    def test_record_handler_wrong_codec():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 RECORD 5,mjpeg,,,,1', socket), ('localhost', 1),
                    MagicMock(
                        client_address=('localhost', 1), seqno=1))
            m.assert_called_once_with(
                socket, ('localhost', 1),
                '2 ERROR\nFormat must be h264 for motion output')

    def test_send_handler():
        with patch('compoundpi.server.NetworkRepeater') as m, \
                patch('compoundpi.server.socket.socket') as s:
            send_file = Mock()
            send_sock = Mock()
            s.return_value = send_sock
            send_sock.makefile.return_value = send_file
            socket = Mock()
            f = compoundpi.server.CompoundPiFile('IMAGE')
            f.stream.write(b'\x10' * 10)
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 SEND 0,5647', socket), ('localhost', 1),
                    MagicMock(client_address=('localhost', 1), seqno=1, files=[f]))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            send_sock.connect.assert_called_once_with(('localhost', 5647))
            send_file.write.assert_has_calls([
                call(b'\x00\x00\x00\x0A'),
                call(b'\x10' * 10),
                ])
            send_file.close.assert_called_once_with()
            send_sock.close.assert_called_once_with()

    def test_list_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            file1 = compoundpi.server.CompoundPiFile('IMAGE', 100.0)
            file1.stream.write(b'\x10' * 10)
            file2 = compoundpi.server.CompoundPiFile('VIDEO', 200.0)
            file2.stream.write(b'\x10' * 20)
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 LIST', socket), ('localhost', 1),
                    MagicMock(
                        client_address=('localhost', 1), seqno=1,
                        files=[file1, file2]))
            m.assert_called_once_with(
                socket, ('localhost', 1),
                '2 OK\n'
                'IMAGE,0,100.000000,10\n'
                'VIDEO,1,200.000000,20')
            assert handler.server.seqno == 2

    def test_clear_handler():
        with patch('compoundpi.server.NetworkRepeater') as m:
            socket = Mock()
            file1 = compoundpi.server.CompoundPiFile('IMAGE', 100.0)
            file2 = compoundpi.server.CompoundPiFile('VIDEO', 200.0)
            handler = compoundpi.server.CompoundPiServerProtocol(
                    (b'2 CLEAR', socket), ('localhost', 1),
                    MagicMock(
                        client_address=('localhost', 1), seqno=1,
                        files=[file1, file2]))
            m.assert_called_once_with(socket, ('localhost', 1), '2 OK\n')
            assert handler.server.seqno == 2
            assert handler.server.files == []

