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

import socket

import netifaces
from PyQt4 import QtCore, QtGui, uic

from . import get_ui_file


class FindDialog(QtGui.QDialog):
    "Implements the servers/find dialog"

    def __init__(self, parent=None):
        super(FindDialog, self).__init__(parent)
        self.ui = uic.loadUi(get_ui_file('find_dialog.ui'), self)
        # Populate the interface list
        for interface in sorted(netifaces.interfaces()):
            self.ui.interface_combo.addItem(interface)
        # Connect up signals
        self.ui.interface_combo.currentIndexChanged.connect(self.interface_changed)
        self.ui.port_edit.textChanged.connect(self.port_changed)
        self.update_ok()

    def _get_interface(self):
        return str(self.ui.interface_combo.currentText()) or None
    def _set_interface(self, value):
        for index in range(self.ui.interface_combo.count()):
            if self.ui.interface_combo.itemText(index) == value:
                self.ui.interface_combo.setCurrentIndex(index)
                return
        self.ui.interface_combo.setEditText(value)
    interface = property(_get_interface, _set_interface)

    def _get_port(self):
        try:
            p = int(self.ui.port_edit.text())
        except ValueError:
            try:
                return socket.getservbyname(self.ui.port_edit.text())
            except IOError:
                return None
        else:
            if 1 <= p <= 65535:
                return p
            else:
                return None
    def _set_port(self, value):
        self.ui.port_edit.setText(str(value))
    port = property(_get_port, _set_port)

    def _get_timeout(self):
        return self.ui.timeout_spinbox.value()
    def _set_timeout(self, value):
        self.ui.timeout_spinbox.setValue(int(value))
    timeout = property(_get_timeout, _set_timeout)

    def _get_expected_count(self):
        return self.ui.expected_spinbox.value()
    def _set_expected_count(self, value):
        self.ui.expected_spinbox.setValue(int(value))
    expected_count = property(_get_expected_count, _set_expected_count)

    def interface_changed(self, index):
        self.update_ok()

    def port_changed(self, text):
        self.update_ok()

    def update_ok(self):
        self.ui.button_box.button(QtGui.QDialogButtonBox.Ok).setEnabled(
                bool(self.interface and self.port))
