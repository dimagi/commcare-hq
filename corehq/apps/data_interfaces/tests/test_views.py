from django.test import RequestFactory, TestCase, override_settings

from django_prbac.models import Grant, Role

from corehq import privileges
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseRuleAction,
    UpdateCaseDefinition,
)
from corehq.apps.data_interfaces.views import (
    AutomaticUpdateRuleListView,
    DeduplicationRuleCreateView,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser


@override_settings(REQUIRE_TWO_FACTOR_FOR_SUPERUSERS=False)
class AutomaticUpdateRuleListViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = cls._create_domain(cls.domain)
        cls.user = cls._create_web_user()

        # Create a role, then link data_cleanup permission to it
        cls.test_role = Role.objects.create(name='test-role', slug='test-role', description='test-role')
        (data_cleanup_permission, _created) = Role.objects.get_or_create(
            slug=privileges.DATA_CLEANUP,
            name=privileges.Titles.get_name_from_privilege(privileges.DATA_CLEANUP)
        )
        Grant.objects.create(from_role=cls.test_role, to_role=data_cleanup_permission)

    def test_can_delete_existing_rule(self):
        rule = self._create_rule()
        deletion_request = self._create_deletion_request(rule.id)

        AutomaticUpdateRuleListView.as_view()(deletion_request, domain=self.domain)

        # the rule is only 'soft' deleted, so it remains in the database
        deleted_rule = AutomaticUpdateRule.objects.get(id=rule.id)
        self.assertTrue(deleted_rule.deleted)

    @classmethod
    def _create_web_user(cls):
        # A Couch user is required for logout
        existing_user = WebUser.get_by_username('test-user')
        if existing_user:
            existing_user.delete('', deleted_by=None)
        user = WebUser.create('', 'test-user', 'mockmock', None, None)
        user.is_superuser = True
        user.is_authenticated = True
        user.save()
        cls.addClassCleanup(user.delete, '', deleted_by=None)
        return user

    @classmethod
    def _create_domain(cls, name):
        domain_obj = create_domain(name)
        cls.addClassCleanup(domain_obj.delete)
        return domain_obj

    def _create_rule(self, domain='test-domain', name='Test Rule', close_case=True, upstream_id=None):
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name=name,
            active=True,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
            case_type='person',
            filter_on_server_modified=True,
            server_modified_boundary=None,
            upstream_id=upstream_id
        )

        if close_case:
            close_case_definition = UpdateCaseDefinition.objects.create(close_case=True)
            action = CaseRuleAction(rule=rule)
            action.definition = close_case_definition
            action.save()

        return rule

    def _create_deletion_request(self, id):
        request = RequestFactory().post('/somepath', {'action': 'delete', 'id': id})
        request.domain = self.domain
        request.user = self.user
        request.role = self.test_role
        return request


class DeduplicationRuleCreateViewTests(TestCase):
    def test_system_properties_are_included_with_case_properties(self):
        case_type = CaseType.objects.create(name='case', domain=self.domain)
        CaseProperty.objects.create(name='prop1', case_type=case_type)
        CaseProperty.objects.create(name='prop2', case_type=case_type)

        prop_dict = DeduplicationRuleCreateView.get_augmented_data_dict_props_by_case_type(self.domain)

        self.assertEqual(set(prop_dict['case']), {'name', 'owner_id', 'prop1', 'prop2'})

    def test_system_properties_work_with_duplicate_case_properties(self):
        case_type = CaseType.objects.create(name='case', domain=self.domain)
        CaseProperty.objects.create(name='name', case_type=case_type)
        CaseProperty.objects.create(name='owner_id', case_type=case_type)

        prop_dict = DeduplicationRuleCreateView.get_augmented_data_dict_props_by_case_type(self.domain)

        self.assertEqual(set(prop_dict['case']), {'name', 'owner_id'})

    def test_system_properties_override_deprecated_properties(self):
        case_type = CaseType.objects.create(name='case', domain=self.domain)
        CaseProperty.objects.create(name='prop1', case_type=case_type)
        CaseProperty.objects.create(name='name', deprecated=True, case_type=case_type)

        prop_dict = DeduplicationRuleCreateView.get_augmented_data_dict_props_by_case_type(self.domain)

        self.assertEqual(set(prop_dict['case']), {'name', 'owner_id', 'prop1'})

    def test_properties_are_sorted(self):
        case_type = CaseType.objects.create(name='cookies', domain=self.domain)
        CaseProperty.objects.create(name='golden_oreos', case_type=case_type)
        CaseProperty.objects.create(name='peanut_butter_oreos', case_type=case_type)
        CaseProperty.objects.create(name='oreos', case_type=case_type)

        prop_dict = DeduplicationRuleCreateView.get_augmented_data_dict_props_by_case_type(self.domain)
        self.assertEqual(
            prop_dict['cookies'],
            ['golden_oreos', 'name', 'oreos', 'owner_id', 'peanut_butter_oreos']
        )

    def setUp(self):
        self.domain = 'test-domain'
