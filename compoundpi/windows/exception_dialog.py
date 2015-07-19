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


import traceback

from . import get_ui_file, get_icon
from ..qt import QtCore, QtGui, loadUi


class ExceptionDialog(QtGui.QDialog):
    "Implements the exception dialog"

    def __init__(self, parent, exc_info):
        super(ExceptionDialog, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.ui = loadUi(get_ui_file('exception_dialog.ui'), self)
        self.ui.traceback_text.setPlainText(
            ''.join(traceback.format_exception(*exc_info)))
        self.ui.icon_label.setPixmap(get_icon('dialog-error').pixmap(32))

