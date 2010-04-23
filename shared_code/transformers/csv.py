from __future__ import absolute_import

import csv
import codecs
import cStringIO
from datetime import datetime
from django.http import HttpResponse
from django.template.defaultfilters import slugify
from django.db import connection

def get_csv_from_django_query(qs, fields=None):
    model = qs.model
    if fields:
        headers = fields
    else:
        headers = []
        for field in model._meta.fields:
            headers.append(field.name)
    rows = []
    for obj in qs:
        row = []
        for field in headers:
            if field in headers:
                val = getattr(obj, field)
                if callable(val):
                    val = val()
                row.append(val)
        rows.append(row)
    name = slugify(model.__name__)
    return format_csv(rows, headers, name)

def format_csv(rows, columns, name, is_single=False):
    response = HttpResponse(mimetype='text/csv')
    response["content-disposition"] = 'attachment; filename="%s-%s.csv"' % \
        (name, str(datetime.now().date()))
    w = UnicodeWriter(response)
    w.writerow(columns)
    if is_single:
        w.writerow(rows)
    else:
        for row in rows:
            w.writerow(row)
    return response


""" 
The following classes are the optimal prime solution for fixing csv.writer 
to be unicode-compatible ( from http://docs.python.org/library/csv.html )

"""

class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        return self.reader.next().encode("utf-8")

class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)

    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]

    def __iter__(self):
        return self

class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """
    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([unicode(s).encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)
