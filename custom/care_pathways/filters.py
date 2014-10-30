from django.utils.translation import ugettext_noop
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter
from corehq.apps.reports.filters.select import YearFilter
from corehq.apps.users.models import CommCareUser
from custom.care_pathways.sqldata import GeographySqlData
from custom.care_pathways.utils import get_domain_configuration, ByTypeHierarchyRecord
from dimagi.utils.decorators.memoized import memoized


class CareBaseDrilldownOptionFilter(BaseDrilldownOptionFilter):
    single_option_select = -1
    single_option_select_without_default_text = -1

    @property
    def filter_context(self):
        controls = []
        for level, label in enumerate(self.rendered_labels):
            if len(label) == 2:
                controls.append({
                    'label': label[0],
                    'slug': label[1],
                    'level': level,
                })
            else:
                controls.append({
                    'label': label[0],
                    'default_text': label[1],
                    'slug': label[2],
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
            'single_option_select': self.single_option_select,
            'single_option_select_without_default_text': self.single_option_select_without_default_text
        }


class GeographyFilter(CareBaseDrilldownOptionFilter):
    label = ugettext_noop("Geography")
    slug = "geography"
    template = "care_pathways/filters/drilldown_options.html"

    @property
    def drilldown_map(self):
        hierarchy = helper = []
        hierarchy_config = sorted([k for k in get_domain_configuration(self.request.domain).geography_hierarchy.keys()])
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
                    if not hierarchy:
                        hierarchy.append(dict(val='0', text='All', next=[]))
                    hierarchy.append(tmp)
                    hierarchy = tmp['next']
                else:
                    hierarchy = tmp_next
            hierarchy = helper

        return hierarchy

    def get_labels(self):
        return [(v['name'], v['prop']) for k, v in sorted(get_domain_configuration(
            self.request.domain).geography_hierarchy.iteritems())]

    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[1])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[1])))
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


class ScheduleFilter(CareBaseDrilldownOptionFilter):
    slug = "farmer_social_category"
    label = "Farmer Social Category"
    template = "care_pathways/filters/drilldown_options.html"

    @property
    def drilldown_map(self):
        return [dict(val='0', text='All', next=[]), dict(val='sc', text='SC', next=[]),
                dict(val='st', text='ST', next=[]), dict(val='obc', text='OBC', next=[]),
                dict(val='other', text='Other', next=[])]

    @classmethod
    def get_labels(cls):
        return [('', 'farmer_social_category')]

    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[1])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[1])))
        return {
            'slug': slug,
            'value': val,
        }


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
        for value_chain in hierarchy_config:
            value_chain.next.insert(0, ByTypeHierarchyRecord(val='0', text='All', next=[]))
            for domain in value_chain.next:
                domain.next.insert(0, ByTypeHierarchyRecord(val='0', text='All', next=[]))

        return hierarchy_config

    @classmethod
    def get_labels(cls):
        return [('Value Chain', 'Any', 'value_chain'), ('Domain', 'domain'), ('Practice', 'practice')]

    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[2]) if len(label) == 3 else str(label[1])
        val = request.GET.getlist('%s_%s' % (cls.slug, slug))
        return {
            'slug': slug,
            'value': val,
        }


class TypeFilterWithoutPractices(TypeFilter):
    @classmethod
    def get_labels(cls):
        return [('Value Chain', 'Any', 'value_chain'), ('Domain', '', 'domain')]


class GroupByFilter(BaseSingleOptionFilter):
    slug = "group_by"
    label = "Group By"
    default_text = ''

    @property
    def options(self):
        return [('value_chain', 'Value Chain'), ('domain', 'Domain'), ('practice', 'Practice')]


class DisaggregateByFilter(BaseSingleOptionFilter):
    slug = "disaggregate_by"
    label = "Disaggregate By"
    default_text = ''

    @property
    def options(self):
        return [('group', 'Group Leadership'), ('sex', 'Sex of Members')]


    @property
    @memoized
    def selected(self):
        return self.get_value(self.request, self.domain) or "sex"


class TableCardGroupByFilter(BaseSingleOptionFilter):
    slug = "group_by"
    label = "Group By"
    default_text = ''

    @property
    def options(self):
        return [('group_name', 'Group Name'), ('group_leadership', 'Group Leadership'),
                ('gender', 'Sex of Members')]

    @property
    @memoized
    def selected(self):
        return self.get_value(self.request, self.domain) or "group_name"

class TableCardTypeFilter(TypeFilter):
    single_option_select_without_default_text = 1

    @property
    def selected(self):
        selected = super(TableCardTypeFilter, self).selected
        if len(selected) == 0 and len(self.drilldown_map) > 0:
            # No data selected, select first element from top hierarchy
            selected.append([self.drilldown_map[0].val])
        return selected

