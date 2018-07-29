from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple

from sqlagg.filters import RawFilter

StubReport = namedtuple('Report', 'domain')


def convert_to_raw_filters_list(*filters):
    return [RawFilter(x) for x in filters]
