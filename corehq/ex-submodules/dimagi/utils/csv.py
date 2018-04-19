""" 
extend csv.writer and csv.reader to support Unicode
from http://docs.python.org/library/csv.html
"""
from __future__ import absolute_import

from __future__ import unicode_literals
import csv
import codecs
import six


class UTF8Recoder(object):
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """

    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.reader).encode("utf-8")

    next = __next__  # For Py2 compatibility


class UnicodeReader(object):
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)

    def __next__(self):
        row = next(self.reader)
        return [six.text_type(s, "utf-8") for s in row]

    next = __next__  # For Py2 compatibility

    def __iter__(self):
        return self


class UnicodeWriter(object):
    """
    A CSV writer which will write rows to CSV file "f" using utf-8.
    """
    def __init__(self, f, dialect=csv.excel, **kwds):
        # Redirect output to a queue
        self.writer = csv.writer(f, dialect=dialect, **kwds)

    def writerow(self, row):
        self.writer.writerow([six.text_type(s).encode("utf-8") for s in row])

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)
