#!/usr/bin/env python

# Copyright (c) 2011, Dirk Thomas, Dorian Scholz, TU Darmstadt
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above
#     copyright notice, this list of conditions and the following
#     disclaimer in the documentation and/or other materials provided
#     with the distribution.
#   * Neither the name of the TU Darmstadt nor the names of its
#     contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

import os
import sys
import importlib


QT_BINDING = None
QT_BINDING_MODULES = {}
QT_BINDING_VERSION = None


def _select_qt_binding(binding_name=None, binding_order=None):
    global QT_BINDING, QT_BINDING_VERSION

    # order of default bindings can be changed here
    DEFAULT_BINDING_ORDER = ['pyqt', 'pyside']
    binding_order = binding_order or DEFAULT_BINDING_ORDER

    # determine binding preference
    if binding_name:
        if binding_name not in binding_order:
            raise ImportError("Qt binding '%s' is unknown" % binding_name)
        binding_order = [binding_name]

    required_modules = [
        'QtCore',
        'QtGui'
    ]
    optional_modules = [
        'QtDeclarative',
        'QtMultimedia',
        'QtNetwork',
        'QtOpenGL',
        'QtOpenVG',
        'QtScript',
        'QtScriptTools'
        'QtSql',
        'QtSvg',
        'QtWebKit',
        'QtXml',
        'QtXmlPatterns',
    ]

    # try to load preferred bindings
    error_msgs = []
    for binding_name in binding_order:
        try:
            binding_loader = globals().get('_load_%s' % binding_name, None)
            if binding_loader:
                QT_BINDING_VERSION = binding_loader(
                        required_modules, optional_modules)
                QT_BINDING = binding_name
                break
            else:
                error_msgs.append(
                        "  Binding loader '_load_%s' not found." % binding_name)
        except ImportError as e:
            error_msgs.append(
                    "  ImportError for '%s': %s" % (binding_name, e))

    if not QT_BINDING:
        raise ImportError(
                "Could not find Qt binding (looked for: %s):\n%s" % (
                    ', '.join(["'%s'" % b for b in binding_order]),
                    '\n'.join(error_msgs))
                )


def _register_binding_module(module_name, module):
    QT_BINDING_MODULES[module_name] = module


def _named_import(name):
    parts = name.split('.')
    assert(len(parts) >= 2)
    module = importlib.import_module(name)
    module_name = parts[-1]
    _register_binding_module(module_name, module)


def _named_optional_import(name):
    try:
        _named_import(name)
    except ImportError:
        pass


def _load_pyqt(required_modules, optional_modules):
    os.environ['QT_API'] = 'pyqt'

    # select PyQt4 API, see
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    import sip
    try:
        sip.setapi('QDate', 2)
        sip.setapi('QDateTime', 2)
        sip.setapi('QString', 2)
        sip.setapi('QTextStream', 2)
        sip.setapi('QTime', 2)
        sip.setapi('QUrl', 2)
        sip.setapi('QVariant', 2)
    except ValueError as e:
        raise RuntimeError(
                'Could not set API version (%s): did you import PyQt4 '
                'directly?' % e)

    for module_name in required_modules:
        _named_import('PyQt4.%s' % module_name)
    for module_name in optional_modules:
        _named_optional_import('PyQt4.%s' % module_name)

    # set some names for compatibility with PySide
    sys.modules['PyQt4.QtCore'].Signal   = sys.modules['PyQt4.QtCore'].pyqtSignal
    sys.modules['PyQt4.QtCore'].Slot     = sys.modules['PyQt4.QtCore'].pyqtSlot
    sys.modules['PyQt4.QtCore'].Property = sys.modules['PyQt4.QtCore'].pyqtProperty

    try:
        import PyQt4.Qwt5
        _register_binding_module('Qwt', PyQt4.Qwt5)
    except ImportError:
        pass

    global _loadUi

    def _loadUi(uifile, baseinstance=None, custom_widgets_=None):
        from PyQt4 import uic
        return uic.loadUi(uifile, baseinstance=baseinstance)

    # override specific function to improve compatibility between different
    # bindings
    from PyQt4.QtGui import QFileDialog
    QFileDialog.getOpenFileName = QFileDialog.getOpenFileNameAndFilter
    QFileDialog.getSaveFileName = QFileDialog.getSaveFileNameAndFilter

    import PyQt4.QtCore
    return PyQt4.QtCore.PYQT_VERSION_STR


def _load_pyside(required_modules, optional_modules):
    os.environ['QT_API'] = 'pyside'

    for module_name in required_modules:
        _named_import('PySide.%s' % module_name)
    for module_name in optional_modules:
        _named_optional_import('PySide.%s' % module_name)

    # set some names for compatibility with PyQt4
    sys.modules['PySide.QtCore'].pyqtSignal   = sys.modules['PySide.QtCore'].Signal
    sys.modules['PySide.QtCore'].pyqtSlot     = sys.modules['PySide.QtCore'].Slot
    sys.modules['PySide.QtCore'].pyqtProperty = sys.modules['PySide.QtCore'].Property

    try:
        import PySideQwt
        _register_binding_module('Qwt', PySideQwt)
    except ImportError:
        pass

    global _loadUi

    def _loadUi(uifile, baseinstance=None, custom_widgets=None):
        from PySide.QtUiTools import QUiLoader
        from PySide.QtCore import QMetaObject
        from PySide.QtGui import QDialog

        class CustomUiLoader(QUiLoader):
            class_aliases = {
                'Line': 'QFrame',
            }

            def __init__(self, baseinstance=None, custom_widgets=None):
                super(CustomUiLoader, self).__init__(baseinstance)
                self._base_instance = baseinstance
                self._custom_widgets = custom_widgets or {}

            def createWidget(self, class_name, parent=None, name=''):
                # don't create the top-level widget, if a base instance is set
                if self._base_instance and not parent:
                    return self._base_instance

                if class_name in self._custom_widgets:
                    widget = self._custom_widgets[class_name](parent)
                else:
                    widget = QUiLoader.createWidget(self, class_name, parent, name)

                if str(type(widget)).find(self.class_aliases.get(class_name, class_name)) < 0:
                    sys.modules['QtCore'].qDebug(
                            str('PySide.loadUi(): could not find widget '
                            'class "%s", defaulting to "%s"' % (
                                class_name, type(widget)))
                            )

                if self._base_instance:
                    setattr(self._base_instance, name, widget)

                return widget

        loader = CustomUiLoader(baseinstance)
        custom_widgets = custom_widgets or {}
        for custom_widget in custom_widgets.values():
            loader.registerCustomWidget(custom_widget)

        ui = loader.load(uifile)
        QMetaObject.connectSlotsByName(ui)
        # Workaround: PySide doesn't automatically center dialogs on their
        # parent windows
        if isinstance(baseinstance, QDialog) and (baseinstance.parentWidget() is not None):
            r = baseinstance.frameGeometry()
            r.moveCenter(baseinstance.parentWidget().frameGeometry().center())
            baseinstance.move(r.topLeft())
        return ui

    import PySide
    return PySide.__version__


def loadUi(uifile, baseinstance=None, custom_widgets=None):
    """
    @type uifile: str
    @param uifile: Absolute path of .ui file
    @type baseinstance: QWidget
    @param baseinstance: the optional instance of the Qt base class.
                         If specified then the user interface is created in
                         it. Otherwise a new instance of the base class is
                         automatically created.
    @type custom_widgets: dict of {str:QWidget}
    @param custom_widgets: Class name and type of the custom classes used
                           in uifile if any. This can be None if no custom
                           class is in use. (Note: this is only necessary
                           for PySide, see
                           http://answers.ros.org/question/56382/what-does-python_qt_bindingloaduis-3rd-arg-do-in-pyqt-binding/
                           for more information)
    """
    return _loadUi(uifile, baseinstance, custom_widgets)


_select_qt_binding(
    getattr(sys, 'SELECT_QT_BINDING', None),
    getattr(sys, 'SELECT_QT_BINDING_ORDER', None),
)
