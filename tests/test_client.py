# vim: set et sw=4 sts=4 fileencoding=utf-8:
#
# Copyright 2014 Dave Jones <dave@waveform.org.uk>.
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


import io
import warnings
import datetime as dt
from fractions import Fraction

import pytest
from mock import Mock, MagicMock, patch, sentinel, call

import compoundpi
import compoundpi.client
from compoundpi.exc import (
        CompoundPiRedefinedServer,
        CompoundPiTransactionFailed,
        CompoundPiInvalidResponse,
        CompoundPiMissingResponse,
        CompoundPiWrongPort,
        CompoundPiMultiResponse,
        CompoundPiUnknownAddress,
        CompoundPiBadResponse,
        CompoundPiStaleResponse,
        CompoundPiFutureResponse,
        CompoundPiSendTimeout,
        CompoundPiSendTruncated,
        CompoundPiNoServers,
        CompoundPiUndefinedServers,
        )


def test_resolution():
    r = compoundpi.client.Resolution(1280, 720)
    assert str(r) == '1280x720'

def test_server_list_init():
    l = compoundpi.client.CompoundPiServerList(
            progress=compoundpi.client.CompoundPiProgressHandler())
    assert l.network == compoundpi.client.IPv4Network('192.168.0.0/16')
    assert l.port == 5647
    assert len(l) == 0

def test_server_list_port():
    l = compoundpi.client.CompoundPiServerList(
            progress=compoundpi.client.CompoundPiProgressHandler())
    l.port = 3000
    assert l.port == 3000

def test_server_list_network():
    l = compoundpi.client.CompoundPiServerList(
            progress=compoundpi.client.CompoundPiProgressHandler())
    l.network = '192.168.0.0/24'
    assert l.network == compoundpi.client.IPv4Network('192.168.0.0/24')

def test_server_list_timeout():
    l = compoundpi.client.CompoundPiServerList(
            progress=compoundpi.client.CompoundPiProgressHandler())
    l.timeout = 30
    assert l.timeout == 30

def test_server_list_index():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock):
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [compoundpi.client.IPv4Address('192.168.0.1')]
        assert l.index('192.168.0.1') == 0

def test_server_list_count():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock):
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [compoundpi.client.IPv4Address('192.168.0.1')]
        assert l.count('192.168.0.1') == 1

def test_server_list_ordering():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock):
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [compoundpi.client.IPv4Address('192.168.0.2')]
        assert l == [compoundpi.client.IPv4Address('192.168.0.2')]
        assert l != [compoundpi.client.IPv4Address('192.168.0.1')]
        assert l != []
        assert l <= [compoundpi.client.IPv4Address('192.168.0.2')]
        assert l <= [compoundpi.client.IPv4Address('192.168.0.3')]
        assert l < [
                compoundpi.client.IPv4Address('192.168.0.2'),
                compoundpi.client.IPv4Address('192.168.0.3')]
        assert l < [compoundpi.client.IPv4Address('192.168.0.3')]
        assert l > []
        assert l > [compoundpi.client.IPv4Address('192.168.0.1')]
        assert l > [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        assert l >= []
        assert l >= [compoundpi.client.IPv4Address('192.168.0.2')]

def test_server_list_get_item():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock):
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        assert l[0] == compoundpi.client.IPv4Address('192.168.0.1')
        assert l[1] == compoundpi.client.IPv4Address('192.168.0.2')

def test_server_list_reversed():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock):
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        assert list(reversed(l)) == [
            compoundpi.client.IPv4Address('192.168.0.2'),
            compoundpi.client.IPv4Address('192.168.0.1')]
        l.reverse()
        assert l == [
            compoundpi.client.IPv4Address('192.168.0.2'),
            compoundpi.client.IPv4Address('192.168.0.1')]

def test_server_list_insert():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.return_value = (
                ('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'),
                ('192.168.0.1', 5647)
                )
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l.insert(0, '192.168.0.1')
        assert l == [compoundpi.client.IPv4Address('192.168.0.1')]
        m.assert_called_once_with(client_sock, ('192.168.0.1', 5647), b'1 HELLO 1000.0')

def test_server_list_insert_again():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.return_value = (
                ('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'),
                ('192.168.0.1', 5647)
                )
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [compoundpi.client.IPv4Address('192.168.0.1')]
        with pytest.raises(CompoundPiRedefinedServer):
            l.insert(0, '192.168.0.1')

def test_server_list_insert_failed1():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.return_value = (
                b'1 ERROR\nUnrecognized version', ('192.168.0.1', 5647)
                )
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        with pytest.raises(CompoundPiTransactionFailed):
            l.insert(0, '192.168.0.1')

def test_server_list_insert_failed2():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.return_value = (
                b'1 OK\nVERSION 0.0', ('192.168.0.1', 5647)
                )
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        with pytest.raises(CompoundPiTransactionFailed):
            l.insert(0, '192.168.0.1')

def test_server_list_append():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.return_value = (
                ('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'),
                ('192.168.0.2', 5647)
                )
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [compoundpi.client.IPv4Address('192.168.0.1')]
        l.append('192.168.0.2')
        assert l == [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        m.assert_called_once_with(client_sock, ('192.168.0.2', 5647), b'1 HELLO 1000.0')

def test_server_list_extend():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.1', 5647)),
                (('2 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.2', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l.extend(['192.168.0.1', '192.168.0.2'])
        assert l == [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        m.assert_any_call(client_sock, ('192.168.0.1', 5647), b'1 HELLO 1000.0')
        m.assert_any_call(client_sock, ('192.168.0.2', 5647), b'2 HELLO 1000.0')

def test_server_list_remove():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock):
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [compoundpi.client.IPv4Address('192.168.0.1')]
        l.remove('192.168.0.1')
        assert l == []
        assert client_sock.sendto.call_count == 0

def test_server_list_set_item():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.3', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        l[1] = '192.168.0.3'
        assert l == [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.3')]
        m.assert_called_once_with(client_sock, ('192.168.0.3', 5647), b'1 HELLO 1000.0')

def test_server_list_del_item():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock):
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [compoundpi.client.IPv4Address('192.168.0.1')]
        del l[0]
        assert l == []
        assert client_sock.sendto.call_count == 0

def test_server_list_move_item():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.NetworkRepeater') as m:
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        l.move(0, '192.168.0.2')
        assert l == [
                compoundpi.client.IPv4Address('192.168.0.2'),
                compoundpi.client.IPv4Address('192.168.0.1')]
        assert m.call_count == 0

def test_server_list_sort():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.NetworkRepeater') as m:
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.2'),
                compoundpi.client.IPv4Address('192.168.0.1')]
        l.sort()
        assert l == [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        assert m.call_count == 0

def test_server_list_find_count():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.1', 5647)),
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.2', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l.find(2)
        l.sort()
        assert l == [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        m.assert_any_call(client_sock, ('192.168.255.255', 5647), b'1 HELLO 1000.0')

def test_server_list_find_all():
    client_sock = Mock()
    def select_effect():
        # Fake the socket having a couple of packets then nothing
        yield ([client_sock], [], [])
        yield ([client_sock], [], [])
        while True:
            yield ([], [], [])
    from time import time as _time
    def time_effect():
        # Set the time to something specific at first so we can test the
        # HELLO message below, then make it return the "real" time so the
        # timeout loop operates correctly
        yield 1000.0
        while True:
            yield _time()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', side_effect=select_effect()), \
            patch('compoundpi.client.time.time', side_effect=time_effect()), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.1', 5647)),
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.2', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l.timeout = 1
        l.find()
        l.sort()
        assert l == [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        print(m.mock_calls)
        m.assert_any_call(client_sock, ('192.168.255.255', 5647), b'1 HELLO 1000.0')

def test_server_list_wrong_port():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.2', 6000)),
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.1', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        with warnings.catch_warnings(record=True) as w:
            l.find(1)
            assert w[0].category == CompoundPiWrongPort

def test_server_list_multi_response():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.1', 5647)),
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.1', 5647)),
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.2', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        with warnings.catch_warnings(record=True) as w:
            l.find(2)
            assert w[0].category == CompoundPiMultiResponse

def test_server_list_unknown_address():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.2', 5647)),
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.1', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [compoundpi.client.IPv4Address('192.168.0.1')]
        with warnings.catch_warnings(record=True) as w:
            l.transact('FRAMERATE 30')
            assert w[0].category == CompoundPiUnknownAddress

def test_server_list_bad_response():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (b'FOO', ('192.168.0.1', 5647)),
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.2', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        with warnings.catch_warnings(record=True) as w:
            l.find(1)
            assert w[0].category == CompoundPiBadResponse

def test_server_list_stale_response():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.1', 5647)),
                (('11 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.2', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._seqno = 10
        with warnings.catch_warnings(record=True) as w:
            l.find(1)
            assert w[0].category == CompoundPiStaleResponse

def test_server_list_future_response():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (('11 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.2', 5647)),
                (('1 OK\nVERSION %s' % compoundpi.__version__).encode('utf-8'), ('192.168.0.1', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        with warnings.catch_warnings(record=True) as w:
            l.find(1)
            assert w[0].category == CompoundPiFutureResponse

def test_server_list_transact_ok():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (b'1 OK', ('192.168.0.2', 5647)),
                (b'1 OK', ('192.168.0.1', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2'),
                ]
        assert l.transact('FRAMERATE 30') == {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        m.assert_called_once_with(client_sock, ('192.168.255.255', 5647), b'1 FRAMERATE 30')

def test_server_list_transact_subset():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (b'1 OK', ('192.168.0.2', 5647)),
                (b'1 OK', ('192.168.0.1', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2'),
                ]
        assert l.transact('FRAMERATE 30', [compoundpi.client.IPv4Address('192.168.0.1')]) == {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            }
        m.assert_called_once_with(client_sock, ('192.168.0.1', 5647), b'1 FRAMERATE 30')

def test_server_list_transact_no_servers():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.NetworkRepeater') as m:
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = []
        with pytest.raises(CompoundPiNoServers):
            assert l.transact('FRAMERATE 30')

def test_server_list_transact_undefined_servers():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.NetworkRepeater') as m:
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2'),
                ]
        with pytest.raises(CompoundPiUndefinedServers):
            l.transact('FRAMERATE 30', [compoundpi.client.IPv4Address('192.168.0.3')])

def test_server_list_transact_missing_response():
    client_sock = Mock()
    def select_effect():
        # Fake the socket having a packet then nothing
        yield ([client_sock], [], [])
        while True:
            yield ([], [], [])
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', side_effect=select_effect()), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (b'1 OK', ('192.168.0.1', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l.timeout = 1
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2'),
                ]
        with pytest.raises(CompoundPiTransactionFailed) as excinfo:
            l.transact('FRAMERATE 30')
            assert len(excinfo.value.errors) == 1
            assert isinstance(excinfo.value.errors[0], CompoundPiMissingResponse)

def test_server_list_transact_server_error():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (b'1 OK', ('192.168.0.1', 5647)),
                (b'1 ERROR\nServer is broken', ('192.168.0.2', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l.timeout = 1
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2'),
                ]
        with pytest.raises(CompoundPiTransactionFailed) as excinfo:
            l.transact('FRAMERATE 30')
            assert len(excinfo.value.errors) == 1
            assert isinstance(excinfo.value.errors[0], CompoundPiServerError)

def test_server_list_transact_invalid_response():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (b'1 OK', ('192.168.0.1', 5647)),
                (b'1 FOO', ('192.168.0.2', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l.timeout = 1
        l._items = [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2'),
                ]
        with pytest.raises(CompoundPiTransactionFailed) as excinfo:
            l.transact('FRAMERATE 30')
            assert len(excinfo.value.errors) == 1
            assert isinstance(excinfo.value.errors[0], CompoundPiInvalidResponse)

def test_client_init():
    def download_server_effect(bind, handler):
        return Mock(**{'socket.getsockname.return_value': bind})
    with patch('compoundpi.client.CompoundPiDownloadServer', side_effect=download_server_effect):
        client = compoundpi.client.CompoundPiClient()
        assert len(client.servers) == 0
        assert client.bind == ('0.0.0.0', 5647)

def test_client_bind():
    def download_server_effect(bind, handler):
        return Mock(**{'socket.getsockname.return_value': bind})
    with patch('compoundpi.client.CompoundPiDownloadServer', side_effect=download_server_effect):
        client = compoundpi.client.CompoundPiClient()
        client.bind = ('0.0.0.0', 8000)
        assert client.bind == ('0.0.0.0', 8000)

def test_client_status_ok():
    status_response = """\
RESOLUTION 1280,720
FRAMERATE 30
AWB auto,14/10,15/10
AGC auto,4,1
EXPOSURE auto,33.200
ISO 100
METERING spot
BRIGHTNESS 50
CONTRAST 25
SATURATION 15
EV 0
FLIP 1,0
DENOISE 0
TIMESTAMP 1000.0
FILES 0
"""
    status_struct = compoundpi.client.CompoundPiStatus(
        resolution=compoundpi.client.Resolution(1280, 720),
        framerate=Fraction(30, 1),
        awb_mode='auto',
        awb_red=Fraction(14, 10),
        awb_blue=Fraction(15, 10),
        agc_mode='auto',
        agc_analog=Fraction(4, 1),
        agc_digital=Fraction(1, 1),
        exposure_mode='auto',
        exposure_speed=33.2,
        ev=0,
        iso=100,
        metering_mode='spot',
        brightness=50,
        contrast=25,
        saturation=15,
        hflip=True,
        vflip=False,
        denoise=False,
        timestamp=dt.datetime.fromtimestamp(1000.0),
        files=0
        )
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): status_response,
            compoundpi.client.IPv4Address('192.168.0.2'): status_response,
            }
        client = compoundpi.client.CompoundPiClient()
        assert client.status() == {
            compoundpi.client.IPv4Address('192.168.0.1'): status_struct,
            compoundpi.client.IPv4Address('192.168.0.2'): status_struct,
            }
        l.assert_called_once_with('STATUS', None)

def test_client_status_bad():
    status_response = "FOO"
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): status_response,
            compoundpi.client.IPv4Address('192.168.0.2'): status_response,
            }
        client = compoundpi.client.CompoundPiClient()
        with pytest.raises(CompoundPiTransactionFailed) as excinfo:
            client.status()
            assert len(excinfo.value.errors) == 2
            assert isinstance(excinfo.value.errors[0], CompoundPiInvalidResponse)
            assert isinstance(excinfo.value.errors[1], CompoundPiInvalidResponse)

def test_client_resolution():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.resolution(1280, 720)
        l.assert_called_once_with('RESOLUTION 1280,720', None)

def test_client_framerate():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.framerate(30)
        l.assert_called_once_with('FRAMERATE 30', None)

def test_client_awb():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.awb('off', 1.4, 1.5)
        l.assert_called_once_with('AWB off,7/5,3/2', None)

def test_client_agc():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.agc('auto')
        l.assert_called_once_with('AGC auto', None)

def test_client_exposure():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.exposure('off', 33.333)
        l.assert_called_once_with('EXPOSURE off,33.333', None)

def test_client_metering():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.metering('average')
        l.assert_called_once_with('METERING average', None)

def test_client_iso():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.iso(100)
        l.assert_called_once_with('ISO 100', None)

def test_client_brightness():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.brightness(50)
        l.assert_called_once_with('BRIGHTNESS 50', None)

def test_client_contrast():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.contrast(25)
        l.assert_called_once_with('CONTRAST 25', None)

def test_client_saturation():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.saturation(15)
        l.assert_called_once_with('SATURATION 15', None)

def test_client_ev():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.ev(6)
        l.assert_called_once_with('EV 6', None)

def test_client_flip():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.flip(True, False)
        l.assert_called_once_with('FLIP 1,0', None)

def test_client_denoise():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.denoise(False)
        l.assert_called_once_with('DENOISE 0', None)

def test_client_capture_now():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.capture()
        l.assert_called_once_with('CAPTURE 1,0,,', None)

def test_client_capture_sync():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.capture(5, video_port=True, delay=2)
        l.assert_called_once_with('CAPTURE 5,1,,1002.0', None)

def test_client_record_now():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.record(5)
        l.assert_called_once_with('RECORD 5.0,h264,,,,0,', None)

def test_client_record_sync():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.record(5, format='mjpeg', delay=2)
        l.assert_called_once_with('RECORD 5.0,mjpeg,,,,0,1002.0', None)

def test_client_list_ok():
    list_response = """\
IMAGE,0,1000.0,1234567
VIDEO,1,2000.0,2345678
"""
    list_struct = [
        compoundpi.client.CompoundPiFile('IMAGE', 0, dt.datetime.fromtimestamp(1000.0), 1234567),
        compoundpi.client.CompoundPiFile('VIDEO', 1, dt.datetime.fromtimestamp(2000.0), 2345678),
        ]
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): list_response,
            compoundpi.client.IPv4Address('192.168.0.2'): list_response,
            }
        client = compoundpi.client.CompoundPiClient()
        assert client.list() == {
            compoundpi.client.IPv4Address('192.168.0.1'): list_struct,
            compoundpi.client.IPv4Address('192.168.0.2'): list_struct,
            }
        l.assert_called_once_with('LIST', None)

def test_client_list_bad():
    list_response = "FOO"
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): list_response,
            compoundpi.client.IPv4Address('192.168.0.2'): list_response,
            }
        client = compoundpi.client.CompoundPiClient()
        with pytest.raises(CompoundPiTransactionFailed) as excinfo:
            client.list()
            assert len(excinfo.value.errors) == 2
            assert isinstance(excinfo.value.errors[0], CompoundPiInvalidResponse)
            assert isinstance(excinfo.value.errors[1], CompoundPiInvalidResponse)

def test_client_clear():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.clear()
        l.assert_called_once_with('CLEAR', None)

def test_client_identify():
    with patch('compoundpi.client.CompoundPiServerList.transact') as l, \
            patch('compoundpi.client.CompoundPiDownloadServer'):
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            compoundpi.client.IPv4Address('192.168.0.2'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client.identify()
        l.assert_called_once_with('BLINK', None)

def test_client_download_ok():
    def download_server_effect(bind, handler):
        return Mock(**{'socket.getsockname.return_value': bind})
    with patch('compoundpi.client.CompoundPiDownloadServer', side_effect=download_server_effect), \
            patch('compoundpi.client.CompoundPiServerList.transact') as l:
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client._server.event = Mock()
        client._server.event.wait.return_value = True
        client.download('192.168.0.1', 0, io.BytesIO())
        l.assert_called_once_with('SEND 0,5647', ['192.168.0.1'])

def test_client_download_timeout():
    def download_server_effect(bind, handler):
        return Mock(**{'socket.getsockname.return_value': bind})
    with patch('compoundpi.client.CompoundPiDownloadServer', side_effect=download_server_effect), \
            patch('compoundpi.client.CompoundPiServerList.transact') as l:
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client._server.event = Mock()
        client._server.event.wait.return_value = False
        with pytest.raises(CompoundPiSendTimeout):
            client.download('192.168.0.1', 0, io.BytesIO())

def test_client_download_exception():
    def download_server_effect(bind, handler):
        return Mock(**{'socket.getsockname.return_value': bind})
    with patch('compoundpi.client.CompoundPiDownloadServer', side_effect=download_server_effect), \
            patch('compoundpi.client.CompoundPiServerList.transact') as l:
        l.return_value = {
            compoundpi.client.IPv4Address('192.168.0.1'): None,
            }
        client = compoundpi.client.CompoundPiClient()
        client._server.event = Mock()
        client._server.event.wait.return_value = True
        client._server.exception = ValueError('Foo')
        with pytest.raises(ValueError) as excinfo:
            client.download('192.168.0.1', 0, io.BytesIO())
            assert excinfo.value.args == ('Foo',)

def test_client_download_handler():
    server = MagicMock(
        output=io.BytesIO(),
        progress=MagicMock(),
        event=Mock(),
        exception=None,
        source='client',
        )
    request = MagicMock(
        makefile=Mock(side_effect=lambda mode, bufsize: io.BytesIO(b'\x00\x00\x00\x07foo bar'))
        )
    compoundpi.client.CompoundPiDownloadHandler(request, ('client', 5647), server)
    server.event.set.assert_called_once_with()
    server.progress.start.assert_called_once_with(7)
    server.progress.finish.assert_called_once_with()
    assert server.output.getvalue() == b'foo bar'

def test_client_download_bad_client():
    server = MagicMock(
        output=io.BytesIO(),
        progress=MagicMock(),
        event=Mock(),
        exception=None,
        source='bad_client',
        )
    request = MagicMock(
        makefile=Mock(side_effect=lambda mode, bufsize: io.BytesIO(b'\x00\x00\x00\x07foo bar'))
        )
    with warnings.catch_warnings(record=True) as w:
        compoundpi.client.CompoundPiDownloadHandler(request, ('client', 5647), server)
        assert w[0].category == CompoundPiUnknownAddress

def test_client_download_truncated():
    server = MagicMock(
        output=io.BytesIO(),
        progress=MagicMock(),
        event=Mock(),
        exception=None,
        source='client',
        )
    request = MagicMock(
        makefile=Mock(side_effect=lambda mode, bufsize: io.BytesIO(b'\x00\x00\x00\x10foo bar'))
        )
    compoundpi.client.CompoundPiDownloadHandler(request, ('client', 5647), server)
    assert isinstance(server.exception, CompoundPiSendTruncated)

def test_client_progress_defaults():
    m = MagicMock()
    p = compoundpi.client.CompoundPiProgressHandler(m)
    p.start(10)
    m.start.assert_called_once_with(10)
    p.update(5)
    m.update.assert_called_once_with(5)
    p.finish()
    m.finish.assert_called_once_with()

