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

from PyQt4 import QtCore, QtGui, uic

from . import get_ui_file


class CaptureDialog(QtGui.QDialog):
    "Implements the servers/capture dialog"

    def __init__(self, parent=None):
        super(CaptureDialog, self).__init__(parent)
        self.ui = uic.loadUi(get_ui_file('capture_dialog.ui'), self)

    def _get_capture_count(self):
        return self.ui.count_spinbox.value()
    def _set_capture_count(self, value):
        self.ui.count_spinbox.setValue(value)
    capture_count = property(_get_capture_count, _set_capture_count)

    def _get_capture_delay(self):
        return self.ui.delay_spinbox.value() or None
    def _set_capture_delay(self, value):
        self.ui.delay_spinbox.setValue(value or 0.0)
    capture_delay = property(_get_capture_delay, _set_capture_delay)

    def _get_capture_video_port(self):
        return self.ui.video_port_check.isChecked()
    def _set_capture_video_port(self, value):
        self.ui.video_port_check.setChecked(bool(value))
    capture_video_port = property(_get_capture_video_port, _set_capture_video_port)

