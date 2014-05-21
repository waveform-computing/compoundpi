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

"Defines all exceptions and warnings used by Compound Pi"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')


class CompoundPiWarning(Warning):
    "Base class for warnings raised by the Compound Pi suite"


class CompoundPiClientWarning(CompoundPiWarning):
    "Warning raised when the Compound Pi client does something unexpected"

    def __init__(self, address, msg):
        super(CompoundPiClientWarning, self).__init__(
            '%s: %s' % (address, msg))
        self.address = address


class CompoundPiServerWarning(CompoundPiWarning):
    "Warning raised when a Compound Pi server does something unexpected"

    def __init__(self, address, msg):
        super(CompoundPiServerWarning, self).__init__(
            '%s: %s' % (address, msg))
        self.address = address


class CompoundPiWrongPort(CompoundPiServerWarning):
    "Warning raised when packets are received from the wrong port"

    def __init__(self, address, port):
        super(CompoundPiWrongPort, self).__init__(
                address, 'response from wrong port %d' % port)


class CompoundPiUnknownAddress(CompoundPiServerWarning):
    "Warning raised when a packet is received from an unexpected address"

    def __init__(self, address):
        super(CompoundPiUnknownAddress, self).__init__(
            address, 'unknown server')


class CompoundPiMultiResponse(CompoundPiServerWarning):
    "Warning raised when multiple responses are received"

    def __init__(self, address):
        super(CompoundPiMultiResponse, self).__init__(
            address, 'multiple responses received')


class CompoundPiBadResponse(CompoundPiServerWarning):
    "Warning raised when a response is badly formed"

    def __init__(self, address):
        super(CompoundPiBadResponse, self).__init__(
            address, 'badly formed response')


class CompoundPiStaleResponse(CompoundPiServerWarning):
    "Warning raised when a stale response (old sequence number) is received"

    def __init__(self, address):
        super(CompoundPiStaleResponse, self).__init__(
            address, 'stale response')


class CompoundPiFutureResponse(CompoundPiServerWarning):
    "Warning raised when a response with a future sequence number is received"

    def __init__(self, address):
        super(CompoundPiFutureResponse, self).__init__(
            address, 'future response')


class CompoundPiWrongVersion(CompoundPiServerWarning):
    "Warning raised when a server reports an incompatible version"

    def __init__(self, address, version):
        super(CompoundPiWrongVersion, self).__init__(
            address, 'wrong version "%s"' % version)
        self.version = version


class CompoundPiHelloError(CompoundPiServerWarning):
    "Warning raised when a server reports an error in response to HELLO"

    def __init__(self, address, error):
        super(CompoundPiHelloError, self).__init__(address, error)
        self.error = error


class CompoundPiStaleSequence(CompoundPiClientWarning):
    def __init__(self, address, seqno):
        super(CompoundPiStaleSequence, self).__init__(
            address, 'Stale sequence number %d' % seqno)


class CompoundPiStaleClientTime(CompoundPiClientWarning):
    def __init__(self, address, ts):
        super(CompoundPiStaleClientTime, self).__init__(
            address, 'Stale client time %f' % ts)


class CompoundPiInvalidClient(CompoundPiClientWarning):
    def __init__(self, address):
        super(CompoundPiInvalidClient, self).__init__(
            address, 'Invalid client or protocol error')


class CompoundPiError(Exception):
    "Base class for errors raised by the Compound Pi suite"


class CompoundPiClientError(CompoundPiError):
    "Base class for client-side errors (configuration, usage, etc.)"


class CompoundPiServerError(CompoundPiError):
    "Base class for server-side errors which associates an address with the message"

    def __init__(self, address, msg):
        super(CompoundPiServerError, self).__init__('%s: %s' % (address, msg))
        self.address = address


class CompoundPiTransactionFailed(CompoundPiError):
    "Compound exception which represents all errors encountered in a transaction"

    def __init__(self, errors, msg=None):
        if msg is None:
            msg = '%d errors encountered while executing' % len(errors)
        msg = '\n'.join([msg] + [str(e) for e in errors])
        super(CompoundPiTransactionFailed, self).__init__(msg)
        self.errors = errors


class CompoundPiNoServers(CompoundPiClientError):
    "Exception raised when a command is execute with no servers defined"

    def __init__(self):
        super(CompoundPiNoServers, self).__init__('no servers defined')


class CompoundPiUndefinedServers(CompoundPiClientError):
    "Exception raised when a transaction is attempted with undefined servers"

    def __init__(self, addresses):
        super(CompoundPiUndefinedServers, self).__init__(
                'transaction with undefined servers: %s' %
                ','.join(str(addr) for addr in addresses))


class CompoundPiRedefinedServers(CompoundPiClientError):
    "Exception raised when a server is added to the list twice"

    def __init__(self, addresses):
        super(CompoundPiRedefinedServers, self).__init__(
                'servers already defined: %s' %
                ','.join(str(addr) for addr in addresses))


class CompoundPiInvalidResponse(CompoundPiServerError):
    "Exception raised when a server returns an unexpected response"

    def __init__(self, address):
        super(CompoundPiInvalidResponse, self).__init__(
                address, 'invalid response')


class CompoundPiMissingResponse(CompoundPiServerError):
    "Exception raised when a server fails to return a response"

    def __init__(self, address):
        super(CompoundPiMissingResponse, self).__init__(
                address, 'no response')


class CompoundPiSendTimeout(CompoundPiServerError):
    "Exception raised when a server fails to open a connection for SEND"

    def __init__(self, address):
        super(CompoundPiSendTimeout, self).__init__(
                address, 'timed out waiting for SEND connection')


