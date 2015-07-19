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


from . import get_ui_file
from ..qt import QtCore, QtGui, loadUi


class ProgressDialog(QtGui.QDialog):
    "Implements the progress dialog"

    def __init__(self, parent=None):
        super(ProgressDialog, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.ui = loadUi(get_ui_file('progress_dialog.ui'), self)
        self.cancelled = False

    def _get_task(self):
        return self.ui.windowTitle()
    def _set_task(self, value):
        self.ui.setWindowTitle(value)
    task = property(_get_task, _set_task)

    def _get_progress(self):
        return self.ui.progress_bar.value()
    def _set_progress(self, value):
        self.ui.progress_bar.setValue(value)
        QtGui.QApplication.instance().processEvents()
    progress = property(_get_progress, _set_progress)

    def _get_limits(self):
        return (
            self.ui.progress_bar.minimum(),
            self.ui.progress_bar.maximum(),
            )
    def _set_limits(self, value):
        self.ui.progress_bar.setRange(value[0], value[1])
    limits = property(_get_limits, _set_limits)

    def reject(self):
        self.cancelled = True
        self.hide()
        self.close()

