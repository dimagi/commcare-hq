import uuid

from django.test import TestCase

from casexml.apps.phone.tests.utils import create_restore_user

from corehq.apps.domain.models import Domain


class TestLiveQuery(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLiveQuery, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.project = Domain(name=cls.domain)
        cls.project.save()
        cls.user = create_restore_user(
            cls.domain,
            username=uuid.uuid4().hex,
        )

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestLiveQuery, cls).tearDownClass()
