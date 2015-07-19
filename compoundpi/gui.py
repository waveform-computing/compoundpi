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
import logging

import pkg_resources

from . import __version__
from .qt import QtCore, QtGui
from .windows.main_window import MainWindow
from .windows.exception_dialog import ExceptionDialog
from .exc import (
    CompoundPiBadResponse,
    CompoundPiMultiResponse,
    )


APPLICATION = None
MAIN_WINDOW = None

def excepthook(exc_type, exc_value, exc_tb):
    ExceptionDialog(MAIN_WINDOW, (exc_type, exc_value, exc_tb)).exec_()

def main(args=None):
    # Ignore extremely common warnings - they're only useful for protocol
    # debugging
    warnings.simplefilter('ignore', category=CompoundPiBadResponse)
    warnings.simplefilter('ignore', category=CompoundPiMultiResponse)
    global APPLICATION, MAIN_WINDOW
    if args is None:
        args = sys.argv
    atexit.register(pkg_resources.cleanup_resources)
    sys.excepthook = excepthook
    APPLICATION = QtGui.QApplication(args)
    APPLICATION.setApplicationName('cpigui')
    APPLICATION.setApplicationVersion(__version__)
    APPLICATION.setOrganizationName('Waveform')
    APPLICATION.setOrganizationDomain('waveform.org.uk')
    MAIN_WINDOW = MainWindow()
    MAIN_WINDOW.show()
    #logging.getLogger().setLevel(logging.DEBUG)
    return APPLICATION.exec_()

if __name__ == '__main__':
    sys.exit(main(sys.argv))

