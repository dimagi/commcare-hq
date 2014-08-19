from django.utils.translation import ugettext_noop
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter
from corehq.apps.reports.filters.select import YearFilter
from corehq.apps.users.models import CommCareUser
from custom.care_pathways.sqldata import GeographySqlData
from custom.care_pathways.utils import get_domain_configuration


class CareBaseDrilldownOptionFilter(BaseDrilldownOptionFilter):
    single_option_select = -1

    @property
    def filter_context(self):
        context = super(CareBaseDrilldownOptionFilter, self).filter_context
        context.update({'single_option_select': self.single_option_select})
        return context


class GeographyFilter(CareBaseDrilldownOptionFilter):
    label = ugettext_noop("Geography")
    slug = "geography"
    template = "care_pathways/filters/drilldown_options.html"

    @property
    def drilldown_map(self):
        hierarchy = helper = []
        hierarchy_config = sorted([k for k in get_domain_configuration(self.request.domain)['geography_hierarchy'].keys()])
        data = GeographySqlData(self.request.domain).get_data()
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
        return [(v['name'], 'All', v['prop']) for k,v in sorted(get_domain_configuration(self.request.domain)['geography_hierarchy'].iteritems())]

    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[2])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[2])))
        return {
            'slug': slug,
            'value': val,
        }


class GenderFilter(BaseSingleOptionFilter):
    slug = "gender"
    label = "Gender"
    default_text = "Any"

    @property
    def options(self):
        return [('2', 'All Women'), ('1', 'Some Women'), ('0', 'No Women')]


class GroupLeadershipFilter(BaseSingleOptionFilter):
    slug = "group_leadership"
    label = "Group Leadership"
    default_text = "Any"

    @property
    def options(self):
        return [('2', 'All Women'), ('1', 'Some Women'), ('0', 'No Women')]


class CBTNameFilter(BaseSingleOptionFilter):
    slug = 'cbt_name'
    label = ugettext_noop('CBT Name')
    default_text = "All"

    @property
    def options(self):
        return [(user._id, user.username) for user in CommCareUser.by_domain(self.domain)]


class ScheduleFilter(BaseSingleOptionFilter):
    slug = "farmer_social_category"
    label = "Farmer Social Category"

    @property
    def options(self):
        return [('sc', 'SC'), ('st', 'ST'), ('obc', 'OBC'), ('other', 'Other')]

class PPTYearFilter(YearFilter):
    label = "PPT Year"


class TypeFilter(CareBaseDrilldownOptionFilter):
    single_option_select = 0
    label = "Filter by Type"
    slug = "type"
    template = "care_pathways/filters/drilldown_options.html"

    @property
    def drilldown_map(self):
        hierarchy_config = get_domain_configuration(self.request.domain)['by_type_hierarchy']
        return hierarchy_config

    @classmethod
    def get_labels(cls):
        return [
                ('Value Chain', 'Any', 'value_chain'),
                ('Domain', '', 'domain'),
                ('Practice', '', 'practice')
        ]


    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[2])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[2])))
        return {
            'slug': slug,
            'value': val,
        }

class GroupByFilter(BaseSingleOptionFilter):
    slug = "group_by"
    label = "Group By"
    default_text = ugettext_noop("Group by...")

    @property
    def options(self):
        return [('value_chain', 'Value Chain'), ('domain', 'Domain'), ('practice', 'Practice')]