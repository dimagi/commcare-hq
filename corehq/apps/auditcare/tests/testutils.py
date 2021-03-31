from django.db import router
from django.test import TestCase
from django.utils.decorators import classproperty

from ..models import AuditEvent


class AuditcareTest(TestCase):

    @classproperty
    def databases(self):
        return {"default", router.db_for_read(AuditEvent)}
