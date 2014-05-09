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


import io
from collections import defaultdict

import netifaces
from PyQt4 import QtCore, QtGui, uic

from . import get_icon, get_ui_file
from .find_dialog import FindDialog
from .configure_dialog import ConfigureDialog
from ..client import CompoundPiClient


class MainWindow(QtGui.QMainWindow):
    "The Compound Pi GUI main window"

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.client = CompoundPiClient(progress=(
            self.progress_start,
            self.progress_update,
            self.progress_finish,
            ))
        self.images = defaultdict(list)
        self.ui = uic.loadUi(get_ui_file('main_window.ui'), self)
        # Read configuration
        self.settings = QtCore.QSettings()
        self.settings.beginGroup('window')
        try:
            self.resize(
                    self.settings.value(
                        'size', QtCore.QSize(640, 480)))
            self.move(
                    self.settings.value(
                        'position', QtCore.QPoint(100, 100)))
        finally:
            self.settings.endGroup()
        # Set up menu icons
        self.ui.quit_action.setIcon(get_icon('application-exit'))
        self.ui.about_action.setIcon(get_icon('help-about'))
        self.ui.about_qt_action.setIcon(get_icon('help-about'))
        self.ui.find_action.setIcon(get_icon('system-search'))
        self.ui.add_action.setIcon(get_icon('list-add'))
        self.ui.remove_action.setIcon(get_icon('list-remove'))
        self.ui.identify_action.setIcon(get_icon('dialog-information'))
        self.ui.capture_action.setIcon(get_icon('camera-photo'))
        self.ui.configure_action.setIcon(get_icon('preferences-system'))
        self.ui.copy_action.setIcon(get_icon('edit-copy'))
        self.ui.clear_action.setIcon(get_icon('edit-clear'))
        self.ui.select_all_action.setIcon(get_icon('edit-select-all'))
        self.ui.refresh_action.setIcon(get_icon('view-refresh'))
        # Configure status bar elements
        self.ui.progress_label = QtGui.QLabel('')
        self.statusBar().addWidget(self.ui.progress_label)
        self.progress_index = 0
        # Connect signals to methods
        self.ui.about_action.triggered.connect(self.help_about)
        self.ui.about_qt_action.triggered.connect(self.help_about_qt)
        self.ui.find_action.triggered.connect(self.servers_find)
        self.ui.add_action.triggered.connect(self.servers_add)
        self.ui.remove_action.triggered.connect(self.servers_remove)
        self.ui.identify_action.triggered.connect(self.servers_identify)
        self.ui.capture_action.triggered.connect(self.servers_capture)
        self.ui.configure_action.triggered.connect(self.servers_configure)
        self.ui.copy_action.triggered.connect(self.edit_copy)
        self.ui.clear_action.triggered.connect(self.edit_clear)
        self.ui.select_all_action.triggered.connect(self.edit_select_all)
        self.ui.refresh_action.triggered.connect(self.view_refresh)
        self.ui.status_bar_action.triggered.connect(self.toggle_status)
        self.ui.view_menu.aboutToShow.connect(self.update_status)
        # Connect the lists to their models
        self.ui.server_list.setModel(ServersModel(self))
        self.ui.image_list.setModel(ImagesModel(self))
        # XXX What about pressing Enter instead of double clicking?
        self.ui.server_list.model().modelReset.connect(
            self.server_list_model_reset)
        self.ui.server_list.model().dataChanged.connect(
            self.server_list_data_changed)
        self.ui.server_list.selectionModel().selectionChanged.connect(
            self.server_list_selection_changed)
        self.ui.server_list.doubleClicked.connect(
            self.server_list_double_clicked)

    @property
    def selected_indexes(self):
        return [i.row() for i in self.ui.server_list.selectionModel().selectedRows()]

    @property
    def selected_addresses(self):
        return self.ui.server_list.model().addresses(self.selected_indexes)

    def close(self):
        "Called when the main window is closed"
        self.settings.beginGroup('window')
        try:
            self.settings.setValue('size', self.size())
            self.settings.setValue('position', self.pos())
        finally:
            self.settings.endGroup()
        super(MainWindow, self).close()

    def help_about(self):
        QtGui.QMessageBox.about(self,
            str(self.tr('About {}')).format(
                QtGui.QApplication.instance().applicationName()),
            str(self.tr("""\
<b>{application}</b>
<p>Version {version}</p>
<p>{application} is a GUI for interrogating an OxiTop OC110 Data Logger.
Project homepage is at
<a href="{url}">{url}</a></p>
<p>Copyright &copy; 2012-2013 {author} &lt;<a href="mailto:{author_email}">{author_email}</a>&gt;</p>""")).format(
                application=QtGui.QApplication.instance().applicationName(),
                version=QtGui.QApplication.instance().applicationVersion(),
                url='http://compoundpi.readthedocs.org/',
                author='Dave Hughes',
                author_email='dave@waveform.org.uk',
            ))

    def help_about_qt(self):
        QtGui.QMessageBox.aboutQt(self, self.tr('About QT'))

    def servers_find(self):
        dialog = FindDialog(self)
        self.settings.beginGroup('last_used')
        try:
            dialog.interface = self.settings.value('interface', '')
            dialog.port = self.settings.value('port', '5647')
            dialog.expected_count = self.settings.value('expected_count', '0')
            if dialog.exec_():
                try:
                    iface = netifaces.ifaddresses(dialog.interface)[netifaces.AF_INET][0]
                except KeyError:
                    raise ValueError(
                        'Interface %s has no IPv4 address' % dialog.interface)
                except IndexError:
                    raise ValueError(
                        'Interface %s has no addresses' % dialog.interface)
                if not (1 <= dialog.port <= 65535):
                    raise ValueError('Port %d is invalid' % dialog.port)
                self.settings.setValue('interface', dialog.interface)
                self.settings.setValue('port', dialog.port)
                self.settings.setValue('expected_count', dialog.expected_count)
                self.client.network = '%s/%s' % (iface['addr'], iface['netmask'])
                self.client.port = dialog.port
                self.ui.server_list.model().find(count=dialog.expected_count)
                for col in range(self.ui.server_list.model().columnCount()):
                    self.ui.server_list.resizeColumnToContents(col)
        finally:
            self.settings.endGroup()

    def servers_add(self):
        raise NotImplementedError
        self.ui.server_list.model().add()

    def servers_remove(self):
        self.ui.server_list.model().remove(self.selected_addresses)

    def servers_identify(self):
        self.client.identify(self.selected_addresses)

    def servers_capture(self):
        self.client.capture(addresses=self.selected_addresses)
        responses = self.client.list(self.selected_addresses)
        for (address, images) in responses.items():
            for image in images:
                stream = io.BytesIO()
                self.client.download(address, image.index, stream)
                if stream.tell() != image.size:
                    raise IOError('Incorrect download size')
                self.images[address].append((image.timestamp, stream))
        # XXX Rollback in the case of a partial download...
        self.client.clear(self.selected_addresses)
        self.ui.server_list.model().refresh_selected()
        self.ui.image_list.model().refresh()

    def servers_configure(self):
        dialog = ConfigureDialog(self)
        self.settings.beginGroup('last_used')
        try:
            if dialog.exec_():
                pass
        finally:
            self.settings.endGroup()

    def edit_copy(self):
        pass

    def edit_clear(self):
        for address in self.selected_addresses:
            del self.images[address]
        self.ui.server_list.model().refresh_selected()
        self.ui.image_list.model().refresh()

    def edit_select_all(self):
        self.ui.server_list.selectAll()

    def view_refresh(self):
        self.ui.server_list.model().refresh_data()

    def server_list_double_clicked(self, index):
        pass

    def server_list_model_reset(self):
        self.ui.refresh_action.setEnabled(self.ui.server_list.model().rowCount())
        self.ui.select_all_action.setEnabled(self.ui.server_list.model().rowCount())

    def server_list_data_changed(self, top_left, bottom_right):
        self.server_list_model_reset()

    def server_list_selection_changed(self, selected, deselected):
        selected = selected.indexes()
        self.ui.remove_action.setEnabled(bool(selected))
        self.ui.identify_action.setEnabled(bool(selected))
        self.ui.capture_action.setEnabled(bool(selected))
        self.ui.configure_action.setEnabled(bool(selected))
        self.ui.image_list.model().refresh()

    def update_status(self):
        self.ui.status_bar_action.setChecked(self.statusBar().isVisible())

    def toggle_status(self):
        if self.statusBar().isVisible():
            self.statusBar().hide()
        else:
            self.statusBar().show()

    def progress_start(self):
        QtGui.QApplication.instance().setOverrideCursor(QtCore.Qt.WaitCursor)

    def progress_update(self):
        self.progress_index += 1
        self.ui.progress_label.setText('Communicating' + '.' * (self.progress_index % 8))
        QtGui.QApplication.instance().processEvents()

    def progress_finish(self):
        self.ui.progress_label.setText('')
        QtGui.QApplication.instance().restoreOverrideCursor()


class ServersModel(QtCore.QAbstractTableModel):
    def __init__(self, parent):
        super(ServersModel, self).__init__()
        self.parent = parent
        self._data = []

    def find(self, count=0):
        self.beginResetModel()
        try:
            self.parent.client.find(count)
            self._data = sorted(self.parent.client.status().items())
        finally:
            self.endResetModel()

    def refresh_data(self):
        self._data = sorted(self.parent.client.status().items())
        self.refresh_all()

    def refresh_all(self):
        first = self.index(0, 0)
        last = self.index(self.rowCount(), 3)
        self.dataChanged.emit(first, last)

    def refresh_selected(self, first_col=0, last_col=3):
        for index in self.parent.selected_indexes:
            self.dataChanged.emit(self.index(index, first_col), self.index(index, last_col))

    def add(self, address):
        raise NotImplementedError

    def remove(self, addresses):
        raise NotImplementedError

    def addresses(self, indexes):
        return [self._data[index][0] for index in indexes]

    def images(self, address):
        # XXX Improve this
        try:
            return [s.images for (a, s) in self._data if a == address][0]
        except IndexError:
            raise KeyError(address)

    def rowCount(self, parent=None):
        if parent is None:
            parent = QtCore.QModelIndex()
        if parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent=None):
        if parent is None:
            parent = QtCore.QModelIndex()
        if parent.isValid():
            return 0
        return 4

    def data(self, index, role):
        if index.isValid() and role == QtCore.Qt.DisplayRole:
            (address, status) = self._data[index.row()]
            return [
                str(address),
                '%dx%d@%s' % (status.resolution[0], status.resolution[1], status.framerate),
                status.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'),
                str(len(self.parent.images[address])),
                ][index.column()]

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return [
                'Address',
                'Mode',
                'Time',
                'Images',
                ][section]
        elif orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
            return section + 1


class ImagesModel(QtCore.QAbstractListModel):
    def __init__(self, parent):
        super(ImagesModel, self).__init__()
        self.parent = parent
        self._data = []
        self._cache = {}

    def refresh(self):
        self.beginResetModel()
        try:
            self._data = []
            for address in self.parent.selected_addresses:
                for timestamp, stream in self.parent.images[address]:
                    try:
                        thumbnail = self._cache[(address, timestamp)]
                    except KeyError:
                        image = QtGui.QPixmap()
                        image.loadFromData(stream.getvalue())
                        thumbnail = image.scaledToWidth(200)
                        self._cache[(address, timestamp)] = thumbnail
                    self._data.append(
                        (timestamp, address, thumbnail, stream))
        finally:
            self.endResetModel()

    def rowCount(self, parent=None):
        if parent is None:
            parent = QtCore.QModelIndex()
        if parent.isValid():
            return 0
        return len(self._data)

    def data(self, index, role):
        if index.isValid():
            timestamp, address, thumbnail, _ = self._data[index.row()]
            if role == QtCore.Qt.DisplayRole:
                return '{ts:%Y-%m-%d %H:%M:%S}\n{addr}'.format(ts=timestamp, addr=address)
            elif role == QtCore.Qt.DecorationRole:
                return thumbnail
