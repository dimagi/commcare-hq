from couchdbkit.ext.django.schema import *
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
        from casexml.apps.case.models import CommCareCase
        if not hasattr(self, "_case"):
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
    
    def update_indices(self, index_update_list):
        from .models import CommCareCase
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

