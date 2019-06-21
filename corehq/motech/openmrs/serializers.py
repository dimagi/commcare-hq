# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
import re

import six
from dateutil import parser as dateutil_parser

from corehq.motech.const import (
    COMMCARE_DATA_TYPE_DATE,
    COMMCARE_DATA_TYPE_TEXT,
)
from corehq.motech.openmrs.const import (
    OPENMRS_DATA_TYPE_BOOLEAN,
    OPENMRS_DATA_TYPE_DATE,
    OPENMRS_DATA_TYPE_DATETIME,
)
from corehq.motech.serializers import serializers
from corehq.util.python_compatibility import soft_assert_type_text


def to_omrs_date(value):
    """
    Drop the time and timezone to export date-only values

    >>> to_omrs_date('2017-06-27T12:00:00+0530') == '2017-06-27'
    True

    """
    if isinstance(value, six.string_types):
        soft_assert_type_text(value)
        if not re.match(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('"{}" is not recognised as a date or a datetime'.format(value))
        value = dateutil_parser.parse(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime('%Y-%m-%d')


def to_omrs_datetime(value):
    """
    Converts CommCare dates and datetimes to OpenMRS datetimes.

    >>> to_omrs_datetime('2017-06-27') == '2017-06-27T00:00:00.000+0000'
    True

    """
    if isinstance(value, six.string_types):
        soft_assert_type_text(value)
        if not re.match(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('"{}" is not recognised as a date or a datetime'.format(value))
        value = dateutil_parser.parse(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        micros = value.strftime('%f')[:3]  # Only 3 digits for OpenMRS
        tz = value.strftime('%z') or '+0000'  # If we don't know, lie
        return value.strftime('%Y-%m-%dT%H:%M:%S.{f}{z}'.format(f=micros, z=tz))


def to_omrs_boolean(value):
    if (
        isinstance(value, six.string_types)
        and value.lower() in ('false', '0')
    ):
        return False
    return bool(value)


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


serializers.update({
    # (from_data_type, to_data_type): function
    (None, OPENMRS_DATA_TYPE_DATE): to_omrs_date,
    (None, OPENMRS_DATA_TYPE_DATETIME): to_omrs_datetime,
    (None, OPENMRS_DATA_TYPE_BOOLEAN): to_omrs_boolean,
    (OPENMRS_DATA_TYPE_DATETIME, COMMCARE_DATA_TYPE_DATE): omrs_datetime_to_date,
    (OPENMRS_DATA_TYPE_BOOLEAN, COMMCARE_DATA_TYPE_TEXT): omrs_boolean_to_text,
})
