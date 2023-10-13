from django.test import TestCase, RequestFactory, override_settings
from django_prbac.models import Role, Grant
from corehq import privileges

from corehq.apps.users.models import WebUser
from corehq.apps.domain.shortcuts import create_domain

from corehq.apps.data_interfaces.models import AutomaticUpdateRule, CaseRuleAction, UpdateCaseDefinition
from corehq.apps.data_interfaces.views import AutomaticUpdateRuleListView


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
