from django.utils.translation import ugettext_lazy
from corehq.apps.reports.filters.select import MonthFilter
from corehq.apps.userreports.sql import get_table_name
from dimagi.utils.decorators.memoized import memoized
from sqlagg.columns import SimpleColumn
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.standard import DatespanMixin


class HierarchySqlData(SqlData):
    @property
    def table_name(self):
        return get_table_name(self.config['domain'], 'location_hierarchy')

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return ['doc_id']

    @property
    def columns(self):
        return [
            DatabaseColumn('block', SimpleColumn('block')),
            DatabaseColumn('district', SimpleColumn('district')),
            DatabaseColumn('first_name', SimpleColumn('first_name')),
            DatabaseColumn('last_name', SimpleColumn('last_name')),
            DatabaseColumn('user_id', SimpleColumn('doc_id'))
        ]


class DrillDownOptionFilter(BaseDrilldownOptionFilter):
    label = ugettext_lazy("Hierarchy")
    slug = "hierarchy"

    @property
    def filter_context(self):
        controls = []
        for level, label in enumerate(self.rendered_labels):
            controls.append({
                'label': label[0],
                'slug': label[1],
                'level': level,
            })

        return {
            'option_map': self.drilldown_map,
            'controls': controls,
            'selected': self.selected,
            'use_last': self.use_only_last,
            'notifications': self.final_notifications,
            'empty_text': self.drilldown_empty_text,
            'is_empty': not self.drilldown_map
        }

    @classmethod
    def get_labels(cls):
        return [('District', 'district'), ('Block', 'block'), ('AF', 'af')]

    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[1])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[1])))
        return {
            'slug': slug,
            'value': val,
        }

    @property
    @memoized
    def drilldown_map(self):
        def make_drilldown(hierarchy):
            hierarchy = [{
                "val": current[0] if isinstance(current, tuple) else current,
                "text": current[1] if isinstance(current, tuple) else current,
                "next": make_drilldown(next_level) if next_level else []
            } for current, next_level in hierarchy.items()]

            return sorted(hierarchy, key=lambda r: r['text'])

        return make_drilldown(self.get_hierarchy())

    @property
    def data_source(self):
        return HierarchySqlData

    def get_hierarchy(self):
        hierarchy = {}
        for location in self.data_source(config={'domain': self.domain}).get_data():
            district = location['district']
            block = location['block']
            user = (u"%s %s" % (location['first_name'] or '', location['last_name'] or '')).strip()
            user_id = location['doc_id']
            if not (district and block and user):
                continue
            hierarchy[district] = hierarchy.get(district, {})
            hierarchy[district][block] = hierarchy[district].get(block, {})
            hierarchy[district][block][(user_id, user)] = None
        return hierarchy


class SampleFormatFilter(BaseSingleOptionFilter):
    slug = 'sf'
    label = ugettext_lazy('Report type')
    default_text = "Format-1 for ASHA Sanginis"

    @property
    def options(self):
        return [
            ('sf2', 'Format-2 Consolidation of the Functionality numbers'),
            ('sf3', 'Format-3 Block Consolidation of the functionality status'),
            ('sf4', 'Format-4 Block Consolidation of the functionality status'),
            ('sf5', 'Format-5 Functionality of ASHAs in blocks')
        ]


class ASHAMonthFilter(MonthFilter):
    label = ugettext_lazy("Last Reporting month of the quarter")


class NRHMDatespanFilter(DatespanFilter):
    template = "up_nrhm/datespan.html"


class NRHMDatespanMixin(DatespanMixin):
    datespan_field = NRHMDatespanFilter
