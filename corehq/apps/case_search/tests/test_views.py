from corehq.util.test_utils import flag_enabled
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.case_search.models import CSQLFixtureExpression, CSQLFixtureExpressionLog
from corehq.apps.case_search.views import CSQLFixtureExpressionView
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import HqPermissions, WebUser
from corehq.apps.users.models_role import UserRole
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch


@flag_enabled('MODULE_BADGES')
class TestCSQLFixtureExpressionView(TestCase):

    DOMAIN = 'test-domain'
    DEFAULT_USER_PASSWORD = 'password'
    USERNAME = 'username@test.com'

    @classmethod
    def setUpClass(cls):
        super(TestCSQLFixtureExpressionView, cls).setUpClass()
        cls.domain_obj = create_domain(cls.DOMAIN)
        cls.user = WebUser.create(
            cls.DOMAIN, cls.USERNAME, cls.DEFAULT_USER_PASSWORD, None, None, is_admin=True
        )
        cls.role = UserRole.create(cls.DOMAIN, 'Fixtures Access', HqPermissions(edit_data=True))
        cls.user.set_role(cls.DOMAIN, cls.role.get_qualified_id())

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.DOMAIN, deleted_by=None)
        cls.domain_obj.delete()
        delete_all_users()
        super(TestCSQLFixtureExpressionView, cls).tearDownClass()

    def _get_view_response(self, data):
        self.client.login(username=self.USERNAME, password=self.DEFAULT_USER_PASSWORD)
        response = self.client.post(reverse(CSQLFixtureExpressionView.urlname, args=[self.DOMAIN]), data)
        return response

    @patch('django_prbac.decorators.has_privilege', return_value=True)
    def test_create_update_delete(self, has_privilege):
        deleted_exp = CSQLFixtureExpression.objects.create(domain=self.DOMAIN, name='deleted_exp', csql='asdf')
        exp2 = CSQLFixtureExpression.objects.create(domain=self.DOMAIN, name='exp2', csql='asdf')
        data = {
            'id': [exp2.id, ''],
            'name': ['exp2', 'exp3'],
            'csql': ['asdfg', 'asdf'],
        }
        response = self._get_view_response(data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CSQLFixtureExpression.objects.filter(
            domain=self.DOMAIN, name='deleted_exp', deleted=False).exists())
        CSQLFixtureExpression.objects.get(domain=self.DOMAIN, name='exp2', id=exp2.id, csql='asdfg')
        CSQLFixtureExpression.objects.get(domain=self.DOMAIN, name='exp3', csql='asdf')
        CSQLFixtureExpressionLog.objects.get(expression=deleted_exp,
                                             action=CSQLFixtureExpressionLog.Action.DELETE)
        CSQLFixtureExpressionLog.objects.get(expression=exp2, action=CSQLFixtureExpressionLog.Action.UPDATE)
        CSQLFixtureExpressionLog.objects.get(name='exp3', action=CSQLFixtureExpressionLog.Action.CREATE)
