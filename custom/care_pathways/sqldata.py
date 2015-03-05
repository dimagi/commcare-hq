from itertools import groupby
from sqlagg.base import AliasColumn, QueryMeta, CustomQueryColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import *
from sqlalchemy.sql.expression import join, alias
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, AggregateColumn, TableDataFormat
from custom.care_pathways.utils import get_domain_configuration, is_mapping, get_mapping, is_domain, is_practice, get_pracices, get_domains, TableCardDataIndividualFormatter, TableCardDataGroupsFormatter
from sqlalchemy import select
import urllib
import re
from django.utils import html

def _get_grouping(prop_dict):
        group = prop_dict['group']
        if group == '' or group == 'value_chain':
            group_by = ['value_chain']
        elif group == 'domain':
            group_by = ['value_chain', 'domains']
        elif group == 'practice':
            group_by = ['value_chain', 'domains', 'practices']
        else:
            group_by = []
        return group_by

class CareQueryMeta(QueryMeta):

    def __init__(self, table_name, filters, group_by, key):
        self.key = key
        super(CareQueryMeta, self).__init__(table_name, filters, group_by)


    def execute(self, metadata, connection, filter_values):
        return connection.execute(self._build_query(filter_values)).fetchall()

    def _build_query(self, filter_values):
        having = []
        filter_cols = []
        external_cols = _get_grouping(filter_values)

        for fil in self.filters:
            if isinstance(fil, ANDFilter):
                filter_cols.append(fil.filters[0].column_name)
                having.append(fil.build_expression())
            elif fil.column_name not in ['group', 'gender', 'group_leadership', 'disaggregate_by',
                                         'table_card_group_by']:
                if fil.column_name not in external_cols and fil.column_name != 'maxmin':
                    filter_cols.append(fil.column_name)
                having.append(fil.build_expression())

        group_having = ''
        having_group_by = []
        if ('disaggregate_by' in filter_values and filter_values['disaggregate_by'] == 'group') or ('table_card_group_by' in filter_values and filter_values['table_card_group_by']):
            group_having = "group_leadership=\'Y\'"
            having_group_by.append('group_leadership')
        elif 'group_leadership' in filter_values and filter_values['group_leadership']:
            group_having = "(MAX(CAST(gender as int4)) + MIN(CAST(gender as int4))) = :group_leadership and group_leadership=\'Y\'"
            having_group_by.append('group_leadership')
            filter_cols.append('group_leadership')
        elif 'gender' in filter_values and filter_values['gender']:
            group_having = "(MAX(CAST(gender as int4)) + MIN(CAST(gender as int4))) = :gender"

        table_card_group = []
        if 'group_name' in self.group_by:
            table_card_group.append('group_name')
        s1 = alias(select(['doc_id', 'group_id', 'MAX(prop_value) + MIN(prop_value) as maxmin'] + filter_cols + external_cols,
                                from_obj='"fluff_FarmerRecordFluff"',
                                group_by=['doc_id', 'group_id'] + filter_cols + external_cols), name='x')
        s2 = alias(select(['group_id', '(MAX(CAST(gender as int4)) + MIN(CAST(gender as int4))) as gender'] + table_card_group, from_obj='"fluff_FarmerRecordFluff"',
                                group_by=['group_id'] + table_card_group + having_group_by, having=group_having), name='y')
        return select(['COUNT(x.doc_id) as %s' % self.key] + self.group_by,
               group_by=['maxmin'] + filter_cols + self.group_by,
               having=" and ".join(having),
               from_obj=join(s1, s2, s1.c.group_id==s2.c.group_id)).params(filter_values)


class CareCustomColumn(CustomQueryColumn):
    query_cls = CareQueryMeta
    name = 'custom_care'

    def get_query_meta(self, default_table_name, default_filters, default_group_by):
        table_name = self.table_name or default_table_name
        filters = self.filters or default_filters
        group_by = self.group_by or default_group_by
        return self.query_cls(table_name, filters, group_by, self.key)


class GeographySqlData(SqlData):
    table_name = "fluff_GeographyFluff"

    def __init__(self, domain):
        self.geography_config = get_domain_configuration(domain)['geography_hierarchy']
        self.config = dict(domain=domain, empty='')

    @property
    def filters(self):
        return [EQ('domain', 'domain'), NOTEQ('lvl_1', 'empty')]

    @property
    def group_by(self):
        return [k for k in self.geography_config.keys()]

    @property
    def columns(self):
        levels = [k for k in self.geography_config.keys()]
        columns = []
        for k in levels:
            columns.append(DatabaseColumn(k, SimpleColumn(k)))
        return columns


class CareSqlData(SqlData):
    no_value = {'sort_key': 0, 'html': 0}
    table_name = 'fluff_FarmerRecordFluff'

    def __init__(self, domain, config, request_params):
        self.domain = domain
        self.geography_config = get_domain_configuration(domain)['geography_hierarchy']
        self.config = config
        self.request_params = self.filter_request_params(request_params)
        super(CareSqlData, self).__init__(config=config)

    def percent_fn(self, x, y, z):
        sum_all = (x or 0) + (y or 0) + (z or 0)
        return "%.2f%%" % (100 * int(x or 0) / float(sum_all or 1))

    @property
    def filters(self):
        filters = [EQ("domain", "domain"), EQ("ppt_year", "ppt_year"), AND([NOTEQ("case_status", "duplicate"),
                                                                            NOTEQ("case_status", "test")])]
        for k, v in self.geography_config.iteritems():
            if k in self.config and self.config[k]:
                filters.append(IN(k, k))
        if 'value_chain' in self.config and self.config['value_chain']:
            filters.append(EQ("value_chain", "value_chain"))
        if 'domains' in self.config and self.config['domains'] and self.config['domains'] != ('0',):
            filters.append(IN("domains", "domains"))
        if 'practices' in self.config and self.config['practices'] and self.config['practices'] != ('0',):
            filters.append(IN("practices", "practices"))
        if 'group_leadership' in self.config and self.config['group_leadership']:
            filters.append(EQ('group_leadership', 'group_leadership'))
        if 'cbt_name' in self.config and self.config['cbt_name']:
            filters.append(EQ('owner_id', 'cbt_name'))
        if 'schedule' in self.config and self.config['schedule'] and self.config['schedule'] != ('0',):
            filters.append(IN('schedule', 'schedule'))
        return filters

    def filter_request_params(self, request_params):
        if 'startdate' in request_params:
            request_params.pop('startdate')
        if 'enddate' in request_params:
             request_params.pop('enddate')
        if 'filterSet' in request_params:
             request_params.pop('filterSet')
        if 'hq_filters' in request_params:
             request_params.pop('hq_filters')

        return request_params


class AdoptionBarChartReportSqlData(CareSqlData):

    def group_name_fn(self, group_name):
        text = None
        if is_mapping(group_name, self.domain):
            self.request_params['type_value_chain'] = group_name
            self.request_params['group_by'] = 'domain'
            text = next((item for item in get_mapping(self.domain) if item['val'] == group_name), None)['text']

        if is_domain(group_name, self.domain):
            self.request_params['type_domain'] = group_name
            self.request_params['group_by'] = 'practice'
            text = next((item for item in get_domains(self.domain) if item['val'] == group_name), None)['text']

        if is_practice(group_name, self.domain):
            # TODO practices should probably redirect to other report
            self.request_params['type_practice'] = group_name

            text = next((item for item in get_pracices(self.domain) if item['val'] == group_name), None)['text']

        from custom.care_pathways.reports.adoption_bar_char_report import AdoptionBarChartReport
        url = html.escape(AdoptionBarChartReport.get_url(*[self.domain]) + "?" + urllib.urlencode(self.request_params))
        return html.mark_safe("<a class='ajax_dialog' href='%s' target='_blank'>%s</a>" % (url, text))

    @property
    def columns(self):
        group = self.config['group']
        first_columns = 'value_chain'
        if group == '' or group == 'value_chain':
            first_columns = 'value_chain'
        elif group == 'domain':
            first_columns = 'domains'
        elif group == 'practice':
            first_columns = 'practices'

        return [
            DatabaseColumn('', SimpleColumn(first_columns), self.group_name_fn),
            AggregateColumn('All', self.percent_fn,
                            [CareCustomColumn('all', filters=self.filters + [EQ("maxmin", 'all'),]), AliasColumn('some'), AliasColumn('none')]),
            AggregateColumn('Some', self.percent_fn,
                            [CareCustomColumn('some', filters=self.filters + [EQ("maxmin", 'some'),]), AliasColumn('all'), AliasColumn('none')]),
            AggregateColumn('None', self.percent_fn,
                            [CareCustomColumn('none', filters=self.filters + [EQ("maxmin", 'none'),]), AliasColumn('all'), AliasColumn('some')])
        ]

    @property
    def group_by(self):
        return _get_grouping(self.config)


class AdoptionDisaggregatedSqlData(CareSqlData):
    no_value = {'sort_key': 0, 'html': 0}

    @property
    def filters(self):
        filters = super(AdoptionDisaggregatedSqlData, self).filters
        if 'disaggregate_by' in self.config and self.config['disaggregate_by']:
            filters.append(EQ('disaggregate_by', self.config['disaggregate_by']))
        return filters

    @property
    def group_by(self):
        return _get_grouping(self.config) + ['gender']

    def _to_display(self, value):
        display = {'sort_key': 0, 'html': 0}
        if value == 0:
            display = {'sort_key': 0, 'html': 'None Women'}
        elif value == 1:
            display = {'sort_key': 0, 'html': 'Some Women'}
        elif value == 2:
            display = {'sort_key': 0, 'html': 'All Women'}

        return display


    @property
    def columns(self):
        return [
            DatabaseColumn('', AliasColumn('gender'), format_fn=self._to_display),
            AggregateColumn('None', lambda x:x,
                            [CareCustomColumn('none', filters=self.filters + [EQ("maxmin", 'none')])]),
            AggregateColumn('Some', lambda x:x,
                            [CareCustomColumn('some', filters=self.filters + [EQ("maxmin", 'some')])]),
            AggregateColumn('All', lambda x:x,
                            [CareCustomColumn('all', filters=self.filters + [EQ("maxmin", 'all')])])

        ]


class TableCardSqlData(CareSqlData):

    def format_cell_fn(self, x, y):
        sum_all = (x or 0) + (y or 0)
        percentage = 100 * int(x or 0) / float(sum_all or 1)
        text = "%d/%d (%.2f%%)" % ((x or 0), sum_all, percentage)

        return text

    def group_name_fn(self, group_name):
        text = None
        if is_mapping(group_name, self.domain):

            text = next((item for item in get_mapping(self.domain) if item['val'] == group_name), None)['text']

        if is_domain(group_name, self.domain):
            text = next((item for item in get_domains(self.domain) if item['val'] == group_name), None)['text']

        if is_practice(group_name, self.domain):
            text = next((item for item in get_pracices(self.domain) if item['val'] == group_name), None)['text']

        return text

    def first_column_format(self, x):
        if self.config['table_card_group_by'] == 'group_name':
            return x
        else:
            if int(x) == 0:
                return 'None Women'
            elif int(x) == 1:
                return 'Some Women'
            elif int(x) == 2:
                return 'All Women'



    @property
    def columns(self):
        if self.config['table_card_group_by'] == 'group_name':
            first_column = 'group_name'
        else:
            first_column = 'gender'

        return [
            DatabaseColumn('', SimpleColumn(first_column), format_fn=self.first_column_format),
            AggregateColumn('practice_count', self.format_cell_fn,
                            [CareCustomColumn('all', filters=self.filters + [EQ("maxmin", 'all')]),
                             CareCustomColumn('none', filters=self.filters + [EQ("maxmin", 'none')])]),
        ]

    def headers(self, data):
        column_headers = []
        groupped_headers = [list(v) for l,v in groupby(sorted(data.keys(), key=lambda x:x[2]), lambda x: x[2])]
        for domain in groupped_headers:
            groupped_practices = [list(v) for l,v in groupby(sorted(domain, key=lambda x:x[3]), lambda x: x[3])]
            domain_group = DataTablesColumnGroup(self.group_name_fn(domain[0][2]))
            for practice in groupped_practices:
                domain_group.add_column(DataTablesColumn(self.group_name_fn(practice[0][3])))

            column_headers.append(domain_group)
        column_headers = sorted(column_headers, key=lambda x: x.html)

        i = 1
        for column in column_headers:
            for j in range(0, len(column.columns)):
                column.columns[j] = DataTablesColumn('Practice ' + i.__str__(), help_text=column.columns[j].html)
                i += 1

        return column_headers

    @property
    def group_by(self):
        if self.config['table_card_group_by'] == 'group_name':
            return ['group_name', 'value_chain', 'domains', 'practices']
        else:
            return ['gender', 'value_chain', 'domains', 'practices']



class TableCardReportGrouppedPercentSqlData(TableCardSqlData):
    slug = 'groupped'
    show_total = False
    datatables = True
    title = ''
    fix_left_col = False
    show_charts = True
    chart_x_label = ''
    chart_y_label = 'Percentages'

    def headers(self, data):
        headers = DataTablesHeader(*[DataTablesColumnGroup('Domain', DataTablesColumn('Practice')),])
        for column in super(TableCardReportGrouppedPercentSqlData, self).headers(data):
            headers.add_column(column)
        return headers

    def format_rows(self, rows):
        formatter = TableCardDataIndividualFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        formatted_rows = formatter.format(rows, keys=self.keys, group_by=self.group_by, domain=self.domain)
        formatter = TableCardDataGroupsFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        return formatter.format(list(formatted_rows), keys=self.keys, group_by=self.group_by)


class TableCardReportIndividualPercentSqlData(TableCardSqlData):
    slug = 'individual'
    title = ''
    show_total = True
    datatables = True
    fix_left_col = True
    show_charts = False

    def format_cell_fn(self, x, y):
        sum_all = (x or 0) + (y or 0)
        percentage = 100 * int(x or 0) / float(sum_all or 1)
        text = "%d/%d (%.2f%%)" % ((x or 0), sum_all, percentage)

        def _get_color(value):
            if 76 <= value <= 100:
                return 'green'
            elif 51 <= value <= 75:
                return 'orange'
            elif 26 <= value <= 51:
                return 'yellow'
            else:
                return 'red'

        return '<span style="display: block; text-align:center;padding:10px;background-color:%s">%s</span>' % (_get_color(percentage), text)

    def headers(self, data):
        headers = DataTablesHeader(*[DataTablesColumnGroup('Domain', DataTablesColumn('Practice')),
                                     DataTablesColumnGroup('Total', DataTablesColumn('Total')),])
        for column in super(TableCardReportIndividualPercentSqlData, self).headers(data):
            headers.add_column(column)
        return headers

    def format_rows(self, rows):
        formatter = TableCardDataIndividualFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        return formatter.format(rows, keys=self.keys, group_by=self.group_by, domain=self.domain)

    def calculate_total_row(self, headers, rows):
        total_row = ['Total']
        for header in range(1, headers.__len__()):
            total_row.append('0/0')

        def _calc_totals(row, idx):
            TAG_RE = re.compile(r'<[^>]+>')
            def remove_tags(text):
                return TAG_RE.sub('', text)

            if 'html' in row:
                row = remove_tags(row['html'])

            init_values = map(int, re.findall(r'\d+', total_row[idx]))
            new_values = map(int, re.findall(r'\d+', row))

            init_values[0] += new_values[0]
            init_values[1] += new_values[1]

            percentage = 100 * int(init_values[0] or 0) / float(init_values[1] or 1)
            text = "%d/%d (%.2f%%)" % ((init_values[0] or 0), init_values[1], percentage)

            total_row[idx] = text

        for row in rows:
            for idx, practice in enumerate(row[1:], 1):
                _calc_totals(practice, idx)

        return total_row
