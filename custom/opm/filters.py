from custom.common import ALL_OPTION

from django.utils.translation import ugettext_noop, ugettext as _
from sqlagg.columns import SimpleColumn

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.reports.filters.select import SelectOpenCloseFilter
from corehq.apps.reports.filters.base import (BaseSingleOptionFilter,
                                              BaseDrilldownOptionFilter)
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


class UserSqlData(SqlData):
    table_name = "fluff_OpmUserFluff"
    group_by = ['doc_id', 'awc', 'awc_code', 'gp', 'block']

    @property
    def filters(self):
        return []

    @property
    def columns(self):
        return [
            DatabaseColumn('doc_id', SimpleColumn('doc_id')),
            DatabaseColumn('awc', SimpleColumn('awc')),
            DatabaseColumn('awc_code', SimpleColumn('awc_code')),
            DatabaseColumn('gp', SimpleColumn('gp')),
            DatabaseColumn('block', SimpleColumn('block')),
        ]


def get_hierarchy():
    """
    Creates a location hierarchy structured as follows:
    hierarchy = {"Atri": {
                    "Sahora": {
                        "Sohran Bigha": None}}}
    """
    hierarchy = {}
    for location in HierarchySqlData().get_data():
        block = location['block']
        gp = location['gp']
        awc = location['awc']
        if not (awc and gp and block):
            continue
        hierarchy[block] = hierarchy.get(block, {})
        hierarchy[block][gp] = hierarchy[block].get(gp, {})
        hierarchy[block][gp][awc] = None
    return hierarchy


def user_data_as_hierarchy():
    """
    Creates a location hierarchy structured as follows:
    hierarchy = {"Atri": {
                    "Sahora": {
                        "<doc_id of awc>": None}}}
    """
    hierarchy = {}
    for location in UserSqlData().get_data():
        block = location['block']
        gp = location['gp']
        awc = location['doc_id']
        if not (awc and gp and block):
            continue
        hierarchy[block] = hierarchy.get(block, {})
        hierarchy[block][gp] = hierarchy[block].get(gp, {})
        hierarchy[block][gp][awc] = None
    return hierarchy


def user_data_by_id():
    """
    Creates user-id -> awc-info dict
    data = {
        '<owner_id>': {
            'awc_name': awc_name,
            'gp': gp,
            'block': block,
            'awc_code': awc_code,
        }
        ...
    }
    """
    data = {}
    for location in UserSqlData().get_data():
        block = location['block']
        gp = location['gp']
        owner_id = location['doc_id']
        awc_name = location['awc']
        awc_code = location['awc_code']
        data[owner_id] = {
            'awc_name': awc_name,
            'gp': gp,
            'block': block,
            'awc_code': awc_code,
        }
    return data


class OpmBaseDrilldownOptionFilter(BaseDrilldownOptionFilter):
    single_option_select = -1
    template = "common/drilldown_options.html"

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
        return make_drilldown(get_hierarchy())

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
    label = ugettext_noop("Hierarchy")
    slug = "hierarchy"

    @property
    def selected(self):
        selected = super(OpmBaseDrilldownOptionFilter, self).selected
        if selected:
            return selected
        return [[ALL_OPTION]]


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


class SelectBlockFilter(BaseSingleOptionFilter):
    slug = "block"
    label = "Block"
    default_text = None

    @property
    def options(self):
        return [('Atri', 'Atri'), ('Wazirganj', 'Wazirganj')]


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
