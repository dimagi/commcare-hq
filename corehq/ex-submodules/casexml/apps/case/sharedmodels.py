import mimetypes

from corehq.form_processor.abstract_models import IsImageMixin
from dimagi.ext.couchdbkit import StringProperty, IntegerProperty, DictProperty
from dimagi.utils.couch import LooselyEqualDocumentSchema


"""
Shared models live here to avoid cyclical import issues
"""


class CommCareCaseIndex(LooselyEqualDocumentSchema):
    """
    In CaseXML v2 we support indices, which link a case to other cases.
    """
    identifier = StringProperty()
    referenced_type = StringProperty()
    referenced_id = StringProperty()
    # relationship = "child" for index to a parent case (default)
    # relationship = "extension" for index to a host case
    relationship = StringProperty('child', choices=['child', 'extension'])

    @property
    def is_deleted(self):
        return not self.referenced_id

    @property
    def referenced_case(self):
        """
        For a 'forward' index this is the case that the the index points to.
        For a 'reverse' index this is the case that owns the index.
        See ``corehq/couchapps/case_indices/views/related/map.js``

        :return: referenced case
        """
        raise NotImplementedError("the couch case model is obsolete")

    @classmethod
    def from_case_index_update(cls, index):
        return cls(identifier=index.identifier,
                   referenced_type=index.referenced_type,
                   referenced_id=index.referenced_id,
                   relationship=index.relationship,)

    def __str__(self):
        return (
            "CommCareCaseIndex("
            "identifier='{index.identifier}', "
            "referenced_type='{index.referenced_type}', "
            "referenced_id='{index.referenced_id}', "
            "relationship='{index.relationship}'"
            ")"
        ).format(index=self)

    def __lt__(self, other):
        return str(self) < str(other)

    def __repr__(self):
        return str(self)


class CommCareCaseAttachment(LooselyEqualDocumentSchema, IsImageMixin):
    identifier = StringProperty()
    attachment_src = StringProperty()
    attachment_from = StringProperty()
    attachment_name = StringProperty()
    server_mime = StringProperty()  # Server detected MIME
    server_md5 = StringProperty()  # Couch detected hash

    attachment_size = IntegerProperty()  # file size
    attachment_properties = DictProperty()  # width, height, other relevant metadata

    @property
    def content_type(self):
        return self.server_mime

    @property
    def is_present(self):
        """
        Helper method to see if this is a delete vs. update

        NOTE this is related to but reversed logic from
        `casexml.apps.case.xml.parser.CaseAttachment.is_delete`.
        """
        return self.attachment_src or self.attachment_from

    @classmethod
    def from_case_index_update(cls, attachment):
        if attachment.attachment_src or attachment.attachment_from:
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
