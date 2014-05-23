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
import os
import shutil
import bisect
from fractions import Fraction
from collections import defaultdict, OrderedDict

import netifaces
from PyQt4 import QtCore, QtGui, uic

from . import get_icon, get_ui_file
from ..client import CompoundPiClient
from .find_dialog import FindDialog
from .configure_dialog import ConfigureDialog
from .capture_dialog import CaptureDialog
from .add_dialog import AddDialog


class MainWindow(QtGui.QMainWindow):
    "The Compound Pi GUI main window"

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.client = CompoundPiClient(progress=(
            self.progress_start,
            self.progress_update,
            self.progress_finish,
            ))
        self.images = defaultdict(OrderedDict)
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
        self.ui.configure_action.setIcon(get_icon('preferences-system'))
        self.ui.capture_action.setIcon(get_icon('camera-photo'))
        self.ui.copy_action.setIcon(get_icon('edit-copy'))
        self.ui.clear_action.setIcon(get_icon('edit-clear'))
        self.ui.export_action.setIcon(get_icon('document-save'))
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
        self.ui.copy_action.triggered.connect(self.images_copy)
        self.ui.export_action.triggered.connect(self.images_export)
        self.ui.clear_action.triggered.connect(self.images_clear)
        self.ui.refresh_action.triggered.connect(self.view_refresh)
        self.ui.toolbar_action.triggered.connect(self.view_toolbar)
        self.ui.status_bar_action.triggered.connect(self.view_status_bar)
        self.ui.view_menu.aboutToShow.connect(self.update_view)
        # Connect the lists to their models
        self.ui.server_list.setModel(ServersModel(self))
        self.ui.image_list.setModel(ImagesModel(self))
        self.ui.server_list.model().modelReset.connect(
            self.server_list_model_reset)
        self.ui.server_list.model().dataChanged.connect(
            self.server_list_data_changed)
        self.ui.server_list.selectionModel().selectionChanged.connect(
            self.server_list_selection_changed)
        self.ui.server_list.customContextMenuRequested.connect(
            self.server_list_context_menu)
        self.ui.image_list.model().modelReset.connect(
            self.image_list_model_reset)
        self.ui.image_list.model().dataChanged.connect(
            self.image_list_data_changed)
        self.ui.image_list.selectionModel().selectionChanged.connect(
            self.image_list_selection_changed)
        self.ui.image_list.customContextMenuRequested.connect(
            self.image_list_context_menu)

    @property
    def selected_images(self):
        return self.ui.image_list.model().get(
            [i.row() for i in self.ui.image_list.selectionModel().selectedIndexes()]
            )

    @property
    def selected_servers(self):
        return self.ui.server_list.model().get(
            [i.row() for i in self.ui.server_list.selectionModel().selectedRows()]
            )

    @property
    def selected_addresses(self):
        return [a for (a, s) in self.selected_servers]

    def closeEvent(self, event):
        super(MainWindow, self).closeEvent(event)
        app = QtGui.QApplication.instance()
        if app.clipboard().ownsClipboard():
            app.clipboard().clear()
        self.settings.beginGroup('window')
        try:
            self.settings.setValue('size', self.size())
            self.settings.setValue('position', self.pos())
        finally:
            self.settings.endGroup()

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
        self.settings.beginGroup('network')
        try:
            dialog.interface = self.settings.value('interface', '')
            dialog.port = self.settings.value('port', 5647)
            dialog.timeout = self.settings.value('timeout', 5)
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
                self.settings.setValue('timeout', dialog.timeout)
                self.settings.setValue('expected_count', dialog.expected_count)
                self.client.network = '%s/%s' % (iface['addr'], iface['netmask'])
                self.client.port = dialog.port
                self.client.timeout = dialog.timeout
                self.ui.server_list.model().find(count=dialog.expected_count)
                for col in range(self.ui.server_list.model().columnCount()):
                    self.ui.server_list.resizeColumnToContents(col)
        finally:
            self.settings.endGroup()

    def servers_add(self):
        dialog = AddDialog(self)
        if dialog.exec_():
            self.ui.server_list.model().add(dialog.server)
            for col in range(self.ui.server_list.model().columnCount()):
                self.ui.server_list.resizeColumnToContents(col)

    def servers_remove(self):
        self.ui.server_list.model().remove(self.selected_addresses)
        for col in range(self.ui.server_list.model().columnCount()):
            self.ui.server_list.resizeColumnToContents(col)

    def servers_identify(self):
        self.client.identify(self.selected_addresses)

    def servers_capture(self):
        dialog = CaptureDialog(self)
        self.settings.beginGroup('capture')
        try:
            dialog.capture_count = int(self.settings.value('count', 1))
            dialog.capture_delay = float(self.settings.value('delay', 0.00))
            dialog.capture_video_port = int(self.settings.value('video_port', 0))
            if dialog.exec_():
                self.settings.setValue('count', dialog.capture_count)
                self.settings.setValue('delay', dialog.capture_delay or 0.0)
                self.settings.setValue('video_port', int(dialog.capture_video_port))
                self.client.capture(
                        count=dialog.capture_count,
                        video_port=dialog.capture_video_port,
                        delay=dialog.capture_delay,
                        addresses=self.selected_addresses)
                responses = self.client.list(self.selected_addresses)
                for (address, images) in responses.items():
                    for image in images:
                        stream = io.BytesIO()
                        self.client.download(address, image.index, stream)
                        if stream.tell() != image.size:
                            raise IOError('Incorrect download size')
                        self.images[address][image.timestamp] = stream
                # XXX Check ordering of self.images[address]
                # XXX Rollback in the case of a partial download...
                self.client.clear(self.selected_addresses)
                self.ui.server_list.model().refresh_selected()
                self.ui.image_list.model().refresh()
        finally:
            self.settings.endGroup()

    def servers_configure(self):
        settings = {
            attr: set(getattr(status, attr) for (addr, status) in self.selected_servers)
            for attr in (
                'resolution',
                'framerate',
                'shutter_speed',
                'awb_mode',
                'exposure_mode',
                'exposure_compensation',
                'iso',
                'metering_mode',
                'brightness',
                'contrast',
                'saturation',
                'hflip',
                'vflip',
                )}
        settings = {
            attr: values.pop() if len(values) == 1 else None
            for (attr, values) in settings.items()
            }
        dialog = ConfigureDialog(self)
        for attr, value in settings.items():
            setattr(dialog, attr, value)
        if dialog.exec_():
            try:
                if dialog.resolution != settings['resolution']:
                    self.client.resolution(
                            *dialog.resolution,
                            addresses=self.selected_addresses)
                if dialog.framerate != settings['framerate']:
                    self.client.framerate(
                            dialog.framerate,
                            addresses=self.selected_addresses)
                if dialog.shutter_speed != settings['shutter_speed']:
                    self.client.shutter_speed(
                            dialog.shutter_speed,
                            addresses=self.selected_addresses)
                if dialog.awb_mode != settings['awb_mode']:
                    self.client.awb(
                            dialog.awb_mode,
                            addresses=self.selected_addresses)
                if (
                        dialog.exposure_mode != settings['exposure_mode'] or
                        dialog.exposure_compensation != settings['exposure_compensation']
                        ):
                    self.client.exposure(
                            dialog.exposure_mode, dialog.exposure_compensation,
                            addresses=self.selected_addresses)
                if dialog.metering_mode != settings['metering_mode']:
                    self.client.metering(
                            dialog.metering_mode,
                            addresses=self.selected_addresses)
                if dialog.iso != settings['iso']:
                    self.client.iso(
                            dialog.iso,
                            addresses=self.selected_addresses)
                if (
                        dialog.brightness != settings['brightness'] or
                        dialog.contrast != settings['contrast'] or
                        dialog.saturation != settings['saturation']
                        ):
                    self.client.levels(
                            dialog.brightness, dialog.contrast, dialog.saturation,
                            addresses=self.selected_addresses)
                if (
                        dialog.hflip != settings['hflip'] or
                        dialog.vflip != settings['vflip']
                        ):
                    self.client.flip(
                            dialog.hflip, dialog.vflip,
                            addresses=self.selected_addresses)
            finally:
                self.ui.server_list.model().refresh_selected(update=True)

    def images_copy(self):
        _, _, _, stream = self.selected_images[0]
        image = QtGui.QImage()
        image.loadFromData(stream.getvalue())
        QtGui.QApplication.instance().clipboard().setImage(image)

    def images_export(self):
        directory = QtGui.QFileDialog.getExistingDirectory(
            self, 'Select Export Directory', os.getcwd())
        if directory:
            self.settings.beginGroup('export')
            try:
                pattern = self.settings.value('pattern', '{timestamp:%Y%m%d%H%M%S}-{address}.jpg')
            finally:
                self.settings.endGroup()
            QtGui.QApplication.instance().setOverrideCursor(QtCore.Qt.WaitCursor)
            try:
                for index, (address, timestamp, _, source) in enumerate(self.selected_images):
                    filename = os.path.join(directory, pattern.format(
                        timestamp=timestamp,
                        address=address,
                        index=index,
                        count=len(os.listdir(directory))
                        ))
                    with io.open(filename, 'wb') as target:
                        source.seek(0)
                        shutil.copyfileobj(source, target)
            finally:
                QtGui.QApplication.instance().restoreOverrideCursor()

    def images_clear(self):
        for address, timestamp, _, _ in self.selected_images:
            del self.images[address][timestamp]
        self.ui.server_list.model().refresh_selected()
        self.ui.image_list.model().refresh()

    def view_refresh(self):
        self.ui.server_list.model().refresh_all(update=True)

    def view_toolbar(self):
        if self.ui.tool_bar.isVisible():
            self.ui.tool_bar.hide()
        else:
            self.ui.tool_bar.show()

    def view_status_bar(self):
        if self.statusBar().isVisible():
            self.statusBar().hide()
        else:
            self.statusBar().show()

    def server_list_model_reset(self):
        self.update_server_actions()

    def server_list_data_changed(self, top_left, bottom_right):
        self.update_server_actions()

    def server_list_selection_changed(self, selected, deselected):
        self.update_server_actions()

    def server_list_context_menu(self, pos):
        menu = QtGui.QMenu(self)
        menu.addAction(self.ui.add_action)
        menu.addAction(self.ui.remove_action)
        menu.addSeparator()
        menu.addAction(self.ui.identify_action)
        menu.addAction(self.ui.configure_action)
        menu.addAction(self.ui.capture_action)
        menu.popup(self.ui.server_list.viewport().mapToGlobal(pos))

    def image_list_model_reset(self):
        self.update_image_actions()

    def image_list_data_changed(self, top_left, bottom_right):
        self.update_image_actions()

    def image_list_selection_changed(self, selected, deselected):
        self.update_image_actions()

    def image_list_context_menu(self, pos):
        menu = QtGui.QMenu(self)
        menu.addAction(self.ui.copy_action)
        menu.addAction(self.ui.export_action)
        menu.addAction(self.ui.clear_action)
        menu.popup(self.ui.image_list.viewport().mapToGlobal(pos))

    def update_server_actions(self):
        has_rows = self.ui.server_list.model().rowCount() > 0
        has_selection = self.ui.server_list.selectionModel().hasSelection()
        self.ui.remove_action.setEnabled(has_selection)
        self.ui.identify_action.setEnabled(has_selection)
        self.ui.capture_action.setEnabled(has_selection)
        self.ui.configure_action.setEnabled(has_selection)
        self.ui.refresh_action.setEnabled(has_rows)
        self.ui.image_list.model().refresh()

    def update_image_actions(self):
        has_selection = self.ui.image_list.selectionModel().hasSelection()
        one_selected = len(self.ui.image_list.selectionModel().selectedIndexes()) == 1
        self.ui.copy_action.setEnabled(one_selected)
        self.ui.export_action.setEnabled(has_selection)
        self.ui.clear_action.setEnabled(has_selection)

    def update_view(self):
        self.ui.toolbar_action.setChecked(self.ui.tool_bar.isVisible())
        self.ui.status_bar_action.setChecked(self.statusBar().isVisible())

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

    def refresh_all(self, update=False):
        if update:
            self._data = sorted(self.parent.client.status().items())
        first = self.index(0, 0)
        last = self.index(self.rowCount(), self.columnCount() - 1)
        self.dataChanged.emit(first, last)

    def refresh_selected(self, update=False):
        if update:
            data = dict(self._data)
            data.update(self.parent.client.status(self.parent.selected_addresses))
            self._data = sorted(data.items())
        self.refresh_all()

    def add(self, address):
        self.parent.client.add([address])
        i = bisect.bisect_left(self._data, (address, None))
        self.beginInsertRows(QtCore.QModelIndex(), i, i)
        try:
            self._data.insert(i,
                (address, self.parent.client.status([address])[address]))
        finally:
            self.endInsertRows()

    def remove(self, addresses):
        for address in addresses:
            i = bisect.bisect_left(self._data, (address, None))
            self.beginRemoveRows(QtCore.QModelIndex(), i, i)
            try:
                self.parent.client.remove([address])
                del self._data[i]
            finally:
                self.endRemoveRows()

    def get(self, indexes):
        return [self._data[index] for index in indexes]

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
        return 9

    def data(self, index, role):
        if index.isValid() and role == QtCore.Qt.DisplayRole:
            (address, status) = self._data[index.row()]
            return [
                str(address),
                '%dx%d@%sfps' % (status.resolution[0], status.resolution[1], status.framerate),
                'auto' if status.shutter_speed == 0 else '%.2fms' % (status.shutter_speed / 1000),
                status.awb_mode,
                '%s (%s%s stops)' % (
                    status.exposure_mode,
                    '+' if status.exposure_compensation >= 0 else '',
                    Fraction(status.exposure_compensation, 6)
                    ),
                status.metering_mode,
                (
                    'both' if status.vflip and status.hflip else
                    'vert' if status.vflip else
                    'horz' if status.hflip else
                    'none'
                    ),
                status.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'),
                str(len(self.parent.images[address])),
                ][index.column()]

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return [
                'Address',
                'Mode',
                'Shutter',
                'AWB',
                'Exposure',
                'Metering',
                'Flip',
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

    def get(self, indexes):
        return [self._data[index] for index in indexes]

    def refresh(self):
        self.beginResetModel()
        try:
            self._data = []
            for address in self.parent.selected_addresses:
                for timestamp, stream in self.parent.images[address].items():
                    try:
                        thumbnail = self._cache[(address, timestamp)]
                    except KeyError:
                        image = QtGui.QPixmap()
                        image.loadFromData(stream.getvalue())
                        thumbnail = image.scaledToWidth(200)
                        self._cache[(address, timestamp)] = thumbnail
                    self._data.append(
                        (address, timestamp, thumbnail, stream))
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
            address, timestamp, thumbnail, _ = self._data[index.row()]
            if role == QtCore.Qt.DisplayRole:
                return '{ts:%Y-%m-%d %H:%M:%S}\n{addr}'.format(ts=timestamp, addr=address)
            elif role == QtCore.Qt.DecorationRole:
                return thumbnail
