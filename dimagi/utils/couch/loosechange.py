import os
import tempfile
import time
import re
from datetime import datetime, timedelta, tzinfo
try:
    import simplejson as json
except ImportError:
    import json

# this is a utility toolkit to perform data analysis on couchdb. couchdb temp views are
# excruciatingly slow. this toolkit dumps the entire db into memory in python, where
# you can process it quickly as you wish.

dumpfile = None
db = None

def get_couch_url(db, server, user, passwd):
    if len(server.split(':')) == 1:
        server += ':5984'

    cred = '%s:%s@' % (user, passwd) if user and passwd else ''
    return 'http://%s%s/%s/_all_docs?include_docs=true' % (cred, server, db)

def temp_filename():
    (fd, path) = tempfile.mkstemp()
    f = os.fdopen(fd)
    f.close()
    return path

def dumpdb(db, server='localhost', user=None, passwd=None):
    """call this to extract the database into a temp file. 'dumpfile' will be
    set to the temp file path"""
    global dumpfile
    dumpfile = temp_filename()

    url = get_couch_url(db, server, user, passwd)
    fetch_cmd = 'wget -O %s --progress=dot:mega %s 1>&2' % (dumpfile, url)
    os.popen(fetch_cmd)

def load(path=None, convert=True, convert_args={'dates': True}):
    """parse the dump file and load the data into memory. 'db' will be set to
    the loaded data"""
    global db

    if not path:
        path = dumpfile
    if not path:
        raise ValueError('no path to db dumpfile!')

    start = time.time()

    raw = json.load(open(path))
    db = [row['doc'] for row in raw['rows']]
    if convert:
        db = convert_data(db, **convert_args)

    end = time.time()

    print 'data loaded: %d docs, %.2fs' % (len(db), end - start)

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

    if data == None:
        data = db

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
    return dict((k, reducefunc(v)) for k, v in mapped.iteritems())

def convert_data(e, **kw):
    """recursively convert parsed json into easy wrappers"""
    if isinstance(e, type({})):
        for k in e.keys():
            e[k] = convert_data(e[k], **kw)
        return AssocArray(e)
    elif hasattr(e, '__iter__'):
        return [convert_data(c, **kw) for c in e]
    else:
        if kw.get('dates'):
            try:
                e = parse_date(e)
            except (ValueError, TypeError):
                pass

        return e

class AssocArray(object):
    """helper object to work with json dicts more intuitively, and make them behave
    more like javascript objects.

    given source dict 'd':
    e = AssocArray(d)
    e.a == e('a') == e['a'] == e.__('a') == d.get('a') (None if 'a' not in d)
    e('@xmlns') == d.get('@xmlns') (e.@xmlns is syntax error)
    e._ == d
    e.__('a', '--') == d.get('a', '--') ('--' if 'a' not in d)
    e.__('a', ex=1) == d['a'] (AttributeError if 'a' not in d)
    e['a', 'b', 'c'] == e.a.b.c, None if e.a through e.a.b.c don't exist, or if e.a, e.a.b aren't AssocArrays
    e('a.b.c') == e['a', 'b', 'c']
    e('_') == d.get('_'), e('__') == d.get('__')
    """
    def __init__(self, _dict):
        self.__dict__ = _dict

    def __call__(self, key):
        return self[key.split('.')]

    def __getattribute__(self, key):
        if key == '_':
            return self.__dict__
        elif key == '__':
            return lambda field, fallback=None, ex=False: aa_get(self, field, fallback, ex)
        else:
            return self.__(key)

    def __getitem__(self, key):
        return aa_chain(self, to_it(key))

    def __repr__(self):
        return repr(self._)

def aa_get(aa, key, fallback, throw_ex):
    try:
        return super(AssocArray, aa).__getattribute__(key)
    except AttributeError:
        if throw_ex:
            raise
        else:
            return fallback

def aa_chain(o, keys):
    if keys:
        try:
            child = o.__(keys[0])
        except (AttributeError, TypeError):
            #handle if o is not an AssocArray
            child = None
        return aa_chain(child, keys[1:]) if child is not None else None
    else:
        return o

def parse_date(s):
    for pattern, parsefunc in DATE_REGEXP:
        match = pattern.match(s)
        if match:
            return parsefunc(**match.groupdict())
    raise ValueError('did not match any date pattern')

def parse_iso_date(p):
    return datetime.strptime(p, '%Y-%m-%d').date()

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
    (re.compile('(?P<p>\d{4}-\d{2}-\d{2})$'), parse_iso_date),
    (re.compile('(?P<p>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?P<frac>\.\d+)?(?P<tz>Z|[+-]\d{2,4})?$'), parse_iso_timestamp),
    (re.compile('\w{3} (?P<p>\w{3} \d{2} \d{4} \d{2}:\d{2}:\d{2}) (GMT|UTC)?(?P<tz>[+-]\d{4})'), parse_js_timestamp),
]

#do i really have to define this myself???
class TZ(tzinfo):
    def __init__(self, tz):
        if isinstance(tz, int):
            self.offset = tz
            self.name = '%s%02d%02d' % ('+' if tz >= 0 else '-', abs(tz) / 60, abs(tz) % 60)
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

def tx(val, translatefunc):
    return translatefunc(val) if val is not None else None

def to_it(val):
    return val if hasattr(val, '__iter__') else [val]

def coalesce(*args):
    for arg in args:
        if arg is not None:
            return arg
    return None
