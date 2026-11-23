from django.test import SimpleTestCase, TestCase, RequestFactory
from django.urls import reverse
from django.utils.safestring import SafeString

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.models import ReportConfiguration, UCRExpression
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled
from corehq.apps.userreports.views import UCRExpressionListView
from corehq.apps.userreports.const import UCR_NAMED_EXPRESSION
from ..views import NamedExpressionHighlighter


class NamedExpressionHighlighterTests(SimpleTestCase):
    def test_normal_text_has_no_changes(self):
        self.assertEqual(NamedExpressionHighlighter.highlight_links('normalText'), 'normalText')

    def test_named_filter_is_highlighted(self):
        highlighted = NamedExpressionHighlighter.highlight_links('NamedFilter:abc')
        self.assertHTMLEqual(highlighted, '<a href="#NamedFilter:abc">NamedFilter:abc</a>')

    def test_result_is_html_safe(self):
        highlighted = NamedExpressionHighlighter.highlight_links('NamedFilter:abc')
        self.assertIsInstance(highlighted, SafeString)


class UCRExpressionListViewTests(TestCase):
    def test_paginated_list_limits_results(self):
        expressions = [self._create_expression(i) for i in range(3)]
        UCRExpression.objects.bulk_create(expressions)
        view = self._create_view(page=1, limit=2)

        names = {expression['itemData']['name'] for expression in view.paginated_list}
        self.assertSetEqual(names, {'expression0', 'expression1'})

    def test_paginated_list_respects_page(self):
        expressions = [self._create_expression(i) for i in range(3)]
        UCRExpression.objects.bulk_create(expressions)
        view = self._create_view(page=2, limit=2)

        names = {expression['itemData']['name'] for expression in view.paginated_list}
        self.assertSetEqual(names, {'expression2'})

    def test_default_limit(self):
        expressions = [self._create_expression(i) for i in range(12)]
        UCRExpression.objects.bulk_create(expressions)
        view = self._create_view(page=1)

        self.assertEqual(len(list(view.paginated_list)), 10)

    @staticmethod
    def _create_expression(index):
        return UCRExpression(
            name=f'expression{index}',
            domain='test-domain',
            expression_type=UCR_NAMED_EXPRESSION
        )

    @staticmethod
    def _create_view(page=1, limit=None):
        view = UCRExpressionListView()
        view.args = ['test-domain']
        kwargs = {'page': page}
        if limit:
            kwargs['limit'] = limit
        view.request = RequestFactory().get('/', kwargs)
        return view


@flag_enabled('USER_CONFIGURABLE_REPORTS')
class DeleteReportRedirectTests(TestCase):
    domain = 'delete-report-redirect'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(domain_obj.delete)
        cls.user = WebUser.create(cls.domain, 'admin@example.com', 'password', None, None, is_admin=True)
        cls.addClassCleanup(cls.user.delete, cls.domain, deleted_by=None)

    def setUp(self):
        self.client.force_login(self.user.get_django_user())

    def _delete_report(self, redirect):
        report = ReportConfiguration(domain=self.domain, config_id='missing-data-source')
        report.save()
        self.addCleanup(report.delete)
        return self.client.get(
            reverse('delete_configurable_report', args=[self.domain, report._id]),
            {'redirect': redirect},
        )

    def test_same_site_redirect(self):
        response = self._delete_report('/a/delete-report-redirect/reports/')
        assert response.status_code == 302
        assert response['Location'] == '/a/delete-report-redirect/reports/'

    def test_external_redirect_falls_back(self):
        response = self._delete_report('https://example.com/')
        assert response.status_code == 302
        assert response['Location'] == reverse('saved_reports', args=[self.domain])
