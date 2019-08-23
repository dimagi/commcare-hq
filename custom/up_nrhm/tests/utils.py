import json
from django.test.testcases import TestCase
from django.test.client import RequestFactory
from fakecouch import FakeCouchDb
from corehq.apps.users.models import WebUser

from corehq.apps.domain.models import Domain
from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.users.models import CommCareUser
from couchforms.models import XFormInstance
import os
from io import open


class UpNrhmTestCase(TestCase):
    data_source_name = 'asha_facilitators.json'

    @classmethod
    def setUpClass(cls):
        super(UpNrhmTestCase, cls).setUpClass()

        data_source_file = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
            'data_sources',
            cls.data_source_name
        )

        with open(data_source_file, encoding='utf-8') as f:
            cls.data_source = DataSourceConfiguration.wrap(json.loads(f.read())['config'])
            cls.named_expressions = cls.data_source.named_expression_objects
            cls.base_item_expression = cls.data_source.base_item_expression

    def setUp(self):
        self.database = FakeCouchDb()
        self.case_orig_db = CommCareCase.get_db()
        self.form_orig_db = XFormInstance.get_db()
        self.user_orig_db = CommCareUser.get_db()
        CommCareCase.set_db(self.database)
        XFormInstance.set_db(self.database)
        CommCareUser.set_db(self.database)
        self.factory = RequestFactory()
        domain = Domain.get_or_create_with_name('up-nrhm')
        domain.is_active = True
        domain.save()
        self.domain = domain
        user = WebUser.get_by_username('test')
        if not user:
            user = WebUser.create(domain.name, 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True
        self.user = user

    def tearDown(self):
        CommCareCase.set_db(self.case_orig_db)
        XFormInstance.set_db(self.form_orig_db)
        CommCareUser.set_db(self.user_orig_db)
