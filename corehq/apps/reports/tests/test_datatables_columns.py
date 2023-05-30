from django.test import SimpleTestCase
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesColumnGroup


class DataTablesColumnTests(SimpleTestCase):
    def test_render_html_full_output(self):
        column = DataTablesColumn('Hello World')
        expected = ('<th rowspan="1" class="clickable">'
            '<div>'
                '<i class="icon-white fa dt-sort-icon"></i>'
                'Hello World'
            '</div>'
        '</th>')
        self.assertHTMLEqual(column.render_html, expected)

    def test_render_html_escapes_title(self):
        column = DataTablesColumn('<script>')
        expected = ('<th rowspan="1" class="clickable">'
            '<div>'
                '<i class="icon-white fa dt-sort-icon"></i>'
                '&lt;script&gt;'
            '</div>'
        '</th>')
        self.assertHTMLEqual(column.render_html, expected)


class DataTablesColumnGroupTests(SimpleTestCase):
    # need to stub this out, because the columns must be instances of DataTablesColumn
    class SimpleColumn(DataTablesColumn):
        @property
        def render_html(self):
            return self.html

    def test_render_html_with_no_columns(self):
        group = DataTablesColumnGroup('Test')
        self.assertHTMLEqual(group.render_html, '')

    def test_render_html_with_columns(self):
        col1 = DataTablesColumn('Hello')
        col2 = DataTablesColumn('World')
        group = DataTablesColumnGroup('Test', col1, col2)
        expected = ('''
        <th colspan="2">
            <strong>Test</strong>
        </th>
        ''')
        self.assertHTMLEqual(group.render_html, expected)

    def test_render_group_html(self):
        col1 = self.SimpleColumn('Column One')
        col2 = self.SimpleColumn('Column Two')
        group = DataTablesColumnGroup('Test', col1, col2)
        self.assertHTMLEqual(group.render_group_html, 'Column One\nColumn Two')
