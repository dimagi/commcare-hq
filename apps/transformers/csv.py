from __future__ import absolute_import

from datetime import datetime
from django.http import HttpResponse
from django.template.defaultfilters import slugify
from django.db import connection
from rapidsms.webui.utils import UnicodeWriter

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


