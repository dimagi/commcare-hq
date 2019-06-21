from __future__ import absolute_import
from __future__ import unicode_literals

import six
from couchdbkit import ResourceNotFound
from django.core.exceptions import ObjectDoesNotExist


class CaseNotFound(ResourceNotFound, ObjectDoesNotExist):
    pass


class XFormNotFound(ResourceNotFound, ObjectDoesNotExist):
    pass


class XFormQuestionValueNotFound(Exception):
    pass


class LedgerValueNotFound(Exception):
    pass


@six.python_2_unicode_compatible
class AttachmentNotFound(ResourceNotFound, ObjectDoesNotExist):

    def __init__(self, attachment_name):
        self.attachment_name = attachment_name

    def __str__(self):
        return "Attachment '{}' not found".format(self.attachment_name)


class CouchSaveAborted(Exception):
    pass


class CaseSaveError(Exception):
    pass


class XFormSaveError(Exception):
    pass


class LedgerSaveError(Exception):
    pass


class InvalidAttachment(Exception):
    pass


class UnknownActionType(Exception):
    """Thrown when an unknown action type is set on a CaseTransaction"""


class PostSaveError(Exception):
    pass


class KafkaPublishingError(Exception):
    pass


class XFormLockError(Exception):
    """Exception raised when a form lock cannot be acquired

    The error message should identify the locked form.
    """
