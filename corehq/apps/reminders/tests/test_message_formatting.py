from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.reminders.event_handlers import get_message_template_params
from corehq.apps.reminders.models import Message
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import create_test_case, set_parent_case
from datetime import datetime, timedelta
from django.test import TestCase


class MessageTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = 'message-formatting-test'
        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()

        cls.mobile_user = CommCareUser.create(
            cls.domain,
            'mobile1@message-formatting-test',
            '12345',
            first_name='Mobile',
            last_name='User'
        )

        cls.web_user = WebUser.create(
            cls.domain,
            'web1@message-formatting-test',
            '12345',
            first_name='Web',
            last_name='User'
        )

        cls.group = Group(domain=cls.domain, name='Test Group')
        cls.group.save()

        cls.location_type = LocationType.objects.create(
            domain=cls.domain,
            name='top-level',
            code='top-level'
        )

        cls.location = SQLLocation.objects.create(
            domain=cls.domain,
            name='Test Location',
            site_code='loc1234',
            location_type=cls.location_type
        )

    @classmethod
    def tearDownClass(cls):
        cls.mobile_user.delete()
        cls.web_user.delete()
        cls.group.delete()
        cls.location.delete()
        cls.location_type.delete()

    def test_render_context(self):
        message = 'The EDD for client with ID {case.external_id} is approaching in {case.edd.days_until} days.'
        context = {'case': {'external_id': 123, 'edd': datetime.utcnow() + timedelta(days=30)}}
        self.assertEqual(
            Message.render(message, **context),
            'The EDD for client with ID 123 is approaching in 30 days.'
        )

    def test_render_nested_context(self):
        message = 'Case name {case.name}, Parent name {case.parent.name}'
        context = {'case': {'name': 'abc', 'parent': {'name': 'def'}}}
        self.assertEqual(
            Message.render(message, **context),
            'Case name abc, Parent name def'
        )

    def test_render_missing_references(self):
        message = 'Case name {case.name}, Case id {case.external_id}, Parent name {case.parent.name}'
        context = {'case': {'name': 'abc'}}
        self.assertEqual(
            Message.render(message, **context),
            'Case name abc, Case id (?), Parent name (?)'
        )

        message = 'Ref {ref1} {ref1.ref2}'
        context = {'case': {'name': 'abc'}}
        self.assertEqual(
            Message.render(message, **context),
            'Ref (?) (?)'
        )

    def create_child_case(self, owner=None, modified_by=None):
        owner = owner or self.mobile_user
        modified_by = modified_by or self.mobile_user
        return create_test_case(self.domain, 'child', 'P002', case_properties={'child_prop1': 'def'},
            owner_id=owner.get_id, user_id=modified_by.get_id)

    def create_parent_case(self, owner=None, modified_by=None):
        owner = owner or self.mobile_user
        modified_by = modified_by or self.mobile_user
        return create_test_case(self.domain, 'parent', 'P001', case_properties={'parent_prop1': 'abc'},
            owner_id=owner.get_id, user_id=modified_by.get_id)

    def get_expected_template_params_for_mobile(self):
        return {
            'name': self.mobile_user.raw_username,
            'first_name': self.mobile_user.first_name,
            'last_name': self.mobile_user.last_name,
        }

    def get_expected_template_params_for_web(self):
        return {
            'name': self.web_user.username,
            'first_name': self.web_user.first_name,
            'last_name': self.web_user.last_name,
        }

    def get_expected_template_params_for_group(self):
        return {
            'name': self.group.name,
        }

    def get_expected_template_params_for_location(self):
        return {
            'name': self.location.name,
            'site_code': self.location.site_code,
        }

    @run_with_all_backends
    def test_case_template_params(self):
        with self.create_child_case() as child_case, self.create_parent_case() as parent_case:
            set_parent_case(self.domain, child_case, parent_case)
            child_case = CaseAccessors(self.domain).get_case(child_case.case_id)
            parent_case = CaseAccessors(self.domain).get_case(parent_case.case_id)

            child_expected_result = {'case': child_case.to_json()}
            child_expected_result['case']['parent'] = parent_case.to_json()
            child_expected_result['case']['owner'] = self.get_expected_template_params_for_mobile()
            child_expected_result['case']['last_modified_by'] = self.get_expected_template_params_for_mobile()
            self.assertEqual(get_message_template_params(child_case), child_expected_result)

            parent_expected_result = {'case': parent_case.to_json()}
            parent_expected_result['case']['owner'] = self.get_expected_template_params_for_mobile()
            parent_expected_result['case']['last_modified_by'] = self.get_expected_template_params_for_mobile()
            self.assertEqual(get_message_template_params(parent_case), parent_expected_result)

    @run_with_all_backends
    def test_owner_template_params(self):
        with self.create_parent_case(owner=self.mobile_user) as case:
            expected_result = {'case': case.to_json()}
            expected_result['case']['owner'] = self.get_expected_template_params_for_mobile()
            expected_result['case']['last_modified_by'] = self.get_expected_template_params_for_mobile()
            self.assertEqual(get_message_template_params(case), expected_result)

        with self.create_parent_case(owner=self.web_user) as case:
            expected_result = {'case': case.to_json()}
            expected_result['case']['owner'] = self.get_expected_template_params_for_web()
            expected_result['case']['last_modified_by'] = self.get_expected_template_params_for_mobile()
            self.assertEqual(get_message_template_params(case), expected_result)

        with self.create_parent_case(owner=self.group) as case:
            expected_result = {'case': case.to_json()}
            expected_result['case']['owner'] = self.get_expected_template_params_for_group()
            expected_result['case']['last_modified_by'] = self.get_expected_template_params_for_mobile()
            self.assertEqual(get_message_template_params(case), expected_result)

        with self.create_parent_case(owner=self.location) as case:
            expected_result = {'case': case.to_json()}
            expected_result['case']['owner'] = self.get_expected_template_params_for_location()
            expected_result['case']['last_modified_by'] = self.get_expected_template_params_for_mobile()
            self.assertEqual(get_message_template_params(case), expected_result)

    @run_with_all_backends
    def test_modified_by_template_params(self):
        with self.create_parent_case(modified_by=self.mobile_user, owner=self.location) as case:
            expected_result = {'case': case.to_json()}
            expected_result['case']['owner'] = self.get_expected_template_params_for_location()
            expected_result['case']['last_modified_by'] = self.get_expected_template_params_for_mobile()
            self.assertEqual(get_message_template_params(case), expected_result)

        with self.create_parent_case(modified_by=self.web_user, owner=self.location) as case:
            expected_result = {'case': case.to_json()}
            expected_result['case']['owner'] = self.get_expected_template_params_for_location()
            expected_result['case']['last_modified_by'] = self.get_expected_template_params_for_web()
            self.assertEqual(get_message_template_params(case), expected_result)

    def test_unicode_template_params(self):
        message = u'Case name {case.name}'
        context = {'case': {'name': u'\u0928\u092e\u0938\u094d\u0924\u0947'}}
        self.assertEqual(
            Message.render(message, **context),
            u'Case name \u0928\u092e\u0938\u094d\u0924\u0947'
        )
