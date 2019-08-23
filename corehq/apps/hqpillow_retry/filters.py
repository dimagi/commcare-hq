from collections import defaultdict
from django.db.models.aggregates import Count
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter
from django.utils.translation import ugettext_noop as _
from pillow_retry.models import PillowError


class PillowErrorFilter(BaseDrilldownOptionFilter):
    slug = 'pillow_error'
    label = _('Filter errors')

    @property
    def drilldown_map(self):
        def err_item(val, name, val_count, next_list=None):
            ret = {
                'val': val,
                'text': '{} ({})'.format(name, val_count)
            }
            if next_list:
                ret['next'] = next_list

            return ret

        data = PillowError.objects.values('pillow', 'error_type').annotate(num_errors=Count('id'))
        data_map = defaultdict(list)
        pillow_counts = defaultdict(lambda: 0)
        for row in data:
            pillow = row['pillow']
            error = row['error_type']
            count = row['num_errors']
            data_map[pillow].append(err_item(error, error, count))
            pillow_counts[pillow] += count

        return [
            err_item(pillow, pillow.split('.')[-1], pillow_counts[pillow], errors)
            for pillow, errors in data_map.items()
        ]

    @classmethod
    def get_labels(cls):
        return [
            (_('Pillow Class'), 'Select pillow...', 'pillow'),
            (_("Error Type"), 'Select error...', 'error'),
        ]
