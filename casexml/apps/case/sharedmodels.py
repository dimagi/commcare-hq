from couchdbkit.ext.django.schema import *

"""
Shared models live here to avoid cyclical import issues
"""
class CommCareCaseIndex(DocumentSchema):
    """
    In CaseXML v2 we support indices, which link a case to other cases.
    """
    identifier = StringProperty()
    referenced_type = StringProperty()
    referenced_id = StringProperty()
    
    def get_referenced_case(self):
        from casexml.apps.case.models import CommCareCase
        return CommCareCase.get(self.referenced_id)
    
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
                if not CommCareCase.get_db().doc_exist(index_update.referenced_id):
                    raise Exception(("Submitted index against an unknown case id: %s. "
                                     "This is not allowed. Most likely your case "
                                     "database is corrupt and you should restore your "
                                     "phone directly from the server.") % index_update.referenced_id)
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

