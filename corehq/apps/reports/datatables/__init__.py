from django.utils.html import format_html, format_html_join
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.functional import Promise

from . import DTSortDirection, DTSortType


class DataTablesColumn(object):
    rowspan = 1

    def __init__(self, name, span=0, sort_type=None, sort_direction=None,
                 help_text=None, sortable=True, rotate=False,
                 expected=None, prop_name=None, visible=True, data_slug=None,
                 alt_prop_name=None, width=None, css_class=None, sql_col=None,
                 use_bootstrap5=False):
        self.html = name
        self.css_span = span
        self.sort_type = sort_type
        self.sort_direction = sort_direction if sort_direction else [DTSortDirection.ASC, DTSortDirection.DSC]
        self.help_text = help_text
        self.sortable = sortable
        self.rotate = rotate
        self.prop_name = prop_name
        self.visible = visible
        if isinstance(expected, int):
            expected = "%d" % expected
        self.expected = expected
        self.data_slug = data_slug
        self.alt_prop_name = alt_prop_name
        self.width = width
        self.css_class = css_class
        self.sql_col = sql_col
        self.use_bootstrap5 = use_bootstrap5

    @property
    def render_html(self):
        css_classes = []
        if self.css_span:
            css_classes.append("span%d" % self.css_span)
        if self.sortable:
            css_classes.append("clickable")

        column_params = dict(
            title=self.html,
            sort=self.sortable,
            rotate=self.rotate,
            css=" ".join(css_classes),
            rowspan=self.rowspan,
            help_text=self.help_text,
            expected=self.expected,
            width=self.width
        )
        if self.use_bootstrap5:
            template_path = "reports/datatables/bootstrap5/column.html"
        else:
            template_path = "reports/datatables/bootstrap3/column.html"
        return render_to_string(template_path, dict(
            col=column_params
        ))

    @property
    def render_aoColumns(self):
        # todo eventually this should be renamed to render_column and references to
        # `render_aoColumns` should be updated.
        if self.use_bootstrap5:
            return self._bootstrap5_render_column()
        return self._bootstrap3_render_aoColumns()

    def _bootstrap5_render_column(self):
        column = {
            "order": self.sort_direction,
            "orderable": self.sortable,
        }
        if self.prop_name:
            column['name'] = self.prop_name
        if self.sort_type:
            column['type'] = self.sort_type
        if self.rotate:
            column["width"] = "10px"
        if not self.visible:
            column["visible"] = self.visible
        if self.data_slug:
            column['data'] = {
                'slug': self.data_slug,
            }
        if self.css_class:
            column['className'] = self.css_class
        return column

    def _bootstrap3_render_aoColumns(self):
        aoColumns = dict(asSorting=self.sort_direction)

        if self.prop_name:
            aoColumns['sName'] = self.prop_name
        if self.sort_type:
            aoColumns["sType"] = self.sort_type
        if not self.sortable:
            aoColumns["bSortable"] = self.sortable
        if self.rotate:
            aoColumns["sWidth"] = '10px'
        if not self.visible:
            aoColumns["bVisible"] = self.visible
        if self.data_slug:
            aoColumns['mDataProp'] = self.data_slug
        if self.css_class:
            aoColumns['sClass'] = self.css_class
        return aoColumns


class NumericColumn(DataTablesColumn):

    def __init__(self, *args, **kwargs):
        return super(NumericColumn, self).__init__(
            sort_type=DTSortType.NUMERIC, sortable=True, *args, **kwargs)


class DataTablesColumnGroup(object):
    css_span = 0

    def __init__(self, name, *args):
        self.columns = list()
        self.html = name
        for col in args:
            if isinstance(col, DataTablesColumn):
                self.add_column(col)

    def add_column(self, column):
        self.columns.append(column)
        self.css_span += column.css_span

    def remove_column(self, column):
        self.columns.remove(column)
        self.css_span -= column.css_span

    @property
    def render_html(self):
        template = '<th{css_class} colspan="{colspan}"><strong>{title}</strong></th>'
        css_class = mark_safe(  # nosec: no user input
            ' class="col-sm-%d"' % self.css_span if self.css_span > 0 else ''
        )
        template_properties = {
            'title': self.html,
            'css_class': css_class,
            'colspan': len(self.columns)
        }
        return format_html(template, **template_properties) if self.columns else ''

    @property
    def render_group_html(self):
        return format_html_join('\n', '{}', ((col.render_html,) for col in self.columns))

    @property
    def render_aoColumns(self):
        aoColumns = list()
        for col in self.columns:
            aoColumns.append(col.render_aoColumns)
        return aoColumns

    def __iter__(self):
        for col in self.columns:
            yield col

    def __len__(self):
        length = 0
        for _ in self:
            length += 1
        return length

    def __bool__(self):
        return True

    __nonzero__ = __bool__


class DataTablesHeader(object):
    has_group = False
    no_sort = False
    complex = True
    span = 0
    auto_width = False
    custom_sort = None

    def __init__(self, *args):
        self.header = list()
        for col in args:
            if isinstance(col, DataTablesColumnGroup):
                self.has_group = True
            if isinstance(col, DataTablesColumnGroup) or \
               isinstance(col, DataTablesColumn):
                self.add_column(col)

    def add_column(self, column):
        self.header.append(column)
        self.span += column.css_span
        self.check_auto_width()

    def remove_column(self, column):
        self.header.remove(column)
        self.span -= column.css_span
        self.check_auto_width()

    def prepend_column(self, column):
        self.header = [column] + self.header
        self.span += column.css_span
        self.check_auto_width()

    def insert_column(self, column, index):
        self.span += column.css_span
        self.header = self.header[:index] + [column] + self.header[index:]
        self.check_auto_width()

    def check_auto_width(self):
        self.auto_width = bool(0 < self.span <= 12)

    @property
    def as_export_table(self):
        head = list()
        groups = list()
        use_groups = False
        for column in self.header:
            if isinstance(column, DataTablesColumnGroup):
                use_groups = True
                groups.extend([column.html] + [" "] * (len(column.columns) - 1))
                for child_columns in column.columns:
                    head.append(child_columns.html)
            else:
                head.append(column.html)
                groups.append(" ")

        def unicodify(h):
            # HACK ideally we would not have to guess at the encoding of `h`
            # (when it is not unicode). Hopefully all byte strings that come
            # through here are encoded as UTF-8. If not, .decode() may blow up.
            return h if isinstance(h, (str, Promise)) else h.decode("utf-8")
        head = list(map(unicodify, head))
        if use_groups:
            return [groups, head]
        else:
            return [head]

    @property
    def render_html(self):
        head = list()
        groups = list()
        for column in self.header:
            if isinstance(column, DataTablesColumn):
                column.rowspan = 2 if self.has_group else 1
                if self.no_sort:
                    column.sortable = False
            elif isinstance(column, DataTablesColumnGroup):
                groups.append(column.render_group_html)
            head.append(column.render_html)

        headers_data = format_html_join('\n', '{}', ((header,) for header in head))
        html = format_html('<tr>{}</tr>', headers_data)

        if len(groups):
            group_data = format_html_join('\n', '{}', ((group,) for group in groups))
            html = format_html('{}<tr>{}</tr>', html, group_data)

        return html

    @property
    def render_aoColumns(self):
        aoColumns = list()
        for column in self.header:
            if isinstance(column, DataTablesColumnGroup):
                aoColumns.extend(column.render_aoColumns)
            else:
                aoColumns.append(column.render_aoColumns)
        return aoColumns

    def __iter__(self):
        for column in self.header:
            yield column

    def __len__(self):
        length = 0
        for col in self:
            length += len(col) if isinstance(col, DataTablesColumnGroup) else 1
        return length

    def __bool__(self):
        return True

    __nonzero__ = __bool__
