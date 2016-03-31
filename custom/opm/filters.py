from custom.common import ALL_OPTION

from django.utils.translation import ugettext_noop, ugettext as _

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.reports.filters.select import SelectOpenCloseFilter
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter
from .utils import user_sql_data


class OpmBaseDrilldownOptionFilter(BaseDrilldownOptionFilter):
    single_option_select = -1
    template = "common/bootstrap2/drilldown_options.html"

    @property
    def selected(self):
        selected = super(OpmBaseDrilldownOptionFilter, self).selected
        if selected:
            return selected
        return [["Atri"], [ALL_OPTION]]

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
            'is_empty': not self.drilldown_map,
            'single_option_select': self.single_option_select
        }

    @property
    @memoized
    def drilldown_map(self):
        def make_drilldown(hierarchy):
            return [{"val": ALL_OPTION, "text": "All", "next": []}] + [{
                "val": current,
                "text": current,
                "next": make_drilldown(next_level) if next_level else []
            } for current, next_level in hierarchy.items()]
        return make_drilldown(user_sql_data().data_as_hierarchy())

    @classmethod
    def get_labels(cls):
        return [('Block', 'block'), ('Gram Panchayat', 'gp'), ('AWC', 'awc')]

    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[1])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[1])))
        return {
            'slug': slug,
            'value': val,
        }


class HierarchyFilter(OpmBaseDrilldownOptionFilter):
    single_option_select = 0
    label = ugettext_noop("Hierarchy")
    slug = "hierarchy"

    @property
    def drilldown_map(self):
        hierarchy = super(HierarchyFilter, self).drilldown_map
        all_hierarchy = [x for x in hierarchy
                         if x['val'].lower() != 'all']
        return all_hierarchy


class MetHierarchyFilter(OpmBaseDrilldownOptionFilter):
    single_option_select = 0
    label = ugettext_noop("Hierarchy")
    slug = "hierarchy"

    @property
    def drilldown_map(self):
        hierarchy = super(MetHierarchyFilter, self).drilldown_map
        met_hierarchy = [x for x in hierarchy
                         if x['val'].lower() in ['atri', 'wazirganj']]
        return met_hierarchy


class OPMSelectOpenCloseFilter(SelectOpenCloseFilter):
    default_text = None

    @property
    def options(self):
        return [
            ('all', _("Show All")),
            ('open', _("Only Open")),
            ('closed', _("Only Closed")),
        ]

    @property
    @memoized
    def selected(self):
        return self.get_value(self.request, self.domain) or "open"

    @classmethod
    def case_status(cls, request_params):
        """
        returns either "all", "open", or "closed"
        """
        return request_params.get(cls.slug) or 'open'
