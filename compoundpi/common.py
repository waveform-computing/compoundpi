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

"Implements code common to server and client portions of Compound Pi"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')


import threading
import time
import random


class NetworkRepeater(threading.Thread):
    """
    Background thread for repeating a network transmission.

    This trivial threading class is used by both the server and client portions
    of Compound Pi to repeat transmissions on the network (required as UDP
    is a deliberately unreliable protocol).

    The *socket* parameter specifies the socket instance that will be used for
    transmission. The *address* parameter specifies the address (as a tuple)
    that is the destination for the transmission. The *data* parameter
    specifies the byte string that is to be sent.

    The optional *timeout* parameter specifies how many seconds must elapse
    before the repeater will cease repeating its tranmissions. The optional
    *interval* parameter specifies the largest possible interval between
    re-transmissions. The actual interval is randomly selected from a uniform
    distribution to reduce the likelihood of colliding transmissions causing
    dropped packets. Prior to use of this class the random number generator
    should be randomly seeded with :func:`random.seed`.

    To terminate re-transmission early (e.g. in the event of receiving a
    response), set the :attr:`terminate` attribute to True then
    :meth:`~threading.join` the thread. The class initializer calls
    :meth:`~threading.start` automatically so you only need construct the
    class.
    """

    def __init__(self, socket, address, data, timeout=5, interval=0.2):
        super(NetworkRepeater, self).__init__()
        self.socket = socket
        self.address = address
        self.data = data
        self.timeout = timeout
        self.interval = interval
        self.terminate = False
        self.daemon = True
        self.start()

    def run(self):
        start = time.time()
        while not self.terminate and time.time() < start + self.timeout:
            self.socket.sendto(self.data, self.address)
            time.sleep(random.uniform(0.0, self.interval))


