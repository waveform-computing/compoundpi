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

"Implements the configure dialog of the GUI interface"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

import fractions

from PyQt4 import QtCore, QtGui, uic

from . import get_ui_file


class ConfigureDialog(QtGui.QDialog):
    "Implements the servers/configure dialog"

    def __init__(self, parent=None):
        super(ConfigureDialog, self).__init__(parent)
        self.ui = uic.loadUi(get_ui_file('configure_dialog.ui'), self)
        # Populate the resolution list
        self.ui.resolution_combo.setModel(ResolutionsModel())
        self.ui.framerate_combo.setModel(FrameratesModel())
        # Populate the framerate list
        # Connect up signals
        self.ui.resolution_combo.editTextChanged.connect(self.resolution_changed)
        self.ui.framerate_combo.editTextChanged.connect(self.framerate_changed)

    def _get_resolution(self):
        s = self.ui.resolution_combo.currentText()
        try:
            width, height = s.split('x', 1)
            width = int(width)
            height = int(height)
        except (TypeError, ValueError):
            return None
        return width, height
    def _set_resolution(self, value):
        if not isinstance(value, str):
            value = '%dx%d' % value
        self.ui.resolution_combo.setEditText(value)
    resolution = property(_get_resolution, _set_resolution)

    def _get_framerate(self):
        try:
            return fractions.Fraction(
                    self.ui.framerate_combo.currentText()).limit_denominator(1000)
        except ValueError:
            return None
    def _set_framerate(self, value):
        self.ui.framerate_combo.setEditText(str(value))
    framerate = property(_get_framerate, _set_framerate)

    def resolution_changed(self, text):
        self.update_ok()

    def framerate_changed(self, text):
        self.update_ok()

    def update_ok(self):
        self.ui.button_box.button(QtGui.QDialogButtonBox.Ok).setEnabled(
                bool(self.resolution and self.framerate))


class ResolutionsModel(QtCore.QAbstractListModel):
    def __init__(self):
        super(ResolutionsModel, self).__init__()
        self._data = [
            ('320x240',   'QVGA',    '4:3'),
            ('640x480',   'VGA',     '4:3'),
            ('768x576',   'PAL',     '4:3'),
            ('800x600',   'SVGA',    '4:3'),
            ('1024x576',  'PAL',     '16:9'),
            ('1024x768',  'XGA',     '4:3'),
            ('1280x720',  'HD 720',  '16:9'),
            ('1680x1050', 'WSXGA+',  '16:10'),
            ('1920x1080', 'HD 1080', '16:9'),
            ('2048x1536', 'QXGA',    '4:3'),
            ('2560x1440', 'WQHD',    '16:9'),
            ('2592x1944', 'Max res', '4:3'),
            ]

    def rowCount(self, parent=None):
        if parent is None:
            parent = QtCore.QModelIndex()
        if parent.isValid():
            return 0
        return len(self._data)

    def data(self, index, role):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                return '%s\t(%s - %s)' % self._data[index.row()]
            elif role == QtCore.Qt.EditRole:
                return self._data[index.row()][0]


class FrameratesModel(QtCore.QAbstractListModel):
    def __init__(self):
        super(FrameratesModel, self).__init__()
        self._data = [
            90,
            60,
            50,
            48,
            30,
            25,
            24,
            23.976,
            15,
            1,
            ]

    def rowCount(self, parent=None):
        if parent is None:
            parent = QtCore.QModelIndex()
        if parent.isValid():
            return 0
        return len(self._data)

    def data(self, index, role):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                return '%gfps' % self._data[index.row()]
            elif role == QtCore.Qt.EditRole:
                return str(self._data[index.row()])

