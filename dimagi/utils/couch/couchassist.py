import os
import tempfile
import time
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

def load(path=None, convert=True):
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
        db = convert_data(db)

    end = time.time()

    print 'data loaded: %d docs, %.2fs' % (len(db), end - start)

def convert_data(e):
    """recursively convert parsed json into easy wrappers"""
    if isinstance(e, type({})):
        for k in e.keys():
            e[k] = convert(e[k])
        return EasyDict(e)
    elif hasattr(e, '__iter__'):
        return [convert(c) for c in e]
    else:
        return e

class EasyDict(object):
    """helper object to work with json dicts more intuitively.
    given source dict 'd' and EasyDict e:
    e = EasyDict(d)
    e.x == d['x']
    e('#x') == d['#x']
    e._ == d
    e('_') == d['_']
    """

    def __init__(self, _dict):
        self.__dict__ = _dict

    def __call__(self, key):
        if key == '_':
            return self.__dict__[key]
        else:
            return self.__getattribute__(key)

    def __getattribute__(self, key):
        if key == '_':
            return self.__dict__
        else:
            return super(EasyDict, self).__getattribute__(key)

    def __repr__(self):
        return repr(self._)
