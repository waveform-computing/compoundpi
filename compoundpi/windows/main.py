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

from PyQt4 import QtCore, QtGui, uic

from . import get_icon, get_ui_file
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
        self.images = {}
        self.ui = uic.loadUi(get_ui_file('main.ui'), self)
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
        # Configure status bar elements
        self.ui.progress_label = QtGui.QLabel('')
        self.statusBar().addWidget(self.ui.progress_label)
        self.progress_index = 0
        # Connect signals to methods
        self.ui.quit_action.setIcon(get_icon('application-exit'))
        self.ui.about_action.triggered.connect(self.about)
        self.ui.about_action.setIcon(get_icon('help-about'))
        self.ui.about_qt_action.triggered.connect(self.about_qt)
        self.ui.about_qt_action.setIcon(get_icon('help-about'))
        self.ui.find_action.setIcon(get_icon('system-search'))
        self.ui.find_action.triggered.connect(self.find_servers)
        self.ui.add_action.setIcon(get_icon('list-add'))
        self.ui.add_action.triggered.connect(self.add_servers)
        self.ui.remove_action.setIcon(get_icon('list-remove'))
        self.ui.remove_action.triggered.connect(self.remove_servers)
        self.ui.identify_action.setIcon(get_icon('dialog-information'))
        self.ui.identify_action.triggered.connect(self.identify)
        self.ui.capture_action.setIcon(get_icon('camera-photo'))
        self.ui.capture_action.triggered.connect(self.capture)
        self.ui.download_action.setIcon(get_icon('go-down'))
        self.ui.download_action.triggered.connect(self.download)
        self.ui.configure_action.setIcon(get_icon('preferences-system'))
        self.ui.configure_action.triggered.connect(self.configure)
        self.ui.select_all_action.setIcon(get_icon('edit-select-all'))
        self.ui.select_all_action.triggered.connect(self.select_all)
        self.ui.refresh_action.setIcon(get_icon('view-refresh'))
        self.ui.refresh_action.triggered.connect(self.refresh)
        self.ui.status_bar_action.triggered.connect(self.toggle_status)
        self.ui.view_menu.aboutToShow.connect(self.update_status)
        # Connect the address list to the model
        self.ui.server_list.setModel(ServersModel(self.client))
        # TODO What about pressing Enter instead of double clicking?
        self.ui.server_list.model().modelReset.connect(
            self.server_list_model_reset)
        self.ui.server_list.model().dataChanged.connect(
            self.server_list_data_changed)
        self.ui.server_list.selectionModel().selectionChanged.connect(
            self.server_list_selection_changed)
        self.ui.server_list.doubleClicked.connect(
            self.server_list_double_clicked)

    @property
    def selected_addresses(self):
        return set(self.ui.server_list.model().addresses(
            i.row() for i in self.ui.server_list.selectionModel().selectedRows()))

    def close(self):
        "Called when the main window is closed"
        self.settings.beginGroup('window')
        try:
            self.settings.setValue('size', self.size())
            self.settings.setValue('position', self.pos())
        finally:
            self.settings.endGroup()
        super(MainWindow, self).close()

    def about(self):
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

    def about_qt(self):
        QtGui.QMessageBox.aboutQt(self, self.tr('About QT'))

    def find_servers(self):
        self.ui.server_list.model().find()
        for col in range(self.ui.server_list.model().columnCount()):
            self.ui.server_list.resizeColumnToContents(col)

    def add_servers(self):
        raise NotImplementedError
        self.ui.server_list.model().add()

    def remove_servers(self):
        self.ui.server_list.model().remove(self.selected_addresses)

    def refresh(self):
        self.ui.server_list.model().refresh()

    def identify(self):
        self.client.identify(self.selected_addresses)

    def capture(self):
        self.client.capture(addresses=self.selected_addresses)
        self.ui.server_list.model().refresh()

    def download(self):
        responses = self.client.list(self.selected_addresses)
        for (address, images) in responses.items():
            if not address in self.images:
                self.images[address] = []
            for image in images:
                output = io.BytesIO()
                self.client.download(address, image.index, output)
                if output.tell() != image.size:
                    raise IOError('Incorrect download size')
                self.images[address].append((image.timestamp, output))
        # XXX Rollback in the case of a partial download...
        self.client.clear(self.selected_addresses)

    def configure(self):
        pass

    def select_all(self):
        pass

    def server_list_double_clicked(self, index):
        pass

    def server_list_model_reset(self):
        self.ui.refresh_action.setEnabled(self.ui.server_list.model().rowCount())
        self.ui.select_all_action.setEnabled(self.ui.server_list.model().rowCount())
        self.ui.download_action.setEnabled(
            any(self.ui.server_list.model().images(addr) > 0
                for addr in self.selected_addresses))

    def server_list_data_changed(self, top_left, bottom_right):
        self.server_list_model_reset()

    def server_list_selection_changed(self, selected, deselected):
        selected = selected.indexes()
        self.ui.remove_action.setEnabled(bool(selected))
        self.ui.identify_action.setEnabled(bool(selected))
        self.ui.capture_action.setEnabled(bool(selected))
        self.ui.configure_action.setEnabled(bool(selected))
        self.ui.download_action.setEnabled(
            any(self.ui.server_list.model().images(addr) > 0
                for addr in self.selected_addresses))

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
    def __init__(self, client):
        super(ServersModel, self).__init__()
        self.client = client
        self.status = []

    def find(self, count=0):
        self.client.find(count)
        self.refresh()

    def add(self, address):
        raise NotImplementedError

    def remove(self, addresses):
        raise NotImplementedError

    def refresh(self):
        self.beginResetModel()
        try:
            self.status = sorted(self.client.status().items())
        finally:
            self.endResetModel()

    def addresses(self, indexes):
        return [self.status[index][0] for index in indexes]

    def images(self, address):
        # XXX Improve this
        try:
            return [s.images for (a, s) in self.status if a == address][0]
        except IndexError:
            raise KeyError(address)

    def rowCount(self, parent=None):
        if parent is None:
            parent = QtCore.QModelIndex()
        if parent.isValid():
            return 0
        return len(self.status)

    def columnCount(self, parent=None):
        if parent is None:
            parent = QtCore.QModelIndex()
        if parent.isValid():
            return 0
        return 4

    def data(self, index, role):
        if not index.isValid():
            return None
        if role != QtCore.Qt.DisplayRole:
            return None
        (address, status) = self.status[index.row()]
        return [
            str(address),
            '%dx%d@%s' % (status.resolution[0], status.resolution[1], status.framerate),
            status.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'),
            str(status.images),
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

    def rowCount(self, parent=None):
        if parent is None:
            parent = QtCore.QModelIndex()
        if parent.isValid():
            return 0

    def data(self, index, role):
        if not index.isValid():
            return None
        if role != QtCore.Qt.DisplayRole:
            return None
