import base64
from copy import copy
from mimetypes import guess_type
import datetime


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
    def view_starting(self, db, view_name, kwargs, total_emitted):
        pass

    def view_ending(self, db, view_name, kwargs, total_emitted, time):
        pass


def paginate_view(db, view_name, chunk_size,
                  log_handler=PaginateViewLogHandler(), **kwargs):
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
    if kwargs.get('reduce', True):
        raise ValueError('paginate_view must be called with reduce=False')

    if 'limit' in kwargs:
        raise ValueError('paginate_view cannot be called with limit')

    if 'skip' in kwargs:
        raise ValueError('paginate_view cannot be called with skip')

    kwargs['limit'] = chunk_size
    total_emitted = 0
    len_results = -1
    while len_results:
        log_handler.view_starting(db, view_name, kwargs, total_emitted)
        start_time = datetime.datetime.utcnow()
        results = db.view(view_name, **kwargs)
        len_results = len(results)

        for result in results:
            yield result

        total_emitted += len_results
        log_handler.view_ending(db, view_name, kwargs, total_emitted,
                                datetime.datetime.utcnow() - start_time)
        if len_results:
            kwargs['startkey'] = result['key']
            kwargs['startkey_docid'] = result['id']
            kwargs['skip'] = 1
