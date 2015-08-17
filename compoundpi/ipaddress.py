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

"""
Makes the ipaddr module more like ipaddress in Python 3.x
"""

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

import sys


if sys.version_info < (3, 3):
    import ipaddr

    if sys.version_info > (3, 1):
        # Monkeypatch ipaddr==2.1.7 to work (mostly) in Python 3.2...
        ipaddr.long = int
        ipaddr.xrange = range

    class IPv4Address(ipaddr.IPv4Address):
        pass

    class IPv4Network(ipaddr.IPv4Network):
        @property
        def broadcast_address(self):
            return self.broadcast
else:
    from ipaddress import IPv4Address, IPv4Network
