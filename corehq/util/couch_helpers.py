import base64
from copy import copy
import hashlib
from mimetypes import guess_type
import datetime
import threading


class CouchAttachmentsBuilder(object):
    """
    Helper for saving attachments on doc save rather than as a separate step.
    Example usage:

    Instead of the normal 1 + N request save where N is the # of attachments:

        foo = Foo()
        foo.save()
        foo.put_attachment(
            name=filename,
            content=content,
            content_type=mime_type
        )

    You can use the following to do a single-request save:

        foo = Foo()

        attachment_builder = CouchAttachmentsBuilder(foo._attachments)
        attachment_builder.add(
            name=filename,
            content=content,
            content_type=mime_type
        )
        foo._attachments = attachment_builder.to_json()

        foo.save(encode_attachments=False)


        # or bulk save
        Foo.get_db().bulk_save([foo, ...])

    NB: If you save without encode_attachments=False
    (here or later on down the line)
    then your attachment content will end up base64 encoded!
    That's a real thing that's happened in the past,
    so be careful who you're passing this object on to!
    (Think signals, etc. where you have no control over who uses it next
    and how/whether they call .save() on the object.)

    """
    def __init__(self, original=None):
        self._dict = original or {}

    @staticmethod
    def couch_style_digest(data):
        return 'md5-{}'.format(base64.b64encode(hashlib.md5(data).digest()))

    def no_change(self, name, data):
        return (
            self._dict.get(name) and
            self._dict[name].get('digest') == self.couch_style_digest(data)
        )

    def add(self, content, name=None, content_type=None):
        if hasattr(content, 'read'):
            if hasattr(content, 'seek'):
                content.seek(0)
            data = content.read()
        else:
            data = content
        if isinstance(data, unicode):
            data = data.encode('utf-8')
        if content_type is None:
            content_type = ';'.join(filter(None, guess_type(name)))
        # optimization alert:
        # don't make couch re-save attachment if there's no change in content
        if self.no_change(name, data):
            # just set the content_type in case it's different
            # don't know of any case where this matters
            # but seems semantically correct
            self._dict[name].update({
                'content_type': content_type,
            })
        else:
            self._dict[name] = {
                'data': base64.b64encode(data),
                'content_type': content_type,
            }

    def remove(self, name):
        """
        raises a `KeyError` if there's no attachment called `name`
        """
        del self._dict[name]

    def to_json(self):
        return copy(self._dict)


class PaginateViewLogHandler(object):

    def log(self, message):
        # subclasses can override this to actually log something
        # built in implementation swallows it
        pass

    def view_starting(self, db, view_name, kwargs, total_emitted):
        self.log(u'Fetching rows {}-{} from couch'.format(
            total_emitted,
            total_emitted + kwargs['limit'] - 1)
        )
        startkey = kwargs.get('startkey')
        self.log(u'  startkey={!r}, startkey_docid={!r}'.format(startkey, kwargs.get('startkey_docid')))

    def view_ending(self, db, view_name, kwargs, total_emitted, time):
        self.log('View call took {}'.format(time))


def paginate_view(db, view_name, chunk_size,
                  log_handler=PaginateViewLogHandler(), **view_kwargs):
    """
    intended as a more performant drop-in replacement for

        iter(db.view(view_name, **kwargs))

    intended specifically to be more performant when dealing with
    large numbers of rows

    Note: If the contents of the couch view do not change over the duration of
    the paginate_view call, this is guaranteed to have the same results
    as a direct view call. If the view is updated, however,
    paginate_views may skip docs that were added/updated during this period
    or may include docs that were removed/updated during this period.
    For this reason, it's best to use this with views that update infrequently
    or that are sorted by date modified and/or add-only,
    or when exactness is not a strict requirement

    chunk_size is how many docs to fetch per request to couchdb

    """
    if view_kwargs.get('reduce', True):
        raise ValueError('paginate_view must be called with reduce=False')

    if 'limit' in view_kwargs:
        raise ValueError('paginate_view cannot be called with limit')

    if 'skip' in view_kwargs:
        raise ValueError('paginate_view cannot be called with skip')

    view_kwargs['limit'] = chunk_size
    total_emitted = 0
    len_results = -1
    while len_results:
        log_handler.view_starting(db, view_name, view_kwargs, total_emitted)
        start_time = datetime.datetime.utcnow()
        results = db.view(view_name, **view_kwargs)
        len_results = len(results)

        for result in results:
            yield result

        total_emitted += len_results
        log_handler.view_ending(db, view_name, view_kwargs, total_emitted,
                                datetime.datetime.utcnow() - start_time)
        if len_results:
            view_kwargs['startkey'] = result['key']
            view_kwargs['startkey_docid'] = result['id']
            view_kwargs['skip'] = 1


_override_db = threading.local()


class OverrideDB(object):
    def __init__(self, document_class, database):
        self.document_class = document_class
        self.database = database
        self.orig_database = None
        self.orig_get_db = None
        if not hasattr(_override_db, 'class_to_db'):
            _override_db.class_to_db = {}

    def __enter__(self):
        try:
            self.orig_database = _override_db.class_to_db[self.document_class]
        except KeyError:
            self.orig_get_db = self.document_class.get_db
            self.document_class.get_db = classmethod(_get_db)
        _override_db.class_to_db[self.document_class] = self.database

    def __exit__(self, exc_type, exc_val, exc_tb):
        # explict comparison with None necessary
        # because Database.__nonzero__ returns the doc count
        if self.orig_database is not None:
            _override_db.class_to_db[self.document_class] = self.orig_database
        else:
            assert self.orig_get_db
            del _override_db.class_to_db[self.document_class]
            self.document_class.get_db = self.orig_get_db


def _get_db(cls):
    return _override_db.class_to_db[cls]
