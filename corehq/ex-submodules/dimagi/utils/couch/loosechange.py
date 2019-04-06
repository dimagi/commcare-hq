from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import re
from datetime import datetime, timedelta, tzinfo
from dimagi.utils.parsing import ISO_DATE_FORMAT


def map_reduce(emitfunc=lambda rec: [(None,)], reducefunc=lambda v: v, data=None, include_docs=False):
    """perform a "map-reduce" on the data

    emitfunc(rec): return an iterable of key-value pairings as (key, value). alternatively, may
        simply emit (key,) (useful for include_docs=True or reducefunc=len)
    reducefunc(values): applied to each list of values with the same key; defaults to just
        returning the list
    data: list of records to operate on. defaults to data loaded from load()
    include_docs: if True, each emitted value v will be implicitly converted to (v, doc) (if
        only key is emitted, v == doc)
    """

    mapped = {}
    for rec in data:
        for emission in emitfunc(rec):
            try:
                k, v = emission
                if include_docs:
                    v = (v, rec)
            except ValueError:
                k, v = emission[0], rec if include_docs else None
            if k not in mapped:
                mapped[k] = []
            mapped[k].append(v)
    return dict((k, reducefunc(v)) for k, v in mapped.items())


def parse_date(s):
    for pattern, parsefunc in DATE_REGEXP:
        match = pattern.match(s)
        if match:
            return parsefunc(**match.groupdict())
    raise ValueError('did not match any date pattern')


def parse_iso_date(p):
    return datetime.strptime(p, ISO_DATE_FORMAT).date()


def parse_iso_timestamp(p, frac, tz):
    return parse_full_timestamp('%Y-%m-%dT%H:%M:%S', p, frac, tz)


def parse_js_timestamp(p, tz):
    return parse_full_timestamp('%b %d %Y %H:%M:%S', p, None, tz)


def parse_full_timestamp(pattern, p, frac, tz):
    stamp = datetime.strptime(p, pattern)
    if frac:
        stamp += timedelta(seconds=float(frac))
    if tz:
        try:
            stamp = stamp.replace(tzinfo=TZ(tz))
        except ValueError:
            pass
    return stamp


DATE_REGEXP = [
    (re.compile(r'(?P<p>\d{4}-\d{2}-\d{2})$'), parse_iso_date),
    (re.compile(r'(?P<p>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?P<frac>\.\d+)?(?P<tz>Z|[+-]\d{2,4})?$'), parse_iso_timestamp),
    (re.compile(r'\w{3} (?P<p>\w{3} \d{2} \d{4} \d{2}:\d{2}:\d{2}) (GMT|UTC)?(?P<tz>[+-]\d{4})'), parse_js_timestamp),
]


#do i really have to define this myself???
class TZ(tzinfo):
    def __init__(self, tz):
        if isinstance(tz, int):
            self.offset = tz
            self.name = '%s%02d%02d' % ('+' if tz >= 0 else '-', abs(tz) // 60, abs(tz) % 60)
        else:
            if tz in ('Z', 'UTC'):
                tz = '+0000'

            self.name = tz
            try:
                sign = {'+': 1, '-': -1}[tz[0]]
                h = int(tz[1:3])
                m = int(tz[3:5]) if len(tz) == 5 else 0
            except:
                raise ValueError('invalid tz spec')
            self.offset = sign * (60 * h + m)

    def utcoffset(self, dt):
        return timedelta(minutes=self.offset)

    def tzname(self, dt):
        return self.name

    def dst(self, dt):
        return timedelta()

    def __getinitargs__(self):
        return (self.offset,)

    def __repr__(self):
        return self.name
