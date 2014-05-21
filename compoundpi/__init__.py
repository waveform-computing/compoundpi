# vim: set et sw=4 sts=4 fileencoding=utf-8:
#
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

"A project for controlling multiple Pi camera modules simultaneously"

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

import sys

__project__      = 'compoundpi'
__version__      = '0.3'
__keywords__     = ['raspberrypi', 'camera', 'multi']
__author__       = 'Dave Hughes'
__author_email__ = 'dave@waveform.org.uk'
__url__          = 'http://compoundpi.readthedocs.org/'
__platforms__    = 'ALL'

__requires__ = []

__extra_requires__ = {
    'client': ['netifaces', 'pyqt'],
    'server': ['picamera', 'rpi.gpio', 'python-daemon'],
    'doc':    ['sphinx'],
    }

if sys.version_info[:2] < (3, 3):
    # Python 3.3+ has an equivalent ipaddress module built-in
    __requires__.append('ipaddr')
if sys.version_info[:2] == (3, 2):
    __extra_requires__['doc'].extend([
        # Particular versions are required for Python 3.2 compatibility.
        # The ordering is reverse because that's what easy_install needs...
        'Jinja<2.7',
        'MarkupSafe<0.16',
        ])

__classifiers__ = [
    'Development Status :: 4 - Beta',
    'Environment :: Console',
    'Intended Audience :: Science/Research',
    'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Programming Language :: Python :: 2.7',
    'Topic :: Multimedia :: Graphics :: Capture',
    'Topic :: Scientific/Engineering',
    ]

__entry_points__ = {
    'console_scripts': [
        'cpid = compoundpi.server:main',
        'cpi = compoundpi.cli:main',
        ],
    'gui_scripts': [
        'cpigui = compoundpi.gui:main',
        ],
    }

