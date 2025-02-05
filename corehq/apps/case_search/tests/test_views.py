from django.test import TestCase
from django.urls import reverse

from corehq.apps.case_search.models import (
    CSQLFixtureExpression,
    CSQLFixtureExpressionLog,
)
from corehq.apps.case_search.views import CSQLFixtureExpressionView
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


@flag_enabled('CSQL_FIXTURE')
class TestCSQLFixtureExpressionView(TestCase):
    domain = 'test-domain'
    username = 'username@test.com'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.user = WebUser.create(
            cls.domain, cls.username, 'password', None, None, is_admin=True
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def hx_action(self, action, data):
        self.client.login(username=self.username, password='password')
        return self.client.post(
            reverse(CSQLFixtureExpressionView.urlname, args=[self.domain]),
            data,
            headers={'HQ-HX-Action': action},
        )

    def test_create_update_delete(self):
        # create
        response = self.hx_action('save_expression', {
            'name': 'my_indicator_name',
            'csql': 'original csql',
        })
        self.assertEqual(response.status_code, 200)
        expression = CSQLFixtureExpression.objects.get(domain=self.domain, name='my_indicator_name')
        self.assertEqual(expression.csql, 'original csql')

        # update
        response = self.hx_action('save_expression', {
            'pk': expression.pk,
            'name': expression.name,
            'csql': 'updated csql',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            CSQLFixtureExpression.objects.get(pk=expression.pk).csql,
            'updated csql',
        )

        # delete
        response = self.hx_action('delete_expression', {'pk': expression.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CSQLFixtureExpression.objects.get(pk=expression.pk).deleted)

        # check log
        self.assertEqual(
            list(expression.csqlfixtureexpressionlog_set.values_list('action', 'csql')),
            [(CSQLFixtureExpressionLog.Action.CREATE.value, 'original csql'),
             (CSQLFixtureExpressionLog.Action.UPDATE.value, 'updated csql'),
             (CSQLFixtureExpressionLog.Action.DELETE.value, '')],
        )
