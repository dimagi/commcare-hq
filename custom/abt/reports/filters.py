from django.utils.translation import ugettext_lazy

from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from custom.abt.reports.fixture_utils import (
    get_data_types_by_tag,
    get_fixture_dicts,
)


class VectorLinkLocFilter(BaseSingleOptionFilter):
    default_text = 'All'

    def get_level_2s(self, level_1_ids):
        data_types_by_tag = get_data_types_by_tag(self.domain)
        return get_fixture_dicts(
            self.domain,
            data_types_by_tag["level_2_dcv"]._id,
            filter_in={'level_1_dcv': level_1_ids}
        )

    def get_level_3s(self, level_2_ids):
        data_types_by_tag = get_data_types_by_tag(self.domain)
        return get_fixture_dicts(
            self.domain,
            data_types_by_tag["level_3_dcv"]._id,
            filter_in={'level_2_dcv': level_2_ids}
        )


class LevelOneFilter(VectorLinkLocFilter):
    slug = 'level_1'
    label = ugettext_lazy('Level 1')

    @property
    def options(self):
        data_types_by_tag = get_data_types_by_tag(self.domain)
        level_1s = get_fixture_dicts(
            self.domain,
            data_types_by_tag["level_1_dcv"]._id,
        )
        return [(loc['id'], loc['name']) for loc in level_1s]


class LevelTwoFilter(VectorLinkLocFilter):
    slug = 'level_2'
    label = ugettext_lazy('Level 2')

    @property
    def options(self):
        level_1 = self.request.GET.get('level_1')
        l1_ids = [level_1] if level_1 else None
        return [(loc['id'], loc['name']) for loc in self.get_level_2s(l1_ids)]


class LevelThreeFilter(VectorLinkLocFilter):
    slug = 'level_3'
    label = ugettext_lazy('Level 3')

    @property
    def options(self):
        level_1 = self.request.GET.get('level_1')
        level_2 = self.request.GET.get('level_2')
        if level_2:
            l2_ids = [level_2]
        elif level_1:
            l1_ids = [level_1]
            l2_ids = [loc['id'] for loc in self.get_level_2s(l1_ids)]
        else:
            l2_ids = None
        return [(loc['id'], loc['name']) for loc in self.get_level_3s(l2_ids)]


class LevelFourFilter(VectorLinkLocFilter):
    slug = 'level_4'
    label = ugettext_lazy('Level 4')

    @property
    def options(self):
        level_1 = self.request.GET.get('level_1')
        level_2 = self.request.GET.get('level_2')
        level_3 = self.request.GET.get('level_3')
        if level_3:
            l3_ids = [level_3]
        elif level_2:
            l2_ids = [level_2]
            l3_ids = [loc['id'] for loc in self.get_level_3s(l2_ids)]
        elif level_1:
            l1_ids = [level_1]
            l2_ids = [loc['id'] for loc in self.get_level_2s(l1_ids)]
            l3_ids = [loc['id'] for loc in self.get_level_3s(l2_ids)]
        else:
            l3_ids = None
        data_types_by_tag = get_data_types_by_tag(self.domain)
        level_4s = get_fixture_dicts(
            self.domain,
            data_types_by_tag["level_4_dcv"]._id,
            filter_in={'level_3_dcv': l3_ids}
        )
        return [(loc['id'], loc['name']) for loc in level_4s]


class SubmissionStatusFilter(BaseSingleOptionFilter):
    slug = 'submission_status'
    label = ugettext_lazy('Submission Status')
    default_text = 'All'

    @property
    def options(self):
        return [
            ('missing_pmt_data', ugettext_lazy('No PMT Data Submitted')),
            ('incorrect_pmt_data', ugettext_lazy('Incorrect PMT Data Submitted')),
        ]
