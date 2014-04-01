"A project for controlling multiple Pi camera modules simultaneously"

import sys

__project__      = 'compoundpi'
__version__      = '0.1'
__keywords__     = ['raspberrypi', 'camera', 'multi']
__author__       = 'Dave Hughes'
__author_email__ = 'dave@waveform.org.uk'
__url__          = 'http://compoundpi.readthedocs.org/'
__platforms__    = 'ALL',

__requires__ = []

__extra_requires__ = {
    'client': [],
    'server': ['picamera'],
    'doc':    ['sphinx'],
    }

if sys.version_info[:2] == (3, 2):
    __extra_requires__['doc'].extend([
        # Particular versions are required for Python 3.2 compatibility.
        # The ordering is reverse because that's what easy_install needs...
        'Jinja<2.7',
        'MarkupSafe<0.16',
        ])

__classifiers__ = [
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Science/Research',
    'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Topic :: Multimedia :: Graphics :: Capture',
    'Topic :: Scientific/Engineering',
    ]

__entry_points__ = {
    'console_scripts': [
        'cpid = compoundpi.server:main',
        'cpi = compoundpi.client:main',
        ],
    }

