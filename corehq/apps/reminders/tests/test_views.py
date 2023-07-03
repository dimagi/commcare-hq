from django.test import TestCase, RequestFactory
from django_prbac.models import Role, Grant
from http import HTTPStatus
from django.core.exceptions import PermissionDenied
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.models import WebUser, HqPermissions
from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.sms.models import Keyword
from corehq.apps.reminders.views import EditNormalKeywordView, ViewNormalKeywordView


class EditNormalKeywordViewTests(TestCase):
    def test_can_successfully_edit_keyword(self):
        keyword = self._create_keyword(keyword='abc', description='some description')
        modified_data = self._create_submission_data(keyword, description='desc')
        user = self._create_web_user()
        request = self._create_request(modified_data, user=user)

        EditNormalKeywordView.as_view()(request, domain=self.domain, keyword_id=keyword.couch_id)

        modified_keyword = Keyword.objects.get(id=keyword.id)
        self.assertEqual(modified_keyword.description, 'desc')

    def test_can_edit_erm_data_with_erm_permission(self):
        keyword = self._create_keyword(description='some description', upstream_id='123')
        modified_data = self._create_submission_data(keyword, description='desc', upstream_id='123')
        user_with_privilege = self._create_web_user(edit_linked_configurations=True)
        request = self._create_request(modified_data, user=user_with_privilege)

        EditNormalKeywordView.as_view()(request, domain=self.domain, keyword_id=keyword.couch_id)

        modified_keyword = Keyword.objects.get(id=keyword.id)
        self.assertEqual(modified_keyword.description, 'desc')

    def test_cannot_remove_synced_status(self):
        keyword = self._create_keyword(upstream_id='123')
        modified_data = self._create_submission_data(keyword, upstream_id=None)
        user = self._create_web_user(edit_linked_configurations=True)
        request = self._create_request(modified_data, user=user)

        EditNormalKeywordView.as_view()(request, domain=self.domain, keyword_id=keyword.couch_id)

        modified_keyword = Keyword.objects.get(id=keyword.id)
        self.assertEqual(modified_keyword.upstream_id, '123')

    def test_cannot_add_synced_status(self):
        keyword = self._create_keyword(upstream_id=None)
        modified_data = self._create_submission_data(keyword, upstream_id='123')
        user = self._create_web_user(edit_linked_configurations=True)
        request = self._create_request(modified_data, user=user)

        EditNormalKeywordView.as_view()(request, domain=self.domain, keyword_id=keyword.couch_id)

        modified_keyword = Keyword.objects.get(id=keyword.id)
        self.assertEqual(modified_keyword.upstream_id, None)

    def test_cannot_edit_keyword_without_erm_permission(self):
        keyword = self._create_keyword(keyword='abc', description='some description', upstream_id='123')
        modified_data = self._create_submission_data(keyword, description='desc')
        user_without_privilege = self._create_web_user(username='no_privs', edit_linked_configurations=False)
        request = self._create_request(modified_data, user=user_without_privilege)

        with self.assertRaises(PermissionDenied):
            EditNormalKeywordView.as_view()(request, domain=self.domain, keyword_id=keyword.couch_id)

    def test_cannot_view_edit_keyword_view_without_erm_permission(self):
        keyword = self._create_keyword(upstream_id='123')
        user_without_privilege = self._create_web_user(username='no_privs', edit_linked_configurations=False)
        request = self._create_view_request({}, user=user_without_privilege)

        with self.assertRaises(PermissionDenied):
            EditNormalKeywordView.as_view()(request, domain=self.domain, keyword_id=keyword.couch_id)

    def test_can_view_view_keyword_view_without_erm_permission(self):
        keyword = self._create_keyword(upstream_id='123')
        user_without_privilege = self._create_web_user(username='no_privs', edit_linked_configurations=False)
        request = self._create_view_request({}, user=user_without_privilege)

        response = ViewNormalKeywordView.as_view()(request, domain=self.domain, keyword_id=keyword.couch_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = cls._create_domain(cls.domain)

        sms_in_permission = Role.objects.get(slug=privileges.INBOUND_SMS)
        sms_out_permission = Role.objects.get(slug=privileges.OUTBOUND_SMS)

        cls.test_role = Role.objects.create(name='test-role', slug='test-role', description='test-role')
        Grant.objects.create(from_role=cls.test_role, to_role=sms_in_permission)
        Grant.objects.create(from_role=cls.test_role, to_role=sms_out_permission)

    def _create_submission_data(self, keyword, **modified_fields):
        initial_data = {
            'keyword': keyword.keyword,
            'description': keyword.description,
            'upstream_id': keyword.upstream_id,
            'sender_content_type': 'sms',
            'sender_message': 'etf',
            'sender_app_and_form_unique-id': '',
            'other_recipient_content_type': 'none',
            'other_recipient_type': 'USER_GROUP',
            'other_recipient_message': '',
            'other_recipient_app_and_form_unique_id': '',
            'allow_keyword_use_by': 'any',
        }

        data = {**initial_data, **modified_fields}
        data['upstream_id'] = data['upstream_id'] or ''

        return data

    def _create_request(self, data, user=None):
        request = RequestFactory().post('/', data=data)
        request.domain = self.domain
        request.user = user or self.user
        request.role = self.test_role
        return request

    def _create_view_request(self, data, user=None):
        request = RequestFactory().get('/', data=data)
        request.domain = self.domain
        request.user = user or self.user
        request.role = self.test_role
        return request

    @classmethod
    def _create_domain(cls, name):
        domain_obj = create_domain(name)
        domain_obj.granted_messaging_access = True
        domain_obj.save()
        cls.addClassCleanup(domain_obj.delete)
        return domain_obj

    def _create_web_user(self, username='test-user', **permissions):
        user = WebUser.create('', username, 'mockmock', None, None)

        user.add_domain_membership(self.domain)
        user_role = UserRole.create(domain=self.domain, name='TestUserRole')
        permissions = {'edit_messaging': True, **permissions}
        user_role.set_permissions(HqPermissions(**permissions).to_list())
        user.set_role(self.domain, user_role.get_qualified_id())

        user.save()
        self.addCleanup(user.delete, '', deleted_by=None)

        user.is_authenticated = True

        return user

    def _create_keyword(self, domain=None, keyword='abc', description='test description', upstream_id=None):
        return Keyword.objects.create(
            domain=domain or self.domain,
            keyword=keyword,
            description=description,
            upstream_id=upstream_id,
        )
