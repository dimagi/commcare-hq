# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
import re

import six
from dateutil import parser as dateutil_parser


def to_timestamp(value):
    """
    OpenMRS accepts strings in the same format for both dates and datetimes.

    >>> to_timestamp('2017-06-27') == '2017-06-27T00:00:00.000+0000'
    True

    """
    if isinstance(value, six.string_types):
        if not re.match('\d{4}-\d{2}-\d{2}', value):
            raise ValueError('"{}" is not recognised as a date or a datetime'.format(value))
        value = dateutil_parser.parse(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        micros = value.strftime('%f')[:3]  # Only 3 digits for OpenMRS
        tz = value.strftime('%z') or '+0000'  # If we don't know, lie
        return value.strftime('%Y-%m-%dT%H:%M:%S.{f}{z}'.format(f=micros, z=tz))


def to_name(value):
    """
    OpenMRS does not accept names that have numbers in them

    >>> to_name('5dbbabc66c12730b') == '-dbbabc--c-----b'
    True

    """
    # Replace non-alphanumeric, digits and underscores with "-", but allow spaces and apostrophes
    def usually_hyphen(match):
        m = match.group()
        return m if m in (' ', "'", "ʼ") else '-'

    nonalpha = re.compile(r'[\W\d_]', re.UNICODE)
    return nonalpha.sub(usually_hyphen, value)
