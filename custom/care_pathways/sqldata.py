from sqlagg.columns import SimpleColumn
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn

KEYS = [u'lvl_1', u'lvl_2', u'lvl_3', u'lvl_4', u'lvl_5']

class GeographySqlData(SqlData):
    table_name = "fluff_GeographyFluff"

    def __init__(self, domain, level=None, name=None, selected_ids=None):
        self.domain = domain
        if selected_ids:
            self.level, self.name = selected_ids[0].split('__') if selected_ids else (None, None)
            self.selected_id = True
        else:
            self.level = level
            self.name = name
            self.selected_id = False

    @property
    def filter_values(self):
        dict = {}
        if self.domain:
            dict['domain'] = self.domain
        if self.level and self.name:
            dict[self.level] = self.name

        return dict

    @property
    def filters(self):
        filters = []
        if self.domain:
            filters.append('domain = :domain')
        if self.level and self.name:
            filters.append(self.level + '= :' + self.level)

        return filters

    @property
    def group_by(self):
        if self.selected_id:
            group = []
            for k in KEYS:
                if k <= self.level:
                    group.append(k)
            return group

        return ['lvl_' + unicode(int(self.level[-1]) + 1)] if self.level else ['lvl_1']

    @property
    def columns(self):
        if self.selected_id:
            columns = []
            for k in KEYS:
                if k <= self.level:
                    columns.append(DatabaseColumn(k, SimpleColumn(k)))
            return columns

        elif self.level:
            next_level = 'lvl_' + unicode(int(self.level[-1]) + 1)
            return [DatabaseColumn(next_level, SimpleColumn(next_level))]

        else:
            return [DatabaseColumn('lvl_1', SimpleColumn('lvl_1'))]

    def get_result(self, path):
        path = path.values()[0]
        result = []
        reversed_keys = KEYS[::-1]
        deepest_child = True
        for k in reversed_keys:
            if path.has_key(k):
                if deepest_child:
                    deepest_child = False
                    result = GeographySqlData(self.domain, level=k, name=path[k]).data.values()
                if self.level != 'lvl_5':
                    previous_level = 'lvl_' + unicode(int(k[-1]) - 1)
                    if previous_level == 'lvl_0':
                        temp_result = GeographySqlData(self.domain).data.values()
                    else:
                        temp_result = GeographySqlData(self.domain, level=previous_level, name=path[previous_level]).data.values()
                    index = [i for i, item in enumerate(temp_result) if item['name']==path[k]][0]
                    temp_result[index]['children'] = result
                    result = temp_result

        return result

    @property
    def data(self):
        result = super(GeographySqlData, self).data
        for v in result.values():
            for k in KEYS:
                if k in v:
                    v['fixture_type'] = k
                    v['name'] = v[k]
                    v['uuid'] = k+'__'+v[k]
                    v['id'] = k+'__'+v[k]
        if self.selected_id:
            return self.get_result(result)
        return dict((k, v) for k, v in result.iteritems() if v)

    @property
    def path(self):
        result = super(GeographySqlData, self).data
        for v in result.values():
            for k in KEYS:
                if k in v:
                    v['uuid'] = k+'__'+v[k]
        return ["lvl_" + str(i+1) + '__' + v for sublist in result.keys() for i, v in enumerate(sublist)]
