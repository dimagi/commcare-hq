from django.db import router
from django.test import TestCase
from django.utils.decorators import classproperty

from ..models import AccessAudit, AuditEvent, NavigationEventAudit


class AuditcareTest(TestCase):

    @classproperty
    def databases(self):
        return {"default", router.db_for_read(AuditEvent)}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        AccessAudit.http_accept.get_related.cache_clear()
        AccessAudit.user_agent.get_related.cache_clear()
        NavigationEventAudit.user_agent.get_related.cache_clear()
        NavigationEventAudit.view.get_related.cache_clear()

    def tearDown(self):
        AccessAudit.http_accept.get_related.cache_clear()
        AccessAudit.user_agent.get_related.cache_clear()
        NavigationEventAudit.user_agent.get_related.cache_clear()
        NavigationEventAudit.view.get_related.cache_clear()
