from django.utils.translation import ugettext_noop
from dimagi.utils.decorators.memoized import memoized
from sqlagg.columns import SimpleColumn
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn


class HierarchySqlData(SqlData):
    table_name = "fluff_UpNRHMLocationHierarchyFluff"

    @property
    def filters(self):
        return []

    @property
    def group_by(self):
        return ['block', 'district', 'username', 'user_id']

    @property
    def columns(self):
        return [
            DatabaseColumn('block', SimpleColumn('block')),
            DatabaseColumn('district', SimpleColumn('district')),
            DatabaseColumn('username', SimpleColumn('username')),
            DatabaseColumn('user_id', SimpleColumn('user_id'))
        ]


class DrillDownOptionFilter(BaseDrilldownOptionFilter):
    label = ugettext_noop("Hierarchy")
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
            return [{
                "val": current[0] if isinstance(current, tuple) else current,
                "text": current[1] if isinstance(current, tuple) else current,
                "next": make_drilldown(next_level) if next_level else []
            } for current, next_level in hierarchy.items()]
        return make_drilldown(self.get_hierarchy())

    def get_hierarchy(self):
        hierarchy = {}
        for location in HierarchySqlData().get_data():
            district = location['district']
            block = location['block']
            user = location['username']
            user_id = location['user_id']
            if not (district and block and user):
                continue
            hierarchy[district] = hierarchy.get(district, {})
            hierarchy[district][block] = hierarchy[district].get(block, {})
            hierarchy[district][block][(user_id, user)] = None
        return hierarchy
