from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop

from corehq.apps.reports.v2.models import BaseColumnFilter, FilterChoiceMeta


class TextCaseColumnFilter(BaseColumnFilter):
    filter_type = 'column_text'
    choices = [
        FilterChoiceMeta('contains', ugettext_noop('Contains')),
        FilterChoiceMeta('is_exactly', ugettext_noop('Is Exactly')),
    ]

    def get_filtered_query(self, query, config):
        # todo
        return query
