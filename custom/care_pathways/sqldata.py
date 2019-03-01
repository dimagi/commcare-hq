from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import sqlalchemy
from sqlagg.base import AliasColumn, QueryMeta, CustomQueryColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import EQ, NOTEQ, AND, IN, RawFilter, ANDFilter
from sqlalchemy.sql.expression import join, alias, cast
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.sqltypes import Integer, VARCHAR

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, AggregateColumn, TableDataFormat
from corehq.apps.reports.util import get_INFilter_bindparams
from custom.care_pathways.utils import get_domain_configuration, is_mapping, get_mapping, is_domain, is_practice, get_pracices, get_domains, TableCardDataIndividualFormatter, TableCardDataGroupsFormatter, \
    get_domains_with_next, TableCardDataGroupsIndividualFormatter
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
import re
from django.utils import html
from custom.utils.utils import clean_IN_filter_value
from six.moves import range
from six.moves import map
import six


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

    def __init__(self, table_name, filters, group_by, order_by, key):
        self.key = key
        super(CareQueryMeta, self).__init__(table_name, filters, group_by, order_by)

    def execute(self, connection, filter_values):
        return connection.execute(self._build_query(filter_values)).fetchall()

    def _build_query(self, filter_values):
        having = []
        filter_cols = []
        external_cols = _get_grouping(filter_values)

        for fil in self.filters:
            if isinstance(fil, ANDFilter):
                filter_cols.append(fil.filters[0].column_name)
                having.append(fil)
            elif isinstance(fil, RawFilter):
                having.append(fil)
            elif fil.column_name not in ['group', 'gender', 'group_leadership', 'disaggregate_by',
                                         'table_card_group_by']:
                if fil.column_name not in external_cols and fil.column_name != 'maxmin':
                    filter_cols.append(fil.column_name)
                having.append(fil)

        group_having = ''
        having_group_by = []
        if ('disaggregate_by' in filter_values and filter_values['disaggregate_by'] == 'group') or \
                (filter_values.get('table_card_group_by') == 'group_leadership'):
            having_group_by.append('group_leadership')
        elif 'group_leadership' in filter_values and filter_values['group_leadership']:
            group_having = "(MAX(CAST(gender as int4)) + MIN(CAST(gender as int4))) " \
                           "= :group_leadership and group_leadership=\'Y\'"
            having_group_by.append('group_leadership')
            filter_cols.append('group_leadership')
        elif 'gender' in filter_values and filter_values['gender']:
            group_having = "(MAX(CAST(gender as int4)) + MIN(CAST(gender as int4))) = :gender"

        table_card_group = []
        if 'group_name' in self.group_by:
            table_card_group.append('group_name')
        s1 = alias(
            sqlalchemy.select(
                [
                    sqlalchemy.column('doc_id'),
                    sqlalchemy.column('group_case_id'),
                    sqlalchemy.column('group_name'),
                    sqlalchemy.column('group_id'),
                    (sqlalchemy.func.max(sqlalchemy.column('prop_value')) + sqlalchemy.func.min(sqlalchemy.column('prop_value'))).label('maxmin')
                ] + filter_cols + external_cols,
                group_by=(
                    [
                        sqlalchemy.column('doc_id'), sqlalchemy.column('group_case_id'),
                        sqlalchemy.column('group_name'), sqlalchemy.column('group_id')
                    ] + filter_cols + external_cols)
            ).select_from(sqlalchemy.table(self.table_name)),
            name='x'
        )
        s2 = alias(
            sqlalchemy.select(
                [
                    sqlalchemy.column('group_case_id'),
                    sqlalchemy.cast(
                        cast(func.max(sqlalchemy.column('gender')), Integer) + cast(func.min(sqlalchemy.column('gender')), Integer), VARCHAR
                    ).label('gender')
                ] + table_card_group,
                group_by=[sqlalchemy.column('group_case_id')] + table_card_group + having_group_by, having=group_having
            ).select_from(sqlalchemy.table(self.table_name)),
            name='y'
        )
        group_by = list(self.group_by)
        if 'group_case_id' in group_by:
            group_by[group_by.index('group_case_id')] = s1.c.group_case_id
            group_by[group_by.index('group_name')] = s1.c.group_name
        return sqlalchemy.select(
            [sqlalchemy.func.count(s1.c.doc_id).label(self.key)] + group_by,
            group_by=[s1.c.maxmin] + filter_cols + group_by,
            having=AND(having).build_expression(),
            from_obj=join(s1, s2, s1.c.group_case_id == s2.c.group_case_id)
        ).params(filter_values)


class CareCustomColumn(CustomQueryColumn):
    query_cls = CareQueryMeta
    name = 'custom_care'

    def get_query_meta(self, default_table_name, default_filters, default_group_by, default_order_by):
        table_name = self.table_name or default_table_name
        filters = self.filters or default_filters
        group_by = self.group_by or default_group_by
        order_by = self.order_by or default_order_by
        return self.query_cls(table_name, filters, group_by, order_by, self.key)


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


class IEQ(EQ):
    def build_expression(self):
        return self.operator(
            func.lower(sqlalchemy.column(self.column_name)), func.lower(sqlalchemy.bindparam(self.parameter))
        )


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
        for k, v in six.iteritems(self.geography_config):
            if k in self.config and self.config[k]:
                filters.append(IN(k, get_INFilter_bindparams(k, self.config[k])))
        if 'value_chain' in self.config and self.config['value_chain']:
            filters.append(EQ("value_chain", "value_chain"))
        if 'group_leadership' in self.config and self.config['group_leadership']:
            filters.append(EQ('group_leadership', 'group_leadership'))
        if 'cbt_name' in self.config and self.config['cbt_name']:
            filters.append(IN('owner_id', get_INFilter_bindparams('cbt_name', self.config['cbt_name'])))
        if 'real_or_test' in self.config and self.config['real_or_test']:
            filters.append(IEQ('real_or_test', 'real_or_test'))
        for column_name in ['domains', 'practices', 'schedule']:
            if column_name in self.config and self.config[column_name] and self.config[column_name] != ('0',):
                filters.append(IN(column_name, get_INFilter_bindparams(column_name, self.config[column_name])))
        return filters

    @property
    def filter_values(self):
        filter_values = dict(**super(CareSqlData, self).filter_values)

        for column_name in list(self.geography_config.keys()) + ['domains', 'practices', 'schedule', 'cbt_name']:
            clean_IN_filter_value(filter_values, column_name)
        return filter_values

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
        url = html.escape(AdoptionBarChartReport.get_url(*[self.domain]) + "?" + six.moves.urllib.parse.urlencode(self.request_params))
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

        columns = [
            DatabaseColumn('', SimpleColumn(first_columns), self.group_name_fn),
            AggregateColumn(
                'Farmers who adopted All practices', self.percent_fn,
                [
                    CareCustomColumn('all', filters=self.filters + [RawFilter("maxmin = 2")]),
                    AliasColumn('some'),
                    AliasColumn('none')
                ]
            )
        ]

        if group != 'practice':
            columns.append(AggregateColumn(
                'Farmers who adopted Some practices', self.percent_fn,
                [
                    CareCustomColumn('some', filters=self.filters + [RawFilter("maxmin = 1")]),
                    AliasColumn('all'),
                    AliasColumn('none')
                ]
            ))

        columns.append(AggregateColumn(
            'Farmers who adopted No practices', self.percent_fn,
            [
                CareCustomColumn('none', filters=self.filters + [RawFilter("maxmin = 0")]),
                AliasColumn('all'),
                AliasColumn('some')
            ]
        ))

        return columns

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
        disaggregate_by = self.config['disaggregate_by']
        disaggregation_type = 'Groups'
        if disaggregate_by == 'group':
            disaggregation_type = 'Leadership'

        if value == '0':
            display = {'sort_key': 0, 'html': 'All Male %s' % disaggregation_type}
        elif value == '1':
            display = {'sort_key': 0, 'html': 'Mixed %s' % disaggregation_type}
        elif value == '2':
            display = {'sort_key': 0, 'html': 'All Female %s' % disaggregation_type}

        return display

    @property
    def columns(self):
        columns = [
            DatabaseColumn('', AliasColumn('gender'), format_fn=self._to_display),
            AggregateColumn('Farmers who adopted No practices', lambda x: x,
                            [CareCustomColumn('none', filters=self.filters + [RawFilter("maxmin = 0")])])
        ]

        if self.config['group'] != 'practice':
            columns.append(
                AggregateColumn('Farmers who adopted Some practices', lambda x: x,
                                [CareCustomColumn('some', filters=self.filters + [RawFilter("maxmin = 1")])]))

        columns.append(AggregateColumn('Farmers who adopted All practices', lambda x: x,
                       [CareCustomColumn('all', filters=self.filters + [RawFilter("maxmin = 2")])]))
        return columns


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
            group_by = 'Groups'
            if self.config['table_card_group_by'] == 'group_leadership':
                group_by = 'Leadership'

            if int(x) == 0:
                return 'All Male %s' % group_by
            elif int(x) == 1:
                return 'Mixed %s' % group_by
            elif int(x) == 2:
                return 'All Female %s' % group_by

    @property
    def formatter(self):
        if self.config['table_card_group_by'] == 'group_name':
            return TableCardDataGroupsIndividualFormatter(TableDataFormat(self.columns, no_value=self.no_value))
        else:
            return TableCardDataIndividualFormatter(TableDataFormat(self.columns, no_value=self.no_value))

    @property
    def columns(self):
        if self.config['table_card_group_by'] == 'group_name':
            first_column = 'group_name'
        else:
            first_column = 'gender'

        return [
            DatabaseColumn('', SimpleColumn(first_column), format_fn=self.first_column_format),
            AggregateColumn('practice_count', self.format_cell_fn,
                            [CareCustomColumn('all', filters=self.filters + [RawFilter("maxmin = 2")]),
                             CareCustomColumn('none', filters=self.filters + [RawFilter("maxmin = 0")])]),
        ]

    @property
    def domains_with_practices(self):
        practices = self.config.get('practices')
        domains = self.config.get('domains')

        return [
            {
                'text': element.text,
                'practices': [
                    practice for practice in element.next
                    if not practices or practices[0] == '0' or practice.val in practices
                ]
            }
            for element in get_domains_with_next(self.domain, value_chain=self.config['value_chain'])
            if not domains or domains[0] == '0' or element.val in domains
        ]

    @property
    def flat_practices(self):
        for domain_with_practices in self.domains_with_practices:
            for practice in domain_with_practices['practices']:
                yield practice

    def headers(self, data):
        column_headers = []
        i = 1
        for domain in self.domains_with_practices:
            domain_group = DataTablesColumnGroup(domain['text'])
            for practice in domain['practices']:
                domain_group.add_column(DataTablesColumn('Practice %i' % i, help_text=practice.text))
                i += 1
            column_headers.append(domain_group)
        return column_headers

    @property
    def group_by(self):
        if self.config['table_card_group_by'] == 'group_name':
            return ['group_case_id', 'group_name', 'group_id', 'value_chain', 'domains', 'practices']
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
        formatter = self.formatter
        formatted_rows = formatter.format(rows, keys=self.keys, group_by=self.config['table_card_group_by'],
                                          domain=self.domain, practices=list(self.flat_practices))
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
            elif 51 <= value < 76:
                return 'orange'
            elif 26 <= value < 51:
                return 'yellow'
            elif 0 <= value < 26:
                return 'red'
            else:
                return ''

        span = '<span style="display: block; text-align:center;padding:10px;background-color:%s">%s</span>'
        return span % (_get_color(percentage), text)

    def _na_format(self, value):
        span = '<span style="display: block; text-align:center;padding:10px;background-color:grey">%s</span>'
        return span % value

    def headers(self, data):
        headers = DataTablesHeader(
            DataTablesColumnGroup('Domain', DataTablesColumn('Practice')),
            DataTablesColumnGroup('Total', DataTablesColumn('Total'))
        )
        for column in super(TableCardReportIndividualPercentSqlData, self).headers(data):
            headers.add_column(column)
        return headers

    def format_rows(self, rows):
        formatter = self.formatter
        formatted = list(formatter.format(rows, keys=self.keys, group_by=self.config['table_card_group_by'],
                                          domain=self.domain, practices=list(self.flat_practices)))
        for row in formatted:
            for el in row:
                if el['sort_key'] == 'N/A':
                    el['html'] = self._na_format(el['sort_key'])
        return formatted

    def calculate_total_row(self, headers, rows):
        total_row = ['Total']
        for header in range(1, len(headers)):
            total_row.append({'sort_key': '0/0', 'html': '0/0'})

        def _calc_totals(row, idx):
            TAG_RE = re.compile(r'<[^>]+>')

            def remove_tags(text):
                return TAG_RE.sub('', text)

            if 'html' in row:
                row = remove_tags(row['html'])

            init_values = list(map(int, re.findall(r'\d+', total_row[idx]['html'])))
            new_values = list(map(int, re.findall(r'\d+', row)))

            init_values[0] += new_values[0]
            init_values[1] += new_values[1]

            percentage = 100 * int(init_values[0] or 0) / float(init_values[1] or 1)
            text = "%d/%d (%.2f%%)" % ((init_values[0] or 0), init_values[1], percentage)

            total_row[idx] = {'html': text, 'sort_key': text}

        for row in rows:
            for idx, practice in enumerate(row[1:], 1):
                if 'sort_key' in practice and practice['sort_key'] == 'N/A':
                    continue
                _calc_totals(practice, idx)
        return total_row
