from django.utils.translation import ugettext_noop
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter
from corehq.apps.reports.filters.dates import DatespanFilter
from custom.world_vision.sqldata import LocationSqlData, LOCATION_HIERARCHY


class LocationFilter(BaseDrilldownOptionFilter):
    label = ugettext_noop("Location")
    slug = "location"
    template = "world_vision/location_filter.html"

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
                    if not hierarchy:
                        hierarchy.append(dict(val=0, text='All', next=[]))
                    hierarchy.append(tmp)
                    hierarchy = tmp['next']
                else:
                    hierarchy = tmp_next
            hierarchy = helper

        return hierarchy

    def get_labels(self):
        return [(v['name'], v['prop']) for k,v in sorted(LOCATION_HIERARCHY.iteritems())]

    @property
    def filter_context(self):
        controls = []
        for level, label in enumerate(self.rendered_labels):
            controls.append({
                'label': label[0],
                'slug': label[1],
                'level': level,
            })

        drilldown_map = list(self.drilldown_map)
        return {
            'option_map': drilldown_map,
            'controls': controls,
            'selected': self.selected,
            'use_last': self.use_only_last,
            'notifications': self.final_notifications,
            'empty_text': self.drilldown_empty_text,
            'is_empty': not drilldown_map,
        }

    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[1])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[1])))
        return {
            'slug': slug,
            'value': val,
        }


class WVDatespanFilter(DatespanFilter):

    template = "world_vision/datespan.html"
    css_class = 'col-md-4'

    @property
    def datespan(self):
        if not self.request.datespan.is_default:
            startdate = self.request.GET['startdate']
            enddate = self.request.GET['enddate']

            return {'startdate': startdate, 'enddate': enddate}
        else:
            return None