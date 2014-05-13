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

"Implements the find dialog of the GUI interface"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

try:
    from ipaddress import IPv4Address
except ImportError:
    from ipaddr import IPv4Address
from PyQt4 import QtCore, QtGui, uic

from . import get_ui_file


class AddDialog(QtGui.QDialog):
    "Implements the servers/add dialog"

    def __init__(self, parent=None):
        super(AddDialog, self).__init__(parent)
        self.ui = uic.loadUi(get_ui_file('add_dialog.ui'), self)
        self.ui.server_edit.textChanged.connect(self.server_changed)
        self.update_ok()

    def _get_server(self):
        try:
            return IPv4Address(self.ui.server_edit.text())
        except ValueError:
            return None
    def _set_server(self, value):
        self.ui.server_edit.setText(str(value))
    server = property(_get_server)

    def server_changed(self, text):
        self.update_ok()

    def update_ok(self):
        self.ui.button_box.button(QtGui.QDialogButtonBox.Ok).setEnabled(
                self.server is not None)
