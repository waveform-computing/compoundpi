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

"Implements the main window of the GUI interface"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')
range = xrange

import io
import os
import sys

from PyQt4 import QtCore, QtGui, uic


if getattr(sys, 'frozen', None):
    def get_ui_dir():
        "Returns the directory containing the *.ui Qt window definitions"
        result = os.path.abspath(os.path.join(
            os.path.dirname(sys.executable), *__name__.split('.')))
        # Check the result is a directory and that it contains at least one .ui file
        if not os.path.isdir(result):
            raise ValueError('Expected %s to be a directory' % result)
        if not any(filename.endswith('.ui') for filename in os.listdir(result)):
            raise ValueError('UI directory %s does not contain any .ui files' % result)
        return result

    UI_DIR = get_ui_dir()

    def resource_exists(module, name):
        name = os.path.join(UI_DIR, name)
        return os.path.exists(name) and not os.path.isdir(name)

    def resource_stream(module, name):
        name = os.path.join(UI_DIR, name)
        return io.open(name, 'r')

    def resource_filename(module, name):
        name = os.path.join(UI_DIR, name)
        return name
else:
    from pkg_resources import resource_stream, resource_filename, resource_exists


def get_ui_file(ui_file):
    "Returns a file-like object for the specified .ui file"
    return resource_stream(__name__, ui_file)

def get_icon(icon_id):
    "Returns an icon from the system theme or our fallback theme if required"
    fallback_path = os.path.join('fallback-theme', icon_id + '.png')
    if resource_exists(__name__, fallback_path):
        return QtGui.QIcon.fromTheme(icon_id,
            QtGui.QIcon(resource_filename(__name__, fallback_path)))
    else:
        return QtGui.QIcon.fromTheme(icon_id)

