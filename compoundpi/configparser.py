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

"""
Makes Python 2's ConfigParser more like configparser.

This is far from a complete translation, and it's strictly read-only, but it's
enough for my purposes...
"""

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')

# Py3: remove this module entirely

import collections
import ConfigParser as _ConfigParser

BasicInterpolation = object()

ExtendedInterpolation = object()

def ConfigParser(
        defaults=None, dict_type=collections.OrderedDict,
        allow_no_value=False, delimiters=('=', ':'),
        comment_prefixes=('#', ';'), inline_comment_prefixes=None, strict=True,
        empty_lines_in_values=True, default_section='DEFAULT',
        interpolation=BasicInterpolation):
    if not strict:
        raise NotImplementedError
    if not empty_lines_in_values:
        raise NotImplementedError
    if default_section != 'DEFAULT':
        raise NotImplementedError
    if delimiters != ('=', ':'):
        raise NotImplementedError
    if comment_prefixes != ('#', ';'):
        raise NotImplementedError
    if interpolation is None:
        result = _ConfigParser.RawConfigParser(defaults, dict_type, allow_no_value)
    elif interpolation is BasicInterpolation:
        result = _ConfigParser.SafeConfigParser(defaults, dict_type, allow_no_value)
    else:
        raise NotImplementedError
    return result

