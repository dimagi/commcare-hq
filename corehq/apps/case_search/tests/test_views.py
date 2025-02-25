from django.urls import reverse

from corehq.tests.util.htmx import HtmxViewTestCase
from corehq.util.test_utils import flag_enabled

from ..models import CSQLFixtureExpression, CSQLFixtureExpressionLog
from ..views import CSQLFixtureExpressionView


@flag_enabled('CSQL_FIXTURE')
class TestCSQLFixtureExpressionView(HtmxViewTestCase):
    def get_url(self):
        return reverse(CSQLFixtureExpressionView.urlname, args=[self.domain])

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
