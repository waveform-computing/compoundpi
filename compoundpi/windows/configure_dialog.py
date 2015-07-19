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

from fractions import Fraction

from . import get_ui_file
from ..client import Resolution
from ..qt import QtCore, QtGui, loadUi


class ConfigureDialog(QtGui.QDialog):
    "Implements the servers/configure dialog"

    def __init__(self, parent=None):
        super(ConfigureDialog, self).__init__(parent)
        self.ui = loadUi(get_ui_file('configure_dialog.ui'), self)
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
            'shade',
            'sunlight',
            'tungsten',
            ]))
        self.ui.agc_combo.setModel(ListModel([
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
        # Construct radio groups
        self.agc_group = QtGui.QButtonGroup(self)
        self.agc_group.addButton(self.ui.agc_auto_radio)
        self.agc_group.addButton(self.ui.agc_manual_radio)
        self.awb_group = QtGui.QButtonGroup(self)
        self.awb_group.addButton(self.ui.awb_auto_radio)
        self.awb_group.addButton(self.ui.awb_manual_radio)
        self.exposure_group = QtGui.QButtonGroup(self)
        self.exposure_group.addButton(self.ui.exposure_auto_radio)
        self.exposure_group.addButton(self.ui.exposure_manual_radio)
        # Connect up signals
        self.ui.button_box.clicked.connect(self.button_box_clicked)
        self.ui.resolution_combo.editTextChanged.connect(self.edit_changed)
        self.ui.framerate_combo.editTextChanged.connect(self.edit_changed)
        self.ui.iso_combo.editTextChanged.connect(self.edit_changed)
        self.ui.agc_auto_radio.toggled.connect(self.agc_radio_changed)
        self.ui.agc_manual_radio.toggled.connect(self.agc_radio_changed)
        self.ui.agc_combo.currentIndexChanged.connect(self.combo_changed)
        self.ui.awb_auto_radio.toggled.connect(self.awb_radio_changed)
        self.ui.awb_manual_radio.toggled.connect(self.awb_radio_changed)
        self.ui.awb_combo.currentIndexChanged.connect(self.combo_changed)
        self.ui.exposure_auto_radio.toggled.connect(self.exposure_radio_changed)
        self.ui.exposure_manual_radio.toggled.connect(self.exposure_radio_changed)
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
            i = self.ui.resolution_combo.model().find(value)
            if i == -1:
                self.ui.resolution_combo.setEditText(
                        '%dx%d' % (value.width, value.height))
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

    def _get_awb_mode(self):
        if self.ui.awb_auto_radio.isChecked():
            return self.ui.awb_combo.model().get(self.ui.awb_combo.currentIndex())
        elif self.ui.awb_manual_radio.isChecked():
            return 'off'
        else:
            return None
    def _set_awb_mode(self, value):
        if value is None:
            self.ui.awb_manual_radio.setChecked(False)
            self.ui.awb_auto_radio.setChecked(False)
        elif value == 'off':
            self.ui.awb_manual_radio.setChecked(True)
        else:
            self.ui.awb_auto_radio.setChecked(True)
            self.ui.awb_combo.setCurrentIndex(self.ui.awb_combo.model().find(value))
    awb_mode = property(_get_awb_mode, _set_awb_mode)

    def _get_awb_red(self):
        return self.ui.awb_red_spinbox.value()
    def _set_awb_red(self, value):
        if value is None:
            value = 1.0
        self.ui.awb_red_spinbox.setValue(value)
    awb_red = property(_get_awb_red, _set_awb_red)

    def _get_awb_blue(self):
        return self.ui.awb_blue_spinbox.value()
    def _set_awb_blue(self, value):
        if value is None:
            value = 1.0
        self.ui.awb_blue_spinbox.setValue(value)
    awb_blue = property(_get_awb_blue, _set_awb_blue)

    def _get_agc_mode(self):
        if self.ui.agc_auto_radio.isChecked():
            return self.ui.agc_combo.model().get(
                    self.ui.agc_combo.currentIndex())
        elif self.ui.agc_manual_radio.isChecked():
            return 'off'
        else:
            return None
    def _set_agc_mode(self, value):
        if value is None:
            self.ui.agc_auto_radio.setChecked(False)
            self.ui.agc_manual_radio.setChecked(False)
        elif value == 'off':
            self.ui.agc_manual_radio.setChecked(True)
        else:
            self.ui.agc_auto_radio.setChecked(True)
            self.ui.agc_combo.setCurrentIndex(
                    self.ui.agc_combo.model().find(value))
    agc_mode = property(_get_agc_mode, _set_agc_mode)

    def _get_agc_analog(self):
        return self.ui.agc_analog_spinbox.value()
    def _set_agc_analog(self, value):
        if value is None:
            value = 1.0
        self.ui.agc_analog_spinbox.setValue(value)
    agc_analog = property(_get_agc_analog, _set_agc_analog)

    def _get_agc_digital(self):
        return self.ui.agc_digital_spinbox.value()
    def _set_agc_digital(self, value):
        if value is None:
            value = 1.0
        self.ui.agc_digital_spinbox.setValue(value)
    agc_digital = property(_get_agc_digital, _set_agc_digital)

    def _get_exposure_mode(self):
        if self.ui.exposure_auto_radio.isChecked():
            return 'auto'
        elif self.ui.exposure_manual_radio.isChecked():
            return 'off'
        else:
            return None
    def _set_exposure_mode(self, value):
        if value is None:
            self.ui.exposure_auto_radio.setChecked(False)
            self.ui.exposure_manual_radio.setChecked(False)
        elif value == 'off':
            self.ui.exposure_manual_radio.setChecked(True)
        else:
            self.ui.exposure_auto_radio.setChecked(True)
    exposure_mode = property(_get_exposure_mode, _set_exposure_mode)

    def _get_exposure_speed(self):
        return self.ui.exposure_speed_spinbox.value()
    def _set_exposure_speed(self, value):
        if value is None:
            value = 0.0
        self.ui.exposure_speed_spinbox.setValue(value)
    exposure_speed = property(_get_exposure_speed, _set_exposure_speed)

    def _get_ev(self):
        return self.ui.ev_slider.value()
    def _set_ev(self, value):
        if value is None:
            value = 0
        self.ui.ev_slider.setValue(value)
    ev = property(_get_ev, _set_ev)

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
            self.ui.hflip_checkbox.setTristate()
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
            self.ui.vflip_checkbox.setTristate()
            self.ui.vflip_checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
        else:
            self.ui.vflip_checkbox.setChecked(value)
    vflip = property(_get_vflip, _set_vflip)

    def _get_denoise(self):
        return {
            QtCore.Qt.Unchecked: False,
            QtCore.Qt.PartiallyChecked: None,
            QtCore.Qt.Checked: True,
            }[self.ui.denoise_checkbox.checkState()]
    def _set_denoise(self, value):
        if value is None:
            self.ui.denoise_checkbox.setTristate()
            self.ui.denoise_checkbox.setCheckState(QtCore.Qt.PartiallyChecked)
        else:
            self.ui.denoise_checkbox.setChecked(value)
    denoise = property(_get_denoise, _set_denoise)

    def edit_changed(self, text):
        self.update_ok()

    def combo_changed(self, index):
        self.update_ok()

    def checkbox_changed(self, state):
        self.update_ok()

    def agc_radio_changed(self, checked):
        self.ui.agc_combo.setEnabled(self.ui.agc_auto_radio.isChecked())
        #self.ui.agc_analog_spinbox.setEnabled(self.ui.agc_manual_radio.isChecked())
        #self.ui.agc_digital_spinbox.setEnabled(self.ui.agc_manual_radio.isChecked())

    def awb_radio_changed(self, checked):
        self.ui.awb_combo.setEnabled(self.ui.awb_auto_radio.isChecked())
        self.ui.awb_red_spinbox.setEnabled(self.ui.awb_manual_radio.isChecked())
        self.ui.awb_blue_spinbox.setEnabled(self.ui.awb_manual_radio.isChecked())

    def exposure_radio_changed(self, checked):
        self.ui.exposure_speed_spinbox.setEnabled(self.ui.exposure_manual_radio.isChecked())

    def update_ok(self):
        self.ui.button_box.button(QtGui.QDialogButtonBox.Ok).setEnabled(
                bool(
                    self.resolution and
                    self.framerate and
                    self.agc_mode and
                    self.awb_mode and
                    self.exposure_mode and
                    self.metering_mode and
                    self.hflip is not None and
                    self.vflip is not None and
                    self.denoise is not None))

    def button_box_clicked(self, button):
        if self.ui.button_box.standardButton(button) == QtGui.QDialogButtonBox.RestoreDefaults:
            self.resolution = (1280, 720)
            self.framerate = 30
            self.agc_mode = 'auto'
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
            self.denoise = True
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


