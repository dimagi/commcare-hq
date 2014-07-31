import json
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter, MultiLocationFilter
from custom.care_pathways.api.v0_1 import GeographySqlData
from casexml.apps.case.models import CommCareCase


class GeographyFilter(MultiLocationFilter):
    label = ugettext_noop("Geography")
    slug = "geography"
    hierarchy = [{"type": "lvl_1", "display": "name"},
                 {"type": "lvl_2", "parent_ref": "lvl_1"},
                 {"type": "lvl_3", "parent_ref": "lvl_2"},
                 {"type": "lvl_4", "parent_ref": "lvl_3"},
                 {"type": "lvl_5", "parent_ref": "lvl_4"}]

    @property
    def api_root(self):
        return reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                        'resource_name': 'geography',
                                                        'api_name': 'v0.5'})

    @property
    def filter_context(self):
        api_root = reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                        'resource_name': 'geography',
                                                        'api_name': 'v0.5'})
        selected_id = self.request.GET.getlist('fixture_id')

        context = {}
        context.update({
            'api_root': api_root,
            'control_name': self.label,
            'control_slug': self.slug,
            'selected': json.dumps(GeographySqlData(self.domain, selected_ids=selected_id).path),
            'fdis': json.dumps(GeographySqlData(self.domain, selected_ids=selected_id).data),
            'hierarchy': self.hierarchy
        })
        return context

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
