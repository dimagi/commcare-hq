# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
import re

import six
from dateutil import parser as dateutil_parser

from corehq.motech.const import COMMCARE_DATA_TYPE_DATE, COMMCARE_DATA_TYPE_TEXT
from corehq.motech.openmrs.const import OPENMRS_DATA_TYPE_DATETIME, OPENMRS_DATA_TYPE_BOOLEAN
from corehq.motech.serializers import serializers


def to_omrs_datetime(value):
    """
    Converts CommCare dates and datetimes to OpenMRS datetimes.

    >>> to_omrs_datetime('2017-06-27') == '2017-06-27T00:00:00.000+0000'
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


def omrs_datetime_to_date(value):
    """
    Converts an OpenMRS datetime to a CommCare date

    >>> omrs_datetime_to_date('2017-06-27T00:00:00.000+0000') == '2017-06-27'
    True

    """
    if value and 'T' in value:
        return value.split('T')[0]
    return value


def omrs_boolean_to_text(value):
    return 'true' if value else 'false'


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


serializers.update({
    # (from_data_type, to_data_type): function
    (None, OPENMRS_DATA_TYPE_DATETIME): to_omrs_datetime,
    (OPENMRS_DATA_TYPE_DATETIME, COMMCARE_DATA_TYPE_DATE): omrs_datetime_to_date,
    (OPENMRS_DATA_TYPE_BOOLEAN, COMMCARE_DATA_TYPE_TEXT): omrs_boolean_to_text,
})
