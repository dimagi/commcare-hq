from sqlagg.columns import SimpleColumn
from corehq.apps.reports.filters.base import (
    BaseSingleOptionFilter, CheckboxFilter, BaseDrilldownOptionFilter)

from django.utils.translation import ugettext_noop
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn


class HierarchySqlData(SqlData):
    table_name = "fluff_OPMHierarchyFluff"

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return ['block', 'gp', 'awc']

    @property
    def columns(self):
        return [
            DatabaseColumn('Block', SimpleColumn('block')),
            DatabaseColumn('Gram Panchayat', SimpleColumn('gp')),
            DatabaseColumn('AWC', SimpleColumn('awc'))
        ]

class OpmBaseDrilldownOptionFilter(BaseDrilldownOptionFilter):
    single_option_select = -1
    template = "opm/drilldown_options.html"

    @property
    def filter_context(self):
        context = super(OpmBaseDrilldownOptionFilter, self).filter_context
        context.update({'single_option_select': self.single_option_select})
        return context

    hierarchy_config = {
        'lvl_1': {
            'prop': 'block',
            'name': 'Block'
        },
        'lvl_2': {
            'prop': 'gp',
            'name': 'Gram Panchayat'
        },
        'lvl_3': {
            'prop': 'awc',
            'name': 'AWC'
        }
    }

    @property
    def drilldown_map(self):
        hierarchy = helper = []
        data = HierarchySqlData().get_data()
        for val in data:
            for lvl in ['block', 'gp', 'awc']:
                tmp = dict(val=val[lvl], text=val[lvl], next=[])
                tmp_next = []
                exist = False
                for item in hierarchy:
                    if item['val'] == val[lvl]:
                        exist = True
                        tmp_next = item['next']
                        break
                if not exist:
                    hierarchy.append(tmp)
                    hierarchy = tmp['next']
                else:
                    hierarchy = tmp_next
            hierarchy = helper
        return hierarchy

    @classmethod
    def get_labels(cls):
        return [('Block', 'All', 'block'), ('Gram Panchayat', 'All', 'gp'), ('AWC', 'All', 'awc')]


    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[2])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[2])))
        return {
            'slug': slug,
            'value': val,
        }


class HierarchyFilter(OpmBaseDrilldownOptionFilter):
    label = ugettext_noop("Hierarchy")
    slug = "hierarchy"



class MetHierarchyFilter(OpmBaseDrilldownOptionFilter):
    single_option_select = 0
    label = ugettext_noop("Hierarchy")
    slug = "hierarchy"

    @classmethod
    def get_labels(cls):
        return [('Block', '', 'block'), ('Gram Panchayat', 'All', 'gp'), ('AWC', 'All', 'awc')]

    @property
    def drilldown_map(self):
        hierarchy = super(MetHierarchyFilter, self).drilldown_map
        met_hierarchy = [x for x in hierarchy if x['val'].lower() in ['atri', 'wazirganj']]
        return met_hierarchy

class SelectBlockFilter(BaseSingleOptionFilter):
    slug = "block"
    label = "Block"
    default_text = None

    @property
    def options(self):
        return [('Atri', 'Atri'), ('Wazirganj', 'Wazirganj')]
