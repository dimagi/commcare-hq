from __future__ import absolute_import
from __future__ import unicode_literals


class CaseRelationshipError(Exception):

    def __init__(self, message, child_case_id, child_case_type, identifier, relationship, num_related_found):
        self.child_case_id = child_case_id
        self.child_case_type = child_case_type
        self.identifier = identifier
        self.relationship = relationship
        self.num_related_found = num_related_found

        super(CaseRelationshipError, self).__init__(message)
