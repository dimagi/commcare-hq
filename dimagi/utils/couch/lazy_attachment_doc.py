from mimetypes import guess_type
from couchdbkit import ResourceNotFound
from dimagi.ext.couchdbkit import Document
from couchdbkit.resource import encode_attachments
from django.core.cache import cache


class LazyAttachmentDoc(Document):
    """
    Cache in local memory (for this request)
    and in memcached (for the next few requests)
    and commit to couchdb.

    Memcached strategy:
    - on fetch, check in local memory, then memcached
      - if both are a miss, fetch from couchdb and store in both
    - before an attachment is committed to couchdb, clear memcached
      (allowing the next fetch to go all the way through.
      Clear rather than write new value, in case something
      goes wrong with the save.

    """

    def __init__(self, *args, **kwargs):
        super(LazyAttachmentDoc, self).__init__(*args, **kwargs)
        self._LAZY_ATTACHMENTS = {}
        # to cache fetched attachments
        # these we do *not* send back down upon save
        self._LAZY_ATTACHMENTS_CACHE = {}

    @classmethod
    def wrap(cls, data):
        self = super(LazyAttachmentDoc, cls).wrap(data)
        if self._attachments:
            for name, attachment in self._attachments.items():
                if isinstance(attachment, basestring):
                    del self._attachments[name]
                    self.lazy_put_attachment(attachment, name)
        return self

    def __attachment_cache_key(self, name):
        return u'lazy_attachment/{id}/{name}'.format(id=self.get_id, name=name)

    def __set_cached_attachment(self, name, content):
        cache.set(self.__attachment_cache_key(name), content,
                  timeout=60 * 60 * 24)

    def __get_cached_attachment(self, name):
        return cache.get(self.__attachment_cache_key(name))

    def __remove_cached_attachment(self, name):
        cache.delete(self.__attachment_cache_key(name))

    def __store_lazy_attachment(self, content, name=None, content_type=None,
                                content_length=None):
        info = {
            'content': content,
            'content_type': content_type,
            'content_length': content_length,
        }
        self._LAZY_ATTACHMENTS[name] = info
        return info

    def put_attachment(self, content, name=None, content_type=None,
                       content_length=None):
        self.__remove_cached_attachment(name)
        info = self.__store_lazy_attachment(content, name, content_type,
                                            content_length)
        return super(LazyAttachmentDoc, self).put_attachment(name=name, **info)

    def lazy_put_attachment(self, content, name=None, content_type=None,
                            content_length=None):
        """
        Ensure the attachment is available through lazy_fetch_attachment
        and that upon self.save(), the attachments are put to the doc as well

        """
        self.__store_lazy_attachment(content, name, content_type,
                                     content_length)

    def lazy_fetch_attachment(self, name):
        # it has been put/lazy-put already during this request
        if name in self._LAZY_ATTACHMENTS and 'content' in self._LAZY_ATTACHMENTS[name]:
            content = self._LAZY_ATTACHMENTS[name]['content']
        # it has been fetched already during this request
        elif name in self._LAZY_ATTACHMENTS_CACHE:
            content = self._LAZY_ATTACHMENTS_CACHE[name]
        else:
            content = self.__get_cached_attachment(name)

            if not content:
                try:
                    content = self.fetch_attachment(name)
                except ResourceNotFound as e:
                    # django cache will pickle this exception for you
                    # but e.response isn't picklable
                    if hasattr(e, 'response'):
                        del e.response
                    content = e
                    raise
                finally:
                    self.__set_cached_attachment(name, content)
                    self._LAZY_ATTACHMENTS_CACHE[name] = content
            else:
                self._LAZY_ATTACHMENTS_CACHE[name] = content

        if isinstance(content, ResourceNotFound):
            raise content

        return content

    def lazy_list_attachments(self):
        keys = set()
        keys.update(getattr(self, '_LAZY_ATTACHMENTS', None) or {})
        keys.update(getattr(self, '_attachments', None) or {})
        return keys

    def register_pre_save(self, fn):
        if not hasattr(self, '_PRE_SAVE'):
            self._PRE_SAVE = []
        self._PRE_SAVE.append(fn)

    def register_post_save(self, fn):
        if not hasattr(self, '_POST_SAVE'):
            self._POST_SAVE = []
        self._POST_SAVE.append(fn)

    def save(self, **params):
        if hasattr(self, '_PRE_SAVE'):
            for pre_save in self._PRE_SAVE:
                pre_save()

            def del_pre_save():
                del self._PRE_SAVE

            self.register_post_save(del_pre_save)
        _attachments = self._attachments.copy() if self._attachments else {}
        for name, info in self._LAZY_ATTACHMENTS.items():
            self.__remove_cached_attachment(name)
            data = info['content']
            content_type = (info['content_type']
                            or ';'.join(filter(None, guess_type(name))))
            if isinstance(data, unicode):
                data = data.encode('utf8')
            _attachments[name] = {
                'content_type': content_type,
                'data': data,
            }
        self._attachments = encode_attachments(_attachments)
        super(LazyAttachmentDoc, self).save(encode_attachments=False, **params)

        if hasattr(self, '_POST_SAVE'):
            for post_save in self._POST_SAVE:
                post_save()

            del self._POST_SAVE
