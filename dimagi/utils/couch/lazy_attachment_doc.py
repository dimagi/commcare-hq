from mimetypes import guess_type
from couchdbkit.ext.django.schema import Document
from couchdbkit.resource import encode_attachments


class LazyAttachmentDoc(Document):

    def __init__(self, *args, **kwargs):
        super(LazyAttachmentDoc, self).__init__(*args, **kwargs)
        self._LAZY_ATTACHMENTS = {}

    @classmethod
    def wrap(cls, data):
        self = super(LazyAttachmentDoc, cls).wrap(data)
        if self._attachments:
            for name, attachment in self._attachments.items():
                if isinstance(attachment, basestring):
                    del self._attachments[name]
                    self.lazy_put_attachment(attachment, name)
        return self

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
        info = self.__store_lazy_attachment(content, name, content_type,
                                            content_length)
        return super(LazyAttachmentDoc, self).put_attachment(name=name, **info)

    def lazy_put_attachment(self, content, name=None, content_type=None,
                            content_length=None):
        """
        Ensure the attachment is available through lazy_fetch_attachment
        and that upon self.save(), the attachments are put to the doc as well

        """
        info = self.__store_lazy_attachment(content, name, content_type,
                                            content_length)

        # def put_attachment():
        #     self.put_attachment(name=name, **info)
        #
        # self.register_post_save(put_attachment)

    def lazy_fetch_attachment(self, name):
        try:
            info = self._LAZY_ATTACHMENTS[name]
            return info['content']
        except KeyError:
            return self.fetch_attachment(name)

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
