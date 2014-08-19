from sqlagg.base import AliasColumn, QueryMeta, CustomQueryColumn
from sqlagg.columns import SimpleColumn
from sqlagg.filters import *
from sqlalchemy.sql.expression import join, alias
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, AggregateColumn
from custom.care_pathways.utils import get_domain_configuration, is_mapping, get_mapping, is_domain, is_practice, get_pracices, get_domains
from sqlalchemy import select
import urllib
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
        result = connection.execute(self._build_query(filter_values)).fetchall()
        #debug
        print result
        return result

    def _build_query(self, filter_values):
        having = []
        filter_cols = []
        external_cols = _get_grouping(filter_values)
        # print filter_values
        for k, v in filter_values.iteritems():
            if v and k not in ['group', 'gender', 'group_leadership']:
                if isinstance(v, tuple):
                    if len(v) == 1:
                        having.append("%s = \'%s\'" % (k, v[0]))
                    else:
                        having.append("%s IN %s" % (k, tuple(["%s" % str(x) for x in v])))
                else:
                    having.append("%s = \'%s\'" % (k, v))
                if k not in external_cols:
                    filter_cols.append(k)
        group_having = ''
        having_group_by = []
        if 'group_leadership' in filter_values and filter_values['group_leadership']:
            group_having = "(MAX(CAST(gender as int4)) + MIN(CAST(gender as int4))) = %s and group_leadership=\'Y\'" % filter_values['group_leadership']
            having_group_by.append('group_leadership')
            filter_cols.append('group_leadership')
        elif 'gender' in filter_values and filter_values['gender']:
            group_having = "(MAX(CAST(gender as int4)) + MIN(CAST(gender as int4))) = %s" % filter_values['gender']

        for fil in self.filters:
            having.append("%s %s %s" % (fil.column_name, fil.operator, fil.parameter))


        s1 = alias(select(['doc_id', 'group_id', 'MAX(prop_value) + MIN(prop_value) as maxmin'] + filter_cols + external_cols,
                                from_obj='"fluff_FarmerRecordFluff"',
                                group_by=['doc_id', 'group_id'] + filter_cols + external_cols), name='x')
        s2 = alias(select(['group_id', '(MAX(CAST(gender as int4)) + MIN(CAST(gender as int4))) as maxmingender'], from_obj='"fluff_FarmerRecordFluff"',
                                group_by=['group_id'] + having_group_by, having=group_having), name='y')
        return select(['COUNT(x.doc_id) as %s' % self.key] + external_cols,
               group_by=['maxmin'] + filter_cols + external_cols,
               having=" and ".join(having),
               from_obj=join(s1, s2, s1.c.group_id==s2.c.group_id))


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
        super(GeographySqlData, self).__init__()

    @property
    def filters(self):
        return []

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
                            [CareCustomColumn('all', filters=[EQ("x.maxmin", 2),]), AliasColumn('some'), AliasColumn('none')]),
            AggregateColumn('Some', self.percent_fn,
                            [CareCustomColumn('some', filters=[EQ("x.maxmin", 1),]), AliasColumn('all'), AliasColumn('none')]),
            AggregateColumn('None', self.percent_fn,
                            [CareCustomColumn('none', filters=[EQ("x.maxmin", 0),]), AliasColumn('all'), AliasColumn('some')])
        ]

    @property
    def filters(self):
        filters = [EQ("ppt_year", "ppt_year")]
        for k, v in self.geography_config.iteritems():
            if v['prop'] in self.config and self.config[v['prop']]:
                filters.append(IN(k, v['prop']))
        if 'value_chain' in self.config and self.config['value_chain']:
            filters.append(EQ("value_chain", "value_chain"))
        if 'domains' in self.config and self.config['domains']:
            filters.append(IN("domains", "domains"))
        if 'practices' in self.config and self.config['practices']:
            filters.append(IN("practices", "practices"))
        if 'group_leadership' in self.config and self.config['group_leadership']:
            filters.append(EQ('group_leadership', 'group_leadership'))
        if 'cbt_name' in self.config and self.config['cbt_name']:
            filters.append(EQ('owner_id', 'cbt_name'))
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
    def group_by(self):
        return _get_grouping(self.config)


class AdoptionDisaggregatedSqlData(CareSqlData):

    @property
    def group_by(self):
        return _get_grouping(self.config)
