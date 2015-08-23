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


import io
import os
import time
import shutil
import bisect
from fractions import Fraction
from collections import defaultdict, OrderedDict

import netifaces

from . import get_icon, get_ui_file
from ..client import CompoundPiClient
from ..qt import QtCore, QtGui, loadUi
from .find_dialog import FindDialog
from .configure_dialog import ConfigureDialog
from .capture_dialog import CaptureDialog
from .add_dialog import AddDialog
from .progress_dialog import ProgressDialog


class MainWindow(QtGui.QMainWindow):
    "The Compound Pi GUI main window"

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.client = CompoundPiClient(ProgressHandler(self))
        self.images = defaultdict(OrderedDict)
        self.ui = loadUi(get_ui_file('main_window.ui'), self)
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
        self.ui.reference_action.setIcon(get_icon('emblem-favorite'))
        self.ui.capture_action.setIcon(get_icon('camera-photo'))
        self.ui.copy_action.setIcon(get_icon('edit-copy'))
        self.ui.clear_action.setIcon(get_icon('edit-clear'))
        self.ui.export_action.setIcon(get_icon('document-save'))
        self.ui.refresh_action.setIcon(get_icon('view-refresh'))
        self.ui.move_top_action.setIcon(get_icon('go-top'))
        self.ui.move_up_action.setIcon(get_icon('go-up'))
        self.ui.move_down_action.setIcon(get_icon('go-down'))
        self.ui.move_bottom_action.setIcon(get_icon('go-bottom'))
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
        self.ui.reference_action.triggered.connect(self.servers_reference)
        self.ui.copy_action.triggered.connect(self.images_copy)
        self.ui.export_action.triggered.connect(self.images_export)
        self.ui.clear_action.triggered.connect(self.images_clear)
        self.ui.refresh_action.triggered.connect(self.view_refresh)
        self.ui.toolbars_servers_action.triggered.connect(self.view_toolbars_servers)
        self.ui.toolbars_actions_action.triggered.connect(self.view_toolbars_actions)
        self.ui.status_bar_action.triggered.connect(self.view_status_bar)
        self.ui.move_top_action.triggered.connect(self.servers_move_top)
        self.ui.move_up_action.triggered.connect(self.servers_move_up)
        self.ui.move_down_action.triggered.connect(self.servers_move_down)
        self.ui.move_bottom_action.triggered.connect(self.servers_move_bottom)
        self.ui.view_menu.aboutToShow.connect(self.update_view)
        self.ui.toolbars_menu.aboutToShow.connect(self.update_toolbars)
        # Connect the lists to their models
        self.ui.server_list.setModel(ServersModel(self))
        self.ui.image_list.setModel(ImagesModel(self))
        self.ui.server_list.model().modelReset.connect(
            self.server_list_model_reset)
        self.ui.server_list.model().dataChanged.connect(
            self.server_list_data_changed)
        # Workaround: PySide has a nasty bug causing a segfault without this
        # intermediate model variable...
        model = self.ui.server_list.selectionModel()
        model.selectionChanged.connect(self.server_list_selection_changed)
        self.ui.server_list.customContextMenuRequested.connect(
            self.server_list_context_menu)
        self.ui.image_list.model().modelReset.connect(
            self.image_list_model_reset)
        self.ui.image_list.model().dataChanged.connect(
            self.image_list_data_changed)
        # Workaround: same as above
        model = self.ui.image_list.selectionModel()
        model.selectionChanged.connect(self.image_list_selection_changed)
        self.ui.image_list.customContextMenuRequested.connect(
            self.image_list_context_menu)

    @property
    def selected_images(self):
        return self.ui.image_list.model().get(
            [i.row() for i in self.ui.image_list.selectionModel().selectedIndexes()]
            )

    def _get_selected_indexes(self):
        return [i.row() for i in self.ui.server_list.selectionModel().selectedRows()]
    def _set_selected_indexes(self, value):
        model = self.ui.server_list.model()
        selection = QtGui.QItemSelection()
        for index in value:
            selection.select(model.index(index, 0), model.index(index, model.columnCount() - 1))
        self.ui.server_list.selectionModel().select(selection, QtGui.QItemSelectionModel.ClearAndSelect)
    selected_indexes = property(_get_selected_indexes, _set_selected_indexes, doc="""
        The list of all selected indexes in the server_list. This property can
        be queried to determine the currently selected indexes, or set to
        change the currently selected indexes.
        """)

    def _get_current_index(self):
        return self.ui.server_list.selectionModel().currentIndex().row()
    def _set_current_index(self, value):
        self.ui.server_list.selectionModel().setCurrentIndex(
            self.ui.server_list.model().index(value, 0), QtGui.QItemSelectionModel.Current)
    current_index = property(_get_current_index, _set_current_index, doc="""
        The current index in the server_list. This property can be queried to
        determine the index with focus (the current index), or set to change
        the index with focus.
        """)

    @property
    def selected_data(self):
        """
        Returns a list of (address, status) tuples. This list is guaranteed to
        be in the same order as that returned by :attr:`selected_indexes`
        provided no alteration occurs between queries.
        """
        return self.ui.server_list.model().get(self.selected_indexes)

    @property
    def selected_addresses(self):
        """
        Returns a list of all selected addresses, in the same order as that
        returned by :attr:`selected_indexes`.
        """
        return [a for (a, s) in self.selected_data]

    def closeEvent(self, event):
        app = QtGui.QApplication.instance()
        if app.clipboard().ownsClipboard():
            app.clipboard().clear()
        self.settings.beginGroup('window')
        try:
            self.settings.setValue('size', self.size())
            self.settings.setValue('position', self.pos())
        finally:
            self.settings.endGroup()
        self.client.close()
        super(MainWindow, self).closeEvent(event)

    def help_about(self):
        QtGui.QMessageBox.about(self,
            'About {}'.format(
                QtGui.QApplication.instance().applicationName()),
            """\
<b>{application}</b>
<p>Version {version}</p>
<p>{application} is a GUI for controlling multiple Compound Pi servers.
The project homepage and documentation is at
<a href="{url}">{url}</a></p>
<p>Copyright &copy; 2012-2013 {author} &lt;<a href="mailto:{author_email}">{author_email}</a>&gt;</p>""".format(
                application=QtGui.QApplication.instance().applicationName(),
                version=QtGui.QApplication.instance().applicationVersion(),
                url='http://compoundpi.readthedocs.org/',
                author='Dave Hughes',
                author_email='dave@waveform.org.uk',
            ))

    def help_about_qt(self):
        QtGui.QMessageBox.aboutQt(self, 'About QT')

    def servers_find(self):
        dialog = FindDialog(self)
        self.settings.beginGroup('network')
        try:
            dialog.interface = self.settings.value('interface', '')
            dialog.port = self.settings.value('port', 5647)
            dialog.timeout = self.settings.value('timeout', 15)
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
                self.servers_resize_columns()
        finally:
            self.settings.endGroup()

    def servers_add(self):
        dialog = AddDialog(self)
        if dialog.exec_():
            self.ui.server_list.model().add(dialog.server)
            self.servers_resize_columns()

    def servers_remove(self):
        self.ui.server_list.model().remove(self.selected_addresses)
        self.servers_resize_columns()

    def servers_move_top(self):
        self.selected_indexes = self.ui.server_list.model().move_top(self.selected_indexes)
        self.current_index = 0

    def servers_move_up(self):
        self.selected_indexes = self.ui.server_list.model().move_up(self.selected_indexes)
        self.current_index -= 1

    def servers_move_down(self):
        self.selected_indexes = self.ui.server_list.model().move_down(self.selected_indexes)
        self.current_index += 1

    def servers_move_bottom(self):
        self.selected_indexes = self.ui.server_list.model().move_bottom(self.selected_indexes)
        self.current_index = self.ui.server_list.model().rowCount() - 1

    def servers_resize_columns(self):
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
            dialog.capture_quality = int(self.settings.value('quality', 85))
            dialog.capture_video_port = int(self.settings.value('video_port', 0))
            if dialog.exec_():
                self.settings.setValue('count', dialog.capture_count)
                self.settings.setValue('delay', dialog.capture_delay or 0.0)
                self.settings.setValue('quality', dialog.capture_quality)
                self.settings.setValue('video_port', int(dialog.capture_video_port))
                self.client.capture(
                        count=dialog.capture_count,
                        video_port=dialog.capture_video_port,
                        quality=dialog.capture_quality,
                        delay=dialog.capture_delay,
                        addresses=self.selected_addresses)
                responses = self.client.list(self.selected_addresses)
                for (address, files) in responses.items():
                    for f in files:
                        if f.filetype == 'IMAGE':
                            stream = io.BytesIO()
                            self.client.download(address, f.index, stream)
                            if stream.tell() != f.size:
                                raise IOError('Incorrect download size')
                            self.images[address][f.timestamp] = stream
                # XXX Check ordering of self.images[address]
                # XXX Rollback in the case of a partial download...
                self.client.clear(self.selected_addresses)
                self.ui.server_list.model().refresh_selected()
                self.ui.image_list.model().refresh()
        finally:
            self.settings.endGroup()

    def servers_configure(self):
        settings = {
            attr: set(getattr(status, attr) for (addr, status) in self.selected_data)
            for attr in (
                'resolution',
                'framerate',
                'agc_mode',
                'agc_analog',
                'agc_digital',
                'awb_mode',
                'awb_red',
                'awb_blue',
                'exposure_mode',
                'exposure_speed',
                'iso',
                'metering_mode',
                'brightness',
                'contrast',
                'saturation',
                'ev',
                'hflip',
                'vflip',
                'denoise',
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
                if dialog.agc_mode != settings['agc_mode']:
                    self.client.agc(
                            dialog.agc_mode,
                            addresses=self.selected_addresses)
                if (dialog.awb_mode != settings['awb_mode']) or (
                        dialog.awb_mode == 'off' and (
                            dialog.awb_red != settings['awb_red'] or
                            dialog.awb_blue != settings['awb_blue']
                            )):
                    self.client.awb(
                            dialog.awb_mode,
                            dialog.awb_red,
                            dialog.awb_blue,
                            addresses=self.selected_addresses)
                if (dialog.exposure_mode != settings['exposure_mode']) or (
                        dialog.exposure_mode == 'off' and
                        dialog.exposure_speed != settings['exposure_speed']
                        ):
                    self.client.exposure(
                            dialog.exposure_mode,
                            dialog.exposure_speed,
                            addresses=self.selected_addresses)
                if dialog.metering_mode != settings['metering_mode']:
                    self.client.metering(
                            dialog.metering_mode,
                            addresses=self.selected_addresses)
                if dialog.iso != settings['iso']:
                    self.client.iso(
                            dialog.iso,
                            addresses=self.selected_addresses)
                if dialog.brightness != settings['brightness']:
                    self.client.brightness(
                            dialog.brightness,
                            addresses=self.selected_addresses)
                if dialog.contrast != settings['contrast']:
                    self.client.contrast(
                            dialog.contrast,
                            addresses=self.selected_addresses)
                if dialog.saturation != settings['saturation']:
                    self.client.saturation(
                            dialog.saturation,
                            addresses=self.selected_addresses)
                if dialog.ev != settings['ev']:
                    self.client.ev(
                            dialog.ev,
                            addresses=self.selected_addresses)
                if (
                        dialog.hflip != settings['hflip'] or
                        dialog.vflip != settings['vflip']
                        ):
                    self.client.flip(
                            dialog.hflip, dialog.vflip,
                            addresses=self.selected_addresses)
                if dialog.denoise != settings['denoise']:
                    self.client.denoise(
                            dialog.denoise,
                            addresses=self.selected_addresses)
            finally:
                self.ui.server_list.model().refresh_selected(update=True)

    def servers_reference(self):
        # There can be only one! ... selected server that is
        addr, status = next(iter(self.selected_data))
        try:
            # Before we go setting resolution and framerate (which will reset
            # the cameras, ensure AGC gains are allowed to float)
            self.client.agc('auto')
            self.client.resolution(*status.resolution)
            self.client.framerate(status.framerate)
            if status.awb_mode == 'off':
                self.client.awb('off', status.awb_red, status.awb_blue)
            else:
                self.client.awb(status.awb_mode)
            if status.agc_mode == 'off':
                # We've just reset the resolution and framerate which has reset
                # all the cameras. Given we can't directly set the gains we
                # need to wait a decent number of frames to let the gains
                # settle before we disable AGC. Here we wait long enough for 30
                # frames to have been captured (1 second at "normal"
                # framerates)
                time.sleep(30.0 / status.framerate)
                self.client.agc('off')
            else:
                self.client.agc(status.agc_mode)
            if status.exposure_mode == 'off':
                self.client.exposure('off', status.exposure_speed)
            else:
                self.client.exposure(status.exposure_mode)
            self.client.ev(status.ev)
            self.client.iso(status.iso)
            self.client.metering(status.metering_mode)
            self.client.brightness(status.brightness)
            self.client.contrast(status.contrast)
            self.client.saturation(status.saturation)
            self.client.denoise(status.denoise)
            self.client.flip(status.hflip, status.vflip)
        finally:
            self.ui.server_list.model().refresh_all(update=True)

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

    def update_view(self):
        self.ui.status_bar_action.setChecked(self.statusBar().isVisible())

    def update_toolbars(self):
        self.ui.toolbars_servers_action.setChecked(self.ui.servers_toolbar.isVisible())
        self.ui.toolbars_actions_action.setChecked(self.ui.actions_toolbar.isVisible())

    def view_toolbars_servers(self):
        if self.ui.servers_toolbar.isVisible():
            self.ui.servers_toolbar.hide()
        else:
            self.ui.servers_toolbar.show()

    def view_toolbars_actions(self):
        if self.ui.actions_toolbar.isVisible():
            self.ui.actions_toolbar.hide()
        else:
            self.ui.actions_toolbar.show()

    def view_status_bar(self):
        if self.statusBar().isVisible():
            self.statusBar().hide()
        else:
            self.statusBar().show()

    def view_refresh(self):
        self.ui.server_list.model().refresh_all(update=True)

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
        menu.addAction(self.ui.reference_action)
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
        row_count = self.ui.server_list.model().rowCount()
        selected_indexes = self.selected_indexes
        has_rows = row_count > 0
        has_selection = bool(selected_indexes)
        one_selected = len(selected_indexes) == 1
        top_selected = 0 in selected_indexes
        bottom_selected = (row_count - 1) in selected_indexes
        self.ui.remove_action.setEnabled(has_selection)
        self.ui.identify_action.setEnabled(has_selection)
        self.ui.capture_action.setEnabled(has_selection)
        self.ui.configure_action.setEnabled(has_selection)
        self.ui.reference_action.setEnabled(one_selected)
        self.ui.refresh_action.setEnabled(has_rows)
        self.ui.move_top_action.setEnabled(has_selection and not top_selected)
        self.ui.move_up_action.setEnabled(has_selection and not top_selected)
        self.ui.move_down_action.setEnabled(has_selection and not bottom_selected)
        self.ui.move_bottom_action.setEnabled(has_selection and not bottom_selected)
        self.ui.image_list.model().refresh()

    def update_image_actions(self):
        has_selection = self.ui.image_list.selectionModel().hasSelection()
        one_selected = len(self.ui.image_list.selectionModel().selectedIndexes()) == 1
        self.ui.copy_action.setEnabled(one_selected)
        self.ui.export_action.setEnabled(has_selection)
        self.ui.clear_action.setEnabled(has_selection)


class ProgressHandler(QtCore.QObject):
    "Links progress events to the progress dialog"

    progress_start_signal = QtCore.Signal(int)
    progress_update_signal = QtCore.Signal(int)
    progress_finish_signal = QtCore.Signal()

    def __init__(self, parent):
        super(ProgressHandler, self).__init__(parent)
        self.parent = parent
        self.progress_dialog = None
        self.progress_time = None
        self.progress_start_signal.connect(self.progress_start_slot)
        self.progress_update_signal.connect(self.progress_update_slot)
        self.progress_finish_signal.connect(self.progress_finish_slot)

    # All the messing around with signals and slots below is required as the
    # progress handlers aren't necessarily called from the main thread

    def start(self, count):
        # Before we start another progress window, make sure any events to do
        # with existing progress windows have been processed
        QtGui.QApplication.instance().sendPostedEvents()
        self.progress_start_signal.emit(count)

    def update(self, count):
        self.progress_update_signal.emit(count)

    def finish(self):
        self.progress_finish_signal.emit()

    @QtCore.Slot(int)
    def progress_start_slot(self, count):
        assert not self.progress_dialog
        self.progress_dialog = ProgressDialog(self.parent)
        self.progress_dialog.show()
        self.progress_dialog.task = self.tr('Progress')
        self.progress_dialog.limits = (0, count)
        QtGui.QApplication.instance().setOverrideCursor(QtCore.Qt.WaitCursor)

    @QtCore.Slot(int)
    def progress_update_slot(self, count):
        now = time.time()
        # Only bother updating the progress dialog if it's been at least
        # 0.1 seconds since we last updated it
        if (self.progress_time is None) or (now - self.progress_time) > 0.1:
            self.progress_time = now
            if self.progress_dialog.cancelled:
                raise KeyboardInterrupt
            self.progress_dialog.progress = count

    @QtCore.Slot()
    def progress_finish_slot(self):
        QtGui.QApplication.instance().restoreOverrideCursor()
        self.progress_dialog.close()
        self.progress_dialog = None


class ServersModel(QtCore.QAbstractTableModel):
    def __init__(self, parent):
        super(ServersModel, self).__init__()
        self.parent = parent
        self._data = {}

    def find(self, count=0):
        self.beginResetModel()
        try:
            self.parent.client.servers.find(count)
            self._data = self.parent.client.status()
        finally:
            self.endResetModel()

    def refresh_all(self, update=False):
        if update:
            self._data = self.parent.client.status()
        first = self.index(0, 0)
        last = self.index(self.rowCount(), self.columnCount() - 1)
        self.dataChanged.emit(first, last)

    def refresh_selected(self, update=False):
        if update:
            self._data.update(self.parent.client.status(self.parent.selected_addresses))
        # XXX This is lazy
        self.refresh_all()

    def add(self, address):
        self.parent.client.servers.append(address)
        self.beginInsertRows(QtCore.QModelIndex(), len(self._data), len(self._data))
        try:
            self._data[address] = self.parent.client.status([address])[address]
        finally:
            self.endInsertRows()

    def remove(self, addresses):
        for address in addresses:
            i = self.parent.client.servers.index(address)
            self.beginRemoveRows(QtCore.QModelIndex(), i, i)
            try:
                del self._data[address]
                self.parent.client.servers.remove(address)
            finally:
                self.endRemoveRows()

    def move_up(self, indexes, by=1):
        indexes = sorted(indexes)
        for index in indexes:
            assert index >= by
            self.parent.client.servers.move(index - by, self.parent.client.servers[index])
        first = self.index(indexes[0] - (by - 1), 0)
        last = self.index(indexes[-1] + 1, self.columnCount() - 1)
        self.dataChanged.emit(first, last)
        return [i - by for i in indexes]

    def move_down(self, indexes, by=1):
        indexes = sorted(indexes, reverse=True)
        final = self.rowCount() - by
        for index in indexes:
            assert index < final
            self.parent.client.servers.move(index + by, self.parent.client.servers[index])
        first = self.index(indexes[-1] - 1, 0)
        last = self.index(indexes[0] + by, self.columnCount() - 1)
        self.dataChanged.emit(first, last)
        return [i + by for i in indexes]

    def move_top(self, indexes):
        indexes = sorted(indexes)
        return self.move_up(indexes, by=indexes[0])

    def move_bottom(self, indexes):
        indexes = sorted(indexes, reverse=True)
        return self.move_down(indexes, by=self.rowCount() - 1 - indexes[0])

    def get(self, indexes):
        return [
            (address, self._data[address])
            for index in indexes
            for address in (self.parent.client.servers[index],)
            ]

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
            address = self.parent.client.servers[index.row()]
            status = self._data[address]
            return [
                str(address),
                '%dx%d@%sfps' % (
                    status.resolution[0],
                    status.resolution[1],
                    status.framerate,
                    ),
                '%s (%.1f,%.1f)' % (
                    status.agc_mode,
                    status.agc_analog,
                    status.agc_digital,
                    ),
                '%s (%.1f,%.1f)' % (
                    status.awb_mode,
                    status.awb_red,
                    status.awb_blue,
                    ),
                '%s (%.2fms)' % (
                    status.exposure_mode,
                    status.exposure_speed,
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
                'AGC',
                'AWB',
                'Exposure',
                'Metering',
                'Flip',
                'Time',
                'Images',
                ][section]
        elif orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
            return section + 1

    def flags(self, index):
        flags = super(ServersModel, self).flags(index) | QtCore.Qt.ItemIsDropEnabled
        if index.isValid():
            flags |= QtCore.Qt.ItemIsDragEnabled
        return flags

    def supportedDropActions(self):
        return QtCore.Qt.MoveAction


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
