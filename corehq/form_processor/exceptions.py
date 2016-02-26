from couchdbkit import ResourceNotFound
from django.core.exceptions import ObjectDoesNotExist

from dimagi.utils.mixins import UnicodeMixIn


class CaseNotFound(ResourceNotFound, ObjectDoesNotExist):
    pass


class XFormNotFound(ResourceNotFound, ObjectDoesNotExist):
    pass


class AttachmentNotFound(UnicodeMixIn, ResourceNotFound, ObjectDoesNotExist):
    def __init__(self, attachment_name):
        self.attachment_name = attachment_name

    def __unicode__(self):
        return "Attachment '{}' not found".format(self.attachment_name)


class CaseSaveError(Exception):
    pass


class LedgerSaveError(Exception):
    pass


class AccessRestricted(Exception):
    pass


class InvalidAttachment(Exception):
    pass
