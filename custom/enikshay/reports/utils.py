from __future__ import absolute_import
from collections import namedtuple

from sqlagg.filters import RawFilter

StubReport = namedtuple('Report', 'domain')


def convert_to_raw_filters_list(*filters):
    return [RawFilter(x) for x in filters]
