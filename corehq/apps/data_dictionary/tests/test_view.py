import uuid

from django.test import Client, TestCase
from django.urls import reverse

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


@flag_enabled('DATA_DICTIONARY')
class UpdateCasePropertyViewTest(TestCase):
    domain_name = uuid.uuid4().hex

    @classmethod
    def setUpClass(cls):
        super(UpdateCasePropertyViewTest, cls).setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.couch_user = WebUser.create(None, "test", "foobar")
        cls.couch_user.add_domain_membership(cls.domain_name, is_admin=True)
        cls.couch_user.save()
        cls.case_type_obj = CaseType(name='caseType', domain=cls.domain_name)
        cls.case_type_obj.save()
        CaseProperty(case_type=cls.case_type_obj, name='property').save()

    @classmethod
    def tearDownClass(cls):
        cls.case_type_obj.delete()
        cls.couch_user.delete()
        cls.domain.delete()
        super(UpdateCasePropertyViewTest, cls).tearDownClass()

    def setUp(self):
        self.url = reverse('update_case_property', args=[self.domain_name])
        self.client = Client()
        self.client.login(username='test', password='foobar')

    def _get_property(self):
        return CaseProperty.objects.filter(
            case_type=self.case_type_obj,
            name='property'
        ).first()

    def _assert_type(self, value=''):
        prop = self._get_property()
        self.assertEqual(prop.data_type, value)

    def _get_case_property(self, name, case_type):
        return CaseProperty.objects.filter(
            case_type__name=case_type,
            name=name
        ).first()

    def test_new_case_type(self):
        self._assert_type()
        post_data = {"properties": '[{"caseType": "somethingelse", "name": "property", "data_type": "date"}]'}
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        prop = self._get_case_property(name="property", case_type="somethingelse")
        self.assertEqual(prop.data_type, 'date')

    def test_new_case_property(self):
        self._assert_type()
        post_data = {"properties": '[{"caseType": "caseType", "name": "otherproperty", "data_type": "date"}]'}
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        prop = self._get_case_property(name="otherproperty", case_type="caseType")
        self.assertEqual(prop.data_type, 'date')

    def test_update_with_incorrect_data_type(self):
        self._assert_type()
        post_data = {"properties": '[{"caseType": "caseType", "name": "property", "data_type": "blah"}]'}
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 400)
        self._assert_type()

    def test_update_no_name(self):
        self._assert_type()
        post_data = {"properties": '[{"caseType": "caseType", "name": "", "data_type": "date"}]'}
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 400)
        self._assert_type()

    def test_update_of_correct_data_type(self):
        self._assert_type()
        post_data = {"properties": '[{"caseType": "caseType", "name": "property", "data_type": "date"}]'}
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        self._assert_type('date')

    def test_update_description(self):
        prop = self._get_property()
        self.assertEqual(prop.description, '')
        post_data = {"properties": '[{"caseType": "caseType", "name": "property", "description": "description"}]'}
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        prop = self._get_property()
        self.assertEqual(prop.description, 'description')
