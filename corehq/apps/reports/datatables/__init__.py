from django.template.loader import render_to_string
from . import DTSortDirection

class DataTablesColumn(object):
    rowspan = 1

    def __init__(self, name, span=0, sort_type=None, sort_direction=None,
                 help_text=None, sortable=True, rotate=False,
                 expected=None, prop_name=None):
        self.html = name
        self.css_span = span
        self.sort_type = sort_type
        self.sort_direction = sort_direction if sort_direction else [DTSortDirection.ASC, DTSortDirection.DSC]
        self.help_text = help_text
        self.sortable = sortable
        self.rotate = rotate
        self.prop_name=prop_name
        if isinstance(expected, int):
            expected = "%d" % expected
        self.expected = expected

    @property
    def render_html(self):
        column_params=dict(
            title=self.html,
            sort=self.sortable,
            rotate=self.rotate,
            css="span%d" % self.css_span if self.css_span > 0 else '',
            rowspan=self.rowspan,
            help_text=self.help_text,
            expected=self.expected
        )
        return render_to_string("reports/datatables/column.html", dict(
            col=column_params
        ))

    @property
    def render_aoColumns(self):
        aoColumns = dict(asSorting=self.sort_direction)

        if self.prop_name:
            aoColumns['sName'] = self.prop_name
        if self.sort_type:
            aoColumns["sType"] = self.sort_type
        if not self.sortable:
            aoColumns["bSortable"] = self.sortable
        if self.rotate:
            aoColumns["sWidth"] = '10px'
        return aoColumns


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
        template = '<th%(css_class)s colspan="%(colspan)d"><strong>%(title)s</strong></th>'
        css_class = ' class="span%d"' % self.css_span if self.css_span > 0 else ''
        return template % dict(title=self.html, css_class=css_class, colspan=len(self.columns)) if self.columns else ""

    @property
    def render_group_html(self):
        group = list()
        for col in self.columns:
            group.append(col.render_html)
        return "\n".join(group)

    @property
    def render_aoColumns(self):
        aoColumns = list()
        for col in self.columns:
            aoColumns.append(col.render_aoColumns)
        return aoColumns


class DataTablesHeader(object):
    has_group = False
    no_sort = False
    complex = True
    span = 0
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
    def as_table(self):
        head = list()
        groups = list()
        use_groups = False
        for column in self.header:
            if isinstance(column, DataTablesColumnGroup):
                use_groups = True
                groups.extend([column.html] + [" "]*(len(column.columns)-1))
                for child_columns in column.columns:
                    head.append(child_columns.html)
            else:
                head.append(column.html)
                groups.append(" ")
        if use_groups:
            return [groups, head]
        else:
            return [head]

    @property
    def render_html(self):
        head = list()
        groups = list()
        head.append("<tr>")
        groups.append("<tr>")
        for column in self.header:
            if isinstance(column, DataTablesColumn):
                column.rowspan = 2 if self.has_group else 1
                if self.no_sort:
                    column.sortable = False
            elif isinstance(column, DataTablesColumnGroup):
                groups.append(column.render_group_html)
            head.append(column.render_html)
        head.append("</tr>")
        groups.append("</tr>")
        if len(groups) > 2:
            head.extend(groups)
        return "\n".join(head)

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



