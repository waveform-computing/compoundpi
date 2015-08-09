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

import pytest
from mock import Mock, MagicMock, patch, sentinel, call

import compoundpi
import compoundpi.client
from compoundpi.exc import (
        CompoundPiRedefinedServer,
        CompoundPiTransactionFailed,
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
                b'1 OK\nVERSION %s' % compoundpi.__version__,
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
                b'1 OK\nVERSION %s' % compoundpi.__version__,
                ('192.168.0.1', 5647)
                )
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l._items = [compoundpi.client.IPv4Address('192.168.0.1')]
        with pytest.raises(CompoundPiRedefinedServer):
            l.insert(0, '192.168.0.1')

def test_server_list_insert_failed():
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

def test_server_list_append():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.return_value = (
                b'1 OK\nVERSION %s' % compoundpi.__version__,
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
                (b'1 OK\nVERSION %s' % compoundpi.__version__, ('192.168.0.1', 5647)),
                (b'2 OK\nVERSION %s' % compoundpi.__version__, ('192.168.0.2', 5647)),
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
                (b'1 OK\nVERSION %s' % compoundpi.__version__, ('192.168.0.3', 5647)),
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

def test_server_list_find():
    client_sock = Mock()
    with patch('compoundpi.client.socket.socket', return_value=client_sock), \
            patch('compoundpi.client.select.select', return_value=([client_sock],)), \
            patch('compoundpi.client.time.time', return_value=1000.0), \
            patch('compoundpi.client.NetworkRepeater') as m:
        client_sock.recvfrom.side_effect = [
                (b'1 OK\nVERSION %s' % compoundpi.__version__, ('192.168.0.1', 5647)),
                (b'1 OK\nVERSION %s' % compoundpi.__version__, ('192.168.0.2', 5647)),
                ]
        l = compoundpi.client.CompoundPiServerList(
                progress=compoundpi.client.CompoundPiProgressHandler())
        l.find(2)
        l.sort()
        assert l == [
                compoundpi.client.IPv4Address('192.168.0.1'),
                compoundpi.client.IPv4Address('192.168.0.2')]
        m.assert_any_call(client_sock, ('192.168.255.255', 5647), b'1 HELLO 1000.0')

