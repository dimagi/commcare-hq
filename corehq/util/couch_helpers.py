import base64
from copy import copy
from mimetypes import guess_type


class CouchAttachmentsBuilder(object):
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
