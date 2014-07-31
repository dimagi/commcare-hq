from django.utils.translation import ugettext_noop
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter
from corehq.apps.reports.filters.select import YearFilter
from casexml.apps.case.models import CommCareCase
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
        hierarchy_config = sorted([k for k in get_domain_configuration('pathways-india-mis')['geography_hierarchy'].keys()])
        data = GeographySqlData('pathways-india-mis').get_data()
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

    @classmethod
    def get_labels(cls):
        return [(v['name'], '', v['prop']) for k,v in get_domain_configuration('pathways-india-mis')['geography_hierarchy'].iteritems()]


    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[2])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[2])))
        print {
            'slug': slug,
            'value': val,
        }
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
        return [('all_woman', 'All Women'), ('some_women', 'Some Women'), ('no_women', 'No Women')]


class GroupLeadershipFilter(BaseSingleOptionFilter):
    slug = "group_leadership"
    label = "Group Leadership"
    default_text = "Any"

    @property
    def options(self):
        return [('all_woman', 'All Women'), ('some_women', 'Some Women'), ('no_women', 'No Women')]


class CBTNameFilter(BaseSingleOptionFilter):
    slug = 'cbt_name'
    label = ugettext_noop('CBT Name')
    default_text = "All"

    @property
    def options(self):
        return [(awc, awc) for awc in get_user_data_set()]


def get_user_data_set():
    cases = CommCareCase.view("case/all_cases", key=["all", "pathways-india-mis", "*"], include_docs=True, reduce=False).all()
    return sorted(list(set(u.group_name.get('group_name') for u in cases)))


class ScheduleCasteFilter(BaseSingleOptionFilter):
    slug = "schedule_caste"
    label = "Schedule Caste"
    default_text = "All"

    @property
    def options(self):
        return []


class ScheduleTribeFilter(BaseSingleOptionFilter):
    slug = "schedule_tribe"
    label = "Schedule Tribe"
    default_text = "All"

    @property
    def options(self):
        return []


class PPTYearFilter(YearFilter):
    label = "PPT Year"


class TypeFilter(CareBaseDrilldownOptionFilter):
    single_option_select = 0
    label = "Filter by Type"
    slug = "type"
    template = "care_pathways/filters/drilldown_options.html"

    @property
    def drilldown_map(self):
        return [
            {
                'val': 'Paddy',
                'text': 'Paddy',
                'next': [
                        {
                            'val': 'domain1',
                            'text': 'Domain1',
                            'next': [
                                {
                                    'val': 'practice1',
                                    'text': 'Pracice1',
                                }
                            ]
                        },
                        {
                            'val': 'domain2',
                            'text': 'Domain2',
                            'next': [
                                {
                                    'val': 'practice2',
                                    'text': 'Pracice2',
                                }
                            ]
                        }
                    ]
            },
            {
                'val': 'Maize',
                'text': 'Maize',
                'next': [
                        {
                            'val': 'domain3',
                            'text': 'Domain3',
                            'next': [
                                {
                                    'val': 'practice3',
                                    'text': 'Pracice3',
                                }
                            ]
                        }
                    ]
            }
        ]

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
        print {
            'slug': slug,
            'value': val,
        }
        return {
            'slug': slug,
            'value': val,
        }
