from sqlagg.columns import SimpleColumn
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn


class GeographySqlData(SqlData):
    table_name = "fluff_GeographyFluff"

    def __init__(self, domain, level=None, name=None, selected_id=None):
        self.domain = domain
        if selected_id:
            self.level, self.name = selected_id.split('__') if selected_id else (None, None)
            self.selected_id = True
        else:
            self.level = level
            self.name = name
            self.selected_id = False

    @property
    def filter_values(self):
        dict = {}
        if self.domain:
            dict[u'domain'] = self.domain
        if self.level and self.name:
            dict[self.level] = self.name

        return dict

    @property
    def filters(self):
        filters = []
        if self.domain:
            filters.append(u'domain = :domain')
        if self.level and self.name:
            filters.append(self.level + u'= :' + self.level)

        return filters

    @property
    def group_by(self):
        if self.selected_id:
            group = []
            for k in keys:
                if k <= self.level:
                    group.append(k)
            return group

        return [u'lvl_' + unicode(int(self.level[-1]) + 1)] if self.level else [u'lvl_1']

    @property
    def columns(self):
        if self.selected_id:
            columns = []
            for k in keys:
                if k <= self.level:
                    columns.append(DatabaseColumn(k, SimpleColumn(k)))
            return columns

        if self.level:
            next_level = u'lvl_' + unicode(int(self.level[-1]) + 1)
            return [DatabaseColumn(next_level, SimpleColumn(next_level))]

        return [DatabaseColumn(u'lvl_1', SimpleColumn(u'lvl_1'))]

    def get_result(self, path):
        path = path.values()[0]
        result = []
        reversed_keys = keys[::-1]
        deepest_child = True
        for k in reversed_keys:
            if path.has_key(k):
                if deepest_child:
                    deepest_child = False
                    result = GeographySqlData(self.domain, level=k, name=path[k]).data.values()
                if self.level != u'lvl_5':
                    previous_level = u'lvl_' + unicode(int(k[-1]) - 1)
                    if previous_level == u'lvl_0':
                        temp_result = GeographySqlData(self.domain).data.values()
                    else:
                        temp_result = GeographySqlData(self.domain, level=previous_level, name=path[previous_level]).data.values()
                    index = [i for i, item in enumerate(temp_result) if item[u'name']==path[k]][0]
                    temp_result[index][u'children'] = result
                    result = temp_result

        return result

    @property
    def data(self):
        result = super(GeographySqlData, self).data
        for v in result.values():
            for k in keys:
                if k in v:
                    v[u'name'] = v[k]
                    v[u'uuid'] = k+'__'+v[k]
        if self.selected_id:
            return self.get_result(result)
        return dict((k, v) for k, v in result.iteritems() if v)

keys = [u'lvl_1', u'lvl_2', u'lvl_3', u'lvl_4', u'lvl_5']
