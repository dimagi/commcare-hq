from django.test import SimpleTestCase, TestCase, RequestFactory
from django.utils.safestring import SafeString

from corehq.apps.userreports.models import UCRExpression
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
