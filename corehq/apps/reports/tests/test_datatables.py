from django.test import SimpleTestCase
from unittest.mock import patch, PropertyMock
from django.utils.safestring import SafeData, mark_safe

from corehq.apps.reports.datatables import (
    DataTablesColumn,
    DataTablesColumnGroup,
    DataTablesHeader
)


class DataTablesColumnTests(SimpleTestCase):
    def test_render_is_safe(self):
        column = DataTablesColumn(name='test-column')
        html = column.render_html
        self.assertIsInstance(html, SafeData)


class DataTablesColumnGroupTests(SimpleTestCase):
    def test_empty_group_html_is_empty_string(self):
        group = DataTablesColumnGroup('empty-group')
        self.assertEqual(group.render_html, '')

    def test_simple_group_html(self):
        col = DataTablesColumn(name='test-column')
        group = DataTablesColumnGroup('test-group')
        group.add_column(col)

        self.assertEqual(group.render_html, '<th colspan="1"><strong>test-group</strong></th>')

    def test_adds_css_span_of_columns(self):
        col1 = DataTablesColumn(name='test-column1', span=2)
        col2 = DataTablesColumn(name='test-column2', span=3)
        group = DataTablesColumnGroup('test-group')
        group.add_column(col1)
        group.add_column(col2)

        self.assertEqual(group.render_html, '<th class="col-sm-5" colspan="2"><strong>test-group</strong></th>')

    def test_render_is_safe(self):
        col = DataTablesColumn(name='test-column')
        group = DataTablesColumnGroup('test-group')
        group.add_column(col)
        self.assertIsInstance(group.render_html, SafeData)

    @patch.object(DataTablesColumn, 'render_html', new_callable=PropertyMock)
    def test_render_group_html_joins_columns(self, mock_render_html):
        mock_render_html.return_value = 'Column'
        col1 = DataTablesColumn(name='test-column1')
        col2 = DataTablesColumn(name='test-column2')
        group = DataTablesColumnGroup('test-group')
        group.add_column(col1)
        group.add_column(col2)

        self.assertEqual(group.render_group_html, 'Column\nColumn')

    @patch.object(DataTablesColumn, 'render_html', new_callable=PropertyMock)
    def test_render_group_html_does_not_escape_child_columns(self, mock_render_html):
        mock_render_html.return_value = mark_safe('<column/>')  # nosec: no user input
        col = DataTablesColumn(name='test-column')
        group = DataTablesColumnGroup('test-group')
        group.add_column(col)

        self.assertEqual(group.render_group_html, '<column/>')

    @patch.object(DataTablesColumn, 'render_html', new_callable=PropertyMock)
    def test_render_group_html_escapes_unsafe_child_columns(self, mock_render_html):
        mock_render_html.return_value = '<column/>'
        col = DataTablesColumn(name='test-column')
        group = DataTablesColumnGroup('test-group')
        group.add_column(col)

        self.assertEqual(group.render_group_html, '&lt;column/&gt;')

    def test_render_group_html_is_safe(self):
        col = DataTablesColumn(name='test-column')
        group = DataTablesColumnGroup('test-group')
        group.add_column(col)

        self.assertIsInstance(group.render_group_html, SafeData)


class DataTablesHeaderTests(SimpleTestCase):
    def test_empty_headers(self):
        header = DataTablesHeader()
        self.assertEqual(header.render_html, '<tr></tr>')

    @patch.object(DataTablesColumn, 'render_html', new_callable=PropertyMock)
    def test_output_from_columns(self, mock_render_html):
        mock_render_html.return_value = mark_safe('<column/>')  # nosec: no user input
        col1 = DataTablesColumn(name='test-column1')
        col2 = DataTablesColumn(name='test-column2')
        headers = DataTablesHeader(col1, col2)
        self.assertEqual(headers.render_html, '<tr><column/>\n<column/></tr>')

    @patch.object(DataTablesColumnGroup, 'render_html', new_callable=PropertyMock)
    @patch.object(DataTablesColumnGroup, 'render_group_html', new_callable=PropertyMock)
    def test_output_from_groups(self, mock_render_html, mock_render_group_html):
        mock_render_html.return_value = mark_safe('<header/>')  # nosec: no user input
        mock_render_group_html.return_value = mark_safe('<column/>')  # nosec: no user input
        group = DataTablesColumnGroup('test-group')
        headers = DataTablesHeader(group)
        # NOTE: This is documenting current behavior, but looks incorrect
        self.assertEqual(headers.render_html, '<tr><column/></tr><tr><header/></tr>')

    @patch.object(DataTablesColumn, 'render_html', new_callable=PropertyMock)
    def test_output_is_safe(self, mock_render_html):
        mock_render_html.return_value = mark_safe('<column/>')  # nosec: no user input
        col = DataTablesColumn(name='test-column1')
        headers = DataTablesHeader(col)
        self.assertIsInstance(headers.render_html, SafeData)
