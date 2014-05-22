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

"Implements the client GUI interface"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

import sys
import atexit
import warnings

import pkg_resources
import sip
for api in ('QDate', 'QDateTime', 'QTime', 'QString', 'QTextStream', 'QUrl', 'QVariant'):
    sip.setapi(api, 2)
from PyQt4 import QtCore, QtGui

from . import __version__
from .windows.main_window import MainWindow
from .exc import (
    CompoundPiBadResponse,
    CompoundPiMultiResponse,
    )


APPLICATION = None
MAIN_WINDOW = None

def excepthook(type, value, tb):
    # XXX Need to expand this to display a complete stack trace and add an
    # e-mail option for bug reports
    QtGui.QMessageBox.critical(
        QtGui.QApplication.instance().activeWindow(),
        QtGui.QApplication.instance().desktop().tr('Error'),
        str(value))

def main(args=None):
    # Ignore extremely common warnings - they're only useful for protocol
    # debugging
    warnings.simplefilter('ignore', category=CompoundPiBadResponse)
    warnings.simplefilter('ignore', category=CompoundPiMultiResponse)
    global APPLICATION, MAIN_WINDOW
    if args is None:
        args = sys.argv
    atexit.register(pkg_resources.cleanup_resources)
    APPLICATION = QtGui.QApplication(args)
    APPLICATION.setApplicationName('cpigui')
    APPLICATION.setApplicationVersion(__version__)
    APPLICATION.setOrganizationName('Waveform')
    APPLICATION.setOrganizationDomain('waveform.org.uk')
    MAIN_WINDOW = MainWindow()
    MAIN_WINDOW.show()
    return APPLICATION.exec_()

if __name__ == '__main__':
    sys.exit(main(sys.argv))

