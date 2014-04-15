#!/usr/bin/env python
# vim: set et sw=4 sts=4:

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

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
    )

import os
import sys
from setuptools import setup, find_packages

if sys.version_info[0] == 2:
    if not sys.version_info >= (2, 7):
        raise ValueError('This application requires Python 2.7 or above')
elif sys.version_info[0] == 3:
    if not sys.version_info >= (3, 2):
        raise ValueError('This application requires Python 3.2 or above')
else:
    raise ValueError('What version of Python is this?!')

HERE = os.path.abspath(os.path.dirname(__file__))

# Workaround <http://bugs.python.org/issue10945>
import codecs
try:
    codecs.lookup('mbcs')
except LookupError:
    ascii = codecs.lookup('ascii')
    func = lambda name, enc=ascii: {True: enc}.get(name=='mbcs')
    codecs.register(func)

# Workaround <http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html>
try:
    import multiprocessing
except ImportError:
    pass

def main():
    import io
    import compoundpi
    with io.open(os.path.join(HERE, 'README.rst'), 'r') as readme:
        setup(
            name                 = compoundpi.__project__,
            version              = compoundpi.__version__,
            description          = compoundpi.__doc__,
            long_description     = readme.read(),
            classifiers          = compoundpi.__classifiers__,
            author               = compoundpi.__author__,
            author_email         = compoundpi.__author_email__,
            url                  = compoundpi.__url__,
            license              = [
                c.rsplit('::', 1)[1].strip()
                for c in compoundpi.__classifiers__
                if c.startswith('License ::')
                ][0],
            keywords             = compoundpi.__keywords__,
            packages             = find_packages(),
            package_data         = {},
            include_package_data = True,
            platforms            = compoundpi.__platforms__,
            install_requires     = compoundpi.__requires__,
            extras_require       = compoundpi.__extra_requires__,
            entry_points         = compoundpi.__entry_points__,
            )


if __name__ == '__main__':
    main()
