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

from fractions import Fraction

from PyQt4 import QtCore, QtGui, uic

from . import get_ui_file
from ..client import Resolution


class ConfigureDialog(QtGui.QDialog):
    "Implements the servers/configure dialog"

    def __init__(self, parent=None):
        super(ConfigureDialog, self).__init__(parent)
        self.ui = uic.loadUi(get_ui_file('configure_dialog.ui'), self)
        # Populate the combo lists
        self.ui.resolution_combo.setModel(ResolutionsModel())
        self.ui.framerate_combo.setModel(FrameratesModel())
        self.ui.iso_combo.setModel(IsoModel())
        self.ui.awb_combo.setModel(ListModel([
            'auto',
            'cloudy',
            'flash',
            'fluorescent',
            'horizon',
            'incandescent',
            #'off', # XXX Need to add (red,blue) controls
            'shade',
            'sunlight',
            'tungsten',
            ]))
        self.ui.exposure_mode_combo.setModel(ListModel([
            'antishake',
            'auto',
            'backlight',
            'beach',
            'fireworks',
            'fixedfps',
            'night',
            'nightpreview',
            'snow',
            'sports',
            'spotlight',
            'verylong',
            ]))
        self.ui.metering_combo.setModel(ListModel([
            'average',
            'backlit',
            'matrix',
            'spot',
            ]))
        # Connect up signals
        self.ui.button_box.clicked.connect(self.button_box_clicked)
        self.ui.resolution_combo.editTextChanged.connect(self.edit_changed)
        self.ui.framerate_combo.editTextChanged.connect(self.edit_changed)
        self.ui.iso_combo.editTextChanged.connect(self.edit_changed)
        self.ui.awb_combo.currentIndexChanged.connect(self.combo_changed)
        self.ui.exposure_mode_combo.currentIndexChanged.connect(self.combo_changed)
        self.ui.metering_combo.currentIndexChanged.connect(self.combo_changed)
        self.ui.hflip_checkbox.stateChanged.connect(self.checkbox_changed)
        self.ui.vflip_checkbox.stateChanged.connect(self.checkbox_changed)
        self.update_ok()

    def _get_resolution(self):
        s = self.ui.resolution_combo.currentText()
        try:
            width, height = s.split('x', 1)
            width = int(width)
            height = int(height)
            return Resolution(width, height)
        except (TypeError, ValueError):
            return None
    def _set_resolution(self, value):
        if value is None:
            self.ui.resolution_combo.setCurrentIndex(-1)
        elif isinstance(value, str):
            self.ui.resolution_combo.setEditText(value)
        else:
            self.ui.resolution_combo.setCurrentIndex(
                    self.ui.resolution_combo.model().find(value))
    resolution = property(_get_resolution, _set_resolution)

    def _get_framerate(self):
        try:
            return Fraction(
                self.ui.framerate_combo.currentText()
                ).limit_denominator(1000)
        except ValueError:
            return None
    def _set_framerate(self, value):
        if value is None:
            self.ui.framerate_combo.setCurrentIndex(-1)
        elif isinstance(value, str):
            self.ui.framerate_combo.setEditText(value)
        else:
            self.ui.framerate_combo.setCurrentIndex(
                    self.ui.framerate_combo.model().find(value))
    framerate = property(_get_framerate, _set_framerate)

    def _get_shutter_speed(self):
        return int(self.ui.shutter_speed_spinbox.value() * 1000)
    def _set_shutter_speed(self, value):
        if value is None:
            value = 0.0
        self.ui.shutter_speed_spinbox.setValue(value / 1000)
    shutter_speed = property(_get_shutter_speed, _set_shutter_speed)

    def _get_awb_mode(self):
        return self.ui.awb_combo.model().get(self.ui.awb_combo.currentIndex())
    def _set_awb_mode(self, value):
        self.ui.awb_combo.setCurrentIndex(self.ui.awb_combo.model().find(value))
    awb_mode = property(_get_awb_mode, _set_awb_mode)

    def _get_exposure_mode(self):
        return self.ui.exposure_mode_combo.model().get(
                self.ui.exposure_mode_combo.currentIndex())
    def _set_exposure_mode(self, value):
        self.ui.exposure_mode_combo.setCurrentIndex(
                self.ui.exposure_mode_combo.model().find(value))
    exposure_mode = property(_get_exposure_mode, _set_exposure_mode)

    def _get_exposure_compensation(self):
        return self.ui.exposure_comp_slider.value()
    def _set_exposure_compensation(self, value):
        if value is None:
            value = 0
        self.ui.exposure_comp_slider.setValue(value)
    exposure_compensation = property(_get_exposure_compensation, _set_exposure_compensation)

    def _get_iso(self):
        return self.ui.iso_combo.model().get(self.ui.iso_combo.currentIndex())
    def _set_iso(self, value):
        self.ui.iso_combo.setCurrentIndex(
                self.ui.iso_combo.model().find(value))
    iso = property(_get_iso, _set_iso)

    def _get_metering_mode(self):
        return self.ui.metering_combo.model().get(
                self.ui.metering_combo.currentIndex())
    def _set_metering_mode(self, value):
        self.ui.metering_combo.setCurrentIndex(
                self.ui.metering_combo.model().find(value))
    metering_mode = property(_get_metering_mode, _set_metering_mode)

    def _get_brightness(self):
        return self.ui.brightness_slider.value()
    def _set_brightness(self, value):
        if value is None:
            value = 50
        self.ui.brightness_slider.setValue(value)
    brightness = property(_get_brightness, _set_brightness)

    def _get_contrast(self):
        return self.ui.contrast_slider.value()
    def _set_contrast(self, value):
        if value is None:
            value = 0
        self.ui.contrast_slider.setValue(value)
    contrast = property(_get_contrast, _set_contrast)

    def _get_saturation(self):
        return self.ui.saturation_slider.value()
    def _set_saturation(self, value):
        if value is None:
            value = 0
        self.saturation_slider.setValue(value)
    saturation = property(_get_saturation, _set_saturation)

    def _get_hflip(self):
        return {
            QtCore.Qt.Unchecked: False,
            QtCore.Qt.PartiallyChecked: None,
            QtCore.Qt.Checked: True,
            }[self.ui.hflip_checkbox.checkState()]
    def _set_hflip(self, value):
        if value is None:
            self.ui.hflip_checkbox.setTriState()
            self.ui.hflip_checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
        else:
            self.ui.hflip_checkbox.setChecked(value)
    hflip = property(_get_hflip, _set_hflip)

    def _get_vflip(self):
        return {
            QtCore.Qt.Unchecked: False,
            QtCore.Qt.PartiallyChecked: None,
            QtCore.Qt.Checked: True,
            }[self.ui.vflip_checkbox.checkState()]
    def _set_vflip(self, value):
        if value is None:
            self.ui.vflip_checkbox.setTriState()
            self.ui.vflip_checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
        else:
            self.ui.vflip_checkbox.setChecked(value)
    vflip = property(_get_vflip, _set_vflip)

    def edit_changed(self, text):
        self.update_ok()

    def combo_changed(self, index):
        self.update_ok()

    def checkbox_changed(self, state):
        self.update_ok()

    def update_ok(self):
        self.ui.button_box.button(QtGui.QDialogButtonBox.Ok).setEnabled(
                bool(
                    self.resolution and
                    self.framerate and
                    self.awb_mode and
                    self.exposure_mode and
                    self.metering_mode and
                    self.hflip is not None and
                    self.vflip is not None))

    def button_box_clicked(self, button):
        if self.ui.button_box.standardButton(button) == QtGui.QDialogButtonBox.RestoreDefaults:
            self.resolution = (1280, 720)
            self.framerate = 30
            self.shutter_speed = 0
            self.awb_mode = 'auto'
            self.exposure_mode = 'auto'
            self.exposure_compensation = 0
            self.iso = 0
            self.metering_mode = 'average'
            self.brightness = 50
            self.contrast = 0
            self.saturation = 0
            self.hflip = False
            self.vflip = False
            self.update_ok()


class ListModel(QtCore.QAbstractListModel):
    def __init__(self, values):
        super(ListModel, self).__init__()
        self._data = list(values)

    def get(self, index):
        if index == -1:
            return None
        return self._data[index]

    def find(self, value):
        if value is not None:
            for i, d in enumerate(self._data):
                if d == value:
                    return i
        return -1

    def rowCount(self, parent=None):
        if parent is None:
            parent = QtCore.QModelIndex()
        if parent.isValid():
            return 0
        return len(self._data)

    def data(self, index, role):
        if index.isValid():
            if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
                return str(self._data[index.row()])


class ResolutionsModel(ListModel):
    def __init__(self):
        super(ResolutionsModel, self).__init__([
            (Resolution(320, 240),   'QVGA'),
            (Resolution(640, 480),   'VGA'),
            (Resolution(768, 576),   'PAL'),
            (Resolution(800, 600),   'SVGA'),
            (Resolution(1024, 576),  'PAL'),
            (Resolution(1024, 768),  'XGA'),
            (Resolution(1280, 720),  'HD 720'),
            (Resolution(1680, 1050), 'WSXGA+'),
            (Resolution(1920, 1080), 'HD 1080'),
            (Resolution(2048, 1536), 'QXGA'),
            (Resolution(2560, 1440), 'WQHD'),
            (Resolution(2592, 1944), 'Max res'),
            ])

    def find(self, resolution):
        if resolution is not None:
            for i, d in enumerate(self._data):
                if d[0] == resolution:
                    return i
        return -1

    def data(self, index, role):
        if index.isValid():
            resolution, name = self._data[index.row()]
            if role == QtCore.Qt.DisplayRole:
                ratio = Fraction(*resolution)
                return '%s\t(%s - %s)' % (resolution, name, ratio)
            elif role == QtCore.Qt.EditRole:
                return str(resolution)


class FrameratesModel(ListModel):
    def __init__(self):
        super(FrameratesModel, self).__init__([
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
            ])

    def find(self, framerate):
        if framerate is not None:
            for i, d in enumerate(self._data):
                if abs(d - framerate) < 0.001:
                    return i
        return -1

    def data(self, index, role):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                return '%gfps' % self._data[index.row()]
            elif role == QtCore.Qt.EditRole:
                return str(self._data[index.row()])


class IsoModel(ListModel):
    def __init__(self):
        super(IsoModel, self).__init__([
            (0,    'auto'),
            (100,  '100'),
            (200,  '200'),
            (400,  '400'),
            (800,  '800'),
            (1600, '1600'),
            ])

    def get(self, index):
        if index == -1:
            return None
        return self._data[index][0]

    def find(self, value):
        if value is not None:
            for i, d in enumerate(self._data):
                if d[0] == value:
                    return i
        return -1

    def data(self, index, role):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                return self._data[index.row()][1]
            elif role == QtCore.Qt.EditRole:
                return self._data[index.row()][0]


