from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy

from corehq.apps.reports.v2.models import BaseColumnFilter, FilterChoiceMeta


class TextCaseColumnFilter(BaseColumnFilter):
    filter_type = 'column_text'
    title = ugettext_lazy("Text")
    choices = [
        FilterChoiceMeta('contains', ugettext_lazy('Contains')),
        FilterChoiceMeta('equals', ugettext_lazy('Equals')),
        FilterChoiceMeta('not_contains', ugettext_lazy('Does Not Contain')),
        FilterChoiceMeta('not_equals', ugettext_lazy('Does Not Equal')),
    ]

    def get_filtered_query(self, query, config):
        # todo
        return query
