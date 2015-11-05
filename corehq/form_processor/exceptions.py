from couchdbkit import ResourceNotFound
from django.core.exceptions import ObjectDoesNotExist


class CaseNotFound(ResourceNotFound, ObjectDoesNotExist):
    pass


class XFormNotFound(ResourceNotFound, ObjectDoesNotExist):
    pass
