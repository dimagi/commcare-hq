from django.utils.translation import ugettext_noop
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter
from custom.world_vision.sqldata import LocationSqlData, LOCATION_HIERARCHY


class LocationFilter(BaseDrilldownOptionFilter):
    label = ugettext_noop("Location")
    slug = "location"
    template = "world_vision/location_filter.html"
    single_option_select = -1
    single_option_select_without_default_text = -1

    @property
    def filter_context(self):
        context = super(LocationFilter, self).filter_context
        context.update({'single_option_select': self.single_option_select})
        context.update({'single_option_select_without_default_text': self.single_option_select_without_default_text})
        return context

    @property
    def drilldown_map(self):
        hierarchy = helper = []
        hierarchy_config = sorted([k for k in LOCATION_HIERARCHY.keys()])
        data = LocationSqlData(self.request.domain).get_data()
        for val in data:
            for lvl in hierarchy_config:
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

    def get_labels(self):
        return [(v['name'], 'All', v['prop']) for k,v in sorted(LOCATION_HIERARCHY.iteritems())]

    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[2])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[2])))
        return {
            'slug': slug,
            'value': val,
        }