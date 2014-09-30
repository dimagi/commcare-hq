import mimetypes
from couchdbkit.ext.django.schema import StringProperty, IntegerProperty, DictProperty

from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.couch import LooselyEqualDocumentSchema


"""
Shared models live here to avoid cyclical import issues
"""


class CommCareCaseIndex(LooselyEqualDocumentSchema, UnicodeMixIn):
    """
    In CaseXML v2 we support indices, which link a case to other cases.
    """
    identifier = StringProperty()
    referenced_type = StringProperty()
    referenced_id = StringProperty()
    
    @property
    def referenced_case(self):
        if not hasattr(self, "_case"):
            from casexml.apps.case.models import CommCareCase
            self._case = CommCareCase.get(self.referenced_id)
        return self._case
    
    @classmethod
    def from_case_index_update(cls, index):
        return cls(identifier=index.identifier,
                   referenced_type=index.referenced_type,
                   referenced_id=index.referenced_id)

    def __unicode__(self):
        return "%(identifier)s ref: (type: %(ref_type)s, id: %(ref_id)s)" % \
                {"identifier": self.identifier,
                 "ref_type": self.referenced_type,
                 "ref_id": self.referenced_id}
    
    def __cmp__(self, other):
        return cmp(unicode(self), unicode(other))

    def __repr__(self):
        return str(self)


class CommCareCaseAttachment(LooselyEqualDocumentSchema, UnicodeMixIn):
    identifier = StringProperty()
    attachment_src = StringProperty()
    attachment_from = StringProperty()
    attachment_name = StringProperty()
    server_mime = StringProperty()  # Server detected MIME
    server_md5 = StringProperty()  # Couch detected hash

    attachment_size = IntegerProperty()  # file size
    attachment_properties = DictProperty()  # width, height, other relevant metadata

    @property
    def is_image(self):
        if self.server_mime is None:
            return None
        return True if self.server_mime.startswith('image/') else False

    @property
    def is_present(self):
        """
        Helper method to see if this is a delete vs. update
        """
        if self.identifier and (self.attachment_src == self.attachment_from is None):
            return False
        else:
            return True

    @property
    def attachment_key(self):
        return self.identifier

    @classmethod
    def from_case_index_update(cls, attachment):
        if attachment.attachment_src:
            guessed = mimetypes.guess_type(attachment.attachment_src)
            if len(guessed) > 0 and guessed[0] is not None:
                mime_type = guessed[0]
            else:
                mime_type = None

            ret = cls(identifier=attachment.identifier,
                      attachment_src=attachment.attachment_src,
                      attachment_from=attachment.attachment_from,
                      attachment_name=attachment.attachment_name,
                      server_mime=mime_type)
        else:
            ret = cls(identifier=attachment.identifier)
        return ret


class IndexHoldingMixIn(object):
    """
    Since multiple objects need this functionality, implement it as a mixin
    """
    
    def has_index(self, id):
        return id in (i.identifier for i in self.indices)
    
    def get_index(self, id):
        found = filter(lambda i: i.identifier == id, self.indices)
        if found:
            assert(len(found) == 1)
            return found[0]
        return None
    
    def get_index_by_ref_id(self, doc_id):
        found = filter(lambda i: i.referenced_id == doc_id, self.indices)
        if found:
            assert(len(found) == 1)
            return found[0]
        return None

    def update_indices(self, index_update_list):
        for index_update in index_update_list:
            if index_update.referenced_id:
                # NOTE: used to check the existence of the referenced
                # case here but is moved into the pre save processing
                pass
            if self.has_index(index_update.identifier):
                if not index_update.referenced_id:
                    # empty ID = delete
                    self.indices.remove(self.get_index(index_update.identifier))
                else:
                    # update
                    index = self.get_index(index_update.identifier)
                    index.referenced_type = index_update.referenced_type
                    index.referenced_id = index_update.referenced_id
            else:
                # no id, no index
                if index_update.referenced_id:
                    self.indices.append(CommCareCaseIndex(identifier=index_update.identifier,
                                                          referenced_type=index_update.referenced_type,
                                                          referenced_id=index_update.referenced_id))

    def remove_index_by_ref_id(self, doc_id):
        index = self.get_index_by_ref_id(doc_id)
        if not index:
            raise ValueError('index with id %s not found in doc %s' % (id, self._id))
        self.indices.remove(index)
