from couchdbkit import ResourceNotFound
from django.core.exceptions import ObjectDoesNotExist

from dimagi.utils.mixins import UnicodeMixIn


class CaseNotFound(ResourceNotFound, ObjectDoesNotExist):
    pass


class XFormNotFound(ResourceNotFound, ObjectDoesNotExist):
    pass


class InvalidAttachment(Exception):
    pass


class AttachmentNotFound(ResourceNotFound, ObjectDoesNotExist, UnicodeMixIn):
    def __init__(self, attachment_name):
        self.attachment_name = attachment_name

    def __unicode__(self):
        return "Attachment '{}' not found".format(self.attachment_name)


class CaseSaveError(Exception):
    pass


class AccessRestricted(Exception):
    pass
